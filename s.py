import subprocess
import sys
import os
import argparse
import glob
import shutil
import json
import urllib.parse
import re
import time
import signal

def run_command(command, suppress_errors=False, timeout=None, retries=1):
    """Run a shell command with real-time output, optional timeout, and retries."""
    attempt = 0
    while attempt <= retries:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        output = []
        start_time = time.time()

        try:
            for line in process.stdout:
                if not suppress_errors:
                    print(line, end='')
                output.append(line)
                if timeout and (time.time() - start_time) > timeout:
                    process.send_signal(signal.SIGTERM)
                    time.sleep(1)
                    if process.poll() is None:
                        process.kill()
                    raise TimeoutError(f"Command timed out after {timeout} seconds")

            process.stdout.close()
            return_code = process.wait()

            if return_code != 0:
                if not suppress_errors:
                    if "Command timed out" not in ''.join(output):
                        print(f"Error: Command failed with return code {return_code}")
                return False, ''.join(output)
            return True, ''.join(output)

        except TimeoutError as e:
            attempt += 1
            if attempt <= retries:
                print(f"Timeout: {e}. Retrying ({attempt}/{retries})...")
                time.sleep(5)
                continue
            else:
                print(f"Timeout: {e}. No more retries left.")
                return False, str(e)
        except Exception as e:
            print(f"Unexpected error: {e}")
            return False, str(e)
        finally:
            if process.poll() is None:
                process.terminate()

def sanitize_filename(filename):
    """Sanitize a string to be a valid filename."""
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '_', filename)
    sanitized = re.sub(r'\s+', '_', sanitized.strip())
    sanitized = sanitized.lstrip('._')
    sanitized = sanitized[:200]
    return sanitized

def get_next_available_name(output_dir, prefix, extension, title=None, start_num=1, force_num=False):
    """Generate the next available filename."""
    if title:
        sanitized_title = sanitize_filename(title)
        num = start_num
        while True:
            name = f"{prefix}_{num}_{sanitized_title}{extension}"
            full_path = os.path.join(output_dir, name)
            if not os.path.exists(full_path):
                base_name = f"{prefix}_{num}_{sanitized_title}"
                return name, base_name, num + 1
            num += 1
    else:
        num = start_num
        while True:
            name = f"{prefix}{num}{extension}"
            full_path = os.path.join(output_dir, name)
            if force_num:
                return name, f"{prefix}{num}", num
            if not os.path.exists(full_path):
                return name, f"{prefix}{num}", num
            num += 1

def get_file_duration(file_path):
    cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{file_path}"'
    success, output = run_command(cmd)
    if success:
        try:
            return float(output.strip())
        except ValueError:
            print(f"Warning: Could not determine duration of {file_path}")
            return 0
    return 0

def get_file_size(file_path):
    try:
        size_bytes = os.path.getsize(file_path)
        return size_bytes / (1024 * 1024)
    except Exception as e:
        print(f"Warning: Could not determine file size of {file_path}: {e}")
        return 0

def has_audio_stream(file_path):
    cmd = f'ffprobe -v error -show_streams -select_streams a -of default=noprint_wrappers=1 "{file_path}"'
    success, output = run_command(cmd)
    return bool(output.strip())

def has_video_stream(file_path):
    cmd = f'ffprobe -v error -show_streams -select_streams v -of default=noprint_wrappers=1 "{file_path}"'
    success, output = run_command(cmd)
    return bool(output.strip())

def get_image_dimensions(image_path):
    cmd = f'ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of json "{image_path}"'
    success, output = run_command(cmd)
    if success:
        data = json.loads(output)
        width = data['streams'][0]['width']
        height = data['streams'][0]['height']
        return width, height
    return None, None

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

def find_image_file(image_path):
    extensions = ['.jpg', '.jpeg', '.png', '.webp', '.JPG', '.JPEG', '.PNG', '.WEBP']
    base_name = os.path.basename(image_path).lower()
    dir_name = os.path.abspath(os.path.dirname(image_path) or ".")
    
    try:
        for file in os.listdir(dir_name):
            file_lower = file.lower()
            if file_lower.startswith(base_name) and os.path.splitext(file_lower)[1] in [ext.lower() for ext in extensions]:
                return os.path.join(dir_name, file)
    except Exception as e:
        print(f"Error accessing directory {dir_name}: {e}")
    return None

def find_video_file(video_path):
    extensions = ['.mp4', '.MP4']
    base_name = os.path.basename(video_path).lower()
    dir_name = os.path.abspath(os.path.dirname(video_path) or ".")
    
    try:
        for file in os.listdir(dir_name):
            file_lower = file.lower()
            if file_lower.startswith(base_name) and os.path.splitext(file_lower)[1] in [ext.lower() for ext in extensions]:
                return os.path.join(dir_name, file)
    except Exception as e:
        print(f"Error accessing directory {dir_name}: {e}")
    return None

def determine_best_resolution(image_files):
    dimensions = []
    for image_file in image_files:
        width, height = get_image_dimensions(image_file)
        if width is None or height is None:
            print(f"Warning: Could not determine dimensions of {image_file}. Skipping.")
            continue
        dimensions.append((width, height))

    if not dimensions:
        print("Error: Could not determine dimensions of any image. Using default 1920x1080.")
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
        target_aspect = 16/9
        default_width, default_height = 1920, 1080
    elif dominant_category == 'portrait':
        target_aspect = 9/16
        default_width, default_height = 1080, 1920
    else:
        target_aspect = 1
        default_width, default_height = 1080, 1080

    max_width = 0
    max_height = 0
    for width, height in dimensions:
        current_aspect = width / height
        if current_aspect > target_aspect:
            scaled_height = height
            scaled_width = int(scaled_height * target_aspect)
        else:
            scaled_width = width
            scaled_height = int(scaled_width / target_aspect)
        max_width = max(max_width, scaled_width)
        max_height = max(max_height, scaled_height)

    max_width = max_width + (max_width % 2)
    max_height = max_height + (max_height % 2)

    if max_width < 640 or max_height < 360:
        return default_width, default_height

    return max_width, max_height

def is_video_platform(url):
    video_domains = ['youtube.com', 'youtu.be', 'tiktok.com', 'vimeo.com', 'dailymotion.com', 'x.com', 'twitter.com']
    parsed_url = urllib.parse.urlparse(url)
    domain = parsed_url.netloc.lower()
    return any(video_domain in domain for video_domain in video_domains)

def is_image_platform(url):
    image_domains = ['instagram.com', 'flickr.com', 'pinterest.com', 'imgur.com']
    parsed_url = urllib.parse.urlparse(url)
    domain = parsed_url.netloc.lower()
    return any(image_domain in domain for image_domain in image_domains)

