# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Album Studio is a PyQt6 desktop application for organizing and processing photos. Users create projects, tag images with album names and print sizes, then batch crop images using smart crop algorithms. The app automatically renames images based on EXIF date metadata.

## Running the Application

**Development mode:**
```bash
python3 -m src.main
```

**Quick install and run:**
```bash
pip install -r requirements.txt && python3 -m src.main
```

**Note:** The app MUST be run as a module (`python3 -m src.main`) from the project root, not directly (`python src/main.py`), because the codebase uses relative imports.

## Building Executables

```bash
# Install build dependencies
pip install pyinstaller

# Build for current platform
python3 build.py

# Platform-specific builds
python3 build.py macos      # macOS .app bundle
python3 build.py windows    # Windows .exe
python3 build.py clean      # Clean build artifacts

# Alternative: use shell scripts
./build-macos.sh            # macOS only
build-windows.bat           # Windows only
```

Output: `dist/AlbumStudio.app` (macOS) or `dist/AlbumStudio/` (Windows)

## Testing & Debugging

**Test image loading:**
```bash
python3 test_image_loading.py
```

This diagnostic script checks:
- Configuration loading
- Project discovery
- Image file detection
- Thumbnail generation with PyQt6

Use when troubleshooting "images not displaying" issues.

## Architecture

### MVC-Like Structure

The codebase follows a clean separation of concerns:

**Models** (`src/models/`):
- `Config`: Loads/saves JSON configuration (albums, sizes, settings)
- `Project`: Represents a photo project with input/output folders and image list
- `ImageItem`: Individual image with tags, EXIF data, and cached thumbnail

**Services** (`src/services/`):
- `ProjectManager`: CRUD operations for projects, persists to `data/projects.json`
- `ImageProcessor`: EXIF date reading, auto-rename by date
- `CropService`: Smart cropping using smartcrop library based on size dimensions

**UI** (`src/ui/`):
- `MainWindow`: Orchestrates the three main UI sections
- `widgets/ProjectToolbar`: Top bar with project dropdown + "New Project" button
- `widgets/ImageGrid`: Center grid displaying image thumbnails
- `widgets/TagPanel`: Bottom bar with album/size dropdowns + action buttons

### Signal/Slot Architecture

The app uses PyQt6's signal/slot mechanism for loose coupling:

```
ProjectToolbar
  ├─ project_changed(name) → MainWindow.on_project_changed()
  └─ new_project_created(name, input, output) → MainWindow.on_new_project()

ImageGrid
  ├─ image_clicked(ImageItem) → MainWindow.on_image_clicked()  # Apply tags
  └─ image_double_clicked(ImageItem) → MainWindow.on_image_double_clicked()  # Clear tags

TagPanel
  ├─ crop_requested() → MainWindow.on_crop_requested()
  └─ refresh_requested() → MainWindow.on_refresh_requested()
```

All widget-to-widget communication goes through MainWindow - widgets never talk directly to each other.

### Data Flow

**Project loading:**
1. `ProjectManager.load_projects()` reads `data/projects.json`
2. `Project.load_images()` scans input folder for supported formats
3. `ImageItem.get_thumbnail()` creates QPixmap thumbnails (cached)
4. `ImageGrid.load_images()` creates `ImageWidget` instances in grid layout

**Tagging workflow:**
1. User selects album/size in `TagPanel`
2. User clicks image in `ImageGrid`
3. Signal emits to `MainWindow.on_image_clicked()`
4. `ImageItem.set_tags()` stores tags
5. `ImageGrid.refresh_display()` updates border colors
6. `ProjectManager.save_project()` persists to JSON

**Cropping workflow:**
1. `CropService.crop_project()` gets all fully-tagged images
2. For each: `CropService.crop_image()` uses smartcrop to find best crop
3. Saves to `output_folder/AlbumName/Size/filename.jpg`
4. Marks `ImageItem.is_cropped = True`

### Configuration System

Three JSON files in `config/`:

**`albums.json`**: Maps album names to allowed sizes
```json
{
  "Wedding Album": ["4x6", "5x7", "8x10"]
}
```

**`sizes.json`**: Defines crop dimensions
```json
{
  "4x6": {"width": 1800, "height": 1200, "ratio": 1.5}
}
```

**`settings.json`**: App preferences (thumbnail size, grid columns, date format, supported file extensions)

Config is loaded once at startup by `Config` class. To reload config, users must create a new project (design limitation).

## PyQt6 Specifics

**Critical:** Use proper Qt enums, not integers:

```python
# CORRECT
pixmap.scaled(size, size,
    Qt.AspectRatioMode.KeepAspectRatio,
    Qt.TransformationMode.SmoothTransformation)

# WRONG (will fail)
pixmap.scaled(size, size, aspectRatioMode=1, transformMode=1)
```

**Double-click handling:** The `ImageWidget` uses a timer-based approach to distinguish single vs double clicks. When `mouseReleaseEvent` fires, it starts a timer. If `mouseDoubleClickEvent` fires before timeout, it cancels the timer and sets a flag. This prevents single-click from executing after double-click.

## Common Issues

**Images not displaying:**
- Check Qt enum usage in `ImageItem.get_thumbnail()`
- Run `python3 test_image_loading.py` to diagnose
- Verify supported formats in config match actual file extensions

**Double-click not clearing tags:**
- Ensure `ImageWidget.click_timer` is stopped in `mouseDoubleClickEvent`
- Verify `double_click_flag` is checked in `_handle_single_click`

**Import errors:**
- Always run as module: `python3 -m src.main`
- Check relative imports use correct depth (`..models`, `.widgets`)

**Config not loading:**
- Config files must exist in `config/` directory
- Check JSON syntax if config seems ignored
- Config is cached - restart app to reload changes

## Output Structure

**Projects JSON:** `data/projects.json` stores all project metadata and image tags

**Cropped images:** `{output_folder}/{album_name}/{size}/{filename}`

Example: `~/Photos/Output/Wedding Album/4x6/20231225_143022.jpg`

## Build Notes

PyInstaller bundles:
- Python interpreter
- All dependencies (PyQt6, Pillow, piexif, smartcrop)
- `config/` folder (via `--add-data`)

The `config/` folder is included in builds, but `data/projects.json` is NOT (user-specific).

When modifying the build process, note that macOS uses `:` as separator (`config:config`) while Windows uses `;` (`config;config`) for `--add-data`.
