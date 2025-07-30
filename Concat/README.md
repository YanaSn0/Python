# Video Concatenation Script

This Python script concatenates `.mp4` video files from a specified directory into a single video, following a specific order: the first video (alphabetically sorted) as a "warning" file, followed by alternating pairs of 2 "Pic" files and 2 "Uni" files, with any remaining files appended at the end. It uses FFmpeg to standardize video formats and concatenate them.

## Features
- Processes `.mp4` files in a specified input directory.
- Standardizes videos to a target resolution (default: 1920x1080) and format.
- Adds silent audio to videos without audio tracks.
- Maintains metadata to track processed files and avoid reprocessing.
- Supports debug mode and quality presets for FFmpeg encoding.

## Requirements
- Python 3.6+
- FFmpeg and FFprobe installed and accessible in the system PATH
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
   - Windows: Download from [FFmpeg website](https://ffmpeg.org/download.html) or use a package manager like `choco install ffmpeg`.
   - Linux/Mac: Install via `sudo apt-get install ffmpeg` (Ubuntu) or `brew install ffmpeg` (Mac).

## Usage
Run the script with the following command:
```bash
python concat.py <input_dir> [--output-dir <output_dir>] [--debug] [--resolution <width>x<height>] [--quality <1-3>]
```

### Arguments
- `input_dir`: Directory containing `.mp4` files (required).
- `--output-dir`: Directory for output video and metadata (default: current directory).
- `--debug`: Enable verbose output for debugging (optional).
- `--resolution`: Target resolution (e.g., `1920x1080`, default: `1920x1080`).
- `--quality`: Encoding quality (1 = fastest, 3 = slowest/best, default: 3).

### Example
```bash
python concat.py pc/concat_in --output-dir pc/concat_out --debug --quality 1
```
This processes all `.mp4` files in `pc/concat_in`, outputs the concatenated video to `pc/concat_out/Concat_1.mp4`, and enables debug output with the fastest encoding quality.

## Output
- Concatenated video saved as `Concat_<number>.mp4` in the output directory.
- Metadata saved as `concat_metadata.json` to track input and output files.
- Temporary files are created in a `temp` directory and cleaned up after processing.

## Notes
- Ensure the input directory contains `.mp4` files with names including "pic" or "uni" for proper sorting.
- The script expects even resolution dimensions (e.g., 1920x1080).
- If FFmpeg commands fail, check that FFmpeg is correctly installed and accessible.

## License
MIT License - see [LICENSE](LICENSE) for details.
