"""
Face Recognizer - Real-time face detection and identification.
Uses InsightFace (ArcFace / buffalo_l) with cosine distance matching.
Returns user_id, confidence score, and face location.
"""

import cv2
import numpy as np
import pickle
import time
from typing import Optional, Tuple, Dict, List

import config
from utils.logger import logger


class FaceRecognizer:
    """
    Real-time face recognizer that identifies registered users
    from a webcam feed using 512-d ArcFace embeddings and cosine distance.
    """

    def __init__(self):
        self.known_encodings: List[np.ndarray] = []
        self.known_ids: List[str] = []
        self.is_loaded = False
        self.frame_count = 0
        self._app = None

    def _get_app(self):
        if self._app is None:
            from insightface.app import FaceAnalysis
            self._app = FaceAnalysis(
                name='buffalo_l',
                providers=['CPUExecutionProvider']
            )
            self._app.prepare(ctx_id=0, det_size=(640, 640))
        return self._app

    def load_encodings(self) -> bool:
        """Load pre-computed face encodings from disk."""
        if not config.ENCODINGS_FILE:
            logger.error("Encodings file path not configured")
            return False

        try:
            with open(config.ENCODINGS_FILE, "rb") as f:
                data = pickle.load(f)

            self.known_encodings = data["encodings"]
            self.known_ids = data["ids"]
            self.is_loaded = True

            unique_users = set(self.known_ids)
            logger.success(
                f"Face recognizer loaded: {len(self.known_encodings)} embeddings "
                f"for {len(unique_users)} users"
            )
            return True
        except FileNotFoundError:
            logger.error(
                f"Encodings file not found: {config.ENCODINGS_FILE}. "
                "Please run the encoder first."
            )
            return False
        except Exception as e:
            logger.error(f"Failed to load encodings: {e}")
            return False

    @staticmethod
    def _cosine_distances(known: List[np.ndarray],
                          probe: np.ndarray) -> np.ndarray:
        """
        Cosine distance between probe and every known embedding.
        Embeddings are L2-normalised so dot product = cosine similarity.
        distance = 1 - similarity  (range 0..2, lower = more similar)
        """
        known_arr = np.array(known)           # (N, 512)
        sims = known_arr @ probe              # (N,)
        return 1.0 - sims

    def recognize_from_frame(self, frame: np.ndarray) -> Tuple[
            Optional[str], float, Optional[Tuple[int, int, int, int]]]:
        """
        Identify a face in a single frame.

        Args:
            frame: BGR image from OpenCV

        Returns:
            Tuple of (user_id or None, confidence 0-1, face_location or None)
            face_location is (top, right, bottom, left) to match original API
        """
        if not self.is_loaded:
            logger.error("Encodings not loaded. Call load_encodings() first.")
            return None, 0.0, None

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        app = self._get_app()
        faces = app.get(rgb)

        if not faces:
            return None, 0.0, None

        # Filter by detection confidence
        faces = [f for f in faces
                 if f.det_score >= config.MIN_FACE_CONFIDENCE]
        if not faces:
            return None, 0.0, None

        # Use the largest face if multiple detected
        face = max(faces,
                   key=lambda f: (f.bbox[2] - f.bbox[0]) *
                                 (f.bbox[3] - f.bbox[1]))

        probe = face.embedding  # 512-d, L2-normalised

        # InsightFace bbox: [x1, y1, x2, y2] → (top, right, bottom, left)
        x1, y1, x2, y2 = face.bbox.astype(int)
        face_loc = (y1, x2, y2, x1)

        if len(self.known_encodings) == 0:
            return None, 0.0, face_loc

        distances = self._cosine_distances(self.known_encodings, probe)
        best_idx = int(np.argmin(distances))
        best_distance = float(distances[best_idx])
        confidence = round(1.0 - best_distance, 4)

        if best_distance <= config.FACE_RECOGNITION_TOLERANCE:
            user_id = self.known_ids[best_idx]

            # Voting: count how many stored embeddings of each user match
            matches = distances <= config.FACE_RECOGNITION_TOLERANCE
            match_counts: Dict[str, int] = {}
            for match, uid in zip(matches, self.known_ids):
                if match:
                    match_counts[uid] = match_counts.get(uid, 0) + 1

            if match_counts:
                voted_id = max(match_counts, key=match_counts.get)
                vote_confidence = (match_counts[voted_id] /
                                   sum(match_counts.values()))
                final_confidence = round(
                    confidence * 0.6 + vote_confidence * 0.4, 4
                )

                if final_confidence < config.MIN_FACE_CONFIDENCE:
                    return None, final_confidence, face_loc

                return voted_id, final_confidence, face_loc

            return user_id, confidence, face_loc
        else:
            return None, confidence, face_loc

    def recognize_with_timeout(self, timeout: int = 10,
                               required_confirmations: int = 5) -> Tuple[
            Optional[str], float]:
        """
        Run real-time recognition with webcam until a user is confirmed
        or timeout is reached.

        Args:
            timeout: Maximum seconds to attempt recognition
            required_confirmations: Number of consecutive matches needed

        Returns:
            Tuple of (user_id or None, average confidence)
        """
        cap = cv2.VideoCapture(config.CAMERA_INDEX)
        if not cap.isOpened():
            logger.error("Cannot open webcam for recognition")
            return None, 0.0

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)

        logger.info(f"Starting face recognition (timeout: {timeout}s)")

        start_time = time.time()
        confirmations: Dict[str, List[float]] = {}
        recognized_user = None
        avg_confidence = 0.0

        while time.time() - start_time < timeout:
            ret, frame = cap.read()
            if not ret:
                continue

            self.frame_count += 1

            if self.frame_count % config.FACE_FRAME_SKIP != 0:
                cv2.imshow("Face Recognition", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                continue

            user_id, confidence, face_loc = self.recognize_from_frame(frame)
            display = frame.copy()

            if face_loc:
                top, right, bottom, left = face_loc
                if user_id:
                    cv2.rectangle(display, (left, top), (right, bottom),
                                  (0, 212, 170), 2)
                    label = f"{user_id} ({confidence:.1%})"
                    cv2.putText(display, label, (left, top - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                                (0, 212, 170), 2)

                    if user_id not in confirmations:
                        confirmations[user_id] = []
                    confirmations[user_id].append(confidence)

                    if len(confirmations[user_id]) >= required_confirmations:
                        recognized_user = user_id
                        avg_confidence = float(
                            np.mean(confirmations[user_id])
                        )
                        break
                else:
                    cv2.rectangle(display, (left, top), (right, bottom),
                                  (0, 0, 233), 2)
                    cv2.putText(display, f"Unknown ({confidence:.1%})",
                                (left, top - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                                (0, 0, 233), 2)

            elapsed = time.time() - start_time
            remaining = max(0, timeout - elapsed)
            cv2.rectangle(display, (0, 0), (display.shape[1], 35),
                          (26, 26, 46), -1)
            cv2.putText(display,
                        f"Scanning... Time remaining: {remaining:.0f}s",
                        (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 212, 170), 1)

            cv2.imshow("Face Recognition", display)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

        if recognized_user:
            logger.success(
                f"Face recognized: {recognized_user} "
                f"(confidence: {avg_confidence:.1%})"
            )
        else:
            logger.warning("Face recognition timed out or no match found")

        return recognized_user, float(avg_confidence)

    def get_frame_with_recognition(self, frame: np.ndarray) -> Tuple[
            np.ndarray, Optional[str], float]:
        """
        Process a frame and return the annotated frame along with
        recognition results. Used by the UI for live camera feed.

        Returns:
            Tuple of (annotated_frame, user_id or None, confidence)
        """
        self.frame_count += 1
        display = frame.copy()

        if self.frame_count % config.FACE_FRAME_SKIP != 0:
            return display, None, 0.0

        user_id, confidence, face_loc = self.recognize_from_frame(frame)

        if face_loc:
            top, right, bottom, left = face_loc
            if user_id:
                color = (0, 212, 170)
                label = f"{user_id} ({confidence:.1%})"
            else:
                color = (0, 0, 233)
                label = f"Unknown ({confidence:.1%})"

            cv2.rectangle(display, (left, top), (right, bottom), color, 2)

            label_size = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
            cv2.rectangle(
                display,
                (left, top - label_size[1] - 10),
                (left + label_size[0] + 5, top),
                color, -1
            )
            cv2.putText(display, label, (left + 2, top - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        return display, user_id, confidence
