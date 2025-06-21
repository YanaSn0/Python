import os
import argparse
import re
import subprocess
import sys
import json
import logging
import shutil
import uuid
import hashlib
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)
logger = logging.getLogger(__name__)

def is_file_locked(file_path, retries=3, delay=4):
    for attempt in range(retries):
        try:
            with open(file_path, 'a'):
                return False
        except (IOError, PermissionError, OSError):
            time.sleep(delay)
    logger.error(f"File {file_path} is locked after {retries} attempts")
    return True

def sanitize_filename(filename):
    invalid_chars = r'[<>:"/\\|?*;\x00-\x1F]'
    sanitized = re.sub(invalid_chars, '_', filename)
    max_length = 100
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    return sanitized or 'unnamed'

def get_file_hash(file_path):
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return str(uuid.uuid4())

def run_command(command, timeout=15):
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(timeout=timeout)
        return stdout or "", stderr if process.returncode != 0 else ""
    except Exception as e:
        return None, str(e)
    finally:
        try:
            process.terminate()
            process.wait(timeout=5)
        except:
            pass

def get_metadata(file_path):
    cmd = f'ffprobe -v quiet -print_format json -show_format -show_streams "{file_path}"'
    stdout, stderr = run_command(cmd)
    if stdout:
        try:
            metadata = json.loads(stdout)
            tags = metadata.get('format', {}).get('tags', {})
            return {
                'title': tags.get('title', os.path.basename(file_path)),
                'artist': tags.get('artist', 'Unknown'),
                'album': tags.get('album', ''),
                'duration': metadata.get('format', {}).get('duration', '')
            }, ""
        except json.JSONDecodeError:
            return {}, "Failed to parse metadata JSON"
    return {}, stderr or "No metadata retrieved"

def apply_metadata(src_path, dest_path, metadata_dict):
    temp_output = dest_path + f".temp_{uuid.uuid4().hex[:12]}.tmp"
    metadata_args = []
    for key, value in metadata_dict.items():
        if value:
            metadata_args.append(f'-metadata {key}="{value.replace('"', '')}"')
    metadata_cmd = " ".join(metadata_args) if metadata_args else ""
    cmd = (
        f'ffmpeg -i "{src_path}" -c copy -map 0 -y '
        f'{metadata_cmd} "{temp_output}"'
    )
    _, stderr = run_command(cmd, timeout=30)
    if os.path.exists(temp_output):
        try:
            shutil.move(temp_output, dest_path)
            return True, ""
        except Exception as e:
            return False, f"Failed to move temp: {str(e)}"
    return False, stderr or "Failed to apply metadata"

def move_file(src, dest, metadata_dict=None, apply_metadata_flag=False, retries=3, delay=4):
    if not os.path.exists(src):
        raise FileNotFoundError(f"Source file does not exist: {src}")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    for attempt in range(retries):
        if is_file_locked(src):
            time.sleep(delay)
            continue
        try:
            counter = 1
            orig_dest = dest
            while os.path.exists(dest):
                base, ext = os.path.splitext(orig_dest)
                dest = f"{base}_{counter}{ext}"
                counter += 1
            if apply_metadata_flag and metadata_dict:
                success, error = apply_metadata(src, dest, metadata_dict)
                if not success:
                    logger.warning(f"Metadata application failed for {src}: {error}, proceeding without metadata")
                    shutil.move(src, dest)
            else:
                shutil.move(src, dest)
            if not os.path.exists(dest):
                raise FileNotFoundError(f"Destination file not created: {dest}")
            logger.info(f"Moved {src} to {dest}")
            return dest
        except (PermissionError, IOError, OSError) as e:
            logger.error(f"Move failed: {src} to {dest}, attempt {attempt + 1}/{retries}: {str(e)}")
            time.sleep(delay)
    raise IOError(f"Unable to move after {retries} attempts: {src}")

def process_files(folder_path, prefix, skipped, metadata, flatten_to_folder):
    abs_folder_path = os.path.abspath(folder_path).replace('/', os.sep)
    if not os.path.isdir(abs_folder_path):
        logger.error(f"'{abs_folder_path}' is not a directory.")
        sys.exit(1)

    skipped_files = []
    processed_files = []

    # If flatten_to_folder is True, use a subfolder named after the prefix
    if flatten_to_folder:
        target_folder = os.path.join(abs_folder_path, sanitize_filename(prefix))
    else:
        target_folder = abs_folder_path

    # Walk through folder and subfolders
    for root, dirs, files in os.walk(abs_folder_path):
        logger.info(f"Processing folder: {root}")
        # Skip files in the target folder to avoid processing already moved files
        if flatten_to_folder and os.path.abspath(root) == os.path.abspath(target_folder):
            logger.info(f"Skipping target folder: {root}")
            continue
        # Sort files for consistent processing
        for filename in sorted(files, key=lambda x: x.lower()):
            # Skip system files like desktop.ini and thumbs.db
            if filename.lower() in {'desktop.ini', 'thumbs.db'}:
                logger.info(f"Skipped system file: {filename}")
                continue
            full_path = os.path.join(root, filename)
            if not os.path.isfile(full_path):
                continue
            if is_file_locked(full_path):
                skipped_files.append((filename, full_path, "File is locked"))
                logger.error(f"Skipped {filename}: File is locked")
                continue

            ext = os.path.splitext(filename)[1] or '.unknown'
            new_name = f"{prefix}{ext}"
            # Use target_folder (prefix-named folder or root) for destination
            new_path = os.path.join(target_folder, new_name)

            try:
                metadata_dict = {}
                if metadata:
                    metadata_dict, meta_error = get_metadata(full_path)
                    if meta_error:
                        logger.warning(f"Metadata extraction failed for {filename}: {meta_error}")
                        skipped_files.append((filename, full_path, f"Metadata extraction error: {meta_error}"))

                final_path = move_file(
                    full_path,
                    new_path,
                    metadata_dict=metadata_dict if metadata_dict else None,
                    apply_metadata_flag=metadata
                )
                processed_files.append((filename, final_path))
                logger.info(f"Renamed {filename} to {os.path.basename(final_path)}")

            except Exception as e:
                skipped_files.append((filename, full_path, f"Rename error: {str(e)}"))
                logger.error(f"Skipped {filename}: {str(e)}")

    if skipped and skipped_files:
        skipped_report_file = os.path.join(abs_folder_path, "skipped.txt")
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
    parser = argparse.ArgumentParser(description="Rename files with a prefix, optionally moving to a new folder named after the prefix")
    parser.add_argument("prefix", help="Prefix for files and name of new folder if --folder is used")
    parser.add_argument("folder_path", help="Folder path to process")
    parser.add_argument("--skipped", action="store_true", help="Generate skipped files report")
    parser.add_argument("--metadata", action="store_true", help="Apply metadata to files")
    parser.add_argument("--folder", action="store_true", help="Move all files to a new folder named after the prefix")
    args = parser.parse_args()

    process_files(
        folder_path=args.folder_path,
        prefix=args.prefix,
        skipped=args.skipped,
        metadata=args.metadata,
        flatten_to_folder=args.folder
    )

if __name__ == "__main__":
    main()
