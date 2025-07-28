import subprocess
import sys
import os
import argparse
import glob
import re
import time
from PIL import Image
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

def get_next_available_name(output_dir, start_number=1):
    number = start_number
    while True:
        name = f"S_{number}{'.mp4'}"
        full_path = os.path.join(output_dir, name)
        if not os.path.exists(full_path):
            return name, full_path, number + 1
        number += 1

def get_image_dimensions(image_path):
    try:
        with Image.open(image_path) as img:
            return img.size
    except Exception:
        print(f"Warning: Could not get dimensions for {image_path}. Using 1080x1080")
        return 1080, 1080

def find_image_file(image_path):
    extensions = ['.jpg', '.jpeg', '.png', '.webp']
    image_path = os.path.abspath(image_path)
    debug_print(f"Image path: {image_path}")
    base_name = os.path.basename(image_path)
    parts = base_name.split('.')
    if len(parts) > 1:
        last_ext = '.' + parts[-1].lower()
        if last_ext in extensions and os.path.exists(image_path):
            debug_print(f"Found image: {image_path}")
            return image_path
        if len(parts) > 2:
            adjusted_name = '.'.join(parts[:-1] + [parts[-1]])
            adjusted_path = os.path.join(os.path.dirname(image_path), adjusted_name)
            if os.path.exists(adjusted_path):
                debug_print(f"Adjusted image: {adjusted_path}")
                return adjusted_path
    directory = os.path.dirname(image_path) or os.path.abspath(".")
    base_name = os.path.splitext(base_name)[0].lower()
    debug_print(f"Searching for image '{base_name}' in '{directory}'")
    if not os.path.isdir(directory):
        debug_print(f"Directory does not exist: {directory}")
        return None
    try:
        matched_files = []
        for file in os.listdir(directory):
            file_lower = file.lower()
            file_base, file_ext = os.path.splitext(file_lower)
            if file_base == base_name and file_ext in extensions:
                matched_files.append(os.path.join(directory, file))
        if not matched_files:
            debug_print(f"No image found for '{base_name}' in '{directory}'")
            return None
        for ext in extensions:
            for match in matched_files:
                if match.lower().endswith(ext):
                    if len(matched_files) > 1 and DEBUG:
                        print(f"Warning: Multiple images found for '{base_name}': {matched_files}. Using '{match}'")
                    debug_print(f"Found image: {match}")
                    return match
        debug_print(f"Fallback image: {matched_files[0]}")
        return matched_files[0]
    except Exception as e:
        print(f"Error accessing directory {directory}: {e}")
        return None

def determine_best_resolution(file_paths):
    dimensions = [get_image_dimensions(file) for file in file_paths]
    if not dimensions:
        print("Error: No valid dimensions found. Using 1920x1080")
        return 1920, 1080
    aspect_ratios = [w/h for w, h in dimensions]
    counts = {'landscape': 0, 'portrait': 0, 'square': 0}
    for ar in aspect_ratios:
        if ar > 1.5:
            counts['landscape'] += 1
        elif ar < 0.67:
            counts['portrait'] += 1
        else:
            counts['square'] += 1
    dominant = max(counts, key=counts.get)
    if dominant == 'landscape':
        target_width, target_height = 1920, 1080
    elif dominant == 'portrait':
        target_width, target_height = 1080, 1920
    else:
        target_width, target_height = 1080, 1080
    return target_width + (target_width % 2), target_height + (target_height % 2)

