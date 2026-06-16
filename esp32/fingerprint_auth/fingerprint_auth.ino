/*
 * ═══════════════════════════════════════════════════════════════
 * ESP32 + R307S Fingerprint Authentication Firmware
 * ═══════════════════════════════════════════════════════════════
 * 
 * Multi-Modal Biometric Authentication System
 * Part of: ATM Security using Face Recognition & Fingerprint Fusion
 * 
 * Hardware:
 *   - ESP32 (any variant)
 *   - R307S / R307 Optical Fingerprint Sensor
 *   
 * Wiring (ESP32 → R307S):
 *   GPIO 16 (RX2) → TX (Green wire)
 *   GPIO 17 (TX2) → RX (White wire)
 *   VIN (5V)      → VCC (Red wire)   ← Use 5V, NOT 3.3V!
 *   GND            → GND (Black wire)
 *   
 * Serial Protocol (ESP32 ↔ Python):
 *   ESP32 → Python:
 *     READY                    → Sensor initialized
 *     MATCH:<id>               → Fingerprint matched with ID
 *     NO_MATCH                 → Fingerprint not found
 *     ENROLL_OK:<id>           → Enrollment successful
 *     ENROLL_FAIL              → Enrollment failed
 *     PLACE_FINGER             → Prompt to place finger
 *     REMOVE_FINGER            → Prompt to remove finger
 *     PLACE_AGAIN              → Prompt to place finger again
 *     SENSOR_ERROR             → Sensor communication error
 *     TEMPLATE_COUNT:<n>       → Number of stored templates
 *     
 *   Python → ESP32:
 *     SCAN                     → Request fingerprint scan
 *     ENROLL:<id>              → Enroll fingerprint with given ID
 *     DELETE:<id>              → Delete fingerprint with given ID
 *     COUNT                    → Get stored template count
 *     STATUS                   → Get sensor status
 *     EMPTY                    → Delete all fingerprints
 *     
 * Library: Adafruit Fingerprint Sensor Library
 *   Install via Arduino Library Manager: "Adafruit Fingerprint Sensor Library"
 */

#include <Adafruit_Fingerprint.h>

// ═══════════════════════════════════════════════════════════════
// PIN CONFIGURATION
// ═══════════════════════════════════════════════════════════════
#define FINGERPRINT_RX  16    // ESP32 RX (connects to R307S TX)
#define FINGERPRINT_TX  17    // ESP32 TX (connects to R307S RX)
#define LED_PIN         2     // Onboard LED for status indication
#define BAUD_RATE       115200 // USB Serial baud rate

// ═══════════════════════════════════════════════════════════════
// GLOBALS
// ═══════════════════════════════════════════════════════════════

// Hardware Serial2 for R307S communication
HardwareSerial fpSerial(2);  
Adafruit_Fingerprint finger = Adafruit_Fingerprint(&fpSerial);

String inputBuffer = "";     // Buffer for incoming serial commands
bool sensorReady = false;    // Sensor initialization status

// Baud rates to try when connecting to R307S
const long sensorBaudRates[] = {57600, 9600, 115200};
const int numBaudRates = 3;

// ═══════════════════════════════════════════════════════════════
// SETUP
// ═══════════════════════════════════════════════════════════════
void setup() {
  // Initialize USB serial (communication with Python)
  Serial.begin(BAUD_RATE);
  while (!Serial) { delay(10); }
  
  // Status LED
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  
  Serial.println("INIT");
  
  // Try multiple baud rates to find the sensor
  for (int i = 0; i < numBaudRates; i++) {
    long baud = sensorBaudRates[i];
    Serial.print("TRYING_BAUD:");
    Serial.println(baud);
    
    fpSerial.begin(baud, SERIAL_8N1, FINGERPRINT_RX, FINGERPRINT_TX);
    finger.begin(baud);
    delay(1000);  // Give sensor time to respond
    
    if (finger.verifyPassword()) {
      sensorReady = true;
      Serial.print("READY_AT:");
      Serial.println(baud);
      Serial.println("READY");

      // IMPORTANT: getParameters() reads the sensor's real template
      // capacity into finger.capacity. Without this call, the library
      // keeps its hardcoded default of 64, and fingerSearch() (used in
      // scanFingerprint() below) only scans IDs 1-64 — any user enrolled
      // with a higher fingerprint ID would silently never be found.
      finger.getParameters();
      Serial.print("CAPACITY:");
      Serial.println(finger.capacity);

      // Report template count
      finger.getTemplateCount();
      Serial.print("TEMPLATE_COUNT:");
      Serial.println(finger.templateCount);
      
      // LED blink to indicate ready
      blinkLED(3, 150);
      return;  // Exit setup, sensor found
    }
    
    fpSerial.end();  // Close before trying next baud rate
    delay(200);
  }
  
  // None of the baud rates worked
  Serial.println("SENSOR_ERROR");
  Serial.println("CHECK_WIRING");
  sensorReady = false;
}

