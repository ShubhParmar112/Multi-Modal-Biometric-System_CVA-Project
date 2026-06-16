"""
Configuration file for Multi-Modal Biometric Authentication System.
All system-wide constants and settings are defined here.
"""

import os

# Force OpenCV to bypass buggy MSMF driver that causes black screens
os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"

# ============================================================
# PATH CONFIGURATION
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
ENCODINGS_DIR = os.path.join(BASE_DIR, "encodings")
ENCODINGS_FILE = os.path.join(ENCODINGS_DIR, "face_encodings.pkl")
DATABASE_PATH = os.path.join(BASE_DIR, "database", "users.db")
LOG_DIR = os.path.join(BASE_DIR, "logs")

# ============================================================
# FACE RECOGNITION SETTINGS
# ============================================================
# InsightFace (ArcFace) uses cosine distance on L2-normalised 512-d embeddings.
# Same-person pairs typically land below 0.40; different people above 0.65.
FACE_RECOGNITION_TOLERANCE = 0.40    # Cosine distance threshold (lower = stricter)
MIN_FACE_CONFIDENCE = 0.6            # Minimum InsightFace det_score to accept
CAMERA_INDEX = 0                     # Webcam index (0 = default)
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
FACE_FRAME_SKIP = 2                  # Process every Nth frame for performance

# ============================================================
# LIVENESS DETECTION SETTINGS
# ============================================================
LIVENESS_ENABLED = True
EYE_AR_THRESH = 0.25                  # Eye aspect ratio threshold for blink
EYE_AR_CONSEC_FRAMES = 2             # Consecutive frames for blink detection (lowered to catch fast blinks)
LIVENESS_BLINK_REQUIRED = 1          # Number of blinks required (lowered from 3 to 1 for convenience)
LIVENESS_TIMEOUT = 15                 # Seconds to wait for liveness check (increased slightly just in case)

# ============================================================
# FINGERPRINT / SERIAL SETTINGS
# ============================================================
SERIAL_PORT = "COM7"                  # Set your ESP32 port: Windows=COM7, macOS=/dev/cu.usbserial-*, Linux=/dev/ttyUSB0
SERIAL_BAUD_RATE = 115200
SERIAL_TIMEOUT = 2                    # Seconds
FINGERPRINT_TIMEOUT = 15              # Seconds to wait for fingerprint scan

# ============================================================
# SOFTWARE FINGERPRINT MATCHING (when R307S hardware is unavailable)
# Uses OpenCV ORB feature matching on fingerprint images.
# Set SOFTWARE_FINGERPRINT = True to use image-based matching
# instead of the ESP32 + R307S hardware.
# ============================================================
SOFTWARE_FINGERPRINT = False           # True = image-based, False = R307S hardware
FINGERPRINT_DATASET_DIR = os.path.join(BASE_DIR, "fingerprint_dataset")
FINGERPRINT_INBOX_DIR = os.path.join(BASE_DIR, "fingerprint_inbox")
FINGERPRINT_TEMPLATES_FILE = os.path.join(ENCODINGS_DIR, "fingerprint_templates.pkl")
FINGERPRINT_MATCH_THRESHOLD = 35     # Minimum good SIFT matches for positive ID (was 25)
FINGERPRINT_ORB_FEATURES = 3000      # Number of SIFT features to extract (was 1500)

# ============================================================
# AUTHENTICATION SETTINGS
# ============================================================
MAX_PIN_ATTEMPTS = 3
PIN_LENGTH = 4
SESSION_TIMEOUT = 30                  # Seconds before session expires
AUTH_LOG_ENABLED = True

# ============================================================
# UI SETTINGS
# ============================================================
WINDOW_TITLE = "SecureATM - Biometric Authentication"
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 750
THEME_MODE = "dark"                   # "dark" or "light"
PRIMARY_COLOR = "#00D4AA"             # Teal accent
SECONDARY_COLOR = "#1A1A2E"           # Dark background
ACCENT_COLOR = "#E94560"              # Red for errors/denied
SUCCESS_COLOR = "#00D4AA"             # Green for success
WARNING_COLOR = "#F5A623"             # Orange for warnings
TEXT_COLOR = "#EAEAEA"
CARD_COLOR = "#16213E"
FONT_FAMILY = "Segoe UI"

# ============================================================
# SIMULATION MODE (when hardware is not connected)
# ============================================================
SIMULATION_MODE = False               # Set True to simulate ESP32/fingerprint
SIMULATED_FINGERPRINT_DELAY = 2       # Seconds to simulate scan time

# ============================================================
# Create directories if they don't exist
# ============================================================
for directory in [DATASET_DIR, ENCODINGS_DIR, LOG_DIR,
                  os.path.dirname(DATABASE_PATH),
                  FINGERPRINT_DATASET_DIR]:
    os.makedirs(directory, exist_ok=True)
