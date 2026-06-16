# Project Progression Log

Documents every significant upgrade made to the system — what was used before,
what replaced it, and why.

---

## 1. Face Recognition Model

| | Before | After |
|---|---|---|
| **Library** | `face-recognition` + `dlib` | `insightface` + `onnxruntime` |
| **Model** | dlib ResNet (128-d embeddings) | ArcFace `buffalo_l` (512-d embeddings) |
| **Detection** | HOG (CPU) or CNN flag in config | RetinaFace (built into InsightFace pipeline) |
| **Accuracy (LFW)** | ~99.38% | ~99.77% |
| **Distance metric** | Euclidean on 128-d vectors | Cosine on L2-normalised 512-d vectors |
| **Tolerance** | 0.38 (Euclidean) | 0.40 (cosine distance) |

**Why:** dlib's ResNet was the weakest link in the stack. InsightFace's ArcFace
model uses a margin-based loss specifically designed for face verification, making
it substantially better at separating similar-looking faces. 512-d embeddings
capture more discriminative features. No `num_jitters` workaround needed — the
model quality handles variation natively.

**Files changed:** `face_recognition_module/face_encoder.py`,
`face_recognition_module/face_recognizer.py`

---

## 2. Face Detection Model

| | Before | After |
|---|---|---|
| **Model** | HOG (Histogram of Oriented Gradients) via dlib | RetinaFace (via InsightFace, built-in) |
| **Config flag** | `FACE_DETECTION_MODEL = "hog"` | Removed — InsightFace handles detection internally |

**Why:** HOG misses faces at angles and in poor lighting. RetinaFace is a
dedicated multi-scale face detector that handles rotation, occlusion, and
varied lighting significantly better. It comes bundled with InsightFace at
no extra cost.

**Files changed:** `config.py`

---

## 3. Liveness Detection Landmarks

| | Before | After |
|---|---|---|
| **Library** | `face_recognition.face_landmarks()` (dlib) | `mediapipe` Face Mesh |
| **Landmark count** | 68 points (6 used for EAR) | 478 points (6 used for EAR) |
| **Eye points** | Dlib's 6-point eye contour | MediaPipe indices `[362,385,387,263,373,380]` / `[33,160,158,133,153,144]` |

**Why:** dlib's 68-point model is older and less accurate at tracking eye
contours in non-frontal poses. MediaPipe Face Mesh was specifically designed
for dense real-time facial landmark tracking and is more robust to head tilt
and motion blur — both common during a live blink check.

**Files changed:** `face_recognition_module/liveness_detector.py`

---

## 4. Liveness Blink Thresholds

| | Before | After |
|---|---|---|
| `LIVENESS_BLINK_REQUIRED` | 2 | 3 |
| `EYE_AR_CONSEC_FRAMES` | 2 | 3 |

**Why:** 2 blinks is too easy to satisfy accidentally (or with a short video
loop). Requiring 3 blinks with 3 consecutive sub-threshold frames per blink
raises the bar for spoofing while still being trivial for a real person.

**Files changed:** `config.py`

---

## 5. Fingerprint Feature Extractor

| | Before | After |
|---|---|---|
| **Algorithm** | ORB (Oriented FAST and Rotated BRIEF) | SIFT (Scale-Invariant Feature Transform) |
| **Descriptor type** | Binary (uint8, Hamming distance) | Float32 (L2 distance, FLANN KD-tree) |
| **Matcher** | `BFMatcher(NORM_HAMMING)` | `FlannBasedMatcher` (KD-tree, `trees=5, checks=50`) |
| **Feature count** | 1500 | 3000 |
| **Match threshold** | 25 good matches | 35 good matches |

**Why:** ORB was designed for real-time general-purpose feature matching and
uses binary descriptors which lose precision on fingerprint ridges. SIFT
produces gradient-based float descriptors that are more distinctive for the
fine ridge patterns in fingerprint images. FLANN with a KD-tree is the
appropriate matcher for float descriptors and is faster than brute-force at
scale. Threshold raised from 25 → 35 to compensate for SIFT's higher
discriminative power (fewer false "good matches").

Note: CLAHE preprocessing and Lowe's ratio test were already implemented
before this upgrade.

**Files changed:** `fingerprint_module/image_matcher.py`, `config.py`

---

## 6. Training Data Volume

| | Before | After |
|---|---|---|
| **Default images per user** | 20 | 40 |

**Why:** More training images across varied lighting, angles, and expressions
give the ArcFace model more representative embeddings to average over,
reducing false rejects for the enrolled user.

**Files changed:** `face_recognition_module/dataset_collector.py`

---

## 7. Security — False Accept Hardening

| | Before | After |
|---|---|---|
| `MIN_FACE_CONFIDENCE` check | Defined in config but **never enforced** | Enforced: returns `None` if `final_confidence < 0.6` |
| Tolerance (Euclidean) | 0.45 | — |
| Tolerance (cosine, InsightFace) | — | 0.40 |

**Why:** The original code defined `MIN_FACE_CONFIDENCE = 0.6` but the
recognizer never checked it, so any face within distance threshold was
accepted regardless of confidence. The fix ensures the combined
distance+voting confidence must also clear 60% before a user ID is returned.

**Files changed:** `face_recognition_module/face_recognizer.py`, `config.py`

---

## 8. Dependencies

| | Before | After |
|---|---|---|
| Added | — | `insightface>=0.7.3`, `onnxruntime>=1.17.0`, `mediapipe>=0.10.0` |
| Removed | `face-recognition>=1.3.0`, `dlib>=19.24.0` | — |

`dlib` is a heavy C++ compile dependency that frequently causes installation
issues. Its removal simplifies `pip install -r requirements.txt` significantly.

**Files changed:** `requirements.txt`
