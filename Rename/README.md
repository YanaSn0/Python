Usage Examples

##  Move Files (Original Behavior):

python rename.py myprefix ./folder --folder --metadata --skipped

Input: ./folder/video.mp4

Output: ./folder/myprefix/myprefix.mp4 (original file moved, metadata applied, skipped report generated if any files are skipped)

Behavior: Moves files to a new folder named myprefix, renames them to myprefix.ext, applies metadata, and generates a skipped report.

##  Copy Files (New Behavior with --copy):

python rename.py myprefix ./folder --folder --metadata --skipped --copy

input: ./folder/video.mp4

Output: ./folder/myprefix/myprefix.mp4 (original file preserved in ./folder, metadata applied, skipped report generated)

Behavior: Copies files to a new folder named myprefix, renames them to myprefix.ext, applies metadata, and generates a skipped report.

##  Rename in Place Without Folder:

python rename.py myprefix ./folder --copy

Input: ./folder/video.mp4

Output: ./folder/myprefix.mp4 (original file preserved)

Behavior: Copies files within the same folder, renaming them to myprefix.ext.

##  Key Features
Copy vs. Move: The --copy flag determines whether files are copied (shutil.copy2, preserving originals) or moved (shutil.move, deleting originals).

Custom Prefix: Files are renamed with a user-specified prefix (e.g., myprefix.ext), with numerical suffixes for conflicts (e.g., myprefix_1.ext).

Metadata Support: With --metadata, extracts metadata (title, artist, album, duration) using ffprobe and applies it using ffmpeg.

Folder Flattening: With --folder, moves or copies files to a new folder named after the prefix.

Skipped Report: With --skipped, generates skipped.txt for files that couldn’t be processed (e.g., locked files or metadata errors).

Error Handling: Includes retries for locked files (is_file_locked), skips system files, and cleans up empty folders.

Dependencies: Requires FFmpeg (ffmpeg, ffprobe) for metadata operations, plus standard Python libraries (os, argparse, re, subprocess, sys, json, logging, shutil, uuid, hashlib, time).

