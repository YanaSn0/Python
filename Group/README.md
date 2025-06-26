Purpose: Groups images by visual similarity using KMeans clustering and MobileNetV2 for feature extraction.

Command:

python group.py ./images 3

First Argument: Folder containing images.

Second Argument: Number of clusters.

Example Output: Images copied to ./output/cluster_1, ./output/cluster_2, etc.

Flags:

--output-dir <path>: Output directory for clustered images (default: ./images/grouped).

--debug: Enable verbose debug output.

Example:

python group.py ./images 3 --output-dir ./output

Groups images in ./images into 3 clusters, saving to ./output/cluster_1, etc.

