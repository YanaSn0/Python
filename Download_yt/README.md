# YouTube Media Downloader

`download_yt.py` downloads YouTube videos/audio from `urls.txt` using `yt-dlp` and `ffmpeg`, saving thumbnails with matching filenames.

## Features
- Downloads videos (`full`) or audio (`audio`) with thumbnails.
- Standardizes video resolution or audio quality.
- Uses Firefox cookies for authentication.
- Sanitizes filenames, supports trimming.

## Setup
1. Install: `pip install yt-dlp`
2. Ensure `ffmpeg`/`ffprobe` in PATH (`choco install ffmpeg` on Windows).
3. Create `urls.txt`:
4. 4. Log into YouTube in Firefox for restricted content.

## Usage
python download_yt.py [full|audio] [--trim <seconds>] [--debug] [--output-dir <path>]
Examples:
python download_yt.py full --output-dir ./downloaded --debug
python download_yt.py audio --trim 60 --output-dir ./audio

## Output
- Videos: <title>_<number>.mp4
- Audio: <title>_<number>.m4a
- Thumbnails: <title>_<number>_thumb.webp

## Troubleshooting
- Update yt-dlp: pip install -U yt-dlp
- Verify ffmpeg in PATH.
- Check debug logs (--debug).

## License
MIT License. Follow YouTube’s Terms of Service.
