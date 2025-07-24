import subprocess
import sys
import os
import argparse
import time
import shlex

DEBUG = False

def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)

def run_command(command, suppress_errors=False, timeout=None, retries=1):
    attempt = 0
    while attempt < retries:
        debug_print(f"Running command (Attempt {attempt+1}/{retries}): {command}")
        stdout = subprocess.PIPE if not suppress_errors else subprocess.DEVNULL
        stderr = subprocess.PIPE if not suppress_errors else subprocess.DEVNULL
        process = subprocess.Popen(command, shell=True, stdout=stdout, stderr=stderr, text=True)
        output, errors = [], []
        try:
            stdout_data, stderr_data = process.communicate(timeout=timeout)
            if stdout_data:
                debug_print(stdout_data, end='')
                output.append(stdout_data)
            if stderr_data:
                debug_print(stderr_data, end='')
                errors.append(stderr_data)
            return_code = process.returncode
            output_str = ''.join(output)
            error_str = ''.join(errors)
            debug_print(f"Command finished: return_code={return_code}")
            if return_code != 0:
                if not suppress_errors:
                    debug_print(f"Error: return_code={return_code}. Output: {output_str}\nErrors: {error_str}")
                return False, output_str + "\n" + error_str
            return True, output_str
        except subprocess.TimeoutExpired:
            process.kill()
            attempt += 1
            if attempt < retries:
                debug_print(f"Timeout after {timeout}s. Retrying {attempt}/{retries}")
                time.sleep(2)
                continue
            debug_print(f"Timeout after {timeout}s. No more retries")
            return False, f"Timeout after {timeout}s"
        except Exception as ex:
            process.kill()
            debug_print(f"Error: {ex}")
            return False, str(ex)
        finally:
            if process.poll() is None:
                process.terminate()

def get_next_available_name(output_dir, prefix, extension, start_number=1):
    number = start_number
    while True:
        name = f"{prefix}_{number}{extension}"
        full_path = os.path.join(output_dir, name)
        if not os.path.exists(full_path):
            return name, full_path, number + 1
        number += 1

def get_file_duration(file_path):
    if not os.access(file_path, os.R_OK):
        print(f"Error: Cannot read file {file_path}")
        return 0
    command = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{file_path}"'
    debug_print(f"Running ffprobe: {command}")
    success, output = run_command(command)
    if not success:
        print(f"Error: ffprobe failed for {file_path}: {output}")
        command = f'ffprobe -v error -show_entries stream=duration -select_streams v:0 -of default=noprint_wrappers=1:nokey=1 "{file_path}"'
        debug_print(f"Trying fallback ffprobe: {command}")
        success, output = run_command(command)
        if not success:
            print(f"Error: Fallback ffprobe failed for {file_path}: {output}")
            return 0
    output = output.strip()
    debug_print(f"Duration output: '{output}'")
    if not output:
        print(f"Warning: Empty duration for {file_path}")
        return 0
    try:
        duration = float(output)
        debug_print(f"Duration: {duration}s")
        return duration
    except ValueError:
        print(f"Error: Invalid duration for {file_path}: '{output}'")
        return 0

def has_video_stream(file_path):
    if not os.access(file_path, os.R_OK):
        print(f"Error: Cannot read file {file_path}")
        return False
    command = f'ffprobe -v error -show_streams -select_streams v -of default=noprint_wrappers=1 "{file_path}"'
    debug_print(f"Checking video: {command}")
    success, output = run_command(command)
    if not success:
        debug_print(f"No video stream in {file_path}: {output}")
        return False
    return bool(output.strip())

def has_audio_stream(file_path):
    if not os.access(file_path, os.R_OK):
        print(f"Error: Cannot read file {file_path}")
        return False
    command = f'ffprobe -v error -show_streams -select_streams a -of default=noprint_wrappers=1 "{file_path}"'
    debug_print(f"Checking audio: {command}")
    success, output = run_command(command)
    if not success:
        debug_print(f"No audio stream in {file_path}: {output}")
        return False
    return bool(output.strip())

