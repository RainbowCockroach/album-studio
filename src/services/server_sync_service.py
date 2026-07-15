"""Server sync service — pull new photos from the home transfer hub.

Pure logic, no Qt imports, so it can be exercised from a REPL or the
`scripts/test_sync.py` CLI. Networking uses only the Python standard library
(`urllib`) — no heavy dependencies are added for this feature.

Design notes (full spec: docs/SERVER_SYNC.md):
- The server is stateless about consumption. "What's new" = server list minus
  the local pull ledger (`pulled_photos.json`), which records every hash already
  fetched. Photos are content-addressed by SHA-256.
- Photos auto-organize into month-named projects ("YYYY-MM"); the month comes
  from each photo's `capturedAt`, falling back to `uploadedAt` when null. The
  desktop never re-derives capture time from the downloaded bytes.
"""

import hashlib
import json
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

# urllib exposes a single socket timeout per request; we use a short one for the
# small JSON/health calls and a long one for streaming photo downloads.
LIST_TIMEOUT = 10      # connect + read for /health and /photos listing
DOWNLOAD_TIMEOUT = 120  # read for streaming photo bytes


class ServerSyncError(Exception):
    """Raised for any sync failure with a user-readable message."""


class RemotePhoto:
    """A single photo as advertised by the server's /photos listing."""

    def __init__(self, hash: str, original_name: str, ext: str, size: int,
                 uploaded_at: datetime, captured_at: Optional[datetime]):
        self.hash = hash
        self.original_name = original_name
        self.ext = ext
        self.size = size
        self.uploaded_at = uploaded_at
        self.captured_at = captured_at

    @property
    def target_month(self) -> str:
        """Month project name ("YYYY-MM"): capturedAt, else uploadedAt."""
        when = self.captured_at or self.uploaded_at
        return when.strftime("%Y-%m")

    @classmethod
    def from_json(cls, data: dict) -> "RemotePhoto":
        """Build from one entry of the /photos response.

        Parses timestamps defensively — `capturedAt` originates from phone EXIF
        and may be malformed; on parse failure it is treated as None. A missing
        or unparseable `uploadedAt` falls back to epoch so the photo still sorts
        and groups deterministically rather than crashing the whole pull.
        """
        uploaded_at = _parse_iso(data.get("uploadedAt")) or datetime.fromtimestamp(0)
        captured_at = _parse_iso(data.get("capturedAt"))
        return cls(
            hash=str(data.get("hash", "")),
            original_name=str(data.get("originalName", "")),
            ext=str(data.get("ext", "")),
            size=int(data.get("size", 0) or 0),
            uploaded_at=uploaded_at,
            captured_at=captured_at,
        )


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO 8601 string defensively; return None on any failure."""
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    # Accept a trailing 'Z' (UTC) which datetime.fromisoformat rejects on <3.11.
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        # Fall back to a plain date or the leading date portion of a timestamp.
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return None


# Characters that are unsafe in a filename on common filesystems.
_UNSAFE_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class ServerSyncService:
    """Lists, filters and downloads new photos, tracking a local pull ledger."""

    def __init__(self, base_url: str, token: str, ledger_path: str):
        self.base_url = (base_url or "").rstrip("/")
        self.token = token or ""
        self.ledger_path = ledger_path
        self._ledger: Optional[dict] = None

    # ------------------------------------------------------------------ HTTP

    def _request(self, path: str, timeout: int, auth: bool = True):
        """Open an authenticated request to the server, returning the response.

        Caller is responsible for closing the returned response object.
        Raises ServerSyncError with a user-readable message on any failure.
        """
        if not self.base_url:
            raise ServerSyncError("No server URL configured.")

        url = f"{self.base_url}{path}"
        # Cloudflare's bot protection blocks the default "Python-urllib/x.y"
        # User-Agent with a 403 before requests reach the server; send a
        # neutral UA so the tunnel lets us through.
        headers = {"User-Agent": "AlbumStudio/1.0"}
        if auth:
            headers["x-api-key"] = self.token

        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise ServerSyncError("Unauthorized — check the server token.")
            if e.code == 404:
                raise ServerSyncError(f"Not found on server: {path}")
            raise ServerSyncError(f"Server error {e.code} for {path}.")
        except urllib.error.URLError as e:
            raise ServerSyncError(f"Cannot reach server at {self.base_url}: {e.reason}")
        except (TimeoutError, OSError) as e:
            raise ServerSyncError(f"Network error contacting server: {e}")

    def test_connection(self) -> Tuple[bool, str]:
        """Check /health (no auth) then a token-validating /photos listing."""
        if not self.base_url:
            return False, "No server URL configured."
        try:
            with self._request("/health", LIST_TIMEOUT, auth=False) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            if body.get("status") != "ok":
                return False, "Server health check did not report ok."
        except ServerSyncError as e:
            return False, str(e)
        except (json.JSONDecodeError, ValueError):
            return False, "Server health response was not valid JSON."

        # Validate the token by listing the current month.
        since = datetime.fromtimestamp(0).strftime("%Y-%m")
        try:
            since = _current_month()
        except Exception:
            pass
        try:
            self.list_remote(since)
        except ServerSyncError as e:
            return False, str(e)
        return True, "Connection OK — server reachable and token accepted."

    def list_remote(self, since: Optional[str]) -> List[RemotePhoto]:
        """Fetch the server photo listing, optionally filtered by `since` month."""
        path = "/photos"
        if since:
            path += "?" + urllib.parse.urlencode({"since": since})
        with self._request(path, LIST_TIMEOUT) as resp:
            try:
                body = json.loads(resp.read().decode("utf-8"))
            except (json.JSONDecodeError, ValueError):
                raise ServerSyncError("Server photo listing was not valid JSON.")
        photos = [RemotePhoto.from_json(p) for p in body.get("photos", [])]
        return [p for p in photos if p.hash]

    # ---------------------------------------------------------------- ledger

    def _load_ledger(self) -> dict:
        if self._ledger is None:
            if os.path.exists(self.ledger_path):
                try:
                    with open(self.ledger_path, "r") as f:
                        self._ledger = json.load(f)
                except (json.JSONDecodeError, OSError):
                    self._ledger = {}
            else:
                self._ledger = {}
            if not isinstance(self._ledger, dict):
                self._ledger = {}
        return self._ledger

    def _save_ledger(self) -> None:
        """Write the ledger atomically (temp file + rename)."""
        ledger = self._load_ledger()
        directory = os.path.dirname(self.ledger_path) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".pulled_", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(ledger, f, indent=2)
            os.replace(tmp, self.ledger_path)
        except OSError as e:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise ServerSyncError(f"Failed to write pull ledger: {e}")

    def is_pulled(self, hash: str) -> bool:
        ledger = self._load_ledger()
        return hash in ledger and hash != "_meta"

    @property
    def last_pull_month(self) -> Optional[str]:
        meta = self._load_ledger().get("_meta", {})
        if isinstance(meta, dict):
            month = meta.get("last_pull_month")
            return month if isinstance(month, str) else None
        return None

    def set_last_pull_month(self, month: str) -> None:
        ledger = self._load_ledger()
        meta = ledger.get("_meta")
        if not isinstance(meta, dict):
            meta = {}
            ledger["_meta"] = meta
        meta["last_pull_month"] = month
        self._save_ledger()

    # -------------------------------------------------------------- new list

    def get_new_photos(self, since: Optional[str]) -> List[RemotePhoto]:
        """Server listing minus everything already in the ledger."""
        remote = self.list_remote(since)
        return [p for p in remote if not self.is_pulled(p.hash)]

    def get_new_photos_auto(self) -> List[RemotePhoto]:
        """Like get_new_photos, choosing `since` from the ledger's last pull.

        First pull (no `_meta`) lists everything; afterwards passes
        `since=<last_pull_month>` — that month is cheaply re-listed and the
        ledger filters any re-downloads.
        """
        return self.get_new_photos(self.last_pull_month)

    @staticmethod
    def group_by_month(photos: List[RemotePhoto]) -> Dict[str, List[RemotePhoto]]:
        """Group photos by their target month ("YYYY-MM")."""
        groups: Dict[str, List[RemotePhoto]] = {}
        for photo in photos:
            groups.setdefault(photo.target_month, []).append(photo)
        return groups

    # ------------------------------------------------------------- download

    def _safe_filename(self, photo: RemotePhoto) -> str:
        """Pick a safe base filename: originalName, else `<hash>.<ext>`."""
        name = (photo.original_name or "").strip()
        name = os.path.basename(name)  # strip any path components
        if name:
            name = _UNSAFE_FILENAME.sub("_", name)
        if not name or name in (".", ".."):
            ext = (photo.ext or "").lstrip(".")
            name = f"{photo.hash}.{ext}" if ext else photo.hash
        return name

    def _unique_path(self, dest_dir: Path, filename: str) -> Path:
        """Return a non-colliding path in dest_dir, adding _2, _3… as needed."""
        candidate = dest_dir / filename
        if not candidate.exists():
            return candidate
        stem, ext = os.path.splitext(filename)
        counter = 2
        while True:
            candidate = dest_dir / f"{stem}_{counter}{ext}"
            if not candidate.exists():
                return candidate
            counter += 1

    def download(self, photo: RemotePhoto, dest_dir: Path, project: str,
                 progress_callback: Optional[Callable[[int, int], None]] = None) -> Path:
        """Stream a photo to `dest_dir`, verify its SHA-256, and ledger it.

        Streams to a temp file in the destination directory, verifies the bytes
        hash to the advertised `photo.hash`, then renames into place. On hash
        mismatch the temp file is removed and the photo is NOT recorded. The
        ledger is updated immediately after a successful download so an
        interrupted pull never re-fetches what already landed.

        Args:
            progress_callback: Optional callback(downloaded_bytes, total_bytes)
                fired per chunk. `total_bytes` is the size the server advertised
                in the listing, which is not re-derived from the stream — so a
                caller must tolerate a final `downloaded_bytes` that disagrees
                with it if the server under- or over-reported.
        """
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        fd, tmp_name = tempfile.mkstemp(prefix=".dl_", suffix=".part", dir=str(dest_dir))
        tmp_path = Path(tmp_name)
        sha = hashlib.sha256()
        downloaded = 0
        try:
            with self._request(f"/photos/{photo.hash}", DOWNLOAD_TIMEOUT) as resp:
                with os.fdopen(fd, "wb") as out:
                    while True:
                        chunk = resp.read(1024 * 256)
                        if not chunk:
                            break
                        sha.update(chunk)
                        out.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, photo.size)
        except ServerSyncError:
            tmp_path.unlink(missing_ok=True)
            raise
        except OSError as e:
            tmp_path.unlink(missing_ok=True)
            raise ServerSyncError(f"Failed downloading {photo.original_name or photo.hash}: {e}")

        digest = sha.hexdigest()
        if digest.lower() != photo.hash.lower():
            tmp_path.unlink(missing_ok=True)
            raise ServerSyncError(
                f"Hash mismatch for {photo.original_name or photo.hash} "
                f"(expected {photo.hash[:12]}…, got {digest[:12]}…)."
            )

        final_path = self._unique_path(dest_dir, self._safe_filename(photo))
        try:
            os.replace(str(tmp_path), str(final_path))
        except OSError as e:
            tmp_path.unlink(missing_ok=True)
            raise ServerSyncError(f"Failed saving {final_path.name}: {e}")

        self._record_pulled(photo.hash, project, final_path.name)
        return final_path

    def _record_pulled(self, hash: str, project: str, filename: str) -> None:
        ledger = self._load_ledger()
        ledger[hash] = {
            "pulled_at": _now_iso(),
            "project": project,
            "filename": filename,
        }
        self._save_ledger()


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _current_month() -> str:
    return datetime.now().strftime("%Y-%m")
