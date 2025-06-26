## Purpose:

Loops a trimmed video or audio file to a target duration.

Command:

python loop.py a input_audio.mp3 --end-time 10 --duration 30

python loop.py v input_video.mp4 --start-time 5 --end-time 15 --duration 60

First Argument: a for audio or v for video.

Second Argument: Input file path.

Required Flag: --end-time specifies the end time of the segment to loop.

Example Output: AL_1.m4a (audio) or VL_1.mp4 (video).

Flags:

--start-time <seconds>: Start time for trimming (default: 0).

--end-time <seconds>: End time for trimming (required).

--duration <seconds>: Target duration for looping (optional; if omitted, no looping occurs).

--output-dir <path>: Output directory (default: input file’s directory).

--debug: Enable verbose debug output.

Example:
                                                   
python loop.py v video.mp4 --end-time 10 --duration 30 --output-dir ./output

Trims video.mp4 to 0-10 seconds, loops it to 30 seconds, saving as ./output/VL_1.mp4.

