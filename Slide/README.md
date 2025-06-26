Purpose: Creates a slideshow video from images, with each image displayed for a specified duration.

Command:

python slide.py 5 ./images image1.jpg image2.jpg

First Argument: Duration per image in seconds.

Second Argument: Folder containing images.

Remaining Arguments: Image names or range (e.g., img1-img3 for img1.jpg, img2.jpg, img3.jpg).

Example Output: S1_1.mp4, S2_2.mp4, etc., in the output directory.

Flags:

--output-dir <path>: Output directory (default: input folder).

--keep-original-resolution: Use original image resolution instead of a standard resolution.

--debug: Enable verbose debug output.

Example:

python slide.py 5 ./images img1-img3 --output-dir ./output

Creates slideshow videos from img1.jpg, img2.jpg, img3.jpg, each 5 seconds, saving as ./output/S1_1.mp4, etc.

