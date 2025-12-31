"""Service for finding similar images using deep learning feature extraction."""
import os
import json
from typing import List, Tuple, Optional, Dict
import numpy as np
from PIL import Image

# Lazy imports for torch to avoid loading if not needed
_model = None
_transform = None

CACHE_FOLDER_NAME = ".cache"
CACHE_FILE_NAME = "feature_cache.json"


class ImageSimilarityService:
    """Find similar images using ResNet50 feature extraction and cosine similarity."""

    def __init__(self):
        """Initialize the similarity service with lazy model loading."""
        self._ensure_model_loaded()

    def _ensure_model_loaded(self):
        """Lazy load the ResNet50 model and transform only when needed."""
        global _model, _transform

        if _model is not None:
            print("[DEBUG] Model already loaded, skipping initialization")
            return

        try:
            print("[DEBUG] Attempting to import PyTorch...")
            import torch
            import torchvision.models as models
            import torchvision.transforms as transforms

            print("[DEBUG] PyTorch imported successfully")
            print(f"[DEBUG] PyTorch version: {torch.__version__}")
            print("[DEBUG] Loading ResNet50 model for image similarity...")

            # Load pre-trained ResNet50
            _model = models.resnet50(weights='IMAGENET1K_V2')
            _model.eval()
            print("[DEBUG] ResNet50 base model loaded")

            # Remove final classification layer to get feature vectors
            _model = torch.nn.Sequential(*list(_model.children())[:-1])
            print("[DEBUG] Final classification layer removed")

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
            print("[DEBUG] Image transforms configured")

            print("[DEBUG] ResNet50 model loaded successfully!")

        except ImportError as e:
            print(f"[DEBUG] ImportError: {e}")
            raise ImportError(
                "PyTorch is required for image similarity. "
                "Install with: pip install torch torchvision"
            ) from e
        except Exception as e:
            print(f"[DEBUG] Unexpected error loading model: {e}")
            raise

    def extract_features(self, image_path: str) -> Optional[np.ndarray]:
        """
        Extract 2048-dimensional feature vector from an image.

        Args:
            image_path: Path to the image file

        Returns:
            Numpy array of shape (2048,) or None if extraction fails
        """
        print(f"[DEBUG] Extracting features from: {image_path}")

        if not os.path.exists(image_path):
            print(f"[DEBUG] ERROR: Image not found: {image_path}")
            return None

        try:
            import torch

            # Load and preprocess image
            print(f"[DEBUG] Loading image...")
            img = Image.open(image_path).convert('RGB')
            print(f"[DEBUG] Image loaded, size: {img.size}, mode: {img.mode}")

            img_tensor = _transform(img).unsqueeze(0)
            print(f"[DEBUG] Image transformed to tensor, shape: {img_tensor.shape}")

            # Extract features
            with torch.no_grad():
                features = _model(img_tensor)

            # Convert to numpy array and flatten
            feature_vector = features.squeeze().numpy()
            print(f"[DEBUG] Features extracted, shape: {feature_vector.shape}")

            return feature_vector

        except Exception as e:
            print(f"[DEBUG] ERROR extracting features from {image_path}: {e}")
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
            print("[DEBUG] WARNING: Zero norm detected in feature vectors")
            return 0.0

        similarity = dot_product / (norm1 * norm2)

        # Normalize to 0-1 range (cosine similarity is in [-1, 1])
        normalized = (similarity + 1) / 2
        print(f"[DEBUG] Similarity computed: {normalized:.4f} (raw: {similarity:.4f})")
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
        print(f"[DEBUG] ========== Finding Similar Images ==========")
        print(f"[DEBUG] Target image: {target_image.file_path}")
        print(f"[DEBUG] Candidate count: {len(candidate_images)}")
        print(f"[DEBUG] Top K: {top_k}, Min similarity: {min_similarity}")

        # Get or extract target features
        target_features = self._get_cached_features(target_image)
        if target_features is None:
            print(f"[DEBUG] ERROR: Failed to extract features from target image: {target_image.file_path}")
            return []

        print(f"[DEBUG] Target features extracted successfully")

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
                print(f"[DEBUG] Match found: {candidate.file_path} (similarity: {similarity:.4f})")

            processed += 1

        print(f"[DEBUG] Processing complete:")
        print(f"[DEBUG]   - Processed: {processed}")
        print(f"[DEBUG]   - Skipped (target): {skipped}")
        print(f"[DEBUG]   - Failed: {failed}")
        print(f"[DEBUG]   - Matches above threshold: {len(similarities)}")

        # Sort by similarity (highest first) and return top_k
        similarities.sort(key=lambda x: x[1], reverse=True)
        result = similarities[:top_k]
        print(f"[DEBUG] Returning top {len(result)} results")
        print(f"[DEBUG] ========================================")
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
            print(f"[DEBUG] Using cached features for: {image_item.file_path}")
            return image_item.feature_vector

        # Extract and cache features
        print(f"[DEBUG] No cached features, extracting for: {image_item.file_path}")
        features = self.extract_features(image_item.file_path)
        if features is not None:
            image_item.feature_vector = features
            print(f"[DEBUG] Features cached successfully")
        else:
            print(f"[DEBUG] Failed to extract and cache features")

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

    def load_images_from_directory(self, directory: str, supported_formats: List[str]) -> List[Dict]:
        """
        Load images from a directory (top level only, no recursion).

        Args:
            directory: Path to the directory containing images
            supported_formats: List of supported file extensions (e.g., ['.jpg', '.png'])

        Returns:
            List of dicts with {'path': str, 'features': np.ndarray or None}
        """
        print(f"[DEBUG] Loading images from comparison directory: {directory}")

        if not os.path.exists(directory):
            print(f"[DEBUG] Comparison directory does not exist: {directory}")
            return []

        # Load cache
        cache = self._load_cache_from_disk(directory)

        images = []
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)

            # Skip directories and non-files
            if not os.path.isfile(file_path):
                continue

            # Check if file has supported format
            _, ext = os.path.splitext(filename)
            if ext.lower() not in [fmt.lower() for fmt in supported_formats]:
                continue

            # Get features from cache or extract
            features = cache.get(file_path)
            if features is not None:
                features = np.array(features)
                print(f"[DEBUG] Loaded cached features for: {file_path}")
            else:
                print(f"[DEBUG] Extracting features for: {file_path}")
                features = self.extract_features(file_path)
                if features is not None:
                    # Update cache
                    cache[file_path] = features.tolist()

            images.append({
                'path': file_path,
                'features': features
            })

        # Save updated cache
        if images:
            self._save_cache_to_disk(directory, cache)

        print(f"[DEBUG] Loaded {len(images)} images from comparison directory")
        return images

    def _get_cache_path(self, directory: str) -> str:
        """Get the path to the cache file for a directory."""
        cache_dir = os.path.join(directory, CACHE_FOLDER_NAME)
        return os.path.join(cache_dir, CACHE_FILE_NAME)

    def _load_cache_from_disk(self, directory: str) -> Dict[str, List]:
        """
        Load feature vector cache from disk.

        Returns:
            Dictionary mapping image_path -> feature_vector (as list)
        """
        cache_path = self._get_cache_path(directory)

        if not os.path.exists(cache_path):
            print(f"[DEBUG] No cache file found at: {cache_path}")
            return {}

        try:
            with open(cache_path, 'r') as f:
                cache = json.load(f)
            print(f"[DEBUG] Loaded cache from: {cache_path} ({len(cache)} entries)")
            return cache
        except Exception as e:
            print(f"[DEBUG] Error loading cache from {cache_path}: {e}")
            return {}

    def _save_cache_to_disk(self, directory: str, cache: Dict[str, List]):
        """
        Save feature vector cache to disk.

        Args:
            directory: Directory containing the images
            cache: Dictionary mapping image_path -> feature_vector (as list)
        """
        cache_dir = os.path.join(directory, CACHE_FOLDER_NAME)
        cache_path = self._get_cache_path(directory)

        try:
            # Create cache directory if it doesn't exist
            os.makedirs(cache_dir, exist_ok=True)

            # Save cache
            with open(cache_path, 'w') as f:
                json.dump(cache, f, indent=2)

            print(f"[DEBUG] Saved cache to: {cache_path} ({len(cache)} entries)")
        except Exception as e:
            print(f"[DEBUG] Error saving cache to {cache_path}: {e}")
