import subprocess
import sys
import os
import argparse
import time
import shutil

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

def main():
    global DEBUG
    parser = argparse.ArgumentParser(description="Split video into video and audio (first 5 seconds)")
    parser.add_argument("input_path", help="Input video file")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()
    DEBUG = args.debug

    input_path = args.input_path
    output_dir = args.output_dir or os.path.dirname(os.path.abspath(input_path)) or "."
    actual_input = find_video_file(input_path)
    if not actual_input or not os.path.exists(actual_input):
        print(f"Error: No input found: {input_path}")
        sys.exit(1)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    file_duration = get_file_duration(actual_input)
    if file_duration < 5:
        print(f"Warning: Input duration {file_duration}s is less than 5s. Using full duration.")
    video_name, video_path, next_number = get_next_available_name(output_dir, "v", ".mp4")
    audio_name, audio_path, _ = get_next_available_name(output_dir, "a", ".m4a", start_number=next_number-1)
    ffmpeg_command = f'ffmpeg -y -i "{actual_input}" -c:v copy -an -t 5 "{video_path}"'
    success, output = run_command(ffmpeg_command)
    if success:
        print(f"Saved video as {video_path.replace(os.sep, '/')}")
        if has_audio_stream(actual_input):
            ffmpeg_command = f'ffmpeg -y -i "{actual_input}" -vn -c:a aac -b:a 128k -t 5 "{audio_path}"'
            success, output = run_command(ffmpeg_command)
            if success:
                print(f"Saved audio as {audio_path.replace(os.sep, '/')}")
            else:
                print(f"Audio extraction failed for {actual_input}: {output}")
                os.remove(video_path)
                sys.exit(1)
        else:
            print(f"No audio stream in {actual_input}")
    else:
        print(f"Split failed for {actual_input}: {output}")
        sys.exit(1)

if __name__ == "__main__":
    main()
