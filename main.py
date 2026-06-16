"""
Main Entry Point - Multi-Modal Biometric Authentication System.
Provides CLI for system management and launches the ATM interface.

Usage:
    python main.py                  → Launch ATM interface
    python main.py --enroll         → Enroll a new user
    python main.py --encode         → Re-encode face dataset
    python main.py --list-users     → List all registered users
    python main.py --list-ports     → List available serial ports
    python main.py --simulate       → Run in simulation mode (no hardware)
    python main.py --test           → Run system self-test
"""

import sys
import os
import argparse

# Force UTF-8 encoding for standard output to support emojis/box-drawing characters on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from utils.logger import logger
from database.db_manager import DatabaseManager
from face_recognition_module.dataset_collector import DatasetCollector
from face_recognition_module.face_encoder import FaceEncoder
from face_recognition_module.face_recognizer import FaceRecognizer
from fingerprint_module.serial_handler import SerialHandler


def enroll_user():
    """Interactive user enrollment workflow."""
    logger.system_event("Enrollment", "Starting new user enrollment")

    db = DatabaseManager()

    # Get user details
    print("\n" + "=" * 50)
    print("   NEW USER ENROLLMENT")
    print("=" * 50)

    user_id = input("\n  User ID (e.g., USR001): ").strip().upper()
    if not user_id:
        logger.error("User ID cannot be empty")
        return

    # Check if user already exists
    if db.get_user(user_id):
        logger.error(f"User {user_id} already exists!")
        return

    name = input("  Full Name: ").strip()
    if not name:
        logger.error("Name cannot be empty")
        return

    pin = input("  4-digit PIN: ").strip()
    if len(pin) != config.PIN_LENGTH or not pin.isdigit():
        logger.error(f"PIN must be exactly {config.PIN_LENGTH} digits")
        return

    pin_confirm = input("  Confirm PIN: ").strip()
    if pin != pin_confirm:
        logger.error("PINs do not match")
        return

    # ── Step 1: Collect face images ──────────────────────
    print(f"\n{'─' * 50}")
    print("  STEP 1: Face Image Collection")
    print(f"{'─' * 50}")
    print("  We will capture 20 face images from your webcam.")
    print("  Follow the on-screen instructions.\n")

    mode = input("  Capture mode - [M]anual or [A]uto? (M/A): ").strip().upper()

    collector = DatasetCollector()
    if mode == "A":
        user_dir = collector.collect_auto(user_id, name, num_images=20)
    else:
        user_dir = collector.collect_faces(user_id, name, num_images=20)

    if not user_dir:
        logger.error("Face collection failed. Enrollment aborted.")
        return

    # ── Step 2: Generate face encodings ──────────────────
    print(f"\n{'─' * 50}")
    print("  STEP 2: Generating Face Encodings")
    print(f"{'─' * 50}\n")

    encoder = FaceEncoder()
    if not encoder.encode_dataset():
        logger.error("Face encoding failed. Enrollment aborted.")
        return

    avg_encoding = encoder.get_average_encoding(user_id)

    # ── Step 3: Fingerprint enrollment ───────────────────
    print(f"\n{'─' * 50}")
    print("  STEP 3: Fingerprint Enrollment")
    print(f"{'─' * 50}\n")

    if config.SOFTWARE_FINGERPRINT:
        # ── Software-based fingerprint enrollment ────────────────
        print("  📷 Software Fingerprint Mode")
        print("  Provide path(s) to fingerprint image(s) from the SOCOFing dataset.")
        print("  Supported formats: JPG, PNG, BMP, TIF")
        print("  Separate multiple paths with commas.\n")

        paths_input = input("  Image path(s): ").strip()
        if not paths_input:
            logger.error("No image paths provided")
            return

        image_paths = [p.strip().strip('"').strip("'")
                       for p in paths_input.split(",")]

        valid_paths = []
        for p in image_paths:
            if os.path.exists(p):
                valid_paths.append(p)
            else:
                logger.warning(f"File not found: {p}")

        if not valid_paths:
            logger.error("No valid fingerprint images found")
            return

        # Copy images to fingerprint dataset directory
        import shutil
        fp_dataset_dir = os.path.join(config.FINGERPRINT_DATASET_DIR, user_id)
        os.makedirs(fp_dataset_dir, exist_ok=True)

        saved_paths = []
        for i, src in enumerate(valid_paths):
            ext = os.path.splitext(src)[1]
            dst = os.path.join(fp_dataset_dir, f"fingerprint_{i:03d}{ext}")
            shutil.copy2(src, dst)
            saved_paths.append(dst)
            logger.info(f"Saved: {os.path.basename(src)} → {dst}")

        # Enroll via ORB image matcher
        from fingerprint_module.image_matcher import FingerprintImageMatcher
        matcher = FingerprintImageMatcher()
        matcher.load_templates()  # Load existing templates
        fingerprint_id = matcher.enroll(user_id, saved_paths)

        if fingerprint_id is None:
            logger.error("Fingerprint enrollment failed — no features extracted")
            return

        print(f"\n  ✓ Fingerprint enrolled as ID {fingerprint_id}")
        print(f"  ✓ {len(saved_paths)} image(s) processed")

    else:
        # ── Hardware-based enrollment (R307S via ESP32) ──────────
        fingerprint_id = input("  Fingerprint ID (1-127): ").strip()
        try:
            fingerprint_id = int(fingerprint_id)
            if not (1 <= fingerprint_id <= 127):
                raise ValueError
        except ValueError:
            logger.error("Fingerprint ID must be between 1 and 127")
            return

        if not config.SIMULATION_MODE:
            serial_handler = SerialHandler()
            if serial_handler.connect():
                print("\n  Place your finger on the R307S sensor...")
                print("  You will need to place it twice for enrollment.\n")

                if not serial_handler.request_enrollment(fingerprint_id):
                    logger.error("Fingerprint enrollment failed")
                    serial_handler.disconnect()
                    return
                serial_handler.disconnect()
            else:
                logger.warning("ESP32 not connected. Skipping hardware enrollment.")
                print("  ⚠ Fingerprint ID will be saved but not enrolled on sensor.")
                print("  ⚠ Enroll on sensor separately using Arduino Serial Monitor.")
        else:
            logger.info(f"SIMULATION: Fingerprint ID {fingerprint_id} registered")

    # ── Step 4: Save to database ─────────────────────────
    print(f"\n{'─' * 50}")
    print("  STEP 4: Saving to Database")
    print(f"{'─' * 50}\n")

    success = db.add_user(
        user_id=user_id,
        name=name,
        fingerprint_id=fingerprint_id,
        pin=pin,
        face_encoding=avg_encoding
    )

    if success:
        print("\n" + "=" * 50)
        print("   ✅ ENROLLMENT SUCCESSFUL!")
        print("=" * 50)
        print(f"   User ID      : {user_id}")
        print(f"   Name          : {name}")
        print(f"   Fingerprint   : ID {fingerprint_id}")
        print(f"   Face Images   : {user_dir}")
        print(f"   PIN           : {'*' * config.PIN_LENGTH}")
        print("=" * 50 + "\n")
    else:
        logger.error("Failed to save user to database")


