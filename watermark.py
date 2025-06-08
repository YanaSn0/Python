#!/usr/bin/env python
# watermark.py
# Script using PyTorch-based LaMa for image inpainting and PaddleOCR for text detection
# Logs to console only for PowerShell capture

import os
import sys
import cv2
import numpy as np
from PIL import Image
import subprocess
import argparse
from pathlib import Path
from paddleocr import PaddleOCR
import logging
from multiprocessing import Pool, cpu_count
import tempfile
import torch
from lama.bin.predict import run as lama_inpaint

# Configure logging to console only
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# Global debug flag
DEBUG = False

def debug_print(*args, **kwargs):
    if DEBUG:
        logging.debug(*args, **kwargs)

def run_command(command, suppress_errors=False):
    debug_print(f"Executing command: {command}")
    stdout = subprocess.PIPE if not suppress_errors else subprocess.DEVNULL
    stderr = subprocess.STDOUT if not suppress_errors else subprocess.DEVNULL
    try:
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
        if not suppress_errors and process.stdout:
            for line in process.stdout:
                debug_print(line, end='')
                output.append(line)
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

def get_image_resolution(image_path):
    if not os.path.exists(image_path):
        logging.error(f"File '{image_path}' does not exist.")
        return None, None
    try:
        with Image.open(image_path) as img:
            width, height = img.size
        return width, height
    except Exception as e:
        logging.error(f"Error getting resolution for {image_path}: {e}")
        return None, None

def get_video_resolution(video_path):
    cmd = f'ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "{video_path}"'
    success, output = run_command(cmd)
    if success:
        try:
            width, height = map(int, output.strip().split('x'))
            return width, height
        except ValueError:
            logging.error(f"Error parsing resolution for {video_path}: {output}")
            return None, None
    return None, None

def detect_text_bottom_right(image, width, height, ocr):
    """Detect text in the bottom-right quadrant using PaddleOCR."""
    try:
        # Focus on bottom-right 25% of the image
        roi_x = width // 2
        roi_y = height // 2
        roi_w = width // 2
        roi_h = height // 2
        roi = image[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w]

        # Convert to RGB for PaddleOCR
        roi_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
        results = ocr.ocr(roi_rgb, cls=True)

        x, y, w, h = roi_x, roi_y, 0, 0
        if results and results[0]:
            for line in results[0]:
                box = line[0]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                x1 = min([p[0] for p in box]) + roi_x
                y1 = min([p[1] for p in box]) + roi_y
                x2 = max([p[0] for p in box]) + roi_x
                y2 = max([p[1] for p in box]) + roi_y
                x = min(x, x1)
                y = min(y, y1)
                w = max(w, x2 - x)
                h = max(h, y2 - y)

        if w > 0 and h > 0:
            padding = 10
            x = max(0, x - padding)
            y = max(0, y - padding)
            w = min(width - x, w + 2 * padding)
            h = min(height - y, h + 2 * padding)
            debug_print(f"Detected text at x={x}, y={y}, w={w}, h={h}")
            return x, y, w, h
        logging.warning("No text detected in bottom-right quadrant.")
        return None
    except Exception as e:
        logging.error(f"Text detection failed: {e}")
        return None

def get_watermark_position(width, height, args):
    if all([args.x is not None, args.y is not None, args.w is not None, args.h is not None]):
        return args.x, args.y, args.w, args.h
    # Predefined resolutions for fallback
    if (width, height) in [(960, 1280), (959, 1280)]:
        return 357, 1222, 586, 43
    elif (width, height) in [(592, 1280), (591, 1280)]:
        return 234, 1180, 154, 80
    elif (width, height) == (1033, 1280):
        return 409, 1180, 269, 80
    elif (width, height) in [(1280, 960), (1280, 959)]:
        return 506, 885, 333, 60
    elif (width, height) == (480, 640):
        return 190, 590, 125, 40
    elif (width, height) == (388, 360):
        return 153, 332, 101, 22
    elif (width, height) == (1160, 1214):
        return 459, 1119, 302, 76
    else:
        width_ratio = width / 960.0
        height_ratio = height / 1280.0
        x = int(357 * width_ratio)
        y = int(1222 * height_ratio)
        w = int(586 * width_ratio)
        h = int(43 * height_ratio)
        logging.warning(f"Resolution {width}x{height} not predefined. Scaling: x={x}, y={y}, w={w}, h={h}")
        return x, y, w, h

