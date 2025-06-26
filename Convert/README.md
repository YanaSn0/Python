Purpose: Converts videos to a standard format (H.264, 30 fps, AAC audio).

Command:

python convert.py ./input_dirFirst Argument: Input directory or file path (supports wildcards, e.g., *.mp4).

Example Output: U_1.mp4, U_2.mp4, etc., in the output directory.

Flags:

--output-dir <path>: Output directory (default: current directory).

--debug: Enable verbose debug output.

Example:

python convert.py ./videos --output-dir ./output

Converts all .mp4 and .mkv files in ./videos to ./output/U_1.mp4, etc.