def encode_faces():
    """Re-encode all face images in the dataset directory."""
    logger.system_event("Encoder", "Re-encoding face dataset")
    encoder = FaceEncoder()
    if encoder.encode_dataset():
        logger.success("Face encoding complete")

        # Optionally update database encodings
        db = DatabaseManager()
        for user_id in encoder.known_encodings:
            avg = encoder.get_average_encoding(user_id)
            if avg is not None:
                db.update_face_encoding(user_id, avg)
                logger.info(f"Updated DB encoding for {user_id}")
    else:
        logger.error("Face encoding failed")


def list_users():
    """Display all registered users."""
    db = DatabaseManager()
    users = db.get_all_users()

    if not users:
        print("\n  No users registered.\n")
        return

    print("\n" + "=" * 60)
    print("  REGISTERED USERS")
    print("=" * 60)
    print(f"  {'ID':<10} {'Name':<20} {'FP ID':<8} {'Created':<20}")
    print("  " + "─" * 56)
    for user in users:
        print(f"  {user['user_id']:<10} {user['name']:<20} "
              f"{user['fingerprint_id']:<8} {user['created_at']:<20}")
    print("=" * 60)
    print(f"  Total: {len(users)} user(s)\n")


def list_ports():
    """List available serial ports."""
    handler = SerialHandler()
    ports = handler.list_available_ports()
    if not ports:
        print("\n  No serial ports found.\n")
    else:
        print("\n  Available Serial Ports:")
        print("  " + "─" * 45)
        for p in ports:
            print(f"  {p['device']:<10} │ {p['description']}")
        print()


