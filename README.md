Media Processing Script 📹🎵🖼️

Python

License

Dependencies

A versatile Python script (s.py) for downloading, processing, combining, splitting, and creating slideshows from media files (videos, audio, images). Powered by yt-dlp, gallery-dl, and ffmpeg, this tool supports platforms like YouTube, Instagram, and TikTok.
Features ✨

    Download: Fetch videos, audio, or images from URLs in urls.txt.
    Combine: Merge a video file with an audio file (e.g., V1.mp4 + A1.m4a → C1.mp4).
    Split: Extract video and audio from a single file (e.g., O1.mp4 → V1.mp4 + A1.m4a).
    Slideshow: Create a video from images (e.g., P1.jpg, P2.jpg → S1.mp4).
    Loop: Extend an audio file to a specified duration.
    Custom Output: Save files to any directory (e.g., C:\Output).

Note: Combining multiple video files is not supported. Use ffmpeg manually for video concatenation (see Workarounds (#workarounds)).
Installation 🚀
Prerequisites

    Python: 3.6 or higher
    Dependencies:
        yt-dlp: Downloads videos and audio.
        gallery-dl: Downloads images.
        ffmpeg & ffprobe: Processes and analyzes media.

Setup

    Clone the Repository:
    bash

    git clone https://github.com/yourusername/media-processing-script.git
    cd media-processing-script

    Install Python Dependencies:
    bash

    pip install yt-dlp gallery-dl

    Install ffmpeg & ffprobe:
        Windows:
            Download from ffmpeg.org.
            Add ffmpeg.exe and ffprobe.exe to your PATH.
        macOS:
        bash

        brew install ffmpeg

        Linux:
        bash

        sudo apt-get install ffmpeg

    Prepare urls.txt:
        Create urls.txt in the same directory as s.py.
        Add URLs (one per line or semicolon-separated):

        https://www.youtube.com/watch?v=dQw4w9WgXcQ
        https://example.com/image;https://example.com/video

Usage 📚
Run commands from the terminal in the script’s directory. Outputs are saved to a specified directory (e.g., C:\Output).
Commands
1. Download Media
Download videos, audio, or images from urls.txt.
bash

python s.py download <submode> --output-dir C:\Output

Submodes:

    audio: Audio only (A1.m4a).
    video: Video only (V1.mp4).
    combined: Video with audio (O1.mp4 or U1.mp4).
    split: Video and audio separately (O1_video.mp4, O1_audio.m4a).
    pic: Images (P1.jpg).
    all: Try video, image, video-only, audio.
    all+a: all + extract audio.
    all+a+v: all+a + split video-only.
    all+v: all + split video-only.

Options:

    --output-dir path: Output directory (e.g., C:\Output).
    --keep-original: Keep original format.
    --clear-dir: Clear output directory first.
    --username user --password pass: Login credentials.
    --cookies path/to/cookies.txt: Cookies file.

Example:
bash

python s.py download all --output-dir C:\Output

2. Combine Video + Audio
Merge one video with one audio file.
bash

python s.py combine path/to/video path/to/audio --output-dir C:\Output

Example:
bash

python s.py combine videos/V1 audio/A1 --output-dir C:\Output

3. Split Video
Extract video and audio from a file.
bash

python s.py split path/to/video --output-dir C:\Output

Example:
bash

python s.py split videos/O11 --output-dir C:\Output

4. Create Slideshow
Make a video from images with a specified delay (seconds).
bash

python s.py slide delay path/to/image1 path/to/image2 --output-dir C:\Output

Example:
bash

python s.py slide 5 pictures/P1 pictures/P2 --output-dir C:\Output

5. Loop Audio
Extend an audio file to a duration (seconds).
bash

python s.py loop path/to/audio duration --output-dir C:\Output

Example:
bash

python s.py loop audio/A1 15 --output-dir C:\Output

Authentication 🔒
Some platforms (e.g., Instagram) require login:

    Default: --cookies-from-browser firefox (uses Firefox cookies).
    Cookies File: --cookies path/to/cookies.txt.
    Credentials: --username user --password pass.

Workarounds 🛠️
Combining Multiple Videos
The script doesn’t combine multiple videos (e.g., V1.mp4 + V2.mp4). Use ffmpeg:

    Create videos.txt in C:\Output:

    file 'V1.mp4'
    file 'V2.mp4'

    Run:
    bash

    ffmpeg -f concat -safe 0 -i videos.txt -c copy C:\Output\combined.mp4

Tip: Ensure videos have the same resolution and codec. Convert if needed:
bash

ffmpeg -i V1.mp4 -c:v libx264 -c:a aac -vf scale=1920:1080,setsar=1 -r 30 V1_converted.mp4

Safety for Sharing 📢
To share this script safely (e.g., on GitHub):

    Sanitize urls.txt:
        Remove private URLs or tokens.
        Use public placeholders (e.g., https://example.com/video).
    Protect Credentials:
        Don’t hardcode usernames, passwords, or cookies in s.py.
        Exclude cookies files from the repository.
    Check Outputs:
        Review files (O1.mp4, A1.m4a, P1.jpg) for sensitive content.
        Strip metadata:
        bash

        ffmpeg -i input.mp4 -map_metadata -1 -c copy output.mp4

    Secure Cookies:
        Store cookies files privately.
        Regenerate cookies if expired.
    Respect Terms:
        Comply with platform terms (YouTube, Instagram, etc.).
        Don’t share content without permission.
    GitHub Best Practices:
        Add this README and an MIT License.
        Exclude local paths and temporary files (e.g., temp_download.mp4).
        Use .gitignore:

        urls.txt
        *.mp4
        *.m4a
        *.jpg
        temp_*

    Sanitize Logs:
        Don’t share error logs with private URLs.
        Replace sensitive data with placeholders.

Troubleshooting 🐛

    yt-dlp Errors:
        Debug formats: yt-dlp --list-formats <url>.
        Check authentication.
    ffmpeg Errors:
        Verify ffmpeg/ffprobe in PATH: ffmpeg -version.
        Ensure file compatibility.
    gallery-dl Errors:
        Validate cookies for Instagram, etc.
    File Not Found:
        Ensure urls.txt exists for download mode.
        Check file paths.
    Crash Cleanup:
        Delete temporary files:
        bash

        del C:\Output\temp_* /q
        rmdir C:\Output\temp_images /s /q

Contributing 🤝
Contributions are welcome! To contribute:

    Fork the repository.
    Create a feature branch (git checkout -b feature-name).
    Commit changes (git commit -m "Add feature").
    Push to the branch (git push origin feature-name).
    Open a Pull Request.

License 📜
This project is licensed under the MIT License. See LICENSE for details.
Acknowledgments 🙌

    Built with yt-dlp, gallery-dl, and ffmpeg.
    Inspired by the need for flexible media processing.
