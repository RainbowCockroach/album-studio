# Server Sync Feature Specification

Guides Claude Code agents implementing the "Pull from server" feature in Album Studio (desktop). Read `CLAUDE.md` first — all of its conventions (signal flow through `MainWindow`, theme system, services-have-no-UI, PyQt6 enum paths, pyright on modified files) apply here without exception.

## Purpose

The owner uploads photos from his phone to a home server all month (sibling repos: `../album-studio-server/` — Node/Fastify transfer hub, `../album-studio-android/` — uploader). Once a month he opens this app and pulls everything new; pulled photos are **automatically organized into month-named projects** (`2026-06` etc.) based on when each photo was taken, then sorted/cropped/printed as usual. After download, the rest of the app must not know or care that photos came from a server.

## Core Design: Month Projects

Each photo carries a `capturedAt` timestamp (ISO 8601, nullable) determined **by the Android app at upload time** (EXIF → filename → MediaStore chain — the desktop never re-derives it from downloaded files). The pull groups photos by month:

- Project month = `capturedAt` truncated to `YYYY-MM`; if `capturedAt` is null, fall back to the month of `uploadedAt`.
- Destination: `{workspace}/{YYYY-MM}/input/` — exactly the folder shape `ProjectManager._discover_workspace_projects()` already auto-registers (any workspace folder containing `input/`). Project name = `YYYY-MM`.
- One pull may touch several month projects; create only the ones that actually receive photos.
- If a month project already exists (registered or as a folder), download into its existing `input/` — never duplicate or rename the project.
- After download, register new projects explicitly via `ProjectManager` (or re-run `load_projects()`, which triggers discovery) and refresh the project list UI so new months appear immediately.

## Core Design: Local Pull Ledger

The server is **stateless by design** — it never tracks what was downloaded. Photos are content-addressed by SHA-256. The desktop keeps a **pull ledger** recording which hashes it has already fetched; "what's new" = server list minus ledger.

