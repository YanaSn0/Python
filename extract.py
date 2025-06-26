import os
import subprocess
import argparse

def create_output_subfolder(output_dir, video_filename):
    # Create a subfolder named after the video file (without extension)
    video_name = os.path.splitext(video_filename)[0]
    subfolder_path = os.path.join(output_dir, video_name)
    os.makedirs(subfolder_path, exist_ok=True)
    return subfolder_path

def extract_frames(input_dir, output_dir):
    # Ensure input and output directories exist
    if not os.path.exists(input_dir):
        print(f"Input directory '{input_dir}' does not exist.")
        return
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Supported video file extensions
    video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.webm')

    # Iterate through all files in the input directory
    for filename in os.listdir(input_dir):
        if filename.lower().endswith(video_extensions):
            input_video = os.path.join(input_dir, filename)
            output_subfolder = create_output_subfolder(output_dir, filename)

            # FFmpeg command to extract all frames
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', input_video,
                '-vf', 'fps=30',  # Adjust fps as needed
                os.path.join(output_subfolder, 'frame_%04d.png')
            ]

            try:
                # Run FFmpeg command
                print(f"Extracting frames from {filename} to {output_subfolder}")
                subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                print(f"Finished extracting frames from {filename}")
            except subprocess.CalledProcessError as e:
                print(f"Error processing {filename}: {e.stderr}")
            except FileNotFoundError:
                print("FFmpeg not found. Ensure FFmpeg is installed and added to your system PATH.")

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Extract frames from all videos in a folder using FFmpeg.")
    parser.add_argument('input_dir', help="Path to the input folder containing video files")
    parser.add_argument('output_dir', help="Path to the output folder for extracted frames")
    
    # Parse arguments
    args = parser.parse_args()

    # Run the extraction process
    extract_frames(args.input_dir, args.output_dir)

if __name__ == "__main__":
    main()
