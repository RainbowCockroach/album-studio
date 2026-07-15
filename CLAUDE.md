# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Album Studio is a PyQt6 desktop app for organizing and batch-cropping photos. Users create projects, tag images with size group + print size, preview/adjust smart crops, apply vintage date stamps, then export. Also includes AI similarity search (ResNet50).

**Tech Stack:** Python 3.13+, PyQt6, Pillow, PyTorch (ResNet50), smartcrop, pillow-heif

## Commands

Activate the venv first in every new shell. Without it a bare `python3`
resolves to Anaconda, which has no PyQt6, and every command below dies at
import. (If activation ever looks like it succeeded but `which python3` still
points outside `.venv`, the venv has been moved — venvs are not relocatable;
recreate it rather than editing its paths.)

```bash
source .venv/bin/activate   # run this first, from the repo root

# Run (MUST use module form — relative imports require it)
python3 -m src.main

# Install dependencies
pip install -r requirements.txt

# Build macOS app
python3 build.py macos

# Type check (pyrightconfig.json pins venvPath/venv, so this needs no activation)
pyright src/
pyright src/path/to/file.py   # single file

# Run the test suite (pure-logic layers: models/ + services/, no Qt widgets)
pip install -r requirements-dev.txt   # first time — installs pytest
python3 -m pytest                      # from repo root; config in pytest.ini
python3 -m pytest tests/test_config.py # single file
```

**Tests** live in `tests/` and cover `models/` and `services/` (config
parsing/migration, server-sync ledger + SHA-256 verify, project CRUD/discovery,
crop geometry, date-stamp helpers). UI widgets are intentionally untested, with
the exceptions below, all pinning Qt-only faults that no service test could see:

- `tests/test_main_window_pull.py` — the "Pull from Server" dialog handlers,
  where a Qt-only bug made the button silently do nothing while every service
  test stayed green. It uses the session-scoped `qapp` fixture and builds a
  `MainWindow` via `__new__` + `QMainWindow.__init__`, skipping the real
  `__init__` (which reads user config and hits the network).
- `tests/test_image_viewer_nav.py` — the image viewer's Left/Right browsing,
  which a default focus policy would silently swallow (see the QScrollArea note
  below). Keys are sent through `dialog.focusWidget()`, not to the dialog, so
  the test exercises the real focus chain; `QTest.keyClick(dialog, …)` bypasses
  the bug and passes either way.
- `tests/test_image_viewer_render.py` — the viewer's off-thread render cache,
  where the faults are ordering ones a service test cannot express: a late
  render painting over the photo the user already arrowed to, or a cache key
  too coarse to notice a date-stamp toggle. It drives `_on_render_done`
  directly rather than racing the thread pool.
- `tests/test_card_grid.py` (+ the thin `test_image_grid.py` /
  `test_find_similar_dialog.py`) — card sizing and column reflow, where
  QGridLayout quietly stretched four photos across the whole window while the
  suite stayed green. See "Card Grid Layout" below. `CardGrid`'s tests use
  plain fixed-size `QWidget`s, since it never looks inside a card.

Reuse those patterns if a widget bug ever again proves untestable from the
service layer. Layout assertions need a `show()` and a `processEvents()` — an
unshown widget reports a default 640×480 and will pass anything. Bind widgets
to a name, too: `Card(...).layout().itemAt(0).widget()` lets Python collect the
card mid-expression and take its Qt children with it.

**Always lint modified files when finishing a task:** `pyright src/path/to/modified_file.py`

**Always build-check when finishing a task** — run this *before* `pytest`, so a syntax or
import error names its own file and line instead of blowing up the test run:

```bash
pyright src/                      # types + syntax across the app
python3 -c "import src.main"      # real import: catches syntax/import errors in widgets
```

The import matters because `tests/` covers `models/` and `services/` (plus the one Qt
test above). A broken `src/ui/` file passes the entire suite and fails only when the
app starts — importing `src.main` pulls in `MainWindow` and every widget, so it
surfaces immediately.
`QApplication` is constructed inside `main()` behind the `__main__` guard, so importing
does not open a window. Run the full `python3 build.py macos` only when packaging or when
the change touches `build.py`, `config/`, or `assets/`.

