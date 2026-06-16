# Step-by-Step Setup Guide

## Prerequisites

### Hardware Required
- [x] ESP32 DevKit (any variant with USB)
- [x] R307S Fingerprint Sensor (with JST cable)
- [x] Breadboard + 4 jumper wires (Male-to-Female)
- [x] Laptop with webcam
- [x] USB cable (Micro-USB or USB-C for ESP32)

### Software Required
- [x] Python 3.8+ installed
- [x] Arduino IDE 2.x installed
- [x] Git (optional)

---

## Part A: Python Environment Setup

### Step 1: Create Virtual Environment

```bash
# Navigate to project directory
cd "c:\Users\Shubh Parmar\Desktop\NMIMS\YEAR 5\Practice\Practice Semester X\CVA Practice\try1"

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Mac/Linux)
# source venv/bin/activate
```

### Step 2: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> ⚠️ **dlib Installation Note (Windows)**
> If `dlib` fails to install, try:
> ```bash
> pip install cmake
> pip install dlib
> ```
> Or install the prebuilt wheel:
> ```bash
> pip install dlib-19.24.2-cp311-cp311-win_amd64.whl
> ```
> Find precompiled wheels at: https://github.com/z-mahmud22/Dlib_Windows_Python3.x

### Step 3: Verify Installation

```bash
python -c "import cv2; print('OpenCV:', cv2.__version__)"
python -c "import face_recognition; print('face_recognition: OK')"
python -c "import serial; print('PySerial:', serial.__version__)"
python -c "import customtkinter; print('CustomTkinter: OK')"
```

---

## Part B: ESP32 Firmware Setup

### Step 1: Install Arduino IDE

1. Download Arduino IDE 2.x from https://www.arduino.cc/en/software
2. Install and open

### Step 2: Add ESP32 Board Support

1. Go to **File → Preferences**
2. In "Additional Board Manager URLs", add:
   ```
   https://dl.espressif.com/dl/package_esp32_index.json
   ```
3. Go to **Tools → Board → Board Manager**
4. Search "ESP32" and install **"esp32 by Espressif Systems"**

### Step 3: Install Fingerprint Library

1. Go to **Sketch → Include Library → Manage Libraries**
2. Search: **"Adafruit Fingerprint Sensor Library"**
3. Install the latest version by Adafruit

### Step 4: Wire the R307S Sensor

Follow the wiring diagram in `docs/wiring_diagram.md`:
```
ESP32 3.3V    → R307S VCC (Red)
ESP32 GND     → R307S GND (Black)
ESP32 GPIO 16 → R307S TX (Green)
ESP32 GPIO 17 → R307S RX (White)
```

### Step 5: Upload Firmware

1. Open `esp32/fingerprint_auth/fingerprint_auth.ino` in Arduino IDE
2. Select board: **Tools → Board → ESP32 Dev Module**
3. Select port: **Tools → Port → COMx** (your ESP32 port)
4. Click **Upload** (→ arrow button)
5. Open **Serial Monitor** (115200 baud) to verify `READY` message

---

## Part C: System Configuration

### Step 1: Configure Serial Port

1. Find your ESP32 port:
   ```bash
   python main.py --list-ports
   ```
2. Edit `config.py`:
   ```python
   SERIAL_PORT = "COM3"  # Change to your port
   ```

### Step 2: Configure Camera

```python
# In config.py
CAMERA_INDEX = 0  # Usually 0 for built-in webcam, 1 for external
```

### Step 3: Run System Test

```bash
python main.py --test
```

All checks should show ✅ (except Face Encodings before first enrollment).

---

## Part D: Enroll Your First User

### Step 1: Start Enrollment

```bash
python main.py --enroll
```

### Step 2: Follow the Prompts

```
  User ID (e.g., USR001): USR001
  Full Name: Shubh Parmar
  4-digit PIN: 1234
  Confirm PIN: 1234
```

### Step 3: Capture Face Images

- Follow on-screen instructions (20 images)
- Press SPACE to capture (Manual mode)
- Or choose Auto mode for automatic capture

### Step 4: Enroll Fingerprint

- Enter fingerprint ID (1-127)
- Place finger on R307S sensor (twice)

### Step 5: Verify Enrollment

```bash
python main.py --list-users
```

---

## Part E: Run the ATM Interface

### With Hardware
```bash
python main.py
```

### Without Hardware (Simulation Mode)
```bash
python main.py --simulate
```

### With Custom Port
```bash
python main.py --port COM5
```

---

## Part F: Authentication Flow

1. Click **"Start Authentication"** in the UI
2. Look at the camera (face recognition)
3. Blink naturally (liveness check)
4. Place finger on R307S sensor (fingerprint)
5. Enter 4-digit PIN on the keypad
6. **Access Granted** or **Denied**

---

## Quick Reference Commands

| Command                    | Purpose                         |
|:---------------------------|:--------------------------------|
| `python main.py`           | Launch ATM interface            |
| `python main.py --simulate`| Launch without hardware         |
| `python main.py --enroll`  | Enroll new user                 |
| `python main.py --encode`  | Re-encode face dataset          |
| `python main.py --list-users`| Show all users               |
| `python main.py --list-ports`| Show serial ports             |
| `python main.py --test`    | System self-test                |
| `python main.py --port COM5`| Override serial port           |

---

## Troubleshooting

| Error                          | Fix                                         |
|:-------------------------------|:--------------------------------------------|
| `dlib` install fails           | Install CMake first, or use prebuilt wheel   |
| Camera not found               | Change `CAMERA_INDEX` in config.py           |
| ESP32 not detected             | Install CP2102/CH340 USB driver              |
| `SENSOR_ERROR` in serial       | Check wiring (TX↔RX crossover)               |
| `No encodings file`            | Run `python main.py --encode`                |
| PIN dialog not appearing       | Ensure face + fingerprint pass first         |
| Slow recognition               | Use `FACE_DETECTION_MODEL = "hog"` (default) |
