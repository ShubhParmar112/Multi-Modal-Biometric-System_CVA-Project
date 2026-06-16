# Testing Strategy

## Overview

This document outlines the testing methodology for the Multi-Modal Biometric Authentication System, covering accuracy metrics, security testing, and system reliability.

---

## 1. Biometric Accuracy Metrics

### 1.1 Face Recognition Metrics

| Metric | Formula | Target |
|:-------|:--------|:-------|
| **False Acceptance Rate (FAR)** | Impostor matches / Total impostor attempts | < 0.1% |
| **False Rejection Rate (FRR)** | Genuine rejections / Total genuine attempts | < 5% |
| **Equal Error Rate (EER)** | FAR = FRR crossover point | < 2% |
| **True Positive Rate (TPR)** | Correct identifications / Total genuine attempts | > 95% |

### How to Test FAR (Face)

```
Test Procedure:
1. Enroll 5 authorized users
2. Have 10 unauthorized persons attempt authentication
3. Record how many unauthorized attempts are accepted
4. FAR = Accepted impostors / Total impostor attempts × 100%

Expected: FAR < 0.1%
```

### How to Test FRR (Face)

```
Test Procedure:
1. Each enrolled user attempts authentication 20 times
2. Vary conditions: lighting, distance, angle, expressions
3. Record how many genuine attempts are rejected
4. FRR = Rejected genuine / Total genuine attempts × 100%

Expected: FRR < 5%
```

### 1.2 Fingerprint Metrics

| Metric | Target |
|:-------|:-------|
| R307S FAR (sensor spec) | < 0.001% |
| R307S FRR (sensor spec) | < 1% |
| Enrollment Success Rate | > 98% |
| Match Time | < 1 second |

### 1.3 Fused System Metrics

Since both biometrics must match, the fused system has:
- **Fused FAR** = FAR_face × FAR_fingerprint (multiplicative, much lower)
- **Fused FRR** = 1 - (1 - FRR_face) × (1 - FRR_fingerprint)

---

## 2. Test Cases

### 2.1 Face Recognition Tests

| # | Test Case | Input | Expected Output | Status |
|:--|:----------|:------|:----------------|:-------|
| F1 | Enrolled user, normal lighting | Known face | MATCH with confidence > 70% | ☐ |
| F2 | Enrolled user, dim lighting | Known face | MATCH with confidence > 60% | ☐ |
| F3 | Unknown person | Unknown face | "Unknown" or low confidence | ☐ |
| F4 | Printed photo (anti-spoofing) | Photo of user | Liveness FAIL (no blinks) | ☐ |
| F5 | Video on phone screen | Video of user | Liveness FAIL | ☐ |
| F6 | No face in frame | Empty frame | "No face detected" | ☐ |
| F7 | Multiple faces | 2+ faces | Uses largest face | ☐ |
| F8 | User with glasses | Glasses on/off | MATCH (if trained with both) | ☐ |
| F9 | Different expressions | Various | MATCH with varied confidence | ☐ |
| F10 | Recognition timeout | No face for 15s | Timeout → DENIED | ☐ |

### 2.2 Fingerprint Tests

| # | Test Case | Input | Expected Output | Status |
|:--|:----------|:------|:----------------|:-------|
| P1 | Enrolled finger | Correct finger | MATCH:<id> | ☐ |
| P2 | Unenrolled finger | Wrong finger | NO_MATCH | ☐ |
| P3 | Wet finger | Damp finger | MATCH or NO_MATCH (acceptable) | ☐ |
| P4 | Sensor timeout | No finger placed | NO_MATCH (timeout) | ☐ |
| P5 | Sensor disconnected | No sensor | SENSOR_ERROR | ☐ |
| P6 | Enrollment flow | New finger, 2 scans | ENROLL_OK:<id> | ☐ |
| P7 | Duplicate enrollment | Same finger, new ID | Should succeed | ☐ |

### 2.3 Identity Fusion Tests

