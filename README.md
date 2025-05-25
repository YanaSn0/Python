Download + Process
Project Banner: https://via.placeholder.com/1200x300.png?text=Download+%26+Process
This repository contains two Python scripts, download.py and process.py, designed to streamline the process of downloading and processing media files (videos, audio, images) for creating content, such as for social media platforms like YouTube and Facebook.
download.py: Downloads media from URLs listed in a urls.txt file, supporting videos, audio, images, or a combination.

process.py: Processes downloaded media with operations like trimming, looping, splitting, combining, converting, creating slideshows, and concatenating videos with effects.

Features
download.py
Submodes: Download audio, video, combined video/audio, split video and audio, pictures, or all types.

Customization: Limit duration, keep original files, or re-encode to a universal format (e.g., 1080x1920 for portrait).

Thumbnails: Optionally download thumbnails in the all submode.

Authentication: Supports username/password or cookies for private content.

process.py
Submodes: Trim, loop, split, combine, convert, create slideshows, or concatenate videos.

Effects: Add a 1-second fade-in effect when concatenating videos.

Universal Format: Convert videos to consistent resolutions based on aspect ratio (e.g., 1080x1920 for portrait).

Slideshows: Create videos from images with customizable delays.

Prerequisites
Ensure the following are installed before using the scripts:
Python 3.x: Install Python at https://www.python.org/downloads/

FFmpeg: Required for media processing. Download FFmpeg at https://ffmpeg.org/download.html and add it to your PATH.

yt-dlp: For downloading videos and audio in download.py. Install via pip:
pip install yt-dlp

gallery-dl: For downloading images in download.py. Install via pip:
pip install gallery-dl

Pillow (PIL): For image processing in process.py (slideshow submode). Install via pip:
pip install Pillow

Firefox Browser: download.py uses Firefox cookies for authentication by default. Alternatively, provide a cookies file or username/password.

Setup
Clone the Repository:
git clone https://github.com/yourusername/your-repo-name.git
cd your-repo-name

Install Dependencies:
pip install yt-dlp gallery-dl Pillow

Verify FFmpeg:
Ensure FFmpeg is accessible in your PATH:
ffmpeg -version

Prepare urls.txt for download.py:
Create a urls.txt file in the repository root.

Add URLs, one per line. Use semicolons (;) to separate multiple URLs on the same line.

Example urls.txt:
https://www.youtube.com/watch?v=example1
https://www.tiktok.com/@user/video/example2;https://twitter.com/user/status/example3
https://example.com/image.jpg

Usage
download.py
Syntax
python download.py <submode> [options]
Submodes
audio: Download audio only (.m4a).

video: Download video only (.mp4, audio stripped).

combined: Download video with audio (.mp4).

split: Download and split into video-only (.mp4) and audio-only (.m4a).

pic: Download images (.jpg, .png, etc.).

all: Attempt all types (video with audio, audio-only, video-only, pictures) until one succeeds.

Options
Option              Description                                              Example Value
--output-dir, -o    Directory to save files (default: current directory).    --output-dir ./downloads
--keep-original     Keep original files without re-encoding.                 --keep-original
--clear-dir         Clear output directory before downloading.               --clear-dir
--username          Username for authentication.                             --username myuser
--password          Password for authentication.                             --password mypass
--cookies           Path to a cookies file.                                  --cookies cookies.txt
--duration          Limit duration of downloads (seconds).                   --duration 60
--audio-only        In all submode, download audio only.                     --audio-only
--link              In audio submode, name files using URL instead of title. --link
--debug             Enable debug output.                                     --debug
Authentication
By default, uses Firefox cookies (--cookies-from-browser firefox). Alternatives:
Username and password: --username myuser --password mypass

Cookies file: --cookies path/to/cookies.txt

Examples
Download Audio (First 60 Seconds):
python download.py audio --output-dir ./downloads --duration 60 --debug
Output: A_1_Title.m4a

Download Video (Keep Original):
python download.py video --output-dir ./downloads --keep-original
Output: V_1_Title.mp4

Download Combined Video and Audio:
python download.py combined --output-dir ./downloads
Output: U_1_Title.mp4

Split Video and Audio:
python download.py split --output-dir ./downloads --duration 120
Output: U_1_Title_video.mp4, U_1_Title_audio.m4a