def get_next_available_name(output_dir, prefix, media_type, start_num=1):
    while True:
        output_name = f"{prefix}_{media_type}_{start_num}"
        output_path = os.path.join(output_dir, f"{output_name}.mp4" if media_type == "Vid" else f"{output_name}.png")
        if not os.path.exists(output_path):
            return output_name, start_num + 1
        start_num += 1

def remove_watermark_image(input_path, output_path, x, y, w, h, temp_dir, ocr):
    try:
        img = cv2.imread(input_path)
        if img is None:
            return False, f"Could not load image {input_path}"

        # Auto-detect text if no coordinates provided
        if x is None:
            logging.info(f"Auto-detecting text for {input_path}")
            height, width = img.shape[:2]
            coords = detect_text_bottom_right(img, width, height, ocr)
            if coords:
                x, y, w, h = coords
            else:
                logging.warning(f"No text detected in {input_path}. Using fallback coordinates.")
                x, y, w, h = get_watermark_position(width, height, args)

        # Expand mask with padding
        padding = 10
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = min(img.shape[1] - x, w + 2 * padding)
        h = min(img.shape[0] - y, h + 2 * padding)

        # Create mask
        mask = np.zeros(img.shape[:2], dtype=np.uint8)
        cv2.rectangle(mask, (x, y), (x + w, y + h), 255, -1)

        # Save temporary image and mask for LaMa
        temp_img_path = os.path.join(temp_dir, "temp_img.png")
        temp_mask_path = os.path.join(temp_dir, "temp_mask.png")
        cv2.imwrite(temp_img_path, img)
        cv2.imwrite(temp_mask_path, mask)

        # Run LaMa inpainting
        output_temp_path = os.path.join(temp_dir, "output.png")
        lama_config = "lama/configs/prediction/default.yaml"
        lama_model = "lama/models/big-lama.pt"
        lama_cmd = (
            f"python lama/bin/predict.py model.path={lama_model} "
            f"indir={temp_dir} outdir={temp_dir} dataset.img_suffix=.png "
            f"dataset.mask_suffix=.png"
        )
        success, lama_output = run_command(lama_cmd)
        if not success:
            return False, f"LaMa inpainting failed: {lama_output}"

        # Load and save inpainted image
        inpainted_img = cv2.imread(output_temp_path)
        if inpainted_img is None:
            return False, "Failed to load inpainted image"
        success = cv2.imwrite(output_path, inpainted_img)
        if success:
            debug_print(f"Saved inpainted image: {output_path}")
            return True, ""
        return False, "Failed to save inpainted image"
    except Exception as e:
        return False, str(e)

def extract_keyframe(video_path, temp_dir):
    """Extract a keyframe for text detection."""
    keyframe_path = os.path.join(temp_dir, "keyframe.jpg")
    cmd = f'ffmpeg -i "{video_path}" -vf "select=eq(pict_type\\,I)" -vframes 1 "{keyframe_path}"'
    success, _ = run_command(cmd, suppress_errors=True)
    return keyframe_path if success else None

def remove_watermark_video(input_path, output_path, x, y, w, h, crf, temp_dir, ocr):
    try:
        # Auto-detect text from a keyframe
        if x is None:
            logging.info(f"Auto-detecting text for {input_path}")
            keyframe_path = extract_keyframe(input_path, temp_dir)
            if keyframe_path:
                img = cv2.imread(keyframe_path)
                if img is None:
                    logging.error(f"Could not load keyframe for {input_path}")
                    return False, "Keyframe loading failed"
                height, width = img.shape[:2]
                coords = detect_text_bottom_right(img, width, height, ocr)
                if coords:
                    x, y, w, h = coords
                else:
                    logging.warning(f"No text detected in {input_path}. Using fallback coordinates.")
                    x, y, w, h = get_watermark_position(width, height, args)
                os.remove(keyframe_path)
            else:
                logging.error(f"Keyframe extraction failed for {input_path}")
                return False, "Keyframe extraction failed"

        filter_cmd = (
            f"delogo=x={x}:y={y}:w={w}:h={h}:show=0,"
            f"bm3d=sigma=3,unsharp=5:5:0.5:5:5:0.5"
        )
        ffmpeg_cmd = (
            f'ffmpeg -i "{input_path}" -vf "{filter_cmd}" '
            f'-c:v libx264 -preset fast -crf {crf} -c:a aac -b:a 128k "{output_path}"'
        )
        success, ffmpeg_output = run_command(ffmpeg_cmd)
        if success:
            debug_print(f"Saved processed video: {output_path}")
            return True, ""
        return False, ffmpeg_output
    except Exception as e:
        return False, str(e)

