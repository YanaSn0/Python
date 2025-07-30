import subprocess
import sys
import os
import argparse
import glob
import json
import time
import shutil
from PIL import Image

DEBUG = False

def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)

def run_command(command, suppress_errors=False, timeout=None, retries=1):
    attempt = 0
    while attempt <= retries:
        debug_print(f"Running command (Attempt {attempt+1}/{retries+1}): {command}")
        stdout = subprocess.PIPE if not suppress_errors else subprocess.DEVNULL
        stderr = subprocess.PIPE if not suppress_errors else subprocess.DEVNULL
        process = subprocess.Popen(command, shell=True, stdout=stdout, stderr=stderr, text=True)
        output, errors = [], []
        try:
            stdout_data, stderr_data = process.communicate(timeout=timeout)
            if stdout_data:
                debug_print(stdout_data, end='')
                output.append(stdout_data)
            if stderr_data:
                debug_print(stderr_data, end='')
                errors.append(stderr_data)
            return_code = process.returncode
            output_str = ''.join(output)
            error_str = ''.join(errors)
            debug_print(f"Command finished: return_code={return_code}")
            if return_code != 0:
                if not suppress_errors:
                    debug_print(f"Error: return_code={return_code}. Output: {output_str}\nErrors: {error_str}")
                return False, output_str + "\n" + error_str
            return True, output_str
        except subprocess.TimeoutExpired:
            process.kill()
            attempt += 1
            if attempt <= retries:
                debug_print(f"Timeout after {timeout}s. Retrying {attempt}/{retries}")
                time.sleep(2)
                continue
            debug_print(f"Timeout after {timeout}s. No more retries")
            return False, f"Timeout after {timeout}s"
        except Exception as ex:
            process.kill()
            debug_print(f"Error: {ex}")
            return False, str(ex)
        finally:
            if process.poll() is None:
                process.terminate()

def get_next_available_name(output_dir, prefix, extension, start_number=1):
    number = start_number
    while True:
        name = f"{prefix}_{number}{extension}"
        full_path = os.path.join(output_dir, name)
        if not os.path.exists(full_path):
            return name, full_path, number + 1
        number += 1

def has_audio_stream(file_path):
    command = f'ffprobe -v error -show_streams -select_streams a -of default=noprint_wrappers=1 "{file_path}"'
    debug_print(f"Checking audio: {command}")
    success, output = run_command(command)
    return bool(output.strip())

def get_video_dimensions(file_path):
    command = f'ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of json "{file_path}"'
    success, output = run_command(command)
    if success:
        try:
            data = json.loads(output)
            if data.get('streams'):
                return data['streams'][0]['width'], data['streams'][0]['height']
        except json.JSONDecodeError:
            pass
    print(f"Warning: Could not get dimensions for {file_path}. Using 1920x1080")
    return 1920, 1080

def extract_number(filename):
    import re
    match = re.search(r'_(\d+)_', filename)
    return int(match.group(1)) if match else 0

