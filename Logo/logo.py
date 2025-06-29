import os
import subprocess
import sys
import argparse
import json
import logging
import shutil
import uuid
import time

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)
logger = logging.getLogger(__name__)

# Get the directory where the script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Define the logo folder path (subfolder named 'logo' in script directory)
LOGO_FOLDER = os.path.join(SCRIPT_DIR, 'logo')

def is_file_locked(file_path, retries=3, delay=4):
    """Check if a file is locked by attempting to open it."""
    for attempt in range(retries):
        try:
            with open(file_path, 'a'):
                return False
        except (IOError, PermissionError, OSError):
            time.sleep(delay)
    logger.error(f"File {file_path} is locked after {retries} attempts")
    return True

def get_video_resolution(video_path):
    """Retrieve the resolution of a video using ffprobe."""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'json',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        width = data['streams'][0]['width']
        height = data['streams'][0]['height']
        return width, height
    except subprocess.CalledProcessError as e:
        logger.error(f"Error processing {video_path}: {e}")
        return None
    except (KeyError, IndexError, json.JSONDecodeError):
        logger.error(f"Could not extract resolution from {video_path}")
        return None

def get_metadata(file_path):
    """Extract metadata from a video file using ffprobe."""
    cmd = f'ffprobe -v quiet -print_format json -show_format -show_streams "{file_path}"'
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            check=True
        )
        metadata = json.loads(result.stdout)
        tags = metadata.get('format', {}).get('tags', {})
        return {
            'title': tags.get('title', os.path.basename(file_path)),
            'artist': tags.get('artist', 'Unknown'),
            'album': tags.get('album', ''),
            'duration': metadata.get('format', {}).get('duration', '')
        }, ""
    except subprocess.CalledProcessError as e:
        return {}, f"FFprobe error: {str(e)}"
    except json.JSONDecodeError:
        return {}, "Failed to parse metadata JSON"

