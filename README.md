# 🏦 Multi-Modal Biometric Authentication System for ATM Security

> **Face Recognition + Fingerprint Fusion + PIN Verification**  
> A fully offline, multi-factor biometric authentication system designed for ATM security.

---

## 📋 System Overview

This project implements a **three-factor authentication pipeline** that combines:

1. **Face Recognition** (Computer Vision — OpenCV + face_recognition)
2. **Fingerprint Authentication** (R307S sensor + ESP32 via UART)
3. **PIN Verification** (Knowledge-based factor)

With **anti-spoofing** via liveness detection (blink detection using Eye Aspect Ratio).

### Authentication Pipeline

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Face Scan   │───▶│  Liveness    │───▶│ Fingerprint  │───▶│  Identity    │───▶│    PIN       │
│  (Webcam)    │    │  Check       │    │  (R307S)     │    │  Fusion      │    │  Entry       │
│              │    │  (Blink)     │    │              │    │              │    │              │
│  Identify    │    │  Anti-spoof  │    │  Verify      │    │  Face == FP? │    │  4-digit     │
│  user        │    │  check       │    │  finger      │    │  Match IDs   │    │  code        │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
       │                   │                   │                   │                   │
    PASS/FAIL          PASS/FAIL           PASS/FAIL           PASS/FAIL           PASS/FAIL
                                                                                       │
                                                                              ┌────────▼────────┐
                                                                              │ ACCESS GRANTED / │
                                                                              │ ACCESS DENIED    │
                                                                              └─────────────────┘
```

---

## 🗂️ Project Structure

```
try1/
├── main.py                          # Entry point (CLI + UI launcher)
├── config.py                        # All system configuration
├── requirements.txt                 # Python dependencies
│
├── face_recognition_module/         # Computer Vision subsystem
│   ├── __init__.py
│   ├── dataset_collector.py         # Webcam-based face image capture
│   ├── face_encoder.py              # Generate 128-d face encodings
│   ├── face_recognizer.py           # Real-time face identification
│   └── liveness_detector.py         # Anti-spoofing (blink detection)
│
├── fingerprint_module/              # ESP32/R307S subsystem
│   ├── __init__.py
│   └── serial_handler.py            # Serial communication with ESP32
│
├── auth/                            # Authentication logic
│   ├── __init__.py
│   └── fusion_engine.py             # Multi-modal fusion orchestrator
│
├── database/                        # Data persistence
│   ├── __init__.py
│   └── db_manager.py                # SQLite CRUD + audit logging
│
├── ui/                              # User interface
│   ├── __init__.py
│   └── atm_interface.py             # CustomTkinter ATM simulation
│
├── utils/                           # Utilities
│   ├── __init__.py
│   └── logger.py                    # Color-coded logging + audit trail
│
├── esp32/                           # Microcontroller firmware
│   └── fingerprint_auth/
│       └── fingerprint_auth.ino     # ESP32 Arduino sketch for R307S
│
├── docs/                            # Documentation
│   ├── wiring_diagram.md            # ESP32 ↔ R307S wiring
│   ├── setup_guide.md               # Full installation guide
│   ├── dataset_guide.md             # Face image collection guide
│   └── testing_strategy.md          # Testing methodology + metrics
│
├── dataset/                         # Face images (created at runtime)
│   └── USR001/
│       └── *.jpg
│
├── encodings/                       # Face encodings (created at runtime)
│   └── face_encodings.pkl
│
├── logs/                            # Audit logs (created at runtime)
│   └── auth_YYYYMMDD.log
│
└── README.md                        # This file
```

---

## 🔧 Hardware Requirements

| Component | Purpose | Notes |
|:----------|:--------|:------|
| ESP32 DevKit | Microcontroller | Any variant with USB |
| R307S Sensor | Fingerprint scanner | Optical, UART interface |
| Breadboard | Prototyping | Standard full/half size |
| Jumper Wires | Connections | 4× Male-to-Female |
| USB Cable | ESP32 ↔ Laptop | Micro-USB or USB-C |
| Laptop | CV Processing | With webcam |

---

## 💻 Software Stack

| Component | Technology | Purpose |
|:----------|:-----------|:--------|
| Backend | Python 3.8+ | Main processing |
| Face Detection | OpenCV (Haar/HOG) | Detect faces in frames |
| Face Recognition | face_recognition (dlib) | 128-d embeddings |
| Anti-Spoofing | EAR Blink Detection | Liveness verification |
| Serial Comm | PySerial | ESP32 communication |
| Database | SQLite3 | User records + audit log |
| UI | CustomTkinter | ATM simulation interface |
| Firmware | Arduino (C++) | ESP32 R307S control |

---

## 🚀 Quick Start

### 1. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 2. Flash ESP32 (if using hardware)
- Open `esp32/fingerprint_auth/fingerprint_auth.ino` in Arduino IDE
- Install "Adafruit Fingerprint Sensor Library"
- Upload to ESP32

### 3. Enroll a User
```bash
python main.py --enroll           # With hardware
python main.py --enroll --simulate # Without hardware
```

### 4. Launch ATM Interface
```bash
python main.py                    # With hardware
python main.py --simulate         # Without hardware
```

---

## 📖 CLI Commands

```
python main.py                     → Launch ATM interface
python main.py --simulate          → Launch in simulation mode
python main.py --enroll            → Enroll new user
python main.py --encode            → Re-encode face dataset
python main.py --list-users        → List registered users
python main.py --list-ports        → List serial ports
python main.py --test              → System self-test
python main.py --port COM5         → Override serial port
```

---

## 🗄️ Database Schema

```sql
-- User records
users (
    user_id        TEXT PRIMARY KEY,    -- e.g., "USR001"
    name           TEXT NOT NULL,       -- "John Doe"
    face_encoding  BLOB,               -- 128-d numpy array (pickled)
    fingerprint_id INTEGER UNIQUE,     -- R307S sensor ID (1-127)
    pin_hash       TEXT NOT NULL,       -- SHA-256 hashed PIN
    created_at     TIMESTAMP,
    last_login     TIMESTAMP,
    is_active      INTEGER DEFAULT 1
)

