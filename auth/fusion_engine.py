"""
Fusion Engine - Multi-modal biometric authentication orchestrator.
Coordinates Face Recognition → Fingerprint → PIN verification pipeline.
Implements decision fusion with confidence scoring and audit logging.
"""

import time
from typing import Optional, Tuple, Dict, Any
from enum import Enum

import config
from utils.logger import logger
from database.db_manager import DatabaseManager
from face_recognition_module.face_recognizer import FaceRecognizer
from face_recognition_module.liveness_detector import LivenessDetector
from fingerprint_module.serial_handler import SerialHandler


class AuthStage(Enum):
    """Authentication pipeline stages."""
    IDLE = "idle"
    FACE_SCAN = "face_scan"
    LIVENESS_CHECK = "liveness_check"
    FINGERPRINT_SCAN = "fingerprint_scan"
    IDENTITY_FUSION = "identity_fusion"
    PIN_ENTRY = "pin_entry"
    GRANTED = "access_granted"
    DENIED = "access_denied"
    ERROR = "error"


class AuthResult:
    """Container for authentication attempt results."""

    def __init__(self):
        self.stage = AuthStage.IDLE
        self.face_id: Optional[str] = None
        self.face_confidence: float = 0.0
        self.fingerprint_id: Optional[int] = None
        self.fingerprint_match: bool = False
        self.identity_match: bool = False
        self.pin_verified: bool = False
        self.final_decision: bool = False
        self.user_name: Optional[str] = None
        self.error_message: Optional[str] = None
        self.timestamp: float = time.time()
        self.duration: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage.value,
            "face_id": self.face_id,
            "face_confidence": self.face_confidence,
            "fingerprint_id": self.fingerprint_id,
            "fingerprint_match": self.fingerprint_match,
            "identity_match": self.identity_match,
            "pin_verified": self.pin_verified,
            "final_decision": self.final_decision,
            "user_name": self.user_name,
            "error_message": self.error_message,
            "duration": round(self.duration, 2)
        }


