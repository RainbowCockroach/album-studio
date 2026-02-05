# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Album Studio is a PyQt6 desktop application for organizing and processing photos. Users create projects, tag images with size_group names and print sizes, then batch crop images using smart crop algorithms. The app automatically renames images based on EXIF date metadata and includes AI-powered image similarity search using ResNet50.

**Tech Stack:** Python 3.13+, PyQt6, Pillow, PyTorch (ResNet50), smartcrop, pillow-heif

## Running the Application

**CRITICAL:** The app MUST be run as a module (`python3 -m src.main`) from the project root, not directly (`python src/main.py`), because the codebase uses relative imports.

**Development mode:**

```bash
python3 -m src.main
```

**Quick install and run:**

```bash
pip install -r requirements.txt && python3 -m src.main
```

**Development dependencies (for building):**

```bash
pip install -r requirements-dev.txt
```

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
5. **Add Date Stamps** (optional): Click "Add Date Stamp" to enter selection mode, select images, then click "Mark to set date stamp" to mark selected images for vintage-style date stamping during export; click "Preview Stamp" to see stamp in full-size viewer
6. **Crop Images**: Click "Crop All Tagged Images" to batch process all tagged images (applies date stamps if enabled)
7. **Find Similar**: Select an image, click "Find similar" to search for visually similar images using AI
8. **Rotate Images** (as needed): Select an image, click "Rotate" to rotate 90° clockwise
9. **Archive** (when done): Creates thumbnails → `workspace/printed/`, zips output, deletes project folders
10. **Configure Size Groups** (as needed): Click "Configure Size Groups" to add/remove/rename size groups and their sizes

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
- `DateStampService`: Applies vintage film camera-style date stamps to images during export

**UI** (`src/ui/`):

- `MainWindow`: Orchestrates the three main UI sections
- `widgets/toolbar_top.py` (`ProjectToolbar`): Top bar with project dropdown + action buttons
- `widgets/image_grid.py` (`ImageGrid`): Center grid displaying image thumbnails with preview mode support
- `widgets/toolbar_bottom.py` (`ToolbarBottom`): Bottom bar with size_group/size dropdowns + action buttons
- `widgets/detail_panel.py` (`DetailPanel`): Left sidebar showing EXIF info and image details
- `widgets/crop_overlay.py` (`CropOverlay`): Draggable crop rectangle overlay for preview mode
- `widgets/date_stamp_preview_overlay.py` (`DateStampPreviewOverlay`): Overlay showing date stamp preview on thumbnails
- `dialogs/ConfigDialog`: GUI for managing size groups, workspace, and comparison directories
- `dialogs/FindSimilarDialog`: UI for similarity search with adjustable threshold and result count
- `dialogs/ImageViewerDialog`: Full-size image viewer dialog with date stamp preview support

### Signal/Slot Architecture

The app uses PyQt6's signal/slot mechanism for loose coupling:

