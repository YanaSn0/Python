Purpose: Splits a video into its video and audio components (first 5 seconds).

Command:

python split.py input_video.mp4

First Argument: Input video file path.

Example Output: v_1.mp4 (video) and a_1.m4a (audio, if present) in the output directory.

Flags:

--output-dir <path>: Output directory (default: input file’s directory).

--debug: Enable verbose debug output.

Example:

python split.py video.mp4 --output-dir ./output

Splits video.mp4 into ./output/v_1.mp4 (video) and ./output/a_1.m4a (audio, if available).

