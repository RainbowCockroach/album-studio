# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Album Studio is a PyQt6 desktop application for organizing and processing photos. Users create projects, tag images with size_group names and print sizes, then batch crop images using smart crop algorithms. The app automatically renames images based on EXIF date metadata and includes AI-powered image similarity search using ResNet50.

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

## User Workflow

The typical user workflow is:

1. **Create Project**: Click "New Project", specify name and workspace directory (creates `workspace/{project}/input` and `workspace/{project}/output`)
2. **Load Images**: Click "Refresh & Rename Images" to scan input folder and auto-rename by EXIF date
3. **Tag Images**: Select size group and size from dropdowns, then click images to tag them (double-click to clear tags)
4. **Preview Crops** (optional): Click "Preview & Adjust Crops" to see and adjust crop positions before final cropping
5. **Crop Images**: Click "Crop All Tagged Images" to batch process all tagged images
6. **Find Similar**: Select an image, click "Find similar" to search for visually similar images using AI
7. **Archive** (when done): Creates thumbnails → `workspace/printed/`, zips output, deletes project folders
8. **Configure Size Groups** (as needed): Click "Configure Size Groups" to add/remove/rename size groups and their sizes

## Architecture

### MVC-Like Structure

The codebase follows a clean separation of concerns:

**Models** (`src/models/`):

- `Config`: Loads/saves JSON configuration (size_groups, sizes, settings)
- `Project`: Represents a photo project with input/output folders and image list
- `ImageItem`: Individual image with tags, EXIF data, cached thumbnail, and feature vector

**Services** (`src/services/`):

- `ProjectManager`: CRUD operations for projects, persists to `data/projects.json`, handles archival
- `ImageProcessor`: EXIF date reading, auto-rename by date
- `CropService`: Smart cropping using smartcrop library based on size dimensions
- `ImageSimilarityService`: ResNet50-based deep learning similarity search with caching

**UI** (`src/ui/`):

- `MainWindow`: Orchestrates the three main UI sections
- `widgets/ProjectToolbar`: Top bar with project dropdown + action buttons
- `widgets/ImageGrid`: Center grid displaying image thumbnails with preview mode support
- `widgets/TagPanel`: Bottom bar with size_group/size dropdowns + action buttons
- `widgets/CropOverlay`: Draggable crop rectangle overlay for preview mode
- `dialogs/ConfigDialog`: GUI for managing size groups, workspace, and comparison directories
- `dialogs/FindSimilarDialog`: UI for similarity search with adjustable threshold and result count

### Signal/Slot Architecture

The app uses PyQt6's signal/slot mechanism for loose coupling:

```
ProjectToolbar
  ├─ project_changed(name) → MainWindow.on_project_changed()
  ├─ new_project_created(name) → MainWindow.on_new_project()
  ├─ archive_requested(name) → MainWindow.on_archive_requested()
  ├─ add_photo_requested() → MainWindow.on_add_photo_requested()
  └─ delete_confirmed() → MainWindow.on_delete_confirmed()

ImageGrid
  ├─ image_clicked(ImageItem) → MainWindow.on_image_clicked()  # Apply tags
  └─ image_double_clicked(ImageItem) → MainWindow.on_image_double_clicked()  # Clear tags

TagPanel
  ├─ crop_requested() → MainWindow.on_crop_requested()
  ├─ refresh_requested() → MainWindow.on_refresh_requested()
  ├─ config_requested() → MainWindow.on_config_requested()
  └─ find_similar_requested() → MainWindow.on_find_similar_requested()

DetailPanel
  └─ rename_requested(ImageItem) → MainWindow.on_rename_requested()
```

All widget-to-widget communication goes through MainWindow - widgets never talk directly to each other.

### Data Flow

**Project loading:**

1. `ProjectManager.load_projects()` reads `data/projects.json`
2. `Project.load_images()` scans input folder for supported formats
3. `Project.load_project_data()` loads `data/projects/{name}/project_data.json` with saved tags/crops
4. `ImageItem.get_thumbnail()` creates QPixmap thumbnails (cached)
5. `ImageGrid.load_images()` creates `ImageWidget` instances in grid layout

