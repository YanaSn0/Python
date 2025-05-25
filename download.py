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
        stderr = subprocess.STDOUT if not suppress_errors else subprocess.DEVNULL
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
        start_time = time.time()

        try:
            if not suppress_errors and process.stdout is not None:
                for line in process.stdout:
                    debug_print(line, end='')
                    output.append(line)
                    if timeout and (time.time() - start_time) > timeout:
                        process.send_signal(signal.SIGTERM)
                        time.sleep(1)
                        if process.poll() is None:
                            process.kill()
                        raise TimeoutError(f"Command timed out after {timeout} seconds")

            if process.stdout is not None:
                process.stdout.close()
            return_code = process.wait()
            output_str = ''.join(output)
            debug_print(f"Debug: Command completed with return code: {return_code}")

            if return_code != 0:
                if not suppress_errors:
                    if "Command timed out" not in output_str:
                        debug_print(f"Error: Command failed with return code {return_code}. Output: {output_str}")
                return False, output_str
            return True, output_str

        except TimeoutError as e:
            attempt += 1
            if attempt <= retries:
                debug_print(f"Debug: Timeout: {e}. Retrying ({attempt}/{retries})...")
                time.sleep(5)
                continue
            else:
                debug_print(f"Debug: Timeout: {e}. No more retries left.")
                return False, str(e)
        except Exception as e:
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
                base_name = f"{prefix}_{num}_{sanitized_title}"
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
    success, output = run_command(cmd)
    if not success:
        return 0
    output = output.strip()
    if not output:
        print(f"Warning: ffprobe returned empty duration for {file_path}")
        return 0
    try:
        duration = float(output)
        return duration
    except ValueError:
        print(f"Warning: Could not determine duration of {file_path}. Output: '{output}'")
        return 0

def has_audio_stream(file_path):
    cmd = f'ffprobe -v error -show_streams -select_streams a -of default=noprint_wrappers=1 "{file_path}"'
    success, output = run_command(cmd)
    return bool(output.strip())

def has_video_stream(file_path):
    cmd = f'ffprobe -v error -show_streams -select_streams v -of default=noprint_wrappers=1 "{file_path}"'
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

def is_video_platform(url):
    video_domains = ['youtube.com', 'youtu.be', 'tiktok.com', 'vimeo.com', 'dailymotion.com', 'x.com', 'twitter.com']
    parsed_url = urllib.parse.urlparse(url)
    domain = parsed_url.netloc.lower()
    return any(video_domain in domain for video_domain in video_domains)

def get_video_title(url, auth):
    yt_dlp_title_cmd = f'yt-dlp {auth} --get-title "{url}"'
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

