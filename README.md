# Python
Script to automate bulk downloads from 1000's of sites

Below is a README.md file for your d.py script, formatted for GitHub. It includes an overview, prerequisites, installation instructions, usage examples for all commands, and additional notes. The README is designed to be clear and concise, making it easy for users to understand how to use the script.
d.py - Media Downloader and Processor
d.py is a Python script for downloading, processing, combining, and creating slideshow videos from media files. It supports downloading videos, audio, and images from URLs (e.g., Instagram, X), combining video and audio files, splitting videos into separate video and audio files, creating slideshow videos from images, and looping audio to a specified duration. The script uses tools like yt-dlp, gallery-dl, and ffmpeg to handle media processing.
Features

    Download Media: Download videos, audio, or images from URLs in urls.txt.
    Combine Media: Combine existing video and audio files, looping audio if needed.
    Split Media: Split a video into separate video and audio files.
    Create Slideshows: Generate a slideshow video from images with a specified delay.
    Loop Audio: Loop an audio file to match a specified duration.
    Dynamic Resizing: Automatically resize images to fit a common resolution for slideshows.
    Consistent Naming: Outputs are named sequentially (e.g., A1.m4a, V1.mp4, P1.jpg).

Prerequisites
Before using the script, ensure you have the following installed:

    Python: Version 3.6 or higher.
    FFmpeg: Required for media processing.
        Download from FFmpeg website and add it to your system PATH.
    yt-dlp: For downloading videos and audio.
        Install via pip: pip install yt-dlp
    gallery-dl: For downloading images.
        Install via pip: pip install gallery-dl
    Firefox: For authentication (the script uses --cookies-from-browser firefox).
        Log into platforms like Instagram or X on Firefox to bypass rate-limiting.

Installation

    Clone the Repository:

    git clone https://github.com/yourusername/d-py.git
    cd d-py

    Replace yourusername with your GitHub username.
    Install Dependencies:

    pip install yt-dlp gallery-dl

    Ensure FFmpeg is installed and added to your PATH.
    Create urls.txt:
        In the same directory as d.py, create a file named urls.txt.
        Add URLs to download media from, one per line or separated by semicolons (;).
        Example:

        https://www.instagram.com/p/DIY8DgYTOwJ/;https://x.com/Snowbals_/status/1914846186073156833

Usage
Run the script from the command line using python d.py <command> [arguments]. Below are the available commands with examples.
1. Download Media
Downloads media from URLs in urls.txt.

    Download Audio:

    python d.py download audio --output-dir C:\Audio --keep-original

        Output: C:\Audio\A1.m4a, A2.m4a, etc.
        Downloads audio from URLs.
    Download Video (No Audio):

    python d.py download video --output-dir C:\Videos --keep-original

        Output: C:\Videos\V1.mp4, V2.mp4, etc.
        Downloads video-only files.
    Download Combined Video and Audio:

    python d.py download combined --output-dir C:\Videos --keep-original

        Output: C:\Videos\O1.mp4, O2.mp4, etc.
        Downloads video and audio, merges them into a single file.
    Download and Split Video and Audio:

    python d.py download split --output-dir C:\Videos --keep-original

        Output: C:\Videos\U1_video.mp4, C:\Videos\U1_audio.m4a, etc.
        Downloads video and audio, splits them into separate files.
    Download Pictures:

    python d.py download pic --output-dir C:\Pictures --keep-original

        Output: C:\Pictures\P1.jpg, P2.jpg, etc.
        Downloads images (e.g., Instagram post thumbnails).

2. Combine Video and Audio
Combines an existing video file with an audio file, looping the audio if needed.

    Command:

    python d.py combine C:\Videos\V1 C:\Audio\A1 --output-dir C:\Videos

        Output: C:\Videos\C1.mp4
        Combines V1.mp4 and A1.m4a into a single video.

3. Split Video into Video and Audio
Splits a combined video file into separate video and audio files.

    Command:

    python d.py split C:\Videos\O1 --output-dir C:\Videos

        Output: C:\Videos\V1.mp4, C:\Videos\A1.m4a (if audio exists)
        Splits O1.mp4 into video and audio files.

4. Create a Slideshow Video
Creates a slideshow video from a list of images, displaying each for a specified delay.

    Command:

    python d.py slide 5 C:\Pictures\P1 C:\Pictures\P2 C:\Pictures\P3 --output-dir C:\Pictures

        Output: C:\Pictures\S1.mp4
        Creates a slideshow video where each image is displayed for 5 seconds (total 15 seconds).

5. Loop Audio to a Duration
Loops an audio file to match a specified duration.

    Command:

    python d.py loop C:\Audio\A1 15 --output-dir C:\Audio

        Output: C:\Audio\L1.m4a
        Loops A1.m4a to a 15-second duration.

Example Workflow

    Download Images and Audio:

    python d.py download pic --output-dir C:\Pictures
    python d.py download audio --output-dir C:\Audio

        Downloads images (P1.jpg, P2.jpg) and audio (A1.m4a).
    Create a Slideshow:

    python d.py slide 5 C:\Pictures\P1 C:\Pictures\P2 --output-dir C:\Pictures

        Output: C:\Pictures\S1.mp4 (10 seconds).
    Loop Audio:

    python d.py loop C:\Audio\A1 10 --output-dir C:\Audio

        Output: C:\Audio\L1.m4a (10 seconds).
    Combine Slideshow with Audio:

    python d.py combine C:\Pictures\S1 C:\Audio\L1 --output-dir C:\Videos

        Output: C:\Videos\C1.mp4.

Additional Notes

    File Extensions:
        The script assumes .mp4 for videos, .m4a for audio, and tries .jpg, .jpeg, .png, .webp for images.
        For combine, split, and loop commands, provide paths without extensions (e.g., C:\Videos\V1 for V1.mp4).
    Authentication:
        Log into platforms like Instagram or X on Firefox to use --cookies-from-browser firefox for downloading.
    Output Naming:
        Outputs are named sequentially: A1.m4a (audio), V1.mp4 (video), O1.mp4/U1.mp4 (combined/split), P1.jpg (pictures), S1.mp4 (slideshow), L1.m4a (looped audio).
    Dynamic Resolution:
        The slide command automatically determines the best resolution for the slideshow based on image dimensions.
    Troubleshooting:
        Ensure FFmpeg, yt-dlp, and gallery-dl are installed and accessible in your PATH.
        Check urls.txt for valid URLs.
        For X downloads, ensure the post is accessible (not private) and you’re logged into X on Firefox.

License
This project is licensed under the MIT License - see the LICENSE file for details.
Notes for GitHub Setup

    Create a Repository:
        Go to GitHub, create a new repository (e.g., d-py), and push the script and README:

        git init
        git add d.py README.md
        git commit -m "Initial commit"
        git remote add origin https://github.com/yourusername/d-py.git
        git push -u origin main

    Add a License:
        Create a LICENSE file with the MIT License text (or your preferred license) and add it to the repository.
    Update Paths:
        If you change the repository name or your username, update the URLs in the README (e.g., https://github.com/yourusername/d-py.git).

This README provides clear instructions for users to get started with your script on GitHub. Let me know if you’d like to add more sections, such as contributing guidelines or a troubleshooting FAQ!
