import subprocess
import sys
import os
import argparse
import time
import shutil
import re

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

def sanitize_filename(filename):
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '', filename.strip()).strip('[]{}()').rstrip('.').lstrip('._')[:200]
    return sanitized or '_'

def get_next_available_name(output_dir, prefix, extension, suffix="", title=None, start_number=1):
    sanitized_title = sanitize_filename(title) if title else None
    number = start_number
    while True:
        if sanitized_title:
            name = f"{prefix}_{number}_{sanitized_title}{suffix}{extension}"
        else:
            name = f"{prefix}_{number}{suffix}{extension}"
        full_path = os.path.join(output_dir, name)
        thumb_path = os.path.join(output_dir, f"{prefix}_{number}{'_'+sanitized_title if sanitized_title else ''}_thumb.webp")
        if not os.path.exists(full_path) and not os.path.exists(thumb_path):
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

def find_video_file(video_path, base_dir=None):
    extensions = ['.mp4', '.mkv']
    base, ext = os.path.splitext(video_path)
    if ext.lower() in extensions and os.path.exists(video_path):
        return video_path
    directory = os.path.abspath(os.path.dirname(video_path) or (base_dir or ""))
    base_name = os.path.splitext(os.path.basename(video_path))[0].lower()
    debug_print(f"Searching for video '{base_name}' in '{directory}'")
    try:
        matched_files = []
        for file in os.listdir(directory):
            file_lower = file.lower()
            file_base, file_ext = os.path.splitext(file_lower)
            if file_base == base_name and file_ext in extensions:
                matched_files.append(os.path.join(directory, file))
        if matched_files:
            for ext in extensions:
                for match in matched_files:
                    if match.lower().endswith(ext):
                        debug_print(f"Found video: {match}")
                        return match
            return matched_files[0]
    except Exception as e:
        print(f"Error accessing directory {directory}: {e}")
    return None

def find_audio_file(input_path):
    extensions = ['.m4a', '.mp3', '.wav', '.aac']
    base, ext = os.path.splitext(input_path)
    if ext.lower() in extensions and os.path.exists(input_path):
        return input_path
    base_name = os.path.splitext(os.path.basename(input_path))[0].lower()
    directory = os.path.abspath(os.path.dirname(input_path) or ".")
    try:
        matched_files = []
        for file in os.listdir(directory):
            file_lower = file.lower()
            file_base, file_ext = os.path.splitext(file_lower)
            if file_base == base_name and file_ext in extensions:
                matched_files.append(os.path.join(directory, file))
        return matched_files[0] if matched_files else None
    except Exception as e:
        print(f"Error accessing directory {directory}: {e}")
    return None

def main():
    global DEBUG
    parser = argparse.ArgumentParser(description="Trim video or audio")
    subparsers = parser.add_subparsers(dest="output_type", help="Output type", required=True)
    trim_audio = subparsers.add_parser("a", help="Trim audio")
    trim_audio.add_argument("input_path", help="Input audio file")
    trim_audio.add_argument("--start-time", type=float, default=0, help="Start time in seconds")
    trim_audio.add_argument("--end-time", type=float, required=True, help="End time in seconds")
    trim_audio.add_argument("--output-dir", help="Output directory")
    trim_audio.add_argument("--debug", action="store_true", help="Enable debug output")
    trim_video = subparsers.add_parser("v", help="Trim video")
    trim_video.add_argument("input_path", help="Input video file")
    trim_video.add_argument("--start-time", type=float, default=0, help="Start time in seconds")
    trim_video.add_argument("--end-time", type=float, required=True, help="End time in seconds")
    trim_video.add_argument("--output-dir", help="Output directory")
    trim_video.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()
    DEBUG = args.debug

    output_type = args.output_type
    input_path = args.input_path
    start_time = args.start_time
    end_time = args.end_time
    output_dir = args.output_dir or os.path.dirname(os.path.abspath(input_path)) or "."
    actual_input = find_audio_file(input_path) if output_type == "a" else find_video_file(input_path)
    if not actual_input or not os.path.exists(actual_input):
        print(f"Error: No {'audio' if output_type == 'a' else 'video'} found: {input_path}")
        sys.exit(1)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    file_duration = get_file_duration(actual_input)
    if file_duration == 0:
        print(f"Error: Could not get duration for {actual_input}")
        sys.exit(1)
    if start_time < 0 or start_time >= file_duration:
        print(f"Error: Start time {start_time} out of bounds (duration: {file_duration}s)")
        sys.exit(1)
    if end_time <= start_time or end_time > file_duration:
        print(f"Error: End time {end_time} out of bounds (start: {start_time}, duration: {file_duration}s)")
        sys.exit(1)
    trim_duration = end_time - start_time
    file_title = os.path.splitext(os.path.basename(actual_input))[0]
    prefix = "A" if output_type == "a" else "V"
    extension = ".m4a" if output_type == "a" else ".mp4"
    name, output_path, _ = get_next_available_name(output_dir, prefix, extension)
    temp_dir = os.path.abspath(os.path.join(".", "temp"))
    temp_path = os.path.join(temp_dir, "temp_file")
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    try:
        if output_type == "v":
            ffmpeg_command = (
                f'ffmpeg -y -i "{actual_input}" -ss {start_time} -t {trim_duration} '
                f'-c:v copy -c:a aac -b:a 128k "{temp_path}{extension}"'
            )
        else:
            ffmpeg_command = (
                f'ffmpeg -y -i "{actual_input}" -vn -ss {start_time} -t {trim_duration} '
                f'-c:a aac -b:a 128k "{temp_path}{extension}"'
            )
        success, output = run_command(ffmpeg_command)
        if not success or not os.path.exists(f"{temp_path}{extension}"):
            print(f"Trim failed for {actual_input}: {output}")
            sys.exit(1)
        os.rename(f"{temp_path}{extension}", output_path)
        print(f"Saved {'audio' if output_type == 'a' else 'video'} as {output_path.replace(os.sep, '/')}")
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    main()
