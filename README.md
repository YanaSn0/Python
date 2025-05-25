Since you now have two scripts—download.py (from your latest upload) and process.py (from the previous interaction)—I'll create a single README file named README.md that covers both scripts under the project name "Download + Process." This README will include commands, usage examples, and setup instructions for both scripts, making it easy for users to understand and use them together.
Download + Process
This project contains two Python scripts, download.py and process.py, designed to download and process media files (videos, audio, images) for various purposes, such as creating social media content. Together, they provide a workflow to download media from URLs and process them into desired formats with effects like trimming, looping, splitting, combining, converting, creating slideshows, and concatenating videos.
download.py: Downloads media (videos, audio, images) from URLs listed in a urls.txt file.
process.py: Processes downloaded media files with various operations like trimming, looping, splitting, combining, converting, creating slideshows, and concatenating videos with effects.
Features
download.py
Download audio, video, combined video/audio, split video and audio, pictures, or all types of media.
Support for duration limits, authentication, and thumbnails.
Option to keep original files or re-encode to a universal format.
process.py
Trim and loop audio or video to a desired duration.
Split videos into separate video and audio files.
Combine video and audio files into a single video.
Convert videos to a universal format (e.g., 1080x1920 for portrait).
Create slideshow videos from images.
Concatenate multiple videos with a 1-second fade-in effect at the start of each segment.
Prerequisites
Before using the scripts, ensure you have the following installed:
Python 3.x: Both scripts are written in Python.
FFmpeg: Required for media processing. Download FFmpeg and add it to your system PATH.
yt-dlp: For downloading videos and audio in download.py. Install via pip:
pip install yt-dlp
gallery-dl: For downloading images in download.py. Install via pip:
pip install gallery-dl
Pillow (PIL): For image processing in process.py (slideshow submode). Install via pip:
pip install Pillow
Firefox Browser: download.py uses Firefox cookies for authentication by default. Ensure Firefox is installed, or provide alternative authentication methods.
Setup
Clone the Repository:
git clone https://github.com/yourusername/your-repo-name.git
cd your-repo-name
Install Dependencies:
Ensure all required Python packages are installed:
pip install yt-dlp gallery-dl Pillow
Ensure FFmpeg is Accessible:
Verify FFmpeg is in your PATH:
ffmpeg -version
Create a urls.txt File for download.py:
In the same directory as download.py, create a file named urls.txt.
Add one or more URLs to download, one per line. You can separate multiple URLs on the same line with a semicolon (;).
Example urls.txt:
https://www.youtube.com/watch?v=example1
https://www.tiktok.com/@user/video/example2;https://twitter.com/user/status/example3
https://example.com/image.jpg
Usage
Both scripts are run using Python and support various submodes and options. Below are the commands and examples for each script.
download.py
General Syntax
python download.py <submode> [options]
Submodes
audio: Download audio only (saved as .m4a).
video: Download video only (saved as .mp4, audio stripped).
combined: Download video with audio (saved as .mp4).
split: Download video with audio and split into video-only (.mp4) and audio-only (.m4a) files.
pic: Download images (saved as .jpg or other image formats).
all: Attempt to download all types (video with audio, audio-only, video-only, pictures) until one succeeds.
Options
Option
Description
Example Value
--output-dir, -o
Directory to save downloaded files (default: current directory).
--output-dir ./downloads
--keep-original
Keep the original file without re-encoding.
--keep-original
--clear-dir
Clear the output directory before downloading.
--clear-dir
--username
Username for authenticated downloads.
--username myuser
--password
Password for authenticated downloads.
--password mypass
--cookies
Path to a cookies file for authentication.
--cookies cookies.txt
--duration
Limit the duration of downloaded videos/audio (in seconds).
--duration 60
--audio-only
In all submode, download audio only (skips video and pictures).
--audio-only
--link
In audio submode, name files based on URL instead of title.
--link
--debug
Enable debug output for troubleshooting.
--debug
Authentication
By default, download.py uses Firefox cookies (--cookies-from-browser firefox). Alternatively:
Username and password:
--username myuser --password mypass
Custom cookies file:
--cookies path/to/cookies.txt
Examples for download.py
Download Audio Only (First 60 Seconds):
python download.py audio --output-dir ./downloads --duration 60 --debug
Output: A_1_Title.m4a, A_2_Title.m4a, etc.
With URL-based naming:
python download.py audio --output-dir ./downloads --duration 60 --link
Output: A_1_youtube.com_watch_v_example.m4a.
Download Video Only (Keep Original):
python download.py video --output-dir ./downloads --keep-original
Output: V_1_Title.mp4, V_2_Title.mp4, etc.
Download Combined Video and Audio (Universal Format):
python download.py combined --output-dir ./downloads
Output: U_1_Title.mp4, U_2_Title.mp4, etc.
Keep original:
python download.py combined --output-dir ./downloads --keep-original
Output: O_1_Title.mp4, etc.
Split Video and Audio:
python download.py split --output-dir ./downloads --duration 120
Output: U_1_Title_video.mp4, U_1_Title_audio.m4a, etc.
Download Pictures:
python download.py pic --output-dir ./downloads
Output: P_1.jpg, P_2.jpg, etc.
Download All Types (With Thumbnails):
python download.py all --output-dir ./downloads --duration 90
Output: U_1_Title.mp4, A_1_Title.m4a, V_1_Title.mp4, P_1.jpg, U_1_Title_thumb.webp, etc.
Audio-only:
python download.py all --output-dir ./downloads --audio-only
Output: A_1_Title.m4a only.
Clear Output Directory:
python download.py combined --output-dir ./downloads --clear-dir
Use Custom Authentication:
python download.py combined --output-dir ./downloads --username myuser --password mypass
process.py
General Syntax
python process.py <submode> <output_type_or_args> [options]
Submodes
trim: Trim audio or video without looping.
Output types: a (audio, .m4a), v (video, .mp4).
loop: Trim and loop audio or video to a desired duration.
Output types: a (audio, .m4a), v (video, .mp4).
loopaudio: Loop an audio file to a desired duration without trimming.
split: Split a video into separate video and audio files.
combine: Combine a video and audio file into a single video.
convert: Convert videos to a universal format (e.g., 1080x1920 for portrait).
slide: Create a slideshow video from images.
concat: Concatenate multiple videos with a 1-second fade-in effect per segment.
Options
Option
Description
Example Value
--output-dir, -o
Directory to save processed files (default: varies by submode).
--output-dir ./processed
--start
Start time in seconds for trimming (default: 0).
--start 10
--end
End time in seconds for trimming (required for trim and loop).
--end 20
--duration
Desired output duration in seconds (for loop, loopaudio).
--duration 30
--username
Username for authenticated downloads (used in title fetching).
--username myuser
--password
Password for authenticated downloads.
--password mypass
--cookies
Path to a cookies file for authentication.
--cookies cookies.txt
--debug
Enable debug output for troubleshooting.
--debug
Examples for process.py
Trim Video:
Trim a video from 10 to 20 seconds:
python process.py trim v ./downloads/U1.mp4 --start 10 --end 20 --output-dir ./processed --debug
Output: V_1_U1.mp4
Trim and Loop Audio:
Trim audio from 0 to 15 seconds and loop to 30 seconds:
python process.py loop a ./downloads/A1.m4a --start 0 --end 15 --duration 30 --output-dir ./processed
Output: AL_1_A1.m4a
Loop Audio Without Trimming:
Loop an audio file to 60 seconds:
python process.py loopaudio ./downloads/A1.m4a 60 --output-dir ./processed
Output: L_1_A1.m4a
Split Video into Video and Audio:
python process.py split ./downloads/U1.mp4 --output-dir ./processed
Output: V_1_U1_video.mp4, V_1_U1_audio.m4a
Combine Video and Audio:
Combine a video and audio file:
python process.py combine ./downloads/V1.mp4 ./downloads/A1.m4a --output-dir ./processed
Output: C_1_V1_A1.mp4
Convert Videos to Universal Format:
Convert all videos in a directory to 1080x1920 (portrait) or other resolutions based on aspect ratio:
python process.py convert ./downloads --output-dir ./converted
Output: U1.mp4, U2.mp4, etc.
Create a Slideshow:
Create a slideshow from images with a 2-second delay per image:
python process.py slide 2 ./images/image1.jpg ./images/image2.jpg --output-dir ./processed
Output: S_1_Slideshow.mp4
Concatenate Videos with Fade-In:
Concatenate all videos in a directory with a 1-second fade-in at the start of each segment:
python process.py concat ./converted --output-dir ./combined --debug
Output: C_1_Concatenated.mp4
Workflow Example: Download and Process Videos
Download Videos:
Download videos in universal format to the downloads directory:
python download.py combined --output-dir ./downloads --duration 60
Convert Videos:
Convert downloaded videos to ensure consistent resolution (e.g., 1080x1920):
python process.py convert ./downloads --output-dir ./converted
Concatenate Videos:
Concatenate the converted videos with a 1-second fade-in effect:
python process.py concat ./converted --output-dir ./combined
Loop for YouTube:
Loop the concatenated video to 300 seconds for YouTube (to avoid being a Short):
python process.py loop v ./combined/C_1_Concatenated.mp4 --start 0 --end 171.12 --duration 300 --output-dir ./looped
Output File Naming
download.py
Audio: A_1_Title.m4a
Video (no audio): V_1_Title.mp4
Combined (original): O_1_Title.mp4
Combined (universal): U_1_Title.mp4
Picture: P_1.jpg (extension varies)
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
FFmpeg Not Found: Ensure FFmpeg is installed and in your PATH.
Authentication Issues (download.py): Verify Firefox cookies or provide a username/password or cookies file.
File Cleanup: Both scripts clean up temporary files, but if interrupted, manually delete temp_* files or directories.
Debug Mode: Enable --debug for detailed output:
python download.py combined --output-dir ./downloads --debug
python process.py concat ./converted --output-dir ./combined --debug
Notes
Ensure URLs in urls.txt are valid and accessible for download.py.
process.py assumes input files exist and are in a supported format.
The universal format in both scripts adjusts resolution based on aspect ratio (e.g., 1080x1920 for portrait videos).
Thumbnails are only downloaded in the all submode of download.py.
Contributing
Submit issues or pull requests to improve the scripts. Suggestions for new features or bug fixes are welcome!
License
This project is licensed under the MIT License. See the LICENSE file for details.
This README provides a comprehensive guide for using both download.py and process.py in a unified workflow. You can add a LICENSE file to your repository if you choose to use the MIT License or another license. Let me know if you'd like to adjust any part of the README!
