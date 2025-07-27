# YouTube Media Downloader

**download_yt.py** downloads YouTube videos/audio from **urls.txt** using **yt-dlp** and **ffmpeg**, saving thumbnails with matching filenames.

## Features
- Downloads videos (full) or audio (audio) with thumbnails.
- Standardizes video resolution or audio quality.
- Uses Firefox cookies for authentication.
- Sanitizes filenames, supports trimming.

## Setup
- Install: **pip install yt-dlp**
- Ensure **ffmpeg**/**ffprobe** in PATH (e.g., **choco install ffmpeg** on Windows).
- Create **urls.txt**:
  ```
  https://youtu.be/hO3gC7kEC3E?si=Kd2p8DC748qszy6r
  https://youtu.be/another_video
  ```
- Log into YouTube in Firefox for restricted content.

## Usage
- **python download_yt.py [full|audio] [--start HH:MM:SS] [--end HH:MM:SS] [--thumb] [--debug] [--output-dir PATH]**
  - **[full|audio]**: Choose to download full video or audio only.
  - **--start HH:MM:SS**: Start time (e.g., **10:41**, default **0:00**).
  - **--end HH:MM:SS**: End time (e.g., **13:11**, optional).
  - **--thumb**: Include thumbnail (optional).
  - **--debug**: Enable debug output (optional).
  - **--output-dir PATH**: Custom output directory (default **./downloaded**).

## Examples
- **python download_yt.py full --output-dir ./downloaded --debug**
- **python download_yt.py audio --start 10:41 --end 13:11 --thumb --output-dir ./audio --debug**

## Output
- Videos: **<title>_trim_X.mp4**
- Audio: **<title>_trim_X.m4a**
- Thumbnails: **<title>_trim_X_thumb.webp**
  - **<title>**: Sanitized YouTube title.
  - **X**: Incrementing number (e.g., **1**, **2**) if files exist.

## Troubleshooting
- Update **yt-dlp**: **pip install -U yt-dlp**
- Verify **ffmpeg** in PATH.
- Check debug logs (**--debug**).

## License
- **MIT License**. Follow YouTube’s Terms of Service.
