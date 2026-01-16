"""Service for finding similar images using deep learning feature extraction."""
import os
from typing import List, Tuple, Optional, Dict
import numpy as np
from PIL import Image
from PyQt6.QtCore import QThread, pyqtSignal, QThreadPool, QRunnable, QObject
from concurrent.futures import ThreadPoolExecutor, as_completed

# Lazy imports for torch to avoid loading if not needed
_model = None
_transform = None

CACHE_FOLDER_NAME = ".cache"
CACHE_FILE_NAME = "feature_cache.npz"


class ImageSimilarityService:
    """Find similar images using ResNet50 feature extraction and cosine similarity."""

    def __init__(self):
        """Initialize the similarity service with lazy model loading."""
        self._ensure_model_loaded()

    def _ensure_model_loaded(self):
        """Lazy load the ResNet50 model and transform only when needed."""
        global _model, _transform

        if _model is not None:
            return

        try:
            import torch
            import torchvision.models as models
            import torchvision.transforms as transforms

            # Load pre-trained ResNet50
            _model = models.resnet50(weights='IMAGENET1K_V2')
            _model.eval()

            # Remove final classification layer to get feature vectors
            _model = torch.nn.Sequential(*list(_model.children())[:-1])

            # Standard ImageNet preprocessing
            _transform = transforms.Compose([
                transforms.Resize(256),
                transforms.CenterCrop(224),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225]
                )
            ])

        except ImportError as e:
            raise ImportError(
                "PyTorch is required for image similarity. "
                "Install with: pip install torch torchvision"
            ) from e
        except Exception as e:
            raise

    def extract_features(self, image_path: str) -> Optional[np.ndarray]:
        """
        Extract 2048-dimensional feature vector from an image.

        Args:
            image_path: Path to the image file

        Returns:
            Numpy array of shape (2048,) or None if extraction fails
        """
        if not os.path.exists(image_path):
            return None

        try:
            import torch

            # Load and preprocess image
            img = Image.open(image_path).convert('RGB')

            img_tensor = _transform(img).unsqueeze(0)

            # Extract features
            with torch.no_grad():
                features = _model(img_tensor)

            # Convert to numpy array and flatten
            feature_vector = features.squeeze().numpy()

            return feature_vector

        except Exception as e:
            import traceback
            traceback.print_exc()
            return None

    def compute_similarity(self, features1: np.ndarray, features2: np.ndarray) -> float:
        """
        Compute cosine similarity between two feature vectors.

        Args:
            features1: First feature vector
            features2: Second feature vector

        Returns:
            Similarity score between 0 and 1 (1 = most similar)
        """
        # Compute cosine similarity
        dot_product = np.dot(features1, features2)
        norm1 = np.linalg.norm(features1)
        norm2 = np.linalg.norm(features2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)

        # Normalize to 0-1 range (cosine similarity is in [-1, 1])
        normalized = (similarity + 1) / 2
        return normalized

    def find_similar_images(
        self,
        target_image,
        candidate_images: List,
        top_k: int = 20,
        min_similarity: float = 0.5
    ) -> List[Tuple[object, float]]:
        """
        Find the most similar images to a target image.

        Args:
            target_image: ImageItem to find similar images for
            candidate_images: List of ImageItem objects to search through
            top_k: Maximum number of similar images to return
            min_similarity: Minimum similarity threshold (0-1)

        Returns:
            List of (ImageItem, similarity_score) tuples, sorted by similarity (highest first)
        """
        # Get or extract target features
        target_features = self._get_cached_features(target_image)
        if target_features is None:
            return []

        similarities = []
        processed = 0
        skipped = 0
        failed = 0

        for candidate in candidate_images:
            # Skip the target image itself
            if candidate.file_path == target_image.file_path:
                skipped += 1
                continue

            # Get or extract candidate features
            candidate_features = self._get_cached_features(candidate)
            if candidate_features is None:
                failed += 1
                continue

            # Compute similarity
            similarity = self.compute_similarity(target_features, candidate_features)

            # Only include if above threshold
            if similarity >= min_similarity:
                similarities.append((candidate, similarity))

            processed += 1

        # Sort by similarity (highest first) and return top_k
        similarities.sort(key=lambda x: x[1], reverse=True)
        result = similarities[:top_k]
        return result

    def _get_cached_features(self, image_item) -> Optional[np.ndarray]:
        """
        Get feature vector from cache or extract if not cached.

        Args:
            image_item: ImageItem object

        Returns:
            Feature vector as numpy array or None
        """
        # Check if features are already cached
        if hasattr(image_item, 'feature_vector') and image_item.feature_vector is not None:
            return image_item.feature_vector

        # Extract and cache features
        features = self.extract_features(image_item.file_path)
        if features is not None:
            image_item.feature_vector = features
        else:
            pass

        return features

    def precompute_features_for_project(self, project, progress_callback=None):
        """
        Precompute and cache feature vectors for all images in a project.

        This is useful for speeding up similarity searches when the user
        wants to find similar images multiple times.

        Args:
            project: Project object containing images
            progress_callback: Optional callback function(current, total) for progress updates
        """
        total = len(project.images)

        for i, image_item in enumerate(project.images):
            # Extract features (will be cached automatically)
            self._get_cached_features(image_item)

            if progress_callback:
                progress_callback(i + 1, total)

        print(f"Precomputed features for {total} images")

    def load_images_from_directory(
        self,
        directory: str,
        supported_formats: List[str],
        progress_callback=None
    ) -> List[Dict]:
        """
        Load images from a directory (top level only, no recursion) with parallel feature extraction.

        Args:
            directory: Path to the directory containing images
            supported_formats: List of supported file extensions (e.g., ['.jpg', '.png'])
            progress_callback: Optional callback(current, total) for progress updates

        Returns:
            List of dicts with {'path': str, 'features': np.ndarray or None}
        """
        if not os.path.exists(directory):
            return []

        # Load cache
        cache = self._load_cache_from_disk(directory)

        # Collect all image paths
        image_paths = []
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)

            # Skip directories and non-files
            if not os.path.isfile(file_path):
                continue

            # Check if file has supported format
            _, ext = os.path.splitext(filename)
            if ext.lower() not in [fmt.lower() for fmt in supported_formats]:
                continue

            image_paths.append(file_path)

        if not image_paths:
            return []

        total = len(image_paths)
        images = []
        paths_needing_extraction = []

        # First pass: collect paths that need feature extraction
        for file_path in image_paths:
            features = cache.get(file_path)
            if features is None:
                paths_needing_extraction.append(file_path)
            else:
                images.append({'path': file_path, 'features': features})

        # If no extraction needed, return cached results
        if not paths_needing_extraction:
            return images

        # Parallel feature extraction for uncached images
        with ThreadPoolExecutor(max_workers=4) as executor:
            # Submit all extraction tasks
            future_to_path = {
                executor.submit(self.extract_features, path): path
                for path in paths_needing_extraction
            }

            # Process completed tasks
            completed = 0
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    features = future.result()
                    if features is not None:
                        cache[path] = features
                        images.append({'path': path, 'features': features})
                    else:
                        images.append({'path': path, 'features': None})
                except Exception as e:
                    print(f"Error extracting features for {path}: {e}")
                    images.append({'path': path, 'features': None})

                completed += 1
                if progress_callback:
                    # Report progress based on total images
                    current = len(image_paths) - len(paths_needing_extraction) + completed
                    progress_callback(current, total)

        # Save updated cache
        self._save_cache_to_disk(directory, cache)

        return images

    def _get_cache_path(self, directory: str) -> str:
        """Get the path to the cache file for a directory."""
        cache_dir = os.path.join(directory, CACHE_FOLDER_NAME)
        return os.path.join(cache_dir, CACHE_FILE_NAME)

    def _load_cache_from_disk(self, directory: str) -> Dict[str, np.ndarray]:
        """
        Load feature vector cache from disk.

        Returns:
            Dictionary mapping image_path -> feature_vector (as numpy array)
        """
        cache_path = self._get_cache_path(directory)

        if not os.path.exists(cache_path):
            return {}

        try:
            loaded = np.load(cache_path, allow_pickle=True)
            # Convert from numpy archive to regular dict
            cache = {key: loaded[key] for key in loaded.files}
            return cache
        except Exception as e:
            return {}

    def _save_cache_to_disk(self, directory: str, cache: Dict[str, np.ndarray]):
        """
        Save feature vector cache to disk.

        Args:
            directory: Directory containing the images
            cache: Dictionary mapping image_path -> feature_vector (as numpy array)
        """
        cache_dir = os.path.join(directory, CACHE_FOLDER_NAME)
        cache_path = self._get_cache_path(directory)

        try:
            # Create cache directory if it doesn't exist
            os.makedirs(cache_dir, exist_ok=True)

            # Save cache as compressed numpy archive
            np.savez_compressed(cache_path, **cache)

        except Exception as e:
            pass


