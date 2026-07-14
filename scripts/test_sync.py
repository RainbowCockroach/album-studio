"""GUI-free CLI to exercise ServerSyncService against a running server.

Run the server repo locally (`npm run dev` in ../album-studio-server) then:

    python3 -m scripts.test_sync list
    python3 -m scripts.test_sync pull <dest_dir>

Server URL and token are read from Album Studio's settings.json (the same
values the desktop app uses), or overridden via env:

    ALBUM_STUDIO_SERVER_URL=http://localhost:3000 \
    ALBUM_STUDIO_TOKEN=secret \
    python3 -m scripts.test_sync list

This intentionally imports nothing from PyQt — it talks to the service directly.
"""

import os
import sys
from pathlib import Path

from src.models.config import Config
from src.services.server_sync_service import ServerSyncService, ServerSyncError
from src.utils.paths import get_user_data_dir


def _make_service() -> ServerSyncService:
    config = Config()
    base_url = os.environ.get("ALBUM_STUDIO_SERVER_URL") or config.get_setting("server_url", "") or ""
    token = os.environ.get("ALBUM_STUDIO_TOKEN") or config.get_setting("server_token", "") or ""
    ledger_path = os.path.join(get_user_data_dir(), "pulled_photos.json")
    if not base_url:
        sys.exit("No server URL — set server_url in settings or ALBUM_STUDIO_SERVER_URL.")
    return ServerSyncService(base_url, token, ledger_path)


def cmd_test() -> None:
    service = _make_service()
    ok, message = service.test_connection()
    print(("OK: " if ok else "FAIL: ") + message)
    sys.exit(0 if ok else 1)


def cmd_list() -> None:
    service = _make_service()
    new = service.get_new_photos_auto()
    groups = service.group_by_month(new)
    total = sum(p.size for p in new)
    print(f"{len(new)} new photos, {total} bytes, last_pull_month={service.last_pull_month}")
    for month in sorted(groups):
        print(f"  {month}: {len(groups[month])} photos")
        for p in groups[month]:
            cap = p.captured_at.isoformat() if p.captured_at else "—"
            print(f"    {p.hash[:12]}  {p.original_name!r}  captured={cap}")


def cmd_pull(dest_root: str) -> None:
    service = _make_service()
    new = service.get_new_photos_auto()
    if not new:
        print("No new photos.")
        return
    groups = service.group_by_month(new)
    advance_month = min(p.uploaded_at.strftime("%Y-%m") for p in new)
    downloaded = failed = 0
    for month in sorted(groups):
        dest_dir = Path(dest_root) / month / "input"
        for photo in groups[month]:
            try:
                path = service.download(photo, dest_dir, month)
                downloaded += 1
                print(f"  ✓ {month}/{path.name}")
            except ServerSyncError as e:
                failed += 1
                print(f"  ✗ {photo.original_name or photo.hash}: {e}")
    service.set_last_pull_month(advance_month)
    print(f"Done: {downloaded} downloaded, {failed} failed.")


def main(argv: list) -> None:
    if not argv:
        sys.exit("Usage: test_sync.py <test|list|pull> [dest_dir]")
    cmd = argv[0]
    if cmd == "test":
        cmd_test()
    elif cmd == "list":
        cmd_list()
    elif cmd == "pull":
        if len(argv) < 2:
            sys.exit("Usage: test_sync.py pull <dest_dir>")
        cmd_pull(argv[1])
    else:
        sys.exit(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main(sys.argv[1:])
