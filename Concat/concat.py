import subprocess
import sys
import os
import argparse
import glob
import json
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
    parser = argparse.ArgumentParser(description="Concatenate videos")
    parser.add_argument("video_paths", nargs='+', help="Video files or directory")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--no-fades", action="store_true", help="Disable fade transitions")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()
    DEBUG = args.debug

    video_paths = args.video_paths
    output_dir = args.output_dir or "."
    base_dir = os.path.dirname(os.path.abspath(video_paths[0])) if len(video_paths) > 0 and os.path.dirname(video_paths[0]) else ""
    debug_print(f"Base directory: {base_dir}")
    if len(video_paths) == 1 and os.path.isdir(video_paths[0]):
        video_dir = os.path.abspath(video_paths[0])
        video_extensions = ['*.mp4', '*.mkv']
        video_files = []
        for ext in video_extensions:
            pattern = os.path.join(video_dir, ext)
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
        debug_print(f"Unique videos: {unique_videos}")
        def get_number(file):
            base = os.path.basename(file)
            match = re.search(r'Concat_(\d+)\.', base, re.I)
            return int(match.group(1)) if match else float('inf')
        try:
            video_paths = sorted(unique_videos, key=get_number)
            debug_print(f"Sorted videos: {video_paths}")
        except Exception as e:
            print(f"Sorting error: {e}")
            sys.exit(1)
        if not video_paths:
            print(f"No videos found in {video_dir}")
            sys.exit(1)
    else:
        video_paths = args.video_paths
    actual_videos = []
    source_durations = []
    for video_path in video_paths:
        try:
            actual_path = find_video_file(video_path, base_dir=base_dir)
            if not actual_path or not os.path.exists(actual_path):
                print(f"Error: No video found: {video_path}")
                sys.exit(1)
            duration = get_file_duration(actual_path)
            if duration == 0:
                print(f"Error: Could not get duration for {video_path}")
                sys.exit(1)
            actual_videos.append(actual_path)
            source_durations.append(duration)
            debug_print(f"Validated video: {actual_path}, Duration: {duration}s")
        except Exception as e:
            print(f"Error processing video {video_path}: {e}")
            sys.exit(1)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        debug_print(f"Created output directory: {output_dir}")
    try:
        width, height = get_video_dimensions(actual_videos[0])
        width += width % 2
        height += height % 2
        aspect_ratio = width / height
        if aspect_ratio > 1.5:
            target_width, target_height = 1920, 1080
        elif aspect_ratio < 0.67:
            target_width, target_height = 1080, 1920
        else:
            target_width, target_height = 1080, 1080
        debug_print(f"Target resolution: {target_width}x{target_height}")
    except Exception as e:
        print(f"Error getting dimensions: {e}")
        sys.exit(1)
    temp_dir = os.path.abspath(os.path.join(".", "temp"))
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    try:
        processed_videos = []
        for index, (video_path, source_duration) in enumerate(zip(actual_videos, source_durations)):
            temp_output_path = os.path.join(temp_dir, f"temp_{index:03d}.mp4")
            has_audio = has_audio_stream(video_path)
            debug_print(f"Processing video {index}: {video_path}, Duration: {source_duration}s, Has audio: {has_audio}")
            video_filters = [
                f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease:force_divisible_by=2",
                f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2",
                "setsar=1",
                "fps=30"
            ]
            if not args.no_fades:
                fade_in = index > 0
                fade_out = index < len(actual_videos) - 1
                fade_duration = 1.0
                if fade_in and fade_out:
                    video_filters.append(f"fade=t=in:st=0:d={fade_duration},fade=t=out:st={source_duration-fade_duration}:d={fade_duration}")
                elif fade_in:
                    video_filters.append(f"fade=t=in:st=0:d={fade_duration}")
                elif fade_out:
                    video_filters.append(f"fade=t=out:st={source_duration-fade_duration}:d={fade_duration}")
            video_filter_string = ",".join(video_filters)
            try:
                if has_audio:
                    ffmpeg_command = (
                        f'ffmpeg -y -i "{video_path}" '
                        f'-c:v libx264 -preset ultrafast -b:v 3500k -r 30 -pix_fmt yuv420p '
                        f'-force_key_frames "expr:gte(t,n_forced*2)" '
                        f'-c:a aac -b:a 128k -ar 48000 -ac 2 '
                        f'-vf "{video_filter_string}" '
                        f'-t {source_duration} '
                        f'"{temp_output_path}"'
                    )
                else:
                    ffmpeg_command = (
                        f'ffmpeg -y -i "{video_path}" '
                        f'-f lavfi -i anullsrc=channel_layout=stereo:sample_rate=48000 '
                        f'-c:v libx264 -preset ultrafast -b:v 3500k -r 30 -pix_fmt yuv420p '
                        f'-force_key_frames "expr:gte(t,n_forced*2)" '
                        f'-c:a aac -b:a 128k -ar 48000 -ac 2 -shortest '
                        f'-vf "{video_filter_string}" '
                        f'-t {source_duration} '
                        f'"{temp_output_path}"'
                    )
                debug_print(f"FFmpeg command: {ffmpeg_command}")
                success, output = run_command(ffmpeg_command, timeout=60, retries=1)
                if not success or not os.path.exists(temp_output_path):
                    print(f"Preprocess failed for {video_path}: {output}")
                    sys.exit(1)
                processed_videos.append(temp_output_path)
                debug_print(f"Processed: {temp_output_path}")
            except Exception as e:
                print(f"Preprocess error for {video_path}: {e}")
                sys.exit(1)
        concat_list = os.path.join(temp_dir, "concat_list.txt")
        try:
            with open(concat_list, "w") as f:
                for video in processed_videos:
                    f.write(f"file '{os.path.abspath(video)}'\n")
            debug_print(f"Created concat list: {concat_list}")
        except Exception as e:
            print(f"Concat list error: {e}")
            sys.exit(1)
        name, output_path, _ = get_next_available_name(output_dir, "Concat", ".mp4")
        debug_print(f"Saving to: {output_path}")
        try:
            ffmpeg_command = (
                f'ffmpeg -y -f concat -safe 0 -i "{concat_list}" '
                f'-c:v libx264 -preset ultrafast -b:v 3500k -r 30 -pix_fmt yuv420p '
                f'-c:a aac -b:a 128k -ar 48000 -ac 2 '
                f'"{output_path}"'
            )
            debug_print(f"FFmpeg concat command: {ffmpeg_command}")
            success, output = run_command(ffmpeg_command, timeout=300, retries=1)
            if success:
                print(f"Saved as {output_path.replace(os.sep, '/')}")
            else:
                print(f"Concatenation failed: {output}")
                sys.exit(1)
        except Exception as e:
            print(f"Concatenation error: {e}")
            sys.exit(1)
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    main()
