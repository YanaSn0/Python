import subprocess
import os
import argparse
import re
import json
import time
from datetime import datetime

DEBUG = False

def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)

def run_command(command):
    debug_print(f"Debug: Executing: {command}")
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')
    output = process.communicate()[0]
    if process.returncode != 0:
        debug_print(f"Error: Command failed: {output}")
        return False, output
    return True, output

def safe_remove(file_path):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            debug_print(f"Deleted: {file_path}")
    except Exception as e:
        debug_print(f"Error deleting {file_path}: {e}")

def get_video_dimensions(video_path):
    cmd = f'ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of json "{video_path}"'
    success, output = run_command(cmd)
    if success:
        try:
            data = json.loads(output)
            if data.get('streams'):
                return data['streams'][0]['width'], data['streams'][0]['height']
        except json.JSONDecodeError:
            debug_print(f"Error parsing ffprobe output: {output}")
    debug_print(f"Warning: Using default 1920x1080 for {video_path}")
    return 1920, 1080

def sanitize_filename(filename):
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '_', filename)
    sanitized = re.sub(r'\s+', '_', sanitized.strip())
    return sanitized[:200]

def get_next_available_name(output_dir, media_ext, title, current_number):
    sanitized_name = sanitize_filename(title if title else "Untitled")
    num = current_number
    while True:
        media_name = f"{sanitized_name}_{num}{media_ext}"
        thumb_name = f"{sanitized_name}_{num}_thumb.webp"
        if not os.path.exists(os.path.join(output_dir, media_name)):
            return media_name, thumb_name, num + 1
        num += 1

def run_yt_dlp(url, output_path, is_audio=False):
    cmd = f'yt-dlp "{url}" -o "{output_path}" --write-thumbnail --cookies-from-browser firefox'
    if is_audio:
        cmd += ' --extract-audio --audio-format m4a --audio-quality 192k'
    else:
        cmd += ' --format "bestvideo+bestaudio/best" --merge-output-format mp4'
    if DEBUG:
        cmd += ' --verbose'
    return run_command(cmd)

def get_video_title(url):
    cmd = f'yt-dlp "{url}" --get-title --cookies-from-browser firefox'
    success, output = run_command(cmd)
    return output.strip() if success else None

def main():
    global DEBUG
    parser = argparse.ArgumentParser(description="Download YouTube media from urls.txt")
    parser.add_argument("command", choices=["audio", "full"], default="full", help="Download audio or full video")
    parser.add_argument("--trim", type=int, help="Seconds to trim")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--output-dir", "-o", default="./downloaded", help="Output directory")
    args = parser.parse_args()

    DEBUG = args.debug
    is_audio = args.command == "audio"
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    url_file = "urls.txt"
    if not os.path.exists(url_file):
        print(f"Error: {url_file} not found.")
        sys.exit(1)
    with open(url_file, "r", encoding='utf-8') as f:
        urls = [url.strip() for line in f for url in line.split(";") if url.strip()]
    if not urls:
        print(f"Error: {url_file} is empty.")
        sys.exit(1)
    unique_urls = list(dict.fromkeys(urls))

    current_number = 1

    for index, url in enumerate(unique_urls):
        print(f"\nProcessing {'audio' if is_audio else 'video'} {index + 1}/{len(unique_urls)}: {url}")
        # Use unique temp base name to avoid overwriting
        shortcode = url.split('youtu.be/')[-1].split('?')[0]  # Extract video ID
        temp_media = os.path.join(output_dir, f"temp_media_{shortcode}")
        temp_files = [temp_media + ext for ext in [".m4a", ".mp4", ".webm", ".mkv", ".part", ".webp", ".jpg", ".jpeg", ".png"]]
        for temp in temp_files:
            safe_remove(temp)

        media_ext = ".m4a" if is_audio else ".mp4"
        title = get_video_title(url) or f"Untitled_{index + 1}"
        output_name, thumb_name, new_number = get_next_available_name(output_dir, media_ext, title, current_number)
        output_path = os.path.join(output_dir, output_name)
        thumb_path = os.path.join(output_dir, thumb_name)

        success, output = run_yt_dlp(url, temp_media + ".%(ext)s", is_audio)
        if not success:
            print(f"Failed to download: {url}")
            print(f"Output: {output}")
            continue

        media_file = None
        for ext in [".m4a" if is_audio else ".mp4", ".webm", ".mkv"]:
            if os.path.exists(temp_media + ext):
                media_file = temp_media + ext
                break
        if not media_file:
            print(f"No media file for: {url}")
            continue

        thumb_file = None
        for ext in [".webp", ".jpg", ".jpeg", ".png"]:
            if os.path.exists(temp_media + ext):  # Check temp_media.<ext> for thumbnail
                thumb_file = temp_media + ext
                break

        if args.trim:
            temp_trimmed = os.path.join(output_dir, f"temp_media_trimmed_{shortcode}{media_ext}")
            codec = 'copy' if not is_audio else 'aac -b:a 192k'
            stream_spec = '-vn' if is_audio else ''
            ffmpeg_cmd = f'ffmpeg -i "{media_file}" {stream_spec} -t {args.trim} -c:v copy -c:a {codec} "{temp_trimmed}"'
            success, ffmpeg_output = run_command(ffmpeg_cmd)
            if success:
                safe_remove(media_file)
                media_file = temp_trimmed
            else:
                print(f"Failed to trim: {url}")
                print(f"FFmpeg output: {ffmpeg_output}")
                continue

        if is_audio:
            ffmpeg_cmd = f'ffmpeg -i "{media_file}" -c:a aac -b:a 192k -ar 44100 "{output_path}"'
        else:
            width, height = get_video_dimensions(media_file)
            width = width + (width % 2)
            height = height + (height % 2)
            aspect_ratio = width / height if height > 0 else 1
            if aspect_ratio > 1.5:
                target_width, target_height = 1920, 1080
            elif aspect_ratio < 0.67:
                target_width, target_height = 1080, 1920
            else:
                target_width, target_height = 1080, 1080
            ffmpeg_cmd = (
                f'ffmpeg -i "{media_file}" -c:v libx264 -preset fast -b:v 3500k -r 30 '
                f'-vf "scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2" '
                f'-c:a aac -b:a 192k -ar 44100 -pix_fmt yuv420p "{output_path}"'
            )

        success, ffmpeg_output = run_command(ffmpeg_cmd)
        if success:
            safe_remove(media_file)
            print(f"Saved {'Audio' if is_audio else 'Video'}: {output_path}")
            if thumb_file:
                if not thumb_file.endswith('.webp'):
                    thumb_temp = temp_media + ".webp"
                    success, convert_output = run_command(f'ffmpeg -i "{thumb_file}" -c:v libwebp "{thumb_temp}"')
                    if success:
                        safe_remove(thumb_file)
                        thumb_file = thumb_temp
                    else:
                        debug_print(f"Failed to convert thumbnail to WebP: {convert_output}")
                try:
                    if os.path.exists(thumb_path):
                        safe_remove(thumb_path)
                    os.rename(thumb_file, thumb_path)
                    print(f"Saved Thumbnail: {thumb_path}")
                except Exception as e:
                    debug_print(f"Error renaming thumbnail {thumb_file} to {thumb_path}: {e}")
            current_number = new_number
        else:
            print(f"Failed to convert: {url}")
            print(f"FFmpeg output: {ffmpeg_output}")

        # Clean up all temporary files
        for temp in temp_files:
            safe_remove(temp)

if __name__ == "__main__":
    main()
