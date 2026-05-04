# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Album Studio is a PyQt6 desktop app for organizing and batch-cropping photos. Users create projects, tag images with size group + print size, preview/adjust smart crops, apply vintage date stamps, then export. Also includes AI similarity search (ResNet50).

**Tech Stack:** Python 3.13+, PyQt6, Pillow, PyTorch (ResNet50), smartcrop, pillow-heif

## Commands

```bash
# Run (MUST use module form — relative imports require it)
python3 -m src.main

# Install dependencies
pip install -r requirements.txt

# Build macOS app
source .venv/bin/activate && python3 build.py macos

# Type check
pyright src/
pyright src/path/to/file.py   # single file

# No automated test suite — manual testing only
```

**Always lint modified files when finishing a task:** `pyright src/path/to/modified_file.py`

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

### Coordinate Systems (Preview/Crop Mode)

Three systems when working with `CropOverlay`:
1. **Widget coords** — overlay position within QLabel
2. **Thumbnail coords** — pixmap coords within QLabel (accounts for centering)
3. **Full image coords** — original resolution, stored in `ImageItem.crop_box`

Always convert explicitly between these when dragging or saving crops.

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

PyInstaller bundles `config/` and `assets/` (including DSEG7 font for date stamps). The `config/` folder must exist in the repo root before building — it is not auto-generated.

macOS uses `:` separator in `--add-data`; Windows uses `;`.
