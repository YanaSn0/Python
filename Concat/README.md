# Video Concatenation Script

Concatenates multiple video files into a single high-quality video using FFmpeg. Supports custom resolutions, fade transitions, and consistent audio/video output.

## Features
- Concatenates `.mp4` and `.mkv` files.
- Custom resolution via `--resolution` (default: 1920x1080).
- Scales and pads videos to maintain aspect ratios.
- Optional fade transitions between videos.
- High-quality encoding (`libx264`, `veryslow`, 5000k bitrate).
- Processes individual files or a directory.
- Debug mode for detailed logs.

## Requirements
- Python 3.6+
- FFmpeg (with ffprobe) in system PATH
  - Windows: `choco install ffmpeg`
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt-get install ffmpeg` or equivalent

## Installation
1. Clone repo:
   ```bash
   git clone https://github.com/your-username/video-concatenation.git
   cd video-concatenation
   ```
2. Verify FFmpeg: `ffmpeg -version`
3. (Optional) Virtual env:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

## Usage
```bash
python concat_videos.py <video_paths> [--output-dir DIR] [--resolution WIDTHxHEIGHT] [--no-fades] [--debug]
```
- `video_paths`: Video files or a directory.
- `--output-dir`: Output directory (default: `.`).
- `--resolution`: Target resolution (default: `1920x1080`).
- `--no-fades`: Disable fade transitions.
- `--debug`: Enable detailed logging.

### Examples
- Concatenate videos:
  ```bash
  python concat_videos.py video1.mp4 video2.mp4 --output-dir output
  ```
- Directory, vertical video:
  ```bash
  python concat_videos.py /path/to/videos --resolution 1080x1920 --output-dir output
  ```
- No fades, debug:
  ```bash
  python concat_videos.py video1.mp4 video2.mp4 --no-fades --debug
  ```

Output: `Concat_N.mp4` in the specified directory.

## Resolutions
- **1920x1080**: Default, ideal for YouTube/TV.
- **1080x1920**: Social media (TikTok, Instagram).
- **3840x2160**: 4K for high-end displays.
Use `--resolution WIDTHxHEIGHT` (even numbers).

## Notes
- Uses `veryslow` preset for quality; for faster encoding, edit script to use `-preset medium`.
- Videos without audio get a silent track.
- Directory videos sorted by `S_N.mp4` pattern.

## Troubleshooting
- FFmpeg errors: Ensure FFmpeg is installed.
- Invalid resolution: Use even `WIDTHxHEIGHT`.
- Enable `--debug` for logs.

## License
MIT License. See [LICENSE](LICENSE).

```

### Instructions
1. **Copy-paste**: Save as `README.md` in your repository root.
2. **Update URL**: Replace `https://github.com/your-username/video-concatenation.git` with your repo URL.
3. **License**: Add a `LICENSE` file with MIT License text (or your choice). Example:
   ```markdown
   MIT License

   Copyright (c) 2025 Your Name

   Permission is hereby granted, free of charge, to any person obtaining a copy
   of this software and associated documentation files (the "Software"), to deal
   in the Software without restriction, including without limitation the rights
   to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
   copies of the Software, and to permit persons to whom the Software is
   furnished to do so, subject to the following conditions:

   The above copyright notice and this permission notice shall be included in all
   copies or substantial portions of the Software.

   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
   OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
   SOFTWARE.
   ```
4. **File Structure**: Ensure `concat_videos.py`, `README.md`, and `LICENSE` are in the repo root.