def main():
    parser = argparse.ArgumentParser(description="Download, process, combine, create slideshows, or batch convert media files")
    subparsers = parser.add_subparsers(dest="mode", help="Mode of operation")

    parser_download = subparsers.add_parser("download", help="Download and process videos/images")
    parser_download.add_argument("submode", choices=["audio", "video", "combined", "split", "pic", "all", "all+a", "all+a+v", "all+v", "full"],
                                 help="Submode: 'audio', 'video', 'combined', 'split', 'pic', 'all', 'all+a', 'all+a+v', 'all+v', or 'full'")
    parser_download.add_argument("--output-dir", "-o", default=".",
                                 help="Directory to save output files (default: current directory)")
    parser_download.add_argument("--keep-original", action="store_true",
                                 help="Keep the original format (skip FFmpeg conversion)")
    parser_download.add_argument("--clear-dir", action="store_true",
                                 help="Clear the output directory before starting downloads")
    parser_download.add_argument("--username", help="Username for yt-dlp authentication")
    parser_download.add_argument("--password", help="Password for yt-dlp authentication")
    parser_download.add_argument("--cookies", help="Path to cookies file for yt-dlp authentication")
    parser_download.add_argument("--duration", type=float, help="Limit the output video to the first X seconds")

    parser_combine = subparsers.add_parser("combine", help="Combine existing video and audio files")
    parser_combine.add_argument("video_path", help="Path to the video file (e.g., ./videos/V1 for V1.mp4)")
    parser_combine.add_argument("audio_path", help="Path to the audio file (e.g., ./audio/A1 for A1.m4a)")
    parser_combine.add_argument("--output-dir", "-o",
                                help="Directory where output will be saved (default: same as video file directory)")

    parser_split = subparsers.add_parser("split", help="Split an existing video file into video and audio")
    parser_split.add_argument("input_path", help="Path to the input video file (e.g., ./videos/O11 for O11.mp4)")
    parser_split.add_argument("--output-dir", "-o",
                              help="Directory where output will be saved (default: same as input file directory)")

    parser_slide = subparsers.add_parser("slide", help="Create a slideshow video from images")
    parser_slide.add_argument("delay", type=float, help="Delay in seconds for each image")
    parser_slide.add_argument("image_paths", nargs='+', help="Paths to image files")
    parser_slide.add_argument("--output-dir", "-o",
                              help="Directory where output will be saved (default: same as first image directory)")

    parser_loop = subparsers.add_parser("loop", help="Loop an audio file to a specified duration")
    parser_loop.add_argument("audio_path", help="Path to the audio file (e.g., ./audio/A1 for A1.m4a)")
    parser_loop.add_argument("duration", type=float, help="Desired duration in seconds")
    parser_loop.add_argument("--output-dir", "-o",
                             help="Directory where output will be saved (default: same as audio file directory)")

    parser_trim = subparsers.add_parser("trim", help="Trim audio from a video between start and end times")
    parser_trim.add_argument("video_path", help="Path to the video file (e.g., ./videos/U1 for U1.mp4)")
    parser_trim.add_argument("--start", type=float, default=0, help="Start time in seconds (default: 0)")
    parser_trim.add_argument("--end", type=float, required=True, help="End time in seconds")
    parser_trim.add_argument("--output-dir", "-o",
                             help="Directory where output will be saved (default: same as video file directory)")

    parser_trim_loop = subparsers.add_parser("trim_loop", help="Trim audio from a video and loop it to a specified duration")
    parser_trim_loop.add_argument("video_path", help="Path to the video file (e.g., ./videos/U1 for U1.mp4)")
    parser_trim_loop.add_argument("--start", type=float, default=0, help="Start time in seconds (default: 0)")
    parser_trim_loop.add_argument("--end", type=float, required=True, help="End time in seconds")
    parser_trim_loop.add_argument("--duration", type=float, required=True, help="Desired output duration in seconds")
    parser_trim_loop.add_argument("--output-dir", "-o",
                                  help="Directory where output will be saved (default: same as video file directory)")

    parser_batch_convert = subparsers.add_parser("batch_convert", help="Convert existing videos to Universal format")
    parser_batch_convert.add_argument("input_dir", help="Directory containing input video files")
    parser_batch_convert.add_argument("--output-dir", "-o", default=".",
                                     help="Directory to save converted files (default: current directory)")

    args = parser.parse_args()
    mode = args.mode

    if mode == "batch_convert":
        input_dir = os.path.abspath(args.input_dir)
        output_dir = os.path.abspath(args.output_dir if args.output_dir else input_dir)

        if not os.path.exists(input_dir):
            print(f"Error: Input directory {input_dir} does not exist.")
            sys.exit(1)

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")

        video_files = glob.glob(os.path.join(input_dir, "*.mp4")) + glob.glob(os.path.join(input_dir, "*.mkv"))
        if not video_files:
            print(f"Error: No .mp4 or .mkv files found in {input_dir}.")
            sys.exit(1)

        print(f"Found {len(video_files)} video files to convert.")

        current_u_number = 1
        for video_file in video_files:
            print(f"\nConverting {video_file}...")
            width, height = get_video_dimensions(video_file)
            width = width + (width % 2)
            height = height + (height % 2)
            aspect_ratio = width / height
            if aspect_ratio > 1.5:
                target_width, target_height = min(width, 1920), min(height, 1080)
            elif aspect_ratio < 0.67:
                target_width, target_height = min(width, 1080), min(height, 1920)
            else:
                target_width, target_height = min(width, 1080), min(height, 1080)
            target_width = target_width + (target_width % 2)
            target_height = target_height + (target_height % 2)

            output_name_with_ext, output_name_base, current_u_number = get_next_available_name(
                output_dir, "U", ".mp4", start_num=current_u_number
            )
            output_path = os.path.join(output_dir, output_name_with_ext)

            ffmpeg_cmd = (
                f'ffmpeg -i "{video_file}" -c:v libx264 -preset ultrafast -b:v 3500k '
                f'-vf "scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2" -r 30 '
                f'-c:a aac -b:a 128k -ar 44100 -t 140 "{output_path}"'
            )
            success, output = run_command(ffmpeg_cmd)
            if success:
                print(f"Saved Universal as {output_path}")
            else:
                print(f"Failed to convert {video_file}")

        print(f"Done! Converted files saved in {output_dir}")
        return

    if mode == "slide":
        delay = args.delay
        image_paths = args.image_paths
        output_dir = args.output_dir if args.output_dir else os.path.dirname(image_paths[0])

        image_files = []
        for image_path in image_paths:
            image_file = find_image_file(image_path)
            if not image_file:
                extensions = ['.jpg', '.jpeg', '.png', '.webp']
                dir_name = os.path.abspath(os.path.dirname(image_path) or ".")
                base_name = os.path.basename(image_path)
                print(f"Error: Image file {image_path} not found.")
                sys.exit(1)
            image_files.append(image_file)

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")

        target_width, target_height = determine_best_resolution(image_files)
        print(f"Using resolution {target_width}x{target_height} for the slideshow.")

        temp_image_dir = os.path.join(output_dir, "temp_slideshow")
        if os.path.exists(temp_image_dir):
            shutil.rmtree(temp_image_dir)
        os.makedirs(temp_image_dir)

        try:
            for i, image_file in enumerate(image_files):
                temp_image = os.path.join(temp_image_dir, f"image_{i:03d}.jpg")
                ffmpeg_cmd = (
                    f'ffmpeg -i "{image_file}" -vf "scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2" "{temp_image}"'
                )
                success, output = run_command(ffmpeg_cmd)
                if not success:
                    print(f"Failed to process image {image_file}")
                    sys.exit(1)

            concat_list = os.path.join(temp_image_dir, "concat_list.txt")
            with open(concat_list, "w") as f:
                for i in range(len(image_files)):
                    f.write(f"file 'image_{i:03d}.jpg'\n")
                    f.write(f"duration {delay}\n")

            output_name_with_ext, output_name_base = get_next_available_name(output_dir, "S", ".mp4")[:2]
            output_name = os.path.join(output_dir, output_name_base)
            print(f"Creating slideshow video: {output_name_with_ext}")

            ffmpeg_cmd = (
                f'ffmpeg -f concat -safe 0 -i "{concat_list}" -c:v libx264 -preset ultrafast -b:v 3500k -r 30 -pix_fmt yuv420p "{output_name}.mp4"'
            )
            success, output = run_command(ffmpeg_cmd)
            if not success:
                print(f"Failed to create slideshow video")
                sys.exit(1)

            print(f"Done! Output saved in {output_dir}")

        finally:
            if os.path.exists(temp_image_dir):
                shutil.rmtree(temp_image_dir)

        return

    if mode == "loop":
        audio_path = args.audio_path + ".m4a"
        duration = args.duration
        output_dir = args.output_dir if args.output_dir else os.path.dirname(audio_path)

        if not os.path.exists(audio_path):
            print(f"Error: Audio file {audio_path} not found.")
            sys.exit(1)

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")

        audio_duration = get_file_duration(audio_path)
        loop = int(duration / audio_duration) + 1 if audio_duration < duration else 0
        print(f"Looping audio to {duration} seconds ({loop} loops).")

        output_name_with_ext, output_name_base = get_next_available_name(output_dir, "L", ".m4a")[:2]
        output_name = os.path.join(output_dir, output_name_base)
        print(f"Output will be saved as {output_name_with_ext}")

        ffmpeg_cmd = (
            f'ffmpeg -stream_loop {loop} -i "{audio_path}" -c:a aac -b:a 128k -t {duration} "{output_name}.m4a"'
        )
        success, output = run_command(ffmpeg_cmd)
        if not success:
            print(f"Failed to loop audio")
            sys.exit(1)

        print(f"Done! Output saved in {output_dir}")
        return

    if mode == "combine":
        video_path = args.video_path + ".mp4"
        audio_path = args.audio_path + ".m4a"
        output_dir = args.output_dir if args.output_dir else os.path.dirname(video_path)

        if not os.path.exists(video_path):
            print(f"Error: Video file {video_path} not found.")
            sys.exit(1)
        if not os.path.exists(audio_path):
            print(f"Error: Audio file {audio_path} not found.")
            sys.exit(1)

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")

        video_duration = get_file_duration(video_path)
        audio_duration = get_file_duration(audio_path)
        loop = int(video_duration / audio_duration) + 1 if audio_duration < video_duration else 0

        output_name_with_ext, output_name_base = get_next_available_name(output_dir, "C", ".mp4")[:2]
        output_name = os.path.join(output_dir, output_name_base)
        print(f"Combining video and audio: {output_name_with_ext}")

        ffmpeg_cmd = (
            f'ffmpeg -i "{video_path}" -stream_loop {loop} -i "{audio_path}" '
            f'-c:v libx264 -preset ultrafast -b:v 3500k -r 30 -pix_fmt yuv420p '
            f'-c:a aac -b:a 128k -ar 44100 -shortest -t {video_duration if video_duration > 0 else 140} "{output_name}.mp4"'
        )
        success, output = run_command(ffmpeg_cmd)
        if not success:
            print(f"Failed to combine files")
            sys.exit(1)

        print(f"Done! Output saved in {output_dir}")
        return

    if mode == "split":
        input_path = args.input_path + ".mp4"
        output_dir = args.output_dir if args.output_dir else os.path.dirname(input_path)

        actual_input_path = find_video_file(args.input_path)
        if not actual_input_path:
            print(f"Error: Input file {input_path} not found.")
            sys.exit(1)

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")

        has_audio = has_audio_stream(actual_input_path)

        video_name_with_ext, video_name_base = get_next_available_name(output_dir, "V", ".mp4")[:2]
        audio_name_with_ext, audio_name_base = get_next_available_name(output_dir, "A", ".m4a")[:2]
        video_output = os.path.join(output_dir, video_name_base)
        audio_output = os.path.join(output_dir, audio_name_base)

        print(f"Splitting {actual_input_path}...")

        ffmpeg_video_cmd = (
            f'ffmpeg -i "{actual_input_path}" -c:v copy -an "{video_output}.mp4"'
        )
        success, output = run_command(ffmpeg_video_cmd)
        if not success:
            print(f"Failed to extract video")
            sys.exit(1)

        if has_audio:
            ffmpeg_audio_cmd = (
                f'ffmpeg -i "{actual_input_path}" -vn -c:a aac -b:a 128k "{audio_output}.m4a"'
            )
            success, output = run_command(ffmpeg_audio_cmd)
            if not success:
                print(f"Failed to extract audio")
                if os.path.exists(f"{video_output}.mp4"):
                    os.remove(f"{video_output}.mp4")
                sys.exit(1)
        else:
            print("No audio stream found in the input file.")

        print(f"Done! Output(s) saved in {output_dir}")
        return

    if mode == "trim":
        video_path = args.video_path + ".mp4"
        output_dir = args.output_dir if args.output_dir else os.path.dirname(video_path)
        start_time = args.start
        end_time = args.end

        actual_video_path = find_video_file(args.video_path)
        if not actual_video_path:
            print(f"Error: Video file {video_path} not found.")
            sys.exit(1)

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")

        if not has_audio_stream(actual_video_path):
            print(f"Error: No audio stream found in {actual_video_path}.")
            sys.exit(1)

        video_duration = get_file_duration(actual_video_path)
        if video_duration == 0:
            print("Error: Could not determine video duration.")
            sys.exit(1)

        if end_time <= start_time or end_time > video_duration:
            print(f"Error: Invalid time range (start: {start_time}, end: {end_time}, duration: {video_duration}).")
            sys.exit(1)

        trim_duration = end_time - start_time
        print(f"Trimming audio from {start_time} to {end_time} seconds.")

        output_name_with_ext, output_name_base = get_next_available_name(output_dir, "T", ".m4a")[:2]
        output_name = os.path.join(output_dir, output_name_base)
        print(f"Output will be saved as {output_name_with_ext}")

        ffmpeg_cmd = (
            f'ffmpeg -i "{actual_video_path}" -vn -ss {start_time} -t {trim_duration} -c:a aac -b:a 128k "{output_name}.m4a"'
        )
        success, output = run_command(ffmpeg_cmd)
        if not success:
            print(f"Failed to trim audio")
            sys.exit(1)

        if has_video_stream(f"{output_name}.m4a"):
            print(f"Error: Output contains a video stream.")
            if os.path.exists(f"{output_name}.m4a"):
                os.remove(f"{output_name}.m4a")
            sys.exit(1)

        print(f"Done! Output saved in {output_dir}")
        return

    if mode == "trim_loop":
        video_path = args.video_path + ".mp4"
        output_dir = args.output_dir if args.output_dir else os.path.dirname(video_path)
        start_time = args.start
        end_time = args.end
        desired_duration = args.duration

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")

        actual_video_path = find_video_file(args.video_path)
        if not actual_video_path:
            print(f"Error: Video file {video_path} not found.")
            sys.exit(1)

        if not has_audio_stream(actual_video_path):
            print(f"Error: No audio stream found in {actual_video_path}.")
            sys.exit(1)

        video_duration = get_file_duration(actual_video_path)
        if video_duration == 0:
            print("Error: Could not determine video duration.")
            sys.exit(1)

        if end_time <= start_time or end_time > video_duration:
            print(f"Error: Invalid time range (start: {start_time}, end: {end_time}, duration: {video_duration}).")
            sys.exit(1)

        if desired_duration <= 0:
            print(f"Error: Desired duration ({desired_duration}) must be greater than 0.")
            sys.exit(1)

        trim_duration = end_time - start_time
        loop = int(desired_duration / trim_duration) if trim_duration < desired_duration else 0
        print(f"Trimming audio from {start_time} to {end_time} seconds, looping {loop} times to reach {desired_duration} seconds.")

        output_name_with_ext, output_name_base = get_next_available_name(output_dir, "TL", ".m4a")[:2]
        output_name = os.path.join(output_dir, output_name_base)
        output_path = os.path.join(output_dir, output_name_with_ext)
        temp_audio_path = os.path.join(output_dir, "temp_trimmed_audio.m4a")
        print(f"Output will be saved as {output_name_with_ext}")

        ffmpeg_trim_cmd = (
            f'ffmpeg -y -i "{actual_video_path}" -vn -ss {start_time} -t {trim_duration} '
            f'-c:a aac -b:a 128k "{temp_audio_path}"'
        )
        success, output = run_command(ffmpeg_trim_cmd)
        if not success:
            print(f"Failed to extract trimmed audio")
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
            sys.exit(1)

        trimmed_duration = get_file_duration(temp_audio_path)
        if trimmed_duration < trim_duration - 0.1 or trimmed_duration > trim_duration + 0.1:
            print(f"Error: Trimmed audio duration ({trimmed_duration}s) does not match expected ({trim_duration}s).")
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
            sys.exit(1)

        ffmpeg_loop_cmd = (
            f'ffmpeg -y -stream_loop {loop} -i "{temp_audio_path}" '
            f'-c:a copy -t {desired_duration} "{output_path}"'
        )
        success, output = run_command(ffmpeg_loop_cmd)
        if not success:
            print(f"Failed to loop trimmed audio")
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
            sys.exit(1)

        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

        if has_video_stream(output_path):
            print(f"Error: Final output contains a video stream.")
            if os.path.exists(output_path):
                os.remove(output_path)
            sys.exit(1)

        final_duration = get_file_duration(output_path)
        if final_duration < desired_duration - 0.1 or final_duration > desired_duration + 0.1:
            print(f"Error: Final output duration ({final_duration}s) does not match desired ({desired_duration}s).")
            if os.path.exists(output_path):
                os.remove(output_path)
            sys.exit(1)

        print(f"Done! Output saved in {output_dir}")
        return

    # Download mode
    submode = args.submode
    output_dir = args.output_dir
    keep_original = args.keep_original
    clear_dir = args.clear_dir
    username = args.username
    password = args.password
    cookies = args.cookies
    duration_limit = args.duration

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")
    elif clear_dir:
        print(f"Clearing output directory: {output_dir}")
        for file in glob.glob(os.path.join(output_dir, "*")):
            if os.path.isfile(file):
                os.remove(file)
            elif os.path.isdir(file):
                shutil.rmtree(file)

    url_file = "urls.txt"
    if not os.path.exists(url_file):
        print(f"Error: {url_file} not found. Create a file with URLs.")
        sys.exit(1)

    urls = []
    with open(url_file, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                line_urls = [url.strip() for url in line.split(";") if url.strip()]
                urls.extend(line_urls)

    if not urls:
        print(f"Error: {url_file} is empty.")
        sys.exit(1)

    unique_urls = list(dict.fromkeys(urls))
    if len(unique_urls) < len(urls):
        print(f"Removed {len(urls) - len(unique_urls)} duplicate URLs.")

    temp_file = os.path.join(output_dir, "temp_download.mp4")
    temp_audio_file = os.path.join(output_dir, "temp_audio.m4a")
    temp_image_dir = os.path.join(output_dir, "temp_images")

    current_v_number = 1
    current_o_number = 1
    current_a_number = 1
    current_p_number = 1
    audio_counter = 1

    processed_urls = {}

    for index, url in enumerate(unique_urls):
        if submode == "all":
            print(f"\nProcessing: {index + 1}/{len(unique_urls)}")
            print(f"Checking link for content: {url}")
        else:
            print(f"\nProcessing {submode} {index + 1}/{len(unique_urls)}: {url}")

        if url not in processed_urls:
            processed_urls[url] = []

        video_downloaded_path = None

        if os.path.exists(temp_file):
            os.remove(temp_file)
        if os.path.exists(temp_audio_file):
            os.remove(temp_audio_file)
        if os.path.exists(temp_image_dir):
            shutil.rmtree(temp_image_dir)

        try:
            if submode == "audio":
                prefix = "A"
                extension = ".m4a"
            elif submode == "video":
                prefix = "V"
                extension = ".mp4"
            elif submode == "pic":
                prefix = "P"
                extension = ".jpg"
            elif submode in ["combined", "full"]:
                prefix = "O" if keep_original else "U"
                extension = ".mp4"
            elif submode == "split":
                prefix = "O" if keep_original else "U"
                extension = "_video.mp4"
            elif submode in ["all", "all+a", "all+a+v", "all+v"]:
                prefix = None
                extension = None
            else:
                pass

            if submode not in ["all", "all+a", "all+a+v", "all+v"]:
                output_name_with_ext, output_name_base = get_next_available_name(output_dir, prefix, extension)[:2]
                output_name = os.path.join(output_dir, output_name_base)

            if submode in ["audio", "video", "combined", "full", "pic"]:
                print(f"Output will be saved as {output_name_with_ext}")
            elif submode == "split":
                print(f"Outputs will be saved as {output_name}_video.mp4 and {output_name}_audio.m4a")
            elif submode not in ["all", "all+a", "all+a+v", "all+v"]:
                print("Checking for content...")

            if username and password:
                auth = f"--username {username} --password {password}"
            elif cookies:
                auth = f"--cookies {cookies}"
            else:
                auth = "--cookies-from-browser firefox"

            if submode == "full":
                output_name_with_ext, output_name_base, current_o_number = get_next_available_name(
                    output_dir, "O", ".mp4", start_num=current_o_number
                )
                output_path = os.path.join(output_dir, output_name_with_ext)
                print(f"Downloading full video: {output_name_with_ext}")
                duration_option = f'--download-sections "*0-{duration_limit}"' if duration_limit else ""
                yt_dlp_cmd = (
                    f'yt-dlp {auth} -f "bestvideo+bestaudio/best" --merge-output-format mp4 '
                    f'{duration_option} -o "{temp_file}" "{url}"'
                )
                success, output = run_command(yt_dlp_cmd, suppress_errors=True, timeout=300, retries=1)
                if not success or not os.path.exists(temp_file):
                    print(f"Failed to download: {url}")
                    continue

                os.rename(temp_file, output_path)
                print(f"Saved Original as {output_path}")
                video_downloaded_path = output_path
                processed_urls[url].append('O')
                continue

            if submode in ["all", "all+a", "all+a+v", "all+v"]:
                # Try picture first for image platforms in 'all' mode
                if submode == "all" and is_image_platform(url) and 'P' not in processed_urls[url]:
                    output_name_with_ext, output_name_base, current_p_number = get_next_available_name(output_dir, "P", ".jpg", start_num=current_p_number)
                    output_name = os.path.join(output_dir, output_name_base)
                    output_path = os.path.join(output_dir, output_name_with_ext)

                    print("Downloading picture...")

                    if os.path.exists(temp_image_dir):
                        shutil.rmtree(temp_image_dir)
                    os.makedirs(temp_image_dir)

                    gallery_dl_check_cmd = "gallery-dl --version"
                    success, output = run_command(gallery_dl_check_cmd, suppress_errors=True)
                    if not success:
                        print("Error: gallery-dl not installed. Install with 'pip install gallery-dl'.")
                        shutil.rmtree(temp_image_dir)
                        continue

                    gallery_dl_cmd = (
                        f'gallery-dl {auth} -D "{temp_image_dir}" --no-skip "{url}"'
                    )
                    success, output = run_command(gallery_dl_cmd, suppress_errors=True)
                    image_files = sorted(glob.glob(os.path.join(temp_image_dir, "*")))

                    if success and image_files:
                        image_file = image_files[0]
                        if keep_original:
                            ext = os.path.splitext(image_file)[1]
                            os.rename(image_file, output_path)
                            print(f"Saved to {output_path}")
                        else:
                            ffmpeg_cmd = (
                                f'ffmpeg -i "{image_file}" "{output_path}"'
                            )
                            success, output = run_command(ffmpeg_cmd, suppress_errors=True)
                            if success:
                                os.remove(image_file)
                                print(f"Saved to {output_path}")
                            else:
                                print(f"Failed to convert image: {url}")
                                if os.path.exists(image_file):
                                    os.remove(image_file)
                        shutil.rmtree(temp_image_dir)
                        processed_urls[url].append('P')
                        continue
                    else:
                        print(f"Failed to download picture: {url}")
                        shutil.rmtree(temp_image_dir)

                if 'O' not in processed_urls[url]:
                    video_prefix = "O" if keep_original else "U"
                    output_name_with_ext, output_name_base, current_o_number = get_next_available_name(output_dir, video_prefix, ".mp4", start_num=current_o_number)
                    output_name = os.path.join(output_dir, output_name_base)
                    output_path = os.path.join(output_dir, output_name_with_ext)

                    if submode == "all":
                        print("Converting to universal format...")

                    yt_dlp_cmd = (
                        f'yt-dlp {auth} -f "bestvideo+bestaudio/best" --merge-output-format mp4 '
                        f'-o "{temp_file}" "{url}"'
                    )
                    success, output = run_command(yt_dlp_cmd, suppress_errors=True, timeout=300, retries=1)
                    if os.path.exists(temp_file):
                        if keep_original:
                            cmd = (
                                f'ffprobe -v error -show_streams -select_streams v:0 -show_entries stream=codec_name -of json "{temp_file}"'
                            )
                            success, output = run_command(cmd, suppress_errors=True)
                            video_codec = None
                            if success:
                                data = json.loads(output)
                                if data.get('streams'):
                                    video_codec = data['streams'][0].get('codec_name')

                            cmd = (
                                f'ffprobe -v error -show_streams -select_streams a:0 -show_entries stream=codec_name -of json "{temp_file}"'
                            )
                            success, output = run_command(cmd, suppress_errors=True)
                            audio_codec = None
                            if success:
                                data = json.loads(output)
                                if data.get('streams'):
                                    audio_codec = data['streams'][0].get('codec_name')

                            if video_codec == 'h264' and (audio_codec == 'aac' or not audio_codec):
                                os.rename(temp_file, output_path)
                                if submode == "all":
                                    print(f"Saved to {output_path}")
                                else:
                                    print(f"Saved Original as {output_path}")
                            else:
                                if submode != "all":
                                    print("Converting to universal format...")
                                width, height = get_video_dimensions(temp_file)
                                width = width + (width % 2)
                                height = height + (height % 2)
                                aspect_ratio = width / height
                                if aspect_ratio > 1.5:
                                    target_width, target_height = min(width, 1920), min(height, 1080)
                                elif aspect_ratio < 0.67:
                                    target_width, target_height = min(width, 1080), min(height, 1920)
                                else:
                                    target_width, target_height = min(width, 1080), min(height, 1080)
                                target_width = target_width + (target_width % 2)
                                target_height = target_height + (target_height % 2)
                                ffmpeg_cmd = (
                                    f'ffmpeg -i "{temp_file}" -c:v libx264 -preset ultrafast -b:v 3500k '
                                    f'-vf "scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2" -r 30 '
                                    f'-c:a aac -b:a 128k -ar 44100 -t 140 "{output_path}"'
                                )
                                success, output = run_command(ffmpeg_cmd, suppress_errors=True)
                                if success:
                                    if os.path.exists(temp_file):
                                        os.remove(temp_file)
                                    if submode == "all":
                                        print(f"Saved to {output_path}")
                                    else:
                                        print(f"Saved Universal as {output_path}")
                                else:
                                    print(f"Failed to convert: {url}")
                                    if os.path.exists(temp_file):
                                        os.remove(temp_file)
                                    continue
                        else:
                            if submode != "all":
                                print("Converting to universal format...")
                            width, height = get_video_dimensions(temp_file)
                            width = width + (width % 2)
                            height = height + (height % 2)
                            aspect_ratio = width / height
                            if aspect_ratio > 1.5:
                                target_width, target_height = min(width, 1920), min(height, 1080)
                            elif aspect_ratio < 0.67:
                                target_width, target_height = min(width, 1080), min(height, 1920)
                            else:
                                target_width, target_height = min(width, 1080), min(height, 1080)
                            target_width = target_width + (target_width % 2)
                            target_height = target_height + (target_height % 2)
                            ffmpeg_cmd = (
                                f'ffmpeg -i "{temp_file}" -c:v libx264 -preset ultrafast -b:v 3500k '
                                f'-vf "scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2" -r 30 '
                                f'-c:a aac -b:a 128k -ar 44100 -t 140 "{output_path}"'
                            )
                            success, output = run_command(ffmpeg_cmd, suppress_errors=True)
                            if success:
                                if os.path.exists(temp_file):
                                    os.remove(temp_file)
                                if submode == "all":
                                    print(f"Saved to {output_path}")
                                else:
                                    print(f"Saved Universal as {output_path}")
                            else:
                                print(f"Failed to convert: {url}")
                                if os.path.exists(temp_file):
                                    os.remove(temp_file)
                                continue
                        video_downloaded_path = output_path
                        processed_urls[url].append('O')

                if 'O' in processed_urls[url]:
                    if submode in ["all+a", "all+a+v", "all+v"]:
                        pass
                    else:
                        continue

                if 'P' not in processed_urls[url] and 'O' not in processed_urls[url]:
                    if is_video_platform(url) and ('V' in processed_urls[url] or 'A' in processed_urls[url]):
                        if submode != "all":
                            print("Skipping picture download for video platform...")
                    else:
                        output_name_with_ext, output_name_base, current_p_number = get_next_available_name(output_dir, "P", ".jpg", start_num=current_p_number)
                        output_name = os.path.join(output_dir, output_name_base)
                        output_path = os.path.join(output_dir, output_name_with_ext)

                        if os.path.exists(temp_image_dir):
                            shutil.rmtree(temp_image_dir)
                        os.makedirs(temp_image_dir)

                        gallery_dl_check_cmd = "gallery-dl --version"
                        success, output = run_command(gallery_dl_check_cmd, suppress_errors=True)
                        if not success:
                            print("Error: gallery-dl not installed. Install with 'pip install gallery-dl'.")
                            shutil.rmtree(temp_image_dir)
                            continue

                        if submode == "all":
                            print("Downloading picture...")
                        else:
                            print("Attempting to download picture...")

                        gallery_dl_cmd = (
                            f'gallery-dl {auth} -D "{temp_image_dir}" --no-skip "{url}"'
                        )
                        success, output = run_command(gallery_dl_cmd, suppress_errors=True)
                        image_files = sorted(glob.glob(os.path.join(temp_image_dir, "*")))

                        if success and image_files:
                            image_file = image_files[0]
                            if keep_original:
                                ext = os.path.splitext(image_file)[1]
                                os.rename(image_file, output_path)
                                if submode == "all":
                                    print(f"Saved to {output_path}")
                                else:
                                    print(f"Saved Picture as {output_path}")
                            else:
                                ffmpeg_cmd = (
                                    f'ffmpeg -i "{image_file}" "{output_path}"'
                                )
                                success, output = run_command(ffmpeg_cmd, suppress_errors=True)
                                if success:
                                    os.remove(image_file)
                                    if submode == "all":
                                        print(f"Saved to {output_path}")
                                    else:
                                        print(f"Saved Picture as {output_path}")
                                else:
                                    print(f"Failed to convert image: {url}")
                                    if os.path.exists(image_file):
                                        os.remove(image_file)
                            shutil.rmtree(temp_image_dir)
                            processed_urls[url].append('P')
                            if submode == "all":
                                continue
                        else:
                            print(f"Failed to download picture: {url}")
                            shutil.rmtree(temp_image_dir)

                if 'V' not in processed_urls[url] and 'O' not in processed_urls[url] and 'P' not in processed_urls[url]:
                    output_name_with_ext, output_name_base, current_v_number = get_next_available_name(output_dir, "V", ".mp4", start_num=current_v_number)
                    output_name = os.path.join(output_dir, output_name_base)
                    output_path = os.path.join(output_dir, output_name_with_ext)

                    if submode == "all":
                        print("Converting to universal format...")
                    else:
                        print("Attempting to download video-only...")

                    yt_dlp_cmd = (
                        f'yt-dlp {auth} -f "bestvideo[ext=mp4]" --merge-output-format mp4 '
                        f'-o "{temp_file}" "{url}"'
                    )
                    success, output = run_command(yt_dlp_cmd, suppress_errors=True, timeout=300, retries=1)
                    if success and os.path.exists(temp_file):
                        if keep_original:
                            os.rename(temp_file, output_path)
                            if submode == "all":
                                print(f"Saved to {output_path}")
                            else:
                                print(f"Saved Video as {output_path}")
                        else:
                            width, height = get_video_dimensions(temp_file)
                            width = width + (width % 2)
                            height = height + (height % 2)
                            aspect_ratio = width / height
                            if aspect_ratio > 1.5:
                                target_width, target_height = min(width, 1920), min(height, 1080)
                            elif aspect_ratio < 0.67:
                                target_width, target_height = min(width, 1080), min(height, 1920)
                            else:
                                target_width, target_height = min(width, 1080), min(height, 1080)
                            target_width = target_width + (target_width % 2)
                            target_height = target_height + (target_height % 2)
                            ffmpeg_cmd = (
                                f'ffmpeg -i "{temp_file}" -c:v libx264 -preset ultrafast -b:v 3500k '
                                f'-vf "scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2" -r 30 '
                                f'-an -t 140 "{output_path}"'
                            )
                            success, output = run_command(ffmpeg_cmd, suppress_errors=True)
                            if success:
                                if os.path.exists(temp_file):
                                    os.remove(temp_file)
                                if submode == "all":
                                    print(f"Saved to {output_path}")
                                else:
                                    print(f"Saved Video as {output_path}")
                            else:
                                print(f"Failed to convert video: {url}")
                                if os.path.exists(temp_file):
                                    os.remove(temp_file)
                                continue
                        processed_urls[url].append('V')
                        if submode == "all":
                            continue
                    else:
                        if submode != "all":
                            print(f"Failed to download video-only: {url}")

                if 'A' not in processed_urls[url] and 'O' not in processed_urls[url] and 'P' not in processed_urls[url]:
                    output_name_with_ext, output_name_base, current_a_number = get_next_available_name(output_dir, "A", ".m4a", start_num=audio_counter, force_num=True)
                    output_name = os.path.join(output_dir, output_name_base)
                    output_path = os.path.join(output_dir, output_name_with_ext)

                    if submode == "all":
                        print("Converting to universal format...")
                    else:
                        print("Attempting to download audio...")

                    yt_dlp_cmd = (
                        f'yt-dlp {auth} -f "bestaudio/best" -o "{temp_audio_file}" "{url}"'
                    )
                    success, output = run_command(yt_dlp_cmd, suppress_errors=True, timeout=300, retries=1)
                    if success and os.path.exists(temp_audio_file):
                        has_video = has_video_stream(temp_audio_file)
                        has_audio = has_audio_stream(temp_audio_file)
                        if has_video and has_audio and 'O' not in processed_urls[url]:
                            video_prefix = "O" if keep_original else "U"
                            video_output_name_with_ext, video_output_name_base, current_o_number = get_next_available_name(output_dir, video_prefix, ".mp4", start_num=current_o_number)
                            video_output_path = os.path.join(output_dir, video_output_name_with_ext)
                            if keep_original:
                                os.rename(temp_audio_file, video_output_path)
                                if submode == "all":
                                    print(f"Saved to {video_output_path}")
                                else:
                                    print(f"Saved Original as {video_output_path}")
                            else:
                                width, height = get_video_dimensions(temp_audio_file)
                                width = width + (width % 2)
                                height = height + (height % 2)
                                aspect_ratio = width / height
                                if aspect_ratio > 1.5:
                                    target_width, target_height = min(width, 1920), min(height, 1080)
                                elif aspect_ratio < 0.67:
                                    target_width, target_height = min(width, 1080), min(height, 1920)
                                else:
                                    target_width, target_height = min(width, 1080), min(height, 1080)
                                target_width = target_width + (target_width % 2)
                                target_height = target_height + (target_height % 2)
                                ffmpeg_cmd = (
                                    f'ffmpeg -i "{temp_audio_file}" -c:v libx264 -preset ultrafast -b:v 3500k '
                                    f'-vf "scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2" -r 30 '
                                    f'-c:a aac -b:a 128k -ar 44100 -t 140 "{video_output_path}"'
                                )
                                success, output = run_command(ffmpeg_cmd, suppress_errors=True)
                                if success:
                                    if os.path.exists(temp_audio_file):
                                        os.remove(temp_audio_file)
                                    if submode == "all":
                                        print(f"Saved to {video_output_path}")
                                    else:
                                        print(f"Saved Original as {video_output_path}")
                                else:
                                    print(f"Failed to convert video: {url}")
                                    if os.path.exists(temp_audio_file):
                                        os.remove(temp_audio_file)
                                    continue
                            video_downloaded_path = video_output_path
                            processed_urls[url].append('O')
                        elif has_video and 'V' not in processed_urls[url]:
                            video_output_name_with_ext, video_output_name_base, current_v_number = get_next_available_name(output_dir, "V", ".mp4", start_num=current_v_number)
                            video_output_path = os.path.join(output_dir, video_output_name_with_ext)
                            if keep_original:
                                os.rename(temp_audio_file, video_output_path)
                                if submode == "all":
                                    print(f"Saved to {video_output_path}")
                                else:
                                    print(f"Saved Video as {video_output_path}")
                            else:
                                width, height = get_video_dimensions(temp_audio_file)
                                width = width + (width % 2)
                                height = height + (height % 2)
                                aspect_ratio = width / height
                                if aspect_ratio > 1.5:
                                    target_width, target_height = min(width, 1920), min(height, 1080)
                                elif aspect_ratio < 0.67:
                                    target_width, target_height = min(width, 1080), min(height, 1920)
                                else:
                                    target_width, target_height = min(width, 1080), min(height, 1080)
                                target_width = target_width + (target_width % 2)
                                target_height = target_height + (target_height % 2)
                                ffmpeg_cmd = (
                                    f'ffmpeg -i "{temp_audio_file}" -c:v libx264 -preset ultrafast -b:v 3500k '
                                    f'-vf "scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2" -r 30 '
                                    f'-t 140 "{video_output_path}"'
                                )
                                success, output = run_command(ffmpeg_cmd, suppress_errors=True)
                                if success:
                                    if os.path.exists(temp_audio_file):
                                        os.remove(temp_audio_file)
                                    if submode == "all":
                                        print(f"Saved to {video_output_path}")
                                    else:
                                        print(f"Saved Video as {video_output_path}")
                                else:
                                    print(f"Failed to convert video: {url}")
                                    if os.path.exists(temp_audio_file):
                                        os.remove(temp_audio_file)
                                    continue
                            processed_urls[url].append('V')
                        else:
                            ffmpeg_cmd = (
                                f'ffmpeg -i "{temp_audio_file}" -c:a aac -b:a 128k "{output_path}"'
                            )
                            success, output = run_command(ffmpeg_cmd, suppress_errors=True)
                            if success:
                                if submode == "all":
                                    print(f"Saved to {output_path}")
                                else:
                                    print(f"Saved Audio as {output_path}")
                                audio_counter += 1
                                if os.path.exists(temp_audio_file):
                                    os.remove(temp_audio_file)
                                processed_urls[url].append('A')
                            else:
                                print(f"Failed to convert audio: {url}")
                                if os.path.exists(temp_audio_file):
                                    os.remove(temp_audio_file)
                                continue
                    else:
                        if submode != "all":
                            print(f"Failed to download audio: {url}")

                if submode in ["all+a", "all+a+v"] and 'A' not in processed_urls[url]:
                    if 'O' in processed_urls[url] and video_downloaded_path and has_audio_stream(video_downloaded_path):
                        output_name_with_ext, output_name_base, current_a_number = get_next_available_name(output_dir, "A", ".m4a", start_num=audio_counter, force_num=True)
                        output_name = os.path.join(output_dir, output_name_base)
                        output_path = os.path.join(output_dir, output_name_with_ext)

                        if submode == "all":
                            print("Converting to universal format...")
                        else:
                            print(f"Extracting audio from video: {video_downloaded_path}")

                        ffmpeg_cmd = (
                            f'ffmpeg -i "{video_downloaded_path}" -vn -c:a aac -b:a 128k "{output_path}"'
                        )
                        success, output = run_command(ffmpeg_cmd, suppress_errors=True)
                        if success:
                            if submode == "all":
                                print(f"Saved to {output_path}")
                            else:
                                print(f"Saved Audio as {output_path}")
                            audio_counter += 1
                            processed_urls[url].append('A')
                        else:
                            print(f"Failed to extract audio from video: {video_downloaded_path}")
                    else:
                        if 'P' in processed_urls[url]:
                            if submode != "all":
                                print("Skipping audio download as picture was downloaded...")
                            continue

                        output_name_with_ext, output_name_base, current_a_number = get_next_available_name(output_dir, "A", ".m4a", start_num=audio_counter, force_num=True)
                        output_name = os.path.join(output_dir, output_name_base)
                        output_path = os.path.join(output_dir, output_name_with_ext)

                        if submode == "all":
                            print("Converting to universal format...")
                        else:
                            print("Attempting to download separate audio...")

                        yt_dlp_cmd = (
                            f'yt-dlp {auth} -f "bestaudio/best" -o "{temp_audio_file}" "{url}"'
                        )
                        success, output = run_command(yt_dlp_cmd, suppress_errors=True, timeout=300, retries=1)
                        if success and os.path.exists(temp_audio_file):
                            has_video = has_video_stream(temp_audio_file)
                            has_audio = has_audio_stream(temp_audio_file)
                            if has_video and has_audio and 'O' not in processed_urls[url]:
                                video_prefix = "O" if keep_original else "U"
                                video_output_name_with_ext, video_output_name_base, current_o_number = get_next_available_name(output_dir, video_prefix, ".mp4", start_num=current_o_number)
                                video_output_path = os.path.join(output_dir, video_output_name_with_ext)
                                if keep_original:
                                    os.rename(temp_audio_file, video_output_path)
                                    if submode == "all":
                                        print(f"Saved to {video_output_path}")
                                    else:
                                        print(f"Saved Original as {video_output_path}")
                                else:
                                    width, height = get_video_dimensions(temp_audio_file)
                                    width = width + (width % 2)
                                    height = height + (height % 2)
                                    aspect_ratio = width / height
                                    if aspect_ratio > 1.5:
                                        target_width, target_height = min(width, 1920), min(height, 1080)
                                    elif aspect_ratio < 0.67:
                                        target_width, target_height = min(width, 1080), min(height, 1920)
                                    else:
                                        target_width, target_height = min(width, 1080), min(height, 1080)
                                    target_width = target_width + (target_width % 2)
                                    target_height = target_height + (target_height % 2)
                                    ffmpeg_cmd = (
                                        f'ffmpeg -i "{temp_audio_file}" -c:v libx264 -preset ultrafast -b:v 3500k '
                                        f'-vf "scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2" -r 30 '
                                        f'-c:a aac -b:a 128k -ar 44100 -t 140 "{video_output_path}"'
                                    )
                                    success, output = run_command(ffmpeg_cmd, suppress_errors=True)
                                    if success:
                                        if os.path.exists(temp_audio_file):
                                            os.remove(temp_audio_file)
                                        if submode == "all":
                                            print(f"Saved to {video_output_path}")
                                        else:
                                            print(f"Saved Original as {video_output_path}")
                                    else:
                                        print(f"Failed to convert video: {url}")
                                        if os.path.exists(temp_audio_file):
                                            os.remove(temp_audio_file)
                                        continue
                                video_downloaded_path = video_output_path
                                processed_urls[url].append('O')
                                if submode in ["all+a", "all+a+v"]:
                                    if submode == "all":
                                        print("Converting to universal format...")
                                    else:
                                        print(f"Extracting audio from video: {video_downloaded_path}")
                                    ffmpeg_cmd = (
                                        f'ffmpeg -i "{video_downloaded_path}" -vn -c:a aac -b:a 128k "{output_path}"'
                                    )
                                    success, output = run_command(ffmpeg_cmd, suppress_errors=True)
                                    if success:
                                        if submode == "all":
                                            print(f"Saved to {output_path}")
                                        else:
                                            print(f"Saved Audio as {output_path}")
                                        audio_counter += 1
                                        processed_urls[url].append('A')
                                    else:
                                        print(f"Failed to extract audio from video: {video_downloaded_path}")
                            elif has_video and 'V' not in processed_urls[url]:
                                video_output_name_with_ext, video_output_name_base, current_v_number = get_next_available_name(output_dir, "V", ".mp4", start_num=current_v_number)
                                video_output_path = os.path.join(output_dir, video_output_name_with_ext)
                                if keep_original:
                                    os.rename(temp_audio_file, video_output_path)
                                    if submode == "all":
                                        print(f"Saved to {video_output_path}")
                                    else:
                                        print(f"Saved Video as {video_output_path}")
                                else:
                                    width, height = get_video_dimensions(temp_audio_file)
                                    width = width + (width % 2)
                                    height = height + (height % 2)
                                    aspect_ratio = width / height
                                    if aspect_ratio > 1.5:
                                        target_width, target_height = min(width, 1920), min(height, 1080)
                                    elif aspect_ratio < 0.67:
                                        target_width, target_height = min(width, 1080), min(height, 1920)
                                    else:
                                        target_width, target_height = min(width, 1080), min(height, 1080)
                                    target_width = target_width + (target_width % 2)
                                    target_height = target_height + (target_height % 2)
                                    ffmpeg_cmd = (
                                        f'ffmpeg -i "{temp_audio_file}" -c:v libx264 -preset ultrafast -b:v 3500k '
                                        f'-vf "scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2" -r 30 '
                                        f'-t 140 "{video_output_path}"'
                                    )
                                    success, output = run_command(ffmpeg_cmd, suppress_errors=True)
                                    if success:
                                        if os.path.exists(temp_audio_file):
                                            os.remove(temp_audio_file)
                                        if submode == "all":
                                            print(f"Saved to {video_output_path}")
                                        else:
                                            print(f"Saved Video as {video_output_path}")
                                    else:
                                        print(f"Failed to convert video: {url}")
                                        if os.path.exists(temp_audio_file):
                                            os.remove(temp_audio_file)
                                        continue
                                processed_urls[url].append('V')
                            else:
                                ffmpeg_cmd = (
                                    f'ffmpeg -i "{temp_audio_file}" -c:a aac -b:a 128k "{output_path}"'
                                )
                                success, output = run_command(ffmpeg_cmd, suppress_errors=True)
                                if success:
                                    if submode == "all":
                                        print(f"Saved to {output_path}")
                                    else:
                                        print(f"Saved Audio as {output_path}")
                                    audio_counter += 1
                                    if os.path.exists(temp_audio_file):
                                        os.remove(temp_audio_file)
                                    processed_urls[url].append('A')
                                else:
                                    print(f"Failed to convert audio: {url}")
                                    if os.path.exists(temp_audio_file):
                                        os.remove(temp_audio_file)
                                    continue
                        else:
                            if submode != "all":
                                print(f"Failed to download audio: {url}")

                if submode in ["all+a+v", "all+v"] and 'O' in processed_urls[url] and 'V' not in processed_urls[url]:
                    output_name_with_ext, output_name_base, current_v_number = get_next_available_name(output_dir, "V", ".mp4", start_num=current_v_number)
                    output_name = os.path.join(output_dir, output_name_base)
                    output_path = os.path.join(output_dir, output_name_with_ext)

                    if submode == "all":
                        print("Converting to universal format...")
                    else:
                        print(f"Splitting video to remove audio: {video_downloaded_path}")

                    ffmpeg_cmd = (
                        f'ffmpeg -i "{video_downloaded_path}" -c:v copy -an "{output_path}"'
                    )
                    success, output = run_command(ffmpeg_cmd, suppress_errors=True)
                    if success:
                        if submode == "all":
                            print(f"Saved to {output_path}")
                        else:
                            print(f"Saved Video-only as {output_path}")
                        processed_urls[url].append('V')
                    else:
                        print(f"Failed to split video: {video_downloaded_path}")

        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            if os.path.exists(temp_audio_file):
                os.remove(temp_audio_file)
            if os.path.exists(temp_image_dir):
                shutil.rmtree(temp_image_dir)

    print(f"Done! Outputs saved in {output_dir}")

if __name__ == "__main__":
    main()
