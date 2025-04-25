# Python

Media Processing Script README
This Python script (s.py) downloads, processes, combines, splits, or creates slideshows from media files (videos, audios, images) using yt-dlp, gallery-dl, and ffmpeg. Below is a guide to set up and use the sanitized script safely, with all commands and precautions for resharing.
Commands

    Download Mode
    Download media from URLs in urls.txt.

python s.py download audio
python s.py download video
python s.py download combined
python s.py download split
python s.py download pic
python s.py download all
python s.py download all+a
python s.py download all+a+v
python s.py download all+v
Add options after submode:

    --output-dir path/to/dir (sets output directory, default is current directory)
    --keep-original (keeps original format, no conversion)
    --clear-dir (clears output directory before starting)
    --username user (username for login)
    --password pass (password for login)
    --cookies path/to/cookies.txt (cookies file for login)

Example:
python s.py download all --output-dir ./media --keep-original

    Combine Mode
    Combine video and audio into one video.

python s.py combine path/to/video path/to/audio
Add option:

    --output-dir path/to/dir (sets output directory)

Example:
python s.py combine ./videos/V1 ./audio/A1 --output-dir ./output

    Split Mode
    Split video into video and audio files.

python s.py split path/to/video
Add option:

    --output-dir path/to/dir (sets output directory)

Example:
python s.py split ./videos/O11 --output-dir ./split

    Slide Mode
    Create slideshow video from images.

python s.py slide delay path/to/image1 path/to/image2
Add option:

    --output-dir path/to/dir (sets output directory)

Example:
python s.py slide 5 ./pictures/P1 ./pictures/P2 --output-dir ./slideshow

    Loop Mode
    Loop audio to a specific duration.

python s.py loop path/to/audio duration
Add option:

    --output-dir path/to/dir (sets output directory)

Example:
python s.py loop ./audio/A1 15 --output-dir ./looped
Setup Instructions
Prerequisites

    Python 3.6 or higher.
    Install tools:
        yt-dlp: Downloads videos and audio.
        gallery-dl: Downloads images.
        ffmpeg: Processes media.
        ffprobe: Analyzes media (comes with ffmpeg).

Install tools:
pip install yt-dlp gallery-dl
Install ffmpeg/ffprobe:

    Windows: Download from ffmpeg.org/download.html, add to PATH.
    macOS: brew install ffmpeg
    Linux: sudo apt-get install ffmpeg

Installation

    Save the script as s.py.
    Create urls.txt in the same directory for download mode. Add URLs (one per line or separated by semicolons).
    Example urls.txt:
    https://example.com/video1;https://example.com/video2
    https://example.com/image
    Ensure yt-dlp, gallery-dl, ffmpeg, ffprobe are in your system PATH.

Fixing Path Issues After Crash
If the script crashed and you're unsure about paths:

    Check if s.py is in your current directory. Run:
    dir (Windows) or ls (macOS/Linux)
    If s.py is missing, save it again.
    Verify urls.txt exists in the same directory as s.py. If missing, recreate it with URLs.
    If using --output-dir, ensure the path exists (e.g., mkdir media for --output-dir ./media).
    Delete leftover temporary files (temp_download.mp4, temp_audio.m4a, temp_images folder) in the output directory to avoid conflicts:
    del temp_* (Windows) or rm -rf temp_* (macOS/Linux)
    Run a test command:
    python s.py download all
    If it fails, check error messages for missing tools or invalid paths.

Running the Script

    Open terminal in the directory with s.py.
    Run a command (e.g., python s.py download all).
    For download mode, ensure urls.txt has valid URLs.

Authentication

    Use --cookies-from-browser firefox (default) or --cookies path/to/cookies.txt.
    Use --username user --password pass for platforms needing login.
    For Instagram or similar, export Firefox cookies or use a cookies file.

Safety Precautions for Resharing

    Sanitize urls.txt:
        Remove private URLs or tokens.
        Use public URLs (e.g., https://example.com/placeholder).
    Avoid Credentials:
        Don't add usernames, passwords, or cookies to s.py.
        Exclude cookies files when sharing.
    Check Output Files:
        Review O#.mp4, A#.m4a, P#.jpg for sensitive content.
        Strip metadata:
        ffmpeg -i input.mp4 -map_metadata -1 -c copy output.mp4
    Secure Cookies:
        Store cookies files securely, don't share them.
        Regenerate cookies if they expire.
    Respect Platform Rules:
        Follow YouTube, Instagram, etc., terms of service.
        Don't share content without owner permission.
    Sharing Script:
        Include this README if sharing on GitHub.
        Add a license (e.g., MIT).
        Remove local paths from s.py.
    Sanitize Logs:
        Don't share error logs with private URLs.
        Replace sensitive data with placeholders.

Troubleshooting

    yt-dlp fails: Run yt-dlp --list-formats url to check formats. Verify login details.
    ffmpeg fails: Ensure ffmpeg, ffprobe are in PATH. Check file compatibility.
    gallery-dl fails: Verify cookies for Instagram, etc.
    File not found: Check urls.txt or file paths.
    Crash cleanup: Delete temp_download.mp4, temp_audio.m4a, temp_images in output directory.

Notes

    Outputs: A1.m4a, V1.mp4, P1.jpg, O1.mp4, U1.mp4, S1.mp4, L1.m4a, C1.mp4.
    Temporary files are removed automatically, but check output directory if errors occur.
    Supports YouTube, Instagram, TikTok, etc., but some platforms need special handling.

For help, check yt-dlp, gallery-dl, or ffmpeg documentation.
This README uses the exact command python s.py download all and clarifies path setup after a crash. Copy this into Notepad and save as README.txt. Let me know if you need further help with the crash or specific paths!
