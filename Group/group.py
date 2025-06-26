import os
import argparse
import shutil
from sklearn.cluster import KMeans
import tensorflow as tf
import numpy as np
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
from tensorflow.keras.preprocessing.image import img_to_array, load_img

DEBUG = False

def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)

def extract_features(image_path, target_size=(224, 224)):
    try:
        image = load_img(image_path, target_size=target_size)
        image_array = img_to_array(image)
        image_array = np.expand_dims(image_array, axis=0)
        image_array = preprocess_input(image_array)
        model = MobileNetV2(weights='imagenet', include_top=False, pooling='avg')
        features = model.predict(image_array)
        return features.flatten()
    except Exception as e:
        print(f"Feature extraction error for {image_path}: {e}")
        return None

def main():
    global DEBUG
    parser = argparse.ArgumentParser(description="Group images by similarity")
    parser.add_argument("folder_path", help="Folder containing images")
    parser.add_argument("num_clusters", type=int, help="Number of clusters")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()
    DEBUG = args.debug

    folder_path = args.folder_path
    num_clusters = args.num_clusters
    output_dir = args.output_dir or os.path.join(os.path.abspath(folder_path), "grouped")
    debug_print(f"Input dir: {folder_path}, Clusters: {num_clusters}, Output dir: {output_dir}")
    actual_folder = os.path.abspath(folder_path)
    debug_print(f"Scanning directory: {actual_folder}")
    if not os.path.isdir(actual_folder):
        print(f"Error: Directory does not exist: {actual_folder}")
        sys.exit(1)
    debug_print(f"Listing directory contents")
    image_extensions = ['.jpg', '.jpeg', '.png', '.webp']
    image_files = [
        os.path.join(actual_folder, f) for f in os.listdir(actual_folder)
        if os.path.isfile(os.path.join(actual_folder, f)) and os.path.splitext(f.lower())[1] in image_extensions
    ]
    debug_print(f"Image files: {image_files}")
    if not image_files:
        print(f"No images found in {actual_folder}")
        sys.exit(1)
    if num_clusters < 1:
        print("Error: Number of clusters must be at least 1")
        sys.exit(1)
    if num_clusters > len(image_files):
        print(f"Warning: Number of clusters {num_clusters} exceeds number of images {len(image_files)}. Setting to {len(image_files)}")
        num_clusters = len(image_files)
    debug_print("Extracting features")
    features_list = []
    valid_files = []
    for file in image_files:
        debug_print(f"Processing: {file}")
        features = extract_features(file)
        if features is not None:
            features_list.append(features)
            valid_files.append(file)
    if not features_list:
        print("Error: No valid features extracted from images")
        sys.exit(1)
    debug_print(f"Extracted features for {len(valid_files)} images")
    kmeans = KMeans(n_clusters=num_clusters, random_state=0)
    labels = kmeans.fit_predict(features_list)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    for cluster_id in range(num_clusters):
        cluster_dir = os.path.join(output_dir, f"cluster_{cluster_id + 1}")
        if not os.path.exists(cluster_dir):
            os.makedirs(cluster_dir)
    for file, label in zip(valid_files, labels):
        cluster_dir = os.path.join(output_dir, f"cluster_{label + 1}")
        dest_path = os.path.join(cluster_dir, os.path.basename(file))
        shutil.copy2(file, dest_path)
        debug_print(f"Copied {file} to {dest_path}")
    print(f"Images grouped into {num_clusters} clusters in {output_dir}")

if __name__ == "__main__":
    main()
