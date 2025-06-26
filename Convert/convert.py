import subprocess
import sys
import os
import argparse
import glob
import json
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

def get_video_dimensions(video_path):
    command = f'ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of json "{video_path}"'
    success, output = run_command(command)
    if success:
        try:
            data = json.loads(output)
            if data.get('streams'):
                return data['streams'][0]['width'], data['streams'][0]['height']
        except json.JSONDecodeError:
            pass
    print(f"Warning: Could not get dimensions for {video_path}. Using 1920x1080")
    return 1920, 1080

def main():
    global DEBUG
    parser = argparse.ArgumentParser(description="Convert videos to standard format")
    parser.add_argument("input_dirs", nargs='+', help="Input directories or files")
    parser.add_argument("--output-dir", default=".", help="Output directory")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()
    DEBUG = args.debug

    input_dirs = args.input_dirs
    output_dir = os.path.abspath(args.output_dir)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    count = 1
    for input_dir in input_dirs:
        if os.path.isdir(input_dir):
            video_extensions = ['*.mp4', '*.mkv']
            video_files = []
            for ext in video_extensions:
                pattern = os.path.join(input_dir, ext)
                debug_print(f"Searching: {pattern}")
                files = glob.glob(pattern)
                debug_print(f"Found: {files}")
                video_files.extend(files)
            seen = set()
            unique_videos = []
            for file in video_files:
                file_lower = file.lower()
                if file_lower not in seen:
                    seen.add(file_lower)
                    unique_videos.append(file)
            def get_number(file):
                match = re.match(r'O(\d+)\.', os.path.basename(file))
                return int(match.group(1)) if match else float('inf')
            video_files = sorted(unique_videos, key=get_number)
        else:
            debug_print(f"Wildcard pattern: {input_dir}")
            video_files = glob.glob(input_dir)
            seen = set()
            unique_videos = []
            for file in video_files:
                file_lower = file.lower()
                if file_lower not in seen:
                    seen.add(file_lower)
                    unique_videos.append(file)
            def get_number(file):
                match = re.match(r'O(\d+)\.', os.path.basename(file))
                return int(match.group(1)) if match else float('inf')
            video_files = sorted(unique_videos, key=get_number)
        if not video_files:
            print(f"No videos found in {input_dir}")
            continue
        print(f"Processing: {input_dir}")
        for i, video_path in enumerate(video_files, 1):
            print(f"Converting {video_path} ({i}/{len(video_files)})")
            name, output_path, _ = get_next_available_name(output_dir, "U", ".mp4", start_number=count)
            width, height = get_video_dimensions(video_path)
            width += width % 2
            height += height % 2
            aspect_ratio = width / height
            if aspect_ratio > 1.5:
                target_width, target_height = 1920, 1080
            elif aspect_ratio < 0.67:
                target_width, target_height = 1080, 1920
            else:
                target_width, target_height = 1080, 1080
            target_width += target_width % 2
            target_height += target_height % 2
            ffmpeg_command = (
                f'ffmpeg -y -i "{video_path}" -fflags +genpts -c:v libx264 -preset ultrafast -b:v 3500k '
                f'-force_key_frames "0" -vf "scale={target_width}:{target_height}:force_divisible_by=2,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2" -r 30 '
                f'-c:a aac -b:a 128k -ar 44100 -t 140 "{output_path}"'
            )
            debug_print(f"FFmpeg command: {ffmpeg_command}")
            success, output = run_command(ffmpeg_command, timeout=30, retries=1)
            if success:
                print(f"Saved as {output_path.replace(os.sep, '/')}")
            else:
                print(f"Conversion failed for {video_path}: {output}")
                sys.exit(1)
            count += 1

if __name__ == "__main__":
    main()