## Architecture

### MVC-Like Structure

- **`src/models/`** — `Config`, `Project`, `ImageItem`. Pure data, no UI.
- **`src/services/`** — `ProjectManager`, `CropService`, `ImageProcessor`, `ImageSimilarityService`, `DateStampService`. Business logic, no UI.
- **`src/ui/`** — `MainWindow` orchestrates everything. Widgets and dialogs emit signals; `MainWindow` handles them all.

### Critical: Widgets Never Talk to Each Other

All widget-to-widget communication goes through `MainWindow` via signals. Never connect a widget's signal directly to another widget.

### Signal Flow (abbreviated)

```
ProjectToolbar  →  MainWindow.on_project_changed / on_new_project / on_archive_requested …
ImageGrid       →  MainWindow.on_image_clicked (apply tag) / on_image_double_clicked (clear tag) …
ToolbarBottom   →  MainWindow.on_crop_requested / on_refresh_requested / on_find_similar_requested …
```

### Theme System — CRITICAL

All colors and stylesheets live in `src/ui/theme.py`. **Never hardcode hex colors or inline stylesheets in widget files.**

- Use `card_style()` for image card `QFrame` styles
- Use `retro_button_style(bg, text, pressed, hover)` for buttons, stored as `STYLE_*` constants
- Use `lighten_color()` to derive tints
- `GLOBAL_STYLESHEET` is applied once in `main.py`; widgets get retro styling automatically via object names (`setObjectName`)

**Scope every stylesheet rule to an object name.** A stylesheet set on a widget
also applies to its children, and Qt's class selectors match subclasses — most
of all, `QLabel` *is a* `QFrame`. A bare `QFrame { … }` rule on an image card
therefore drew the card's background, border and radius around its own
thumbnail, filename and tag labels, boxing each one inside the card. Hence
`QFrame#imageCard` in `card_style()`.

### Card Grid Layout — CRITICAL

Every grid of photos in the app is a `CardGrid`
(`src/ui/widgets/card_grid.py`) — the main `ImageGrid` and the similar-images
results both. Cards are a **fixed** `card_size(thumbnail_size)` (theme.py) and
the grid reflows its *column count* to the viewport width — never the reverse.
`CardGrid` never resizes a card, so a caller handing it a self-sizing widget
gets the stretching straight back.

Three things keep it that way, and dropping any one brings the stretch back:

- Cards set `setFixedSize` + a `Fixed` size policy.
- `_rebuild_layout()` puts a stretch column and row *past* the last card, so
  `QGridLayout` has somewhere to dump leftover space. Without them it inflates
  the card cells instead — four photos in a wide window became four ~490px-wide
  cards. Fixed-size cards alone are **not** enough: the cells still widen and
  the cards just drift apart across them, which looks the same.
- Columns are re-derived from the **scroll viewport** width (via an event
  filter on it), not from the grid widget's own width: a vertical scrollbar
  appearing narrows the viewport without ever resizing the grid.

There is deliberately no column-count setting — `thumbnail_size` is the only
knob, and the count follows from it. Guarded by `tests/test_card_grid.py`
(layout) and `tests/test_theme.py` (the geometry maths, no Qt needed); the
per-caller tests pin only that the cards handed over are fixed-size.

One card shape serves the whole app: a thumbnail square, a full-size text row
and a small caption row. The two rows are named for their type, not their
content, because the two grids fill them differently — hence
`CARD_TEXT_HEIGHT`/`CARD_CAPTION_HEIGHT` rather than tag/filename.

**A stylesheet background or border will not paint on a bare `QWidget`
subclass** — it has no styled `paintEvent`, so the rule is silently ignored.
The similar-images card set one for years and drew nothing. Subclass `QFrame`
(as both cards now do), or set `WA_StyledBackground`.

### Configuration System

Two config layers:

