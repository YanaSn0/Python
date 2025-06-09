print("Script is starting...")

import subprocess
import sys
import os
import argparse
import re
import json
import urllib.parse
import time
import glob
import shutil
from PIL import Image

# Global debug flag
DEBUG = False

def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)

def run_command(command, suppress_errors=False, timeout=None, retries=1):
    """Run a shell command with real-time output, optional timeout, and retries."""
    attempt = 0
    while attempt <= retries:
        debug_print(f"Debug: Executing command (Attempt {attempt + 1}/{retries + 1}): {command}")
        stdout = subprocess.PIPE if not suppress_errors else subprocess.DEVNULL
        stderr = subprocess.PIPE if not suppress_errors else subprocess.DEVNULL
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=stdout,
            stderr=stderr,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        output = []
        error_output = []
        try:
            stdout_data, stderr_data = process.communicate(timeout=timeout)
            if stdout_data:
                debug_print(stdout_data, end='')
                output.append(stdout_data)
            if stderr_data:
                debug_print(stderr_data, end='')
                error_output.append(stderr_data)
            return_code = process.returncode
            output_str = ''.join(output)
            error_str = ''.join(error_output)
            debug_print(f"Debug: Command completed with return code: {return_code}")
            if return_code != 0:
                if not suppress_errors:
                    debug_print(f"Error: Command failed with return code {return_code}. Output: {output_str}")
                    debug_print(f"Error: Stderr: {error_str}")
                return False, output_str + "\n" + error_str
            return True, output_str
        except subprocess.TimeoutExpired:
            process.kill()
            attempt += 1
            if attempt <= retries:
                debug_print(f"Debug: Command timed out after {timeout} seconds. Retrying ({attempt}/{retries})...")
                time.sleep(5)
                continue
            else:
                debug_print(f"Debug: Command timed out after {timeout} seconds. No more retries left.")
                return False, f"Command timed out after {timeout} seconds"
        except Exception as e:
            process.kill()
            debug_print(f"Unexpected error during command execution: {e}")
            return False, str(e)
        finally:
            if process.poll() is None:
                process.terminate()

def sanitize_filename(filename):
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '_', filename)
    sanitized = re.sub(r'\s+', '_', sanitized.strip())
    sanitized = sanitized.lstrip('._')
    sanitized = sanitized[:200]
    return sanitized

def get_next_available_name(output_dir, prefix, extension, suffix="", title=None, start_num=1, use_url=False, url=None):
    if use_url and url:
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path.strip('/')
        query = urllib.parse.parse_qs(parsed_url.query)
        si_param = query.get('si', [''])[0]
        name_base = f"{path}_{si_param}" if si_param else path
        sanitized = sanitize_filename(name_base)
    elif title:
        sanitized = sanitize_filename(title)
    else:
        sanitized = None
    if sanitized:
        num = start_num
        while True:
            name = f"{prefix}_{num}_{sanitized}{suffix}{extension}"
            full_path = os.path.join(output_dir, name)
            thumb_path = os.path.join(output_dir, f"{prefix}_{num}_{sanitized}_thumb.webp")
            if not os.path.exists(full_path) and not os.path.exists(thumb_path):
                base_name = f"{prefix}_{num}_{sanitized}"
                return name, full_path, num + 1
            num += 1
    else:
        num = start_num
        while True:
            name = f"{prefix}_{num}{suffix}{extension}"
            full_path = os.path.join(output_dir, name)
            thumb_path = os.path.join(output_dir, f"{prefix}_{num}_thumb.webp")
            if not os.path.exists(full_path) and not os.path.exists(thumb_path):
                base_name = f"{prefix}_{num}"
                return name, full_path, num + 1
            num += 1

def get_file_duration(file_path):
    cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{file_path}"'
    debug_print(f"Debug: Running ffprobe command to get duration: {cmd}")
    success, output = run_command(cmd)
    if not success:
        debug_print(f"Debug: ffprobe failed to determine duration: {output}")
        return 0
    output = output.strip()
    debug_print(f"Debug: ffprobe duration output: '{output}'")
    if not output:
        print(f"Warning: ffprobe returned empty duration for {file_path}")
        return 0
    try:
        duration = float(output)
        debug_print(f"Debug: Successfully determined duration: {duration} seconds")
        return duration
    except ValueError:
        print(f"Warning: Could not determine duration of {file_path}. Output: '{output}'")
        return 0

def has_audio_stream(file_path):
    cmd = f'ffprobe -v error -show_streams -select_streams a -of default=noprint_wrappers=1 "{file_path}"'
    debug_print(f"Debug: Running ffprobe command to check audio stream: {cmd}")
    success, output = run_command(cmd)
    return bool(output.strip())

def has_video_stream(file_path):
    cmd = f'ffprobe -v error -show_streams -select_streams v -of default=noprint_wrappers=1 "{file_path}"'
    debug_print(f"Debug: Running ffprobe command to check video stream: {cmd}")
    success, output = run_command(cmd)
    return bool(output.strip())

def get_video_dimensions(video_path):
    cmd = f'ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of json "{video_path}"'
    success, output = run_command(cmd)
    if success:
        data = json.loads(output)
        if data.get('streams'):
            width = data['streams'][0]['width']
            height = data['streams'][0]['height']
            return width, height
    print(f"Warning: Could not determine dimensions of {video_path}. Using default 1920x1080.")
    return 1920, 1080

def get_image_dimensions(image_path):
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            return width, height
    except Exception as e:
        print(f"Warning: Could not determine dimensions of {image_path} using Pillow: {e}")
        print(f"Using default dimensions 1080x1080 for {image_path}.")
        return 1080, 1080

def find_video_file(video_path, base_dir=None):
    extensions = ['.mp4', '.mkv']
    base_path, ext = os.path.splitext(video_path)
    if ext.lower() in extensions and os.path.exists(video_path):
        return video_path
    if os.path.dirname(video_path):
        dir_name = os.path.abspath(os.path.dirname(video_path))
        base_name = os.path.splitext(os.path.basename(video_path))[0].lower()
    else:
        dir_name = os.path.abspath(base_dir if base_dir else ".")
        base_name = os.path.splitext(video_path)[0].lower()
    debug_print(f"Debug: Searching for video with base name '{base_name}' in directory '{dir_name}'")
    try:
        matching_files = []
        for file in os.listdir(dir_name):
            file_lower = file.lower()
            file_base, file_ext = os.path.splitext(file_lower)
            if file_base == base_name and file_ext in extensions:
                matching_files.append(os.path.join(dir_name, file))
        if matching_files:
            for ext in extensions:
                for match in matching_files:
                    if match.lower().endswith(ext):
                        debug_print(f"Debug: Found video file: {match}")
                        return match
            return matching_files[0]
    except Exception as e:
        print(f"Error accessing directory {dir_name}: {e}")
    return None

