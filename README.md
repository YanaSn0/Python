# Media Processing Script (s.py)

## Requirements

- **Python 3.x**: Install from [python.org](https://www.python.org/downloads/)
- **FFmpeg**: Install from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH
- **Optional (for download mode)**:
  - `yt-dlp`: `pip install yt-dlp`
  - `gallery-dl`: `pip install gallery-dl`

## Commands

### Split a video into audio and video files

python s.py split U1 --output-dir ./output


### Loop an audio file to a specified duration

python s.py loop A1 60 --output-dir ./output


### Trim and loop audio directly from a video (last 30 seconds)

python s.py trim_loop_from_video U1 60 --last 30 --output-dir ./output


### Trim and loop audio from a video (specific range, e.g., 30-45 seconds)

python s.py trim_loop_from_video U1 60 --start 30 --trim-duration 15 --output-dir ./output

OR

python s.py trim_loop_from_video U1 60 --start 30 --end 45 --output-dir ./output


### Combine a video and audio file

python s.py combine V1 A1 --output-dir ./output


### Create a slideshow from images (5-second delay per image)

python s.py slide 5 P1 P2 --output-dir ./output


### Batch convert videos to universal format

python s.py batch_convert videos --output-dir ./output


### Download media from URLs (urls.txt required)

python s.py download audio --output-dir ./output
