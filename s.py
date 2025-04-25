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
            print(f"Error: {result.stderr}! You may need to ensure you're logged into the platform on Firefox or use --username and --password with yt-dlp.")
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

def find_image_file(image_path):
    extensions = ['.jpg', '.jpeg', '.png', '.webp']
    for ext in extensions:
        full_path = image_path + ext
        if os.path.exists(full_path):
            return full_path
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
    """Determine if the URL is from a platform where the primary content is typically a video."""
    video_domains = ['youtube.com', 'youtu.be', 'tiktok.com', 'vimeo.com', 'dailymotion.com', 'x.com', 'twitter.com']
    parsed_url = urllib.parse.urlparse(url)
    domain = parsed_url.netloc.lower()
    return any(video_domain in domain for video_domain in video_domains)

def is_instagram_url(url):
    """Determine if the URL is from Instagram."""
    parsed_url = urllib.parse.urlparse(url)
    domain = parsed_url.netloc.lower()
    return 'instagram.com' in domain

def main():
    parser = argparse.ArgumentParser(description="Download, process, combine, or create slideshows from media files")
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

    args = parser.parse_args()
    mode = args.mode

    if mode == "slide":
        delay = args.delay
        image_paths = args.image_paths
        output_dir = args.output_dir if args.output_dir else os.path.dirname(image_paths[0])

        image_files = []
        for image_path in image_paths:
            image_file = find_image_file(image_path)
            if not image_file:
                print(f"Error: Image file {image_path} not found (tried .jpg, .jpeg, .png, .webp).")
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
                    print(f"Failed to process image {image_file}.")
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
                f'ffmpeg -f concat -safe 0 -i "{concat_list}" -c:v libx264 -b:v 3500k -r 30 -pix_fmt yuv420p "{output_name}.mp4"'
            )
            success, output = run_command(ffmpeg_cmd)
            if not success:
                print(f"Failed to create slideshow video.")
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

        output_name_with_ext, output_name_base = get_next_available_name(output_dir, "L", ".m4a")[:2]
        output_name = os.path.join(output_dir, output_name_base)
        print(f"Looping audio to {duration} seconds...")
        print(f"Output will be saved as {output_name_with_ext}")

        ffmpeg_cmd = (
            f'ffmpeg -i "{audio_path}" -stream_loop {loop} -c:a copy -t {duration} "{output_name}.m4a"'
        )
        success, output = run_command(ffmpeg_cmd)
        if not success:
            print(f"Failed to loop audio.")
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
            f'ffmpeg -i "{video_path}" -stream_loop {loop} -i "{audio_path}" -c:v copy '
            f'-c:a aac -b:a 128k -ar 44100 -shortest -t {video_duration if video_duration > 0 else 140} "{output_name}.mp4"'
        )
        success, output = run_command(ffmpeg_cmd)
        if not success:
            print(f"Failed to combine files.")
            sys.exit(1)

        print(f"Done! Output saved in {output_dir}")
        return

    if mode == "split":
        input_path = args.input_path + ".mp4"
        output_dir = args.output_dir if args.output_dir else os.path.dirname(input_path)

        if not os.path.exists(input_path):
            print(f"Error: Input file {input_path} not found.")
            sys.exit(1)

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")

        cmd = (
            f'ffprobe -v error -show_streams -select_streams a -of default=noprint_wrappers=1 "{input_path}"'
        )
        success, output = run_command(cmd)
        has_audio = bool(output.strip())

        video_name_with_ext, video_name_base = get_next_available_name(output_dir, "V", ".mp4")[:2]
        audio_name_with_ext, audio_name_base = get_next_available_name(output_dir, "A", ".m4a")[:2]
        video_output = os.path.join(output_dir, video_name_base)
        audio_output = os.path.join(output_dir, audio_name_base)

        print(f"Splitting {input_path}...")
        print(f"Outputs will be saved as {video_name_with_ext} and {audio_name_with_ext if has_audio else '(no audio)'}")

        ffmpeg_video_cmd = (
            f'ffmpeg -i "{input_path}" -c:v copy -an "{video_output}.mp4"'
        )
        success, output = run_command(ffmpeg_cmd)
        if not success:
            print(f"Failed to extract video.")
            sys.exit(1)

        if has_audio:
            ffmpeg_audio_cmd = (
                f'ffmpeg -i "{input_path}" -vn -c:a copy "{audio_output}.m4a"'
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

    # Deduplicate URLs to prevent processing the same URL multiple times
    unique_urls = list(dict.fromkeys(urls))  # Preserves order while removing duplicates
    if len(unique_urls) < len(urls):
        print(f"Removed {len(urls) - len(unique_urls)} duplicate URLs from processing.")

    temp_file = os.path.join(output_dir, "temp_download.mp4")
    temp_audio_file = os.path.join(output_dir, "temp_audio.m4a")
    temp_image_dir = os.path.join(output_dir, "temp_images")

    current_v_number = 1  # For video-only downloads (V1 to V5)
    current_o_number = 1  # For videos with audio (O1 to O5 or U1 to U5)
    current_a_number = 1  # For audio (A1 to A5)
    current_p_number = 1  # For pictures (P1)
    audio_counter = 1     # To track the sequence of successful audio downloads

    # Track processed URLs and their output types to avoid duplicates
    processed_urls = {}  # URL -> list of output types ('O', 'P', 'V', 'A')

    for index, url in enumerate(unique_urls):
        print(f"\nProcessing {submode} {index + 1}/{len(unique_urls)}: {url}")

        # Initialize the list of output types for this URL
        if url not in processed_urls:
            processed_urls[url] = []

        # Reset video_downloaded_path for this URL
        video_downloaded_path = None

        # Clean up temporary files from previous iterations
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
            else:  # all, all+a, all+a+v, all+v
                # We'll set prefixes dynamically in the loop
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
            else:  # all, all+a, all+a+v, all+v
                print("Checking for Original, Picture, Video, or Audio...")

            # Determine authentication method
            if username and password:
                auth = f"--username {username} --password {password}"
            elif cookies:
                auth = f"--cookies {cookies}"
            else:
                auth = "--cookies-from-browser firefox"

            if submode in ["all", "all+a", "all+a+v", "all+v"]:
                # Step 1: Try to download full video (O1.mp4 to O5.mp4 or U1.mp4 to U5.mp4)
                if 'O' not in processed_urls[url]:
                    video_prefix = "O" if keep_original else "U"
                    output_name_with_ext, output_name_base, current_o_number = get_next_available_name(output_dir, video_prefix, ".mp4", start_num=current_o_number)
                    output_name = os.path.join(output_dir, output_name_base)
                    output_path = os.path.join(output_dir, output_name_with_ext)

                    yt_dlp_cmd = (
                        f'yt-dlp '  # Assumes yt-dlp is in the system PATH
                        f'{auth} -f "bestvideo+bestaudio/best" --merge-output-format mp4 -o "{temp_file}" "{url}"'
                    )
                    # Run the command with error suppression to avoid premature failure messages
                    success, output = run_command(yt_dlp_cmd, suppress_errors=True)
                    # Check if the file was actually created, regardless of the command's reported success
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
                            os.rename(temp_file, output_path)
                            print(f"Saved Original as {output_path}")
                        else:
                            print("Converting to universal combined format...")
                            ffmpeg_cmd = (
                                f'ffmpeg -i "{temp_file}" -c:v libx264 -b:v 3500k '
                                f'-vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2" -r 30 '
                                f'-c:a aac -b:a 128k -ar 44100 -t 140 "{output_path}"'
                            )
                            success, output = run_command(ffmpeg_cmd)
                            if success:
                                if os.path.exists(temp_file):
                                    os.remove(temp_file)
                                print(f"Saved Original as {output_path}")
                            else:
                                print(f"Failed to convert: {url}")
                                if os.path.exists(temp_file):
                                    os.remove(temp_file)
                                continue
                        video_downloaded_path = output_path  # Store the path for potential audio extraction or splitting
                        processed_urls[url].append('O')

                # If an 'O' file was saved, skip Steps 2, 3, and 4
                if 'O' in processed_urls[url]:
                    if submode in ["all+a", "all+a+v", "all+v"]:
                        # Proceed to audio extraction (for all+a, all+a+v) or video splitting (for all+a+v, all+v) below
                        pass
                    else:
                        continue  # In 'all' mode, we're done with this URL

                # Step 2: If video fails, try to download picture (P1.jpg)
                if 'P' not in processed_urls[url] and 'O' not in processed_urls[url]:
                    # Skip picture download for video platforms if video/audio was attempted
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
                                image_file = image_files[0]  # Take the first image
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
                                    continue  # Picture downloaded, skip other steps unless in all+a, all+a+v, or all+v mode
                            else:
                                shutil.rmtree(temp_image_dir)
                        else:
                            print(f"Failed to download picture: {url}")
                            if os.path.exists(temp_image_dir):
                                shutil.rmtree(temp_image_dir)

                # Step 3: If picture fails or is skipped, try to download video-only (V1.mp4 to V5.mp4)
                if 'V' not in processed_urls[url] and 'O' not in processed_urls[url] and 'P' not in processed_urls[url]:
                    print("Picture download failed or skipped, attempting to download video-only...")
                    output_name_with_ext, output_name_base, current_v_number = get_next_available_name(output_dir, "V", ".mp4", start_num=current_v_number)
                    output_name = os.path.join(output_dir, output_name_base)
                    output_path = os.path.join(output_dir, output_name_with_ext)

                    yt_dlp_cmd = (
                        f'yt-dlp '  # Assumes yt-dlp is in the system PATH
                        f'{auth} -f "bestvideo[ext=mp4]" --merge-output-format mp4 -o "{temp_file}" "{url}"'
                    )
                    success, output = run_command(yt_dlp_cmd)
                    if success and os.path.exists(temp_file):
                        if keep_original:
                            os.rename(temp_file, output_path)
                            print(f"Saved Video as {output_path}")
                        else:
                            print("Converting to universal video-only format...")
                            ffmpeg_cmd = (
                                f'ffmpeg -i "{temp_file}" -c:v libx264 -b:v 3500k '
                                f'-vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2" -r 30 '
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
                            continue  # Video-only downloaded, skip other steps unless in all+a, all+a+v, or all+v mode

                # Step 4: If video-only fails, try to download audio (A1.m4a to A5.m4a)
                if 'A' not in processed_urls[url] and 'O' not in processed_urls[url] and 'P' not in processed_urls[url]:
                    print("Video-only download failed, attempting to download audio...")
                    output_name_with_ext, output_name_base, current_a_number = get_next_available_name(output_dir, "A", ".m4a", start_num=audio_counter, force_num=True)
                    output_name = os.path.join(output_dir, output_name_base)
                    output_path = os.path.join(output_dir, output_name_with_ext)

                    yt_dlp_cmd = (
                        f'yt-dlp '  # Assumes yt-dlp is in the system PATH
                        f'{auth} -f "bestaudio/best" -o "{temp_audio_file}" "{url}"'
                    )
                    success, output = run_command(yt_dlp_cmd)
                    if success and os.path.exists(temp_audio_file):
                        # Check if the downloaded file has a video stream
                        has_video = has_video_stream(temp_audio_file)
                        has_audio = has_audio_stream(temp_audio_file)
                        if has_video and has_audio and 'O' not in processed_urls[url]:
                            print("Downloaded file contains both video and audio streams, treating as original...")
                            # Treat as an original file (save as O#.mp4)
                            video_prefix = "O" if keep_original else "U"
                            video_output_name_with_ext, video_output_name_base, current_o_number = get_next_available_name(output_dir, video_prefix, ".mp4", start_num=current_o_number)
                            video_output_path = os.path.join(output_dir, video_output_name_with_ext)
                            if keep_original:
                                os.rename(temp_audio_file, video_output_path)
                                print(f"Saved Original as {video_output_path}")
                            else:
                                print("Converting to universal combined format...")
                                ffmpeg_cmd = (
                                    f'ffmpeg -i "{temp_audio_file}" -c:v libx264 -b:v 3500k '
                                    f'-vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2" -r 30 '
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
                            video_downloaded_path = video_output_path  # Store for potential audio extraction or splitting
                            processed_urls[url].append('O')
                        elif has_video and 'V' not in processed_urls[url]:
                            print("Downloaded file contains a video stream, treating as video...")
                            # Treat as a video file (save as V#.mp4)
                            video_output_name_with_ext, video_output_name_base, current_v_number = get_next_available_name(output_dir, "V", ".mp4", start_num=current_v_number)
                            video_output_path = os.path.join(output_dir, video_output_name_with_ext)
                            if keep_original:
                                os.rename(temp_audio_file, video_output_path)
                                print(f"Saved Video as {video_output_path}")
                            else:
                                print("Converting to universal video-only format...")
                                ffmpeg_cmd = (
                                    f'ffmpeg -i "{temp_audio_file}" -c:v libx264 -b:v 3500k '
                                    f'-vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2" -r 30 '
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
                            # No video stream, treat as audio
                            ffmpeg_cmd = (
                                f'ffmpeg -i "{temp_audio_file}" -c:a aac -b:a 128k "{output_path}"'
                            )
                            success, output = run_command(ffmpeg_cmd)
                            if success:
                                print(f"Saved Audio as {output_path}")
                                audio_counter += 1  # Increment only on successful audio download
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
                        continue  # Audio downloaded or failed, move to next URL

                # Step 5: In all+a or all+a+v mode, attempt to extract audio if not already done
                if submode in ["all+a", "all+a+v"] and 'A' not in processed_urls[url]:
                    # If an 'O' file exists, extract audio from it
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
                            audio_counter += 1  # Increment on successful audio extraction
                            processed_urls[url].append('A')
                        else:
                            print(f"Failed to extract audio from video: {video_downloaded_path}")
                    else:
                        # If no 'O' file, try downloading audio separately (but only if no 'P' file exists)
                        if 'P' in processed_urls[url]:
                            print("Skipping audio download as a picture was already downloaded for this URL...")
                            continue

                        output_name_with_ext, output_name_base, current_a_number = get_next_available_name(output_dir, "A", ".m4a", start_num=audio_counter, force_num=True)
                        output_name = os.path.join(output_dir, output_name_base)
                        output_path = os.path.join(output_dir, output_name_with_ext)

                        print("Attempting to download separate audio...")
                        yt_dlp_cmd = (
                            f'yt-dlp '  # Assumes yt-dlp is in the system PATH
                            f'{auth} -f "bestaudio/best" -o "{temp_audio_file}" "{url}"'
                        )
                        success, output = run_command(yt_dlp_cmd)
                        if success and os.path.exists(temp_audio_file):
                            # Check if the downloaded file has a video stream
                            has_video = has_video_stream(temp_audio_file)
                            has_audio = has_audio_stream(temp_audio_file)
                            if has_video and has_audio and 'O' not in processed_urls[url]:
                                print("Downloaded file contains both video and audio streams, treating as original...")
                                # Treat as an original file (save as O#.mp4)
                                video_prefix = "O" if keep_original else "U"
                                video_output_name_with_ext, video_output_name_base, current_o_number = get_next_available_name(output_dir, video_prefix, ".mp4", start_num=current_o_number)
                                video_output_path = os.path.join(output_dir, video_output_name_with_ext)
                                if keep_original:
                                    os.rename(temp_audio_file, video_output_path)
                                    print(f"Saved Original as {video_output_path}")
                                else:
                                    print("Converting to universal combined format...")
                                    ffmpeg_cmd = (
                                        f'ffmpeg -i "{temp_audio_file}" -c:v libx264 -b:v 3500k '
                                        f'-vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2" -r 30 '
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
                                # Since we now have an 'O' file, extract audio from it (for all+a or all+a+v)
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
                                # Treat as a video file (save as V#.mp4)
                                video_output_name_with_ext, video_output_name_base, current_v_number = get_next_available_name(output_dir, "V", ".mp4", start_num=current_v_number)
                                video_output_path = os.path.join(output_dir, video_output_name_with_ext)
                                if keep_original:
                                    os.rename(temp_audio_file, video_output_path)
                                    print(f"Saved Video as {video_output_path}")
                                else:
                                    print("Converting to universal video-only format...")
                                    ffmpeg_cmd = (
                                        f'ffmpeg -i "{temp_audio_file}" -c:v libx264 -b:v 3500k '
                                        f'-vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2" -r 30 '
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
                                # No video stream, treat as audio
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

                # Step 6: In all+a+v or all+v mode, split the original video into a video-only file (V#.mp4)
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
            # Final cleanup
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