def find_audio_file(audio_path):
    extensions = ['.m4a', '.mp3', '.wav', '.aac', '.flac', '.ogg', '.mp4', '.mkv']
    base_path, ext = os.path.splitext(audio_path)
    if ext.lower() in extensions and os.path.exists(audio_path):
        return audio_path
    base_name = os.path.splitext(os.path.basename(audio_path))[0].lower()
    dir_name = os.path.abspath(os.path.dirname(audio_path) or ".")
    try:
        matching_files = []
        for file in os.listdir(dir_name):
            file_lower = file.lower()
            file_base, file_ext = os.path.splitext(file_lower)
            if file_base == base_name and file_ext in extensions:
                matching_files.append(os.path.join(dir_name, file))
        return matching_files[0] if matching_files else None
    except Exception as e:
        print(f"Error accessing directory {dir_name}: {e}")
    return None

def find_image_file(image_path):
    extensions = ['.jpg', '.jpeg', '.png', '.webp']
    image_path = os.path.abspath(image_path)
    debug_print(f"Debug: Processing image path: {image_path}")
    ext = os.path.splitext(image_path)[1].lower()
    if ext in extensions and os.path.exists(image_path):
        debug_print(f"Debug: Found image file directly: {image_path}")
        return image_path
    dir_name = os.path.dirname(image_path) if os.path.dirname(image_path) else os.path.abspath(".")
    base_name = os.path.splitext(os.path.basename(image_path))[0].lower()
    debug_print(f"Debug: Searching for image with base name '{base_name}' in directory '{dir_name}'")
    if not os.path.isdir(dir_name):
        debug_print(f"Debug: Directory does not exist: {dir_name}")
        return None
    try:
        matching_files = []
        for file in os.listdir(dir_name):
            file_lower = file.lower()
            file_ext = os.path.splitext(file_lower)[1]
            if os.path.splitext(file_lower)[0] == base_name and file_ext in extensions:
                matching_files.append(os.path.join(dir_name, file))
        if not matching_files:
            debug_print(f"Debug: No matching image files found for base name '{base_name}' in '{dir_name}'")
            return None
        for ext in extensions:
            for match in matching_files:
                if match.lower().endswith(ext):
                    if len(matching_files) > 1 and DEBUG:
                        print(f"Warning: Multiple images found for '{base_name}': {matching_files}. Using '{match}'.")
                    debug_print(f"Debug: Selected image file: {match}")
                    return match
        debug_print(f"Debug: Selected image file (fallback): {matching_files[0]}")
        return matching_files[0]
    except Exception as e:
        print(f"Error accessing directory {dir_name}: {e}")
        return None

def get_video_title(file_path, auth):
    yt_dlp_title_cmd = f'yt-dlp {auth} --get-title "{file_path}"'
    success, output = run_command(yt_dlp_title_cmd, suppress_errors=False)
    if success and output.strip() and not output.lower().startswith("error"):
        return output.strip()
    return None

def determine_best_resolution(image_files):
    dimensions = []
    for image_file in image_files:
        width, height = get_image_dimensions(image_file)
        dimensions.append((width, height))
    if not dimensions:
        print("Error: No dimensions determined for any image. Using default 1920x1080.")
        return 1920, 1080
    aspect_ratios = [(w/h) for w, h in dimensions]
    categories = {'landscape': 0, 'portrait': 0, 'square': 0}
    for ar in aspect_ratios:
        if ar > 1.5:
            categories['landscape'] += 1
        elif ar < 0.67:
            categories['portrait'] += 1
        else:
            categories['square'] += 1
    dominant_category = max(categories, key=categories.get)
    if dominant_category == 'landscape':
        target_width, target_height = 1920, 1080
    elif dominant_category == 'portrait':
        target_width, target_height = 1080, 1920
    else:
        target_width, target_height = 1080, 1080
    target_width = target_width + (target_width % 2)
    target_height = target_height + (target_height % 2)
    return target_width, target_height

def parse_image_names(image_names, folder_path):
    """Parse image_names as a list, range (e.g., P0-P32), or wildcard (e.g., P*)."""
    if not image_names:  # If no image_names provided, return all images in folder
        extensions = ['*.jpg', '*.jpeg', '*.png', '*.webp']
        image_files = []
        for ext in extensions:
            pattern = os.path.join(folder_path, ext)
            image_files.extend(glob.glob(pattern))
        image_names = [os.path.splitext(os.path.basename(f))[0] for f in sorted(image_files)]
        if not image_names:
            print(f"Error: No images found in {folder_path}")
            sys.exit(1)
        return image_names
    if len(image_names) == 1:
        name = image_names[0]
        range_match = re.match(r'^([A-Za-z]+)(\d+)-([A-Za-z]+)(\d+)$', name)
        if range_match:
            prefix1, start, prefix2, end = range_match.groups()
            if prefix1 == prefix2 and start.isdigit() and end.isdigit():
                start, end = int(start), int(end)
                if start <= end:
                    return [f"{prefix1}{i}" for i in range(start, end + 1)]
                else:
                    print(f"Error: Invalid range {name}. Start must be less than or equal to end.")
                    sys.exit(1)
            else:
                print(f"Error: Invalid range format {name}. Use format like P0-P32.")
                sys.exit(1)
        if '*' in name:
            pattern = os.path.join(folder_path, name + '.*')
            files = glob.glob(pattern)
            image_names = [os.path.splitext(os.path.basename(f))[0] for f in sorted(files)]
            if not image_names:
                print(f"Error: No images found matching pattern {name} in {folder_path}")
                sys.exit(1)
            return image_names
    return image_names

def extract_image_features(image_path, target_size=(224, 224)):
    """Extract features from an image using a pre-trained MobileNetV2 model."""
    import tensorflow as tf
    import numpy as np
    from tensorflow.keras.applications import MobileNetV2
    from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
    from tensorflow.keras.preprocessing.image import img_to_array, load_img
    try:
        img = load_img(image_path, target_size=target_size)
        img_array = img_to_array(img)
        img_array = np.expand_dims(img_array, axis=0)
        img_array = preprocess_input(img_array)
        model = MobileNetV2(weights='imagenet', include_top=False, pooling='avg')
        features = model.predict(img_array)
        return features.flatten()
    except Exception as e:
        print(f"Error extracting features from {image_path}: {e}")
        return None