| # | Test Case | Face ID | FP ID | Expected | Status |
|:--|:----------|:--------|:------|:---------|:-------|
| U1 | Both match same user | USR001 | 1 (USR001's) | PROCEED to PIN | ☐ |
| U2 | Face ≠ Fingerprint | USR001 | 2 (USR002's) | DENIED (mismatch) | ☐ |
| U3 | Face OK, FP fails | USR001 | None | DENIED | ☐ |
| U4 | Face fails, FP OK | None | 1 | DENIED (face first) | ☐ |

### 2.4 PIN Entry Tests

| # | Test Case | Input | Expected | Status |
|:--|:----------|:------|:---------|:-------|
| N1 | Correct PIN | Valid 4-digit | ACCESS GRANTED | ☐ |
| N2 | Wrong PIN | Invalid PIN | Error + retry | ☐ |
| N3 | 3 wrong PINs | 3× invalid | LOCKED OUT | ☐ |
| N4 | Cancel PIN entry | Click Cancel | DENIED | ☐ |
| N5 | Incomplete PIN | 2 digits + submit | Error message | ☐ |

### 2.5 System Integration Tests

| # | Test Case | Description | Expected | Status |
|:--|:----------|:------------|:---------|:-------|
| S1 | Full happy path | Face→FP→PIN all correct | ACCESS GRANTED | ☐ |
| S2 | Full reject path | Unknown person | DENIED at face | ☐ |
| S3 | Multiple users | 3 users, each authenticates | All succeed | ☐ |
| S4 | Sequential attempts | Deny→Reset→Success | Works correctly | ☐ |
| S5 | Simulation mode | No hardware, --simulate | Full pipeline works | ☐ |
| S6 | Session timeout | Wait 30s during auth | Session expires | ☐ |

---

## 3. Performance Benchmarks

| Metric | Target | How to Measure |
|:-------|:-------|:---------------|
| Face detection time | < 200ms per frame | Time `recognize_from_frame()` |
| Face encoding generation | < 2s per image | Time `encode_dataset()` |
| Fingerprint match time | < 1s | Measure ESP32 scan time |
| PIN verification | < 50ms | Time `verify_pin()` |
| Total auth pipeline | < 30s | End-to-end timing |
| UI frame rate | > 25 FPS | Monitor camera feed |
| Memory usage | < 500MB | Monitor Python process |

---

## 4. Security Testing

### 4.1 Anti-Spoofing Tests

```
Test 1: Printed Photo Attack
  - Print a high-quality photo of enrolled user
  - Hold in front of webcam
  - Expected: DENIED (liveness check fails - no blink)

Test 2: Screen Replay Attack
  - Play a video of enrolled user on phone/tablet
  - Hold in front of webcam
  - Expected: DENIED (liveness check may detect flat surface)

Test 3: Fingerprint Cast
  - Use clay/silicone fingerprint mold
  - Expected: NO_MATCH (R307S has anti-spoofing)
```

### 4.2 Database Security

- PINs are stored as SHA-256 hashes (not plaintext)
- Face encodings are serialized binary (not reversible to face)
- Database is local SQLite (no network exposure)

---

## 5. Running Tests

### Automated Self-Test

```bash
python main.py --test
```

This checks:
1. ✅ Database connectivity
2. ✅ Face encodings loaded
3. ✅ Webcam accessible
4. ✅ Serial port connected
5. ✅ Dataset directory populated

### Manual Testing Checklist

```
[ ] 1. Install all dependencies (requirements.txt)
[ ] 2. Flash ESP32 firmware
[ ] 3. Wire R307S sensor
[ ] 4. Enroll at least 2 users
[ ] 5. Run face recognition test (known user)
[ ] 6. Run face recognition test (unknown person)
[ ] 7. Run fingerprint test (enrolled finger)
[ ] 8. Run fingerprint test (unenrolled finger)
[ ] 9. Run full pipeline (happy path)
[ ] 10. Run full pipeline (mismatch path)
[ ] 11. Test PIN attempts (correct + 3 wrong)
[ ] 12. Test simulation mode
[ ] 13. Test liveness detection with photo
[ ] 14. Check log files generated
[ ] 15. Verify database audit trail
```

---

## 6. Accuracy Improvement Tips

1. **More training images** → Higher recognition accuracy
2. **Lower tolerance** → Stricter matching (fewer false accepts)
3. **More jitters** → Better encodings (slower enrollment)
4. **CNN model** → Better detection (requires GPU)
5. **Multiple confirmations** → Reduces random false matches
6. **Proper lighting** → Consistent recognition
