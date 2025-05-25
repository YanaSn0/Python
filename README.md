## Media Scripts README

## Media Scripts Commands

## download.py

## Download Audio Only

Saves audio as .m4a files.

python download.py audio --output-dir ./audio --debug  

## Download Video Only

Saves video without audio as .mp4 files.

python download.py video --output-dir ./videos --debug  

## Download Images

Saves images as .jpg or other formats.

python download.py pic --output-dir ./images --debug  

## Download Combined Video and Audio

Saves videos with audio as .mp4 files.

python download.py combined --output-dir ./combined --debug  

## Download and Split into Video and Audio

Saves separate video (.mp4) and audio (.m4a) files.

python download.py split --output-dir ./split --debug  

## Download All Possible Media Types

Tries combined video/audio, audio-only, video-only, then images.

python download.py all --output-dir ./all --debug  

## Download with Authentication

Uses username/password or cookies for private content.

python download.py audio --output-dir ./audio --username your_username --password your_password --debug  

python download.py audio --output-dir ./audio --cookies cookies.txt --debug  

## Download with Duration Limit

Limits downloaded media duration (e.g., first 30 seconds).

python download.py combined --output-dir ./combined --duration 30 --debug  

## Download with URL-Based Naming

Names audio files based on URL instead of title.

python download.py audio --output-dir ./audio --link --debug  

## Keep Original Files

Preserves original files without re-encoding.

python download.py combined --output-dir ./combined --keep-original --debug  

## Clear Output Directory

Clears the output directory before downloading.

python download.py audio --output-dir ./audio --clear-dir --debug  

## process.py

## Trim Video

Trims a video to specified start and end times, outputs as .mp4.

python process.py trim v ./videos/U1.mp4 --start 10 --end 20 --output-dir ./trimmed --debug  

## Trim Audio

Extracts and trims audio from a video, outputs as .m4a.

python process.py trim a ./videos/U1.mp4 --start 10 --end 20 --output-dir ./trimmed --debug  

## Loop Video

Trims and loops a video to a desired duration, outputs as .mp4.

python process.py loop v ./videos/U1.mp4 --start 10 --end 20 --duration 60 --output-dir ./looped --debug  

## Loop Audio from Video

Trims and loops audio from a video, outputs as .m4a.

python process.py loop a ./videos/U1.mp4 --start 10 --end 20 --duration 60 --output-dir ./looped --debug  

## Loop Audio File

Loops an audio file to a desired duration, outputs as .m4a.

python process.py loopaudio ./audio/A1.m4a 60 --output-dir ./looped --debug  

## Split Video

Splits a video into video (.mp4) and audio (.m4a) files.

python process.py split ./videos/O11.mp4 --output-dir ./split --debug  

## Combine Video and Audio

Combines video and audio files into a single .mp4.

python process.py combine ./videos/V1.mp4 ./audio/A1.m4a --output-dir ./combined --debug  

## Convert Videos to Universal Format

Converts videos to a standardized format (e.g., 1920x1080 for landscape).

python process.py convert ./reels --output-dir ./converted --debug  

## Create Slideshow

Creates a slideshow video from images with specified delay.

python process.py slide 3 ./images/image1.jpg ./images/image2.jpg --output-dir ./slideshows --debug  

## Concatenate Videos

Concatenates videos into one with fade-in transitions.

python process.py concat ./videos/V1.mp4 ./videos/V2.mp4 --output-dir ./concatenated --debug  

python process.py concat ./videos --output-dir ./concatenated --debug  
