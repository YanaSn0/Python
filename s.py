import subprocess
import sys
import os
import argparse
import glob
import shutil
import json
import urllib.parse

def run_command(command, suppress_errors=False):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        if not suppress_errors:
            error_message = f"Error: {result.stderr}"
            print(error_message)
        return False, result.stderr
    return True, result.stderr if result.stderr else result.stdout

def get_next_available_name(output_dir, prefix, extension, start_num=1, force_num=False):
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
    cmd = (
        f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{file_path}"'
    )
    success, output = run_command(cmd)
    if success:
        try:
            return float(output.strip())
        except ValueError:
            print(f"Warning: Could not determine duration of {file_path}")
            return 0
    return 0

def has_audio_stream(file_path):
    cmd = (
        f'ffprobe -v error -show_streams -select_streams a -of default=noprint_wrappers=1 "{file_path}"'
    )
    success, output = run_command(cmd)
    return bool(output.strip())

def has_video_stream(file_path):
    cmd = (
        f'ffprobe -v error -show_streams -select_streams v -of default=noprint_wrappers=1 "{file_path}"'
    )
    success, output = run_command(cmd)
    return bool(output.strip())

def get_image_dimensions(image_path):
    cmd = (
        f'ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of json "{image_path}"'
    )
    success, output = run_command(cmd)
    if success:
        data = json.loads(output)
        width = data['streams'][0]['width']
        height = data['streams'][0]['height']
        return width, height
    return None, None

def get_video_dimensions(video_path):
    cmd = (
        f'ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of json "{video_path}"'
    )
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
    dir_name = os.path.dirname(image_path) or "."
    dir_name = os.path.abspath(dir_name)
    print(f"Looking for base name (lowercase): {base_name} in directory: {dir_name}")
    
    try:
        files = os.listdir(dir_name)
        print(f"Files in directory: {files}")
        for file in files:
            file_lower = file.lower()
            if file_lower.startswith(base_name) and os.path.splitext(file_lower)[1] in [ext.lower() for ext in extensions]:
                full_path = os.path.join(dir_name, file)
                print(f"Found matching file: {full_path}")
                return full_path
    except Exception as e:
        print(f"Error listing directory {dir_name}: {e}")
    return None

def find_video_file(video_path):
    extensions = ['.mp4', '.MP4']
    base_name = os.path.basename(video_path).lower()
    dir_name = os.path.dirname(video_path) or "."
    dir_name = os.path.abspath(dir_name)
    print(f"Looking for video base name (lowercase): {base_name} in directory: {dir_name}")
    
    try:
        files = os.listdir(dir_name)
        print(f"Files in directory: {files}")
        for file in files:
            file_lower = file.lower()
            if file_lower.startswith(base_name) and os.path.splitext(file_lower)[1] in [ext.lower() for ext in extensions]:
                full_path = os.path.join(dir_name, file)
                print(f"Found matching video file: {full_path}")
                return full_path
    except Exception as e:
        print(f"Error listing directory {dir_name}: {e}")
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
        if ar > 1.5:  # Close to 16:9 (1.777)
            categories['landscape'] += 1
        elif ar < 0.67:  # Close to 9:16 (0.5625)
            categories['portrait'] += 1
        else:  # Close to 1:1 (1.0)
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

def is_instagram_url(url):
    parsed_url = urllib.parse.urlparse(url)
    domain = parsed_url.netloc.lower()
    return 'instagram.com' in domain

