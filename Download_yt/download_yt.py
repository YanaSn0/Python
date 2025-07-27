import subprocess
import os
import argparse
import re
import json
import sys
import shutil
import time
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def check_dependencies():
    """Check if required tools are installed."""
    for cmd in ["yt-dlp", "ffmpeg", "ffprobe"]:
        if not shutil.which(cmd):
            logging.error(f"{cmd} not found. Please install it.")
            sys.exit(1)

def run_command(command, timeout=600):
    """Execute a shell command with a timeout and print output in real-time."""
    logging.debug(f"Executing: {command}")
    try:
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')
        output_lines = []
        for line in process.stdout:
            print(line, end='')  # Print each line immediately to show progress
            output_lines.append(line.strip())
            logging.debug(line.strip())  # Log all output for verbose debugging
        output = "\n".join(output_lines)
        return True, output  # Assume success if output is captured, check title manually
    except subprocess.TimeoutExpired:
        logging.error(f"Command timed out after {timeout} seconds: {command}")
        process.kill()
        return False, "Timeout"
    except Exception as e:
        logging.error(f"Exception running command: {e}")
        return False, str(e)

def safe_remove(file_path):
    """Safely delete a file."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logging.debug(f"Deleted: {file_path}")
    except Exception as e:
        logging.error(f"Error deleting {file_path}: {e}")

def get_video_dimensions(video_path):
    """Get video dimensions using ffprobe."""
    cmd = f'ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of json "{video_path}"'
    success, output = run_command(cmd)
    if success:
        try:
            data = json.loads(output)
            if data.get('streams'):
                return data['streams'][0]['width'], data['streams'][0]['height']
        except json.JSONDecodeError:
            logging.error(f"Error parsing ffprobe output: {output}")
    logging.warning(f"Using default 1920x1080 for {video_path}")
    return 1920, 1080

def sanitize_filename(filename):
    """Sanitize filename by removing invalid characters."""
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '_', filename)
    sanitized = re.sub(r'\s+', '_', sanitized.strip())
    return sanitized[:200]

def get_next_available_name(output_dir, media_ext, title, include_thumb=False):
    """Generate unique filenames with title_trim_X pattern."""
    sanitized_name = sanitize_filename(title if title else "Untitled")
    trim_number = 1
    while True:
        media_name = f"{sanitized_name}_trim_{trim_number}{media_ext}"
        thumb_name = f"{sanitized_name}_trim_{trim_number}_thumb.webp" if include_thumb else None
        full_media_path = os.path.join(output_dir, media_name)
        logging.debug(f"Checking if {full_media_path} exists")
        if not os.path.exists(full_media_path):
            logging.debug(f"Selected {media_name} as available")
            return media_name, thumb_name, trim_number + 1
        trim_number += 1
        logging.debug(f"File exists, incrementing to trim_{trim_number}")

def run_yt_dlp(url, output_path, is_audio=False, start_time=0, duration=None, include_thumb=False):
    """Run yt-dlp to download media with optional trimming and thumbnail."""
    clean_url = re.sub(r'\?si=[^&]*', '', url)
    cmd = f'yt-dlp "{clean_url}" -o "{output_path}" --geo-bypass --verbose'
    if is_audio:
        cmd += ' --extract-audio --audio-format m4a --audio-quality 192k --format bestaudio'
    else:
        cmd += ' --format "bestvideo+bestaudio/best" --merge-output-format mp4'
    if duration:
        cmd += f' --postprocessor-args "ffmpeg:-ss {start_time} -t {duration}"'
    if not include_thumb:
        cmd += ' --no-write-thumbnail'
    return run_command(cmd)

def get_video_title(url):
    """Get video title using yt-dlp."""
    clean_url = re.sub(r'\?si=[^&]*', '', url)
    cmd = f'yt-dlp "{clean_url}" --get-title --geo-bypass'
    success, output = run_command(cmd)
    if output:  # Check if output contains the title, regardless of success flag
        for line in output.split('\n'):
            line = line.strip()
            if line and not line.startswith('['):
                return line
    logging.warning("Failed to retrieve title, using 'Untitled' as fallback")
    return "Untitled"

def time_to_seconds(time_str):
    """Convert HH:MM:SS or MM:SS format to seconds."""
    try:
        h, m, s = [float(x) for x in re.sub(r'^(\d+):(\d+):(\d+)$', r'\1:\2:\3', time_str).split(':')]
        return int(h * 3600 + m * 60 + s)
    except ValueError:
        m, s = [float(x) for x in re.sub(r'^(\d+):(\d+)$', r'\1:\2', time_str).split(':')]
        return int(m * 60 + s)

def main():
    """Main function to download and process YouTube media."""
    parser = argparse.ArgumentParser(description="Download YouTube media from urls.txt")
    parser.add_argument("command", choices=["audio", "full"], default="full", help="Download audio or full video")
    parser.add_argument("--start", type=str, default="0:00", help="Start time in HH:MM:SS or MM:SS format")
    parser.add_argument("--end", type=str, help="End time in HH:MM:SS or MM:SS format")
    parser.add_argument("--thumb", action="store_true", help="Include thumbnail in output")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--output-dir", "-o", default="./downloaded", help="Output directory")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    check_dependencies()
    is_audio = args.command == "audio"
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    url_file = "urls.txt"
    if not os.path.exists(url_file):
        logging.error(f"{url_file} not found.")
        sys.exit(1)
    with open(url_file, "r", encoding='utf-8') as f:
        urls = [url.strip() for line in f for url in line.split(";") if url.strip()]
    if not urls:
        logging.error(f"{url_file} is empty.")
        sys.exit(1)
    unique_urls = list(dict.fromkeys(urls))

    current_number = 1

    for index, url in enumerate(unique_urls):
        logging.info(f"\nProcessing {'audio' if is_audio else 'video'} {index + 1}/{len(unique_urls)}: {url}")
        shortcode = url.split('youtu.be/')[-1].split('?')[0]
        temp_media = os.path.join(output_dir, f"temp_media_{shortcode}")
        temp_files = [temp_media + ext for ext in [".m4a", ".mp4", ".webm", ".mkv", ".part", ".webp", ".jpg", ".jpeg", ".png"]]
        for temp in temp_files:
            safe_remove(temp)

        media_ext = ".m4a" if is_audio else ".mp4"
        title = get_video_title(url)
        logging.debug(f"Initial title from output: {title}")
        logging.debug(f"Final title before filename: {title}")
        output_name, thumb_name, new_number = get_next_available_name(output_dir, media_ext, title, args.thumb)
        output_path = os.path.join(output_dir, output_name)
        thumb_path = os.path.join(output_dir, thumb_name) if thumb_name else None

        # Convert start and end times to seconds
        start_seconds = time_to_seconds(args.start)
        end_seconds = time_to_seconds(args.end) if args.end else None
        duration = end_seconds - start_seconds if end_seconds else None

        if duration and duration <= 0:
            logging.error(f"End time ({args.end}) must be after start time ({args.start})")
            continue

        success, output = run_yt_dlp(url, temp_media + ".%(ext)s", is_audio, start_seconds, duration, args.thumb)
        if not success:
            logging.error(f"Failed to download: {url}")
            logging.error(f"Output: {output}")
            continue

        media_file = None
        for ext in [".m4a" if is_audio else ".mp4", ".webm", ".mkv"]:
            if os.path.exists(temp_media + ext):
                media_file = temp_media + ext
                break
        if not media_file:
            logging.error(f"No media file found for: {url}")
            continue

        # Move temp file to final output path
        if os.path.exists(media_file):
            try:
                shutil.move(media_file, output_path)
                logging.info(f"Saved {'Audio' if is_audio else 'Video'}: {output_path}")
            except Exception as e:
                logging.error(f"Error moving {media_file} to {output_path}: {e}")
                continue
        else:
            logging.error(f"Media file {media_file} not created")
            continue

        if thumb_path and os.path.exists(temp_media + ".webp"):
            thumb_file = temp_media + ".webp"
            try:
                shutil.move(thumb_file, thumb_path)
                logging.info(f"Saved Thumbnail: {thumb_path}")
            except Exception as e:
                logging.error(f"Error moving thumbnail {thumb_file} to {thumb_path}: {e}")

        for temp in temp_files:
            safe_remove(temp)

        current_number = new_number

if __name__ == "__main__":
    main()