- Ledger file: `pulled_photos.json` in the app-support dir (same dir as project metadata: `~/Library/Application Support/AlbumStudio/` on macOS, `%APPDATA%\AlbumStudio\` on Windows — reuse the existing path helper).
- Format: `{"<hash>": {"pulled_at": "<ISO8601>", "project": "<YYYY-MM project name>", "filename": "<saved filename>"}}`
- Write atomically (temp file + rename). Update after **each** successful file download, not once at the end — a pull interrupted at photo 30/100 must not re-download the first 30.
- A photo deleted from the project later does NOT come off the ledger — pulled is pulled. (Re-pull of specific photos is a non-goal; manual ledger edit is the escape hatch.)

## API Contract (duplicate — canonical copy lives in `../album-studio-server/CLAUDE.md`)

Base URL and token come from settings. All routes except `/health` require an API key in the `x-api-key` header.

| Method & Path | Response |
|---|---|
| `GET /health` (no auth) | `200 {"status": "ok"}` |
| `GET /photos?since=YYYY-MM` | `200 {"photos": [{"hash", "originalName", "ext", "size", "uploadedAt", "capturedAt"}]}` sorted by uploadedAt ascending; `since` = include that upload-month and later; `capturedAt` may be null |
| `GET /photos/{hash}` | `200` photo bytes, `Content-Disposition: attachment; filename="<originalName>"`; `404` unknown |

`401 {"error": "unauthorized"}` on bad token. The server is HTTPS behind Cloudflare Tunnel; plain `http://` must also work (LAN testing).

## Implementation

### 1. Settings (`src/models/config.py` + settings UI)

Two new keys in `settings.json`: `server_url` (string, default `""`), `server_token` (string, default `""`). The shallow merge of bundled-under-user already propagates new keys; add the defaults to the bundled `config/settings.json`. Expose both in the existing settings dialog, plus a "Test connection" button (calls `GET /health`, then `GET /photos?since=<current month>` to validate the token). Token is stored plainly in the user settings file — acceptable for this single-user tool; do not invent a keychain integration.

### 2. Service (`src/services/server_sync_service.py`)

Pure logic, no Qt imports. Use `requests` if already feasible, else stdlib `urllib` — do NOT add heavy dependencies.

```python
class ServerSyncService:
    def test_connection(self) -> tuple[bool, str]              # (ok, message)
    def list_remote(self, since: str | None) -> list[RemotePhoto]
    def get_new_photos(self, since: str | None) -> list[RemotePhoto]   # list_remote minus ledger
    def group_by_month(self, photos: list[RemotePhoto]) -> dict[str, list[RemotePhoto]]
        # "YYYY-MM" -> photos; month from captured_at, falling back to uploaded_at
    def download(self, photo: RemotePhoto, dest_dir: Path, project: str) -> Path
        # streams to disk, verifies sha256, records {project, filename} in ledger
```

`RemotePhoto` carries `hash`, `original_name`, `ext`, `size`, `uploaded_at: datetime`, `captured_at: datetime | None`, and a `target_month` property implementing the fallback. Parse `capturedAt` defensively — it originates from phone EXIF; on parse failure treat as None.

- `download()` streams to a temp file in `dest_dir`, **verifies the SHA-256 matches the advertised hash**, then renames into place. Mismatch → raise, do not ledger it.
- Filename on disk: `originalName`, with `_2`, `_3`… suffix on collision within `dest_dir`; fall back to `<hash>.<ext>` if originalName is empty/unsafe. Record the final name in the ledger.
- Sensible timeouts (connect 10s, read 120s) and clear exception messages — these surface in the UI.

### 3. UI Flow

Follow the existing convention exactly: widgets emit signals, `MainWindow` handles them, widgets never talk to each other.

- Add a **"Pull from server"** button to `ProjectToolbar` (styled via `retro_button_style` constants in `theme.py` — never inline styles). Signal → `MainWindow.on_pull_from_server_requested`.
- Handler flow:
  1. If `server_url`/`server_token` unset → message box pointing to settings.
  2. Fetch the new-photo list on a worker (QThread or existing worker pattern — check how "Find similar" does background work and mirror it). Never call the network on the UI thread.
  3. Group by month and show confirmation with the breakdown, e.g.: "44 new photos (210 MB): 2026-05 → 3, 2026-06 → 41. Download?" No project needs to be open — destinations are the month projects, created as needed.
  4. Download each photo into `{workspace}/{YYYY-MM}/input/` on the worker thread with a progress dialog (current/total + filename, cancellable between files).
  5. On finish (or cancel partway): report "Downloaded N photos into M projects (K failed)", register any new month projects with `ProjectManager`, and refresh the project list/grid so the new months appear immediately.
- Network/auth errors → user-readable message box; never a stack trace, never a silent failure.

### 4. `since` Optimization

First pull: no `since` (full list). Afterwards store `last_pull_month` ("YYYY-MM") in the ledger file (top-level key `"_meta"`) and pass `since=<that month>` — the month itself is re-listed (cheap) and the ledger filters re-downloads. Keep the full-list fallback trivial to trigger (e.g. if `_meta` missing).

## Testing

There is no automated test suite in this repo (manual testing only — see CLAUDE.md). Still:
- Keep `ServerSyncService` import-clean of Qt so it can be exercised from a REPL.
- Add `scripts/test_sync.py`: a small CLI (`python3 -m scripts.test_sync list|pull <dir>`) that exercises the service against a running server (the server repo runs locally via `npm run dev`) without launching the GUI.
- Manual end-to-end checklist: configure settings → pull into a scratch workspace → verify month project folders, files + ledger → pull again → verify zero downloads → verify the new month projects appear in the project dropdown → run `pyright` on all modified files.

## Non-Goals — Do NOT Build

- No upload from desktop, no delete-on-server, no server-side read state, no background/automatic sync, no multi-server support. One button, pulled monthly, that's all.
- No manual target-project selection and no re-deriving capture time from downloaded files (EXIF reading for grouping) — `capturedAt` from the server listing is authoritative; month grouping is the only mode.
