Purpose: Concatenates multiple videos into a single video, with optional fade transitions.

Command:

python concat.py video1.mp4 video2.mp4

python concat.py ./videos

First Argument: Video file paths or a directory containing videos.

Example Output: Concat_1.mp4 in the output directory.

Flags:

--output-dir <path>: Output directory (default: current directory).

--no-fades: Disable fade transitions between videos.

--debug: Enable verbose debug output.

Example:

python concat.py ./videos --output-dir ./output --no-fades

Concatenates all .mp4 and .mkv files in ./videos into ./output/Concat_1.mp4 without fades.