def main():
    global DEBUG
    parser = argparse.ArgumentParser(description="Download and process videos/images")
    parser.add_argument("submode", choices=["audio", "video", "combined", "split", "pic", "all"])
    parser.add_argument("--output-dir", "-o", default=".")
    parser.add_argument("--keep-original", action="store_true")
    parser.add_argument("--clear-dir", action="store_true")
    parser.add_argument("--username")
    parser.add_argument("--password")
    parser.add_argument("--cookies")
    parser.add_argument("--duration", type=float)
    parser.add_argument("--audio-only", action="store_true")
    parser.add_argument("--link", action="store_true")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    DEBUG = args.debug
    submode = args.submode
    output_dir = args.output_dir
    keep_original = args.keep_original
    clear_dir = args.clear_dir
    username = args.username
    password = args.password
    cookies = args.cookies
    duration_limit = args.duration
    audio_only = args.audio_only
    use_link_naming = args.link

    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
        except Exception as e:
            print(f"Error: Failed to create output directory {output_dir}: {e}")
            sys.exit(1)
    elif clear_dir:
        print(f"Clearing output directory: {output_dir}")
        try:
            for file in glob.glob(os.path.join(output_dir, "*")):
                if os.path.isfile(file):
                    os.remove(file)
                elif os.path.isdir(file):
                    shutil.rmtree(file)
        except Exception as e:
            print(f"Error: Failed to clear output directory {output_dir}: {e}")
            sys.exit(1)

    url_file = "urls.txt"
    if not os.path.exists(url_file):
        print(f"Error: {url_file} not found.")
        sys.exit(1)

    urls = []
    try:
        with open(url_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    line_urls = [url.strip() for url in line.split(";") if url.strip()]
                    urls.extend(line_urls)
    except Exception as e:
        print(f"Error: Failed to read {url_file}: {e}")
        sys.exit(1)

    if not urls:
        print(f"Error: {url_file} is empty.")
        sys.exit(1)

    unique_urls = list(dict.fromkeys(urls))
    if len(unique_urls) < len(urls):
        print(f"Removed {len(urls) - len(unique_urls)} duplicate URLs.")

    temp_file = os.path.join(output_dir, "temp_download.mp4")
    temp_audio_file = os.path.join(output_dir, "temp_audio.m4a")
    temp_image_dir = os.path.join(output_dir, "temp_images")
    temp_thumbnail = os.path.join(output_dir, "temp_download.webp")
    temp_audio_thumbnail = os.path.join(output_dir, "temp_audio.m4a.webp")

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

        for temp in [temp_file, temp_audio_file, temp_thumbnail, temp_audio_thumbnail]:
            if os.path.exists(temp):
                try:
                    os.remove(temp)
                    debug_print(f"Debug: Cleaned up {temp}")
                except Exception as e:
                    print(f"Warning: Failed to clean up {temp}: {e}")
        if os.path.exists(temp_image_dir):
            try:
                shutil.rmtree(temp_image_dir)
                debug_print(f"Debug: Cleaned up {temp_image_dir}")
            except Exception as e:
                print(f"Warning: Failed to clean up {temp_image_dir}: {e}")

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
            elif submode == "all":
                prefix = "O" if keep_original else "U"
                extension = ".mp4"

            if username and password:
                auth = f"--username {username} --password {password}"
            elif cookies:
                auth = f"--cookies {cookies}"
            else:
                auth = "--cookies-from-browser firefox"

            video_title = f"Untitled_{index + 1}"
            title_fetched = False
            if submode != "pic" and not (submode == "audio" and use_link_naming):
                title = get_video_title(url, auth)
                if title:
                    video_title = title
                    title_fetched = True
                else:
                    print(f"Warning: Could not fetch title for {url}.")

            if submode not in ["all"]:
                if submode == "audio" and use_link_naming:
                    output_name_with_ext, output_name_base, current_a_number = get_next_available_name(
                        output_dir, prefix, extension, start_num=current_a_number, use_url=True, url=url
                    )
                else:
                    output_name_with_ext, output_name_base, current_a_number = get_next_available_name(
                        output_dir, prefix, extension, title=video_title, start_num=current_a_number
                    )
                output_path = os.path.join(output_dir, output_name_with_ext)
                thumbnail_path = os.path.join(output_dir, f"{output_name_base}_thumb.webp")

            if submode == "audio":
                duration_option = f'--download-sections "*0-{duration_limit}"' if duration_limit else ""
                duration_message = f"Duration: {duration_limit}s" if duration_limit else "Duration: Full"

                yt_dlp_cmd = (
                    f'yt-dlp {auth} -f "bestaudio/best" -x --audio-format m4a '
                    f'--progress-template "[downloading] %(info.title)s %(progress._percent_str)s" '
                    f'{duration_option} -o "{temp_audio_file}" "{url}"'
                )
                success, output = run_command(yt_dlp_cmd, timeout=300, retries=1)
                if not success or not os.path.exists(temp_audio_file):
                    print(f"Failed to download audio: {url}")
                    continue

                if not title_fetched and not use_link_naming:
                    video_title = extract_title_from_output(output, video_title)
                    output_name_with_ext, output_name_base, current_a_number = get_next_available_name(
                        output_dir, "A", ".m4a", title=video_title, start_num=current_a_number
                    )
                    output_path = os.path.join(output_dir, output_name_with_ext)

                try:
                    os.rename(temp_audio_file, output_path)
                    print(f"download: {duration_message}")
                    print(f"Saved as {output_path.replace(os.sep, '/')}")
                except Exception as e:
                    print(f"Error: Failed to rename {temp_audio_file}: {e}")
                    if os.path.exists(temp_audio_file):
                        os.remove(temp_audio_file)
                    continue

                processed_urls[url].append('A')
                continue

            if submode == "video":
                duration_option = f'--download-sections "*0-{duration_limit}"' if duration_limit else ""
                duration_message = f"Duration: {duration_limit}s" if duration_limit else "Duration: Full"

                yt_dlp_cmd = (
                    f'yt-dlp {auth} -f "bestvideo[ext=mp4]" --merge-output-format mp4 '
                    f'--progress-template "[downloading] %(info.title)s %(progress._percent_str)s" '
                    f'{duration_option} -o "{temp_file}" "{url}"'
                )
                success, output = run_command(yt_dlp_cmd, timeout=300, retries=1)
                if not success or not os.path.exists(temp_file):
                    print(f"Failed to download video: {url}")
                    continue

                if not title_fetched:
                    video_title = extract_title_from_output(output, video_title)
                    output_name_with_ext, output_name_base, current_v_number = get_next_available_name(
                        output_dir, "V", ".mp4", title=video_title, start_num=current_v_number
                    )
                    output_path = os.path.join(output_dir, output_name_with_ext)

                if keep_original:
                    os.rename(temp_file, output_path)
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
                        f'-an "{output_path}"'
                    )
                    success, output = run_command(ffmpeg_cmd)
                    if not success:
                        print(f"Failed to convert video: {url}")
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                        continue
                    if os.path.exists(temp_file):
                        os.remove(temp_file)

                print(f"download: {duration_message}")
                print(f"Saved Video as {output_path.replace(os.sep, '/')}")
                processed_urls[url].append('V')
                continue

            if submode == "pic":
                output_name_with_ext, output_name_base, current_p_number = get_next_available_name(
                    output_dir, "P", ".jpg", start_num=current_p_number
                )
                output_path = os.path.join(output_dir, output_name_with_ext)

                os.makedirs(temp_image_dir, exist_ok=True)
                gallery_dl_cmd = f'gallery-dl --cookies-from-browser firefox -D "{temp_image_dir}" "{url}"'
                success, output = run_command(gallery_dl_cmd)
                if success:
                    image_files = sorted(glob.glob(os.path.join(temp_image_dir, "*")))
                    if image_files:
                        image_file = image_files[0]
                        ext = os.path.splitext(image_file)[1]
                        final_output_path = os.path.join(output_dir, f"{output_name_base}{ext}")
                        os.rename(image_file, final_output_path)
                        print(f"Saved Picture as {final_output_path.replace(os.sep, '/')}")
                        shutil.rmtree(temp_image_dir)
                        processed_urls[url].append('P')
                        continue
                print(f"Failed to download picture: {url}")
                shutil.rmtree(temp_image_dir, ignore_errors=True)
                continue

            if submode == "combined":
                duration_option = f'--download-sections "*0-{duration_limit}"' if duration_limit else ""
                duration_message = f"Duration: {duration_limit}s" if duration_limit else "Duration: Full"

                yt_dlp_cmd = (
                    f'yt-dlp {auth} -f "bestvideo+bestaudio/best" --merge-output-format mp4 '
                    f'--progress-template "[downloading] %(info.title)s %(progress._percent_str)s" '
                    f'{duration_option} -o "{temp_file}" "{url}"'
                )
                success, output = run_command(yt_dlp_cmd, timeout=300, retries=1)
                if not success or not os.path.exists(temp_file):
                    print(f"Failed to download: {url}")
                    continue

                if not title_fetched:
                    video_title = extract_title_from_output(output, video_title)
                    output_name_with_ext, output_name_base, current_o_number = get_next_available_name(
                        output_dir, prefix, ".mp4", title=video_title, start_num=current_o_number
                    )
                    output_path = os.path.join(output_dir, output_name_with_ext)

                if keep_original:
                    cmd = f'ffprobe -v error -show_streams -select_streams v:0 -show_entries stream=codec_name -of json "{temp_file}"'
                    success, output = run_command(cmd)
                    video_codec = None
                    if success:
                        data = json.loads(output)
                        if data.get('streams'):
                            video_codec = data['streams'][0].get('codec_name')

                    cmd = f'ffprobe -v error -show_streams -select_streams a:0 -show_entries stream=codec_name -of json "{temp_file}"'
                    success, output = run_command(cmd)
                    audio_codec = None
                    if success:
                        data = json.loads(output)
                        if data.get('streams'):
                            audio_codec = data['streams'][0].get('codec_name')

                    if video_codec == 'h264' and (audio_codec == 'aac' or not audio_codec):
                        os.rename(temp_file, output_path)
                    else:
                        width, height = get_video_dimensions(temp_file)
                        width = width + (width % 2)
                        height = height + (height % 2)
                        ffmpeg_cmd = (
                            f'ffmpeg -i "{temp_file}" -c:v libx264 -preset ultrafast -b:v 3500k '
                            f'-vf "scale={width}:{height}:force_original_aspect_ratio=decrease" -r 30 '
                            f'-c:a aac -b:a 128k -ar 44100 "{output_path}"'
                        )
                        success, output = run_command(ffmpeg_cmd)
                        if not success:
                            print(f"Failed to convert: {url}")
                            if os.path.exists(temp_file):
                                os.remove(temp_file)
                            continue
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
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
                        f'-c:a aac -b:a 128k -ar 44100 "{output_path}"'
                    )
                    success, output = run_command(ffmpeg_cmd)
                    if not success:
                        print(f"Failed to convert: {url}")
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                        continue
                    if os.path.exists(temp_file):
                        os.remove(temp_file)

                print(f"download: {duration_message}")
                print(f"Saved as {output_path.replace(os.sep, '/')}")
                video_downloaded_path = output_path
                processed_urls[url].append('O')
                continue

            if submode == "split":
                duration_option = f'--download-sections "*0-{duration_limit}"' if duration_limit else ""
                duration_message = f"Duration: {duration_limit}s" if duration_limit else "Duration: Full"

                yt_dlp_cmd = (
                    f'yt-dlp {auth} -f "bestvideo+bestaudio/best" --merge-output-format mp4 '
                    f'--progress-template "[downloading] %(info.title)s %(progress._percent_str)s" '
                    f'{duration_option} -o "{temp_file}" "{url}"'
                )
                success, output = run_command(yt_dlp_cmd, timeout=300, retries=1)
                if not success or not os.path.exists(temp_file):
                    print(f"Failed to download: {url}")
                    continue

                if not title_fetched:
                    video_title = extract_title_from_output(output, video_title)
                    output_name_with_ext, output_name_base, current_o_number = get_next_available_name(
                        output_dir, prefix, "_video.mp4", title=video_title, start_num=current_o_number
                    )
                    output_path = os.path.join(output_dir, output_name_with_ext)
                    audio_output_path = os.path.join(output_dir, f"{output_name_base}_audio.m4a")

                ffmpeg_cmd = f'ffmpeg -i "{temp_file}" -c:v copy -an "{output_path}"'
                success, output = run_command(ffmpeg_cmd)
                if success:
                    print(f"download: {duration_message}")
                    print(f"Saved Video-only as {output_path.replace(os.sep, '/')}")
                    if has_audio_stream(temp_file):
                        ffmpeg_cmd = f'ffmpeg -i "{temp_file}" -vn -c:a aac -b:a 128k "{audio_output_path}"'
                        success, output = run_command(ffmpeg_cmd)
                        if success:
                            print(f"Saved Audio as {audio_output_path.replace(os.sep, '/')}")
                        else:
                            print(f"Failed to extract audio: {url}")
                    else:
                        print(f"No audio stream in {url}")
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                    processed_urls[url].append('O')
                    processed_urls[url].append('A')
                else:
                    print(f"Failed to split video: {url}")
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                continue

            if submode == "all":
                duration_option = f'--download-sections "*0-{duration_limit}"' if duration_limit else ""
                duration_message = f"Duration: {duration_limit}s" if duration_limit else "Duration: Full"
                any_success = False

                # If audio-only is specified, skip video and picture downloads
                if audio_only:
                    output_name_with_ext, output_name_base, current_a_number = get_next_available_name(
                        output_dir, "A", ".m4a", title=video_title, start_num=current_a_number
                    )
                    audio_output_path = os.path.join(output_dir, output_name_with_ext)
                    thumbnail_path = os.path.join(output_dir, f"{output_name_base}_thumb.webp")

                    yt_dlp_cmd = (
                        f'yt-dlp {auth} -f "bestaudio/best" -x --audio-format m4a '
                        f'--write-thumbnail --convert-thumbnails webp '
                        f'--progress-template "[downloading] %(info.title)s %(progress._percent_str)s" '
                        f'{duration_option} -o "{temp_audio_file}" "{url}"'
                    )
                    success, output = run_command(yt_dlp_cmd, timeout=300, retries=1)
                    if success and os.path.exists(temp_audio_file):
                        if not title_fetched:
                            video_title = extract_title_from_output(output, video_title)
                            output_name_with_ext, output_name_base, current_a_number = get_next_available_name(
                                output_dir, "A", ".m4a", title=video_title, start_num=current_a_number
                            )
                            audio_output_path = os.path.join(output_dir, output_name_with_ext)
                            thumbnail_path = os.path.join(output_dir, f"{output_name_base}_thumb.webp")

                        # Check if the downloaded file has a video stream, which it shouldn't
                        has_video = has_video_stream(temp_audio_file)
                        has_audio = has_audio_stream(temp_audio_file)
                        debug_print(f"Debug: Downloaded file has video stream: {has_video}, audio stream: {has_audio}")

                        if has_video:
                            debug_print(f"Debug: Unexpected video stream in audio-only download, extracting audio with ffmpeg")
                            # Force audio extraction with ffmpeg to ensure no video stream
                            temp_audio_only = os.path.join(output_dir, "temp_audio_only.m4a")
                            ffmpeg_cmd = f'ffmpeg -i "{temp_audio_file}" -vn -c:a aac -b:a 128k "{temp_audio_only}"'
                            success, output = run_command(ffmpeg_cmd)
                            if success and os.path.exists(temp_audio_only):
                                debug_print(f"Debug: Successfully extracted audio with ffmpeg")
                                os.remove(temp_audio_file)
                                os.rename(temp_audio_only, temp_audio_file)
                            else:
                                debug_print(f"Debug: Failed to extract audio with ffmpeg: {output}")
                                print(f"Failed to extract audio: {url}")
                                if os.path.exists(temp_audio_file):
                                    os.remove(temp_audio_file)
                                if os.path.exists(temp_audio_thumbnail):
                                    os.remove(temp_audio_thumbnail)
                                continue

                        # Now process the audio file
                        ffmpeg_cmd = f'ffmpeg -i "{temp_audio_file}" -c:a aac -b:a 128k "{audio_output_path}"'
                        success, output = run_command(ffmpeg_cmd)
                        if success:
                            print(f"download: {duration_message}")
                            print(f"Saved Audio as {audio_output_path.replace(os.sep, '/')}")
                            audio_counter += 1
                            if os.path.exists(temp_audio_file):
                                os.remove(temp_audio_file)
                            processed_urls[url].append('A')
                            any_success = True
                        else:
                            debug_print(f"Debug: Failed to convert audio: {output}")
                            print(f"Failed to convert audio: {url}")
                            if os.path.exists(temp_audio_file):
                                os.remove(temp_audio_file)
                            if os.path.exists(temp_audio_thumbnail):
                                os.remove(temp_audio_thumbnail)
                            continue

                        # Check for the thumbnail (yt-dlp renames it to temp_audio.m4a.webp)
                        if os.path.exists(temp_audio_thumbnail):
                            try:
                                os.rename(temp_audio_thumbnail, thumbnail_path)
                                print(f"Saved Thumbnail as {thumbnail_path.replace(os.sep, '/')}")
                            except Exception as e:
                                print(f"Error: Failed to rename thumbnail: {e}")
                                if os.path.exists(temp_audio_thumbnail):
                                    os.remove(temp_audio_thumbnail)
                        else:
                            debug_print(f"Debug: Thumbnail not found at {temp_audio_thumbnail} for {url}")
                            print(f"Warning: Thumbnail not downloaded for {url}")
                    else:
                        debug_print(f"Debug: Failed to download audio: {output}")
                        print(f"Failed to download audio: {url}")
                        if os.path.exists(temp_audio_file):
                            os.remove(temp_audio_file)
                        if os.path.exists(temp_audio_thumbnail):
                            os.remove(temp_audio_thumbnail)

                    if not any_success:
                        print(f"No audio could be downloaded for {url}")
                    continue

                # Try combined video/audio first (with thumbnail if not audio-only)
                if 'O' not in processed_urls[url]:
                    output_name_with_ext, output_name_base, current_o_number = get_next_available_name(
                        output_dir, prefix, ".mp4", title=video_title, start_num=current_o_number
                    )
                    output_path = os.path.join(output_dir, output_name_with_ext)
                    thumbnail_path = os.path.join(output_dir, f"{output_name_base}_thumb.webp")

                    yt_dlp_cmd = (
                        f'yt-dlp {auth} -f "bestvideo+bestaudio/best" --merge-output-format mp4 '
                        f'--write-thumbnail --convert-thumbnails webp '
                        f'--progress-template "[downloading] %(info.title)s %(progress._percent_str)s" '
                        f'{duration_option} -o "{temp_file}" "{url}"'
                    )
                    success, output = run_command(yt_dlp_cmd, timeout=300, retries=1)
                    if success and os.path.exists(temp_file):
                        if not title_fetched:
                            video_title = extract_title_from_output(output, video_title)
                            output_name_with_ext, output_name_base, current_o_number = get_next_available_name(
                                output_dir, prefix, ".mp4", title=video_title, start_num=current_o_number
                            )
                            output_path = os.path.join(output_dir, output_name_with_ext)
                            thumbnail_path = os.path.join(output_dir, f"{output_name_base}_thumb.webp")

                        if keep_original:
                            cmd = f'ffprobe -v error -show_streams -select_streams v:0 -show_entries stream=codec_name -of json "{temp_file}"'
                            success, output = run_command(cmd)
                            video_codec = None
                            if success:
                                data = json.loads(output)
                                if data.get('streams'):
                                    video_codec = data['streams'][0].get('codec_name')

                            cmd = f'ffprobe -v error -show_streams -select_streams a:0 -show_entries stream=codec_name -of json "{temp_file}"'
                            success, output = run_command(cmd)
                            audio_codec = None
                            if success:
                                data = json.loads(output)
                                if data.get('streams'):
                                    audio_codec = data['streams'][0].get('codec_name')

                            if video_codec == 'h264' and (audio_codec == 'aac' or not audio_codec):
                                os.rename(temp_file, output_path)
                                print(f"download: {duration_message}")
                                print(f"Saved Original as {output_path.replace(os.sep, '/')}")
                                any_success = True
                            else:
                                width, height = get_video_dimensions(temp_file)
                                width = width + (width % 2)
                                height = height + (height % 2)
                                ffmpeg_cmd = (
                                    f'ffmpeg -i "{temp_file}" -c:v libx264 -preset ultrafast -b:v 3500k '
                                    f'-vf "scale={width}:{height}:force_original_aspect_ratio=decrease" -r 30 '
                                    f'-c:a aac -b:a 128k -ar 44100 "{output_path}"'
                                )
                                success, output = run_command(ffmpeg_cmd)
                                if success:
                                    if os.path.exists(temp_file):
                                        os.remove(temp_file)
                                    print(f"download: {duration_message}")
                                    print(f"Saved Converted Original as {output_path.replace(os.sep, '/')}")
                                    any_success = True
                                else:
                                    debug_print(f"Debug: Failed to convert video: {output}")
                                    print(f"Failed to convert: {url}")
                                    if os.path.exists(temp_file):
                                        os.remove(temp_file)
                                    if os.path.exists(temp_thumbnail):
                                        os.remove(temp_thumbnail)
                                    # Continue to next download type
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
                                f'-c:a aac -b:a 128k -ar 44100 "{output_path}"'
                            )
                            success, output = run_command(ffmpeg_cmd)
                            if success:
                                if os.path.exists(temp_file):
                                    os.remove(temp_file)
                                print(f"download: {duration_message}")
                                print(f"Saved Universal as {output_path.replace(os.sep, '/')}")
                                any_success = True
                            else:
                                debug_print(f"Debug: Failed to convert video: {output}")
                                print(f"Failed to convert: {url}")
                                if os.path.exists(temp_file):
                                    os.remove(temp_file)
                                if os.path.exists(temp_thumbnail):
                                    os.remove(temp_thumbnail)
                                # Continue to next download type

                        if os.path.exists(temp_thumbnail):
                            try:
                                os.rename(temp_thumbnail, thumbnail_path)
                                print(f"Saved Thumbnail as {thumbnail_path.replace(os.sep, '/')}")
                            except Exception as e:
                                print(f"Error: Failed to rename thumbnail: {e}")
                                if os.path.exists(temp_thumbnail):
                                    os.remove(temp_thumbnail)
                        else:
                            debug_print(f"Debug: Thumbnail not downloaded for {url}")
                            print(f"Warning: Thumbnail not downloaded for {url}")

                        video_downloaded_path = output_path
                        processed_urls[url].append('O')
                    else:
                        debug_print(f"Debug: Failed to download combined video/audio: {output}")
                        print(f"Failed to download combined video/audio: {url}")
                        if os.path.exists(temp_thumbnail):
                            os.remove(temp_thumbnail)

                # Try audio-only if combined failed
                if 'O' not in processed_urls[url] and 'A' not in processed_urls[url]:
                    output_name_with_ext, output_name_base, current_a_number = get_next_available_name(
                        output_dir, "A", ".m4a", title=video_title, start_num=current_a_number
                    )
                    audio_output_path = os.path.join(output_dir, output_name_with_ext)
                    thumbnail_path = os.path.join(output_dir, f"{output_name_base}_thumb.webp")

                    yt_dlp_cmd = (
                        f'yt-dlp {auth} -f "bestaudio/best" -x --audio-format m4a '
                        f'--write-thumbnail --convert-thumbnails webp '
                        f'--progress-template "[downloading] %(info.title)s %(progress._percent_str)s" '
                        f'{duration_option} -o "{temp_audio_file}" "{url}"'
                    )
                    success, output = run_command(yt_dlp_cmd, timeout=300, retries=1)
                    if success and os.path.exists(temp_audio_file):
                        if not title_fetched:
                            video_title = extract_title_from_output(output, video_title)
                            output_name_with_ext, output_name_base, current_a_number = get_next_available_name(
                                output_dir, "A", ".m4a", title=video_title, start_num=current_a_number
                            )
                            audio_output_path = os.path.join(output_dir, output_name_with_ext)
                            thumbnail_path = os.path.join(output_dir, f"{output_name_base}_thumb.webp")

                        # Check if the downloaded file has a video stream
                        has_video = has_video_stream(temp_audio_file)
                        has_audio = has_audio_stream(temp_audio_file)
                        debug_print(f"Debug: Downloaded file has video stream: {has_video}, audio stream: {has_audio}")

                        if has_video and has_audio and 'O' not in processed_urls[url]:
                            print("Downloaded file has video and audio, treating as original...")
                            video_prefix = "O" if keep_original else "U"
                            video_output_name_with_ext, video_output_name_base, current_o_number = get_next_available_name(
                                output_dir, video_prefix, ".mp4", title=video_title, start_num=current_o_number
                            )
                            video_output_path = os.path.join(output_dir, video_output_name_with_ext)
                            thumbnail_path = os.path.join(output_dir, f"{video_output_name_base}_thumb.webp")
                            if keep_original:
                                os.rename(temp_audio_file, video_output_path)
                                print(f"download: {duration_message}")
                                print(f"Saved Original as {video_output_path.replace(os.sep, '/')}")
                                any_success = True
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
                                    f'-c:a aac -b:a 128k -ar 44100 "{video_output_path}"'
                                )
                                success, output = run_command(ffmpeg_cmd)
                                if success:
                                    if os.path.exists(temp_audio_file):
                                        os.remove(temp_audio_file)
                                    print(f"download: {duration_message}")
                                    print(f"Saved Original as {video_output_path.replace(os.sep, '/')}")
                                    any_success = True
                                else:
                                    debug_print(f"Debug: Failed to convert video: {output}")
                                    print(f"Failed to convert video: {url}")
                                    if os.path.exists(temp_audio_file):
                                        os.remove(temp_audio_file)
                                    if os.path.exists(temp_audio_thumbnail):
                                        os.remove(temp_audio_thumbnail)
                                    continue
                            video_downloaded_path = video_output_path
                            processed_urls[url].append('O')
                        elif has_video and 'V' not in processed_urls[url]:
                            print("Downloaded file has video, treating as video...")
                            video_output_name_with_ext, video_output_name_base, current_v_number = get_next_available_name(
                                output_dir, "V", ".mp4", title=video_title, start_num=current_v_number
                            )
                            video_output_path = os.path.join(output_dir, video_output_name_with_ext)
                            thumbnail_path = os.path.join(output_dir, f"{video_output_name_base}_thumb.webp")
                            if keep_original:
                                os.rename(temp_audio_file, video_output_path)
                                print(f"download: {duration_message}")
                                print(f"Saved Video as {video_output_path.replace(os.sep, '/')}")
                                any_success = True
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
                                    f'-an "{video_output_path}"'
                                )
                                success, output = run_command(ffmpeg_cmd)
                                if success:
                                    if os.path.exists(temp_audio_file):
                                        os.remove(temp_audio_file)
                                    print(f"download: {duration_message}")
                                    print(f"Saved Video as {video_output_path.replace(os.sep, '/')}")
                                    any_success = True
                                else:
                                    debug_print(f"Debug: Failed to convert video: {output}")
                                    print(f"Failed to convert video: {url}")
                                    if os.path.exists(temp_audio_file):
                                        os.remove(temp_audio_file)
                                    if os.path.exists(temp_audio_thumbnail):
                                        os.remove(temp_audio_thumbnail)
                                    continue
                            processed_urls[url].append('V')
                        else:
                            ffmpeg_cmd = f'ffmpeg -i "{temp_audio_file}" -c:a aac -b:a 128k "{audio_output_path}"'
                            success, output = run_command(ffmpeg_cmd)
                            if success:
                                print(f"download: {duration_message}")
                                print(f"Saved Audio as {audio_output_path.replace(os.sep, '/')}")
                                audio_counter += 1
                                if os.path.exists(temp_audio_file):
                                    os.remove(temp_audio_file)
                                processed_urls[url].append('A')
                                any_success = True
                            else:
                                debug_print(f"Debug: Failed to convert audio: {output}")
                                print(f"Failed to convert audio: {url}")
                                if os.path.exists(temp_audio_file):
                                    os.remove(temp_audio_file)
                                if os.path.exists(temp_audio_thumbnail):
                                    os.remove(temp_audio_thumbnail)
                                continue

                        if os.path.exists(temp_audio_thumbnail):
                            try:
                                os.rename(temp_audio_thumbnail, thumbnail_path)
                                print(f"Saved Thumbnail as {thumbnail_path.replace(os.sep, '/')}")
                            except Exception as e:
                                print(f"Error: Failed to rename thumbnail: {e}")
                                if os.path.exists(temp_audio_thumbnail):
                                    os.remove(temp_audio_thumbnail)
                        else:
                            debug_print(f"Debug: Thumbnail not downloaded for {url}")
                            print(f"Warning: Thumbnail not downloaded for {url}")
                    else:
                        debug_print(f"Debug: Failed to download audio: {output}")
                        print(f"Failed to download audio: {url}")
                        if os.path.exists(temp_audio_file):
                            os.remove(temp_audio_file)
                        if os.path.exists(temp_audio_thumbnail):
                            os.remove(temp_audio_thumbnail)

                # Try video-only if combined failed
                if 'O' not in processed_urls[url] and 'V' not in processed_urls[url]:
                    output_name_with_ext, output_name_base, current_v_number = get_next_available_name(
                        output_dir, "V", ".mp4", title=video_title, start_num=current_v_number
                    )
                    video_output_path = os.path.join(output_dir, output_name_with_ext)
                    thumbnail_path = os.path.join(output_dir, f"{output_name_base}_thumb.webp")

                    yt_dlp_cmd = (
                        f'yt-dlp {auth} -f "bestvideo[ext=mp4]" --merge-output-format mp4 '
                        f'--write-thumbnail --convert-thumbnails webp '
                        f'--progress-template "[downloading] %(info.title)s %(progress._percent_str)s" '
                        f'{duration_option} -o "{temp_file}" "{url}"'
                    )
                    success, output = run_command(yt_dlp_cmd, timeout=300, retries=1)
                    if success and os.path.exists(temp_file):
                        if not title_fetched:
                            video_title = extract_title_from_output(output, video_title)
                            output_name_with_ext, output_name_base, current_v_number = get_next_available_name(
                                output_dir, "V", ".mp4", title=video_title, start_num=current_v_number
                            )
                            video_output_path = os.path.join(output_dir, output_name_with_ext)
                            thumbnail_path = os.path.join(output_dir, f"{output_name_base}_thumb.webp")

                        if keep_original:
                            os.rename(temp_file, video_output_path)
                            print(f"download: {duration_message}")
                            print(f"Saved Video as {video_output_path.replace(os.sep, '/')}")
                            any_success = True
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
                                f'-an "{video_output_path}"'
                            )
                            success, output = run_command(ffmpeg_cmd)
                            if success:
                                if os.path.exists(temp_file):
                                    os.remove(temp_file)
                                print(f"download: {duration_message}")
                                print(f"Saved Video as {video_output_path.replace(os.sep, '/')}")
                                any_success = True
                            else:
                                debug_print(f"Debug: Failed to convert video: {output}")
                                print(f"Failed to convert video: {url}")
                                if os.path.exists(temp_file):
                                    os.remove(temp_file)
                                if os.path.exists(temp_thumbnail):
                                    os.remove(temp_thumbnail)
                                continue

                        if os.path.exists(temp_thumbnail):
                            try:
                                os.rename(temp_thumbnail, thumbnail_path)
                                print(f"Saved Thumbnail as {thumbnail_path.replace(os.sep, '/')}")
                            except Exception as e:
                                print(f"Error: Failed to rename thumbnail: {e}")
                                if os.path.exists(temp_thumbnail):
                                    os.remove(temp_thumbnail)
                        else:
                            debug_print(f"Debug: Thumbnail not downloaded for {url}")
                            print(f"Warning: Thumbnail not downloaded for {url}")

                        processed_urls[url].append('V')
                    else:
                        debug_print(f"Debug: Failed to download video-only: {output}")
                        print(f"Failed to download video-only: {url}")
                        if os.path.exists(temp_thumbnail):
                            os.remove(temp_thumbnail)

                # Try picture if video failed
                if 'O' not in processed_urls[url] and 'V' not in processed_urls[url] and 'P' not in processed_urls[url]:
                    if is_video_platform(url) and ('A' in processed_urls[url]):
                        print("Skipping picture download for video platform...")
                    else:
                        print("Video download failed, attempting picture...")
                        output_name_with_ext, output_name_base, current_p_number = get_next_available_name(
                            output_dir, "P", ".jpg", start_num=current_p_number
                        )
                        picture_output_path = os.path.join(output_dir, output_name_with_ext)

                        os.makedirs(temp_image_dir, exist_ok=True)
                        gallery_dl_cmd = f'gallery-dl --cookies-from-browser firefox -D "{temp_image_dir}" "{url}"'
                        success, output = run_command(gallery_dl_cmd)
                        if success:
                            image_files = sorted(glob.glob(os.path.join(temp_image_dir, "*")))
                            if image_files:
                                image_file = image_files[0]
                                ext = os.path.splitext(image_file)[1]
                                final_output_path = os.path.join(output_dir, f"{output_name_base}{ext}")
                                os.rename(image_file, final_output_path)
                                print(f"Saved Picture as {final_output_path.replace(os.sep, '/')}")
                                processed_urls[url].append('P')
                                shutil.rmtree(temp_image_dir)
                                any_success = True
                                continue
                            else:
                                debug_print(f"Debug: No images found in temp directory after gallery-dl")
                                print(f"No images found to save for {url}")
                        else:
                            debug_print(f"Debug: Failed to download picture: {output}")
                            print(f"Failed to download picture: {url}")
                        shutil.rmtree(temp_image_dir, ignore_errors=True)

                if not any_success:
                    print(f"No content could be downloaded for {url}")

        except Exception as e:
            print(f"Error: Unexpected issue while processing {url}: {e}")
            continue

        finally:
            for temp in [temp_file, temp_audio_file, temp_thumbnail, temp_audio_thumbnail]:
                if os.path.exists(temp):
                    try:
                        os.remove(temp)
                    except Exception as e:
                        print(f"Warning: Failed to clean up {temp}: {e}")
            if os.path.exists(temp_image_dir):
                try:
                    shutil.rmtree(temp_image_dir)
                except Exception as e:
                    print(f"Warning: Failed to clean up {temp_image_dir}: {e}")

    print(f"Done! Outputs saved in {output_dir}")

if __name__ == "__main__":
    main()