def main():
    global DEBUG
    parser = argparse.ArgumentParser(description="Process media files: trim, loop, loopaudio, split, combine, convert, create slideshows, concatenate, group, or copyrename")
    subparsers = parser.add_subparsers(dest="submode", help="Submode: 'trim', 'loop', 'loopaudio', 'split', 'combine', 'convert', 'slide', 'concat', 'group', 'copyrename'")
    subparsers.required = True

    # Subparser for 'trim' submode
    parser_trim = subparsers.add_parser("trim", help="Trim audio or video without looping")
    trim_subparsers = parser_trim.add_subparsers(dest="output_type", help="Output type: 'a' for audio (.m4a), 'v' for video (.mp4)")
    trim_subparsers.required = True
    parser_trim_audio = trim_subparsers.add_parser("a", help="Output as audio (.m4a)")
    parser_trim_audio.add_argument("input_path", help="Path to the audio or video file (e.g., ./videos/U1 for U1.mp4 or ./audio/A1 for A1.m4a)")
    parser_trim_audio.add_argument("--start", type=float, default=0, help="Start time in seconds (default: 0)")
    parser_trim_audio.add_argument("--end", type=float, required=True, help="End time in seconds")
    parser_trim_audio.add_argument("--output-dir", "-o", help="Directory where output will be saved (default: same as input file directory)")
    parser_trim_audio.add_argument("--username")
    parser_trim_audio.add_argument("--password")
    parser_trim_audio.add_argument("--cookies")
    parser_trim_audio.add_argument("--debug", action="store_true", help="Enable debug output")
    parser_trim_video = trim_subparsers.add_parser("v", help="Output as video (.mp4)")
    parser_trim_video.add_argument("input_path", help="Path to the video file (e.g., ./videos/U1 for U1.mp4)")
    parser_trim_video.add_argument("--start", type=float, default=0, help="Start time in seconds (default: 0)")
    parser_trim_video.add_argument("--end", type=float, required=True, help="End time in seconds")
    parser_trim_video.add_argument("--output-dir", "-o", help="Directory where output will be saved (default: same as video file directory)")
    parser_trim_video.add_argument("--username")
    parser_trim_video.add_argument("--password")
    parser_trim_video.add_argument("--cookies")
    parser_trim_video.add_argument("--debug", action="store_true", help="Enable debug output")

    # Subparser for 'loop' submode
    parser_loop = subparsers.add_parser("loop", help="Trim and loop audio or video to a desired duration")
    loop_subparsers = parser_loop.add_subparsers(dest="output_type", help="Output type: 'a' for audio (.m4a), 'v' for video (.mp4)")
    loop_subparsers.required = True
    parser_loop_audio = loop_subparsers.add_parser("a", help="Output as audio (.m4a)")
    parser_loop_audio.add_argument("video_path", help="Path to the video file (e.g., ./videos/U1 for U1.mp4)")
    parser_loop_audio.add_argument("--start", type=float, default=0, help="Start time in seconds (default: 0)")
    parser_loop_audio.add_argument("--end", type=float, required=True, help="End time in seconds")
    parser_loop_audio.add_argument("--duration", type=float, help="Desired output duration in seconds (optional, enables looping)")
    parser_loop_audio.add_argument("--output-dir", "-o", help="Directory where output will be saved (default: same as video file directory)")
    parser_loop_audio.add_argument("--username")
    parser_loop_audio.add_argument("--password")
    parser_loop_audio.add_argument("--cookies")
    parser_loop_audio.add_argument("--debug", action="store_true", help="Enable debug output")
    parser_loop_video = loop_subparsers.add_parser("v", help="Output as video (.mp4)")
    parser_loop_video.add_argument("video_path", help="Path to the video file (e.g., ./videos/U1 for U1.mp4)")
    parser_loop_video.add_argument("--start", type=float, default=0, help="Start time in seconds (default: 0)")
    parser_loop_video.add_argument("--end", type=float, required=True, help="End time in seconds")
    parser_loop_video.add_argument("--duration", type=float, help="Desired output duration in seconds (optional, enables looping)")
    parser_loop_video.add_argument("--output-dir", "-o", help="Directory where output will be saved (default: same as video file directory)")
    parser_loop_video.add_argument("--username")
    parser_loop_video.add_argument("--password")
    parser_loop_video.add_argument("--cookies")
    parser_loop_video.add_argument("--debug", action="store_true", help="Enable debug output")

    # Subparser for 'loopaudio' submode
    parser_loopaudio = subparsers.add_parser("loopaudio", help="Loop an audio file to a desired duration without trimming")
    parser_loopaudio.add_argument("audio_path", help="Path to the audio file (e.g., ./audio/A1 for A1.m4a)")
    parser_loopaudio.add_argument("duration", type=float, help="Desired output duration in seconds")
    parser_loopaudio.add_argument("--output-dir", "-o", help="Directory where output will be saved (default: same as audio file directory)")
    parser_loopaudio.add_argument("--username")
    parser_loopaudio.add_argument("--password")
    parser_loopaudio.add_argument("--cookies")
    parser_loopaudio.add_argument("--debug", action="store_true", help="Enable debug output")

    # Subparser for 'split' submode
    parser_split = subparsers.add_parser("split", help="Split a video into separate video and audio files")
    parser_split.add_argument("input_path", help="Path to the input video file (e.g., ./videos/O11 for O11.mp4)")
    parser_split.add_argument("--output-dir", "-o", help="Directory where outputs will be saved (default: same as input file directory)")
    parser_split.add_argument("--username")
    parser_split.add_argument("--password")
    parser_split.add_argument("--cookies")
    parser_split.add_argument("--debug", action="store_true", help="Enable debug output")

    # Subparser for 'combine' submode
    parser_combine = subparsers.add_parser("combine", help="Combine video and audio files into a single video")
    parser_combine.add_argument("input", nargs='?', default=".", help="Either a directory containing video/audio pairs (e.g., ./combine) or omit to process pairs in the current directory")
    parser_combine.add_argument("--output-dir", "-o", help="Directory where output will be saved (default: same as video file directory)")
    parser_combine.add_argument("--username")
    parser_combine.add_argument("--password")
    parser_combine.add_argument("--cookies")
    parser_combine.add_argument("--debug", action="store_true", help="Enable debug output")

    # Subparser for 'convert' submode
    parser_convert = subparsers.add_parser("convert", help="Convert existing videos to universal format")
    parser_convert.add_argument("input", nargs='+', help="Directories containing video files (e.g., ./folder34 ./folder35)")
    parser_convert.add_argument("--output-dir", "-o", default=".", help="Directory where outputs will be saved (default: current directory)")
    parser_convert.add_argument("--username")
    parser_convert.add_argument("--password")
    parser_convert.add_argument("--cookies")
    parser_convert.add_argument("--debug", action="store_true", help="Enable debug output")

    # Subparser for 'slide' submode
    parser_slide = subparsers.add_parser("slide", help="Create a slideshow video from images in a folder")
    parser_slide.add_argument("delay", type=float, help="Delay in seconds for each image")
    parser_slide.add_argument("folder_path", help="Path to the folder containing image files (e.g., ./slide_in)")
    parser_slide.add_argument("image_names", nargs='*', help="Names of image files without extensions, range (e.g., P0-P32), or wildcard (e.g., P*). If omitted, uses all images in folder.")
    parser_slide.add_argument("--output-dir", "-o", help="Directory where output will be saved (default: folder path)")
    parser_slide.add_argument("--keep-original", action="store_true", help="Use original image resolutions and formats without resizing")
    parser_slide.add_argument("--username")
    parser_slide.add_argument("--password")
    parser_slide.add_argument("--cookies")
    parser_slide.add_argument("--debug", action="store_true", help="Enable debug output")

    # Subparser for 'concat' submode
    parser_concat = subparsers.add_parser("concat", help="Concatenate multiple videos into one")
    parser_concat.add_argument("video_paths", nargs='+', help="Paths to video files or a single directory containing video files to concatenate")
    parser_concat.add_argument("--output-dir", "-o", help="Directory where output will be saved (default: current directory)")
    parser_concat.add_argument("--username")
    parser_concat.add_argument("--password")
    parser_concat.add_argument("--cookies")
    parser_concat.add_argument("--debug", action="store_true", help="Enable debug output")

    # Subparser for 'group' submode
    parser_group = subparsers.add_parser("group", help="Group images in a folder by visual similarity")
    parser_group.add_argument("folder_path", help="Path to the folder containing images to group (e.g., ./reels)")
    parser_group.add_argument("num_clusters", type=int, help="Number of clusters to group images into (e.g., 3)")
    parser_group.add_argument("--output-dir", "-o", help="Directory where grouped images will be saved (default: folder_path/grouped)")
    parser_group.add_argument("--username")
    parser_group.add_argument("--password")
    parser_group.add_argument("--cookies")
    parser_group.add_argument("--debug", action="store_true", help="Enable debug output")

    # Subparser for 'copyrename' submode
    parser_copyrename = subparsers.add_parser("copyrename", help="Copy and rename pictures and reels from subfolders into a single folder")
    parser_copyrename.add_argument("source_dir", help="Path to the source folder containing subfolders with pictures and reels (e.g., C:\\Users\\user\\path)")
    parser_copyrename.add_argument("dest_dir", help="Path to the destination folder where files will be copied and renamed (e.g., C:\\Users\\user\\output)")
    parser_copyrename.add_argument("--username")
    parser_copyrename.add_argument("--password")
    parser_copyrename.add_argument("--cookies")
    parser_copyrename.add_argument("--debug", action="store_true", help="Enable debug output")

    args = parser.parse_args()
    DEBUG = args.debug
    submode = args.submode

    if args.username and args.password:
        auth = f"--username {args.username} --password {args.password}"
    elif args.cookies:
        auth = f"--cookies {args.cookies}"
    else:
        auth = "--cookies-from-browser firefox"

    temp_dir = os.path.abspath(os.path.join(".", "temp_slideshow"))
    temp_trimmed_path = os.path.join(temp_dir, "temp_trimmed_file")

    try:
        if submode in ["trim", "loop"]:
            output_type = args.output_type
            # MODIFIED START: Use input_path instead of video_path and handle audio/video
            input_path = args.input_path if submode == "trim" else args.video_path
            start_time = args.start
            end_time = args.end
            desired_duration = getattr(args, "duration", None)
            output_dir = args.output_dir if args.output_dir else os.path.dirname(os.path.abspath(input_path)) or "."
            # Determine if input is audio or video based on output_type for trim submode
            if submode == "trim":
                if output_type == "a":
                    actual_input_path = find_audio_file(input_path)
                else:
                    actual_input_path = find_video_file(input_path)
            else:
                actual_input_path = find_video_file(input_path)
            # MODIFIED END
            if not actual_input_path or not os.path.exists(actual_input_path):
                print(f"Error: {'Audio' if output_type == 'a' and submode == 'trim' else 'Video'} file not found: {input_path}")
                sys.exit(1)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            file_duration = get_file_duration(actual_input_path)
            if file_duration == 0:
                print(f"Error: Could not determine duration of {actual_input_path}")
                sys.exit(1)
            if start_time < 0 or start_time >= file_duration:
                print(f"Error: Start time {start_time} is out of bounds (file duration: {file_duration} seconds)")
                sys.exit(1)
            if end_time <= start_time or end_time > file_duration:
                print(f"Error: End time {end_time} is out of bounds (start: {start_time}, file duration: {file_duration} seconds)")
                sys.exit(1)
            trim_duration = end_time - start_time
            file_title = os.path.splitext(os.path.basename(actual_input_path))[0]
            title = get_video_title(actual_input_path, auth) if submode == "trim" and output_type == "v" else None
            if title:
                file_title = title
            if output_type == "a":
                prefix = "A" if submode == "trim" else "AL"
                extension = ".m4a"
            else:
                prefix = "V" if submode == "trim" else "VL"
                extension = ".mp4"
            output_name_with_ext, output_path, _ = get_next_available_name(
                output_dir, prefix, extension
            )
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            try:
                if output_type == "v":
                    ffmpeg_cmd = (
                        f'ffmpeg -y -i "{actual_input_path}" -ss {start_time} -t {trim_duration} '
                        f'-c:v copy -c:a aac -b:a 128k "{temp_trimmed_path}{extension}"'
                    )
                else:
                    ffmpeg_cmd = (
                        f'ffmpeg -y -i "{actual_input_path}" -vn -ss {start_time} -t {trim_duration} '
                        f'-c:a aac -b:a 128k "{temp_trimmed_path}{extension}"'
                    )
                success, output = run_command(ffmpeg_cmd)
                if not success or not os.path.exists(f"{temp_trimmed_path}{extension}"):
                    print(f"Failed to trim {actual_input_path}")
                    sys.exit(1)
                if submode == "trim":
                    os.rename(f"{temp_trimmed_path}{extension}", output_path)
                    print(f"Saved {'Audio' if output_type == 'a' else 'Video'} as {output_path.replace(os.sep, '/')}")
                else:
                    if desired_duration:
                        loop_duration = desired_duration
                        if loop_duration <= trim_duration:
                            print(f"Warning: Desired duration {loop_duration} is less than or equal to trimmed duration {trim_duration}. No looping needed.")
                            os.rename(f"{temp_trimmed_path}{extension}", output_path)
                            print(f"Saved {'Audio' if output_type == 'a' else 'Video'} as {output_path.replace(os.sep, '/')}")
                        else:
                            loop_count = int(loop_duration // trim_duration)
                            if loop_duration % trim_duration > 0:
                                loop_count += 1
                            final_duration = min(loop_duration, loop_count * trim_duration)
                            if output_type == "v":
                                ffmpeg_cmd = (
                                    f'ffmpeg -y -stream_loop {loop_count - 1} -i "{temp_trimmed_path}{extension}" '
                                    f'-c:v copy -c:a copy -t {final_duration} "{output_path}"'
                                )
                            else:
                                ffmpeg_cmd = (
                                    f'ffmpeg -y -stream_loop {loop_count - 1} -i "{temp_trimmed_path}{extension}" '
                                    f'-c:a copy -t {final_duration} "{output_path}"'
                                )
                            success, output = run_command(ffmpeg_cmd)
                            if success:
                                print(f"Saved Looped {'Audio' if output_type == 'a' else 'Video'} as {output_path.replace(os.sep, '/')}")
                            else:
                                print(f"Failed to loop {actual_input_path}")
                                sys.exit(1)
                            if os.path.exists(f"{temp_trimmed_path}{extension}"):
                                os.remove(f"{temp_trimmed_path}{extension}")
                    else:
                        os.rename(f"{temp_trimmed_path}{extension}", output_path)
                        print(f"Saved {'Audio' if output_type == 'a' else 'Video'} as {output_path.replace(os.sep, '/')}")
            finally:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)

        elif submode == "loopaudio":
            audio_path = args.audio_path
            desired_duration = args.duration
            output_dir = args.output_dir or os.path.dirname(os.path.abspath(audio_path)) or "."
            actual_audio_path = find_audio_file(audio_path)
            if not actual_audio_path or not os.path.exists(actual_audio_path):
                print(f"Error: Audio file not found: {audio_path}")
                sys.exit(1)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            audio_duration = get_file_duration(actual_audio_path)
            if audio_duration == 0:
                print(f"Error: Could not determine duration of {actual_audio_path}")
                sys.exit(1)
            if desired_duration <= audio_duration:
                print(f"Warning: Desired duration {desired_duration} is less than or equal to audio duration {audio_duration}. No looping needed.")
                loop_count = 0
                final_duration = desired_duration
            else:
                loop_count = int(desired_duration // audio_duration)
                if desired_duration % audio_duration > 0:
                    loop_count += 1
                final_duration = min(desired_duration, loop_count * audio_duration)
            output_name_with_ext, output_path, _ = get_next_available_name(
                output_dir, "Audio", ".m4a"
            )
            ffmpeg_cmd = (
                f'ffmpeg -y -stream_loop {loop_count - 1} -i "{actual_audio_path}" '
                f'-c:a aac -b:a 128k -t {final_duration} "{output_path}"'
            )
            success, output = run_command(ffmpeg_cmd)
            if success:
                print(f"Saved Looped Audio as {output_path.replace(os.sep, '/')}")
            else:
                print(f"Failed to loop {actual_audio_path}")
                sys.exit(1)

        elif submode == "split":
            input_path = args.input_path
            output_dir = args.output_dir or os.path.dirname(os.path.abspath(input_path)) or "."
            actual_input_path = find_video_file(input_path)
            if not actual_input_path or not os.path.exists(actual_input_path):
                print(f"Error: Input file not found: {input_path}")
                sys.exit(1)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            video_output_name_with_ext, video_output_path, _ = get_next_available_name(
                output_dir, "Vid", ".mp4"
            )
            audio_output_path = os.path.join(output_dir, f"{os.path.splitext(video_output_name_with_ext)[0]}_audio.m4a")
            ffmpeg_cmd = (
                f'ffmpeg -y -i "{actual_input_path}" -c:v copy -an "{video_output_path}"'
            )
            success, output = run_command(ffmpeg_cmd)
            if success:
                print(f"Saved Video-only as {video_output_path.replace(os.sep, '/')}")
                if has_audio_stream(actual_input_path):
                    ffmpeg_cmd = (
                        f'ffmpeg -y -i "{actual_input_path}" -vn -c:a aac -b:a 128k "{audio_output_path}"'
                    )
                    success, output = run_command(ffmpeg_cmd)
                    if success:
                        print(f"Saved Audio as {audio_output_path.replace(os.sep, '/')}")
                    else:
                        print(f"Failed to extract audio from {actual_input_path}")
                        os.remove(video_output_path)
                        sys.exit(1)
                else:
                    print(f"No audio stream in {actual_input_path}")
            else:
                print(f"Failed to split video from {actual_input_path}")
                sys.exit(1)

        elif submode == "combine":
            input_path = args.input
            output_dir = args.output_dir or input_path if os.path.isdir(input_path) else os.path.dirname(os.path.abspath(input_path)) or "."
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            abs_input_path = os.path.abspath(input_path)
            debug_print(f"Debug: Scanning directory {abs_input_path}")

            video_extensions = ['.mp4', '.mkv']
            audio_extensions = ['.m4a', '.mp3', '.wav', '.aac', '.flac', '.ogg', '.mp4', '.mkv']
            all_files = []

            if os.path.isdir(abs_input_path):
                debug_print(f"Debug: Directory exists. Listing files...")
                for file in os.listdir(abs_input_path):
                    file_lower = file.lower()
                    base_name, ext = os.path.splitext(file_lower)
                    if ext in video_extensions or ext in audio_extensions:
                        all_files.append((base_name, file, ext))
                        debug_print(f"Debug: Found file: {file}")
            else:
                print(f"Error: {abs_input_path} is not a directory. Please provide a directory path or run in a directory with video/audio pairs.")
                sys.exit(1)

            if not all_files:
                print(f"No video or audio files found in {abs_input_path}.")
                sys.exit(1)

            video_files = []
            audio_files = []
            for base_name, file_name, ext in all_files:
                full_path = os.path.join(abs_input_path, file_name)
                if base_name.startswith('v') or 'media-video' in base_name:
                    video_files.append((base_name, full_path))
                    debug_print(f"Debug: Classified as video: {file_name}")
                elif base_name.startswith('a') or 'media-audio' in base_name:
                    audio_files.append((base_name, full_path))
                    debug_print(f"Debug: Classified as audio: {file_name}")
                else:
                    debug_print(f"Debug: Skipping file {file_name} - does not start with V/A or contain media-video/media-audio")

            def get_number(filename):
                base_name = filename[0]
                if base_name.startswith('v') or base_name.startswith('a'):
                    match = re.match(r'^(v|a)(\d+)$', base_name, re.IGNORECASE)
                    return int(match.group(2)) if match else float('inf')
                elif 'media-video' in base_name or 'media-audio' in base_name:
                    parts = base_name.rsplit('-', 1)
                    if len(parts) > 1 and parts[-1].isdigit():
                        return int(parts[-1])
                return float('inf')

            video_files.sort(key=get_number)
            audio_files.sort(key=get_number)

            pairs = []
            for video_base, video_path in video_files:
                video_num = get_number((video_base, video_path))
                for audio_base, audio_path in audio_files:
                    audio_num = get_number((audio_base, audio_path))
                    if video_num == audio_num:
                        pairs.append((video_base, video_path, audio_base, audio_path))
                        debug_print(f"Debug: Paired {video_base} with {audio_base}")
                        break
                else:
                    debug_print(f"Debug: No audio match found for {video_base}")

            if not pairs:
                print(f"No matching video/audio pairs found in {abs_input_path}. Ensure files are named like V1.mp4 and A1.mp4, or media-video-...-1.mp4 and media-audio-...-1.mp4.")
                sys.exit(1)

            print(f"Found {len(pairs)} video/audio pairs to combine: {[v_base for v_base, _, a_base, _ in pairs]}")

            current_number = 1
            for video_base, video_path, audio_base, audio_path in pairs:
                print(f"Processing pair {current_number}/{len(pairs)}: {video_base} with {audio_base}")
                actual_video_path = video_path
                actual_audio_path = audio_path

                if not os.path.exists(actual_video_path):
                    print(f"Error: Video file not found: {actual_video_path}")
                    continue
                if not os.path.exists(actual_audio_path):
                    print(f"Error: Audio file not found: {actual_audio_path}")
                    continue

                if not has_video_stream(actual_video_path):
                    print(f"Error: {actual_video_path} does not contain a video stream. Skipping.")
                    continue
                if not has_audio_stream(actual_audio_path):
                    print(f"Error: {actual_audio_path} does not contain an audio stream. Skipping.")
                    continue

                video_duration = get_file_duration(actual_video_path)
                audio_duration = get_file_duration(actual_audio_path)
                if video_duration == 0 or audio_duration == 0:
                    print(f"Error: Could not determine duration of {actual_video_path} or {actual_audio_path}")
                    continue

                output_name_with_ext, output_path, _ = get_next_available_name(
                    output_dir, "Comb", ".mp4", start_num=current_number
                )
                loop_count = int(video_duration // audio_duration) if audio_duration > 0 else 0
                if video_duration % audio_duration > 0:
                    loop_count += 1
                max_duration = 140
                final_duration = video_duration if video_duration > 0 else max_duration

                ffmpeg_cmd = (
                    f'ffmpeg -y -i "{actual_video_path}" -stream_loop {loop_count - 1} -i "{actual_audio_path}" '
                    f'-map 0:v:0 -map 1:a:0 '
                    f'-c:v libx264 -preset ultrafast -b:v 3500k -r 30 -pix_fmt yuv420p '
                    f'-c:a aac -b:a 128k -ar 44100 -shortest -t {final_duration} "{output_path}"'
                )

                success, output = run_command(ffmpeg_cmd)
                if success:
                    print(f"Saved Combined Video as {output_path.replace(os.sep, '/')}")
                else:
                    print(f"Failed to combine {actual_video_path} and {actual_audio_path}")
                    debug_print(f"FFmpeg output: {output}")
                current_number += 1

        elif submode == "convert":
            input_dirs = args.input
            output_dir = os.path.abspath(args.output_dir)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            current_number = 1
            for input_dir in input_dirs:
                if os.path.isdir(input_dir):
                    video_extensions = ['*.mp4', '*.mkv']
                    video_files = []
                    for ext in video_extensions:
                        pattern = os.path.join(input_dir, ext)
                        debug_print(f"Debug: Searching for files with pattern: {pattern}")
                        found_files = glob.glob(pattern)
                        debug_print(f"Debug: Found files: {found_files}")
                        video_files.extend(found_files)
                    seen = set()
                    unique_video_files = []
                    for f in video_files:
                        f_lower = f.lower()
                        if f_lower not in seen:
                            seen.add(f_lower)
                            unique_video_files.append(f)
                    def get_number(filename):
                        basename = os.path.basename(filename)
                        match = re.match(r'O(\d+)\.\w+$', basename)
                        if match:
                            return int(match.group(1))
                        return float('inf')
                    video_files = sorted(unique_video_files, key=get_number)
                    debug_print(f"Debug: Sorted files (by numerical order): {video_files}")
                else:
                    debug_print(f"Debug: Using wildcard pattern: {input_dir}")
                    video_files = glob.glob(input_dir)
                    seen = set()
                    unique_video_files = []
                    for f in video_files:
                        f_lower = f.lower()
                        if f_lower not in seen:
                            seen.add(f_lower)
                            unique_video_files.append(f)
                    def get_number(filename):
                        basename = os.path.basename(filename)
                        match = re.match(r'O(\d+)\.\w+$', basename)
                        if match:
                            return int(match.group(1))
                        return float('inf')
                    video_files = sorted(unique_video_files, key=get_number)

                if not video_files:
                    print(f"No video files found in {input_dir}")
                    continue

                print(f"Processing folder: {input_dir}")
                for idx, video_file in enumerate(video_files, start=1):
                    print(f"Converting {video_file} ({idx}/{len(video_files)} in {input_dir})...")
                    output_name_with_ext, output_path, _ = get_next_available_name(
                        output_dir, "Uni", ".mp4", start_num=current_number
                    )
                    width, height = get_video_dimensions(video_file)
                    width = width + (width % 2)
                    height = height + (height % 2)
                    aspect_ratio = width / height
                    if aspect_ratio > 1.5:
                        target_width, target_height = 1920, 1080
                    elif aspect_ratio < 0.67:
                        target_width, target_height = 1080, 1920
                    else:
                        target_width, target_height = 1080, 1080
                    target_width = target_width + (target_width % 2)
                    target_height = target_height + (target_height % 2)
                    ffmpeg_cmd = (
                        f'ffmpeg -y -i "{video_file}" -fflags +genpts -c:v libx264 -preset ultrafast -b:v 3500k '
                        f'-force_key_frames "0" '
                        f'-vf "scale={target_width}:{target_height}:force_divisible_by=2,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2" -r 30 '
                        f'-c:a aac -b:a 128k -ar 44100 -t 140 "{output_path}"'
                    )
                    debug_print(f"Debug: FFmpeg command: {ffmpeg_cmd}")
                    success, output = run_command(ffmpeg_cmd, timeout=30, retries=1)
                    if success:
                        print(f"Saved Universal as {output_path.replace(os.sep, '/')}")
                        current_number += 1
                    else:
                        print(f"Failed to convert {video_file}")
                        print(f"FFmpeg output: {output}")
                        sys.exit(1)

        elif submode == "slide":
            delay = args.delay
            folder_path = args.folder_path
            image_names = args.image_names
            output_dir = args.output_dir or os.path.abspath(folder_path)
            keep_original = args.keep_original

            if not os.path.isdir(folder_path):
                print(f"Error: Folder path does not exist: {folder_path}")
                sys.exit(1)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            image_names = parse_image_names(image_names, folder_path)
            image_paths = [os.path.join(folder_path, name) for name in image_names]
            actual_image_paths = []
            for image_path in image_paths:
                actual_image_path = find_image_file(image_path)
                if not actual_image_path or not os.path.exists(actual_image_path):
                    print(f"Error: Image file not found: {image_path}. Supported extensions: .jpg, .jpeg, .png, .webp")
                    sys.exit(1)
                debug_print(f"Debug: Resolved image path: {image_path} -> {actual_image_path}")
                actual_image_paths.append(actual_image_path)

            if not actual_image_paths:
                print(f"No image files found for names: {image_names}. Supported extensions: .jpg, .jpeg, .png, .webp")
                sys.exit(1)

            target_width, target_height = determine_best_resolution(actual_image_paths)
            debug_print(f"Debug: Determined target resolution: {target_width}x{target_height}")

            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

            try:
                processed_videos = []
                for idx, image_path in enumerate(actual_image_paths):
                    temp_video = os.path.join(temp_dir, f"image_{idx:03d}.mp4")
                    debug_print(f"Debug: Converting image {image_path} to video {temp_video}")

                    if keep_original:
                        width, height = get_image_dimensions(image_path)
                        width = width + (width % 2)
                        height = height + (height % 2)
                        ffmpeg_cmd = (
                            f'ffmpeg -y -loop 1 -i "{image_path}" '
                            f'-c:v libx264 -preset fast -b:v 3500k -r 30 -pix_fmt yuv420p '
                            f'-vf "scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2" '
                            f'-t {delay} "{temp_video}"'
                        )
                    else:
                        ffmpeg_cmd = (
                            f'ffmpeg -y -loop 1 -i "{image_path}" '
                            f'-c:v libx264 -preset fast -b:v 3500k -r 30 -pix_fmt yuv420p '
                            f'-vf "scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2" '
                            f'-t {delay} "{temp_video}"'
                        )

                    success, output = run_command(ffmpeg_cmd)
                    if success and os.path.exists(temp_video):
                        processed_videos.append(temp_video)
                        debug_print(f"Debug: Successfully created: {temp_video}")
                    else:
                        print(f"Failed to process image {image_path} into video")
                        debug_print(f"Debug: FFmpeg output: {output}")
                        sys.exit(1)

                concat_list_path = os.path.join(temp_dir, "concat_list.txt")
                debug_print(f"Debug: Creating concat list at {concat_list_path}")
                with open(concat_list_path, "w") as f:
                    for vid in processed_videos:
                        f.write(f"file '{os.path.abspath(vid)}'\n")

                output_name_with_ext, output_path, _ = get_next_available_name(
                    output_dir, "Slide", ".mp4"
                )
                debug_print(f"Debug: Saving slideshow to {output_path}")

                ffmpeg_cmd = (
                    f'ffmpeg -y -f concat -safe 0 -i "{concat_list_path}" '
                    f'-c:v copy -an "{output_path}"'
                )
                success, output = run_command(ffmpeg_cmd)
                if success:
                    print(f"Saved Slideshow as {output_path.replace(os.sep, '/')}")
                else:
                    print("Failed to create slideshow")
                    debug_print(f"FFmpeg output: {output}")
                    sys.exit(1)

            finally:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)

        elif submode == "concat":
            video_paths = args.video_paths
            output_dir = args.output_dir or "."
            base_dir = None
            if len(video_paths) > 0 and os.path.dirname(video_paths[0]):
                base_dir = os.path.dirname(video_paths[0])
                debug_print(f"Debug: Using base directory from first argument: {base_dir}")
            if len(video_paths) == 1 and os.path.isdir(video_paths[0]):
                video_dir = os.path.abspath(video_paths[0])
                video_extensions = ['*.mp4', '*.mkv']
                video_files = []
                for ext in video_extensions:
                    pattern = os.path.join(video_dir, ext)
                    debug_print(f"Debug: Searching for files with pattern: {pattern}")
                    found_files = glob.glob(pattern)
                    debug_print(f"Debug: Found files: {found_files}")
                    video_files.extend(found_files)
                video_files = sorted(set(f.lower() for f in video_files))
                video_files = [next(f for f in video_files if f.lower() == v.lower()) for v in video_files]
                video_paths = sorted(video_files)
                if not video_paths:
                    print(f"No video files found in directory: {video_dir}")
                    sys.exit(1)
            else:
                video_paths = args.video_paths
            actual_video_paths = []
            segment_durations = []
            for video_path in video_paths:
                actual_video_path = find_video_file(video_path, base_dir=base_dir)
                if not actual_video_path or not os.path.exists(actual_video_path):
                    print(f"Error: Video file not found: {video_path}")
                    sys.exit(1)
                duration = get_file_duration(actual_video_path)
                if duration == 0:
                    print(f"Error: Could not determine duration of {video_path}")
                    sys.exit(1)
                actual_video_paths.append(actual_video_path)
                segment_durations.append(duration)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            width, height = get_video_dimensions(actual_video_paths[0])
            width = width + (width % 2)
            height = height + (height % 2)
            aspect_ratio = width / height
            if aspect_ratio > 1.5:
                width, height = 1920, 1080
            elif aspect_ratio < 0.67:
                width, height = 1080, 1920
            else:
                width, height = 1080, 1080
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            try:
                processed_video_paths = []
                fade_duration = 1.0
                num_videos = len(actual_video_paths)
                for idx, (video_path, duration) in enumerate(zip(actual_video_paths, segment_durations)):
                    temp_output = os.path.join(temp_dir, f"temp_{idx:03d}.mp4")
                    has_audio = has_audio_stream(video_path)
                    debug_print(f"Debug: Processing video {idx}: {video_path}, Duration: {duration}, Has Audio: {has_audio}")
                    apply_fade_in = idx > 0
                    apply_fade_out = idx < num_videos - 1
                    video_filters = [
                        f"scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2",
                        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
                        "setsar=1:1",
                        "fps=30"
                    ]
                    if apply_fade_in and apply_fade_out:
                        video_filters.append(f"fade=t=in:st=0:d={fade_duration},fade=t=out:st={duration-fade_duration}:d={fade_duration}")
                    elif apply_fade_in:
                        video_filters.append(f"fade=t=in:st=0:d={fade_duration}")
                    elif apply_fade_out:
                        video_filters.append(f"fade=t=out:st={duration-fade_duration}:d={fade_duration}")
                    video_filter_str = ",".join(video_filters)
                    if has_audio:
                        ffmpeg_cmd = (
                            f'ffmpeg -y -i "{video_path}" '
                            f'-c:v libx264 -preset ultrafast -b:v 3500k -r 30 -pix_fmt yuv420p '
                            f'-force_key_frames "expr:gte(t,n_forced*2)" '
                            f'-c:a aac -b:a 128k -ar 48000 -ac 2 '
                            f'-vf "{video_filter_str}" '
                            f'-t {duration} '
                            f'"{temp_output}"'
                        )
                    else:
                        ffmpeg_cmd = (
                            f'ffmpeg -y -i "{video_path}" '
                            f'-f lavfi -i anullsrc=channel_layout=stereo:sample_rate=48000 '
                            f'-c:v libx264 -preset ultrafast -b:v 3500k -r 30 -pix_fmt yuv420p '
                            f'-force_key_frames "expr:gte(t,n_forced*2)" '
                            f'-c:a aac -b:a 128k -ar 48000 -ac 2 -shortest '
                            f'-vf "{video_filter_str}" '
                            f'-t {duration} '
                            f'"{temp_output}"'
                        )
                    debug_print(f"Debug: Preprocessing command: {ffmpeg_cmd}")
                    success, output = run_command(ffmpeg_cmd, timeout=60, retries=1)
                    if not success or not os.path.exists(temp_output):
                        print(f"Failed to preprocess {video_path}: {output}")
                        sys.exit(1)
                    processed_video_paths.append(temp_output)
                concat_list_path = os.path.join(temp_dir, "concat_list.txt")
                with open(concat_list_path, "w") as f:
                    for vid in processed_video_paths:
                        f.write(f"file '{os.path.abspath(vid)}'\n")
                output_name_with_ext, output_path, _ = get_next_available_name(
                    output_dir, "Concat", ".mp4"
                )
                debug_print(f"Debug: Saving concatenated video to {output_path}")
                ffmpeg_cmd = (
                    f'ffmpeg -y -f concat -safe 0 -i "{concat_list_path}" '
                    f'-c:v libx264 -preset ultrafast -b:v 3500k -r 30 -pix_fmt yuv420p '
                    f'-c:a aac -b:a 128k -ar 48000 -ac 2 '
                    f'"{output_path}"'
                )
                debug_print(f"Debug: Final FFmpeg command: {ffmpeg_cmd}")
                success, output = run_command(ffmpeg_cmd, timeout=300, retries=1)
                if success:
                    print(f"Saved Concatenated Video as {output_path.replace(os.sep, '/')}")
                else:
                    print("Failed to concatenate videos")
                    debug_print(f"FFmpeg output: {output}")
                    sys.exit(1)
            finally:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)

        elif submode == "group":
            from sklearn.cluster import KMeans
            try:
                debug_print("Debug: Entering group submode")
                folder_path = args.folder_path
                num_clusters = args.num_clusters
                output_dir = args.output_dir or os.path.join(os.path.abspath(folder_path), "grouped")
                debug_print(f"Debug: Folder path: {folder_path}, Number of clusters: {num_clusters}, Output dir: {output_dir}")

                abs_folder_path = os.path.abspath(folder_path)
                debug_print(f"Debug: Scanning directory {abs_folder_path}")

                if not os.path.isdir(abs_folder_path):
                    print(f"Error: {abs_folder_path} is not a directory. Please provide a valid directory path.")
                    sys.exit(1)

                debug_print(f"Debug: Directory {abs_folder_path} exists. Listing files...")

                image_extensions = ['.jpg', '.jpeg', '.png', '.webp']
                image_files = []
                for file in os.listdir(abs_folder_path):
                    file_lower = file.lower()
                    _, ext = os.path.splitext(file_lower)
                    full_path = os.path.join(abs_folder_path, file)
                    if os.path.isfile(full_path) and ext in image_extensions:
                        image_files.append(full_path)
                        debug_print(f"Debug: Found image file: {full_path}")

                if not image_files:
                    print(f"No supported image files found in {abs_folder_path}.")
                    sys.exit(1)

                if num_clusters < 1:
                    print("Error: Number of clusters must be at least 1.")
                    sys.exit(1)

                if num_clusters > len(image_files):
                    print(f"Warning: Number of clusters ({num_clusters}) exceeds number of images ({len(image_files)}). Setting clusters to {len(image_files)}.")
                    num_clusters = len(image_files)

                debug_print("Debug: Extracting features from images...")
                features_list = []
                valid_image_files = []
                for image_path in image_files:
                    debug_print(f"Debug: Processing {image_path}")
                    features = extract_image_features(image_path)
                    if features is not None:
                        features_list.append(features)
                        valid_image_files.append(image_path)
                    else:
                        debug_print(f"Debug: Skipping {image_path} due to feature extraction failure")

                if not features_list:
                    print("Error: Could not extract features from any images.")
                    sys.exit(1)

                debug_print(f"Debug: Performing K-Means clustering with {num_clusters} clusters...")
                kmeans = KMeans(n_clusters=num_clusters, random_state=42)
                kmeans.fit(features_list)
                labels = kmeans.labels_
                debug_print(f"Debug: Clustering completed. Labels: {labels}")

                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                    debug_print(f"Debug: Created output directory {output_dir}")

                for cluster_id in range(num_clusters):
                    cluster_dir = os.path.join(output_dir, f"cluster_{cluster_id}")
                    if not os.path.exists(cluster_dir):
                        os.makedirs(cluster_dir)
                        debug_print(f"Debug: Created cluster directory {cluster_dir}")

                for image_path, label in zip(valid_image_files, labels):
                    cluster_dir = os.path.join(output_dir, f"cluster_{label}")
                    dest_path = os.path.join(cluster_dir, os.path.basename(image_path))
                    debug_print(f"Debug: Copying {image_path} to {dest_path}")
                    try:
                        shutil.copy2(image_path, dest_path)
                        print(f"Grouped {os.path.basename(image_path)} into cluster_{label}")
                    except Exception as e:
                        print(f"Failed to copy {image_path} to {dest_path}: {e}")
                        continue

                print(f"Successfully grouped {len(valid_image_files)} images into {num_clusters} clusters in {output_dir}")

            except Exception as e:
                print(f"Error in group submode: {e}")
                sys.exit(1)

        elif submode == "copyrename":
            try:
                debug_print("Debug: Entering copyrename submode")
                source_dir = args.source_dir
                dest_dir = args.dest_dir
                debug_print(f"Debug: Source directory: {source_dir}, Destination directory: {dest_dir}")

                abs_source_dir = os.path.abspath(source_dir)
                abs_dest_dir = os.path.abspath(dest_dir)
                debug_print(f"Debug: Absolute source directory: {abs_source_dir}, Absolute destination directory: {abs_dest_dir}")

                if not os.path.isdir(abs_source_dir):
                    print(f"Error: Source directory does not exist: {abs_source_dir}")
                    sys.exit(1)

                if not os.path.exists(abs_dest_dir):
                    os.makedirs(abs_dest_dir)
                    debug_print(f"Debug: Created destination directory: {abs_dest_dir}")

                picture_extensions = ['.jpg', '.jpeg', '.png', '.webp']
                reel_extensions = ['.mp4', '.mkv']

                files_to_copy = []
                for root, dirs, files in os.walk(abs_source_dir):
                    subfolder_name = os.path.basename(root)
                    for file in files:
                        file_lower = file.lower()
                        _, ext = os.path.splitext(file_lower)
                        full_path = os.path.join(root, file)
                        if ext in picture_extensions or ext in reel_extensions:
                            files_to_copy.append((full_path, subfolder_name, file, ext))
                            debug_print(f"Debug: Found file: {full_path} in subfolder: {subfolder_name}")

                if not files_to_copy:
                    print(f"No pictures or reels found in {abs_source_dir} or its subfolders.")
                    sys.exit(1)

                debug_print(f"Debug: Found {len(files_to_copy)} files to copy and rename")

                counter = 1
                for full_path, subfolder_name, file, ext in files_to_copy:
                    if ext in picture_extensions:
                        prefix = "Pic"
                    else:
                        prefix = "Reel"
                    output_name_with_ext, output_path, _ = get_next_available_name(
                        abs_dest_dir, prefix, ext, start_num=counter
                    )
                    debug_print(f"Debug: Copying {full_path} to {output_path}")
                    try:
                        shutil.copy2(full_path, output_path)
                        print(f"Copied and renamed {file} to {output_name_with_ext}")
                        counter += 1
                    except Exception as e:
                        print(f"Failed to copy {full_path} to {output_path}: {e}")
                        continue

            except Exception as e:
                print(f"Error in copyrename submode: {e}")
                sys.exit(1)

    except Exception as e:
        print(f"Error in {submode} submode: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
