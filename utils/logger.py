"""
Logging utility for the Biometric Authentication System.
Provides structured, color-coded console output and persistent file logging.
"""

import os
import logging
from datetime import datetime
from colorama import init, Fore, Style

import config

# Initialize colorama for Windows terminal color support
init(autoreset=True)


class SystemLogger:
    """
    Centralized logger that writes to both console (color-coded)
    and a rotating log file for audit trails.
    """

    def __init__(self, name: str = "BiometricAuth"):
        self.name = name
        self._setup_file_logger()

    def _setup_file_logger(self):
        """Configure file-based logging with timestamped log files."""
        log_filename = datetime.now().strftime("auth_%Y%m%d.log")
        log_path = os.path.join(config.LOG_DIR, log_filename)

        self.file_logger = logging.getLogger(self.name)
        self.file_logger.setLevel(logging.DEBUG)

        # Prevent duplicate handlers on re-initialization
        if not self.file_logger.handlers:
            handler = logging.FileHandler(log_path, encoding="utf-8")
            handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)-8s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            handler.setFormatter(formatter)
            self.file_logger.addHandler(handler)

    def _timestamp(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    def info(self, message: str):
        """Log informational message (cyan)."""
        print(f"{Fore.CYAN}[{self._timestamp()}] [INFO]    {message}{Style.RESET_ALL}")
        self.file_logger.info(message)

    def success(self, message: str):
        """Log success message (green)."""
        print(f"{Fore.GREEN}[{self._timestamp()}] [SUCCESS] {message}{Style.RESET_ALL}")
        self.file_logger.info(f"SUCCESS: {message}")

    def warning(self, message: str):
        """Log warning message (yellow)."""
        print(f"{Fore.YELLOW}[{self._timestamp()}] [WARNING] {message}{Style.RESET_ALL}")
        self.file_logger.warning(message)

    def error(self, message: str):
        """Log error message (red)."""
        print(f"{Fore.RED}[{self._timestamp()}] [ERROR]   {message}{Style.RESET_ALL}")
        self.file_logger.error(message)

    def auth_event(self, user_id: str, event: str, result: str):
        """
        Log an authentication event for the audit trail.
        
        Args:
            user_id: The user being authenticated
            event: Type of event (face_scan, fingerprint, pin_entry, etc.)
            result: Result of the event (success, failure, timeout, etc.)
        """
        msg = f"AUTH_EVENT | user={user_id} | event={event} | result={result}"
        if result in ("success", "granted"):
            self.success(msg)
        elif result in ("failure", "denied", "mismatch"):
            self.error(msg)
        else:
            self.info(msg)

    def system_event(self, event: str, details: str = ""):
        """Log a system-level event (startup, shutdown, config change, etc.)."""
        msg = f"SYSTEM | {event}"
        if details:
            msg += f" | {details}"
        self.info(msg)


# Global logger instance
logger = SystemLogger()
