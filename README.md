# Media Processing Script (s.py)

## Requirements

- Python 3.x: Install from https://www.python.org/downloads/
- FFmpeg: Install from https://ffmpeg.org/download.html and add to PATH
- Optional (for download mode):
  - yt-dlp: pip install yt-dlp
  - gallery-dl: pip install gallery-dl

## Commands

### Split a video into audio and video files
python s.py split U1 --output-dir ./output

### Loop an audio file to a specified duration
python s.py loop A1 60 --output-dir ./output

### Trim audio from a video between start and end times
python s.py trim U1 --start 30 --end 45 --output-dir ./output

### Trim and loop audio from a video (specific range, e.g., 30-45 seconds)
python s.py trim_loop U1 --start 30 --end 45 --duration 60 --output-dir ./output

### Combine a video and audio file
python s.py combine V1 A1 --output-dir ./output

### Create a slideshow from images (5-second delay per image)
python s.py slide 5 P1 P2 --output-dir ./output

### Batch convert videos to universal format
python s.py batch_convert videos --output-dir ./output

### Download media from URLs (urls.txt required)
python s.py download all --output-dir ./output
python s.py download all+a --output-dir ./output
python s.py download all+a+v --output-dir ./output
python s.py download all+v --output-dir ./output
python s.py download audio --output-dir ./output
python s.py download video --output-dir ./output
python s.py download combined --output-dir ./output
python s.py download split --output-dir ./output
python s.py download pic --output-dir ./output
python s.py download full --output-dir ./output
python s.py download all --output-dir ./output --keep-original
python s.py download all --output-dir ./output --clear-dir
python s.py download all --output-dir ./output --username myuser --password mypass
python s.py download all --output-dir ./output --cookies cookies.txt
python s.py download all --output-dir ./output --duration 60