```
ProjectToolbar
  ├─ project_changed(name) → MainWindow.on_project_changed()
  ├─ new_project_created(name) → MainWindow.on_new_project()
  ├─ archive_requested(name) → MainWindow.on_archive_requested()
  ├─ add_photo_requested() → MainWindow.on_add_photo_requested()
  ├─ delete_mode_toggled(bool) → MainWindow.on_delete_mode_toggled()
  ├─ delete_confirmed() → MainWindow.on_delete_confirmed()
  ├─ date_stamp_mode_toggled(bool) → MainWindow.on_date_stamp_mode_toggled()
  └─ date_stamp_confirmed() → MainWindow.on_date_stamp_confirmed()

ImageGrid
  ├─ image_clicked(ImageItem) → MainWindow.on_image_clicked()  # Apply tags
  ├─ image_double_clicked(ImageItem) → MainWindow.on_image_double_clicked()  # Clear tags
  ├─ image_selected(ImageItem) → MainWindow.on_image_selected()  # Right-click select
  └─ image_preview_requested(path) → MainWindow.on_image_preview_requested()  # View full size

ToolbarBottom
  ├─ crop_requested() → MainWindow.on_crop_requested()
  ├─ save_requested() → MainWindow.on_save_requested()
  ├─ cancel_requested() → MainWindow.on_cancel_requested()
  ├─ refresh_requested() → MainWindow.on_refresh_requested()
  ├─ config_requested() → MainWindow.on_config_requested()
  ├─ detail_toggled(bool) → DetailPanel.setVisible()
  ├─ find_similar_requested() → MainWindow.on_find_similar_requested()
  ├─ rotate_requested() → MainWindow.on_rotate_requested()
  └─ preview_stamp_requested() → MainWindow.on_preview_stamp_requested()

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
9. If image has `date_stamp` flag enabled, `DateStampService.apply_date_stamp()` overlays vintage date stamp
10. Saves to `output_folder/{size_group}/{size}/{filename}.jpg`
11. Marks `ImageItem.is_cropped = True`

**Date stamping workflow:**

1. User clicks "Add Date Stamp" button to enter selection mode
2. `MainWindow.on_date_stamp_mode_toggled()` calls `ImageGrid.toggle_selection_mode(enabled, mode='date_stamp')`
3. User clicks images to select them (green border indicates selection)
4. User clicks "Mark to set date stamp" button to confirm
5. `MainWindow.on_date_stamp_confirmed()` sets `ImageItem.add_date_stamp = True` for all selected images
6. `ImageItem.add_date_stamp` flag saved to project_data.json, 📅 indicator appears on thumbnails
7. User can click "Preview Stamp" to see full-size preview in `ImageViewerDialog`
8. During crop operation, `DateStampService` applies physics-based vintage stamp:
   - Reads EXIF date metadata from image
   - Calculates font size based on physical print dimensions (maintains consistent size across print sizes)
   - Uses blackbody-inspired color temperature gradient for authentic warm-edge glow
   - Outer layers use Linear Dodge (Add) blend for saturated warm edges (red-orange)
   - Inner layers use Screen blend for light projection effect (yellow-white core)
   - 13-layer rendering with colors shifting from deep red-orange (outer) to pale yellow (core)
   - Uses DSEG7 Classic font (bundled in `assets/fonts/`) for authentic digital display aesthetic
9. Date format, position, warm shift, and opacity configurable in `config/settings.json`

**Similarity search workflow:**

1. User clicks an image (sets `MainWindow.last_clicked_image`)
2. User clicks "Find similar" button
3. `ImageSimilarityService` lazy-loads ResNet50 model
4. Loads images from comparison directory (default: `{workspace}/printed/`)
5. Extracts 2048-dim feature vectors (cached in `.cache/feature_cache.npz`)
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

**`settings.json`**: App preferences (thumbnail size, grid columns, date format, supported file extensions, workspace/comparison directories, date stamp settings)

Date stamp settings include:
- `date_stamp_format`: Date format string (e.g., "'YY.MM.DD", "MM.DD.'YY")
- `date_stamp_position`: Placement on image (bottom-right, bottom-left, top-right, top-left)
- `date_stamp_temp_outer`: Outer glow color temperature in Kelvin (1000-4000, default: 1800 - warm orange)
- `date_stamp_temp_core`: Core text color temperature in Kelvin (4000-10000, default: 6500 - bright white)
- `date_stamp_opacity`: Text opacity 0-100 (default: 90)
- `date_stamp_glow_intensity`: Glow effect strength 0-100 (default: 80)
- `date_stamp_margin`: Distance from edges in pixels (default: 30)
- `date_stamp_physical_height`: Physical height in print units (default: 0.2)
- `date_stamp_target_dpi`: Pixels per print unit for size calculation (default: 300)

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

# WRONG (will fail in PyQt6)
pixmap.scaled(size, size, aspectRatioMode=1, transformMode=1)
```

**Event handling patterns:**

- **Double-click handling:** The `ImageWidget` uses a timer-based approach to distinguish single vs double clicks. When `mouseReleaseEvent` fires, it starts a timer. If `mouseDoubleClickEvent` fires before timeout, it cancels the timer and sets a flag. This prevents single-click from executing after double-click.

- **Preview mode interaction:** When in preview mode, `ImageGrid` overlays `CropOverlay` widgets on each tagged image. The overlay uses `WA_TransparentForMouseEvents` set to False to capture mouse events for dragging. Crop rectangles are constrained to image bounds and maintain aspect ratio based on the size tag's ratio.

- **Signal/slot safety:** Never directly connect widgets to other widgets. All communication goes through `MainWindow` as the orchestrator (see Signal/Slot Architecture section).

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

- ResNet50 features cached in-memory (`ImageItem.feature_vector`) and on-disk (`.cache/feature_cache.npz`)
- Cache file stored alongside comparison images for persistence across sessions
- Feature extraction is expensive (~1-2 seconds per image), caching enables instant searches
- Cache uses compressed numpy format (.npz) for efficient storage (~5-10x smaller than JSON)