def apply_metadata(src_path, logo_path, dest_path, metadata_dict, x_offset, y_offset):
    """Apply metadata and watermark to the output video using ffmpeg."""
    temp_output = dest_path + f".temp_{uuid.uuid4().hex[:12]}.tmp"
    metadata_args = []
    for key, value in metadata_dict.items():
        if value:
            metadata_args.append(f'-metadata {key}="{value.replace('"', '')}"')
    metadata_cmd = " ".join(metadata_args) if metadata_args else ""
    cmd = (
        f'ffmpeg -i "{src_path}" -i "{logo_path}" '
        f'-filter_complex "overlay=main_w-overlay_w-{x_offset}:main_h-overlay_h-{y_offset}" '
        f'-c:v libx264 -c:a copy -f mp4 -y {metadata_cmd} "{temp_output}"'
    )
    try:
        subprocess.run(cmd, shell=True, check=True)
        if os.path.exists(temp_output):
            shutil.move(temp_output, dest_path)
            return True, ""
        return False, "Failed to move temp file"
    except subprocess.CalledProcessError as e:
        return False, f"FFmpeg error: {str(e)}"

def process_videos_in_folder(folder_path, prefix, logo_file, x_offset, y_offset, metadata=False, skipped=False):
    """Process all .mp4 files in the folder, applying a watermark and saving to a subfolder."""
    abs_folder_path = os.path.abspath(folder_path).replace('/', os.sep)
    if not os.path.isdir(abs_folder_path):
        logger.error(f"Error: {abs_folder_path} is not a valid directory")
        sys.exit(1)

    # Check for logo file in the 'logo' subfolder of script directory
    logo_path = os.path.join(LOGO_FOLDER, logo_file)
    if not os.path.exists(logo_path):
        logger.error(f"Error: {logo_file} not found in {LOGO_FOLDER}")
        sys.exit(1)

    # Create output folder named after the prefix
    output_folder = os.path.join(abs_folder_path, prefix)
    os.makedirs(output_folder, exist_ok=True)

    # Focus on .mp4 files
    videos = [f for f in os.listdir(abs_folder_path) if f.lower().endswith('.mp4')]
    if not videos:
        logger.error(f"No .mp4 files found in {abs_folder_path}")
        sys.exit(1)

    skipped_files = []
    processed_files = []

    logger.info(f"Found .mp4 videos in {abs_folder_path}:")
    for video in sorted(videos, key=lambda x: x.lower()):
        video_path = os.path.join(abs_folder_path, video)
        if is_file_locked(video_path):
            skipped_files.append((video, video_path, "File is locked"))
            logger.error(f"Skipped {video}: File is locked")
            continue

        resolution = get_video_resolution(video_path)
        if not resolution:
            skipped_files.append((video, video_path, "Could not extract resolution"))
            continue

        width, height = resolution
        logger.info(f"{video}: {width}x{height}")

        # Generate new filename with prefix
        new_name = f"{prefix}_{os.path.splitext(video)[0]}{os.path.splitext(video)[1]}"  # Add prefix to original filename
        output_video = os.path.join(output_folder, new_name)
        counter = 1
        while os.path.exists(output_video):
            base, ext = os.path.splitext(new_name)
            output_video = os.path.join(output_folder, f"{base}_{counter}{ext}")
            counter += 1

        # Get metadata if requested
        metadata_dict = {}
        if metadata:
            metadata_dict, meta_error = get_metadata(video_path)
            if meta_error:
                logger.warning(f"Metadata extraction failed for {video}: {meta_error}")
                skipped_files.append((video, video_path, f"Metadata extraction error: {meta_error}"))

        # FFmpeg command to apply watermark
        ffmpeg_cmd = (
            f'ffmpeg -i "{video_path}" -i "{logo_path}" '
            f'-filter_complex "overlay=main_w-overlay_w-{x_offset}:main_h-overlay_h-{y_offset}" '
            f'-c:v libx264 -c:a copy -f mp4 "{output_video}"'
        )
        logger.info(f"FFmpeg command:\n```{ffmpeg_cmd}```")

        # Execute FFmpeg command or apply metadata
        try:
            if metadata and metadata_dict:
                success, error = apply_metadata(video_path, logo_path, output_video, metadata_dict, x_offset, y_offset)
                if not success:
                    logger.warning(f"Metadata application failed for {video}: {error}, proceeding without metadata")
                    subprocess.run(ffmpeg_cmd, shell=True, check=True)
            else:
                subprocess.run(ffmpeg_cmd, shell=True, check=True)
            logger.info(f"Successfully created {output_video}")
            processed_files.append((video, output_video))
        except subprocess.CalledProcessError as e:
            logger.error(f"Error executing FFmpeg for {video}: {e}")
            skipped_files.append((video, video_path, f"FFmpeg error: {str(e)}"))

    # Generate skipped files report if requested
    if skipped and skipped_files:
        skipped_report_file = os.path.join(output_folder, "skipped.txt")
        try:
            with open(skipped_report_file, 'w', encoding='utf-8') as f:
                f.write("Skipped files:\n")
                total_size = 0
                for orig_name, path, reason in sorted(skipped_files, key=lambda x: x[0].lower()):
                    f.write(f"{orig_name} at {path}: {reason}\n")
                    if os.path.exists(path):
                        size = os.path.getsize(path) / (1024 ** 2)
                        total_size += size
                        f.write(f"  Size: {size:.2f} MB\n")
                    else:
                        f.write("  Size: File not found\n")
                f.write(f"Total skipped size: {total_size:.2f} MB\n")
            logger.info(f"Skip report generated at {skipped_report_file}")
        except Exception as e:
            logger.error(f"Failed to write skipped report: {str(e)}")

    logger.info(f"Processed {len(processed_files)} files")

def main():
    """Parse command-line arguments and process videos."""
    parser = argparse.ArgumentParser(description="Add a watermark to .mp4 files and rename with a prefix")
    parser.add_argument("prefix", help="Prefix for output video filenames and output folder")
    parser.add_argument("logo_file", help="Name of the logo file (e.g., logo1.png) in the 'logo' subfolder")
    parser.add_argument("x_offset", type=int, help="X offset from right edge for watermark")
    parser.add_argument("y_offset", type=int, help="Y offset from bottom edge for watermark")
    parser.add_argument("folder_path", help="Folder path containing .mp4 files")
    parser.add_argument("--metadata", action="store_true", help="Apply metadata to output videos")
    parser.add_argument("--skipped", action="store_true", help="Generate skipped files report")
    args = parser.parse_args()

    process_videos_in_folder(
        folder_path=args.folder_path,
        prefix=args.prefix,
        logo_file=args.logo_file,
        x_offset=args.x_offset,
        y_offset=args.y_offset,
        metadata=args.metadata,
        skipped=args.skipped
    )

if __name__ == "__main__":
    main()
