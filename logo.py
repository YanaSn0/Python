import os
import subprocess
import sys

def get_video_resolution(video_path):
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
        data = eval(result.stdout)  # Simplified JSON parsing
        width = data['streams'][0]['width']
        height = data['streams'][0]['height']
        return width, height
    except subprocess.CalledProcessError as e:
        print(f"Error processing {video_path}: {e}")
        return None
    except (KeyError, IndexError):
        print(f"Could not extract resolution from {video_path}")
        return None

def process_videos_in_folder(folder_path, x_offset, y_offset):
    if not os.path.isdir(folder_path):
        print(f"Error: {folder_path} is not a valid directory")
        return

    # Focus on .mp4 files specifically
    videos = [f for f in os.listdir(folder_path) if f.lower().endswith('.mp4')]

    if not videos:
        print(f"No .mp4 files found in {folder_path}")
        return

    watermark_path = os.path.join(folder_path, "watermark.png")
    if not os.path.exists(watermark_path):
        print(f"Error: watermark.png not found in {folder_path}")
        return

    print(f"Found .mp4 videos in {folder_path}:")
    for video in videos:
        video_path = os.path.join(folder_path, video)
        resolution = get_video_resolution(video_path)
        if resolution:
            width, height = resolution
            print(f"{video}: {width}x{height}")
            # FFmpeg command with .mp4 output, using existing watermark.png, custom position
            output_video = os.path.join(folder_path, f"output_{os.path.splitext(video)[0]}.mp4")
            ffmpeg_cmd = f'ffmpeg -i {video_path} -i {watermark_path} -filter_complex "overlay=main_w-overlay_w-{x_offset}:main_h-overlay_h-{y_offset}" -c:a copy {output_video}'
            print(f"FFmpeg command:\n```{ffmpeg_cmd}```")
            # Execute the FFmpeg command
            try:
                subprocess.run(ffmpeg_cmd, shell=True, check=True)
                print(f"Successfully created {output_video}")
            except subprocess.CalledProcessError as e:
                print(f"Error executing FFmpeg: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python logo.py <folder_path> <x_offset> <y_offset>")
        sys.exit(1)

    folder_path = sys.argv[1]
    x_offset = sys.argv[2]  # Distance from right edge
    y_offset = sys.argv[3]  # Distance from bottom edge
    process_videos_in_folder(folder_path, x_offset, y_offset)