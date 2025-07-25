import subprocess
import sys
import os
import argparse

DEBUG = False

def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)

def run_command(command, suppress_errors=False):
    debug_print(f"Running command: {command}")
    stdout = subprocess.PIPE if not suppress_errors else subprocess.DEVNULL
    stderr = subprocess.PIPE if not suppress_errors else subprocess.DEVNULL
    process = subprocess.Popen(command, shell=True, stdout=stdout, stderr=stderr, text=True)
    stdout_data, stderr_data = process.communicate()
    output = stdout_data or ""
    errors = stderr_data or ""
    debug_print(f"Command finished: return_code={process.returncode}")
    if process.returncode != 0 and not suppress_errors:
        debug_print(f"Error output: {output}\n{errors}")
    return process.returncode == 0, output + "\n" + errors

def get_next_available_name(output_dir, prefix, extension, start_number=1):
    number = start_number
    while True:
        name = f"{prefix}_{number}{extension}"
        full_path = os.path.join(output_dir, name)
        if not os.path.exists(full_path):
            return name, full_path, number + 1
        number += 1

def find_video_file(video_path):
    extensions = ['.mp4', '.mkv']
    if os.path.splitext(video_path)[1].lower() in extensions and os.path.exists(video_path):
        return video_path
    directory = os.path.dirname(video_path) or "."
    base_name = os.path.splitext(os.path.basename(video_path))[0].lower()
    debug_print(f"Searching for video '{base_name}' in '{directory}'")
    for file in os.listdir(directory):
        if file.lower().startswith(base_name) and os.path.splitext(file)[1].lower() in extensions:
            debug_print(f"Found video: {os.path.join(directory, file)}")
            return os.path.join(directory, file)
    return None

def main():
    global DEBUG
    parser = argparse.ArgumentParser(description="Trim video between start and end times")
    parser.add_argument("type", choices=["v"], help="Output type (v for video)")
    parser.add_argument("input_path", help="Input video file")
    parser.add_argument("--start-time", type=float, required=True, help="Start time in seconds")
    parser.add_argument("--end-time", type=float, required=True, help="End time in seconds")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()
    DEBUG = args.debug

    input_path = args.input_path
    output_dir = args.output_dir or os.path.join(os.path.dirname(input_path), "split")
    actual_input = find_video_file(input_path)
    if not actual_input:
        print(f"Error: No input found: {input_path}")
        sys.exit(1)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Calculate duration
    duration = args.end_time - args.start_time
    if duration <= 0:
        print(f"Error: End time ({args.end_time}s) must be greater than start time ({args.start_time}s).")
        sys.exit(1)

    # Construct output path with incrementing number
    base_name = os.path.splitext(os.path.basename(actual_input))[0]
    output_name, output_path, _ = get_next_available_name(output_dir, f"V_{base_name}", ".mp4")
    output_path = output_path.replace(os.sep, '/')

    # FFmpeg command matching manual approach exactly
    ffmpeg_command = (
        f'ffmpeg -y -i "{actual_input}" -ss {args.start_time} -t {duration} '
        f'-c:v libx264 -c:a aac -b:a 128k -preset fast "{output_path}"'
    )
    success, output = run_command(ffmpeg_command)
    if success:
        print(f"Saved video as {output_path}")
    else:
        print(f"Trim failed for {actual_input}: {output}")
        sys.exit(1)

if __name__ == "__main__":
    main()