### Date Stamp Rendering

- Uses physics-based blackbody color temperature gradient for authentic warm-edge glow
- Color temperature configurable: outer glow (1000-4000K) and core text (4000-10000K)
- `kelvin_to_rgb()` function converts temperature to accurate RGB using Planckian locus approximation
- Font size automatically scales based on physical print dimensions to maintain consistent appearance across different print sizes
- 13-layer rendering with dual blend modes:
  - Outer layers (4): Linear Dodge (Add) for saturated warm edges at configured outer temperature
  - Transition layers (3): Screen blend - interpolated between outer and core temperatures
  - Inner layers (4): Screen blend - approaching core temperature
  - Core layers (2): Screen blend - at configured core temperature
- Gaussian blur radii scale proportionally to font size (6x to 0.05x font size)
- Linear Dodge creates characteristic saturated warm bleed at transition zone
- DSEG7 Classic font provides authentic digital display appearance (7-segment LED style)
- Thumbnail preview uses simplified solid-color rendering (for size preview only)
- Config dialog provides temperature sliders with visual gradient preview
- All rendering done with PIL/Pillow and NumPy for maximum compatibility and quality

## Common Issues

**Images not displaying:**

- Check Qt enum usage in `src/models/image_item.py:54-59` (must use `Qt.AspectRatioMode.KeepAspectRatio`)
- Verify supported formats in `config/settings.json` line 8-17 match actual file extensions
- Check console output for errors during `Project.load_images()` in `src/models/project.py`
- Ensure `ImageLoader.load_pixmap()` in `src/utils/image_loader.py` handles the format

**Double-click not clearing tags:**

- Ensure `ImageWidget.click_timer` is stopped in `mouseDoubleClickEvent` in `src/ui/widgets/image_grid.py`
- Verify `double_click_flag` is checked in `_handle_single_click`

**Import errors:**

- Always run as module: `python3 -m src.main` (not `python src/main.py`)
- Check relative imports use correct depth (`..models` for services, `.widgets` for UI)
- Entry point is `src/main.py:7` which calls `MainWindow()`

**Config not loading:**

- Config files must exist in `config/` directory (size_group.json, sizes.json, settings.json)
- Check JSON syntax if config seems ignored
- Use "Configure Size Groups" button to edit configs via GUI (preferred over manual editing)
- Config loaded in `src/models/config.py`

**Preview mode issues:**

- Crop overlay not draggable: Check `WA_TransparentForMouseEvents` is set to False in `src/ui/widgets/crop_overlay.py`
- Crop rect goes outside image: Verify `set_image_bounds()` is called with correct bounds
- Aspect ratio wrong: Ensure size tag has valid ratio in `config/sizes.json`
- Preview mode logic in `src/ui/widgets/image_grid.py` `enter_preview_mode()` and `exit_preview_mode()`

**Similarity search not working:**

- Verify PyTorch is installed: `pip install torch torchvision`
- Check comparison directory exists and contains images (default: `{workspace}/printed/`)
- Ensure workspace directory is configured in `config/settings.json` line 2
- Look for `[DEBUG]` logs showing feature extraction progress in console
- Service implementation: `src/services/image_similarity_service.py`

**Archive creating empty folders:**

- Output folder must contain cropped images (crop images before archiving)
- Archive only processes images in output folder, not input folder
- Archive workflow in `src/services/project_manager.py` `archive_project()` method

**Date stamps not appearing:**

- Verify `ImageItem.date_stamp` flag is True in project_data.json
- Check DSEG7 font exists in `assets/fonts/DSEG7Classic-Regular.ttf`
- Date stamp only applied during crop operation (not retroactively on already-cropped images)
- View console logs for PIL/Pillow errors during stamp rendering
- Preview stamp in full-size viewer to verify settings before batch cropping
- Service implementation: `src/services/date_stamp_service.py`

## Workspace & Output Structure

**Workspace directory structure** (configured in `config/settings.json`):

```
{workspace}/                          # e.g., ~/Photos/album-studio-projects
├── {project_name}/
│   ├── input/                       # User adds images here
│   │   └── 20231225_143022.jpg
│   └── output/                      # Cropped images organized by tags
│       └── {size_group_name}/       # e.g., "Wedding Size Group"
│           └── {size}/              # e.g., "4x6"
│               └── {filename}.jpg
├── printed/                         # Archived thumbnails (800px) from all projects
│   └── 20231225_143022.jpg
└── {project_name}_output.zip        # Archived output folders
```

