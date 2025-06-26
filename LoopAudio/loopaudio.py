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
    parser = argparse.ArgumentParser(description="Loop audio to specified duration")
    parser.add_argument("audio_path", help="Input audio file")
    parser.add_argument("duration", type=float, help="Target duration in seconds")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()
    DEBUG = args.debug

    audio_path = args.audio_path
    duration = args.duration
    output_dir = args.output_dir or os.path.dirname(os.path.abspath(audio_path)) or "."
    actual_audio = find_audio_file(audio_path)
    if not actual_audio or not os.path.exists(actual_audio):
        print(f"Error: No audio found: {audio_path}")
        sys.exit(1)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    audio_duration = get_file_duration(actual_audio)
    if audio_duration == 0:
        print(f"Error: Could not get duration for {actual_audio}")
        sys.exit(1)
    if duration <= audio_duration:
        print(f"Warning: Duration {duration} <= audio duration {audio_duration}. No looping")
        loop_count, final_duration = 0, duration
    else:
        loop_count = int(duration // audio_duration) + (1 if duration % audio_duration > 0 else 0)
        final_duration = min(duration, loop_count * audio_duration)
    name, output_path, _ = get_next_available_name(output_dir, "A", ".m4a")
    ffmpeg_command = (
        f'ffmpeg -y -stream_loop {loop_count-1} -i "{actual_audio}" '
        f'-c:a aac -b:a 128k -t {final_duration} "{output_path}"'
    )
    success, output = run_command(ffmpeg_command)
    if success:
        print(f"Saved audio as {output_path.replace(os.sep, '/')}")
    else:
        print(f"Loop failed for {actual_audio}: {output}")
        sys.exit(1)

if __name__ == "__main__":
    main()