**Tagging workflow:**

1. User selects size_group/size in `TagPanel`
2. User clicks image in `ImageGrid`
3. Signal emits to `MainWindow.on_image_clicked()`
4. `ImageItem.set_tags()` stores tags
5. `ImageGrid.refresh_display()` updates border colors (green=fully tagged, orange=partial, gray=none)
6. `ProjectManager.save_project()` persists to JSON

**Cropping workflow:**

1. User clicks "Preview & Adjust Crops" to enter preview mode
2. `ImageGrid.enter_preview_mode()` displays `CropOverlay` widgets on tagged images
3. Smartcrop algorithm calculates initial crop positions (aspect ratio locked to size tag)
4. User drags crop rectangles to adjust crop positions
5. On exit, crop positions saved to `ImageItem.crop_box` dict with {x, y, width, height}
6. User clicks "Crop All Tagged Images"
7. `CropService.crop_project()` gets all fully-tagged images
8. For each: `CropService.crop_image()` uses `crop_box` if set, otherwise smartcrop to find best crop
9. Saves to `output_folder/{size_group}/{size}/{filename}.jpg`
10. Marks `ImageItem.is_cropped = True`

**Similarity search workflow:**

1. User clicks an image (sets `MainWindow.last_clicked_image`)
2. User clicks "Find similar" button
3. `ImageSimilarityService` lazy-loads ResNet50 model
4. Loads images from comparison directory (default: `{workspace}/printed/`)
5. Extracts 2048-dim feature vectors (cached in `.cache/feature_cache.json`)
6. Computes cosine similarity between target and all candidates
7. Returns top matches above threshold, sorted by similarity
8. `FindSimilarDialog` displays results with similarity percentages

**Archival workflow:**

1. User clicks "Archive Project"
2. `ProjectManager.archive_project()`:
   - Creates 800px thumbnails from output folder → `{workspace}/printed/`
   - Zips output folder → `{workspace}/{name}_output.zip`
   - Deletes input and output folders
   - Removes project from projects.json

### Configuration System

Three JSON files in `config/`:

**`size_group.json`**: Maps size group names to their allowed sizes with ratios and aliases

```json
{
  "A5": {
    "sizes": [
      { "ratio": "9x6", "alias": "9x6" },
      { "ratio": "5x7", "alias": "5x7" }
    ]
  }
}
```

**`sizes.json`**: Defines aspect ratios for each size (deprecated for width/height but ratio still used)

```json
{
  "4x6": { "ratio": 1.5 },
  "5x7": { "ratio": 1.4 }
}
```

**`settings.json`**: App preferences (thumbnail size, grid columns, date format, supported file extensions, workspace/comparison directories)

**Configuration Management:**

- Config loaded at startup by `Config` class with automatic migration from old format
- Users can edit size groups/sizes via GUI: Click "Configure Size Groups" button in TagPanel
- `ConfigDialog` provides split-panel interface: size groups (left) and their sizes (right)
- Workspace and comparison directory paths editable in Config dialog
- Changes are saved immediately to `size_group.json` and `settings.json`
- Config changes automatically update projects and reload affected tags

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

**Preview mode interaction:** When in preview mode, `ImageGrid` overlays `CropOverlay` widgets on each tagged image. The overlay uses `WA_TransparentForMouseEvents` set to False to capture mouse events for dragging. Crop rectangles are constrained to image bounds and maintain aspect ratio based on the size tag's ratio.

## Image Processing Details

### HEIC Support

- Uses `pillow-heif` for HEIC/HEIF format support
- `ImageLoader.load_pixmap()` handles HEIC transparently
- Fallback from Qt native loading to Pillow for unsupported formats

### Smart Cropping Performance

- For large images (>600px), downscales before smartcrop analysis to improve speed
- Calculates crop on smaller version, then scales coordinates back to full resolution
- Massive performance improvement for HEIC files