// ═══════════════════════════════════════════════════════════════
// MAIN LOOP
// ═══════════════════════════════════════════════════════════════
void loop() {
  // Read and process serial commands from Python
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      inputBuffer.trim();
      if (inputBuffer.length() > 0) {
        processCommand(inputBuffer);
        inputBuffer = "";
      }
    } else {
      inputBuffer += c;
    }
  }
  
  delay(10);  // Small delay to prevent watchdog timeout
}

// ═══════════════════════════════════════════════════════════════
// COMMAND PROCESSOR
// ═══════════════════════════════════════════════════════════════
void processCommand(String cmd) {
  cmd.trim();
  cmd.toUpperCase();
  
  if (!sensorReady && cmd != "STATUS") {
    Serial.println("SENSOR_ERROR");
    return;
  }
  
  if (cmd == "SCAN") {
    // ── Fingerprint scan and match ──────────────────
    scanFingerprint();
    
  } else if (cmd.startsWith("ENROLL:")) {
    // ── Enroll new fingerprint ──────────────────────
    int id = cmd.substring(7).toInt();
    if (id >= 1 && id <= 127) {
      enrollFingerprint(id);
    } else {
      Serial.println("ENROLL_FAIL");
    }
    
  } else if (cmd.startsWith("DELETE:")) {
    // ── Delete specific fingerprint ─────────────────
    int id = cmd.substring(7).toInt();
    deleteFingerprint(id);
    
  } else if (cmd == "COUNT") {
    // ── Get stored template count ───────────────────
    finger.getTemplateCount();
    Serial.print("TEMPLATE_COUNT:");
    Serial.println(finger.templateCount);
    
  } else if (cmd == "STATUS") {
    // ── Sensor status check ─────────────────────────
    if (sensorReady) {
      finger.getTemplateCount();
      Serial.print("STATUS_OK:");
      Serial.println(finger.templateCount);
    } else {
      Serial.println("SENSOR_ERROR");
    }
    
  } else if (cmd == "EMPTY") {
    // ── Delete all fingerprints ─────────────────────
    if (finger.emptyDatabase() == FINGERPRINT_OK) {
      Serial.println("EMPTY_OK");
    } else {
      Serial.println("EMPTY_FAIL");
    }
    
  } else {
    Serial.println("UNKNOWN_CMD");
  }
}

// ═══════════════════════════════════════════════════════════════
// FINGERPRINT SCAN & MATCH
// ═══════════════════════════════════════════════════════════════
void scanFingerprint() {
  Serial.println("PLACE_FINGER");
  digitalWrite(LED_PIN, HIGH);
  
  // Wait for finger to be placed (max 10 seconds)
  unsigned long startTime = millis();
  int result = -1;
  
  while (millis() - startTime < 10000) {
    result = finger.getImage();
    if (result == FINGERPRINT_OK) {
      break;  // Finger detected
    }
    if (result == FINGERPRINT_NOFINGER) {
      delay(100);
      continue;
    }
    // Communication or imaging error
    Serial.println("SENSOR_ERROR");
    digitalWrite(LED_PIN, LOW);
    return;
  }
  
  if (result != FINGERPRINT_OK) {
    Serial.println("NO_MATCH");  // Timeout, no finger placed
    digitalWrite(LED_PIN, LOW);
    return;
  }
  
  // Convert image to feature template (stored in char buffer 1)
  result = finger.image2Tz();
  if (result != FINGERPRINT_OK) {
    Serial.println("NO_MATCH");
    digitalWrite(LED_PIN, LOW);
    return;
  }
  
  // Search for matching template in sensor database
  result = finger.fingerSearch();
  
  if (result == FINGERPRINT_OK) {
    // ── Match found ─────────────────────────────────
    Serial.print("MATCH:");
    Serial.println(finger.fingerID);
    
    // Blink LED to indicate success
    blinkLED(2, 100);
  } else if (result == FINGERPRINT_NOTFOUND) {
    Serial.println("NO_MATCH");
    blinkLED(5, 50);  // Rapid blink for failure
  } else {
    Serial.println("SENSOR_ERROR");
  }
  
  digitalWrite(LED_PIN, LOW);
}