Download Pictures:
python download.py pic --output-dir ./downloads
Output: P_1.jpg

Download All Types (With Thumbnails):
python download.py all --output-dir ./downloads --duration 90
Output: U_1_Title.mp4, A_1_Title.m4a, U_1_Title_thumb.webp, etc.

process.py
Syntax
python process.py <submode> <output_type_or_args> [options]
Submodes
trim <a|v>: Trim audio (a) or video (v) without looping.

loop <a|v>: Trim and loop audio (a) or video (v).

loopaudio: Loop an audio file without trimming.

split: Split a video into video and audio files.

combine: Combine video and audio into a single video.

convert: Convert videos to a universal format.

slide: Create a slideshow video from images.

concat: Concatenate videos with a 1-second fade-in per segment.

Options
Option              Description                                              Example Value
--output-dir, -o    Directory to save files (default: varies by submode).    --output-dir ./processed
--start             Start time for trimming (default: 0).                    --start 10
--end               End time for trimming (required for trim, loop).         --end 20
--duration          Desired output duration (for loop, loopaudio).           --duration 30
--username          Username for title fetching (optional).                  --username myuser
--password          Password for title fetching (optional).                  --password mypass
--cookies           Cookies file for title fetching (optional).              --cookies cookies.txt
--debug             Enable debug output.                                     --debug
Examples
Trim Video:
python process.py trim v ./downloads/U1.mp4 --start 10 --end 20 --output-dir ./processed
Output: V_1_U1.mp4

Trim and Loop Audio:
python process.py loop a ./downloads/A1.m4a --start 0 --end 15 --duration 30 --output-dir ./processed
Output: AL_1_A1.m4a

Loop Audio:
python process.py loopaudio ./downloads/A1.m4a 60 --output-dir ./processed
Output: L_1_A1.m4a

Split Video:
python process.py split ./downloads/U1.mp4 --output-dir ./processed
Output: V_1_U1_video.mp4, V_1_U1_audio.m4a

Combine Video and Audio:
python process.py combine ./downloads/V1.mp4 ./downloads/A1.m4a --output-dir ./processed
Output: C_1_V1_A1.mp4

Convert Videos:
python process.py convert ./downloads --output-dir ./converted
Output: U1.mp4, U2.mp4, etc.

Create Slideshow:
python process.py slide 2 ./images/image1.jpg ./images/image2.jpg --output-dir ./processed
Output: S_1_Slideshow.mp4

Concatenate Videos:
python process.py concat ./converted --output-dir ./combined --debug
Output: C_1_Concatenated.mp4

Workflow Example
Download Videos:
python download.py combined --output-dir ./downloads --duration 60

Convert Videos:
python process.py convert ./downloads --output-dir ./converted

Concatenate with Fade-In:
python process.py concat ./converted --output-dir ./combined

Loop for YouTube:
python process.py loop v ./combined/C_1_Concatenated.mp4 --start 0 --end 171.12 --duration 300 --output-dir ./looped

Output File Naming
download.py
Audio: A_1_Title.m4a

Video (no audio): V_1_Title.mp4

Combined (original): O_1_Title.mp4

Combined (universal): U_1_Title.mp4

Picture: P_1.jpg

Thumbnails: <prefix>_<number>_Title_thumb.webp

process.py
Trim (audio/video): A_1_Title.m4a or V_1_Title.mp4

Loop (audio/video): AL_1_Title.m4a or VL_1_Title.mp4

Loopaudio: L_1_Title.m4a

Split: V_1_Title_video.mp4, V_1_Title_audio.m4a

Combine: C_1_VideoTitle_AudioTitle.mp4

Convert: U1.mp4, U2.mp4, etc.

Slide: S_1_Slideshow.mp4

Concat: C_1_Concatenated.mp4

Troubleshooting
FFmpeg Not Found:
Ensure FFmpeg is installed and in your PATH.

Authentication Issues (download.py):
Verify Firefox cookies or provide credentials.

Debugging:
Use --debug for detailed output:
python download.py combined --output-dir ./downloads --debug
python process.py concat ./converted --output-dir ./combined --debug

File Cleanup:
If interrupted, manually delete temp_* files or directories.

Contributing
Contributions are welcome! Please submit issues or pull requests for bug fixes or new features.
License
This project is licensed under the MIT License. See the LICENSE file for details.

