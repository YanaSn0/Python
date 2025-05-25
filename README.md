## download + process

I’ll create a concise README for GitHub with all the commands for both download.py and process.py, using proper Markdown headings (#) and spacing for readability, in plain text without any copy buttons or UI elements. I’ll focus on including every possible command example based on the scripts' submodes and options, while keeping it straightforward.

## Media Scripts Commands:

download.py

python download.py audio --duration 30
python download.py audio --link
python download.py video --duration 60
python download.py video --keep-original
python download.py combined --duration 45
python download.py combined --keep-original
python download.py split --duration 20
python download.py split --keep-original
python download.py pic
python download.py all
python download.py all --audio-only
python download.py audio --output-dir ./downloads --clear-dir
python download.py combined --username user --password pass
python download.py pic --cookies cookies.txt --debug  

process.py

python process.py trim a ./videos/U1.mp4 --start 10 --end 30
python process.py trim v ./videos/U1.mp4 --start 5 --end 20
python process.py trim a ./videos/U1.mp4 --end 15 --output-dir ./trimmed
python process.py loop a ./videos/U1.mp4 --start 5 --end 15 --duration 60
python process.py loop v ./videos/U1.mp4 --start 10 --end 20 --duration 90
python process.py loop v ./videos/U1.mp4 --start 0 --end 10 --output-dir ./looped
python process.py loopaudio ./audio/A1.m4a 120
python process.py loopaudio ./audio/A1.m4a 180 --output-dir ./looped_audio
python process.py split ./videos/O11.mp4
python process.py split ./videos/O11.mp4 --output-dir ./split_files
python process.py combine ./videos/V1.mp4 ./audio/A1.m4a
python process.py combine ./videos/V1.mp4 ./audio/A1.m4a --output-dir ./combined
python process.py convert ./reels
python process.py convert ./reels/reel*.mp4 --output-dir ./converted
python process.py slide 5 ./images/image1.jpg ./images/image2.jpg
python process.py slide 3 ./images/*.jpg --output-dir ./slideshows
python process.py concat ./videos/vid1.mp4 ./videos/vid2.mp4
python process.py concat ./videos
python process.py concat ./videos/vid1.mp4 ./videos/vid2.mp4 --output-dir ./concatenated
python process.py trim v ./videos/U1.mp4 --end 20 --username user --password pass
python process.py split ./videos/O11.mp4 --cookies cookies.txt --debug 

This README includes all possible command examples for both scripts, covering each submode and key options, with proper Markdown headings and spacing for GitHub. It’s in plain text for easy copying. Let me know if you need any adjustments!