### Feature Extraction Caching

- ResNet50 features cached in-memory (`ImageItem.feature_vector`) and on-disk (`.cache/feature_cache.json`)
- Cache file stored alongside comparison images for persistence across sessions
- Feature extraction is expensive (~1-2 seconds per image), caching enables instant searches

## Common Issues

**Images not displaying:**

- Check Qt enum usage in `ImageItem.get_thumbnail()`
- Verify supported formats in `config/settings.json` match actual file extensions
- Check console output for errors during `Project.load_images()`

**Double-click not clearing tags:**

- Ensure `ImageWidget.click_timer` is stopped in `mouseDoubleClickEvent`
- Verify `double_click_flag` is checked in `_handle_single_click`

**Import errors:**

- Always run as module: `python3 -m src.main`
- Check relative imports use correct depth (`..models`, `.widgets`)

**Config not loading:**

- Config files must exist in `config/` directory
- Check JSON syntax if config seems ignored
- Use "Configure Size Groups" button to edit configs via GUI (preferred over manual editing)

**Preview mode issues:**

- Crop overlay not draggable: Check `WA_TransparentForMouseEvents` is set to False
- Crop rect goes outside image: Verify `set_image_bounds()` is called with correct bounds
- Aspect ratio wrong: Ensure size tag has valid ratio in `sizes.json`

**Similarity search not working:**

- Verify PyTorch is installed: `pip install torch torchvision`
- Check comparison directory exists and contains images
- Ensure workspace directory is configured in settings
- Look for `[DEBUG]` logs showing feature extraction progress

**Archive creating empty folders:**

- Output folder must contain cropped images (crop images before archiving)
- Archive only processes images in output folder, not input folder

## Output Structure

**Projects JSON:** `data/projects.json` stores all project metadata

**Project data JSON:** `data/projects/{name}/project_data.json` stores image tags and crop positions

**Cropped images:** `{output_folder}/{size_group_name}/{size}/{filename}.jpg`

Example: `~/Photos/ProjectName/output/Wedding Size Group/4x6/20231225_143022.jpg`

**Archived thumbnails:** `{workspace}/printed/{filename}.jpg` (global folder, all archived projects)

**Archived zips:** `{workspace}/{project_name}_output.zip`

## Build Notes

PyInstaller bundles:

- Python interpreter
- All dependencies (PyQt6, Pillow, piexif, smartcrop, torch, torchvision)
- `config/` folder (via `--add-data`)

The `config/` folder is included in builds, but `data/projects.json` is NOT (user-specific).

When modifying the build process, note that macOS uses `:` as separator (`config:config`) while Windows uses `;` (`config;config`) for `--add-data`.

## Critical Implementation Patterns

### Coordinate System Conversions (Preview Mode)

When working with crop overlays, there are three coordinate systems:

- **Widget coordinates**: Overlay position in QLabel
- **Thumbnail coordinates**: Pixmap coordinates within QLabel (accounts for centering)
- **Full image coordinates**: Original resolution (stored in `crop_box`)

Always convert between these systems when dragging or saving crops.

### Lazy Loading Pattern

- `ImageSimilarityService` only loaded when user clicks "Find similar"
- Thumbnails only loaded when `ImageItem.get_thumbnail()` called
- Prevents loading PyTorch/heavy resources unless needed

### Memory Management

- Call `ImageItem.clear_thumbnail_cache()` to free memory
- Feature vectors persist in memory during session for fast searches
- Large images downscaled before analysis

### Aspect Ratio Calculations

- Ratio = width / height (e.g., "9x6" = 1.5)
- Crop maintains ratio by constraining dimensions during drag
- Always calculate largest possible crop fitting within image bounds

## Testing & Debugging

No automated test suite currently exists. Manual testing workflow:

1. Run the app: `python3 -m src.main`
2. Create a test project with sample images
3. Test tagging, preview mode, cropping, and similarity search workflows
4. Check console for `[DEBUG]` logs when issues occur

Debug logs are extensive throughout similarity search and archival processes.
