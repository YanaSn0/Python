import subprocess
import sys
import os
import argparse
import glob
import json
import time
import re
from PIL import Image
import logging
import shutil
import hashlib
import uuid

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)
logger = logging.getLogger(__name__)

DEBUG = False

def debug_print(*args, **kwargs):
    if DEBUG:
        logger.debug(*args, **kwargs)

def run_command(command, suppress_errors=False, timeout=None, retries=1):
    attempt = 0
    while attempt < retries:
        debug_print(f"Running command (Attempt {attempt+1}/{retries}): {command}")
        stdout = subprocess.PIPE if not suppress_errors else subprocess.DEVNULL
        stderr = subprocess.PIPE if not suppress_errors else subprocess.DEVNULL
        process = subprocess.Popen(command, shell=True, stdout=stdout, stderr=stderr, text=True)
        try:
            stdout_data, stderr_data = process.communicate(timeout=timeout)
            if stdout_data:
                debug_print(f"STDOUT: {stdout_data}")
            if stderr_data:
                debug_print(f"STDERR: {stderr_data}")
            return_code = process.returncode
            if return_code != 0 and not suppress_errors:
                debug_print(f"Error: return_code={return_code}")
                return False, stdout_data + "\n" + stderr_data
            return True, stdout_data
        except subprocess.TimeoutExpired:
            process.kill()
            if attempt < retries - 1:
                debug_print(f"Timeout after {timeout}s. Retrying {attempt+1}/{retries}")
                time.sleep(2)
                attempt += 1
                continue
            debug_print(f"Timeout after {timeout}s. No more retries")
            return False, f"Timeout after {timeout}s"
        except Exception as ex:
            process.kill()
            debug_print(f"Command execution error: {ex}")
            return False, str(ex)
        finally:
            if process.poll() is None:
                process.terminate()

def get_file_hash(file_path):
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()[:8]
    except Exception:
        return str(uuid.uuid4())[:8]

def get_video_dimensions(video_path):
    command = f'ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of json "{video_path}"'
    success, output = run_command(command)
    if success:
        try:
            data = json.loads(output)
            if data.get('streams'):
                return data['streams'][0]['width'], data['streams'][0]['height']
        except json.JSONDecodeError:
            logger.warning(f"JSON decode error for {video_path}: {output}")
    logger.warning(f"Could not get dimensions for {video_path}. Using 1920x1080")
    return 1920, 1080

def convert_image(input_path, output_path, target_ratio=None, crop=False):
    try:
        with Image.open(input_path) as img:
            img = img.convert("RGB")
            width, height = img.size
            debug_print(f"Image {input_path} size: {width}x{height}")

            new_img = img.copy()
            if target_ratio == "9:16":
                target_aspect = 9 / 16
                original_aspect = width / height

                if abs(original_aspect - target_aspect) < 0.1:  # Close to 9:16, stretch proportionally
                    if original_aspect > target_aspect:
                        new_height = int(width * (16 / 9))
                        new_img = new_img.resize((width, new_height), Image.Resampling.LANCZOS)
                    else:
                        new_width = int(height * (9 / 16))
                        new_img = new_img.resize((new_width, height), Image.Resampling.LANCZOS)
                if crop:
                    if original_aspect > target_aspect:
                        new_width = int(height * (9 / 16))
                        left = (width - new_width) // 2
                        new_img = new_img.crop((left, 0, left + new_width, height))
                    else:
                        new_height = int(width * (16 / 9))
                        top = (height - new_height) // 2
                        new_img = new_img.crop((0, top, width, top + new_height))
                    new_img = new_img.resize((int(new_img.width * 540 / max(new_img.width, new_img.height * 9 / 16)), 540), Image.Resampling.LANCZOS)

            elif target_ratio == "1:1":
                target_aspect = 1
                original_aspect = width / height

                if abs(original_aspect - target_aspect) < 0.1:
                    if width > height:
                        new_height = width
                        new_img = new_img.resize((width, new_height), Image.Resampling.LANCZOS)
                    else:
                        new_width = height
                        new_img = new_img.resize((new_width, height), Image.Resampling.LANCZOS)
                if crop:
                    if width > height:
                        new_height = height
                        left = (width - height) // 2
                        new_img = new_img.crop((left, 0, left + new_height, height))
                    else:
                        new_width = width
                        top = (height - width) // 2
                        new_img = new_img.crop((0, top, new_width, top + new_width))
                    new_img = new_img.resize((max(new_img.width, new_img.height), max(new_img.width, new_img.height)), Image.Resampling.LANCZOS)

            else:
                new_img = img

            temp_output_path = output_path + ".tmp"
            new_img.save(temp_output_path, "JPEG", quality=100)
            os.replace(temp_output_path, output_path)
            debug_print(f"Converted {input_path} to {output_path} (Size: {new_img.size}) with ratio {target_ratio}")
            return True
    except Exception as e:
        logger.error(f"Image conversion error for {input_path}: {e}")
        if os.path.exists(temp_output_path):
            os.remove(temp_output_path)
            debug_print(f"Removed failed temp file: {temp_output_path}")
        return False

