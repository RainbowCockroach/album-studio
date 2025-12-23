`pip install -r requirements.txt && python3 -m src.main`

# Album Studio

A PyQt6-based image sorting and processing application for organizing photos into albums with automatic renaming, tagging, and smart cropping capabilities.

## Features

- **Project Management**: Create and manage multiple photo projects
- **Automatic Renaming**: Rename images based on EXIF date taken data (format: YYYYMMDD_HHMMSS)
- **Two-Level Tagging**: Tag images with album names and print sizes
- **Smart Cropping**: Use AI-powered smart crop to automatically crop images to specified dimensions
- **Visual Grid Interface**: View all images in a grid with visual indicators for tagging status
- **Batch Processing**: Process multiple images at once

## Installation

1. Clone or download this repository

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

If using Conda, you may need to install separately:

```bash
pip install PyQt6 Pillow piexif smartcrop
```

## Running the Application

From the project root directory:

```bash
python3 -m src.main
```

The application will start in full screen mode.

## Building for Distribution

To create standalone executables for macOS or Windows, see [BUILD.md](BUILD.md) for detailed instructions.

**Quick build:**

```bash
# Install PyInstaller
pip install pyinstaller

# Build for current platform
python3 build.py

# Or use platform-specific scripts
./build-macos.sh          # macOS
build-windows.bat         # Windows
```

The built application will be in the `dist/` folder.

## Usage

### Creating a Project

1. Click "New Project" button in the top toolbar
2. Enter a project name
3. Select an input folder (where your original images are located)
4. Select an output folder (where cropped images will be saved)
5. Click OK

### Managing Images

1. **Select a project** from the dropdown menu at the top
2. **Refresh & Rename Images**:
   - Click "Refresh & Rename Images" button
   - This will scan the input folder and rename images based on their EXIF date
   - Images will be renamed to format: YYYYMMDD_HHMMSS.jpg

### Tagging Images

1. **Select album and size** from the dropdowns at the bottom:

   - Choose an album name (e.g., "Wedding Album")
   - Choose a size (e.g., "4x6") - sizes are filtered based on the selected album

2. **Apply tags to images**:

   - Single click on an image to apply the currently selected album and size tags
   - Double click on an image to clear all its tags

3. **Visual indicators**:
   - Gray border: No tags
   - Orange border: Partially tagged (only album or only size)
   - Green border: Fully tagged (both album and size)

### Cropping Images

1. Tag all images with both album and size
2. Click "Crop All Tagged Images" button
3. Confirm the operation
4. Cropped images will be saved to: `output_folder/AlbumName/Size/filename.jpg`

## Configuration

### Albums and Sizes

Edit `config/albums.json` to define available albums and their allowed sizes:

```json
{
  "Wedding Album": ["4x6", "5x7", "8x10"],
  "Portrait Album": ["5x7", "8x10", "11x14"]
}
```

Edit `config/sizes.json` to define size dimensions for cropping:

```json
{
  "4x6": {
    "width": 1800,
    "height": 1200,
    "ratio": 1.5
  }
}
```

### Settings

Edit `config/settings.json` to customize:

- `thumbnail_size`: Size of thumbnails in grid (default: 200)
- `grid_columns`: Number of columns in grid (default: 5)
- `date_format`: Format for renamed files (default: "%Y%m%d\_%H%M%S")
- `supported_formats`: Image file extensions to process

## Project Structure

```
album-studio/
├── src/
│   ├── main.py                 # Entry point
│   ├── ui/
│   │   ├── main_window.py      # Main application window
│   │   └── widgets/            # UI widgets
│   ├── models/                 # Data models
│   ├── services/               # Business logic
│   └── utils/                  # Utilities
├── config/                     # Configuration files
├── data/                       # Project data storage
└── requirements.txt            # Python dependencies
```

## Keyboard Shortcuts

- Click image: Apply current tags
- Double-click image: Clear all tags

## Tips

- Keep your images organized in separate folders for each project
- Use descriptive album names that match your physical albums
- The smart crop algorithm will find the most important part of the image automatically
- Tagged status is saved automatically when you tag/untag images
- You can edit config files to add new albums or sizes without restarting the app (just create a new project to reload config)

## Troubleshooting

**Images not loading?**

- Make sure your input folder contains supported image formats (.jpg, .jpeg, .png)
- Check that the folder path is correct

**EXIF date not found?**

- The app will fall back to file modification time if EXIF data is not available
- Some images (screenshots, edited photos) may not have EXIF date information

**Cropping fails?**

- Ensure the image is large enough for the target crop size
- Check that the size configuration is correct in sizes.json

## License

This project is provided as-is for personal and commercial use.
