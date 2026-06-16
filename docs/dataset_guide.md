# Dataset Collection Guide

## Overview

This guide explains how to collect face images for the biometric authentication system. Quality dataset = better recognition accuracy.

---

## Directory Structure

```
dataset/
├── USR001/
│   ├── USR001_000.jpg
│   ├── USR001_001.jpg
│   ├── ... (15-30 images)
│   └── USR001_019.jpg
├── USR002/
│   ├── USR002_000.jpg
│   └── ...
└── USR003/
    └── ...
```

Each user gets their own folder named by `user_id`. Images are automatically named during collection.

---

## Collection Methods

### Method 1: Automated Collection (Recommended)

```bash
python main.py --enroll
```

This launches the interactive enrollment wizard which:
1. Asks for user details (ID, name, PIN)
2. Opens the webcam with guided instructions
3. Captures 20 images automatically (or manually with SPACE)
4. Generates face encodings
5. Enrolls fingerprint on R307S sensor
6. Saves everything to the database

### Method 2: Manual Collection

If you prefer to collect images separately:

1. Create a folder: `dataset/USR001/`
2. Take 15-30 photos of the person
3. Save them as `.jpg` or `.png` in the folder
4. Run encoding: `python main.py --encode`

### Method 3: Using the Collector Script Directly

```python
from face_recognition_module.dataset_collector import DatasetCollector

collector = DatasetCollector()

# Manual mode (press SPACE to capture)
collector.collect_faces("USR001", "John Doe", num_images=20)

# Auto mode (captures automatically every 0.5s)
collector.collect_auto("USR001", "John Doe", num_images=20, delay=0.5)
```

---

## Best Practices for High-Quality Dataset

### Lighting Conditions
- ✅ Well-lit room with even lighting
- ✅ Natural light from the front
- ❌ Avoid harsh shadows on the face
- ❌ Avoid backlighting (window behind)

### Face Angles (follow on-screen prompts)
- 📸 Straight/frontal view (most important)
- 📸 Slight left turn (~15°)
- 📸 Slight right turn (~15°)
- 📸 Slight upward tilt
- 📸 Slight downward tilt

### Expressions
- 😐 Neutral expression
- 🙂 Slight smile
- 😊 Natural smile

### Distance
- 📏 Normal distance (arm's length from webcam)
- 📏 Slightly closer
- 📏 Slightly farther

### Accessories
- 👓 With and without glasses (if applicable)
- 🧢 Without hat/cap (during enrollment)

---

## Recommended Number of Images

| Scenario              | Images/User | Notes                        |
|:----------------------|:------------|:-----------------------------|
| Minimum viable        | 5-10        | Basic recognition            |
| Recommended           | 15-25       | Good accuracy                |
| High security         | 30-50       | Best accuracy, more jitters  |

---

## After Collection

1. **Encode the dataset:**
   ```bash
   python main.py --encode
   ```
   This processes all images and generates `encodings/face_encodings.pkl`

2. **Verify encoding:**
   ```bash
   python main.py --test
   ```
   Check that the "Face Encodings" test passes.

3. **Add more images later:**
   Simply add more images to the user's folder and re-run `--encode`.

---

## Troubleshooting

| Issue                          | Solution                                    |
|:-------------------------------|:--------------------------------------------|
| "No face found in image"       | Ensure face is clearly visible, improve lighting |
| "Multiple faces detected"      | Only one person should be in frame          |
| Low recognition accuracy       | Add more images with varied angles          |
| Webcam not opening             | Check camera index in `config.py`           |
| Encoding takes too long        | Use "hog" model (default), not "cnn"        |
