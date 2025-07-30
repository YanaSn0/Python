# Image Slideshow Creator

This Python script creates video slideshows from images in a specified directory using FFmpeg. It converts images (`.jpg`, `.jpeg`, `.png`, `.webp`) into `.mp4` video slides with a specified duration, optionally standardizing resolution based on the dominant aspect ratio of the input images.

## Features
- Converts images to video slides with a fixed duration per image.
- Supports `.jpg`, `.jpeg`, `.png`, and `.webp` formats.
- Automatically detects image names or processes ranges (e.g., `img1-img10`).
- Determines optimal resolution (landscape, portrait, or square) based on input images.
- Option to keep original image resolutions.
- Maintains metadata to track processed slides and avoid reprocessing.
- Supports debug mode for verbose output.

## Requirements
- Python 3.6+
- FFmpeg installed and accessible in the system PATH
- PIL (Pillow) library (`pip install Pillow`)

## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/<your-username>/<your-repo>.git
   ```
2. Install the required Python package:
   ```bash
   pip install Pillow
   ```
3. Ensure FFmpeg is installed:
   - Windows: Download from [FFmpeg website](https://ffmpeg.org/download.html) or use `choco install ffmpeg`.
   - Linux/Mac: Install via `sudo apt-get install ffmpeg` (Ubuntu) or `brew install ffmpeg` (Mac).

## Usage
Run the script with the following command:
```bash
python slideshow.py <duration> <folder_path> [image_names] [--output-dir <output_dir>] [--keep-original-resolution] [--debug]
```

### Arguments
- `duration`: Duration per image in seconds (e.g., `5.0`).
- `folder_path`: Directory containing images.
- `image_names`: Optional list of image names, a range (e.g., `img1-img10`), or a wildcard (e.g., `img*`). If omitted, processes all images in the folder.
- `--output-dir`: Directory for output videos and metadata (default: `folder_path`).
- `--keep-original-resolution`: Preserve original image resolutions instead of standardizing.
- `--debug`: Enable verbose output for debugging.

### Example
```bash
python slideshow.py 5.0 images img1-img5 --output-dir output --debug
```
This creates 5-second video slides from `img1` to `img5` in the `images` directory, saving them to the `output` directory with debug output.

## Output
- Video slides saved as `<image_name>_slide.mp4` in the output directory.
- Metadata saved as `slideshow_metadata.json` to track input images and output videos.
- Temporary files are created in a `temp` directory and cleaned up after processing.

## Notes
- Ensure the input directory contains supported image files.
- Image names should include numeric parts for proper sorting (e.g., `img1.jpg`, `img2.png`).
- If FFmpeg commands fail, verify that FFmpeg is correctly installed and accessible.

## License
MIT License - see [LICENSE](LICENSE) for details.
