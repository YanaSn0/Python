Purpose: Loops an audio file to a specified duration.

Command:

python loopaudio.py input_audio.mp3 30

First Argument: Input audio file path.

Second Argument: Target duration in seconds.

Example Output: A_1.m4a in the output directory.

Flags:

--output-dir <path>: Output directory (default: input file’s directory).

--debug: Enable verbose debug output.

Example:

python loopaudio.py audio.mp3 30 --output-dir ./output

Loops audio.mp3 to 30 seconds, saving as ./output/A_1.m4a.

