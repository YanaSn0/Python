# Media Processing Scripts (download.py and process.py)

## Requirements

- Python 3.x: Install from https://www.python.org/downloads/
- FFmpeg: Install from https://ffmpeg.org/download.html and add to PATH
- Optional (for download mode):
  - yt-dlp: pip install yt-dlp
  - gallery-dl: pip install gallery-dl
- Put the url in url.txt then save.
- The debug flags aren't needed.
- Folders will be created if they don't already exist.
 
## Commands

## download.py

## Download full with custom name.

python download.py YanaSn0w1 full --debug --output-dir ./output

## With title as name.

python download.py full --debug --output-dir ./output

## Download Audio Only

## Saves audio as .m4a files.

python download.py audio --debug

## Download Video Only

## Saves video without audio as .mp4 files.

python download.py video --output-dir ./videos --debug 

## Download and Split into Video and Audio

## Saves separate video (.mp4) and audio (.m4a) files.

python download.py split --output-dir ./split --debug   

## Download with Duration Limit

## Limits downloaded media duration (e.g., first 30 seconds).

python download.py combined --output-dir ./combined --duration 30 --debug  

## Download with URL-Based Naming

## Names audio files based on URL instead of title.

python download.py audio --output-dir ./audio --link --debug  

## Keep Original Files

## Preserves original files without re-encoding.

python download.py combined --output-dir ./combined --keep-original --debug  

## Clear Output Directory

## Clears the output directory before downloading.

python download.py audio --output-dir ./audio --clear-dir --debug  

## process.py



## Trim Video

## Trims a video to specified start and end times, outputs as .mp4.

python process.py trim v ./videos/V1.mp4 --start 22 --end 27 --output-dir ./trimmed --debug

## Trims Audio to specified start and end times, outputs as .m4a.

python process.py trim a ./videos/A1.m4a --start 22 --end 27 --output-dir ./trimmed --debug

## Extracts and trims audio from a video, outputs as .m4a.

python process.py trim a ./videos/U1.mp4 --start 10 --end 20 --output-dir ./trimmed --debug  

## Loop Video

## Trims and loops a video to a desired duration, outputs as .mp4.

python process.py loop v ./videos/U1.mp4 --start 10 --end 20 --duration 60 --output-dir ./looped --debug  

## Loop Audio from Video

## Trims and loops audio from a video, outputs as .m4a.

python process.py loop a ./videos/U1.mp4 --start 10 --end 20 --duration 60 --output-dir ./looped --debug  

## Loop Audio File

## Loops an audio file to a desired duration, outputs as .m4a.

python process.py loopaudio ./audio/A1.m4a 60 --output-dir ./looped --debug  

## Split Video

## Splits a video into video (.mp4) and audio (.m4a) files.

python process.py split ./downloaded/YanaSn0w1_Video --debug

## Combine Video and Audio

## Combines video and audio files into a single:

python process.py combine ./looped --output-dir ./combined --debug

## Slideshow Video from Pictures with specified delay:

## Slideshow from all images in a directory:

python process.py slide 5 ./slide_in --output-dir ./slide_out

## Slideshow from a double extension image file.

python process.py slide 5 ./slide_in image.psd.png --output-dir ./slide_out

## Slideshow from a wildcard pattern:

python process.py slide 3 ./images/*.jpg --output-dir ./output

## Slideshow from an image:

python process.py slide 5 ./slide_in P1 --output-dir ./slide_out --debug

## Slideshow from images:

python process.py slide 5 ./slide_in P1 P2 --output-dir ./slide_out --debug

## Convert Videos to Universal Format:

## Converts videos to a standardized format (e.g., 1920x1080 for landscape) so works on socials and so concatenate doesn't glitch out.

python process.py convert ./reels --output-dir ./converted --debug

## Concatenate Videos:

## Concatenates videos into one with fade-in transitions.

## Concatenates all videos in a folder:

python process.py concat ./slide_out --output-dir ./concat_out --debug  

## Concatenates videos in a folder:

python process.py concat ./videos/V1.mp4 ./videos/V2.mp4 --output-dir ./concatenated --debug  
