"""
Liveness Detection Module - Anti-spoofing via blink detection.
Uses MediaPipe Face Landmarker Tasks API (mediapipe >= 0.10.x).
Falls back to legacy solutions API for older mediapipe versions.

Eye Aspect Ratio (EAR) indices from the 478-landmark model:
  Left eye:  [362, 385, 387, 263, 373, 380]
  Right eye: [33,  160, 158, 133, 153, 144]
"""

import os
import cv2
import numpy as np
import time
from typing import Tuple

import config
from utils.logger import logger

_LEFT_EYE_EAR  = [362, 385, 387, 263, 373, 380]
_RIGHT_EYE_EAR = [33,  160, 158, 133, 153, 144]

_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
)
_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models", "face_landmarker.task"
)


def _download_model():
    """Download the FaceLandmarker model if not already present."""
    if os.path.exists(_MODEL_PATH):
        return
    os.makedirs(os.path.dirname(_MODEL_PATH), exist_ok=True)
    logger.info("Downloading MediaPipe face_landmarker model (~29MB)...")
    import urllib.request
    urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
    logger.success("face_landmarker model downloaded")


class LivenessDetector:
    """
    Anti-spoofing detector using MediaPipe Face Landmarker Eye Aspect Ratio.
    A real person must blink LIVENESS_BLINK_REQUIRED times to pass.
    """

    def __init__(self):
        self.blink_count   = 0
        self.ear_history   = []
        self.is_eye_closed = False
        self._detector     = None  # FaceLandmarker (Tasks API)

    # ─────────────────────────────────────────────────────────────
    # Detector initialisation
    # ─────────────────────────────────────────────────────────────

    def _get_detector(self):
        """Lazy-init the MediaPipe FaceLandmarker (Tasks API)."""
        if self._detector is None:
            _download_model()
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision as mp_vision

            options = mp_vision.FaceLandmarkerOptions(
                base_options=mp_python.BaseOptions(
                    model_asset_path=_MODEL_PATH
                ),
                num_faces=1,
                min_face_detection_confidence=0.5,
                min_face_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self._detector = mp_vision.FaceLandmarker.create_from_options(options)
        return self._detector

    # ─────────────────────────────────────────────────────────────
    # EAR helpers
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _eye_aspect_ratio(eye_points: np.ndarray) -> float:
        """EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)"""
        v1 = np.linalg.norm(eye_points[1] - eye_points[5])
        v2 = np.linalg.norm(eye_points[2] - eye_points[4])
        h  = np.linalg.norm(eye_points[0] - eye_points[3])
        return (v1 + v2) / (2.0 * h) if h > 0 else 0.0

    def _get_ear_from_frame(self, rgb_frame: np.ndarray) -> Tuple[
            float, np.ndarray, np.ndarray]:
        """
        Run the FaceLandmarker on one RGB frame.
        Returns (EAR, left_eye_pts, right_eye_pts) in pixel coordinates,
        or (0.0, empty, empty) when no face is detected.
        """
        import mediapipe as mp

        detector = self._get_detector()
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        result   = detector.detect(mp_image)

        if not result.face_landmarks:
            return 0.0, np.array([]), np.array([])

        lm   = result.face_landmarks[0]
        h, w = rgb_frame.shape[:2]

        left_pts  = np.array([(lm[i].x * w, lm[i].y * h) for i in _LEFT_EYE_EAR])
        right_pts = np.array([(lm[i].x * w, lm[i].y * h) for i in _RIGHT_EYE_EAR])

        ear = (self._eye_aspect_ratio(left_pts) +
               self._eye_aspect_ratio(right_pts)) / 2.0
        return ear, left_pts, right_pts

    # ─────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────

    def check_liveness(self, timeout: int = None,
                       required_blinks: int = None) -> Tuple[bool, int]:
        """
        Run liveness detection via webcam. User must blink naturally.

        Returns:
            Tuple of (passed: bool, blink_count: int)
        """
        timeout         = timeout         or config.LIVENESS_TIMEOUT
        required_blinks = required_blinks or config.LIVENESS_BLINK_REQUIRED

        cap = cv2.VideoCapture(config.CAMERA_INDEX)
        if not cap.isOpened():
            logger.error("Cannot open webcam for liveness detection")
            return False, 0

        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  config.CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)

        self.blink_count   = 0
        self.is_eye_closed = False
        consec_closed      = 0
        start_time         = time.time()

        logger.info(f"Liveness check started. Please blink {required_blinks} times.")

        while time.time() - start_time < timeout:
            ret, frame = cap.read()
            if not ret:
                continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            ear, left_pts, right_pts = self._get_ear_from_frame(rgb)
            display = frame.copy()

            if left_pts.size > 0:
                cv2.polylines(display, [left_pts.astype(np.int32)],
                              True, (0, 212, 170), 1)
                cv2.polylines(display, [right_pts.astype(np.int32)],
                              True, (0, 212, 170), 1)

                if ear < config.EYE_AR_THRESH:
                    consec_closed += 1
                else:
                    if consec_closed >= config.EYE_AR_CONSEC_FRAMES:
                        self.blink_count += 1
                        logger.info(
                            f"Blink detected! ({self.blink_count}/{required_blinks})")
                    consec_closed = 0

                cv2.putText(display, f"EAR: {ear:.3f}",
                            (display.shape[1] - 150, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 212, 170), 1)
            else:
                cv2.putText(display, "No face detected",
                            (10, display.shape[0] - 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 233), 2)

            elapsed   = time.time() - start_time
            remaining = max(0, timeout - elapsed)

            cv2.rectangle(display, (0, 0), (display.shape[1], 50), (26, 26, 46), -1)
            cv2.putText(display,
                        f"LIVENESS CHECK | Blinks: "
                        f"{self.blink_count}/{required_blinks} "
                        f"| Time: {remaining:.0f}s",
                        (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 212, 170), 1)
            cv2.putText(display, "Please blink naturally",
                        (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

            progress  = self.blink_count / required_blinks
            bar_width = int(display.shape[1] * 0.6)
            bar_x     = int(display.shape[1] * 0.2)
            bar_y     = display.shape[0] - 20
            cv2.rectangle(display, (bar_x, bar_y),
                          (bar_x + bar_width, bar_y + 10), (50, 50, 80), -1)
            cv2.rectangle(display, (bar_x, bar_y),
                          (bar_x + int(bar_width * min(progress, 1.0)), bar_y + 10),
                          (0, 212, 170), -1)

            cv2.imshow("Liveness Detection", display)

            if self.blink_count >= required_blinks:
                logger.success("Liveness check PASSED")
                time.sleep(0.5)
                break

            if cv2.waitKey(1) & 0xFF == ord('q'):
                logger.warning("Liveness check cancelled by user")
                break

        cap.release()
        cv2.destroyAllWindows()

        passed = self.blink_count >= required_blinks
        if not passed:
            logger.warning(
                f"Liveness check FAILED: {self.blink_count}/{required_blinks} blinks")
        return passed, self.blink_count

    def check_frame_liveness(self, frame: np.ndarray) -> Tuple[
            float, bool, np.ndarray]:
        """
        Check liveness on a single frame (used by the UI live feed).

        Returns:
            Tuple of (ear_value, blink_detected, annotated_frame)
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        ear, left_pts, right_pts = self._get_ear_from_frame(rgb)
        display = frame.copy()

        if left_pts.size > 0:
            cv2.polylines(display, [left_pts.astype(np.int32)],
                          True, (0, 212, 170), 1)
            cv2.polylines(display, [right_pts.astype(np.int32)],
                          True, (0, 212, 170), 1)
            return ear, ear < config.EYE_AR_THRESH, display

        return 0.0, False, display

    def reset(self):
        """Reset blink counter for a new liveness check."""
        self.blink_count   = 0
        self.is_eye_closed = False
        self.ear_history   = []
