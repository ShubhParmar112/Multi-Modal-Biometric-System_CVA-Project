"""
Face Encoder - Generates 512-dimensional ArcFace embeddings using InsightFace.
Processes the dataset directory and creates a serialized encoding file
for fast recognition at runtime.
"""

import os
import pickle
import cv2
import numpy as np
from typing import Dict, List, Optional

import config
from utils.logger import logger


class FaceEncoder:
    """
    Encodes face images from the dataset directory into 512-d ArcFace vectors
    via InsightFace (buffalo_l model). Saves encodings to disk for efficient
    loading during recognition.
    """

    def __init__(self):
        self.known_encodings: Dict[str, List[np.ndarray]] = {}
        self.known_names: Dict[str, str] = {}
        self._app = None

    def _get_app(self):
        if self._app is None:
            from insightface.app import FaceAnalysis
            self._app = FaceAnalysis(
                name='buffalo_l',
                providers=['CPUExecutionProvider']
            )
            self._app.prepare(ctx_id=0, det_size=(640, 640))
            logger.info("InsightFace buffalo_l model loaded")
        return self._app

    def encode_dataset(self) -> bool:
        """
        Process all images in the dataset directory and generate 512-d embeddings.

        Expected directory structure:
            dataset/
              USR001/
                USR001_000.jpg
                ...
              USR002/
                ...

        Returns:
            True if encodings were generated successfully
        """
        if not os.path.exists(config.DATASET_DIR):
            logger.error(f"Dataset directory not found: {config.DATASET_DIR}")
            return False

        user_dirs = [d for d in os.listdir(config.DATASET_DIR)
                     if os.path.isdir(os.path.join(config.DATASET_DIR, d))]

        if not user_dirs:
            logger.error("No user directories found in dataset")
            return False

        app = self._get_app()
        all_encodings = []
        all_ids = []
        total_images = 0
        failed_images = 0

        for user_id in user_dirs:
            user_path = os.path.join(config.DATASET_DIR, user_id)
            images = [f for f in os.listdir(user_path)
                      if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]

            if not images:
                logger.warning(f"No images found for user {user_id}")
                continue

            logger.info(f"Encoding {len(images)} images for user: {user_id}")
            user_encodings = []

            for img_name in images:
                img_path = os.path.join(user_path, img_name)
                try:
                    image = cv2.imread(img_path)
                    if image is None:
                        logger.warning(f"Cannot read image: {img_name}")
                        failed_images += 1
                        continue

                    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                    faces = app.get(rgb)

                    if len(faces) == 0:
                        logger.warning(f"No face found in {img_name}")
                        failed_images += 1
                        continue

                    if len(faces) > 1:
                        logger.warning(
                            f"Multiple faces in {img_name}, using largest"
                        )
                        faces = [max(
                            faces,
                            key=lambda f: (
                                (f.bbox[2] - f.bbox[0]) *
                                (f.bbox[3] - f.bbox[1])
                            )
                        )]

                    # 512-d L2-normalised ArcFace embedding
                    embedding = faces[0].normed_embedding
                    user_encodings.append(embedding)
                    all_encodings.append(embedding)
                    all_ids.append(user_id)
                    total_images += 1

                except Exception as e:
                    logger.error(f"Error processing {img_path}: {e}")
                    failed_images += 1

            if user_encodings:
                self.known_encodings[user_id] = user_encodings
                logger.success(
                    f"User {user_id}: {len(user_encodings)} embeddings generated"
                )

        if not all_encodings:
            logger.error("No valid encodings generated from dataset")
            return False

        encoding_data = {
            "encodings": all_encodings,
            "ids": all_ids,
            "user_encodings": self.known_encodings,
        }

        os.makedirs(config.ENCODINGS_DIR, exist_ok=True)
        with open(config.ENCODINGS_FILE, "wb") as f:
            pickle.dump(encoding_data, f)

        logger.success(
            f"Encodings saved: {total_images} faces from "
            f"{len(self.known_encodings)} users "
            f"({failed_images} failed) → {config.ENCODINGS_FILE}"
        )
        return True

    def load_encodings(self) -> bool:
        """Load pre-computed encodings from disk."""
        if not os.path.exists(config.ENCODINGS_FILE):
            logger.error(
                f"Encodings file not found: {config.ENCODINGS_FILE}. "
                "Run encode_dataset() first."
            )
            return False

        try:
            with open(config.ENCODINGS_FILE, "rb") as f:
                data = pickle.load(f)

            self.known_encodings = data.get("user_encodings", {})
            logger.success(
                f"Loaded encodings for {len(self.known_encodings)} users"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to load encodings: {e}")
            return False

    def get_average_encoding(self, user_id: str) -> Optional[np.ndarray]:
        """
        Get the average embedding for a user (used for DB storage).
        Re-normalises after averaging so the vector stays unit-length.
        """
        if user_id in self.known_encodings:
            encodings = self.known_encodings[user_id]
            avg = np.mean(encodings, axis=0)
            norm = np.linalg.norm(avg)
            return avg / norm if norm > 0 else avg
        return None

    def add_encoding(self, user_id: str, encoding: np.ndarray):
        """Add a single embedding for a user (for live enrollment)."""
        if user_id not in self.known_encodings:
            self.known_encodings[user_id] = []
        self.known_encodings[user_id].append(encoding)