def run_self_test():
    """Run a system self-test to verify all components."""
    print("\n" + "=" * 50)
    print("   SYSTEM SELF-TEST")
    print("=" * 50 + "\n")

    results = {}

    # Test 1: Database
    print("  [1/5] Database...", end=" ")
    try:
        db = DatabaseManager()
        db.get_all_users()
        print("✅ OK")
        results["Database"] = True
    except Exception as e:
        print(f"❌ FAIL: {e}")
        results["Database"] = False

    # Test 2: Face encodings
    print("  [2/5] Face Encodings...", end=" ")
    if os.path.exists(config.ENCODINGS_FILE):
        try:
            recognizer = FaceRecognizer()
            recognizer.load_encodings()
            print(f"✅ OK ({len(recognizer.known_ids)} encodings)")
            results["Face Encodings"] = True
        except Exception as e:
            print(f"❌ FAIL: {e}")
            results["Face Encodings"] = False
    else:
        print("⚠️  NOT FOUND (run --encode first)")
        results["Face Encodings"] = False

    # Test 3: Webcam
    print("  [3/5] Webcam...", end=" ")
    try:
        import cv2
        cap = cv2.VideoCapture(config.CAMERA_INDEX)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            if ret:
                print(f"✅ OK ({frame.shape[1]}x{frame.shape[0]})")
                results["Webcam"] = True
            else:
                print("❌ FAIL: Cannot read frame")
                results["Webcam"] = False
        else:
            print("❌ FAIL: Cannot open camera")
            results["Webcam"] = False
    except Exception as e:
        print(f"❌ FAIL: {e}")
        results["Webcam"] = False

    # Test 4: Fingerprint subsystem
    if config.SOFTWARE_FINGERPRINT:
        print("  [4/5] Fingerprint Templates...", end=" ")
        if os.path.exists(config.FINGERPRINT_TEMPLATES_FILE):
            try:
                from fingerprint_module.image_matcher import FingerprintImageMatcher
                matcher = FingerprintImageMatcher()
                if matcher.load_templates():
                    print(f"✅ OK ({len(matcher.templates)} templates)")
                    results["Fingerprint"] = True
                else:
                    print("❌ FAIL: Cannot load templates")
                    results["Fingerprint"] = False
            except Exception as e:
                print(f"❌ FAIL: {e}")
                results["Fingerprint"] = False
        else:
            print("⚠️  NOT FOUND (run --enroll first)")
            results["Fingerprint"] = False
    elif config.SIMULATION_MODE:
        print("  [4/5] Serial Port...", end=" ")
        print("⚠️  SIMULATION MODE (skipped)")
        results["Serial Port"] = None
    else:
        print("  [4/5] Serial Port...", end=" ")
        try:
            handler = SerialHandler()
            if handler.connect():
                print(f"✅ OK ({config.SERIAL_PORT})")
                handler.disconnect()
                results["Serial Port"] = True
            else:
                print(f"❌ FAIL: Cannot connect to {config.SERIAL_PORT}")
                results["Serial Port"] = False
        except Exception as e:
            print(f"❌ FAIL: {e}")
            results["Serial Port"] = False

    # Test 5: Dataset directory
    print("  [5/5] Dataset...", end=" ")
    if os.path.exists(config.DATASET_DIR):
        users = [d for d in os.listdir(config.DATASET_DIR)
                 if os.path.isdir(os.path.join(config.DATASET_DIR, d))]
        total_images = sum(
            len([f for f in os.listdir(os.path.join(config.DATASET_DIR, u))
                 if f.endswith(('.jpg', '.png'))])
            for u in users
        )
        print(f"✅ OK ({len(users)} users, {total_images} images)")
        results["Dataset"] = True
    else:
        print("⚠️  EMPTY (run --enroll first)")
        results["Dataset"] = False

    # Summary
    passed = sum(1 for v in results.values() if v is True)
    total = sum(1 for v in results.values() if v is not None)
    print(f"\n  Result: {passed}/{total} checks passed")
    print("=" * 50 + "\n")


def main():
    """Main entry point with CLI argument handling."""
    parser = argparse.ArgumentParser(
        description="Multi-Modal Biometric Authentication System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                  Launch ATM interface
  python main.py --simulate       Launch in simulation mode
  python main.py --enroll         Enroll a new user
  python main.py --encode         Re-encode face dataset
  python main.py --list-users     Show registered users
  python main.py --list-ports     Show serial ports
  python main.py --test           Run system self-test
        """
    )

    parser.add_argument("--enroll", action="store_true",
                        help="Enroll a new user")
    parser.add_argument("--encode", action="store_true",
                        help="Re-encode face dataset")
    parser.add_argument("--list-users", action="store_true",
                        help="List all registered users")
    parser.add_argument("--list-ports", action="store_true",
                        help="List available serial ports")
    parser.add_argument("--simulate", action="store_true",
                        help="Run in simulation mode (no hardware)")
    parser.add_argument("--test", action="store_true",
                        help="Run system self-test")
    parser.add_argument("--port", type=str,
                        help="Override serial port (e.g., COM4)")

    args = parser.parse_args()

    # Apply overrides
    if args.simulate:
        config.SIMULATION_MODE = True
        logger.info("🔧 SIMULATION MODE enabled")

    if args.port:
        config.SERIAL_PORT = args.port
        logger.info(f"Serial port overridden to: {args.port}")

    # ── Banner ────────────────────────────────────────────
    print("\n" + "═" * 56)
    print("  🏦 Multi-Modal Biometric Authentication System")
    print("     Face Recognition + Fingerprint + PIN Fusion")
    print("═" * 56)

    # ── Dispatch ──────────────────────────────────────────
    if args.enroll:
        enroll_user()
    elif args.encode:
        encode_faces()
    elif args.list_users:
        list_users()
    elif args.list_ports:
        list_ports()
    elif args.test:
        run_self_test()
    else:
        # Launch ATM interface
        logger.system_event("Main", "Launching ATM Interface")
        from ui.atm_interface import ATMInterface
        app = ATMInterface()
        app.run()


if __name__ == "__main__":
    main()