**Application data directory** (`data/` in project root):

```
data/
├── projects.json                    # All projects metadata
└── projects/
    └── {project_name}/
        └── project_data.json        # Tags, crop positions per project
```

**Important paths:**

- Input folder: `{workspace}/{project_name}/input/`
- Output folder: `{workspace}/{project_name}/output/`
- Comparison directory for similarity search: `{workspace}/printed/` (configurable)
- Feature cache: `{comparison_directory}/.cache/feature_cache.npz`

## Build Notes

PyInstaller bundles:

- Python interpreter
- All dependencies (PyQt6, Pillow, piexif, smartcrop, torch, torchvision)
- `config/` folder (via `--add-data`)
- `assets/` folder including DSEG7 Classic font (via `--add-data`)

The `config/` and `assets/` folders are included in builds, but `data/projects.json` is NOT (user-specific).

When modifying the build process, note that macOS uses `:` as separator (`config:config`, `assets:assets`) while Windows uses `;` (`config;config`, `assets;assets`) for `--add-data`.

## Critical Implementation Patterns

### Coordinate System Conversions (Preview Mode)

When working with crop overlays, there are three coordinate systems:

- **Widget coordinates**: Overlay position in QLabel
- **Thumbnail coordinates**: Pixmap coordinates within QLabel (accounts for centering)
- **Full image coordinates**: Original resolution (stored in `crop_box`)

Always convert between these systems when dragging or saving crops.

### Lazy Loading Pattern

Critical for performance and startup time:

- **Similarity service:** `ImageSimilarityService` only instantiated when user clicks "Find similar" (`MainWindow.similarity_service = None` initially in `src/ui/main_window.py:23`)
- **PyTorch models:** ResNet50 only loaded when similarity service initializes (saves ~500MB memory)
- **Thumbnails:** Only generated on-demand via `ImageItem.get_thumbnail()` and cached in `_thumbnail` field
- **Feature vectors:** Computed once, cached in-memory (`ImageItem.feature_vector`) and on-disk (`.cache/feature_cache.npz`)

When adding heavy dependencies, follow this pattern to avoid bloating startup time.

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

## Code Quality and Linting

**CRITICAL:** Always lint modified files when a task is finished (when the user confirms the task is complete). This ensures code quality and catches potential issues before committing.

### Type Checking

The project uses Pyright and mypy for type checking with relaxed settings suitable for PyQt6:

```bash
# Type check with Pyright (configured in pyrightconfig.json)
pyright src/

# Type check specific files
pyright src/services/crop_service.py

# Type check with mypy (configured in mypy.ini)
mypy src/
```

Type checking configuration:
- Missing imports flagged as errors
- Unused imports and variables flagged
- Optional access patterns flagged as warnings
- Third-party libraries without stubs (pillow-heif, piexif, smartcrop, torch) have ignore rules in mypy.ini

### Linting Workflow

When you finish implementing a task (user confirms completion):

1. **Type check the modified files:**
   ```bash
   pyright src/path/to/modified_file.py
   ```

2. **Check for common issues:**
   - Unused imports
   - Undefined variables
   - Type mismatches
   - Missing imports

3. **Fix any issues found** before considering the task complete

This step is mandatory for all code changes to maintain code quality and prevent runtime errors.

## File Structure

```
album-studio/
├── src/
│   ├── main.py              # Application entry point
│   ├── models/              # Data models (Config, Project, ImageItem)
│   ├── services/            # Business logic (ProjectManager, CropService, ImageProcessor, ImageSimilarityService, DateStampService)
│   ├── ui/
│   │   ├── main_window.py   # Main orchestrator window
│   │   ├── widgets/         # Reusable UI components (ImageGrid, toolbars, panels, overlays)
│   │   └── dialogs/         # Modal dialogs (ConfigDialog, FindSimilarDialog, ImageViewerDialog)
│   └── utils/               # Utilities (ImageLoader for HEIC support, paths)
├── config/                  # JSON configuration files (size_group.json, sizes.json, settings.json)
├── data/                    # Runtime data (projects.json, project_data per project)
├── assets/                  # Application icon, DSEG7 Classic font
│   └── fonts/               # DSEG7Classic-Regular.ttf for date stamps
├── build.py                 # Cross-platform build script
├── BUILD.md                 # Detailed build documentation
└── requirements.txt         # Python dependencies
```
