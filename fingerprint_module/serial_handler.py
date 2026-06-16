"""
Serial Handler - Communication layer between Python and ESP32.
Reads fingerprint match results from ESP32 via USB serial.
Handles connection management, reconnection, and data parsing.
"""

import serial
import serial.tools.list_ports
import time
import threading
from typing import Optional, Tuple, Callable

import config
from utils.logger import logger


class SerialHandler:
    """
    Manages serial communication with ESP32 for fingerprint data.

    Protocol (ESP32 → Python):
        MATCH:<fingerprint_id>     → Fingerprint matched, returns ID
        NO_MATCH                    → No fingerprint match
        ENROLL_OK:<fingerprint_id>  → Enrollment successful
        ENROLL_FAIL                 → Enrollment failed
        SENSOR_ERROR                → Sensor communication error
        READY                       → ESP32 ready for commands

    Protocol (Python → ESP32):
        SCAN                        → Request fingerprint scan
        ENROLL:<fingerprint_id>     → Start enrollment for given ID
        STATUS                      → Request sensor status
    """

    def __init__(self, port: str = None, baud_rate: int = None):
        self.port = port or config.SERIAL_PORT
        self.baud_rate = baud_rate or config.SERIAL_BAUD_RATE
        self.connection: Optional[serial.Serial] = None
        self.is_connected = False
        self._listener_thread: Optional[threading.Thread] = None
        self._listening = False
        self._callback: Optional[Callable] = None

    def connect(self) -> bool:
        """
        Establish serial connection with ESP32.

        Returns:
            True if connection was successful
        """
        if config.SIMULATION_MODE:
            logger.info("SIMULATION MODE: Skipping serial connection")
            self.is_connected = True
            return True

        # If configured port fails, try to auto-detect an ESP32
        ports_to_try = [self.port] + self._find_esp32_ports(exclude=self.port)

        for port in ports_to_try:
            try:
                self.connection = serial.Serial(
                    port=port,
                    baudrate=self.baud_rate,
                    timeout=config.SERIAL_TIMEOUT,
                    write_timeout=config.SERIAL_TIMEOUT
                )
                
                # The ESP32's setup() in fingerprint_auth.ino tests multiple baud rates
                # with 1000ms delays between them. We must wait long enough for it
                # to completely finish booting before sending any commands.
                logger.info("Waiting 3.5s for ESP32 and R307S to initialize...")
                time.sleep(3.5)

                self.port = port
                self.is_connected = True
                logger.success(f"Serial connected: {port} @ {self.baud_rate}")

                # Flush any startup messages (INIT, READY, READY_AT, etc) from the buffer
                self.connection.reset_input_buffer()
                return True

            except serial.SerialException as e:
                if port == self.port:
                    logger.warning(f"Serial failed on {port}: {e}")
                else:
                    logger.info(f"Auto-detect: {port} unavailable, trying next...")

        logger.error(f"Could not connect to ESP32. Run 'python main.py --list-ports' to see available ports.")
        self.is_connected = False
        return False

    @staticmethod
    def _find_esp32_ports(exclude: str = None) -> list:
        """Return a list of ports that look like ESP32 USB-serial adapters."""
        esp32_keywords = ("cp210", "ch340", "ch341", "ftdi", "esp32", "uart", "usb serial")
        candidates = []
        for port in serial.tools.list_ports.comports():
            if port.device == exclude:
                continue
            desc = (port.description or "").lower()
            mfr = (port.manufacturer or "").lower()
            if any(kw in desc or kw in mfr for kw in esp32_keywords):
                candidates.append(port.device)
        return candidates

    def disconnect(self):
        """Close the serial connection."""
        self._listening = False
        if self.connection and self.connection.is_open:
            self.connection.close()
        self.is_connected = False
        logger.info("Serial connection closed")

    @staticmethod
    def list_available_ports() -> list:
        """List all available serial ports on the system."""
        ports = serial.tools.list_ports.comports()
        port_list = []
        for port in ports:
            port_list.append({
                "device": port.device,
                "description": port.description,
                "manufacturer": port.manufacturer or "Unknown"
            })
            logger.info(f"Found port: {port.device} - {port.description}")
        return port_list

    def send_command(self, command: str) -> bool:
        """
        Send a command to the ESP32.

        Args:
            command: Command string (e.g., "SCAN", "ENROLL:1")

        Returns:
            True if command was sent successfully
        """
        if config.SIMULATION_MODE:
            logger.info(f"SIMULATION: Sent command → {command}")
            return True

        if not self.is_connected or not self.connection:
            logger.error("Cannot send command: not connected")
            return False

        try:
            self.connection.write(f"{command}\n".encode())
            self.connection.flush()
            logger.info(f"Sent to ESP32: {command}")
            return True
        except serial.SerialException as e:
            logger.error(f"Failed to send command: {e}")
            return False

    def read_response(self, timeout: float = None) -> Optional[str]:
        """
        Read a single line response from ESP32.

        Args:
            timeout: Override default timeout (seconds)

        Returns:
            Response string or None if timeout/error
        """
        if config.SIMULATION_MODE:
            return self._simulate_response()

        if not self.is_connected or not self.connection:
            return None

        try:
            if timeout:
                self.connection.timeout = timeout

            line = self.connection.readline().decode().strip()

            if timeout:
                self.connection.timeout = config.SERIAL_TIMEOUT

            if line:
                logger.info(f"Received from ESP32: {line}")
                return line
            return None

        except serial.SerialException as e:
            logger.error(f"Serial read error: {e}")
            return None
        except UnicodeDecodeError:
            logger.warning("Received non-UTF8 data from ESP32")
            return None

    def request_fingerprint_scan(self, timeout: float = None,
                                 expected_user_id: str = None) -> Tuple[
            Optional[int], bool]:
        """
        Request a fingerprint scan from ESP32 and wait for result.

        Args:
            timeout: Max seconds to wait for scan result
            expected_user_id: The user_id already identified by face
                               recognition. Only used in SIMULATION_MODE to
                               simulate a correct match for whoever is being
                               tested (instead of hardcoding a single user).

        Returns:
            Tuple of (fingerprint_id or None, is_match: bool)
        """
        timeout = timeout or config.FINGERPRINT_TIMEOUT

        if config.SIMULATION_MODE:
            return self._simulate_fingerprint_scan(expected_user_id)

        # Send scan command
        if not self.send_command("SCAN"):
            return None, False

        # Wait for response
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = self.read_response(timeout=1.0)
            if response:
                if response == "PLACE_FINGER":
                    logger.info("Sensor is ready. Please place your finger.")
                    continue
                    
                result = self._parse_match_response(response)
                if result != (None, False) or response == "NO_MATCH" or response == "SENSOR_ERROR":
                    return result
            time.sleep(0.1)

        logger.warning("Fingerprint scan timed out")
        return None, False

    def request_enrollment(self, fingerprint_id: int,
                           timeout: float = 30) -> bool:
        """
        Request fingerprint enrollment on ESP32.

        Args:
            fingerprint_id: ID to assign (1-127 for R307S)
            timeout: Max seconds to wait for enrollment

        Returns:
            True if enrollment was successful
        """
        if config.SIMULATION_MODE:
            logger.info(f"SIMULATION: Enrolled fingerprint ID {fingerprint_id}")
            time.sleep(config.SIMULATED_FINGERPRINT_DELAY)
            return True

        if not self.send_command(f"ENROLL:{fingerprint_id}"):
            return False

        start_time = time.time()
        while time.time() - start_time < timeout:
            response = self.read_response(timeout=1.0)
            if response:
                if response.startswith("ENROLL_OK"):
                    logger.success(
                        f"Fingerprint enrolled: ID {fingerprint_id}")
                    return True
                elif response == "ENROLL_FAIL":
                    logger.error("Fingerprint enrollment failed")
                    return False
                elif response == "PLACE_FINGER":
                    logger.info("Place your finger on the sensor...")
                elif response == "REMOVE_FINGER":
                    logger.info("Remove your finger...")
                elif response == "PLACE_AGAIN":
                    logger.info("Place the same finger again...")
            time.sleep(0.1)

        logger.warning("Enrollment timed out")
        return False

    @staticmethod
    def _parse_match_response(response: str) -> Tuple[Optional[int], bool]:
        """
        Parse a fingerprint match response from ESP32.

        Expected formats:
            MATCH:<id>  → (id, True)
            NO_MATCH    → (None, False)
        """
        if response.startswith("MATCH:"):
            try:
                fp_id = int(response.split(":")[1])
                return fp_id, True
            except (ValueError, IndexError):
                logger.error(f"Invalid MATCH response: {response}")
                return None, False
        elif response == "NO_MATCH":
            return None, False
        elif response == "SENSOR_ERROR":
            logger.error("Fingerprint sensor error reported by ESP32")
            return None, False
        else:
            logger.warning(f"Unexpected response: {response}")
            return None, False

    def _simulate_response(self) -> str:
        """Simulate a response for testing without hardware."""
        time.sleep(0.5)
        return "READY"

    def _simulate_fingerprint_scan(self, expected_user_id: str = None) -> Tuple[
            Optional[int], bool]:
        """
        Simulate a fingerprint scan for testing without hardware.

        Looks up the fingerprint_id already on file for the user that face
        recognition just identified, so simulation mode correctly matches
        whichever user is being tested instead of always returning a single
        hardcoded ID (which made every user except the first one fail
        identity fusion).
        """
        logger.info("SIMULATION: Simulating fingerprint scan...")
        time.sleep(config.SIMULATED_FINGERPRINT_DELAY)

        if expected_user_id:
            from database.db_manager import DatabaseManager
            user = DatabaseManager().get_user(expected_user_id)
            if user and user.get("fingerprint_id") is not None:
                simulated_id = user["fingerprint_id"]
                logger.info(
                    f"SIMULATION: Fingerprint matched → ID {simulated_id} "
                    f"(user: {expected_user_id})"
                )
                return simulated_id, True

            logger.warning(
                f"SIMULATION: No fingerprint_id on file for "
                f"{expected_user_id}"
            )
            return None, False

        # No user context available — fall back to the first known
        # fingerprint_id rather than a hardcoded "1" that may not exist.
        logger.warning(
            "SIMULATION: No expected_user_id provided; "
            "cannot simulate a meaningful match."
        )
        return None, False

    def start_listener(self, callback: Callable[[str], None]):
        """
        Start a background thread that continuously listens for
        ESP32 messages and calls the callback function.

        Args:
            callback: Function to call with each received message
        """
        self._callback = callback
        self._listening = True
        self._listener_thread = threading.Thread(
            target=self._listener_loop, daemon=True
        )
        self._listener_thread.start()
        logger.info("Serial listener started in background")

    def _listener_loop(self):
        """Background loop that reads serial data."""
        while self._listening:
            try:
                response = self.read_response(timeout=0.5)
                if response and self._callback:
                    self._callback(response)
            except Exception as e:
                logger.error(f"Listener error: {e}")
                time.sleep(1)

    def stop_listener(self):
        """Stop the background listener thread."""
        self._listening = False
        if self._listener_thread:
            self._listener_thread.join(timeout=3)
        logger.info("Serial listener stopped")