-- Audit trail
auth_logs (
    id             INTEGER PRIMARY KEY,
    user_id        TEXT,
    event_type     TEXT,               -- face_recognition, fingerprint, pin_entry, etc.
    result         TEXT,               -- success, failure, timeout, denied
    details        TEXT,
    timestamp      TIMESTAMP
)
```

---

## 📊 Key Features

- ✅ **Multi-modal fusion** — Face + Fingerprint + PIN
- ✅ **Anti-spoofing** — Liveness detection via blink analysis
- ✅ **Confidence scoring** — Majority voting + distance metrics
- ✅ **Audit logging** — Every auth event logged to file + database
- ✅ **Multiple users** — Support for 127 users (R307S limit)
- ✅ **Simulation mode** — Full testing without hardware
- ✅ **Fully offline** — Zero cloud dependencies
- ✅ **Premium UI** — Dark-themed ATM simulation with live camera feed
- ✅ **Modular design** — Each component independently testable

---

## 📚 Documentation

| Document | Description |
|:---------|:------------|
| [Setup Guide](docs/setup_guide.md) | Full installation + configuration |
| [Wiring Diagram](docs/wiring_diagram.md) | ESP32 ↔ R307S connections |
| [Dataset Guide](docs/dataset_guide.md) | Face image collection tips |
| [Testing Strategy](docs/testing_strategy.md) | Accuracy metrics + test cases |

---

## 🔐 Security Considerations

- PINs stored as SHA-256 hashes (not reversible)
- Face encodings are 128-d vectors (cannot reconstruct face)
- All processing done locally (no cloud, no internet)
- Audit trail for forensic analysis
- Liveness detection prevents photo/video attacks
- Identity fusion prevents stolen biometric replay

---

## 📄 License

Academic project — NMIMS University, Semester X  
Computer Vision Applications Practice