class FusionEngine:
    """
    Orchestrates the multi-modal biometric authentication pipeline.

    Pipeline:  Face Detection → Liveness Check → Fingerprint Scan
               → Identity Fusion → PIN Verification → Decision

    Each stage must pass before proceeding to the next.
    """

    def __init__(self):
        self.db = DatabaseManager()
        self.face_recognizer = FaceRecognizer()
        self.liveness_detector = LivenessDetector()
        self.serial_handler = SerialHandler()
        self.fingerprint_matcher = None  # Initialized if SOFTWARE_FINGERPRINT
        self.current_result = AuthResult()
        self._stage_callbacks = {}

    def initialize(self) -> bool:
        """
        Initialize all subsystems.

        Returns:
            True if all components initialized successfully
        """
        logger.system_event("Fusion Engine", "Initializing subsystems...")
        success = True

        # Load face encodings
        if not self.face_recognizer.load_encodings():
            logger.warning(
                "Face encodings not loaded. "
                "Run enrollment first or check encodings file."
            )
            success = False

        # Initialize fingerprint subsystem
        if config.SOFTWARE_FINGERPRINT:
            from fingerprint_module.image_matcher import FingerprintImageMatcher
            self.fingerprint_matcher = FingerprintImageMatcher()
            if self.fingerprint_matcher.load_templates():
                logger.success("Software fingerprint matcher ready")
            else:
                logger.warning(
                    "No fingerprint templates loaded. "
                    "Run enrollment first."
                )
        elif not config.SIMULATION_MODE:
            if not self.serial_handler.connect():
                logger.warning(
                    "ESP32 not connected. Fingerprint auth unavailable."
                )
                success = False
        else:
            self.serial_handler.connect()
            logger.info("Running in SIMULATION MODE")

        logger.system_event("Fusion Engine", "Initialization complete")
        return success

    def set_stage_callback(self, callback):
        """
        Set a callback function that gets called when the auth stage changes.
        Used by the UI to update the display.

        Args:
            callback: Function(stage: AuthStage, result: AuthResult)
        """
        self._stage_callback = callback

    def _update_stage(self, stage: AuthStage):
        """Update the current authentication stage and notify UI."""
        self.current_result.stage = stage
        logger.info(f"Auth stage → {stage.value}")
        if hasattr(self, '_stage_callback') and self._stage_callback:
            self._stage_callback(stage, self.current_result)

    def authenticate(self, pin_callback=None) -> AuthResult:
        """
        Run the full authentication pipeline.

        Args:
            pin_callback: Function that returns user-entered PIN string.
                          If None, PIN is skipped (for testing).

        Returns:
            AuthResult with the outcome of the authentication attempt
        """
        self.current_result = AuthResult()
        start_time = time.time()

        try:
            # ─── STAGE 1: Face Recognition ───────────────────
            self._update_stage(AuthStage.FACE_SCAN)
            face_id, face_confidence = self.face_recognizer.recognize_with_timeout(
                timeout=15, required_confirmations=5
            )

            self.current_result.face_id = face_id
            self.current_result.face_confidence = face_confidence

            if not face_id:
                self.current_result.error_message = (
                    "Face not recognized. Access denied."
                )
                self._update_stage(AuthStage.DENIED)
                self.db.log_auth_event(
                    "UNKNOWN", "face_recognition", "failure",
                    f"confidence={face_confidence:.3f}"
                )
                return self._finalize(start_time)

            logger.success(
                f"Face identified: {face_id} (confidence: {face_confidence:.1%})"
            )
            self.db.log_auth_event(
                face_id, "face_recognition", "success",
                f"confidence={face_confidence:.3f}"
            )

            # Get user info from database
            user = self.db.get_user(face_id)
            if user:
                self.current_result.user_name = user["name"]

            # ─── STAGE 2: Liveness Check (if enabled) ────────
            if config.LIVENESS_ENABLED:
                self._update_stage(AuthStage.LIVENESS_CHECK)
                self.liveness_detector.reset()
                passed, blink_count = self.liveness_detector.check_liveness()

                if not passed:
                    self.current_result.error_message = (
                        "Liveness check failed. Possible spoofing detected."
                    )
                    self._update_stage(AuthStage.DENIED)
                    self.db.log_auth_event(
                        face_id, "liveness_check", "failure",
                        f"blinks={blink_count}"
                    )
                    return self._finalize(start_time)

                self.db.log_auth_event(
                    face_id, "liveness_check", "success",
                    f"blinks={blink_count}"
                )

            # ─── STAGE 3: Fingerprint Scan ───────────────────
            self._update_stage(AuthStage.FINGERPRINT_SCAN)
            logger.info("Place your finger on the sensor...")

            fp_id, fp_match = self.serial_handler.request_fingerprint_scan(
                timeout=config.FINGERPRINT_TIMEOUT,
                expected_user_id=face_id
            )

            self.current_result.fingerprint_id = fp_id
            self.current_result.fingerprint_match = fp_match

            if not fp_match or fp_id is None:
                self.current_result.error_message = (
                    "Fingerprint not recognized. Access denied."
                )
                self._update_stage(AuthStage.DENIED)
                self.db.log_auth_event(
                    face_id, "fingerprint", "failure"
                )
                return self._finalize(start_time)

            self.db.log_auth_event(
                face_id, "fingerprint", "success",
                f"fingerprint_id={fp_id}"
            )

            # ─── STAGE 4: Identity Fusion ────────────────────
            self._update_stage(AuthStage.IDENTITY_FUSION)
            identity_match = self._fuse_identities(face_id, fp_id)
            self.current_result.identity_match = identity_match

            if not identity_match:
                self.current_result.error_message = (
                    f"Identity mismatch: Face ID '{face_id}' does not match "
                    f"Fingerprint ID '{fp_id}'. Access denied."
                )
                self._update_stage(AuthStage.DENIED)
                self.db.log_auth_event(
                    face_id, "identity_fusion", "mismatch",
                    f"face={face_id}, fp={fp_id}"
                )
                return self._finalize(start_time)

            logger.success("Identity fusion: MATCH confirmed")
            self.db.log_auth_event(
                face_id, "identity_fusion", "success"
            )

            # ─── STAGE 5: PIN Entry ─────────────────────────
            self._update_stage(AuthStage.PIN_ENTRY)

            if pin_callback:
                pin_attempts = 0
                while pin_attempts < config.MAX_PIN_ATTEMPTS:
                    pin = pin_callback()
                    if pin is None:
                        # User cancelled
                        self.current_result.error_message = "PIN entry cancelled."
                        self._update_stage(AuthStage.DENIED)
                        return self._finalize(start_time)

                    if self.db.verify_pin(face_id, pin):
                        self.current_result.pin_verified = True
                        break
                    else:
                        pin_attempts += 1
                        remaining = config.MAX_PIN_ATTEMPTS - pin_attempts
                        logger.warning(
                            f"Wrong PIN. {remaining} attempts remaining."
                        )
                        self.db.log_auth_event(
                            face_id, "pin_entry", "failure",
                            f"attempt={pin_attempts}"
                        )

                if not self.current_result.pin_verified:
                    self.current_result.error_message = (
                        f"Maximum PIN attempts ({config.MAX_PIN_ATTEMPTS}) exceeded."
                    )
                    self._update_stage(AuthStage.DENIED)
                    self.db.log_auth_event(
                        face_id, "pin_entry", "locked_out"
                    )
                    return self._finalize(start_time)
            else:
                # No PIN callback provided (testing mode)
                self.current_result.pin_verified = True

            self.db.log_auth_event(face_id, "pin_entry", "success")

            # ─── STAGE 6: Access Granted ─────────────────────
            self.current_result.final_decision = True
            self._update_stage(AuthStage.GRANTED)
            self.db.update_last_login(face_id)
            self.db.log_auth_event(face_id, "session", "granted")
            logger.success(
                f"ACCESS GRANTED for {self.current_result.user_name or face_id}"
            )

        except Exception as e:
            self.current_result.error_message = f"System error: {str(e)}"
            self.current_result.stage = AuthStage.ERROR
            logger.error(f"Authentication error: {e}")
            self.db.log_auth_event("SYSTEM", "error", "failure", str(e))

        return self._finalize(start_time)

    def _fuse_identities(self, face_id: str, fingerprint_id: int) -> bool:
        """
        Verify that the face-recognized user matches the fingerprint user.

        Decision rule:
            The user record retrieved by face_id must have the same
            fingerprint_id as returned by the ESP32.

        Args:
            face_id: User ID from face recognition
            fingerprint_id: Fingerprint ID from ESP32

        Returns:
            True if both biometrics point to the same user
        """
        user = self.db.get_user(face_id)
        if user is None:
            logger.error(f"User {face_id} not found in database")
            return False

        stored_fp_id = user.get("fingerprint_id")
        if stored_fp_id is None:
            logger.error(f"No fingerprint ID stored for user {face_id}")
            return False

        match = (stored_fp_id == fingerprint_id)
        logger.info(
            f"Identity fusion: face={face_id}, "
            f"stored_fp={stored_fp_id}, scanned_fp={fingerprint_id} "
            f"→ {'MATCH' if match else 'MISMATCH'}"
        )
        return match

    def _finalize(self, start_time: float) -> AuthResult:
        """Finalize the authentication result with timing data."""
        self.current_result.duration = time.time() - start_time
        return self.current_result

    def shutdown(self):
        """Cleanly shut down all subsystems."""
        logger.system_event("Fusion Engine", "Shutting down...")
        self.serial_handler.disconnect()
        logger.system_event("Fusion Engine", "Shutdown complete")