def convert_video(input_path, output_path, target_ratio=None, duration=None):
    ffmpeg_path = "ffmpeg"
    debug_print(f"Testing FFmpeg at {ffmpeg_path}")
    success, output = run_command(f'"{ffmpeg_path}" -version')
    if not success:
        debug_print(f"FFmpeg not found via PATH. Output: {output}")
        ffmpeg_path = r"C:\ffmpeg\bin\ffmpeg.exe"
        debug_print(f"Trying explicit path {ffmpeg_path}")
        success, output = run_command(f'"{ffmpeg_path}" -version')
        if not success:
            logger.error(f"FFmpeg not found at {ffmpeg_path}. Install or adjust path.")
            return False

    width, height = get_video_dimensions(input_path)
    debug_print(f"Video {input_path} size: {width}x{height}")

    duration_flag = f"-t {duration}" if duration is not None else ""
    if target_ratio == "9:16":
        temp_output_path = output_path + ".tmp"
        ffmpeg_command = (
            f'"{ffmpeg_path}" -y -i "{input_path}" -c:v libx264 -preset ultrafast -b:v 3500k '
            f'-vf "scale=540:960:force_original_aspect_ratio=decrease,pad=ceil(iw/2)*2:ceil(ih/2)*2:0:0" '
            f'-r 30 -c:a aac -b:a 128k -ar 44100 {duration_flag} -f mp4 "{temp_output_path}"'
        )
    else:
        temp_output_path = output_path + ".tmp"
        ffmpeg_command = (
            f'"{ffmpeg_path}" -y -i "{input_path}" -c:v libx264 -preset ultrafast -b:v 3500k '
            f'-r 30 -c:a aac -b:a 128k -ar 44100 {duration_flag} -f mp4 "{temp_output_path}"'
        )

    debug_print(f"Executing: {ffmpeg_command}")
    success, output = run_command(ffmpeg_command, retries=2)
    if success:
        out_width, out_height = get_video_dimensions(temp_output_path)
        debug_print(f"Output dimensions: {out_width}x{out_height}")
        os.replace(temp_output_path, output_path)
        debug_print(f"Saved as {output_path.replace(os.sep, '/')} (Target: 540x960 if 9:16)")
        return True
    else:
        logger.error(f"Conversion failed for {input_path}: {output}")
        if os.path.exists(temp_output_path):
            os.remove(temp_output_path)
            debug_print(f"Removed failed temp file: {temp_output_path}")
        return False

def get_files_recursive(directory, extensions):
    files = []
    input_dir = os.path.abspath(directory)  # Base directory for input
    for root, _, filenames in os.walk(directory):
        full_root = os.path.abspath(root)
        for filename in filenames:
            file_path = os.path.join(root, filename)
            abs_file_path = os.path.abspath(file_path)
            if any(filename.lower().endswith(ext) for ext in extensions):
                # Only include files directly under input_dir
                if abs_file_path.startswith(input_dir) and not any(abs_file_path.startswith(os.path.join(input_dir, subdir)) for subdir in ['converted_videos', 'converted_pictures', 'converted', 'converted_one_to_one', 'converted_nine_sixteen']):
                    files.append(file_path)
                    debug_print(f"Included file: {file_path}")
                else:
                    debug_print(f"Excluded file (in subdir): {file_path}")
        debug_print(f"Scanned {root}, found {len(filenames)} files, included {len(files)} valid files")
    try:
        return sorted(files, key=lambda x: int(re.match(r'O(\d+)\.', os.path.basename(x)).group(1)) if re.match(r'O(\d+)\.', os.path.basename(x)) else float('inf'))
    except Exception as e:
        debug_print(f"Sorting error: {e}. Falling back to alphabetical sort.")
        return sorted(files)

def get_next_available_name(output_dir, prefix, file_type, start_number=1, duration=None):
    number = start_number
    duration_suffix = f"_{duration}s" if duration is not None else "_full"
    while True:
        if file_type == "image":
            name = f"{prefix}_Pic_{number}.jpg"
        else:
            name = f"{prefix}_Uni_{number}{duration_suffix}.mp4"
        full_path = os.path.join(output_dir, name)
        debug_print(f"Checking output path: {full_path}")
        if not os.path.exists(full_path):
            debug_print(f"Available name: {full_path}")
            return name, full_path, number + 1
        number += 1

def log_conversion(input_path, output_path, output_dir, duration=None):
    log_file = os.path.join(output_dir, "conversion_log.json")
    entry = {
        "input_path": input_path,
        "output_path": output_path,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "duration": duration,
        "type": "image" if output_path.lower().endswith(".jpg") else "video"
    }
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            try:
                log_data = json.load(f)
            except json.JSONDecodeError:
                log_data = []
    else:
        log_data = []
    log_data.append(entry)
    with open(log_file, 'w') as f:
        json.dump(log_data, f, indent=4)

