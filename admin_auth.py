# admin_auth.py
#
# Administrator authentication for the permanent LAN admin page.
#
# - Password stored as salted SHA-256 hash in admin_auth.json
# - Session tokens kept in memory
# - Failed-attempt lockout and inactivity timeout

import hashlib
import json
import os
import time

try:
    import ubinascii
except ImportError:
    ubinascii = None


AUTH_FILE = "admin_auth.json"
DEFAULT_PASSWORD = "admin1234"
SESSION_COOKIE = "esaatech_session"
SESSION_TIMEOUT_MS = 10 * 60 * 1000
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MS = 60 * 1000


def _now_ms():
    if hasattr(time, "ticks_ms"):
        return time.ticks_ms()

    return int(time.time() * 1000)


def _ticks_diff(a, b):
    if hasattr(time, "ticks_diff"):
        return time.ticks_diff(a, b)

    return a - b


def _ticks_add(a, offset):
    if hasattr(time, "ticks_add"):
        return time.ticks_add(a, offset)

    return a + offset


class AdminAuth:
    def __init__(self):
        self.sessions = {}
        self.failed_attempts = 0
        self.lockout_until_ms = 0
        self._ensure_password_file()

    # -------------------------------------------------

    def _to_hex(self, data):
        if ubinascii is not None:
            return ubinascii.hexlify(data).decode()

        return "".join("{:02x}".format(byte) for byte in data)

    # -------------------------------------------------

    def _random_hex(self, size=16):
        return self._to_hex(os.urandom(size))

    # -------------------------------------------------

    def _hash_password(self, password, salt):
        digest = hashlib.sha256(
            (salt + ":" + password).encode("utf-8")
        ).digest()
        return self._to_hex(digest)

    # -------------------------------------------------

    def _ensure_password_file(self):
        try:
            with open(AUTH_FILE, "r") as file:
                config = json.load(file)

            if config.get("salt") and config.get("password_hash"):
                return
        except (OSError, ValueError):
            pass

        self.set_password(DEFAULT_PASSWORD)
        print(
            "Admin password initialized to default:",
            DEFAULT_PASSWORD
        )

    # -------------------------------------------------

    def _load_auth_config(self):
        with open(AUTH_FILE, "r") as file:
            return json.load(file)

    # -------------------------------------------------

    def set_password(self, password):
        password = password or ""

        if len(password) < 4:
            raise ValueError(
                "Password must be at least 4 characters."
            )

        salt = self._random_hex(8)
        password_hash = self._hash_password(password, salt)

        config = {
            "salt": salt,
            "password_hash": password_hash
        }

        with open(AUTH_FILE, "w") as file:
            json.dump(config, file)

        # Force re-login after a password change.
        self.sessions = {}

        return True

    # -------------------------------------------------

    def verify_password(self, password):
        config = self._load_auth_config()
        salt = config.get("salt", "")
        expected = config.get("password_hash", "")
        actual = self._hash_password(password or "", salt)
        return actual == expected

    # -------------------------------------------------

    def is_locked_out(self):
        now = _now_ms()

        if self.lockout_until_ms == 0:
            return False

        if _ticks_diff(now, self.lockout_until_ms) >= 0:
            self.lockout_until_ms = 0
            self.failed_attempts = 0
            return False

        return True

    # -------------------------------------------------

    def lockout_seconds_remaining(self):
        if not self.is_locked_out():
            return 0

        remaining = _ticks_diff(
            self.lockout_until_ms,
            _now_ms()
        )

        if remaining <= 0:
            return 0

        return (remaining + 999) // 1000

    # -------------------------------------------------

    def record_failed_login(self):
        self.failed_attempts += 1

        if self.failed_attempts >= MAX_FAILED_ATTEMPTS:
            self.lockout_until_ms = _ticks_add(
                _now_ms(),
                LOCKOUT_MS
            )
            self.failed_attempts = 0
            return True

        return False

    # -------------------------------------------------

    def clear_failed_logins(self):
        self.failed_attempts = 0
        self.lockout_until_ms = 0

    # -------------------------------------------------

    def create_session(self):
        token = self._random_hex(16)
        self.sessions[token] = _now_ms()
        self.clear_failed_logins()
        return token

    # -------------------------------------------------

    def destroy_session(self, token):
        if token in self.sessions:
            del self.sessions[token]

    # -------------------------------------------------

    def validate_session(self, token):
        if not token:
            return False

        last_seen = self.sessions.get(token)

        if last_seen is None:
            return False

        age = _ticks_diff(_now_ms(), last_seen)

        if age > SESSION_TIMEOUT_MS:
            del self.sessions[token]
            return False

        self.sessions[token] = _now_ms()
        return True

    # -------------------------------------------------

    def login(self, password):
        """
        Returns (ok, message, token_or_none).
        """

        if self.is_locked_out():
            seconds = self.lockout_seconds_remaining()
            return (
                False,
                "Too many failed attempts. Try again in {} seconds.".format(
                    seconds
                ),
                None
            )

        if self.verify_password(password):
            token = self.create_session()
            return True, "Login successful.", token

        locked = self.record_failed_login()

        if locked:
            return (
                False,
                "Too many failed attempts. Try again in 60 seconds.",
                None
            )

        remaining = MAX_FAILED_ATTEMPTS - self.failed_attempts

        return (
            False,
            "Incorrect password. {} attempt(s) remaining.".format(
                remaining
            ),
            None
        )


def get_cookie(request, name):
    """
    Reads one cookie value from a raw HTTP request string.
    """

    if not request:
        return None

    header_part = request.split("\r\n\r\n", 1)[0]

    for line in header_part.split("\r\n"):
        if not line.lower().startswith("cookie:"):
            continue

        cookie_header = line.split(":", 1)[1].strip()

        for part in cookie_header.split(";"):
            item = part.strip()

            if "=" not in item:
                continue

            key, value = item.split("=", 1)

            if key.strip() == name:
                return value.strip()

    return None


def session_cookie_header(token):
    return (
        "Set-Cookie: {}={}; Path=/; HttpOnly; SameSite=Lax".format(
            SESSION_COOKIE,
            token
        )
    )


def clear_session_cookie_header():
    return (
        "Set-Cookie: {}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax".format(
            SESSION_COOKIE
        )
    )