// ═══════════════════════════════════════════════════════════════
// FINGERPRINT ENROLLMENT
// ═══════════════════════════════════════════════════════════════
void enrollFingerprint(int id) {
  int result;
  
  // ── Step 1: First image capture ───────────────────
  Serial.println("PLACE_FINGER");
  digitalWrite(LED_PIN, HIGH);
  
  // Wait for finger
  unsigned long startTime = millis();
  while (millis() - startTime < 15000) {
    result = finger.getImage();
    if (result == FINGERPRINT_OK) break;
    if (result == FINGERPRINT_NOFINGER) {
      delay(100);
      continue;
    }
    Serial.println("ENROLL_FAIL");
    digitalWrite(LED_PIN, LOW);
    return;
  }
  
  if (result != FINGERPRINT_OK) {
    Serial.println("ENROLL_FAIL");
    digitalWrite(LED_PIN, LOW);
    return;
  }
  
  // Convert to template (buffer 1)
  result = finger.image2Tz(1);
  if (result != FINGERPRINT_OK) {
    Serial.println("ENROLL_FAIL");
    digitalWrite(LED_PIN, LOW);
    return;
  }
  
  // ── Step 2: Remove finger ─────────────────────────
  Serial.println("REMOVE_FINGER");
  delay(1000);
  
  // Wait for finger to be removed
  startTime = millis();
  while (millis() - startTime < 5000) {
    if (finger.getImage() == FINGERPRINT_NOFINGER) break;
    delay(100);
  }
  
  // ── Step 3: Second image capture ──────────────────
  Serial.println("PLACE_AGAIN");
  
  startTime = millis();
  while (millis() - startTime < 15000) {
    result = finger.getImage();
    if (result == FINGERPRINT_OK) break;
    if (result == FINGERPRINT_NOFINGER) {
      delay(100);
      continue;
    }
    Serial.println("ENROLL_FAIL");
    digitalWrite(LED_PIN, LOW);
    return;
  }
  
  if (result != FINGERPRINT_OK) {
    Serial.println("ENROLL_FAIL");
    digitalWrite(LED_PIN, LOW);
    return;
  }
  
  // Convert to template (buffer 2)
  result = finger.image2Tz(2);
  if (result != FINGERPRINT_OK) {
    Serial.println("ENROLL_FAIL");
    digitalWrite(LED_PIN, LOW);
    return;
  }
  
  // ── Step 4: Create model from both templates ──────
  result = finger.createModel();
  if (result != FINGERPRINT_OK) {
    Serial.println("ENROLL_FAIL");
    digitalWrite(LED_PIN, LOW);
    return;
  }
  
  // ── Step 5: Store model in sensor flash ───────────
  result = finger.storeModel(id);
  if (result == FINGERPRINT_OK) {
    Serial.print("ENROLL_OK:");
    Serial.println(id);
    blinkLED(3, 200);  // Success indication
  } else {
    Serial.println("ENROLL_FAIL");
  }
  
  digitalWrite(LED_PIN, LOW);
}

// ═══════════════════════════════════════════════════════════════
// DELETE FINGERPRINT
// ═══════════════════════════════════════════════════════════════
void deleteFingerprint(int id) {
  if (finger.deleteModel(id) == FINGERPRINT_OK) {
    Serial.print("DELETE_OK:");
    Serial.println(id);
  } else {
    Serial.println("DELETE_FAIL");
  }
}

// ═══════════════════════════════════════════════════════════════
// UTILITY FUNCTIONS
// ═══════════════════════════════════════════════════════════════
void blinkLED(int times, int delayMs) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(delayMs);
    digitalWrite(LED_PIN, LOW);
    delay(delayMs);
  }
}
