import subprocess
import sys
import os
import argparse
import re
import urllib.parse
import json
import yt_dlp
from contextlib import nullcontext
import time

# Global debug flag
DEBUG = False

def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)

def run_command(command, suppress_errors=False):
    debug_print(f"Debug: Executing command: {command}")
    stdout = subprocess.PIPE if not suppress_errors else subprocess.DEVNULL
    stderr = subprocess.STDOUT if not suppress_errors else subprocess.DEVNULL
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=stdout,
        stderr=stderr,
        text=True,
        errors='replace',
        bufsize=1,
        universal_newlines=True
    )
    output = []
    try:
        if not suppress_errors and process.stdout:
            with open("ffmpeg_log.txt", "a", encoding="utf-8", errors="replace") if DEBUG else nullcontext() as log_file:
                for line in process.stdout:
                    debug_print(line, end='')
                    output.append(line)
                    if log_file:
                        log_file.write(line)
        return_code = process.wait()
        output_str = ''.join(output)
        if return_code != 0 and not suppress_errors:
            return False, output_str
        return True, output_str
    except Exception as e:
        return False, str(e)
    finally:
        if process.stdout:
            process.stdout.close()
        try:
            process.terminate()
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

def safe_remove(file_path):
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            return True
        except PermissionError:
            debug_print(f"Warning: PermissionError on attempt {attempt + 1} for {file_path}. Retrying...")
            time.sleep(1)
    debug_print(f"Error: Failed to delete {file_path} after {max_attempts} attempts.")
    return False

def get_video_dimensions(video_path):
    cmd = f'ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of json "{video_path}"'
    success, output = run_command(cmd)
    if success:
        try:
            data = json.loads(output)
            if data.get('streams'):
                width = data['streams'][0]['width']
                height = data['streams'][0]['height']
                return width, height
        except json.JSONDecodeError:
            debug_print(f"Error: Failed to parse ffprobe output for {video_path}")
    debug_print(f"Warning: Could not determine dimensions of {video_path}. Using default 1920x1080.")
    return 1920, 1080

def run_yt_dlp(params, output_path):
    debug_print(f"Debug: Executing yt-dlp: {params}")
    try:
        ydl_opts = {
            'outtmpl': output_path,
            'progress_hooks': [lambda d: debug_print(f"[downloading] {d.get('info_dict', {}).get('title', 'Unknown')} {d.get('_percent_str', '')}")],
            'cookiesfrombrowser': ('firefox',),
            'writethumbnail': True,
            'postprocessors': params.get('postprocessors', []),
            'clean_metadata': True,
        }
        ydl_opts.update({k: v for k, v in params.items() if k not in ['postprocessors', 'writethumbnail']})
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([params.get('url')])
        return True, ""
    except Exception as e:
        debug_print(f"Error: yt-dlp failed: {e}")
        return False, str(e)

def sanitize_filename(filename):
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '_', filename)
    sanitized = re.sub(r'\s+', '_', sanitized.strip())
    sanitized = sanitized[:200]
    return sanitized

def get_url_base_name(url):
    parsed_url = urllib.parse.urlparse(url)
    path = parsed_url.path.strip('/')
    query = urllib.parse.parse_qs(parsed_url.query)
    si_param = query.get('si', [''])[0]
    name_base = f"{path}_{si_param}" if si_param else path
    return sanitize_filename(name_base)

def get_next_available_name(output_dir, media_ext, title=None, custom_name=None, start_num=1, use_url=False, url=None):
    if custom_name:
        sanitized_name = sanitize_filename(custom_name)
    elif use_url and url:
        sanitized_name = get_url_base_name(url)
    else:
        sanitized_name = sanitize_filename(title) if title else "Untitled"

    num = start_num
    while True:
        media_name = f"{sanitized_name}_Uni_{num}{media_ext}"
        thumb_name = f"{sanitized_name}_Uni_{num}_thumb.webp"
        media_path = os.path.join(output_dir, media_name)
        thumb_path = os.path.join(output_dir, thumb_name)
        if not os.path.exists(media_path):
            return media_name, thumb_name, num + 1
        num += 1