def main():
    parser = argparse.ArgumentParser(description="Download, process, combine, create slideshows, or batch convert media files")
    subparsers = parser.add_subparsers(dest="mode", help="Mode of operation")

    parser_download = subparsers.add_parser("download", help="Download and process videos/images")
    parser_download.add_argument("submode", choices=["audio", "video", "combined", "split", "pic", "all", "all+a", "all+a+v", "all+v"],
                                 help="Submode: 'audio', 'video', 'combined', 'split', 'pic', 'all', 'all+a', 'all+a+v', or 'all+v'")
    parser_download.add_argument("--output-dir", "-o", default=".",
                                 help="Directory to save output files (default: current directory)")
    parser_download.add_argument("--keep-original", action="store_true",
                                 help="Keep the original format (skip FFmpeg conversion)")
    parser_download.add_argument("--clear-dir", action="store_true",
                                 help="Clear the output directory before starting downloads")
    parser_download.add_argument("--username", help="Username for yt-dlp authentication")
    parser_download.add_argument("--password", help="Password for yt-dlp authentication")
    parser_download.add_argument("--cookies", help="Path to cookies file for yt-dlp authentication")

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
    parser_slide.add_argument("delay", type=float, help="Delay in seconds for each image (e.g., 5)")
    parser_slide.add_argument("image_paths", nargs='+', help="Paths to image files (e.g., ./pictures/P1 ./pictures/P2)")
    parser_slide.add_argument("--output-dir", "-o",
                              help="Directory where output will be saved (default: same as first image directory)")

    parser_loop = subparsers.add_parser("loop", help="Loop an audio file to a specified duration")
    parser_loop.add_argument("audio_path", help="Path to the audio file (e.g., ./audio/A1 for A1.m4a)")
    parser_loop.add_argument("duration", type=float, help="Desired duration in seconds (e.g., 15)")
    parser_loop.add_argument("--output-dir", "-o",
                             help="Directory where output will be saved (default: same as audio file directory)")

    # New mode: trim_loop_from_video
    parser_trim_loop = subparsers.add_parser("trim_loop_from_video", help="Trim audio from a video and loop it to a specified duration")
    parser_trim_loop.add_argument("video_path", help="Path to the video file (e.g., ./videos/U1 for U1.mp4)")
    parser_trim_loop.add_argument("loop_duration", type=float, help="Desired duration of the final looped audio in seconds (e.g., 60)")
    parser_trim_loop.add_argument("--start", type=float, default=0, help="Start time in seconds (default: 0)")
    parser_trim_loop.add_argument("--trim-duration", type=float, help="Duration to trim in seconds (optional)")
    parser_trim_loop.add_argument("--end", type=float, help="End time in seconds (alternative to --trim-duration)")
    parser_trim_loop.add_argument("--last", type=float, help="Extract the last X seconds of the audio (e.g., --last 30)")
    parser_trim_loop.add_argument("--output-dir", "-o",
                                  help="Directory where output will be saved (default: same as video file directory)")

    parser_batch_convert = subparsers.add_parser("batch_convert", help="Convert existing videos to Universal format")
    parser_batch_convert.add_argument("input_dir", help="Directory containing input video files (e.g., ./videos)")
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
            print(f"\nConverting {video_file} to Universal format...")
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
                f'ffmpeg -i "{video_file}" -c:v libx264 -b:v 3500k '
                f'-vf "scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2" -r 30 '
                f'-c:a aac -b:a 128k -ar 44100 -t 140 "{output_path}"'
            )
            success, output = run_command(ffmpeg_cmd)
            if success:
                print(f"Saved Universal as {output_path}")
            else:
                print(f"Failed to convert {video_file}: {output}")

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
                extensions = ['.jpg', '.jpeg', '.png', '.webp', '.JPG', '.JPEG', '.PNG', '.WEBP']
                dir_name = os.path.abspath(os.path.dirname(image_path) or ".")
                base_name = os.path.basename(image_path)
                tried_paths = [os.path.join(dir_name, f"{base_name}{ext}") for ext in extensions]
                print(f"Error: Image file {image_path} not found. Tried: {', '.join(tried_paths)}")
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
                    print(f"Failed to process image {image_file}. FFmpeg output: {output}")
                    sys.exit(1)

            concat_list = os.path.join(temp_image_dir, "concat_list.txt")
            with open(concat_list, "w") as f:
                for i in range(len(image_files)):
                    f.write(f"file 'image_{i:03d}.jpg'\n")
                    f.write(f"duration {delay}\n")

            output_name_with_ext, output_name_base = get_next_available_name(output_dir, "S", ".mp4")[:2]
            output_name = os.path.join(output_dir, output_name_base)
            print(f"Creating slideshow video...")
            print(f"Output will be saved as {output_name_with_ext}")

            ffmpeg_cmd = (
                f'ffmpeg -f concat -safe 0 -i "{concat_list}" -c:v libx264 -profile:v baseline -level 4.0 -b:v 3500k -r 30 -pix_fmt yuv420p "{output_name}.mp4"'
            )
            success, output = run_command(ffmpeg_cmd)
            if not success:
                print(f"Failed to create slideshow video. FFmpeg output: {output}")
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
        if audio_duration == 0:
            print("Error: Could not determine audio duration. Proceeding without looping.")
            loop = 0
        else:
            loop = int(duration / audio_duration) + 1 if audio_duration < duration else 0
            print(f"Audio duration: {audio_duration} seconds, looping {loop} times to reach at least {duration} seconds.")

        output_name_with_ext, output_name_base = get_next_available_name(output_dir, "L", ".m4a")[:2]
        output_name = os.path.join(output_dir, output_name_base)
        print(f"Looping audio to {duration} seconds...")
        print(f"Output will be saved as {output_name_with_ext}")

        ffmpeg_cmd = (
            f'ffmpeg -stream_loop {loop} -i "{audio_path}" -c:a copy -t {duration} "{output_name}.m4a"'
        )
        success, output = run_command(ffmpeg_cmd)
        if not success:
            print(f"Failed to loop audio. FFmpeg output: {output}")
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
        if video_duration == 0 or audio_duration == 0:
            print("Error: Could not determine durations. Proceeding without looping.")
            loop = 0
        else:
            loop = int(video_duration / audio_duration) + 1 if audio_duration < video_duration else 0

        output_name_with_ext, output_name_base = get_next_available_name(output_dir, "C", ".mp4")[:2]
        output_name = os.path.join(output_dir, output_name_base)
        print(f"Combining {video_path} and {audio_path}...")
        print(f"Output will be saved as {output_name_with_ext}")

        ffmpeg_cmd = (
            f'ffmpeg -i "{video_path}" -stream_loop {loop} -i "{audio_path}" '
            f'-c:v libx264 -profile:v baseline -level 4.0 -b:v 3500k -r 30 -pix_fmt yuv420p '
            f'-c:a aac -b:a 128k -ar 44100 -shortest -t {video_duration if video_duration > 0 else 140} "{output_name}.mp4"'
        )
        success, output = run_command(ffmpeg_cmd)
        if not success:
            print(f"Failed to combine files. FFmpeg output: {output}")
            sys.exit(1)

        print(f"Done! Output saved in {output_dir}")
        return

    if mode == "split":
        input_path = args.input_path + ".mp4"
        output_dir = args.output_dir if args.output_dir else os.path.dirname(input_path)

        actual_input_path = find_video_file(args.input_path)
        if not actual_input_path:
            dir_name = os.path.abspath(os.path.dirname(input_path) or ".")
            base_name = os.path.basename(input_path)
            tried_paths = [os.path.join(dir_name, f"{base_name}{ext}") for ext in ['.mp4', '.MP4']]
            print(f"Error: Input file {input_path} not found. Tried: {', '.join(tried_paths)}")
            sys.exit(1)

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")

        cmd = (
            f'ffprobe -v error -show_streams -select_streams a -of default=noprint_wrappers=1 "{actual_input_path}"'
        )
        success, output = run_command(cmd)
        has_audio = bool(output.strip())

        video_name_with_ext, video_name_base = get_next_available_name(output_dir, "V", ".mp4")[:2]
        audio_name_with_ext, audio_name_base = get_next_available_name(output_dir, "A", ".m4a")[:2]
        video_output = os.path.join(output_dir, video_name_base)
        audio_output = os.path.join(output_dir, audio_name_base)

        print(f"Splitting {actual_input_path}...")
        print(f"Outputs will be saved as {video_name_with_ext} and {audio_name_with_ext if has_audio else '(no audio)'}")

        ffmpeg_video_cmd = (
            f'ffmpeg -i "{actual_input_path}" -c:v copy -an "{video_output}.mp4"'
        )
        success, output = run_command(ffmpeg_video_cmd)
        if not success:
            print(f"Failed to extract video.")
            sys.exit(1)

        if has_audio:
            ffmpeg_audio_cmd = (
                f'ffmpeg -i "{actual_input_path}" -vn -c:a copy "{audio_output}.m4a"'
            )
            success, output = run_command(ffmpeg_audio_cmd)
            if not success:
                print(f"Failed to extract audio.")
                if os.path.exists(f"{video_output}.mp4"):
                    os.remove(f"{video_output}.mp4")
                sys.exit(1)
        else:
            print("No audio stream found in the input file.")

        print(f"Done! Output(s) saved in {output_dir}")
        return

    if mode == "trim_loop_from_video":
        video_path = args.video_path + ".mp4"
        loop_duration = args.loop_duration
        output_dir = args.output_dir if args.output_dir else os.path.dirname(video_path)
        start_time = args.start
        trim_duration = args.trim_duration
        end_time = args.end
        last_duration = args.last

        actual_video_path = find_video_file(args.video_path)
        if not actual_video_path:
            dir_name = os.path.abspath(os.path.dirname(video_path) or ".")
            base_name = os.path.basename(video_path)
            tried_paths = [os.path.join(dir_name, f"{base_name}{ext}") for ext in ['.mp4', '.MP4']]
            print(f"Error: Video file {video_path} not found. Tried: {', '.join(tried_paths)}")
            sys.exit(1)

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")

        # Check if the video has an audio stream
        if not has_audio_stream(actual_video_path):
            print(f"Error: No audio stream found in the video file {actual_video_path}.")
            sys.exit(1)

        # Get the total duration of the video (and its audio)
        video_duration = get_file_duration(actual_video_path)
        if video_duration == 0:
            print("Error: Could not determine video duration. Cannot proceed.")
            sys.exit(1)

        # Handle --last flag
        if last_duration is not None:
            if last_duration <= 0 or last_duration > video_duration:
                print(f"Error: Last duration ({last_duration}) must be positive and less than video duration ({video_duration}).")
                sys.exit(1)
            start_time = video_duration - last_duration
            trim_duration = last_duration
        else:
            # Determine the trim duration
            if end_time is not None and trim_duration is None:
                if end_time <= start_time or end_time > video_duration:
                    print(f"Error: End time ({end_time}) must be greater than start time ({start_time}) and less than video duration ({video_duration}).")
                    sys.exit(1)
                trim_duration = end_time - start_time
            elif trim_duration is None:
                # Default to the remaining duration from start_time
                trim_duration = video_duration - start_time
                if trim_duration <= 0:
                    print(f"Error: Start time ({start_time}) must be less than video duration ({video_duration}).")
                    sys.exit(1)
            else:
                if start_time + trim_duration > video_duration:
                    print(f"Error: Start time ({start_time}) + trim duration ({trim_duration}) exceeds video duration ({video_duration}).")
                    sys.exit(1)

        # Calculate looping based on the trimmed duration
        loop = int(loop_duration / trim_duration) + 1 if trim_duration < loop_duration else 0
        print(f"Trimmed audio duration: {trim_duration} seconds, looping {loop} times to reach at least {loop_duration} seconds.")

        output_name_with_ext, output_name_base = get_next_available_name(output_dir, "L", ".m4a")[:2]
        output_name = os.path.join(output_dir, output_name_base)
        print(f"Extracting and looping audio to {loop_duration} seconds...")
        print(f"Output will be saved as {output_name_with_ext}")

        # Extract and trim the audio directly from the video
        temp_audio_path = os.path.join(output_dir, "temp_extracted.m4a")
        ffmpeg_extract_trim_cmd = (
            f'ffmpeg -i "{actual_video_path}" -vn -ss {start_time} -t {trim_duration} -c:a copy "{temp_audio_path}"'
        )
        success, output = run_command(ffmpeg_extract_trim_cmd)
        if not success:
            print(f"Failed to extract and trim audio from video. FFmpeg output: {output}")
            sys.exit(1)

        # Loop the trimmed audio
        ffmpeg_cmd = (
            f'ffmpeg -stream_loop {loop} -i "{temp_audio_path}" -c:a copy -t {loop_duration} "{output_name}.m4a"'
        )
        success, output = run_command(ffmpeg_cmd)
        if not success:
            print(f"Failed to loop audio. FFmpeg output: {output}")
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
            sys.exit(1)

        # Clean up the temporary file
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

        print(f"Done! Output saved in {output_dir}")
        return

    # Download mode (audio, video, combined, split, pic, all, all+a, all+a+v, all+v)
    submode = args.submode
    output_dir = args.output_dir
    keep_original = args.keep_original
    clear_dir = args.clear_dir
    username = args.username
    password = args.password
    cookies = args.cookies

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
        print(f"Error: {url_file} not found. Create a file named {url_file} with URLs.")
        print("URLs can be one per line or multiple per line separated by semicolons (;).")
        sys.exit(1)

    urls = []
    with open(url_file, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                line_urls = [url.strip() for url in line.split(";") if url.strip()]
                urls.extend(line_urls)

    if not urls:
        print(f"Error: {url_file} is empty. Add URLs to the file.")
        sys.exit(1)

    unique_urls = list(dict.fromkeys(urls))
    if len(unique_urls) < len(urls):
        print(f"Removed {len(urls) - len(unique_urls)} duplicate URLs from processing.")

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
            elif submode == "combined":
                prefix = "O" if keep_original else "U"
                extension = ".mp4"
            elif submode == "split":
                prefix = "O" if keep_original else "U"
                extension = "_video.mp4"
            else:
                pass

            if submode not in ["all", "all+a", "all+a+v", "all+v"]:
                output_name_with_ext, output_name_base = get_next_available_name(output_dir, prefix, extension)[:2]
                output_name = os.path.join(output_dir, output_name_base)

            if submode == "audio":
                print(f"Output will be saved as {output_name_with_ext}")
            elif submode == "video" or submode == "combined":
                print(f"Output will be saved as {output_name_with_ext}")
            elif submode == "split":
                print(f"Outputs will be saved as {output_name}_video.mp4 and {output_name}_audio.m4a")
            elif submode == "pic":
                print(f"Output will be saved as {output_name_with_ext}")
            else:
                print("Checking for Original, Picture, Video, or Audio...")

            if username and password:
                auth = f"--username {username} --password {password}"
            elif cookies:
                auth = f"--cookies {cookies}"
            else:
                auth = "--cookies-from-browser firefox"

            if submode in ["all", "all+a", "all+a+v", "all+v"]:
                if 'O' not in processed_urls[url]:
                    video_prefix = "O" if keep_original else "U"
                    output_name_with_ext, output_name_base, current_o_number = get_next_available_name(output_dir, video_prefix, ".mp4", start_num=current_o_number)
                    output_name = os.path.join(output_dir, output_name_base)
                    output_path = os.path.join(output_dir, output_name_with_ext)

                    yt_dlp_cmd = (
                        f'yt-dlp {auth} -f "bestvideo+bestaudio/best" --merge-output-format mp4 -o "{temp_file}" "{url}"'
                    )
                    success, output = run_command(yt_dlp_cmd, suppress_errors=True)
                    if os.path.exists(temp_file):
                        success = True
                        print(f"Video download succeeded: {temp_file} exists.")
                    else:
                        success = False
                        print(f"Video download failed: {url}")
                        if "No video formats found" in output:
                            print("No video formats available for this URL.")
                        else:
                            print(f"Error details: {output}")
                            print("Unexpected error during video download. Check authentication or URL validity.")

                    if success:
                        if keep_original:
                            cmd = (
                                f'ffprobe -v error -show_streams -select_streams v:0 -show_entries stream=codec_name -of json "{temp_file}"'
                            )
                            success, output = run_command(cmd)
                            video_codec = None
                            if success:
                                data = json.loads(output)
                                if data.get('streams'):
                                    video_codec = data['streams'][0].get('codec_name')

                            cmd = (
                                f'ffprobe -v error -show_streams -select_streams a:0 -show_entries stream=codec_name -of json "{temp_file}"'
                            )
                            success, output = run_command(cmd)
                            audio_codec = None
                            if success:
                                data = json.loads(output)
                                if data.get('streams'):
                                    audio_codec = data['streams'][0].get('codec_name')

                            if video_codec == 'h264' and (audio_codec == 'aac' or not audio_codec):
                                os.rename(temp_file, output_path)
                                print(f"Saved Original as {output_path}")
                            else:
                                print("Original video has incompatible codecs (requires H.264/AAC). Converting...")
                                width, height = get_video_dimensions(temp_file)
                                width = width + (width % 2)
                                height = height + (height % 2)
                                ffmpeg_cmd = (
                                    f'ffmpeg -i "{temp_file}" -c:v libx264 -b:v 3500k '
                                    f'-vf "scale={width}:{height}:force_original_aspect_ratio=decrease" -r 30 '
                                    f'-c:a aac -b:a 128k -ar 44100 -t 140 "{output_path}"'
                                )
                                success, output = run_command(ffmpeg_cmd)
                                if success:
                                    if os.path.exists(temp_file):
                                        os.remove(temp_file)
                                    print(f"Saved Converted Original as {output_path}")
                                else:
                                    print(f"Failed to convert: {url}")
                                    if os.path.exists(temp_file):
                                        os.remove(temp_file)
                                    continue
                        else:
                            print("Converting to universal combined format...")
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
                                f'ffmpeg -i "{temp_file}" -c:v libx264 -b:v 3500k '
                                f'-vf "scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2" -r 30 '
                                f'-c:a aac -b:a 128k -ar 44100 -t 140 "{output_path}"'
                            )
                            success, output = run_command(ffmpeg_cmd)
                            if success:
                                if os.path.exists(temp_file):
                                    os.remove(temp_file)
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
                        print("Skipping picture download for video platform after video/audio attempt...")
                    else:
                        print("Video download failed or skipped, attempting to download picture...")
                        output_name_with_ext, output_name_base, current_p_number = get_next_available_name(output_dir, "P", ".jpg", start_num=current_p_number)
                        output_name = os.path.join(output_dir, output_name_base)
                        output_path = os.path.join(output_dir, output_name_with_ext)

                        if os.path.exists(temp_image_dir):
                            shutil.rmtree(temp_image_dir)
                        os.makedirs(temp_image_dir)
                        gallery_dl_cmd = (
                            f'gallery-dl --cookies-from-browser firefox -D "{temp_image_dir}" "{url}"'
                        )
                        success, output = run_command(gallery_dl_cmd)
                        if success:
                            image_files = sorted(glob.glob(os.path.join(temp_image_dir, "*")))
                            if image_files:
                                image_file = image_files[0]
                                if keep_original:
                                    ext = os.path.splitext(image_file)[1]
                                    os.rename(image_file, output_path)
                                    print(f"Saved Picture as {output_path}")
                                else:
                                    ffmpeg_cmd = (
                                        f'ffmpeg -i "{image_file}" "{output_path}"'
                                    )
                                    success, output = run_command(ffmpeg_cmd)
                                    if success:
                                        os.remove(image_file)
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
                                shutil.rmtree(temp_image_dir)
                        else:
                            print(f"Failed to download picture: {url}")
                            if os.path.exists(temp_image_dir):
                                shutil.rmtree(temp_image_dir)

                if 'V' not in processed_urls[url] and 'O' not in processed_urls[url] and 'P' not in processed_urls[url]:
                    print("Picture download failed or skipped, attempting to download video-only...")
                    output_name_with_ext, output_name_base, current_v_number = get_next_available_name(output_dir, "V", ".mp4", start_num=current_v_number)
                    output_name = os.path.join(output_dir, output_name_base)
                    output_path = os.path.join(output_dir, output_name_with_ext)

                    yt_dlp_cmd = (
                        f'yt-dlp {auth} -f "bestvideo[ext=mp4]" --merge-output-format mp4 -o "{temp_file}" "{url}"'
                    )
                    success, output = run_command(yt_dlp_cmd)
                    if success and os.path.exists(temp_file):
                        if keep_original:
                            os.rename(temp_file, output_path)
                            print(f"Saved Video as {output_path}")
                        else:
                            print("Converting to universal video-only format...")
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
                                f'ffmpeg -i "{temp_file}" -c:v libx264 -b:v 3500k '
                                f'-vf "scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2" -r 30 '
                                f'-an -t 140 "{output_path}"'
                            )
                            success, output = run_command(ffmpeg_cmd)
                            if success:
                                if os.path.exists(temp_file):
                                    os.remove(temp_file)
                                print(f"Saved Video as {output_path}")
                            else:
                                print(f"Failed to convert video: {url}")
                                if os.path.exists(temp_file):
                                    os.remove(temp_file)
                                continue
                        processed_urls[url].append('V')
                        if submode == "all":
                            continue

                if 'A' not in processed_urls[url] and 'O' not in processed_urls[url] and 'P' not in processed_urls[url]:
                    print("Video-only download failed, attempting to download audio...")
                    output_name_with_ext, output_name_base, current_a_number = get_next_available_name(output_dir, "A", ".m4a", start_num=audio_counter, force_num=True)
                    output_name = os.path.join(output_dir, output_name_base)
                    output_path = os.path.join(output_dir, output_name_with_ext)

                    yt_dlp_cmd = (
                        f'yt-dlp {auth} -f "bestaudio/best" -o "{temp_audio_file}" "{url}"'
                    )
                    success, output = run_command(yt_dlp_cmd)
                    if success and os.path.exists(temp_audio_file):
                        has_video = has_video_stream(temp_audio_file)
                        has_audio = has_audio_stream(temp_audio_file)
                        if has_video and has_audio and 'O' not in processed_urls[url]:
                            print("Downloaded file contains both video and audio streams, treating as original...")
                            video_prefix = "O" if keep_original else "U"
                            video_output_name_with_ext, video_output_name_base, current_o_number = get_next_available_name(output_dir, video_prefix, ".mp4", start_num=current_o_number)
                            video_output_path = os.path.join(output_dir, video_output_name_with_ext)
                            if keep_original:
                                os.rename(temp_audio_file, video_output_path)
                                print(f"Saved Original as {video_output_path}")
                            else:
                                print("Converting to universal combined format...")
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
                                    f'ffmpeg -i "{temp_audio_file}" -c:v libx264 -b:v 3500k '
                                    f'-vf "scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2" -r 30 '
                                    f'-c:a aac -b:a 128k -ar 44100 -t 140 "{video_output_path}"'
                                )
                                success, output = run_command(ffmpeg_cmd)
                                if success:
                                    if os.path.exists(temp_audio_file):
                                        os.remove(temp_audio_file)
                                    print(f"Saved Original as {video_output_path}")
                                else:
                                    print(f"Failed to convert video: {url}")
                                    if os.path.exists(temp_audio_file):
                                        os.remove(temp_audio_file)
                                    continue
                            video_downloaded_path = video_output_path
                            processed_urls[url].append('O')
                        elif has_video and 'V' not in processed_urls[url]:
                            print("Downloaded file contains a video stream, treating as video...")
                            video_output_name_with_ext, video_output_name_base, current_v_number = get_next_available_name(output_dir, "V", ".mp4", start_num=current_v_number)
                            video_output_path = os.path.join(output_dir, video_output_name_with_ext)
                            if keep_original:
                                os.rename(temp_audio_file, video_output_path)
                                print(f"Saved Video as {video_output_path}")
                            else:
                                print("Converting to universal video-only format...")
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
                                    f'ffmpeg -i "{temp_audio_file}" -c:v libx264 -b:v 3500k '
                                    f'-vf "scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2" -r 30 '
                                    f'-t 140 "{video_output_path}"'
                                )
                                success, output = run_command(ffmpeg_cmd)
                                if success:
                                    if os.path.exists(temp_audio_file):
                                        os.remove(temp_audio_file)
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
                            success, output = run_command(ffmpeg_cmd)
                            if success:
                                print(f"Saved Audio as {output_path}")
                                audio_counter += 1
                                if os.path.exists(temp_audio_file):
                                    os.remove(temp_audio_file)
                                processed_urls[url].append('A')
                            else:
                                print(f"Failed to convert audio to m4a: {url}")
                                if os.path.exists(temp_audio_file):
                                    os.remove(temp_audio_file)
                                continue
                    else:
                        print(f"Failed to download audio: {url}")
                        print(f"Try debugging with: yt-dlp --list-formats {url}")
                        if os.path.exists(temp_audio_file):
                            os.remove(temp_audio_file)
                        continue

                if submode in ["all+a", "all+a+v"] and 'A' not in processed_urls[url]:
                    if 'O' in processed_urls[url] and video_downloaded_path and has_audio_stream(video_downloaded_path):
                        output_name_with_ext, output_name_base, current_a_number = get_next_available_name(output_dir, "A", ".m4a", start_num=audio_counter, force_num=True)
                        output_name = os.path.join(output_dir, output_name_base)
                        output_path = os.path.join(output_dir, output_name_with_ext)

                        print(f"Extracting audio from existing video: {video_downloaded_path}")
                        ffmpeg_cmd = (
                            f'ffmpeg -i "{video_downloaded_path}" -vn -c:a aac -b:a 128k "{output_path}"'
                        )
                        success, output = run_command(ffmpeg_cmd)
                        if success:
                            print(f"Saved Audio as {output_path}")
                            audio_counter += 1
                            processed_urls[url].append('A')
                        else:
                            print(f"Failed to extract audio from video: {video_downloaded_path}")
                    else:
                        if 'P' in processed_urls[url]:
                            print("Skipping audio download as a picture was already downloaded for this URL...")
                            continue

                        output_name_with_ext, output_name_base, current_a_number = get_next_available_name(output_dir, "A", ".m4a", start_num=audio_counter, force_num=True)
                        output_name = os.path.join(output_dir, output_name_base)
                        output_path = os.path.join(output_dir, output_name_with_ext)

                        print("Attempting to download separate audio...")
                        yt_dlp_cmd = (
                            f'yt-dlp {auth} -f "bestaudio/best" -o "{temp_audio_file}" "{url}"'
                        )
                        success, output = run_command(yt_dlp_cmd)
                        if success and os.path.exists(temp_audio_file):
                            has_video = has_video_stream(temp_audio_file)
                            has_audio = has_audio_stream(temp_audio_file)
                            if has_video and has_audio and 'O' not in processed_urls[url]:
                                print("Downloaded file contains both video and audio streams, treating as original...")
                                video_prefix = "O" if keep_original else "U"
                                video_output_name_with_ext, video_output_name_base, current_o_number = get_next_available_name(output_dir, video_prefix, ".mp4", start_num=current_o_number)
                                video_output_path = os.path.join(output_dir, video_output_name_with_ext)
                                if keep_original:
                                    os.rename(temp_audio_file, video_output_path)
                                    print(f"Saved Original as {video_output_path}")
                                else:
                                    print("Converting to universal combined format...")
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
                                        f'ffmpeg -i "{temp_audio_file}" -c:v libx264 -b:v 3500k '
                                        f'-vf "scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2" -r 30 '
                                        f'-c:a aac -b:a 128k -ar 44100 -t 140 "{video_output_path}"'
                                    )
                                    success, output = run_command(ffmpeg_cmd)
                                    if success:
                                        if os.path.exists(temp_audio_file):
                                            os.remove(temp_audio_file)
                                        print(f"Saved Original as {video_output_path}")
                                    else:
                                        print(f"Failed to convert video: {url}")
                                        if os.path.exists(temp_audio_file):
                                            os.remove(temp_audio_file)
                                        continue
                                video_downloaded_path = video_output_path
                                processed_urls[url].append('O')
                                if submode in ["all+a", "all+a+v"]:
                                    print(f"Extracting audio from newly downloaded video: {video_downloaded_path}")
                                    ffmpeg_cmd = (
                                        f'ffmpeg -i "{video_downloaded_path}" -vn -c:a aac -b:a 128k "{output_path}"'
                                    )
                                    success, output = run_command(ffmpeg_cmd)
                                    if success:
                                        print(f"Saved Audio as {output_path}")
                                        audio_counter += 1
                                        processed_urls[url].append('A')
                                    else:
                                        print(f"Failed to extract audio from video: {video_downloaded_path}")
                            elif has_video and 'V' not in processed_urls[url]:
                                print("Downloaded file contains a video stream, treating as video...")
                                video_output_name_with_ext, video_output_name_base, current_v_number = get_next_available_name(output_dir, "V", ".mp4", start_num=current_v_number)
                                video_output_path = os.path.join(output_dir, video_output_name_with_ext)
                                if keep_original:
                                    os.rename(temp_audio_file, video_output_path)
                                    print(f"Saved Video as {video_output_path}")
                                else:
                                    print("Converting to universal video-only format...")
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
                                        f'ffmpeg -i "{temp_audio_file}" -c:v libx264 -b:v 3500k '
                                        f'-vf "scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2" -r 30 '
                                        f'-t 140 "{video_output_path}"'
                                    )
                                    success, output = run_command(ffmpeg_cmd)
                                    if success:
                                        if os.path.exists(temp_audio_file):
                                            os.remove(temp_audio_file)
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
                                success, output = run_command(ffmpeg_cmd)
                                if success:
                                    print(f"Saved Audio as {output_path}")
                                    audio_counter += 1
                                    if os.path.exists(temp_audio_file):
                                        os.remove(temp_audio_file)
                                    processed_urls[url].append('A')
                                else:
                                    print(f"Failed to convert audio to m4a: {url}")
                                    if os.path.exists(temp_audio_file):
                                        os.remove(temp_audio_file)
                        else:
                            print(f"Failed to download separate audio: {url}")
                            print(f"Try debugging with: yt-dlp --list-formats {url}")
                            if os.path.exists(temp_audio_file):
                                os.remove(temp_audio_file)

                if submode in ["all+a+v", "all+v"] and 'O' in processed_urls[url] and 'V' not in processed_urls[url]:
                    output_name_with_ext, output_name_base, current_v_number = get_next_available_name(output_dir, "V", ".mp4", start_num=current_v_number)
                    output_name = os.path.join(output_dir, output_name_base)
                    output_path = os.path.join(output_dir, output_name_with_ext)

                    print(f"Splitting video to remove audio from: {video_downloaded_path}")
                    ffmpeg_cmd = (
                        f'ffmpeg -i "{video_downloaded_path}" -c:v copy -an "{output_path}"'
                    )
                    success, output = run_command(ffmpeg_cmd)
                    if success:
                        print(f"Saved Video-only as {output_path}")
                        processed_urls[url].append('V')
                    else:
                        print(f"Failed to split video to remove audio: {video_downloaded_path}")

        finally:
            if os.path.exists(temp_file):
                print("Cleaning up temporary video file...")
                os.remove(temp_file)
            if os.path.exists(temp_audio_file):
                print("Cleaning up temporary audio file...")
                os.remove(temp_audio_file)
            if os.path.exists(temp_image_dir):
                print("Cleaning up temporary image directory...")
                shutil.rmtree(temp_image_dir)

    print(f"Done! Outputs saved in {output_dir}")

if __name__ == "__main__":
    main()