def main():
    global DEBUG
    parser = argparse.ArgumentParser(description="Concatenate 2 Pic slides and 2 Uni reels with extra files as singles")
    parser.add_argument("input_dir", help="Input directory containing files")
    parser.add_argument("--output-dir", default=".", help="Output directory")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--resolution", default="1920x1080", help="Target resolution (e.g., 1920x1080)")
    parser.add_argument("--quality", type=int, choices=[1, 2, 3], default=3, help="Quality level (1=fastest, 3=slowest/best quality)")
    args = parser.parse_args()
    DEBUG = args.debug

    # Map quality level to FFmpeg preset
    preset_map = {1: "ultrafast", 2: "medium", 3: "veryslow"}
    ffmpeg_preset = preset_map[args.quality]

    # Parse resolution
    try:
        target_width, target_height = map(int, args.resolution.split('x'))
        if target_width % 2 != 0 or target_height % 2 != 0:
            raise ValueError("Resolution dimensions must be even")
    except ValueError as e:
        print(f"Error: Invalid resolution format '{args.resolution}'. Use WIDTHxHEIGHT (e.g., 1920x1080). Error: {e}")
        sys.exit(1)

    input_dir = os.path.abspath(args.input_dir)
    output_dir = os.path.abspath(args.output_dir)
    if not os.path.exists(input_dir):
        print(f"Error: Input directory does not exist: {input_dir}")
        sys.exit(1)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    temp_dir = os.path.abspath(os.path.join(".", "temp"))
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    # Get all .mp4 files and sort by filename to ensure consistent order
    all_files = glob.glob(os.path.join(input_dir, "*.mp4"))
    if not all_files:
        print(f"Error: No .mp4 files found in {input_dir}")
        sys.exit(1)
    all_files.sort()  # Sort alphabetically to get the first file consistently

    # Initialize or load existing metadata
    metadata_file = os.path.join(output_dir, "concat_metadata.json")
    if os.path.exists(metadata_file):
        with open(metadata_file, "r") as f:
            metadata = json.load(f)
        if not isinstance(metadata.get("input_videos", []), list):
            metadata["input_videos"] = []
        if "output_video" not in metadata:
            metadata["output_video"] = ""
    else:
        metadata = {"input_videos": [], "output_video": ""}
    
    try:
        # Normalize paths for comparison
        existing_videos = set(metadata["input_videos"])
        current_input_videos = [os.path.normpath(f).replace(os.sep, '/') for f in all_files]
        existing_output = metadata.get("output_video", "")
        
        if existing_output and os.path.exists(existing_output) and all(v in existing_videos for v in current_input_videos):
            print(f"Skipping: all input files have already been used for {os.path.basename(existing_output)}")
            new_videos = [v.replace(os.sep, '/') for v in all_files if v.replace(os.sep, '/') not in existing_videos]
            if new_videos:
                metadata["input_videos"].extend(new_videos)
                with open(metadata_file, "w") as f:
                    json.dump(metadata, f, indent=4)
                print(f"Updated metadata with new videos to {metadata_file.replace(os.sep, '/')}")
            else:
                print(f"No new videos to add, metadata unchanged at {metadata_file.replace(os.sep, '/')}")
            sys.exit(0)

        debug_print(f"Found files: {all_files}")

        # Categorize and sort files numerically
        pic_files = sorted([f for f in all_files if "pic" in f.lower()], key=extract_number)
        uni_files = sorted([f for f in all_files if "uni" in f.lower()], key=extract_number)
        other_files = [f for f in all_files if f not in pic_files and f not in uni_files]

        # Use the first file as the warning file
        warning_file = all_files[0]  # First file in sorted order
        input_files = [warning_file]
        all_files.remove(warning_file)  # Remove it to avoid duplication

        # Recategorize remaining files
        pic_files = [f for f in all_files if "pic" in f.lower()]
        uni_files = [f for f in all_files if "uni" in f.lower()]
        other_files = [f for f in all_files if f not in pic_files and f not in uni_files]

        # Sort remaining files numerically
        pic_files.sort(key=extract_number)
        uni_files.sort(key=extract_number)

        # Process in 2 Pic, 2 Uni chunks, ensuring all files are included
        pic_index = 0
        uni_index = 0
        while pic_index < len(pic_files) or uni_index < len(uni_files):
            # Add up to 2 Pic files if available
            input_files.extend(pic_files[pic_index:pic_index + 2])
            pic_index += 2
            # Add up to 2 Uni files if available
            input_files.extend(uni_files[uni_index:uni_index + 2])
            uni_index += 2

        # Add any remaining other files
        input_files.extend(other_files)

        debug_print(f"Processing order: {input_files}")

        # Process each file to ensure consistent format
        processed_videos = []
        video_filters = [
            f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease:force_divisible_by=2",
            f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2",
            "setsar=1",
            "fps=30"
        ]
        video_filter_string = ",".join(video_filters)

        for i, file_path in enumerate(input_files):
            temp_output_name, temp_output_path, _ = get_next_available_name(temp_dir, f"Temp_{i+1}", ".mp4")
            has_audio = has_audio_stream(file_path)
            if has_audio:
                ffmpeg_command = (
                    f'ffmpeg -y -i "{file_path}" '
                    f'-c:v libx264 -preset {ffmpeg_preset} -b:v 5000k -r 30 -pix_fmt yuv420p '
                    f'-force_key_frames "expr:gte(t,n_forced*2)" '
                    f'-c:a aac -b:a 192k -ar 48000 -ac 2 '
                    f'-vf "{video_filter_string}" '
                    f'"{temp_output_path}"'
                )
            else:
                ffmpeg_command = (
                    f'ffmpeg -y -i "{file_path}" '
                    f'-f lavfi -i anullsrc=channel_layout=stereo:sample_rate=48000 '
                    f'-c:v libx264 -preset {ffmpeg_preset} -b:v 5000k -r 30 -pix_fmt yuv420p '
                    f'-force_key_frames "expr:gte(t,n_forced*2)" '
                    f'-c:a aac -b:a 192k -ar 48000 -ac 2 -shortest '
                    f'-vf "{video_filter_string}" '
                    f'"{temp_output_path}"'
                )
            debug_print(f"FFmpeg command for {os.path.basename(file_path)}: {ffmpeg_command}")
            success, output = run_command(ffmpeg_command, timeout=300, retries=1)
            if success and os.path.exists(temp_output_path):
                print(f"Processed {os.path.basename(file_path)} as {temp_output_path.replace(os.sep, '/')}")
                if file_path.replace(os.sep, '/') not in existing_videos:
                    metadata["input_videos"].append(file_path.replace(os.sep, '/'))
                processed_videos.append(temp_output_path)
            else:
                print(f"Failed to process {file_path} into video: {output}")
                sys.exit(1)

        # Concatenate using concat filter
        input_string = " ".join([f"-i \"{v}\"" for v in processed_videos])
        filter_inputs = []
        stream_map = []
        for i, video in enumerate(processed_videos):
            has_audio = has_audio_stream(video)
            filter_inputs.append(f"[{i}:v]")
            stream_map.append(f"{i}:v")
            if has_audio:
                filter_inputs.append(f"[{i}:a]")
                stream_map.append(f"{i}:a")

        concat_filter = f"{' '.join(filter_inputs)}concat=n={len(processed_videos)}:v=1:a={1 if any(has_audio_stream(v) for v in processed_videos) else 0}[outv]{'[outa]' if any(has_audio_stream(v) for v in processed_videos) else ''}"
        map_string = "-map [outv]" + (" -map [outa]" if any(has_audio_stream(v) for v in processed_videos) else " -an")
        final_output_path = existing_output if existing_output and os.path.exists(existing_output) else os.path.join(output_dir, get_next_available_name(output_dir, "Concat", ".mp4")[1])
        ffmpeg_command = (
            f'ffmpeg -y {input_string} '
            f'-filter_complex "{concat_filter}" '
            f'{map_string} '
            f'-c:v libx264 -preset {ffmpeg_preset} -b:v 5000k -r 30 -pix_fmt yuv420p '
            f'{"-c:a aac -b:a 192k -ar 48000 -ac 2" if any(has_audio_stream(v) for v in processed_videos) else "-an"} '
            f'"{final_output_path}"'
        )
        debug_print(f"FFmpeg concat command: {ffmpeg_command}")
        success, output = run_command(ffmpeg_command, timeout=600, retries=1)
        if success:
            print(f"Saved as {final_output_path.replace(os.sep, '/')} ({len(processed_videos)} segments)")
            metadata["output_video"] = final_output_path.replace(os.sep, '/')
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=4)
            print(f"Saved metadata to {metadata_file.replace(os.sep, '/')}")
            # Clean up temporary files
            for video in processed_videos:
                if os.path.exists(video):
                    os.remove(video)
                    debug_print(f"Removed temporary file: {video}")
        else:
            print(f"Concatenation failed: {output}")
            sys.exit(1)
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    main()
