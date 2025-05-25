import subprocess
import sys
import os
import argparse
import re
import json
import urllib.parse
import time
import signal
import glob
import shutil

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
        stderr = subprocess.PIPE if not suppress_errors else subprocess.DEVNULL  # Capture stderr separately
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
        start_time = time.time()

        try:
            # Use communicate with a timeout to prevent hanging
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

def get_next_available_name(output_dir, prefix, extension, title=None, start_num=1, use_url=False, url=None):
    if use_url and url:
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path.strip('/')
        query = urllib.parse.parse_qs(parsed_url.query)
        si_param = query.get('si', [''])[0]
        name_base = f"{path}_{si_param}" if si_param else path
        sanitized_title = sanitize_filename(name_base)
    elif title:
        sanitized_title = sanitize_filename(title)
    else:
        sanitized_title = None

    if sanitized_title:
        num = start_num
        while True:
            name = f"{prefix}_{num}_{sanitized_title}{extension}"
            full_path = os.path.join(output_dir, name)
            thumb_path = os.path.join(output_dir, f"{prefix}_{num}_{sanitized_title}_thumb.webp")
            if not os.path.exists(full_path) and not os.path.exists(thumb_path):
                base_name = f"{prefix姐妹sanitized_title}"
                return name, base_name, num + 1
            num += 1
    else:
        num = start_num
        while True:
            name = f"{prefix}_{num}{extension}"
            full_path = os.path.join(output_dir, name)
            thumb_path = os.path.join(output_dir, f"{prefix}_{num}_thumb.webp")
            if not os.path.exists(full_path) and not os.path.exists(thumb_path):
                base_name = f"{prefix}_{num}"
                return name, base_name, num + 1
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
        from PIL import Image  # Import here to avoid requiring Pillow for other submodes
        with Image.open(image_path) as img:
            width, height = img.size
            return width, height
    except Exception as e:
        print(f"Warning: Could not determine dimensions of {image_path} using Pillow: {e}")
        print(f"Using default dimensions 1080x1080 for {image_path}.")
        return 1080, 1080

def find_video_file(video_path):
    extensions = ['.mp4', '.mkv']
    if os.path.splitext(video_path)[1].lower() in extensions and os.path.exists(video_path):
        return video_path
    base_name = os.path.splitext(os.path.basename(video_path))[0].lower()
    dir_name = os.path.abspath(os.path.dirname(video_path) or ".")

    try:
        matching_files = []
        for file in os.listdir(dir_name):
            file_lower = file.lower()
            ext = os.path.splitext(file_lower)[1]
            if file_lower.startswith(base_name) and ext in extensions:
                matching_files.append(os.path.join(dir_name, file))
        if matching_files:
            for ext in extensions:
                for match in matching_files:
                    if match.lower().endswith(ext):
                        return match
            return matching_files[0]
    except Exception as e:
        print(f"Error accessing directory {dir_name}: {e}")
    return None

def find_audio_file(audio_path):
    extensions = ['.m4a']
    if os.path.splitext(audio_path)[1].lower() in extensions and os.path.exists(audio_path):
        return audio_path
    base_name = os.path.splitext(os.path.basename(audio_path))[0].lower()
    dir_name = os.path.abspath(os.path.dirname(audio_path) or ".")

    try:
        matching_files = []
        for file in os.listdir(dir_name):
            file_lower = file.lower()
            ext = os.path.splitext(file_lower)[1]
            if file_lower.startswith(base_name) and ext in extensions:
                matching_files.append(os.path.join(dir_name, file))
        return matching_files[0] if matching_files else None
    except Exception as e:
        print(f"Error accessing directory {dir_name}: {e}")
    return None

def find_image_file(image_path):
    extensions = ['.jpg', '.jpeg', '.png', '.webp']
    if os.path.splitext(image_path)[1].lower() in extensions and os.path.exists(image_path):
        return image_path
    base_name = os.path.splitext(os.path.basename(image_path))[0].lower()
    dir_name = os.path.abspath(os.path.dirname(image_path) or ".")

    try:
        matching_files = []
        for file in os.listdir(dir_name):
            file_lower = file.lower()
            ext = os.path.splitext(file_lower)[1]
            if file_lower.startswith(base_name) and ext in extensions:
                matching_files.append(os.path.join(dir_name, file))
        return matching_files[0] if matching_files else None
    except Exception as e:
        print(f"Error accessing directory {dir_name}: {e}")
    return None