- **Bundled** (`config/` in repo / app bundle): read-only defaults
- **User** (`~/Library/Application Support/AlbumStudio/config/` on macOS, `%APPDATA%\AlbumStudio\config\` on Windows): written when user saves via UI

**`settings.json`** — pure app settings only. Loader shallow-merges bundled under user (`{**bundled, **user}`) so new keys reach existing users on upgrade.

**`size_group.json`** — user data (groups + per-size cost/color). User file fully overrides bundled; no merging. Format:

```json
{
  "groups": { "<group>": { "sizes": [{"ratio", "alias"}, ...] } },
  "sizes":  { "<ratio>": { "cost": float, "color": "#hex" } }
}
```

Cost and color are keyed by size **ratio** (e.g. `"9x6"`), not by group — so `9x6` in A4 and A5 share the same cost/color. Public API is unchanged: `Config.get_size_cost()`, `set_size_cost()`, `get_size_color()`, `set_size_color()` all read/write `self.size_metadata`.

`_migrate_size_group_data()` handles three legacy formats and pulls any old `size_costs`/`size_colors` out of `settings.json` into `size_metadata` on first load. Sizes without a color get a random one assigned automatically.

Ratios are parsed directly from size names via `Config.parse_size_ratio()` (e.g. `"9x6"` → 1.5). There is no `sizes.json`.

### PyQt6 Enums — CRITICAL

Always use full enum paths, never integers:

```python
# Correct
pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
# Wrong — fails in PyQt6
pixmap.scaled(w, h, aspectRatioMode=1, transformMode=1)
```

### Lazy Loading

Heavy dependencies are deferred to first use:
- `ImageSimilarityService` (and ResNet50 model, ~500MB) — only instantiated when user clicks "Find similar"
- Thumbnails — generated on demand via `ImageItem.get_thumbnail()`, cached in `_thumbnail`
- Feature vectors — computed once, cached in-memory and in `.cache/feature_cache.npz`

### Smartcrop Must Run on a Downscaled Copy — CRITICAL

**Never hand a full-resolution photo to `smartcrop.crop()`.** Its cost scales
with pixel count: a 12MP phone photo took **9 seconds**, versus 0.29s at 1200px,
for a crop offset differing by ~6% of image height. It only picks a *region*, so
full resolution buys nothing.

The trap is that smartcrop *has* a built-in prescale which looks like it handles
this, and it never fires here. It engages only when the requested crop is much
smaller than the source, but `get_crop_dimensions()` asks for the **largest**
crop that fits — 4000px wide out of a 4000px-wide photo. That pins smartcrop's
internal `scale` at 1.0, so `prescale_size` lands at exactly 1.0, misses its
`< 1` branch, and every pixel gets analysed.

So downscale at the call site. `CropService._find_smart_crop_box()` is the one
place that calls smartcrop for the service layer (`ImageGrid` does its own,
already-prescaled); both `get_crop_box` and `crop_image` route through it, and
results are memoised in `_SMART_CROP_MEMO`, keyed by (path, mtime, size_tag,
target), so an export reuses the exact box the viewer previewed.

That memo is deliberately **not** written back to `ImageItem.crop_box`, which
means "the user dragged this" and is persisted to the project file. Conflating
them would persist a box locked to one aspect ratio — which re-tagging to a
different size does not clear (BUG-4 in `docs/KNOWN_BUGS.md`).

### QPixmap is GUI-Thread-Only — CRITICAL

`QPixmap` is a `QPaintDevice`; constructing one off the main thread is undefined
behaviour. `QImage` is safe anywhere. So background loaders call
`ImageLoader.load_qimage()` and the **main thread** converts via
`QPixmap.fromImage()` (~0ms even for 12MP). `load_pixmap()` is just a GUI-thread
wrapper over `load_qimage()` — keep the real work in the latter.

Related, in `image_loader`: **`max_size` is a ceiling, not a target.**
`QSize.scaled()`/`QImage.scaled()` grow as happily as they shrink, so both
QImageReader branches guard against upscaling — the Pillow branch never did, and
the two must agree or behaviour depends on the file format.

Never convert PIL → Qt via a PNG buffer (`img.save(buf, 'PNG')` +
`loadFromData`). That costs a full encode *and* decode for pixels that never
touch a disk: 2.8s versus 20ms for a 12MP frame. Use `pil_to_qimage()`.

### Image Viewer Renders Off-Thread

`ImageViewerDialog` renders on a `QThreadPool` (`_RenderTask` → `_render_image`)
because a tagged 12MP photo costs ~600ms even after the fixes above, and used to
cost ~11s on the UI thread. Consequences to respect when changing it:

- **Renders are dispatched by key and may land late.** `_on_render_done` paints
  only if the result still matches `_pending_key`; anything else is cached but
  not shown, or an arrow-key press would flash a stale photo. Results still get
  cached — that is how prefetch lands.
- **`_render_key()` must include everything that changes pixels** (path, size
  tag, crop box, date-stamp flag), or toggling a date stamp serves the pre-stamp
  frame back.
- **The previous frame stays on screen while the next renders** (blanking reads
  as a crash), with `_loading` driving a `[Loading…]` hint. Every exit path must
  clear it — including a cache hit, which awaits nothing but can still arrive
  with the flag set from a photo the user arrowed away from.
- **`closeEvent` waits the pool out.** Tasks emit into the dialog; letting Python
  collect it mid-render fires a signal at freed memory.

Guarded by `tests/test_image_viewer_render.py`.

### EXIF Orientation — CRITICAL

**Never call `Image.open()` on a photo. Use `open_oriented()` from
`src/utils/image_loader.py`.** Phone cameras write the raw sensor buffer and
record the rotation needed for display in EXIF tag 274 rather than re-encoding
the pixels, so a plain `Image.open()` hands you sideways or upside-down pixels
for a perfectly valid file. Qt is the same trap from the other side:
`QImageReader.autoTransform()` is **off by default**, and `QPixmap(path)` never
transforms at all — so every JPEG load needs `setAutoTransform(True)`.

**Upright pixels are the app's internal coordinate space.** Crop boxes,
smartcrop analysis, similarity features and exports all assume it, so the
rotation must be applied at load, everywhere, or the layers disagree.

This bit once, on server-pulled JPEGs: they showed upside down in the grid, and
`crop_image()` saves without an EXIF block, so an export cropped from raw pixels
was **permanently** upside down — no tag left to correct it. The print comes out
wrong. Guarded by `tests/test_image_orientation.py`.

Two things hid the bug, which is why it surfaced only via the server:

- **HEIC is immune.** `pillow_heif` rotates at decode and resets the tag to 1,
  so HEIC looks right through a plain `Image.open()`. Only JPEG is exposed.
- **Added images used to be rewritten on copy-in**, baking rotation into the
  file, while `ServerSyncService.download()` deliberately does not — it writes
  hash-verified bytes verbatim and must not mutate them. Pulled photos were the
  one path keeping their tag. That rewrite (`correct_image_orientation()`) is
  now **deleted**: `open_oriented()` makes it redundant, and it cost a lossy
  re-encode. Files now keep their tags; nothing rewrites a photo to fix rotation.

Two consequences worth remembering:

- `ImageLoader.get_image_dimensions()` reports **displayed** dimensions:
  orientations 5–8 are quarter turns and swap the axes.
- Anything that rewrites pixels must read through `open_oriented()` too, or it
  rotates the raw buffer while the display shows upright — the two disagree.
  `ImageProcessor.rotate_image()` is the live example: it saves the user's
  rotation with no tag, so it must start from upright pixels. It also relies on
  `open_oriented()` restoring `.format`, since Pillow copies drop it and a
  `None` format would save a `.heic` as JPEG.
- **Pillow writes no EXIF on save unless you pass `exif=` explicitly** — an
  omission silently drops the capture date, camera, everything. `rotate_image()`
  carries `img.info["exif"]` across by hand for exactly this reason. Re-attaching
  is safe *only* because `open_oriented()` already stripped the orientation tag
  from those bytes; re-attaching raw EXIF to pixels whose rotation is baked in
  would double-rotate on the next load. Note this loss hides behind
  `get_display_date()`'s `YYYYMMDD_HHMMSS` filename fallback, so date stamps keep
  working and the metadata is gone silently.

### Coordinate Systems (Preview/Crop Mode)

Three systems when working with `CropOverlay`:
1. **Widget coords** — overlay position within QLabel
2. **Thumbnail coords** — pixmap coords within QLabel (accounts for centering)
3. **Full image coords** — original resolution, **EXIF orientation applied**
   (see above), stored in `ImageItem.crop_box`

Always convert explicitly between these when dragging or saving crops.

### QProgressDialog — CRITICAL

`QProgressDialog.close()` **emits `canceled()`** (from its `closeEvent`), and
leaves `wasCanceled()` true. So a handler that closes the dialog before reading
its own cancel flag will always conclude the user cancelled — this silently
broke "Pull from Server" entirely. Disconnect the `canceled` slot before
closing, or read the flag first. `_close_pull_list_dialog()` in `main_window.py`
is the reference pattern.

Note `cancel()` is *not* the same as a Cancel-button click: it flips
`wasCanceled()` without emitting `canceled()`. Qt wires the button as
`clicked -> canceled`, so tests simulating a user cancel must emit the signal.

### QScrollArea Swallows Arrow Keys — CRITICAL

`QScrollArea` inherits `QAbstractScrollArea`, which **accepts focus by default
and consumes arrow keys** to scroll itself. A parent's `keyPressEvent` therefore
never sees Left/Right/Up/Down once the scroll area has focus — and on a frameless
dialog opened with `open()`, focus lands there automatically. This is why
`ImageViewerDialog` sets `scroll_area.setFocusPolicy(Qt.FocusPolicy.NoFocus)`;
without it the viewer's Left/Right browsing silently does nothing while ESC and R
keep working (the scroll area ignores *those*, so they propagate). Any child that
takes focus does the same thing — the viewer's nav chevrons are `NoFocus` for
exactly this reason, or Space/arrows would re-fire the button.

Tests must send keys through the focus chain (`dialog.focusWidget()`) to catch
this; `QTest.keyClick(dialog, …)` delivers straight to the dialog and passes even
when the bug is present.

### Double-Click Handling

`ImageWidget` uses a timer to distinguish single vs double clicks. `mouseReleaseEvent` starts a timer; `mouseDoubleClickEvent` cancels it and sets a flag. This prevents the single-click action from firing after a double-click. Don't break this pattern when modifying click handling.

## Key Data Paths

- Input: `{workspace}/{project}/input/`
- Output: `{workspace}/{project}/output/{size_group}/{size}/`
- Printed thumbnails: `{workspace}/printed/`
- Comparison dir for similarity: `{workspace}/_past_printed/` (derived from workspace, not stored in settings)
- Project metadata: `~/Library/Application Support/AlbumStudio/` (macOS) — persists across app updates
- Feature cache: `{comparison_dir}/.cache/feature_cache.npz`

## Build Notes

`python3 build.py macos` builds the `.app`; `python3 build.py dmg` wraps it into
the installer disk image. Everything below is load-bearing — each line is a bug
that shipped, and every one of them was **silent**: the build exited 0 and the
damage appeared only in the packaged app. Nothing here is caught by `pytest` or
by running from source, so treat a green suite as no evidence at all about the
bundle.

### The entry point is `run.py`, never `src/main.py` — CRITICAL

`src/main.py` uses relative imports (`from .ui...`), which is why running from
source needs module form (`python3 -m src.main`). PyInstaller executes its entry
script as `__main__`, with no parent package, so pointing it at `src/main.py`
breaks **twice**:

- the frozen app dies on launch with `ImportError` at line 1, and
- PyInstaller's analysis cannot follow those imports either, so it silently
  bundles **none of `src/`** — and no torch, no numpy.

The second is what makes this vicious: the build succeeds, and the only tell is
weight. A correct build is **~557 MB** (torch is most of it); the broken one was
70 MB and dead on arrival. `run.py` is a shim that imports `src.main`, keeping
`src` a real package for both the analysis and the runtime.
Guarded by `tests/test_build_entry_point.py`.

### Bundled data is at `sys._MEIPASS`, not next to the executable — CRITICAL

PyInstaller unpacks `--add-data` into `sys._MEIPASS`. Inside a `.app` that is
`Contents/Frameworks`; `Contents/MacOS` holds **only** the binary, so anything
derived from `dirname(sys.executable)` finds nothing. `_bundled_resource_dir()`
in `src/utils/paths.py` is the single place that decides this — read bundled
files through `get_config_dir()` / `get_assets_dir()`, never by hand.

It fails quietly: `Config._read_json()` returns `None` for a missing file, so a
packaged app silently fell back to defaults and started with **no size groups**.
(`get_app_bundle_dir()` deliberately still uses the executable's directory — it
is migration-only and wants exactly that.)
Guarded by `tests/test_frozen_resources.py`.

### Both `config/` and `assets/` must be passed to `--add-data`

`config/` carries the shipped settings + size-group templates; `assets/` carries
the DSEG7 font and `app_icon.png`. Neither is auto-generated, and both must exist
in the repo root before building. A missing font does not raise —
`DateStampService` falls back to Pillow's default bitmap font and the stamp draws
in the wrong typeface. macOS uses a `:` separator; Windows uses `;`.
Guarded by `tests/test_build_packaging.py::TestBundledData`.

### The icon is required, and a DMG needs an `/Applications` symlink

`build.py` **aborts** if `assets/icon.icns` (or `.ico`) is missing rather than
dropping the flag, because PyInstaller substitutes its own Python-logo icon and
still reports success — which is how the wrong icon shipped for months. See
`BUILD.md` for regenerating the three icon files from one source image.

The drag-to-install window is not something macOS provides: the image must
contain an `/Applications` symlink beside the app, or it opens as a lone icon in
an empty window with nowhere to drop it. `build.py dmg` stages that symlink (or
delegates to `create-dmg` when installed). A bare
`hdiutil create -srcfolder dist/AlbumStudio.app` does **not**.
Guarded by `tests/test_build_packaging.py`.

The app is unsigned and un-notarized, so a downloaded DMG needs right-click →
**Open** on first launch to get past Gatekeeper.

## Server Sync Feature (IMPLEMENTED — full spec in `docs/SERVER_SYNC.md`)

Photos are uploaded from the owner's phone to a home server (sibling repo `../album-studio-server/`); this app pulls new ones monthly, auto-organizing them into month-named projects (`{workspace}/2026-06/input/` etc.) by each photo's capture time (`capturedAt` from the server listing). The complete specification — API contract, pull ledger design, UI flow, and implementation rules — lives in **`docs/SERVER_SYNC.md`** in this repo. Read it before working on anything sync-related. Implementation map:

- Service: `src/services/server_sync_service.py` — `ServerSyncService` (+ `RemotePhoto`, `ServerSyncError`). No Qt imports; stdlib `urllib` only (no new deps). Streams downloads, verifies SHA-256, updates the ledger after each file.
- Settings keys `server_url` / `server_token` in `settings.json` (defaults in `config/settings.json` + `Config._get_default_settings()`); edited in the config dialog's **Server** tab with a "Test connection" button.
- Local pull ledger `pulled_photos.json` in the app-support dir (`get_user_data_dir()`) replaces server-side state; `"_meta".last_pull_month` drives the `since=` optimization. The server is stateless by design.
- Month projects use the folder shape `_discover_workspace_projects()` auto-registers; the desktop never reads EXIF for grouping — the Android app decides `capturedAt` at upload.
- "Pull from server" button on `ProjectToolbar` → `MainWindow.on_pull_from_server_requested` → `PullListWorker` (list) → confirm breakdown → `PullDownloadWorker` (download w/ progress dialog) → register new month projects + refresh UI.
- GUI-free CLI: `python3 -m scripts.test_sync test|list|pull <dir>` (reads settings or `ALBUM_STUDIO_SERVER_URL`/`ALBUM_STUDIO_TOKEN` env).
