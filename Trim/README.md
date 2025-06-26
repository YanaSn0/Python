python trim.py a input_audio.mp3 --end-time 10

python trim.py v input_video.mp4 --start-time 5 --end-time 15

First Argument: a for audio or v for video.

Second Argument: Input file path (e.g., input_audio.mp3 or input_video.mp4).

Required Flag: --end-time specifies the end time in seconds.

Example Output: A_1.mp4 (audio) or V_1.mp4 (video) in the output directory.

Flags:

--start-time <seconds>: Start time for trimming (default: 0).

--end-time <seconds>: End time for trimming (required).

--output-dir <path>: Output directory (default: input file’s directory).

--debug: Enable verbose debug output.

python trim.py a audio.mp3 --end-time 10 --output-dir ./output --debug

Trims audio.mp3 from 0 to 10 seconds, saving as ./output/A_1.m4a.