def get_video_title(file_path, auth):
    yt_dlp_title_cmd = f'yt-dlp {auth} --get-title "{file_path}"'
    success, output = run_command(yt_dlp_title_cmd, suppress_errors=False)
    if success and output.strip() and not output.lower().startswith("error"):
        return output.strip()
    return None

def extract_title_from_output(output, default_title):
    for line in output.splitlines():
        youtube_match = re.search(r'\[youtube\]\s+[^:]+:\s+(.+?)(?=\s+\[|$)', line)
        if youtube_match and "Extracting URL" not in line:
            return youtube_match.group(1).strip()
        info_match = re.search(r'\[info\]\s+[^:]+:\s+(.+?)(?=\s+\[|$)', line)
        if info_match:
            return info_match.group(1).strip()
        downloading_match = re.search(r'\[downloading\]\s+(.+?)\s+\d+\.\d+[KMG]?iB', line)
        if downloading_match:
            return downloading_match.group(1).strip()
    return default_title

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

def main():
    global DEBUG
    parser = argparse.ArgumentParser(description="Process media files: trim, loop, split, combine, convert, or create slideshows")
    subparsers = parser.add_subparsers(dest="submode", help="Submode: 'trim', 'loop', 'loopaudio', 'split', 'combine', 'convert', 'slide', 'concat'")
    subparsers.required = True

    # Subparser for 'trim' submode (trim-only, supports audio or video output)
    parser_trim = subparsers.add_parser("trim", help="Trim audio or video without looping")
    trim_subparsers = parser_trim.add_subparsers(dest="output_type", help="Output type: 'a' for audio (.m4a), 'v' for video (.mp4)")
    trim_subparsers.required = True

    # 'trim a' (audio output)
    parser_trim_audio = trim_subparsers.add_parser("a", help="Output as audio (.m4a)")
    parser_trim_audio.add_argument("video_path", help="Path to the video file (e.g., ./videos/U1 for U1.mp4)")
    parser_trim_audio.add_argument("--start", type=float, default=0, help="Start time in seconds (default: 0)")
    parser_trim_audio.add_argument("--end", type=float, required=True, help="End time in seconds")
    parser_trim_audio.add_argument("--output-dir", "-o", help="Directory where output will be saved (default: same as video file directory)")
    parser_trim_audio.add_argument("--username")
    parser_trim_audio.add_argument("--password")
    parser_trim_audio.add_argument("--cookies")
    parser_trim_audio.add_argument("--debug", action="store_true", help="Enable debug output")

    # 'trim v' (video output)
    parser_trim_video = trim_subparsers.add_parser("v", help="Output as video (.mp4)")
    parser_trim_video.add_argument("video_path", help="Path to the video file (e.g., ./videos/U1 for U1.mp4)")
    parser_trim_video.add_argument("--start", type=float, default=0, help="Start time in seconds (default: 0)")
    parser_trim_video.add_argument("--end", type=float, required=True, help="End time in seconds")
    parser_trim_video.add_argument("--output-dir", "-o", help="Directory where output will be saved (default: same as video file directory)")
    parser_trim_video.add_argument("--username")
    parser_trim_video.add_argument("--password")
    parser_trim_video.add_argument("--cookies")
    parser_trim_video.add_argument("--debug", action="store_true", help="Enable debug output")

    # Subparser for 'loop' submode (trim and loop, supports audio or video output)
    parser_loop = subparsers.add_parser("loop", help="Trim and loop audio or video to a desired duration")
    loop_subparsers = parser_loop.add_subparsers(dest="output_type", help="Output type: 'a' for audio (.m4a), 'v' for video (.mp4)")
    loop_subparsers.required = True

    # 'loop a' (audio output)
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

    # 'loop v' (video output)
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

    # Subparser for 'loopaudio' submode (loop an audio file without trimming)
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
    parser_combine = subparsers.add_parser("combine", help="Combine a video and audio file into a single video")
    parser_combine.add_argument("video_path", help="Path to the video file (e.g., ./videos/V1 for V1.mp4)")
    parser_combine.add_argument("audio_path", help="Path to the audio file (e.g., ./audio/A1 for A1.m4a)")
    parser_combine.add_argument("--output-dir", "-o", help="Directory where output will be saved (default: same as video file directory)")
    parser_combine.add_argument("--username")
    parser_combine.add_argument("--password")
    parser_combine.add_argument("--cookies")
    parser_combine.add_argument("--debug", action="store_true", help="Enable debug output")

    # Subparser for 'convert' submode
    parser_convert = subparsers.add_parser("convert", help="Convert existing videos to universal format")
    parser_convert.add_argument("input", help="Directory containing video files or a wildcard pattern (e.g., ./reels or ./reels/reel*.mp4)")
    parser_convert.add_argument("--output-dir", "-o", default=".", help="Directory where outputs will be saved (default: current directory)")
    parser_convert.add_argument("--username")
    parser_convert.add_argument("--password")
    parser_convert.add_argument("--cookies")
    parser_convert.add_argument("--debug", action="store_true", help="Enable debug output")

    # Subparser for 'slide' submode
    parser_slide = subparsers.add_parser("slide", help="Create a slideshow video from images")
    parser_slide.add_argument("delay", type=float, help="Delay in seconds for each image")
    parser_slide.add_argument("image_paths", nargs='+', help="Paths to image files or a directory/wildcard pattern (e.g., ./images or ./images/*.jpg)")
    parser_slide.add_argument("--output-dir", "-o", help="Directory where output will be saved (default: first image directory)")
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

    args = parser.parse_args()
    DEBUG = args.debug
    submode = args.submode

    # Handle authentication
    if args.username and args.password:
        auth = f"--username {args.username} --password {args.password}"
    elif args.cookies:
        auth = f"--cookies {args.cookies}"
    else:
        auth = "--cookies-from-browser firefox"

    # Common temporary file paths
    temp_dir = os.path.abspath(os.path.join(".", "temp_slideshow"))
    temp_trimmed_path = os.path.join(temp_dir, "temp_trimmed_file")

    try:
        if submode in ["trim", "loop"]:
            output_type = args.output_type
            video_path = args.video_path
            start_time = args.start
            end_time = args.end
            desired_duration = getattr(args, "duration", None)
            output_dir = args.output_dir if args.output_dir else os.path.dirname(os.path.abspath(video_path)) or "."

            # Validate and set up
            actual_video_path = find_video_file(video_path)
            if not actual_video_path or not os.path.exists(actual_video_path):
                print(f"Error: Video file not found: {video_path}")
                sys.exit(1)

            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            video_duration = get_file_duration(actual_video_path)
            if video_duration == 0:
                print(f"Error: Could not determine duration of {actual_video_path}")
                sys.exit(1)

            if start_time < 0 or start_time >= video_duration:
                print(f"Error: Start time {start_time} is out of bounds (video duration: {video_duration} seconds)")
                sys.exit(1)

            if end_time <= start_time or end_time > video_duration:
                print(f"Error: End time {end_time} is out of bounds (start: {start_time}, video duration: {video_duration} seconds)")
                sys.exit(1)

            trim_duration = end_time - start_time

            # Get video title
            video_title = os.path.splitext(os.path.basename(actual_video_path))[0]
            title_fetched = False
            title = get_video_title(actual_video_path, auth)
            if title:
                video_title = title
                title_fetched = True

            # Determine output prefix and extension
            if output_type == "a":
                prefix = "A" if submode == "trim" else "AL"
                extension = ".m4a"
            else:  # output_type == "v"
                prefix = "V" if submode == "trim" else "VL"
                extension = ".mp4"

            output_name_with_ext, output_name_base, _ = get_next_available_name(
                output_dir, prefix, extension, title=video_title
            )
            output_path = os.path.join(output_dir, output_name_with_ext)

            # Create temporary directory
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

            try:
                # Trim the video/audio
                if output_type == "v":
                    ffmpeg_cmd = (
                        f'ffmpeg -y -i "{actual_video_path}" -ss {start_time} -t {trim_duration} '
                        f'-c:v copy -c:a aac -b:a 128k "{temp_trimmed_path}{extension}"'
                    )
                else:  # output_type == "a"
                    ffmpeg_cmd = (
                        f'ffmpeg -y -i "{actual_video_path}" -vn -ss {start_time} -t {trim_duration} '
                        f'-c:a aac -b:a 128k "{temp_trimmed_path}{extension}"'
                    )

                success, output = run_command(ffmpeg_cmd)
                if not success or not os.path.exists(f"{temp_trimmed_path}{extension}"):
                    print(f"Failed to trim {actual_video_path}")
                    sys.exit(1)

                # If submode is 'trim', we're done after trimming
                if submode == "trim":
                    os.rename(f"{temp_trimmed_path}{extension}", output_path)
                    print(f"Saved {'Audio' if output_type == 'a' else 'Video'} as {output_path.replace(os.sep, '/')}")
                else:  # submode == "loop"
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
                            else:  # output_type == "a"
                                ffmpeg_cmd = (
                                    f'ffmpeg -y -stream_loop {loop_count - 1} -i "{temp_trimmed_path}{extension}" '
                                    f'-c:a copy -t {final_duration} "{output_path}"'
                                )
                            success, output = run_command(ffmpeg_cmd)
                            if success:
                                print(f"Saved Looped {'Audio' if output_type == 'a' else 'Video'} as {output_path.replace(os.sep, '/')}")
                            else:
                                print(f"Failed to loop {actual_video_path}")
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
            output_dir = args.output_dir if args.output_dir else os.path.dirname(os.path.abspath(audio_path)) or "."

            # Validate and set up
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

            # Get audio title
            audio_title = os.path.splitext(os.path.basename(actual_audio_path))[0]

            output_name_with_ext, output_name_base, _ = get_next_available_name(
                output_dir, "L", ".m4a", title=audio_title
            )
            output_path = os.path.join(output_dir, output_name_with_ext)

            ffmpeg_cmd = (
                f'ffmpeg -stream_loop {loop_count - 1} -i "{actual_audio_path}" '
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
            output_dir = args.output_dir if args.output_dir else os.path.dirname(os.path.abspath(input_path)) or "."

            # Validate and set up
            actual_input_path = find_video_file(input_path)
            if not actual_input_path or not os.path.exists(actual_input_path):
                print(f"Error: Input file not found: {input_path}")
                sys.exit(1)

            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            # Get input title
            input_title = os.path.splitext(os.path.basename(actual_input_path))[0]
            title_fetched = False
            title = get_video_title(actual_input_path, auth)
            if title:
                input_title = title
                title_fetched = True

            video_output_name_with_ext, video_output_name_base, _ = get_next_available_name(
                output_dir, "V", "_video.mp4", title=input_title
            )
            video_output_path = os.path.join(output_dir, video_output_name_with_ext)
            audio_output_path = os.path.join(output_dir, f"{video_output_name_base}_audio.m4a")

            # Split video
            ffmpeg_cmd = f'ffmpeg -i "{actual_input_path}" -c:v copy -an "{video_output_path}"'
            success, output = run_command(ffmpeg_cmd)
            if success:
                print(f"Saved Video-only as {video_output_path.replace(os.sep, '/')}")
                if has_audio_stream(actual_input_path):
                    ffmpeg_cmd = f'ffmpeg -i "{actual_input_path}" -vn -c:a aac -b:a 128k "{audio_output_path}"'
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
            video_path = args.video_path
            audio_path = args.audio_path
            output_dir = args.output_dir if args.output_dir else os.path.dirname(os.path.abspath(video_path)) or "."

            # Validate and set up
            actual_video_path = find_video_file(video_path)
            if not actual_video_path or not os.path.exists(actual_video_path):
                print(f"Error: Video file not found: {video_path}")
                sys.exit(1)

            actual_audio_path = find_audio_file(audio_path)
            if not actual_audio_path or not os.path.exists(actual_audio_path):
                print(f"Error: Audio file not found: {audio_path}")
                sys.exit(1)

            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            video_duration = get_file_duration(actual_video_path)
            audio_duration = get_file_duration(actual_audio_path)
            if video_duration == 0 or audio_duration == 0:
                print(f"Error: Could not determine duration of {actual_video_path} or {actual_audio_path}")
                sys.exit(1)

            # Get titles
            video_title = os.path.splitext(os.path.basename(actual_video_path))[0]
            audio_title = os.path.splitext(os.path.basename(actual_audio_path))[0]
            combined_title = f"{video_title}_{audio_title}"

            output_name_with_ext, output_name_base, _ = get_next_available_name(
                output_dir, "C", ".mp4", title=combined_title
            )
            output_path = os.path.join(output_dir, output_name_with_ext)

            # Determine loop count for audio to match or exceed video duration
            loop_count = int(video_duration // audio_duration) if audio_duration > 0 else 0
            if video_duration % audio_duration > 0:
                loop_count += 1

            # Combine video and audio
            max_duration = 140  # Default max duration
            final_duration = video_duration if video_duration > 0 else max_duration
            ffmpeg_cmd = (
                f'ffmpeg -i "{actual_video_path}" -stream_loop {loop_count - 1} -i "{actual_audio_path}" '
                f'-c:v libx264 -preset ultrafast -b:v 3500k -r 30 -pix_fmt yuv420p '
                f'-c:a aac -b:a 128k -ar 44100 -shortest -t {final_duration} "{output_path}"'
            )
            success, output = run_command(ffmpeg_cmd)
            if success:
                print(f"Saved Combined Video as {output_path.replace(os.sep, '/')}")
            else:
                print(f"Failed to combine {actual_video_path} and {actual_audio_path}")
                sys.exit(1)

        elif submode == "convert":
            input_arg = args.input
            output_dir = os.path.abspath(args.output_dir)

            # Determine if input_arg is a directory or a wildcard pattern
            if os.path.isdir(input_arg):
                # If it's a directory, match all video files within it
                video_extensions = ['*.mp4', '*.mkv']
                video_files = []
                for ext in video_extensions:
                    pattern = os.path.join(input_arg, ext)
                    debug_print(f"Debug: Searching for files with pattern: {pattern}")
                    found_files = glob.glob(pattern)
                    debug_print(f"Debug: Found files: {found_files}")
                    video_files.extend(found_files)
                # Remove duplicates (case-insensitive) to handle Windows file system behavior
                video_files = list(dict.fromkeys([f.lower() for f in video_files]))
                # Restore original case for file paths
                video_files = [next(f for f in video_files if f.lower() == v.lower()) for v in video_files]
            else:
                # If it's a wildcard pattern, use it directly
                debug_print(f"Debug: Using wildcard pattern: {input_arg}")
                video_files = glob.glob(input_arg)
                # Remove duplicates in case the pattern matches the same file in different cases
                video_files = list(dict.fromkeys([f.lower() for f in video_files]))
                video_files = [next(f for f in video_files if f.lower() == v.lower()) for v in video_files]

            # Sort files to ensure consistent numbering
            video_files = sorted(video_files)

            if not video_files:
                print(f"No video files found for input: {input_arg}")
                sys.exit(1)

            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            current_number = 1
            for video_file in video_files:
                print(f"Converting {video_file} ({current_number}/{len(video_files)})...")
                # Use simple numbering for output filename (U1.mp4, U2.mp4, etc.)
                output_name_with_ext = f"U{current_number}.mp4"
                output_path = os.path.join(output_dir, output_name_with_ext)

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
                    f'ffmpeg -i "{video_file}" -fflags +genpts -c:v libx264 -preset ultrafast -b:v 3500k '
                    f'-force_key_frames "0" '
                    f'-vf "scale={target_width}:{target_height}:force_divisible_by=2,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2" -r 30 '
                    f'-c:a aac -b:a 128k -ar 44100 -t 140 "{output_path}"'
                )
                debug_print(f"Debug: Running ffmpeg command: {ffmpeg_cmd}")
                success, output = run_command(ffmpeg_cmd, timeout=30, retries=1)  # 30-second timeout per file
                if success:
                    print(f"Saved Universal as {output_path.replace(os.sep, '/')}")
                else:
                    print(f"Failed to convert {video_file}")
                    print(f"FFmpeg output: {output}")
                    sys.exit(1)
                current_number += 1

        elif submode == "slide":
            delay = args.delay
            image_paths = args.image_paths
            output_dir = args.output_dir if args.output_dir else (os.path.dirname(os.path.abspath(image_paths[0])) if image_paths else ".") or "."

            # Check if image_paths is a single directory or wildcard pattern
            if len(image_paths) == 1:
                image_input = image_paths[0]
                if os.path.isdir(image_input):
                    # If it's a directory, find all image files within it
                    image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.webp']
                    image_files = []
                    for ext in image_extensions:
                        pattern = os.path.join(image_input, ext)
                        debug_print(f"Debug: Searching for files with pattern: {pattern}")
                        found_files = glob.glob(pattern)
                        debug_print(f"Debug: Found files: {found_files}")
                        image_files.extend(found_files)
                    # Remove duplicates (case-insensitive)
                    image_files = list(dict.fromkeys([f.lower() for f in image_files]))
                    image_files = [next(f for f in image_files if f.lower() == v.lower()) for v in image_files]
                    image_paths = sorted(image_files)  # Sort to ensure consistent order
                    if not image_paths:
                        print(f"No image files found in directory: {image_input}")
                        sys.exit(1)
                else:
                    # Check if it's a wildcard pattern
                    debug_print(f"Debug: Using wildcard pattern: {image_input}")
                    image_files = glob.glob(image_input)
                    image_files = list(dict.fromkeys([f.lower() for f in image_files]))
                    image_files = [next(f for f in image_files if f.lower() == v.lower()) for v in image_files]
                    image_paths = sorted(image_files)
                    if not image_paths:
                        print(f"No image files found for pattern: {image_input}")
                        sys.exit(1)

            # Validate image files
            actual_image_paths = []
            for image_path in image_paths:
                actual_image_path = find_image_file(image_path)
                if not actual_image_path or not os.path.exists(actual_image_path):
                    print(f"Error: Image file not found: {image_path}")
                    sys.exit(1)
                actual_image_paths.append(actual_image_path)

            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            # Determine best resolution for slideshow
            target_width, target_height = determine_best_resolution(actual_image_paths)

            # Create temporary directory for processed images
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

            try:
                # Process each image to the target resolution
                processed_images = []
                for idx, image_path in enumerate(actual_image_paths):
                    temp_image = os.path.join(temp_dir, f"image_{idx:03d}{os.path.splitext(image_path)[1]}")
                    ffmpeg_cmd = (
                        f'ffmpeg -i "{image_path}" '
                        f'-vf "scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2" '
                        f'"{temp_image}"'
                    )
                    success, output = run_command(ffmpeg_cmd)
                    if success and os.path.exists(temp_image):
                        processed_images.append(temp_image)
                    else:
                        print(f"Failed to process image {image_path}")
                        sys.exit(1)

                # Create concat file for slideshow
                concat_list_path = os.path.join(temp_dir, "concat_list.txt")
                with open(concat_list_path, "w") as f:
                    for img in processed_images:
                        f.write(f"file '{os.path.abspath(img)}'\n")
                        f.write(f"duration {delay}\n")

                # Create slideshow video
                output_name_with_ext, output_name_base, _ = get_next_available_name(
                    output_dir, "S", "_Slideshow.mp4", title="Slideshow"
                )
                output_path = os.path.join(output_dir, output_name_with_ext)

                ffmpeg_cmd = (
                    f'ffmpeg -f concat -safe 0 -i "{concat_list_path}" '
                    f'-c:v libx264 -preset ultrafast -b:v 3500k -r 30 -pix_fmt yuv420p "{output_path}"'
                )
                success, output = run_command(ffmpeg_cmd)
                if success:
                    print(f"Saved Slideshow as {output_path.replace(os.sep, '/')}")
                else:
                    print("Failed to create slideshow")
                    sys.exit(1)

            finally:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)

        elif submode == "concat":
            video_paths = args.video_paths
            output_dir = args.output_dir if args.output_dir else "."

            # Check if video_paths is a single directory
            if len(video_paths) == 1:
                video_dir = os.path.abspath(video_paths[0])  # Normalize the path
                if os.path.isdir(video_dir):
                    # If it's a directory, find all video files within it
                    video_extensions = ['*.mp4', '*.mkv']
                    video_files = []
                    for ext in video_extensions:
                        pattern = os.path.join(video_dir, ext)
                        debug_print(f"Debug: Searching for files with pattern: {pattern}")
                        found_files = glob.glob(pattern)
                        debug_print(f"Debug: Found files: {found_files}")
                        video_files.extend(found_files)
                    # Remove duplicates (case-insensitive)
                    video_files = list(dict.fromkeys([f.lower() for f in video_files]))
                    video_files = [next(f for f in video_files if f.lower() == v.lower()) for v in video_files]
                    video_paths = sorted(video_files)  # Sort to ensure consistent order
                    if not video_paths:
                        print(f"No video files found in directory: {video_dir}")
                        sys.exit(1)
                else:
                    # Treat it as a single file path
                    video_paths = [video_dir]
            else:
                # Multiple file paths provided
                # Remove duplicates in case the same file is specified in different cases
                video_paths = list(dict.fromkeys([f.lower() for f in video_paths]))
                video_paths = [next(f for f in video_paths if f.lower() == v.lower()) for v in video_paths]

            # Validate video files
            actual_video_paths = []
            for video_path in video_paths:
                actual_video_path = find_video_file(video_path)
                if not actual_video_path or not os.path.exists(actual_video_path):
                    print(f"Error: Video file not found: {video_path}")
                    sys.exit(1)
                actual_video_paths.append(actual_video_path)

            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            # Determine target resolution (use the resolution of the first video)
            width, height = get_video_dimensions(actual_video_paths[0])
            width = width + (width % 2)
            height = height + (height % 2)
            # Override with expected resolution from convert submode
            aspect_ratio = width / height
            if aspect_ratio > 1.5:
                width, height = 1920, 1080
            elif aspect_ratio < 0.67:
                width, height = 1080, 1920
            else:
                width, height = 1080, 1080

            # Calculate segment durations and fade-in points
            segment_durations = []
            for video_path in actual_video_paths:
                duration = get_file_duration(video_path)
                if duration == 0:
                    print(f"Error: Could not determine duration of {video_path}")
                    sys.exit(1)
                segment_durations.append(duration)

            # Create input arguments and filter complex for concat with fade-in
            input_args = ' '.join([f'-i "{video_path}"' for video_path in actual_video_paths])
            num_videos = len(actual_video_paths)

            # Build the filter complex
            # Example: [0:v] fade=t=in:st=0:d=1[v0];[1:v]fade=t=in:st=0:d=1[v1];...;[v0][0:a][v1][1:a]...concat=n=17:v=1:a=1[v][a];[v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2[vout]
            video_streams = []
            concat_inputs = []
            for i in range(num_videos):
                # Apply 1-second fade-in to each video stream
                video_streams.append(f'[{i}:v]fade=t=in:st=0:d=1[v{i}]')
                # Pair each faded video stream with its corresponding audio stream
                scollect_inputs.extend([f'[v{i}]', f'[{i}:a]'])

            # Add scaling and padding to the filter complex
            filter_complex = (
                f"{';'.join(video_streams)};"  # Semicolon between video filters
                f"{' '.join(concat_inputs)}"   # Interleave video and audio streams
                f"concat=n={num_videos}:v=1:a=1[v][a];"
                f"[v]scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2[vout]"
            )

            # Create output file name
            output_name_with_ext, output_name_base, _ = get_next_available_name(
                output_dir, "C", "_Concatenated.mp4", title="Concatenated"
            )
            output_path = os.path.join(output_dir, output_name_with_ext)

            # Run ffmpeg to concatenate with concat filter and fade-in
            ffmpeg_cmd = (
                f'ffmpeg {input_args} '
                f'-filter_complex "{filter_complex}" '
                f'-map "[vout]" -map "[a]" '  # Map the scaled video output
                f'-c:v libx264 -preset ultrafast -b:v 3500k '
                f'-r 30 '
                f'-c:a aac -b:a 128k -ar 44100 "{output_path}"'
            )
            debug_print(f"Debug: Running ffmpeg command: {ffmpeg_cmd}")
            success, output = run_command(ffmpeg_cmd, timeout=120, retries=1)  # 120-second timeout for concatenation
            if success:
                print(f"Saved Concatenated Video as {output_path.replace(os.sep, '/')}")
            else:
                print("Failed to concatenate videos")
                print(f"FFmpeg output: {output}")
                sys.exit(1)

    except Exception as e:
        print(f"Error: Unexpected issue during processing: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()