def process_file(args_tuple):
    """Process a single file (for parallel processing)."""
    args, input_path, output_dir, prefix, crf, custom_coords, temp_dir, ocr = args_tuple
    filename = os.path.basename(input_path)
    ext = Path(filename).suffix.lower()
    is_video = ext in video_extensions
    media_type = "Vid" if is_video else "Pic"

    logging.info(f"Processing {media_type.lower()}: {filename}")

    # Get resolution
    resolution = get_video_resolution(input_path) if is_video else get_image_resolution(input_path)
    if resolution is None:
        logging.error(f"Skipping {input_path} due to resolution error.")
        return

    width, height = resolution
    x, y, w, h = custom_coords if custom_coords else (None, None, None, None)

    # Get output name
    global image_num, video_num
    output_name, next_num = get_next_available_name(
        output_dir, prefix, media_type, video_num if is_video else image_num
    )
    output_path = os.path.join(output_dir, f"{output_name}.mp4" if is_video else f"{output_name}.png")
    if is_video:
        globals()['video_num'] = next_num
    else:
        globals()['image_num'] = next_num

    # Process file
    if is_video:
        success, error = remove_watermark_video(input_path, output_path, x, y, w, h, crf, temp_dir, ocr)
    else:
        success, error = remove_watermark_image(input_path, output_path, x, y, w, h, temp_dir, ocr)

    if success:
        logging.info(f"Saved {media_type} as: {output_path}")
    else:
        logging.error(f"Failed to process {filename}: {error}")

def main():
    global DEBUG, image_num, video_num, args
    image_num = 1
    video_num = 1

    parser = argparse.ArgumentParser(description="Remove watermarks from images and videos using PyTorch")
    parser.add_argument("prefix", nargs="?", default="", help="Custom prefix for output files")
    parser.add_argument("input_dir", help="Input directory containing images/videos")
    parser.add_argument("output_dir", help="Output directory for processed files")
    parser.add_argument("--crf", type=int, default=22, help="Video quality CRF (0-51, lower=better)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--x", type=int, help="Watermark x-coordinate")
    parser.add_argument("--y", type=int, help="Watermark y-coordinate")
    parser.add_argument("--w", type=int, help="Watermark width")
    parser.add_argument("--h", type=int, help="Watermark height")
    parser.add_argument("--auto", action="store_true", help="Auto-detect text in bottom-right")
    args = parser.parse_args()

    DEBUG = args.debug
    if DEBUG:
        logging.getLogger().setLevel(logging.DEBUG)

    prefix = args.prefix
    input_dir = os.path.abspath(args.input_dir)
    output_dir = os.path.abspath(args.output_dir)
    crf = args.crf
    custom_coords = (args.x, args.y, args.w, args.h) if all([args.x, args.y, args.w, args.h]) else None

    # Validate directories
    os.makedirs(output_dir, exist_ok=True)
    if not os.path.exists(input_dir):
        logging.error(f"Input directory {input_dir} does not exist.")
        sys.exit(1)

    # Check for LaMa model
    lama_model = "lama/models/big-lama.pt"
    if not os.path.exists(lama_model):
        logging.error(f"LaMa model not found at {lama_model}. Download from https://github.com/saic-mdal/lama.")
        sys.exit(1)

    # Initialize PaddleOCR
    try:
        ocr = PaddleOCR(use_angle_cls=True, lang="en")
    except Exception as e:
        logging.error(f"Failed to initialize PaddleOCR: {e}")
        sys.exit(1)

    # Supported formats
    global image_extensions, video_extensions
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif'}
    video_extensions = {'.mp4', '.mkv', '.webm', '.mov', '.avi'}

    # Collect files
    files = [f for f in os.listdir(input_dir) if Path(f).suffix.lower() in image_extensions | video_extensions]
    if not files:
        logging.error(f"No supported files found in {input_dir}.")
        sys.exit(1)

    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Prepare tasks for parallel processing
        tasks = [
            (args, os.path.join(input_dir, f), output_dir, prefix, crf, custom_coords, temp_dir, ocr)
            for f in sorted(files)
        ]

        # Process images in parallel, videos sequentially
        image_tasks = [t for t in tasks if Path(t[1]).suffix.lower() in image_extensions]
        video_tasks = [t for t in tasks if Path(t[1]).suffix.lower() in video_extensions]

        if image_tasks:
            logging.info(f"Processing {len(image_tasks)} images with {cpu_count()} workers")
            with Pool(cpu_count()) as pool:
                pool.map(process_file, image_tasks)

        for i, task in enumerate(video_tasks, 1):
            logging.info(f"Processing video {i}/{len(video_tasks)}")
            process_file(task)

if __name__ == "__main__":
    main()