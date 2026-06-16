"""
Database Manager for the Biometric Authentication System.
Handles all CRUD operations for user records using SQLite.
"""

import sqlite3
import hashlib
import os
import pickle
from typing import Optional, List, Dict, Any

import config
from utils.logger import logger


class DatabaseManager:
    """
    SQLite database manager for storing user credentials.
    Each user record contains: user_id, name, face_encoding,
    fingerprint_id, and hashed PIN.
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DATABASE_PATH
        self._initialize_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create and return a new database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_db(self):
        """Create the users table if it doesn't exist."""
        conn = self._get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id       TEXT PRIMARY KEY,
                    name          TEXT NOT NULL,
                    face_encoding BLOB,
                    fingerprint_id INTEGER UNIQUE,
                    pin_hash      TEXT NOT NULL,
                    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login    TIMESTAMP,
                    is_active     INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS auth_logs (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id       TEXT,
                    event_type    TEXT NOT NULL,
                    result        TEXT NOT NULL,
                    details       TEXT,
                    timestamp     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            conn.commit()
            logger.system_event("Database initialized", self.db_path)
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def _hash_pin(pin: str) -> str:
        """Hash a PIN using SHA-256 for secure storage."""
        return hashlib.sha256(pin.encode()).hexdigest()

    def add_user(self, user_id: str, name: str, fingerprint_id: int,
                 pin: str, face_encoding=None) -> bool:
        """
        Add a new user to the database.

        Args:
            user_id: Unique identifier (e.g., "USR001")
            name: Full name of the user
            fingerprint_id: ID stored in the R307S sensor (1-127)
            pin: 4-digit PIN (will be hashed before storage)
            face_encoding: numpy array of face encoding (128-dim)

        Returns:
            True if user was added successfully, False otherwise
        """
        conn = self._get_connection()
        try:
            encoding_blob = None
            if face_encoding is not None:
                encoding_blob = pickle.dumps(face_encoding)

            conn.execute(
                """INSERT INTO users (user_id, name, face_encoding,
                   fingerprint_id, pin_hash) VALUES (?, ?, ?, ?, ?)""",
                (user_id, name, encoding_blob, fingerprint_id,
                 self._hash_pin(pin))
            )
            conn.commit()
            logger.success(f"User added: {user_id} ({name})")
            return True
        except sqlite3.IntegrityError as e:
            logger.error(f"User already exists or duplicate fingerprint: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to add user: {e}")
            return False
        finally:
            conn.close()

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a user record by user_id."""
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ? AND is_active = 1",
                (user_id,)
            ).fetchone()
            if row:
                user = dict(row)
                if user["face_encoding"]:
                    user["face_encoding"] = pickle.loads(user["face_encoding"])
                return user
            return None
        finally:
            conn.close()

    def get_user_by_fingerprint(self, fingerprint_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a user record by fingerprint ID."""
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE fingerprint_id = ? AND is_active = 1",
                (fingerprint_id,)
            ).fetchone()
            if row:
                user = dict(row)
                if user["face_encoding"]:
                    user["face_encoding"] = pickle.loads(user["face_encoding"])
                return user
            return None
        finally:
            conn.close()

    def get_all_users(self) -> List[Dict[str, Any]]:
        """Retrieve all active users."""
        conn = self._get_connection()
        try:
            rows = conn.execute(
                "SELECT user_id, name, fingerprint_id, created_at FROM users WHERE is_active = 1"
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def verify_pin(self, user_id: str, pin: str) -> bool:
        """
        Verify a user's PIN against the stored hash.

        Returns:
            True if PIN matches, False otherwise
        """
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT pin_hash FROM users WHERE user_id = ? AND is_active = 1",
                (user_id,)
            ).fetchone()
            if row and row["pin_hash"] == self._hash_pin(pin):
                return True
            return False
        finally:
            conn.close()

    def update_face_encoding(self, user_id: str, face_encoding) -> bool:
        """Update the face encoding for an existing user."""
        conn = self._get_connection()
        try:
            encoding_blob = pickle.dumps(face_encoding)
            conn.execute(
                "UPDATE users SET face_encoding = ? WHERE user_id = ?",
                (encoding_blob, user_id)
            )
            conn.commit()
            logger.info(f"Face encoding updated for user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update face encoding: {e}")
            return False
        finally:
            conn.close()

    def update_last_login(self, user_id: str):
        """Update the last login timestamp for a user."""
        conn = self._get_connection()
        try:
            conn.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()
        finally:
            conn.close()

    def log_auth_event(self, user_id: str, event_type: str,
                       result: str, details: str = ""):
        """
        Log an authentication event to the audit table.

        Args:
            user_id: User involved (can be "UNKNOWN")
            event_type: face_recognition, fingerprint, pin_entry, session
            result: success, failure, timeout, denied
            details: Additional context
        """
        if not config.AUTH_LOG_ENABLED:
            return
        conn = self._get_connection()
        try:
            conn.execute(
                """INSERT INTO auth_logs (user_id, event_type, result, details)
                   VALUES (?, ?, ?, ?)""",
                (user_id, event_type, result, details)
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to log auth event: {e}")
        finally:
            conn.close()

    def get_auth_logs(self, user_id: str = None,
                      limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent authentication logs, optionally filtered by user."""
        conn = self._get_connection()
        try:
            if user_id:
                rows = conn.execute(
                    """SELECT * FROM auth_logs WHERE user_id = ?
                       ORDER BY timestamp DESC LIMIT ?""",
                    (user_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM auth_logs ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def delete_user(self, user_id: str) -> bool:
        """Soft-delete a user by marking them inactive."""
        conn = self._get_connection()
        try:
            conn.execute(
                "UPDATE users SET is_active = 0 WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()
            logger.info(f"User deactivated: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete user: {e}")
            return False
        finally:
            conn.close()