def get_existing_conversion(input_path, output_dir, prefix, file_type, duration=None):
    log_file = os.path.join(output_dir, "conversion_log.json")
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            try:
                log_data = json.load(f)
                for entry in log_data:
                    if entry["input_path"] == input_path and entry.get("duration") == duration and entry["type"] == file_type:
                        return entry["output_path"]
            except json.JSONDecodeError:
                logger.warning("Error reading conversion_log.json")
    return None

def main():
    parser = argparse.ArgumentParser(description="Convert videos and images to standard formats with prefix-based renaming")
    parser.add_argument("prefix", help="Prefix for output filenames (e.g., YanaSn0w1)")
    parser.add_argument("input_dirs", nargs='+', help="Input directories or files (e.g., convert_in)")
    parser.add_argument("--output-dir", default="convert_out", help="Output directory (default: convert_out)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--v", action="store_true", help="Process videos only")
    parser.add_argument("--p", action="store_true", help="Process images only")
    parser.add_argument("--one_to_one", action="store_true", help="Force 1:1 aspect ratio")
    parser.add_argument("--nine_sixteen", action="store_true", help="Force 9:16 aspect ratio")
    parser.add_argument("--crop", action="store_true", help="Crop images to fit target aspect ratio")
    parser.add_argument("--t", type=int, default=None, help="Limit output video duration in seconds (default: process entire video)")
    args = parser.parse_args()
    global DEBUG
    DEBUG = args.debug

    input_paths = args.input_dirs
    prefix = args.prefix
    output_dir = os.path.abspath(args.output_dir)

    # Comment out directory clearing to preserve existing files
    # for folder in ['converted_videos', 'converted_pictures', 'converted', 'converted_one_to_one', 'converted_nine_sixteen']:
    #     folder_path = os.path.join(output_dir, folder)
    #     if os.path.exists(folder_path):
    #         shutil.rmtree(folder_path, ignore_errors=True)
    #         debug_print(f"Removed existing folder: {folder_path}")

    video_extensions = ['.mp4', '.mkv', '.webm']
    image_extensions = ['.webp', '.png', '.jpg']
    extensions = video_extensions if args.v and not args.p else image_extensions if args.p and not args.v else video_extensions + image_extensions

    image_count = 1
    video_count = 1
    for input_path in input_paths:
        if not os.path.exists(input_path):
            logger.error(f"Path {input_path} does not exist")
            continue

        if os.path.isfile(input_path):
            files = [input_path] if any(input_path.lower().endswith(ext) for ext in extensions) else []
            logger.info(f"Processing file: {input_path}")
        else:
            files = get_files_recursive(input_path, extensions)
            if not files:
                logger.error(f"No files found in {input_path} with extensions {extensions}")
                continue
            logger.info(f"Processing directory: {input_path}")

        for i, file_path in enumerate(files, 1):
            logger.info(f"Checking {file_path} ({i}/{len(files)})")
            _, ext = os.path.splitext(file_path)
            is_video = file_path.lower().endswith(tuple(video_extensions))
            output_subdir = os.path.join(output_dir, "converted_videos" if is_video else "converted_pictures")
            os.makedirs(output_subdir, exist_ok=True)
            debug_print(f"Created output directory: {output_subdir}")

            file_type = "video" if is_video else "image"
            existing_output = get_existing_conversion(file_path, output_dir, prefix, file_type, duration=args.t)
            if existing_output and os.path.exists(existing_output):
                logger.info(f"Skipping {file_path}: already converted to {existing_output}")
                continue

            if not os.path.exists(file_path):
                logger.warning(f"Skipping {file_path}: source file does not exist")
                continue

            if is_video and (not args.p or args.v):
                name, output_path, video_count = get_next_available_name(output_subdir, prefix, "video", start_number=video_count, duration=args.t)
                logger.info(f"Attempting to convert video: {file_path}")
                success = convert_video(file_path, output_path, target_ratio="9:16" if args.nine_sixteen else "1:1" if args.one_to_one else None, duration=args.t)
                if success:
                    log_conversion(file_path, output_path, output_dir, duration=args.t)
                if not success:
                    logger.error(f"Failed to convert video: {file_path}")
            elif not is_video and (not args.v or args.p):
                name, output_path, image_count = get_next_available_name(output_subdir, prefix, "image", start_number=image_count, duration=None)
                logger.info(f"Attempting to convert image: {file_path}")
                success = convert_image(file_path, output_path, target_ratio="9:16" if args.nine_sixteen else "1:1" if args.one_to_one else None, crop=args.crop)
                if success:
                    log_conversion(file_path, output_path, output_dir, duration=None)
                if not success:
                    logger.error(f"Failed to convert image: {file_path}")

if __name__ == "__main__":
    main()
