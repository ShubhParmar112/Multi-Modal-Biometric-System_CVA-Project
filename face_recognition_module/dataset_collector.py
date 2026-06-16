"""
Dataset Collector - Captures face images from webcam for training.
Guides the user through capturing multiple angles and expressions
for robust face recognition training.
"""

import os
import cv2
import time
from typing import Optional

import config
from utils.logger import logger


class DatasetCollector:
    """
    Captures face images from a webcam and saves them in the dataset
    directory organized by user_id for later encoding.
    """

    INSTRUCTIONS = [
        "Look straight at the camera",
        "Turn your head slightly LEFT",
        "Turn your head slightly RIGHT",
        "Tilt your head UP slightly",
        "Tilt your head DOWN slightly",
        "Smile naturally",
        "Keep a neutral expression",
        "Move slightly CLOSER to camera",
        "Move slightly FARTHER from camera",
        "Turn head LEFT more",
    ]

    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

    def collect_faces(self, user_id: str, name: str,
                      num_images: int = 40) -> Optional[str]:
        """
        Capture face images from webcam for a specific user.

        Args:
            user_id: Unique user identifier
            name: User's display name
            num_images: Number of images to capture (default 20)

        Returns:
            Path to the user's image directory, or None on failure
        """
        # Create user directory
        user_dir = os.path.join(config.DATASET_DIR, user_id)
        os.makedirs(user_dir, exist_ok=True)

        cap = cv2.VideoCapture(config.CAMERA_INDEX)
        if not cap.isOpened():
            logger.error("Cannot open webcam for dataset collection")
            return None

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)

        logger.info(f"Starting dataset collection for {name} ({user_id})")
        logger.info(f"Capturing {num_images} images. Press 'SPACE' to capture, 'Q' to quit.")

        count = 0
        while count < num_images:
            ret, frame = cap.read()
            if not ret:
                logger.error("Failed to read from webcam")
                break

            # Detect faces for visual feedback
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80)
            )

            display = frame.copy()

            # Draw face rectangles
            for (x, y, w, h) in faces:
                cv2.rectangle(display, (x, y), (x + w, y + h),
                              (0, 212, 170), 2)

            # Display instruction
            instruction_idx = min(count, len(self.INSTRUCTIONS) - 1)
            instruction = self.INSTRUCTIONS[instruction_idx]

            # Header bar
            cv2.rectangle(display, (0, 0), (display.shape[1], 50),
                          (26, 26, 46), -1)
            cv2.putText(display, f"Collecting: {name} | {count}/{num_images}",
                        (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 212, 170), 1)
            cv2.putText(display, f"Instruction: {instruction}",
                        (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (234, 234, 234), 1)

            # Footer
            cv2.rectangle(display, (0, display.shape[0] - 30),
                          (display.shape[1], display.shape[0]),
                          (26, 26, 46), -1)
            cv2.putText(display, "SPACE: Capture | Q: Quit",
                        (10, display.shape[0] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

            cv2.imshow("Dataset Collection", display)

            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                logger.info("Collection cancelled by user")
                break
            elif key == ord(' '):
                if len(faces) == 1:
                    # Save the FULL frame natively - InsightFace needs context to detect the face properly!
                    filename = f"{user_id}_{count:03d}.jpg"
                    filepath = os.path.join(user_dir, filename)
                    cv2.imwrite(filepath, frame)

                    count += 1
                    logger.info(f"Captured image {count}/{num_images}")
                elif len(faces) == 0:
                    logger.warning("No face detected. Adjust your position.")
                else:
                    logger.warning("Multiple faces detected. Ensure only one face is visible.")

        cap.release()
        cv2.destroyAllWindows()

        if count > 0:
            logger.success(f"Collected {count} images for {name} → {user_dir}")
            return user_dir
        else:
            logger.warning("No images collected")
            return None

    def collect_auto(self, user_id: str, name: str,
                     num_images: int = 20, delay: float = 0.5) -> Optional[str]:
        """
        Auto-capture face images at regular intervals (no manual trigger).

        Args:
            user_id: Unique user identifier
            name: User's display name
            num_images: Number of images to capture
            delay: Delay between captures in seconds

        Returns:
            Path to the user's image directory, or None on failure
        """
        user_dir = os.path.join(config.DATASET_DIR, user_id)
        os.makedirs(user_dir, exist_ok=True)

        cap = cv2.VideoCapture(config.CAMERA_INDEX)
        if not cap.isOpened():
            logger.error("Cannot open webcam")
            return None

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)

        logger.info(f"Auto-capturing {num_images} images for {name}")
        logger.info("Follow the on-screen instructions. Press Q to abort.")

        count = 0
        last_capture = 0

        while count < num_images:
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80)
            )

            display = frame.copy()

            for (x, y, w, h) in faces:
                cv2.rectangle(display, (x, y), (x + w, y + h),
                              (0, 212, 170), 2)

            # Instruction
            instruction_idx = min(count, len(self.INSTRUCTIONS) - 1)
            cv2.rectangle(display, (0, 0), (display.shape[1], 50),
                          (26, 26, 46), -1)
            cv2.putText(display, f"Auto-Capture: {name} | {count}/{num_images}",
                        (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 212, 170), 1)
            cv2.putText(display, f"Do: {self.INSTRUCTIONS[instruction_idx]}",
                        (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (234, 234, 234), 1)

            cv2.imshow("Auto Dataset Collection", display)

            # Auto capture with delay
            current_time = time.time()
            if (len(faces) == 1 and
                    current_time - last_capture >= delay):
                
                # Save full frame instead of cropping so InsightFace can detect it
                filepath = os.path.join(user_dir, f"{user_id}_{count:03d}.jpg")
                cv2.imwrite(filepath, frame)
                count += 1
                last_capture = current_time
                logger.info(f"Auto-captured {count}/{num_images}")

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

        if count > 0:
            logger.success(f"Auto-collected {count} images → {user_dir}")
            return user_dir
        return None
