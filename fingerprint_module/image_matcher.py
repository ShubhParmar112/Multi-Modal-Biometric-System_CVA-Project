"""
Software-based Fingerprint Matcher using OpenCV SIFT features.
Replaces the hardware R307S sensor when ESP32 is unavailable.

Uses SIFT (Scale-Invariant Feature Transform) for minutiae-like
feature extraction and FLANN-based KD-tree matching with Lowe's ratio test.
SIFT produces float32 descriptors that are more discriminative than
ORB's binary descriptors for fingerprint ridge patterns.
Includes CLAHE preprocessing for ridge contrast enhancement.
"""

import os
import cv2
import numpy as np
import pickle
from typing import Optional, Tuple, List, Dict, Any

import config
from utils.logger import logger


class FingerprintImageMatcher:
    """
    Software fingerprint matcher using SIFT feature detection
    and FLANN-based KD-tree matching.

    Replaces R307S hardware scanner for demo/testing environments.

    Pipeline:
        1. Preprocess (grayscale, resize, CLAHE, blur)
        2. SIFT feature extraction (keypoints + float32 descriptors)
        3. FLANN KD-tree matcher with kNN + Lowe's ratio test
        4. Score-based threshold decision
    """

    # FLANN parameters for SIFT (KD-tree, float32 descriptors)
    _FLANN_INDEX_KDTREE = 1
    _FLANN_INDEX_PARAMS = dict(algorithm=1, trees=5)
    _FLANN_SEARCH_PARAMS = dict(checks=50)

    def __init__(self):
        self.sift = cv2.SIFT_create(nfeatures=config.FINGERPRINT_ORB_FEATURES)
        self.flann = cv2.FlannBasedMatcher(
            self._FLANN_INDEX_PARAMS, self._FLANN_SEARCH_PARAMS
        )
        self.templates: Dict[int, Dict[str, Any]] = {}
        self.is_loaded = False
        self._next_id = 1

    # ═══════════════════════════════════════════════════════════
    # IMAGE PREPROCESSING
    # ═══════════════════════════════════════════════════════════

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """
        Enhance fingerprint image for robust feature extraction.

        Pipeline:
            1. Grayscale conversion
            2. Resize to standard 300×400 dimensions
            3. CLAHE (Contrast Limited Adaptive Histogram Equalization)
               for ridge contrast enhancement
            4. Gaussian blur for noise reduction

        Args:
            image: BGR or grayscale image

        Returns:
            Preprocessed grayscale image
        """
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Resize to standard dimensions for consistent feature counts
        gray = cv2.resize(gray, (300, 400))

        # CLAHE for ridge contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Gaussian blur for noise reduction
        enhanced = cv2.GaussianBlur(enhanced, (5, 5), 1.0)

        return enhanced

    # ═══════════════════════════════════════════════════════════
    # FEATURE EXTRACTION
    # ═══════════════════════════════════════════════════════════

    def extract_features(self, image: np.ndarray) -> Tuple[
            Optional[list], Optional[np.ndarray]]:
        """
        Extract SIFT keypoints and descriptors from a fingerprint image.

        Args:
            image: Raw fingerprint image (BGR or grayscale)

        Returns:
            Tuple of (keypoints, descriptors) or (None, None)
        """
        processed = self.preprocess(image)
        keypoints, descriptors = self.sift.detectAndCompute(processed, None)

        if descriptors is None or len(keypoints) < 10:
            logger.warning(
                f"Too few features extracted: "
                f"{len(keypoints) if keypoints else 0} keypoints"
            )
            return None, None

        # FLANN requires float32
        descriptors = descriptors.astype(np.float32)
        logger.info(f"Extracted {len(keypoints)} SIFT features from fingerprint")
        return keypoints, descriptors

    # ═══════════════════════════════════════════════════════════
    # ENROLLMENT
    # ═══════════════════════════════════════════════════════════

    def enroll(self, user_id: str, image_paths: List[str]) -> Optional[int]:
        """
        Enroll fingerprint(s) for a user by extracting and storing
        ORB feature templates.

        Processes multiple images and stores all descriptor sets for
        improved matching robustness. The best matching set will be
        used during authentication.

        Args:
            user_id: User identifier (e.g., "USR001")
            image_paths: List of fingerprint image file paths

        Returns:
            Assigned fingerprint_id (int), or None on failure
        """
        if not image_paths:
            logger.error("No fingerprint images provided for enrollment")
            return None

        all_descriptors = []

        for path in image_paths:
            img = cv2.imread(path)
            if img is None:
                logger.warning(f"Cannot read fingerprint image: {path}")
                continue

            kps, descs = self.extract_features(img)
            if descs is not None:
                all_descriptors.append(descs)
                logger.info(
                    f"Enrolled image: {os.path.basename(path)} "
                    f"({len(kps)} features)"
                )

        if not all_descriptors:
            logger.error("No valid features extracted from any image")
            return None

        # Assign fingerprint ID
        fp_id = self._next_id

        # Store template
        self.templates[fp_id] = {
            'user_id': user_id,
            'descriptor_sets': all_descriptors,
            'image_count': len(all_descriptors)
        }

        self._next_id += 1
        self.save_templates()

        logger.success(
            f"Fingerprint enrolled: ID {fp_id} for {user_id} "
            f"({len(all_descriptors)} images, "
            f"{sum(len(d) for d in all_descriptors)} total features)"
        )
        return fp_id

    # ═══════════════════════════════════════════════════════════
    # MATCHING
    # ═══════════════════════════════════════════════════════════

    def match(self, image_path: str,
              threshold: int = None) -> Tuple[Optional[int], bool, float]:
        """
        Match a fingerprint image against all stored templates.

        Uses ORB feature matching with Lowe's ratio test to find
        the best matching template above the confidence threshold.

        Args:
            image_path: Path to the probe fingerprint image
            threshold: Minimum good matches for positive ID
                       (default from config)

        Returns:
            Tuple of (fingerprint_id or None, is_match, confidence 0-1)
        """
        threshold = threshold or config.FINGERPRINT_MATCH_THRESHOLD

        img = cv2.imread(image_path)
        if img is None:
            logger.error(f"Cannot read fingerprint image: {image_path}")
            return None, False, 0.0

        probe_kps, probe_descs = self.extract_features(img)
        if probe_descs is None:
            logger.warning("No features extracted from probe image")
            return None, False, 0.0

        best_fp_id = None
        best_score = 0

        for fp_id, template in self.templates.items():
            template_best_score = 0

            for descriptors in template['descriptor_sets']:
                try:
                    # kNN matching with k=2 for Lowe's ratio test
                    matches = self.flann.knnMatch(
                        probe_descs, descriptors.astype(np.float32), k=2
                    )

                    # Lowe's ratio test — keep only distinctive matches
                    good_matches = []
                    for match_pair in matches:
                        if len(match_pair) == 2:
                            m, n = match_pair
                            if m.distance < 0.75 * n.distance:
                                good_matches.append(m)

                    score = len(good_matches)

                    if score > template_best_score:
                        template_best_score = score

                except cv2.error as e:
                    logger.warning(f"Match error for template {fp_id}: {e}")
                    continue

            if template_best_score > best_score:
                best_score = template_best_score
                best_fp_id = fp_id

        # Calculate confidence as ratio of score to threshold
        confidence = min(best_score / max(threshold * 2, 1), 1.0)

        if best_score >= threshold:
            user_id = self.templates[best_fp_id]['user_id']
            logger.success(
                f"Fingerprint matched: ID {best_fp_id} (user: {user_id}, "
                f"good_matches: {best_score}, confidence: {confidence:.1%})"
            )
            return best_fp_id, True, confidence
        else:
            logger.warning(
                f"No fingerprint match (best score: {best_score}, "
                f"threshold: {threshold})"
            )
            return None, False, confidence

    def match_and_visualize(self, image_path: str,
                            threshold: int = None) -> Tuple[
            Optional[int], bool, float, Optional[np.ndarray]]:
        """
        Match a fingerprint and generate a visualization of the
        keypoints extracted from the probe image.

        Useful for demo presentations to show the feature extraction.

        Returns:
            Tuple of (fp_id, is_match, confidence, visualization_image)
        """
        fp_id, is_match, confidence = self.match(image_path, threshold)

        # Generate visualization
        img = cv2.imread(image_path)
        if img is not None:
            processed = self.preprocess(img)
            kps, _ = self.sift.detectAndCompute(processed, None)
            vis = cv2.drawKeypoints(
                processed, kps, None,
                color=(0, 212, 170),
                flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS
            )
            return fp_id, is_match, confidence, vis

        return fp_id, is_match, confidence, None

    # ═══════════════════════════════════════════════════════════
    # PERSISTENCE
    # ═══════════════════════════════════════════════════════════

    def save_templates(self):
        """Persist fingerprint templates to disk."""
        os.makedirs(config.ENCODINGS_DIR, exist_ok=True)
        data = {
            'templates': self.templates,
            'next_id': self._next_id
        }
        with open(config.FINGERPRINT_TEMPLATES_FILE, 'wb') as f:
            pickle.dump(data, f)
        logger.info(
            f"Fingerprint templates saved: {len(self.templates)} templates "
            f"→ {config.FINGERPRINT_TEMPLATES_FILE}"
        )

    def load_templates(self) -> bool:
        """Load fingerprint templates from disk."""
        if not os.path.exists(config.FINGERPRINT_TEMPLATES_FILE):
            logger.warning("No fingerprint templates file found")
            return False

        try:
            with open(config.FINGERPRINT_TEMPLATES_FILE, 'rb') as f:
                data = pickle.load(f)

            self.templates = data['templates']
            self._next_id = data['next_id']
            self.is_loaded = True

            logger.success(
                f"Loaded {len(self.templates)} fingerprint templates"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to load fingerprint templates: {e}")
            return False