def try_ffmpeg_command(video_file, audio_file, output_path, use_simplified=False):
    if use_simplified:
        ffmpeg_command = (
            f'ffmpeg -y -i "{video_file}" -i "{audio_file}" '
            f'-map 0:v:0? -map 1:a:0? -c:v copy -c:a copy -shortest "{output_path}"'
        )
    else:
        video_duration = get_file_duration(video_file)
        audio_duration = get_file_duration(audio_file)
        if video_duration == 0 or audio_duration == 0:
            print(f"Warning: Could not get duration for video ({video_duration}s) or audio ({audio_duration}s). Using simplified FFmpeg command.")
            return try_ffmpeg_command(video_file, audio_file, output_path, use_simplified=True)
        loop_count = max(0, int(video_duration // audio_duration) + (1 if video_duration % audio_duration > 0 else 0))
        final_duration = video_duration
        ffmpeg_command = (
            f'ffmpeg -y -i "{video_file}" -stream_loop {loop_count-1} -i "{audio_file}" '
            f'-map 0:v:0? -map 1:a:0? -c:v libx264 -preset ultrafast -b:v 3500k -r 30 -pix_fmt yuv420p '
            f'-c:a aac -b:a 128k -ar 44100 -shortest -t {final_duration} "{output_path}"'
        )
    
    success, output = run_command(ffmpeg_command, timeout=300)
    return success, output

def main():
    global DEBUG
    parser = argparse.ArgumentParser(description="Combine two MP4 files: one for video, one for audio")
    parser.add_argument("input_dir", help="Input directory containing two MP4 files")
    parser.add_argument("output_dir", help="Output directory for the combined file")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()
    DEBUG = args.debug

    input_dir = os.path.abspath(args.input_dir)
    output_dir = os.path.abspath(args.output_dir)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    debug_print(f"Scanning directory: {input_dir}")
    
    # Get all files in the directory
    if not os.path.isdir(input_dir):
        print(f"Error: Input directory does not exist: {input_dir}")
        sys.exit(1)
    
    files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
    if len(files) != 2:
        print(f"Error: Directory must contain exactly two files, found {len(files)}: {files}")
        sys.exit(1)

    # Validate file readability
    for file_path in files:
        if not os.access(file_path, os.R_OK):
            print(f"Error: Cannot read file {file_path}")
            sys.exit(1)

    # Classify files based on streams
    video_file = None
    audio_file = None
    for file_path in files:
        has_video = has_video_stream(file_path)
        has_audio = has_audio_stream(file_path)
        debug_print(f"File {file_path}: video={has_video}, audio={has_audio}")
        
        if has_video and video_file is None:
            video_file = file_path
        elif has_audio and audio_file is None:
            audio_file = file_path
        else:
            print(f"Error: File {file_path} does not fit selection criteria (already selected video or audio)")
            sys.exit(1)

    if not video_file:
        print(f"Error: No file with video stream found in {input_dir}")
        sys.exit(1)
    if not audio_file:
        print(f"Error: No file with audio stream found in {input_dir}")
        sys.exit(1)

    debug_print(f"Selected video: {video_file}, audio: {audio_file}")

    # Generate output file name
    name, output_path, _ = get_next_available_name(output_dir, "C", ".mp4", start_number=1)
    
    # Try FFmpeg command (first with durations, then simplified, then swap files)
    success, output = try_ffmpeg_command(video_file, audio_file, output_path)
    if not success:
        print(f"Combine failed for video={video_file}, audio={audio_file}: {output}")
        print("Trying with swapped video/audio files...")
        success, output = try_ffmpeg_command(audio_file, video_file, output_path)
        if not success:
            print(f"Combine failed with swapped files: {output}")
            sys.exit(1)

    print(f"Saved as {output_path.replace(os.sep, '/')}")

if __name__ == "__main__":
    main()