def parse_image_names(names, folder_path):
    if not names:
        extensions = ['*.jpg', '*.jpeg', '*.png', '*.webp']
        files = []
        for ext in extensions:
            files.extend(glob.glob(os.path.join(folder_path, ext)))
        if not files:
            print(f"Error: No images found in {folder_path}")
            sys.exit(1)
        def get_number(file):
            match = re.search(r'(\d+)', os.path.splitext(os.path.basename(file))[0])
            return int(match.group(1)) if match else float('inf')
        files = sorted(files, key=get_number)
        names = [os.path.splitext(os.path.basename(file))[0] for file in files]
        debug_print(f"Sorted image files: {files}")
        return names
    if len(names) == 1:
        name = names[0]
        range_match = re.match(r'^([A-Za-z]+)(\d+)-([A-Za-z]+)(\d+)$', name)
        if range_match:
            prefix1, start, prefix2, end = range_match.groups()
            if prefix1 == prefix2 and start.isdigit() and end.isdigit():
                start, end = int(start), int(end)
                if start <= end:
                    return [f"{prefix1}{i}" for i in range(start, end + 1)]
                print(f"Error: Invalid range {name}: Start > End")
                sys.exit(1)
            print(f"Error: Invalid range format {name}")
            sys.exit(1)
        if '*' in name:
            pattern = os.path.join(folder_path, name + '.*')
            files = glob.glob(pattern)
            if not files:
                print(f"Error: No images found for {name} in {folder_path}")
                sys.exit(1)
            def get_number(file):
                match = re.search(r'(\d+)', os.path.splitext(os.path.basename(file))[0])
                return int(match.group(1)) if match else float('inf')
            files = sorted(files, key=get_number)
            names = [os.path.splitext(os.path.basename(file))[0] for file in files]
            debug_print(f"Wildcard matched image files: {files}")
            return names
    def get_number(name):
        match = re.search(r'(\d+)', name)
        return int(match.group(1)) if match else float('inf')
    names = sorted(names, key=get_number)
    debug_print(f"Sorted image names: {names}")
    return names

def main():
    global DEBUG
    parser = argparse.ArgumentParser(description="Create slideshow from images")
    parser.add_argument("duration", type=float, help="Duration per image in seconds")
    parser.add_argument("folder_path", help="Folder containing images")
    parser.add_argument("image_names", nargs='*', help="Image names or range")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--keep-original-resolution", action="store_true", help="Keep original image resolution")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()
    DEBUG = args.debug

    duration = args.duration
    folder_path = args.folder_path
    image_names = args.image_names
    output_dir = args.output_dir or os.path.abspath(folder_path)
    keep_original_resolution = args.keep_original_resolution
    if not os.path.isdir(folder_path):
        print(f"Error: Directory does not exist: {folder_path}")
        sys.exit(1)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    image_names = parse_image_names(image_names, folder_path)
    image_paths = [os.path.join(folder_path, name) for name in image_names]
    actual_paths = []
    for image_path in image_paths:
        actual_image = find_image_file(image_path)
        if not actual_image or not os.path.exists(actual_image):
            print(f"Error: No image found: {image_path}")
            sys.exit(1)
        debug_print(f"Image {image_path} resolved to {actual_image}")
        actual_paths.append(actual_image)
    if not actual_paths:
        print(f"No images found in {folder_path}")
        sys.exit(1)
    debug_print(f"Found {len(actual_paths)} images")
    target_width, target_height = determine_best_resolution(actual_paths)
    debug_print(f"Target resolution: {target_width}x{target_height}")
    temp_dir = os.path.abspath(os.path.join(".", "temp"))
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    try:
        for i, image_path in enumerate(actual_paths, 1):
            name, output_path, next_number = get_next_available_name(output_dir, start_number=i)
            debug_print(f"Processing image {image_path} to {output_path}")
            if keep_original_resolution:
                width, height = get_image_dimensions(image_path)
                width += width % 2
                height += height % 2
                ffmpeg_command = (
                    f'ffmpeg -y -loop 1 -i "{image_path}" '
                    f'-c:v libx264 -preset fast -b:v 3500k -r 30 -pix_fmt yuv420p '
                    f'-vf "scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2" '
                    f'-t {duration} "{output_path}"'
                )
            else:
                ffmpeg_command = (
                    f'ffmpeg -y -loop 1 -i "{image_path}" '
                    f'-c:v libx264 -preset fast -b:v 3500k -r 30 -pix_fmt yuv420p '
                    f'-vf "scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2" '
                    f'-t {duration} "{output_path}"'
                )
            debug_print(f"FFmpeg command: {ffmpeg_command}")
            success, output = run_command(ffmpeg_command)
            if success and os.path.exists(output_path):
                print(f"Saved Slide {i} as {output_path.replace(os.sep, '/')}")
            else:
                print(f"Failed to process image {image_path} into video")
                debug_print(f"FFmpeg output: {output}")
                sys.exit(1)
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    main()
