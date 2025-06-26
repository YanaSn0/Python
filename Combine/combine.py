import subprocess
import sys
import os
import argparse
import time

DEBUG = False

def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)

def run_command(command, suppress_errors=False, timeout=None, retries=1):
    attempt = 0
    while attempt <= retries:
        debug_print(f"Running command (Attempt {attempt+1}/{retries+1}): {command}")
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
            if attempt <= retries:
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
    command = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{file_path}"'
    debug_print(f"Running ffprobe: {command}")
    success, output = run_command(command)
    if not success:
        debug_print(f"ffprobe failed: {output}")
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
        print(f"Warning: Invalid duration for {file_path}: '{output}'")
        return 0

def has_audio_stream(file_path):
    command = f'ffprobe -v error -show_streams -select_streams a -of default=noprint_wrappers=1 "{file_path}"'
    debug_print(f"Checking audio: {command}")
    success, output = run_command(command)
    return bool(output.strip())

def has_video_stream(file_path):
    command = f'ffprobe -v error -show_streams -select_streams v -of default=noprint_wrappers=1 "{file_path}"'
    debug_print(f"Checking video: {command}")
    success, output = run_command(command)
    return bool(output.strip())

def main():
    global DEBUG
    parser = argparse.ArgumentParser(description="Combine one video and one audio file from a directory")
    parser.add_argument("input_dir", help="Input directory containing one video and one audio file")
    parser.add_argument("output_dir", help="Output directory for the combined file")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()
    DEBUG = args.debug

    input_dir = args.input_dir
    output_dir = os.path.abspath(args.output_dir)
    actual_input_dir = os.path.abspath(input_dir)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    debug_print(f"Scanning directory: {actual_input_dir}")
    video_extensions = ['.mp4', '.mkv']
    audio_extensions = ['.m4a', '.mp3', '.wav', '.aac']
    video_files, audio_files = [], []
    if os.path.isdir(actual_input_dir):
        debug_print(f"Listing directory contents")
        for file in os.listdir(actual_input_dir):
            file_lower = file.lower()
            base, ext = os.path.splitext(file_lower)
            full_path = os.path.join(actual_input_dir, file)
            if ext in video_extensions:
                video_files.append((base, full_path))
                debug_print(f"Video: {file}")
            elif ext in audio_extensions:
                audio_files.append((base, full_path))
                debug_print(f"Audio: {file}")
            else:
                debug_print(f"Skipping {file}")
    else:
        print(f"Error: Input directory does not exist: {actual_input_dir}")
        sys.exit(1)
    if not video_files or not audio_files:
        print(f"Error: No {'video' if not video_files else 'audio'} files found in {actual_input_dir}")
        sys.exit(1)
    if len(video_files) > 1:
        print(f"Error: Multiple video files found in {actual_input_dir}: {[v[1] for v in video_files]}. Please ensure only one video file is present.")
        sys.exit(1)
    if len(audio_files) > 1:
        print(f"Error: Multiple audio files found in {actual_input_dir}: {[a[1] for a in audio_files]}. Please ensure only one audio file is present.")
        sys.exit(1)
    video_base, video_path = video_files[0]
    audio_base, audio_path = audio_files[0]
    debug_print(f"Combining video: {video_path} with audio: {audio_path}")
    if not os.path.exists(video_path):
        print(f"Error: Video file does not exist: {video_path}")
        sys.exit(1)
    if not os.path.exists(audio_path):
        print(f"Error: Audio file does not exist: {audio_path}")
        sys.exit(1)
    if not has_video_stream(video_path):
        print(f"Error: No video stream in {video_base}")
        sys.exit(1)
    if not has_audio_stream(audio_path):
        print(f"Error: No audio stream in {audio_base}")
        sys.exit(1)
    video_duration = get_file_duration(video_path)
    audio_duration = get_file_duration(audio_path)
    if video_duration == 0 or audio_duration == 0:
        print(f"Error: Could not get duration for {video_path} or {audio_path}")
        sys.exit(1)
    name, output_path, _ = get_next_available_name(output_dir, "C", ".mp4", start_number=1)
    loop_count = max(0, int(video_duration // audio_duration) + (1 if video_duration % audio_duration > 0 else 0))
    final_duration = video_duration
    ffmpeg_command = (
        f'ffmpeg -y -i "{video_path}" -stream_loop {loop_count-1} -i "{audio_path}" '
        f'-map 0:v:0 -map 1:a:0 -c:v libx264 -preset ultrafast -b:v 3500k -r 30 -pix_fmt yuv420p '
        f'-c:a aac -b:a 128k -ar 44100 -shortest -t {final_duration} "{output_path}"'
    )
    success, output = run_command(ffmpeg_command)
    if success:
        print(f"Saved as {output_path.replace(os.sep, '/')}")
    else:
        print(f"Combine failed for {video_path} and {audio_path}: {output}")
        sys.exit(1)

if __name__ == "__main__":
    main()
