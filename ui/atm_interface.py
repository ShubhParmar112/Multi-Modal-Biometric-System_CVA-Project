"""
ATM Interface - Premium dark-themed Tkinter GUI for biometric authentication.
Shows camera feed, authentication steps, PIN entry, and final result.
Uses CustomTkinter for modern, polished UI components.
"""

import os
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
import cv2
import threading
import time
import numpy as np
from PIL import Image, ImageTk
from typing import Optional, Callable

import config
from utils.logger import logger
from auth.fusion_engine import FusionEngine, AuthStage, AuthResult
from face_recognition_module.face_recognizer import FaceRecognizer
from face_recognition_module.liveness_detector import LivenessDetector
from database.db_manager import DatabaseManager


class ATMInterface:
    """
    Premium ATM simulation UI with live camera feed, step-by-step
    authentication progress, PIN entry, and result display.
    """

    def __init__(self):
        # ── Theme Setup ──────────────────────────────────────
        ctk.set_appearance_mode(config.THEME_MODE)
        ctk.set_default_color_theme("dark-blue")

        # ── Main Window ──────────────────────────────────────
        self.root = ctk.CTk()
        self.root.title(config.WINDOW_TITLE)
        self.root.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")
        self.root.resizable(False, False)
        self.root.configure(fg_color=config.SECONDARY_COLOR)

        # ── State Variables ──────────────────────────────────
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running = False
        self.auth_active = False
        self.current_stage = AuthStage.IDLE
        self.face_recognizer = FaceRecognizer()
        self.liveness_detector = LivenessDetector()
        self.fusion_engine = FusionEngine()
        self.db = DatabaseManager()
        self.pin_value = ""
        self.pin_callback_result = None
        self.pin_event = threading.Event()

        # Fingerprint dialog state (software mode)
        self.fp_image_path = None
        self.fp_event = threading.Event()

        # Stage display data
        self.stages_info = {
            AuthStage.IDLE: ("⏳", "Ready", "Insert card or begin authentication"),
            AuthStage.FACE_SCAN: ("👤", "Face Scan", "Look at the camera..."),
            AuthStage.LIVENESS_CHECK: ("👁️", "Liveness Check", "Please blink naturally"),
            AuthStage.FINGERPRINT_SCAN: ("🔐", "Fingerprint", "Place finger on sensor"),
            AuthStage.IDENTITY_FUSION: ("🔄", "Verifying", "Cross-checking identities..."),
            AuthStage.PIN_ENTRY: ("🔢", "PIN Entry", "Enter your 4-digit PIN"),
            AuthStage.GRANTED: ("✅", "Granted", "Authentication successful!"),
            AuthStage.DENIED: ("❌", "Denied", "Authentication failed"),
            AuthStage.ERROR: ("⚠️", "Error", "System error occurred"),
        }

        # ── Build UI ─────────────────────────────────────────
        self._build_header()
        self._build_main_content()
        self._build_footer()

        # ── Protocol for window close ────────────────────────
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ═══════════════════════════════════════════════════════════
    # UI CONSTRUCTION
    # ═══════════════════════════════════════════════════════════

    def _build_header(self):
        """Build the top header bar with branding."""
        header = ctk.CTkFrame(
            self.root, height=60, fg_color="#0D1B2A",
            corner_radius=0
        )
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)

        # Bank logo / title
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", padx=20, pady=10)

        ctk.CTkLabel(
            title_frame, text="🏦",
            font=ctk.CTkFont(size=28)
        ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            title_frame, text="SecureATM",
            font=ctk.CTkFont(family=config.FONT_FAMILY, size=22, weight="bold"),
            text_color=config.PRIMARY_COLOR
        ).pack(side="left")

        ctk.CTkLabel(
            title_frame, text="Biometric Authentication System",
            font=ctk.CTkFont(family=config.FONT_FAMILY, size=12),
            text_color="#7B8794"
        ).pack(side="left", padx=(12, 0))

        # Status indicator (right side)
        self.status_frame = ctk.CTkFrame(header, fg_color="transparent")
        self.status_frame.pack(side="right", padx=20, pady=10)

        self.status_dot = ctk.CTkLabel(
            self.status_frame, text="●",
            font=ctk.CTkFont(size=14), text_color=config.SUCCESS_COLOR
        )
        self.status_dot.pack(side="left", padx=(0, 5))

        self.status_label = ctk.CTkLabel(
            self.status_frame, text="System Ready",
            font=ctk.CTkFont(family=config.FONT_FAMILY, size=12),
            text_color=config.TEXT_COLOR
        )
        self.status_label.pack(side="left")

    def _build_main_content(self):
        """Build the main content area: camera + auth panel."""
        main = ctk.CTkFrame(
            self.root, fg_color=config.SECONDARY_COLOR,
            corner_radius=0
        )
        main.pack(fill="both", expand=True, padx=15, pady=10)

        # ── Left Panel: Camera Feed ──────────────────────
        left_panel = ctk.CTkFrame(
            main, fg_color=config.CARD_COLOR,
            corner_radius=12, border_width=1,
            border_color="#2A3A5C"
        )
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 8))

        camera_header = ctk.CTkFrame(left_panel, fg_color="transparent")
        camera_header.pack(fill="x", padx=15, pady=(12, 5))

        ctk.CTkLabel(
            camera_header, text="📷 Live Camera Feed",
            font=ctk.CTkFont(family=config.FONT_FAMILY, size=14, weight="bold"),
            text_color=config.TEXT_COLOR
        ).pack(side="left")

        self.camera_status_label = ctk.CTkLabel(
            camera_header, text="● Active",
            font=ctk.CTkFont(size=11),
            text_color=config.SUCCESS_COLOR
        )
        self.camera_status_label.pack(side="right")

        # Camera display canvas
        self.camera_label = ctk.CTkLabel(
            left_panel, text="Camera initializing...",
            font=ctk.CTkFont(size=14),
            text_color="#7B8794",
            fg_color="#0A0F1A",
            corner_radius=8,
            width=580, height=420
        )
        self.camera_label.pack(padx=15, pady=(5, 10))

        # Confidence bar
        conf_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        conf_frame.pack(fill="x", padx=15, pady=(0, 12))

        ctk.CTkLabel(
            conf_frame, text="Confidence:",
            font=ctk.CTkFont(family=config.FONT_FAMILY, size=11),
            text_color="#7B8794"
        ).pack(side="left")

        self.confidence_bar = ctk.CTkProgressBar(
            conf_frame, width=200, height=8,
            progress_color=config.PRIMARY_COLOR,
            fg_color="#0A0F1A"
        )
        self.confidence_bar.pack(side="left", padx=8)
        self.confidence_bar.set(0)

        self.confidence_label = ctk.CTkLabel(
            conf_frame, text="0%",
            font=ctk.CTkFont(family=config.FONT_FAMILY, size=11, weight="bold"),
            text_color=config.PRIMARY_COLOR
        )
        self.confidence_label.pack(side="left")

        # ── Right Panel: Auth Steps + Controls ──────────
        right_panel = ctk.CTkFrame(
            main, width=350, fg_color=config.CARD_COLOR,
            corner_radius=12, border_width=1,
            border_color="#2A3A5C"
        )
        right_panel.pack(side="right", fill="both", padx=(8, 0))
        right_panel.pack_propagate(False)

        # Auth steps header
        ctk.CTkLabel(
            right_panel, text="🔐 Authentication Pipeline",
            font=ctk.CTkFont(family=config.FONT_FAMILY, size=14, weight="bold"),
            text_color=config.TEXT_COLOR
        ).pack(padx=15, pady=(15, 8))

        # Separator
        ctk.CTkFrame(
            right_panel, height=1, fg_color="#2A3A5C"
        ).pack(fill="x", padx=15, pady=5)

        # Pipeline steps
        self.step_cards = {}
        steps = [
            ("face", "1", "Face Recognition", "Identify user via webcam"),
            ("liveness", "2", "Liveness Detection", "Anti-spoofing check"),
            ("fingerprint", "3", "Fingerprint Scan",
             "Verify via image scan" if config.SOFTWARE_FINGERPRINT else "Verify via R307S sensor"),
            ("fusion", "4", "Identity Fusion", "Cross-match biometrics"),
            ("pin", "5", "PIN Verification", "Enter 4-digit PIN code"),
        ]

        for key, num, title, desc in steps:
            card = self._create_step_card(right_panel, num, title, desc)
            self.step_cards[key] = card

        # Separator
        ctk.CTkFrame(
            right_panel, height=1, fg_color="#2A3A5C"
        ).pack(fill="x", padx=15, pady=8)

        # Result display
        self.result_frame = ctk.CTkFrame(
            right_panel, fg_color="#0A0F1A",
            corner_radius=8, height=60
        )
        self.result_frame.pack(fill="x", padx=15, pady=5)
        self.result_frame.pack_propagate(False)

        self.result_icon = ctk.CTkLabel(
            self.result_frame, text="⏳",
            font=ctk.CTkFont(size=24)
        )
        self.result_icon.pack(side="left", padx=15)

        result_text_frame = ctk.CTkFrame(
            self.result_frame, fg_color="transparent"
        )
        result_text_frame.pack(side="left", fill="both", expand=True)

        self.result_title = ctk.CTkLabel(
            result_text_frame, text="Awaiting Authentication",
            font=ctk.CTkFont(family=config.FONT_FAMILY, size=13, weight="bold"),
            text_color=config.TEXT_COLOR, anchor="w"
        )
        self.result_title.pack(fill="x", pady=(10, 0))

        self.result_detail = ctk.CTkLabel(
            result_text_frame, text="Press 'Start' to begin",
            font=ctk.CTkFont(family=config.FONT_FAMILY, size=10),
            text_color="#7B8794", anchor="w"
        )
        self.result_detail.pack(fill="x")

        # ── Buttons ──────────────────────────────────────
        btn_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(8, 12), side="bottom")

        self.start_btn = ctk.CTkButton(
            btn_frame, text="▶  Start Authentication",
            font=ctk.CTkFont(family=config.FONT_FAMILY, size=13, weight="bold"),
            fg_color=config.PRIMARY_COLOR, text_color="#0D1B2A",
            hover_color="#00B894", height=40, corner_radius=8,
            command=self._start_auth
        )
        self.start_btn.pack(fill="x", pady=(0, 6))

        self.reset_btn = ctk.CTkButton(
            btn_frame, text="↻  Reset",
            font=ctk.CTkFont(family=config.FONT_FAMILY, size=12),
            fg_color="#2A3A5C", text_color=config.TEXT_COLOR,
            hover_color="#3A4A6C", height=35, corner_radius=8,
            command=self._reset
        )
        self.reset_btn.pack(fill="x")

    def _create_step_card(self, parent, number: str, title: str,
                          description: str) -> dict:
        """Create a pipeline step card with status indicator."""
        frame = ctk.CTkFrame(
            parent, fg_color="#0D1B2A", corner_radius=6, height=42
        )
        frame.pack(fill="x", padx=15, pady=3)
        frame.pack_propagate(False)

        # Step number circle
        num_label = ctk.CTkLabel(
            frame, text=number,
            font=ctk.CTkFont(family=config.FONT_FAMILY, size=11, weight="bold"),
            text_color="#0D1B2A", fg_color="#3A4A6C",
            corner_radius=10, width=22, height=22
        )
        num_label.pack(side="left", padx=(10, 8), pady=8)

        # Text
        text_frame = ctk.CTkFrame(frame, fg_color="transparent")
        text_frame.pack(side="left", fill="both", expand=True)

        title_label = ctk.CTkLabel(
            text_frame, text=title,
            font=ctk.CTkFont(family=config.FONT_FAMILY, size=12, weight="bold"),
            text_color="#8899AA", anchor="w"
        )
        title_label.pack(fill="x", pady=(6, 0))

        desc_label = ctk.CTkLabel(
            text_frame, text=description,
            font=ctk.CTkFont(family=config.FONT_FAMILY, size=9),
            text_color="#556677", anchor="w"
        )
        desc_label.pack(fill="x")

        # Status icon
        status_label = ctk.CTkLabel(
            frame, text="○",
            font=ctk.CTkFont(size=14), text_color="#3A4A6C"
        )
        status_label.pack(side="right", padx=10)

        return {
            "frame": frame,
            "num": num_label,
            "title": title_label,
            "desc": desc_label,
            "status": status_label
        }

    def _build_footer(self):
        """Build the bottom status bar."""
        footer = ctk.CTkFrame(
            self.root, height=30, fg_color="#0D1B2A",
            corner_radius=0
        )
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        if config.SOFTWARE_FINGERPRINT:
            mode_text = "📷 SOFTWARE FP"
        elif config.SIMULATION_MODE:
            mode_text = "🔧 SIMULATION"
        else:
            mode_text = "🔌 HARDWARE"
        ctk.CTkLabel(
            footer, text=f"  {mode_text} MODE  |  "
                         f"Tolerance: {config.FACE_RECOGNITION_TOLERANCE}",
            font=ctk.CTkFont(family=config.FONT_FAMILY, size=10),
            text_color="#556677"
        ).pack(side="left", padx=10)

        self.time_label = ctk.CTkLabel(
            footer, text="",
            font=ctk.CTkFont(family=config.FONT_FAMILY, size=10),
            text_color="#556677"
        )
        self.time_label.pack(side="right", padx=10)
        self._update_clock()

    # ═══════════════════════════════════════════════════════════
    # CAMERA MANAGEMENT
    # ═══════════════════════════════════════════════════════════

    def _start_camera(self):
        """Start the webcam feed."""
        self.cap = cv2.VideoCapture(config.CAMERA_INDEX)
        if not self.cap.isOpened():
            logger.error("Cannot open webcam")
            self.camera_status_label.configure(
                text="● Offline", text_color=config.ACCENT_COLOR
            )
            return

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
        self.is_running = True
        self._update_camera()

    def _update_camera(self):
        """Refresh the camera feed in the UI."""
        if not self.is_running or self.cap is None:
            return

        ret, frame = self.cap.read()
        if ret:
            # If auth is active and we're in face scan stage, run recognition
            if self.auth_active and self.current_stage == AuthStage.FACE_SCAN:
                frame, user_id, confidence = \
                    self.face_recognizer.get_frame_with_recognition(frame)
                if user_id:
                    self.confidence_bar.set(confidence)
                    self.confidence_label.configure(
                        text=f"{confidence:.0%}"
                    )

            # Convert to display format
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            img = img.resize((580, 420), Image.LANCZOS)
            imgtk = ctk.CTkImage(light_image=img, dark_image=img, size=(580, 420))

            self.camera_label.configure(image=imgtk, text="")
            self.camera_label.image = imgtk

        # Schedule next update (~30 FPS)
        self.root.after(33, self._update_camera)

    def _stop_camera(self):
        """Stop the webcam feed."""
        self.is_running = False
        if self.cap:
            self.cap.release()
            self.cap = None

    # ═══════════════════════════════════════════════════════════
    # AUTHENTICATION FLOW (UI-DRIVEN)
    # ═══════════════════════════════════════════════════════════

    def _start_auth(self):
        """Begin the authentication pipeline in a background thread."""
        if self.auth_active:
            return

        self._reset()
        self.auth_active = True
        self.start_btn.configure(state="disabled", text="⏳ Authenticating...")

        # Run auth in background thread to keep UI responsive
        auth_thread = threading.Thread(target=self._run_auth_pipeline, daemon=True)
        auth_thread.start()

    def _run_auth_pipeline(self):
        """
        Execute the full authentication pipeline with UI updates.
        This runs in a background thread.
        """
        result = AuthResult()
        start_time = time.time()

        try:
            # Initialize recognizer if needed
            if not self.face_recognizer.is_loaded:
                self.face_recognizer.load_encodings()

            # ─── STAGE 1: Face Recognition ────────────────
            self._ui_update_stage("face", "active", "Scanning face...")
            self.current_stage = AuthStage.FACE_SCAN

            # Use the camera feed for recognition (5 second window)
            face_id = None
            face_confidence = 0.0
            confirmations = {}
            scan_start = time.time()
            required_confirmations = 5

            while time.time() - scan_start < 12:
                if self.cap and self.cap.isOpened():
                    ret, frame = self.cap.read()
                    if ret:
                        uid, conf, loc = self.face_recognizer.recognize_from_frame(frame)
                        if uid:
                            confirmations.setdefault(uid, []).append(conf)
                            if len(confirmations[uid]) >= required_confirmations:
                                face_id = uid
                                face_confidence = np.mean(confirmations[uid])
                                break
                time.sleep(0.1)

            if not face_id:
                self._ui_update_stage("face", "failed", "No face recognized")
                self._show_result("denied", "Face Not Recognized",
                                  "No matching face found. Try again.")
                self._finish_auth()
                return

            # Get user name
            user = self.db.get_user(face_id)
            user_name = user["name"] if user else face_id

            self._ui_update_stage("face", "passed",
                                  f"Identified: {user_name} ({face_confidence:.0%})")
            self.root.after(0, lambda: self.confidence_bar.set(face_confidence))
            self.root.after(0, lambda: self.confidence_label.configure(
                text=f"{face_confidence:.0%}"))

            self.db.log_auth_event(face_id, "face_recognition", "success",
                                   f"confidence={face_confidence:.3f}")
            time.sleep(0.8)

            # ─── STAGE 2: Liveness Check ──────────────────
            if config.LIVENESS_ENABLED:
                self._ui_update_stage("liveness", "active",
                                      "Blink 2 times to verify")
                self.current_stage = AuthStage.LIVENESS_CHECK

                self.liveness_detector.reset()
                blink_count = 0
                consec_closed = 0
                liveness_start = time.time()

                while time.time() - liveness_start < config.LIVENESS_TIMEOUT:
                    if self.cap and self.cap.isOpened():
                        ret, frame = self.cap.read()
                        if ret:
                            ear, blink, _ = \
                                self.liveness_detector.check_frame_liveness(frame)
                            if ear < config.EYE_AR_THRESH:
                                consec_closed += 1
                            else:
                                if consec_closed >= config.EYE_AR_CONSEC_FRAMES:
                                    blink_count += 1
                                    self._ui_update_stage(
                                        "liveness", "active",
                                        f"Blinks: {blink_count}/{config.LIVENESS_BLINK_REQUIRED}"
                                    )
                                consec_closed = 0

                            if blink_count >= config.LIVENESS_BLINK_REQUIRED:
                                break
                    time.sleep(0.05)

                if blink_count < config.LIVENESS_BLINK_REQUIRED:
                    self._ui_update_stage("liveness", "failed",
                                          "Liveness check failed")
                    self._show_result("denied", "Spoofing Detected",
                                      "Liveness verification failed.")
                    self._finish_auth()
                    return

                self._ui_update_stage("liveness", "passed", "Liveness confirmed")
                time.sleep(0.5)
            else:
                self._ui_update_stage("liveness", "skipped", "Disabled")

            # ─── STAGE 3: Fingerprint Scan ────────────────
            self.current_stage = AuthStage.FINGERPRINT_SCAN

            if config.SOFTWARE_FINGERPRINT:
                # ── Software fingerprint matching (image-based) ──
                self._ui_update_stage("fingerprint", "active",
                                      "Select fingerprint image...")

                # Show file dialog on main thread, wait for result
                self.fp_image_path = None
                self.fp_event.clear()
                self.root.after(
                    0, lambda: self._show_fingerprint_dialog(user_name)
                )

                # Block auth thread until user selects an image
                self.fp_event.wait(timeout=120)

                if not self.fp_image_path:
                    self._ui_update_stage("fingerprint", "failed",
                                          "No image selected")
                    self._show_result("denied", "Fingerprint Failed",
                                      "No fingerprint image provided.")
                    self._finish_auth()
                    return

                # Run ORB feature matching
                self._ui_update_stage("fingerprint", "active",
                                      "Matching fingerprint features...")
                time.sleep(0.5)

                fp_id, fp_match, fp_conf = \
                    self.fusion_engine.fingerprint_matcher.match(
                        self.fp_image_path
                    )

                if not fp_match or fp_id is None:
                    self._ui_update_stage("fingerprint", "failed",
                                          "Fingerprint not recognized")
                    self._show_result("denied", "Fingerprint Failed",
                                      "No matching fingerprint found.")
                    self.db.log_auth_event(
                        face_id, "fingerprint", "failure")
                    self._finish_auth()
                    return

                self._ui_update_stage(
                    "fingerprint", "passed",
                    f"Matched: ID {fp_id} ({fp_conf:.0%})"
                )
                self.db.log_auth_event(
                    face_id, "fingerprint", "success",
                    f"fp_id={fp_id}, confidence={fp_conf:.3f}"
                )

            else:
                # ── Hardware fingerprint scan (R307S via ESP32) ──
                self._ui_update_stage("fingerprint", "active",
                                      "Place finger on sensor...")

                if not self.fusion_engine.serial_handler.is_connected:
                    self.fusion_engine.serial_handler.connect()

                fp_id, fp_match = \
                    self.fusion_engine.serial_handler.request_fingerprint_scan(
                        timeout=config.FINGERPRINT_TIMEOUT,
                        expected_user_id=face_id
                    )

                if not fp_match or fp_id is None:
                    self._ui_update_stage("fingerprint", "failed",
                                          "Fingerprint not recognized")
                    self._show_result("denied", "Fingerprint Failed",
                                      "No matching fingerprint found.")
                    self.db.log_auth_event(
                        face_id, "fingerprint", "failure")
                    self._finish_auth()
                    return

                self._ui_update_stage("fingerprint", "passed",
                                      f"Matched: ID {fp_id}")
                self.db.log_auth_event(
                    face_id, "fingerprint", "success",
                    f"fp_id={fp_id}"
                )

            time.sleep(0.5)

            # ─── STAGE 4: Identity Fusion ─────────────────
            self._ui_update_stage("fusion", "active",
                                  "Cross-matching identities...")
            self.current_stage = AuthStage.IDENTITY_FUSION
            time.sleep(0.5)

            # Check if face ID and fingerprint ID belong to same user
            if user and user.get("fingerprint_id") == fp_id:
                self._ui_update_stage("fusion", "passed",
                                      "Identity confirmed ✓")
                self.db.log_auth_event(face_id, "identity_fusion", "success")
            else:
                self._ui_update_stage("fusion", "failed",
                                      "Identity mismatch!")
                self._show_result("denied", "Identity Mismatch",
                                  f"Face ≠ Fingerprint. Possible fraud.")
                self.db.log_auth_event(face_id, "identity_fusion", "mismatch",
                                       f"face={face_id}, fp={fp_id}")
                self._finish_auth()
                return

            time.sleep(0.5)

            # ─── STAGE 5: PIN Entry ───────────────────────
            self._ui_update_stage("pin", "active", "Enter your PIN")
            self.current_stage = AuthStage.PIN_ENTRY

            # Show PIN dialog and wait for result
            self.pin_value = ""
            self.pin_event.clear()
            self.root.after(0, lambda: self._show_pin_dialog(face_id, user_name))

            # Wait for PIN entry (blocking in background thread)
            self.pin_event.wait(timeout=60)

            if self.pin_callback_result is None:
                self._ui_update_stage("pin", "failed", "PIN entry cancelled")
                self._show_result("denied", "Cancelled",
                                  "PIN entry was cancelled.")
                self._finish_auth()
                return

            if self.pin_callback_result:
                self._ui_update_stage("pin", "passed", "PIN verified ✓")
                self.db.log_auth_event(face_id, "pin_entry", "success")
            else:
                self._ui_update_stage("pin", "failed", "Wrong PIN!")
                self._show_result("denied", "Invalid PIN",
                                  "Maximum PIN attempts exceeded.")
                self.db.log_auth_event(face_id, "pin_entry", "failure")
                self._finish_auth()
                return

            time.sleep(0.3)

            # ─── ACCESS GRANTED ───────────────────────
            duration = time.time() - start_time
            self._show_result("granted", f"Welcome, {user_name}!",
                              f"Authenticated in {duration:.1f}s")
            self.db.update_last_login(face_id)
            self.db.log_auth_event(face_id, "session", "granted",
                                   f"duration={duration:.1f}s")

        except Exception as e:
            logger.error(f"Auth pipeline error: {e}")
            self._show_result("error", "System Error", str(e))

        self._finish_auth()

    def _finish_auth(self):
        """Clean up after authentication attempt."""
        self.auth_active = False
        self.current_stage = AuthStage.IDLE
        self.root.after(0, lambda: self.start_btn.configure(
            state="normal", text="▶  Start Authentication"
        ))

    # ═══════════════════════════════════════════════════════════
    # PIN ENTRY DIALOG
    # ═══════════════════════════════════════════════════════════

    def _show_pin_dialog(self, user_id: str, user_name: str):
        """Show a modal PIN entry dialog."""
        self.pin_dialog = ctk.CTkToplevel(self.root)
        self.pin_dialog.title("PIN Entry")
        self.pin_dialog.geometry("320x450")
        self.pin_dialog.resizable(False, False)
        self.pin_dialog.configure(fg_color=config.SECONDARY_COLOR)
        self.pin_dialog.transient(self.root)
        self.pin_dialog.grab_set()

        # Center on parent
        self.pin_dialog.update_idletasks()
        x = self.root.winfo_x() + (config.WINDOW_WIDTH - 320) // 2
        y = self.root.winfo_y() + (config.WINDOW_HEIGHT - 450) // 2
        self.pin_dialog.geometry(f"+{x}+{y}")

        # Header
        ctk.CTkLabel(
            self.pin_dialog, text="🔢 Enter PIN",
            font=ctk.CTkFont(family=config.FONT_FAMILY, size=18, weight="bold"),
            text_color=config.TEXT_COLOR
        ).pack(pady=(20, 5))

        ctk.CTkLabel(
            self.pin_dialog, text=f"User: {user_name}",
            font=ctk.CTkFont(family=config.FONT_FAMILY, size=12),
            text_color="#7B8794"
        ).pack(pady=(0, 15))

        # PIN display (dots)
        self.pin_display = ctk.CTkLabel(
            self.pin_dialog, text="● ● ● ●".replace("●", "○"),
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=config.PRIMARY_COLOR,
            fg_color="#0A0F1A", corner_radius=8,
            width=200, height=50
        )
        self.pin_display.pack(pady=10)

        self.pin_error_label = ctk.CTkLabel(
            self.pin_dialog, text="",
            font=ctk.CTkFont(family=config.FONT_FAMILY, size=10),
            text_color=config.ACCENT_COLOR
        )
        self.pin_error_label.pack(pady=(0, 5))

        # Keypad
        keypad_frame = ctk.CTkFrame(
            self.pin_dialog, fg_color="transparent"
        )
        keypad_frame.pack(padx=30, pady=5)

        self._pin_input = ""
        self._pin_attempts = 0

        buttons = [
            ["1", "2", "3"],
            ["4", "5", "6"],
            ["7", "8", "9"],
            ["⌫", "0", "✓"],
        ]

        for row_idx, row in enumerate(buttons):
            for col_idx, label in enumerate(row):
                if label == "⌫":
                    cmd = self._pin_backspace
                    color = "#2A3A5C"
                    hover = "#3A4A6C"
                elif label == "✓":
                    cmd = lambda uid=user_id: self._pin_submit(uid)
                    color = config.PRIMARY_COLOR
                    hover = "#00B894"
                else:
                    cmd = lambda l=label: self._pin_press(l)
                    color = "#1B2838"
                    hover = "#2A3A5C"

                btn = ctk.CTkButton(
                    keypad_frame, text=label,
                    font=ctk.CTkFont(family=config.FONT_FAMILY,
                                     size=18, weight="bold"),
                    width=72, height=52, corner_radius=8,
                    fg_color=color, hover_color=hover,
                    text_color=config.TEXT_COLOR if label != "✓" else "#0D1B2A",
                    command=cmd
                )
                btn.grid(row=row_idx, column=col_idx, padx=4, pady=4)

        # Cancel button
        ctk.CTkButton(
            self.pin_dialog, text="Cancel",
            font=ctk.CTkFont(family=config.FONT_FAMILY, size=12),
            fg_color=config.ACCENT_COLOR, hover_color="#C0392B",
            text_color="white", width=120, height=32,
            corner_radius=6, command=self._pin_cancel
        ).pack(pady=(10, 15))

        self.pin_dialog.protocol("WM_DELETE_WINDOW", self._pin_cancel)

    def _pin_press(self, digit: str):
        """Handle keypad digit press."""
        if len(self._pin_input) < config.PIN_LENGTH:
            self._pin_input += digit
            dots = "● " * len(self._pin_input) + \
                   "○ " * (config.PIN_LENGTH - len(self._pin_input))
            self.pin_display.configure(text=dots.strip())

    def _pin_backspace(self):
        """Handle backspace on PIN keypad."""
        if self._pin_input:
            self._pin_input = self._pin_input[:-1]
            dots = "● " * len(self._pin_input) + \
                   "○ " * (config.PIN_LENGTH - len(self._pin_input))
            self.pin_display.configure(text=dots.strip())

    def _pin_submit(self, user_id: str):
        """Verify the entered PIN."""
        if len(self._pin_input) != config.PIN_LENGTH:
            self.pin_error_label.configure(
                text=f"PIN must be {config.PIN_LENGTH} digits"
            )
            return

        if self.db.verify_pin(user_id, self._pin_input):
            self.pin_callback_result = True
            self.pin_dialog.destroy()
            self.pin_event.set()
        else:
            self._pin_attempts += 1
            remaining = config.MAX_PIN_ATTEMPTS - self._pin_attempts

            if remaining <= 0:
                self.pin_callback_result = False
                self.pin_dialog.destroy()
                self.pin_event.set()
            else:
                self.pin_error_label.configure(
                    text=f"Wrong PIN! {remaining} attempts left"
                )
                self._pin_input = ""
                self.pin_display.configure(
                    text="○ " * config.PIN_LENGTH
                )

    def _pin_cancel(self):
        """Cancel PIN entry."""
        self.pin_callback_result = None
        self.pin_dialog.destroy()
        self.pin_event.set()

    # ═══════════════════════════════════════════════════════════
    # FINGERPRINT IMAGE DIALOG (SOFTWARE MODE)
    # ═══════════════════════════════════════════════════════════

    def _show_fingerprint_dialog(self, user_name: str):
        """Show a modal dialog for fingerprint image selection."""
        self.fp_dialog = ctk.CTkToplevel(self.root)
        self.fp_dialog.title("Fingerprint Scan")
        self.fp_dialog.geometry("420x600")
        self.fp_dialog.resizable(False, False)
        self.fp_dialog.configure(fg_color=config.SECONDARY_COLOR)
        self.fp_dialog.transient(self.root)
        self.fp_dialog.grab_set()
        self._fp_server = None

        # Center on parent
        self.fp_dialog.update_idletasks()
        x = self.root.winfo_x() + (config.WINDOW_WIDTH - 420) // 2
        y = self.root.winfo_y() + (config.WINDOW_HEIGHT - 600) // 2
        self.fp_dialog.geometry(f"+{x}+{y}")

        # Header
        ctk.CTkLabel(
            self.fp_dialog, text="🔐 Fingerprint Verification",
            font=ctk.CTkFont(family=config.FONT_FAMILY,
                             size=18, weight="bold"),
            text_color=config.TEXT_COLOR
        ).pack(pady=(20, 5))

        ctk.CTkLabel(
            self.fp_dialog, text=f"User: {user_name}",
            font=ctk.CTkFont(family=config.FONT_FAMILY, size=12),
            text_color="#7B8794"
        ).pack(pady=(0, 10))

        # Image preview area
        self.fp_preview = ctk.CTkLabel(
            self.fp_dialog,
            text="No image selected\n\nBrowse a fingerprint image file",
            font=ctk.CTkFont(size=12),
            text_color="#556677",
            fg_color="#0A0F1A", corner_radius=8,
            width=280, height=220
        )
        self.fp_preview.pack(padx=20, pady=10)

        # Status label
        self.fp_status_label = ctk.CTkLabel(
            self.fp_dialog,
            text="Choose a method below",
            font=ctk.CTkFont(family=config.FONT_FAMILY, size=11),
            text_color="#7B8794"
        )
        self.fp_status_label.pack(pady=5)

        # Buttons
        btn_frame = ctk.CTkFrame(self.fp_dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=30, pady=5)

        # Browse file
        ctk.CTkButton(
            btn_frame, text="📁  Browse Image File",
            font=ctk.CTkFont(family=config.FONT_FAMILY,
                             size=13, weight="bold"),
            fg_color="#1B4D8E", text_color="#E8F0FE",
            hover_color="#2A5DA0", height=40, corner_radius=8,
            command=self._fp_browse
        ).pack(fill="x", pady=(0, 6))

        # Submit button (disabled until image selected)
        self.fp_submit_btn = ctk.CTkButton(
            btn_frame, text="✓  Verify Fingerprint",
            font=ctk.CTkFont(family=config.FONT_FAMILY,
                             size=13, weight="bold"),
            fg_color="#2A3A5C", text_color=config.TEXT_COLOR,
            hover_color="#3A4A6C", height=40, corner_radius=8,
            state="disabled",
            command=self._fp_submit
        )
        self.fp_submit_btn.pack(fill="x", pady=(0, 6))

        ctk.CTkButton(
            btn_frame, text="Cancel",
            font=ctk.CTkFont(family=config.FONT_FAMILY, size=12),
            fg_color=config.ACCENT_COLOR, hover_color="#C0392B",
            text_color="white", height=32, corner_radius=6,
            command=self._fp_cancel
        ).pack(fill="x")

        self.fp_dialog.protocol("WM_DELETE_WINDOW", self._fp_cancel)

    def _fp_browse(self):
        """Open a file dialog to select a fingerprint image."""
        filepath = filedialog.askopenfilename(
            title="Select Fingerprint Image",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.bmp *.tif *.tiff"),
                ("All files", "*.*")
            ]
        )
        if filepath:
            self.fp_image_path = filepath
            try:
                img = Image.open(filepath)
                img = img.resize((280, 220), Image.LANCZOS)
                imgtk = ctk.CTkImage(light_image=img, dark_image=img, size=(280, 220))
                self.fp_preview.configure(image=imgtk, text="")
                self.fp_preview.image = imgtk
                self.fp_status_label.configure(
                    text=f"Selected: {os.path.basename(filepath)}",
                    text_color=config.PRIMARY_COLOR
                )
                self.fp_submit_btn.configure(
                    state="normal",
                    fg_color=config.PRIMARY_COLOR,
                    text_color="#0D1B2A"
                )
            except Exception as e:
                self.fp_status_label.configure(
                    text=f"Error loading image: {e}",
                    text_color=config.ACCENT_COLOR
                )

    def _fp_submit(self):
        """Submit the selected fingerprint image for matching."""
        if self._fp_server:
            self._fp_server.stop()
            self._fp_server = None
        self.fp_dialog.destroy()
        self.fp_event.set()

    def _fp_cancel(self):
        """Cancel fingerprint scan."""
        if self._fp_server:
            self._fp_server.stop()
            self._fp_server = None
        self.fp_image_path = None
        self.fp_dialog.destroy()
        self.fp_event.set()

    # ═══════════════════════════════════════════════════════════
    # UI HELPER METHODS
    # ═══════════════════════════════════════════════════════════

    def _ui_update_stage(self, step_key: str, status: str, message: str):
        """
        Update a pipeline step card in the UI (thread-safe).

        Args:
            step_key: Key in self.step_cards (face, liveness, fingerprint, etc.)
            status: "active", "passed", "failed", or "skipped"
            message: Status message to display
        """
        def update():
            card = self.step_cards.get(step_key)
            if not card:
                return

            if status == "active":
                card["frame"].configure(
                    fg_color="#0D2137", border_width=1, border_color=config.PRIMARY_COLOR
                )
                card["status"].configure(text="◉", text_color=config.WARNING_COLOR)
                card["title"].configure(text_color=config.TEXT_COLOR)
                card["desc"].configure(text=message, text_color=config.WARNING_COLOR)
                self.status_label.configure(text=message)
            elif status == "passed":
                card["frame"].configure(
                    fg_color="#0D2A1A", border_width=1, border_color=config.SUCCESS_COLOR
                )
                card["status"].configure(text="✓", text_color=config.SUCCESS_COLOR)
                card["title"].configure(text_color=config.SUCCESS_COLOR)
                card["desc"].configure(text=message, text_color=config.SUCCESS_COLOR)
                self.status_label.configure(text=message)
            elif status == "failed":
                card["frame"].configure(
                    fg_color="#2A0D0D", border_width=1, border_color=config.ACCENT_COLOR
                )
                card["status"].configure(text="✗", text_color=config.ACCENT_COLOR)
                card["title"].configure(text_color=config.ACCENT_COLOR)
                card["desc"].configure(text=message, text_color=config.ACCENT_COLOR)
                self.status_label.configure(text=message)
                self.status_dot.configure(text_color=config.ACCENT_COLOR)
            elif status == "skipped":
                card["status"].configure(text="—", text_color="#556677")
                card["desc"].configure(text=message, text_color="#556677")

        self.root.after(0, update)

    def _show_result(self, result_type: str, title: str, detail: str):
        """Update the result display card (thread-safe)."""
        def update():
            if result_type == "granted":
                color = config.SUCCESS_COLOR
                icon = "✅"
                self.result_frame.configure(fg_color="#0D2A1A")
                self.status_dot.configure(text_color=config.SUCCESS_COLOR)
            elif result_type == "denied":
                color = config.ACCENT_COLOR
                icon = "❌"
                self.result_frame.configure(fg_color="#2A0D0D")
                self.status_dot.configure(text_color=config.ACCENT_COLOR)
            else:
                color = config.WARNING_COLOR
                icon = "⚠️"
                self.result_frame.configure(fg_color="#2A1A0D")

            self.result_icon.configure(text=icon)
            self.result_title.configure(text=title, text_color=color)
            self.result_detail.configure(text=detail)
            self.status_label.configure(text=title)

        self.root.after(0, update)

    def _reset(self):
        """Reset all UI elements to initial state."""
        self.auth_active = False
        self.current_stage = AuthStage.IDLE
        self.pin_value = ""
        self.fp_image_path = None
        self.confidence_bar.set(0)
        self.confidence_label.configure(text="0%")
        self.status_dot.configure(text_color=config.SUCCESS_COLOR)
        self.status_label.configure(text="System Ready")

        # Reset result card
        self.result_frame.configure(fg_color="#0A0F1A")
        self.result_icon.configure(text="⏳")
        self.result_title.configure(
            text="Awaiting Authentication",
            text_color=config.TEXT_COLOR
        )
        self.result_detail.configure(text="Press 'Start' to begin")

        # Reset step cards
        for key, card in self.step_cards.items():
            card["frame"].configure(
                fg_color="#0D1B2A", border_width=0
            )
            card["status"].configure(text="○", text_color="#3A4A6C")
            card["title"].configure(text_color="#8899AA")
            # Restore original descriptions
            original_descs = {
                "face": "Identify user via webcam",
                "liveness": "Anti-spoofing check",
                "fingerprint": "Verify via image scan" if config.SOFTWARE_FINGERPRINT else "Verify via R307S sensor",
                "fusion": "Cross-match biometrics",
                "pin": "Enter 4-digit PIN code"
            }
            card["desc"].configure(
                text=original_descs.get(key, ""),
                text_color="#556677"
            )

        self.start_btn.configure(
            state="normal", text="▶  Start Authentication"
        )

    def _update_clock(self):
        """Update the footer clock."""
        import datetime
        now = datetime.datetime.now().strftime("%H:%M:%S  |  %d %b %Y")
        self.time_label.configure(text=now)
        self.root.after(1000, self._update_clock)

    def _on_close(self):
        """Handle window close."""
        self.is_running = False
        self._stop_camera()
        self.fusion_engine.shutdown()
        self.root.destroy()

    # ═══════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════

    def run(self):
        """Start the ATM interface application."""
        logger.system_event("ATM Interface", "Starting UI...")

        # Initialize systems
        self.fusion_engine.initialize()

        # Start camera
        self._start_camera()

        # Run main loop
        self.root.mainloop()