def get_video_title(url):
    ydl_opts = {
        'simulate': True,
        'quiet': True,
        'cookiesfrombrowser': ('firefox',),
        'url': url,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title')
            if title:
                return title.strip()
    except Exception as e:
        debug_print(f"Error: Failed to fetch title: {e}")
        return None

def find_downloaded_media_file(temp_media_base, is_audio=False):
    extensions = ['.m4a', '.opus', '.webm', '.mp3'] if is_audio else ['.mp4', '.webm', '.mkv']
    for ext in extensions:
        temp_path = temp_media_base + ext
        if os.path.exists(temp_path):
            return temp_path
    return None

def find_downloaded_thumbnail(temp_thumb_base):
    possible_extensions = ['.webp', '.jpg', '.jpeg', '.png']
    for ext in possible_extensions:
        temp_path = temp_thumb_base + ext
        if os.path.exists(temp_path):
            return temp_path
    return None

def convert_thumbnail_to_webp(input_path, output_path):
    ffmpeg_cmd = f'ffmpeg -i "{input_path}" -c:v libwebp "{output_path}"'
    success, ffmpeg_output = run_command(ffmpeg_cmd)
    if success:
        safe_remove(input_path)
        return True
    print(f"Error: Failed to convert thumbnail: {ffmpeg_output}")
    return False

def trim_media(input_path, output_path, trim_limit, is_audio=False):
    codec = 'copy' if not is_audio else 'aac -b:a 128k'
    stream_spec = '-vn' if is_audio else ''
    ffmpeg_cmd = f'ffmpeg -i "{input_path}" {stream_spec} -t {trim_limit} -c:v copy -c:a {codec} "{output_path}"'
    success, ffmpeg_output = run_command(ffmpeg_cmd)
    if success:
        safe_remove(input_path)
        return True
    print(f"Error: Failed to trim media: {ffmpeg_output}")
    return False

def main():
    global DEBUG
    parser = argparse.ArgumentParser(description="Download audio or video in universal format")
    parser.add_argument("custom_name", nargs="?", default=None, help="Custom name for media and thumbnail")
    parser.add_argument("command", choices=["audio", "full"], help="Main command (audio or full for video)")
    parser.add_argument("--trim", type=int, help="Seconds to trim")
    parser.add_argument("--audio-only", action="store_true", help="Ensure audio-only download (for audio command)")
    parser.add_argument("--link", action="store_true", help="Use URL for naming")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--output-dir", "-o", help="Directory where output will be saved (default: downloaded)")
    args = parser.parse_args()

    DEBUG = args.debug
    trim_limit = args.trim
    custom_name = args.custom_name
    use_url_naming = args.link
    command = args.command
    is_audio = command == "audio"

    # Set output directory
    output_dir = os.path.abspath(args.output_dir if args.output_dir else os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloaded"))
    os.makedirs(output_dir, exist_ok=True)

    url_file = "urls.txt"
    if not os.path.exists(url_file):
        print(f"Error: {url_file} not found.")
        sys.exit(1)

    urls = []
    with open(url_file, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                urls.extend([url.strip() for url in line.split(";") if url.strip()])
    if not urls:
        print(f"Error: {url_file} is empty.")
        sys.exit(1)

    unique_urls = list(dict.fromkeys(urls))
    temp_media_file = os.path.join(output_dir, "temp_media")
    temp_media_thumbnail = os.path.join(output_dir, "temp_media")
    current_number = 1

    for index, url in enumerate(unique_urls):
        try:
            print(f"\nProcessing {'audio' if is_audio else 'video'} {index + 1}/{len(unique_urls)}: {url}")

            for temp in [temp_media_file + ext for ext in [".m4a", ".opus", ".webm", ".mp3", ".mp4", ".mkv"]] + \
                        [temp_media_thumbnail + ext for ext in [".webp", '.jpg', '.jpeg', '.png']]:
                safe_remove(temp)

            media_ext = ".m4a" if is_audio else ".mp4"
            video_title = f"Untitled_{index + 1}"
            title = get_video_title(url)
            if title:
                video_title = title

            output_name_with_ext, thumbnail_name, current_number = get_next_available_name(
                output_dir, media_ext, title=video_title, custom_name=custom_name,
                start_num=current_number, use_url=use_url_naming, url=url
            )
            output_path = os.path.join(output_dir, output_name_with_ext)
            thumbnail_path = os.path.join(output_dir, thumbnail_name)
            duration_message = f"Duration: {trim_limit}s" if trim_limit else "Duration: Full"

            ydl_params = {
                'format': 'bestaudio/best' if is_audio else 'bestvideo+bestaudio/best',
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'm4a'}] if is_audio else [],
                'url': url,
            }

            success, yt_dlp_output = run_yt_dlp(ydl_params, temp_media_file)
            if not success:
                print(f"Error: Failed to download {'audio' if is_audio else 'video'}: {url}")
                downloaded_thumbnail = find_downloaded_thumbnail(temp_media_thumbnail)
                if downloaded_thumbnail:
                    if not downloaded_thumbnail.endswith('.webp'):
                        convert_thumbnail_to_webp(downloaded_thumbnail, temp_media_thumbnail + ".webp")
                        downloaded_thumbnail = temp_media_thumbnail + ".webp"
                    os.rename(downloaded_thumbnail, thumbnail_path)
                    print(f"Saved Thumbnail as: {thumbnail_path}")
                continue

            downloaded_media_file = find_downloaded_media_file(temp_media_file, is_audio)
            if not downloaded_media_file:
                print(f"Error: No {'audio' if is_audio else 'video'} file found for {url}")
                downloaded_thumbnail = find_downloaded_thumbnail(temp_media_thumbnail)
                if downloaded_thumbnail:
                    if not downloaded_thumbnail.endswith('.webp'):
                        convert_thumbnail_to_webp(downloaded_thumbnail, temp_media_thumbnail + ".webp")
                        downloaded_thumbnail = temp_media_thumbnail + ".webp"
                    os.rename(downloaded_thumbnail, thumbnail_path)
                    print(f"Saved Thumbnail as: {thumbnail_path}")
                continue

            downloaded_thumbnail = find_downloaded_thumbnail(temp_media_thumbnail)
            if downloaded_thumbnail and not downloaded_thumbnail.endswith('.webp'):
                convert_thumbnail_to_webp(downloaded_thumbnail, temp_media_thumbnail + ".webp")
                downloaded_thumbnail = temp_media_thumbnail + ".webp"

            # Handle trimming for both audio and video
            if trim_limit:
                temp_trimmed_media = os.path.join(output_dir, f"temp_media_trimmed{media_ext}")
                if trim_media(downloaded_media_file, temp_trimmed_media, trim_limit, is_audio):
                    downloaded_media_file = temp_trimmed_media
                else:
                    safe_remove(downloaded_media_file)
                    if downloaded_thumbnail:
                        os.rename(downloaded_thumbnail, thumbnail_path)
                        print(f"Saved Thumbnail as: {thumbnail_path}")
                    continue

            # Convert media to final format
            if is_audio:
                ffmpeg_cmd = f'ffmpeg -i "{downloaded_media_file}" -c:a aac -b:a 128k -ar 44100 "{output_path}"'
            else:
                width, height = get_video_dimensions(downloaded_media_file)
                width = width + (width % 2)
                height = height + (height % 2)
                aspect_ratio = width / height if height > 0 else 1
                if aspect_ratio > 1.5:
                    target_width, target_height = 1920, 1080
                elif aspect_ratio < 0.67:
                    target_width, target_height = 1080, 1920
                else:
                    target_width, target_height = 1080, 1080
                target_width = target_width + (target_width % 2)
                target_height = target_height + (target_height % 2)
                ffmpeg_cmd = (
                    f'ffmpeg -i "{downloaded_media_file}" -c:v libx264 -preset fast -b:v 3500k -r 30 '
                    f'-vf "scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2" '
                    f'-c:a aac -b:a 128k -ar 44100 -pix_fmt yuv420p "{output_path}"'
                )

            success, ffmpeg_output = run_command(ffmpeg_cmd)
            if success:
                safe_remove(downloaded_media_file)
                print(f"Download: {duration_message}")
                print(f"Saved {'Audio' if is_audio else 'Video'} as: {output_path}")
                if downloaded_thumbnail:
                    os.rename(downloaded_thumbnail, thumbnail_path)
                    print(f"Saved Thumbnail as: {thumbnail_path}")
            else:
                print(f"Error: Failed to convert {'audio' if is_audio else 'video'}: {url}")
                print(f"FFmpeg output: {ffmpeg_output}")
                safe_remove(downloaded_media_file)
                if downloaded_thumbnail:
                    os.rename(downloaded_thumbnail, thumbnail_path)
                    print(f"Saved Thumbnail as: {thumbnail_path}")
        except Exception as e:
            print(f"Error: Skipped processing {url} due to: {str(e)}")
            for temp in [temp_media_file + ext for ext in [".m4a", ".opus", ".webm", ".mp3", ".mp4", ".mkv"]] + \
                        [temp_media_thumbnail + ext for ext in [".webp", '.jpg', '.jpeg', '.png']]:
                safe_remove(temp)
            continue

if __name__ == "__main__":
    main()