class SimilaritySearchWorker(QThread):
    """Background worker for similarity search with progress updates."""

    progress_updated = pyqtSignal(int, int, str)  # current, total, message
    search_complete = pyqtSignal(list)  # list of similar images

    def __init__(
        self,
        similarity_service,
        target_image,
        comparison_directory: str,
        supported_formats: List[str],
        top_k: int = 20,
        min_similarity: float = 0.5
    ):
        super().__init__()
        self.similarity_service = similarity_service
        self.target_image = target_image
        self.comparison_directory = comparison_directory
        self.supported_formats = supported_formats
        self.top_k = top_k
        self.min_similarity = min_similarity
        self.cancelled = False

    def run(self):
        """Run similarity search in background."""
        try:
            # Load comparison images with parallel feature extraction
            def on_progress(current, total):
                if not self.cancelled:
                    self.progress_updated.emit(current, total, f"Processing image {current}/{total}")

            self.progress_updated.emit(0, 0, "Loading comparison images...")

            comparison_images = self.similarity_service.load_images_from_directory(
                self.comparison_directory,
                self.supported_formats,
                progress_callback=on_progress
            )

            if self.cancelled:
                self.search_complete.emit([])
                return

            # Convert to ImageItem-like objects for find_similar_images
            from ..models.image_item import ImageItem

            candidate_items = []
            for img_dict in comparison_images:
                if img_dict['features'] is not None:
                    item = ImageItem(img_dict['path'])
                    item.feature_vector = img_dict['features']
                    candidate_items.append(item)

            self.progress_updated.emit(0, 0, "Finding similar images...")

            # Find similar images
            results = self.similarity_service.find_similar_images(
                self.target_image,
                candidate_items,
                top_k=self.top_k,
                min_similarity=self.min_similarity
            )

            self.search_complete.emit(results)

        except Exception as e:
            print(f"Error in similarity search: {e}")
            import traceback
            traceback.print_exc()
            self.search_complete.emit([])

    def cancel(self):
        """Cancel the search operation."""
        self.cancelled = True
