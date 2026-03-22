"""Security utilities — JWT tokens and password hashing.

Uses passlib for bcrypt hashing and python-jose for JWT.
Falls back gracefully if dependencies aren't installed.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# JWT Configuration — empty env must fall back (Compose may pass JWT_SECRET=)
_raw_jwt = (os.environ.get("JWT_SECRET") or "").strip()
JWT_SECRET = _raw_jwt if _raw_jwt else secrets.token_hex(32)
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def hash_password(password: str) -> str:
    """Hash a password using bcrypt directly or SHA256 fallback."""
    try:
        import bcrypt
        pwd = password.encode("utf-8")[:72]  # bcrypt max 72 bytes
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(pwd, salt).decode("utf-8")
    except ImportError:
        logger.warning("bcrypt not installed, using SHA256 fallback")
        salt = secrets.token_hex(16)
        hashed = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
        return f"sha256:{salt}:{hashed}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    try:
        import bcrypt
        if hashed_password.startswith("sha256:"):
            _, salt, expected = hashed_password.split(":", 2)
            actual = hashlib.sha256(f"{salt}:{plain_password}".encode()).hexdigest()
            return hmac.compare_digest(actual, expected)
        pwd = plain_password.encode("utf-8")[:72]
        return bcrypt.checkpw(pwd, hashed_password.encode("utf-8"))
    except ImportError:
        if hashed_password.startswith("sha256:"):
            _, salt, expected = hashed_password.split(":", 2)
            actual = hashlib.sha256(f"{salt}:{plain_password}".encode()).hexdigest()
            return hmac.compare_digest(actual, expected)
        return False


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    try:
        from jose import jwt
    except ImportError:
        logger.warning("python-jose not installed, using simple token fallback")
        return _simple_token(data)

    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(data: dict[str, Any]) -> str:
    """Create a JWT refresh token."""
    try:
        from jose import jwt
    except ImportError:
        return _simple_token(data)

    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict[str, Any] | None:
    """Verify and decode a JWT token. Returns payload or None."""
    try:
        from jose import jwt, JWTError
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except ImportError:
        return _verify_simple_token(token)
    except Exception:
        return None


def _simple_token(data: dict[str, Any]) -> str:
    """Fallback token when jose is not installed."""
    import json
    import base64
    payload = json.dumps(data).encode()
    sig = hmac.new(JWT_SECRET.encode(), payload, hashlib.sha256).hexdigest()[:16]
    return base64.urlsafe_b64encode(payload).decode() + "." + sig


def _verify_simple_token(token: str) -> dict[str, Any] | None:
    """Verify fallback token."""
    import json
    import base64
    try:
        parts = token.rsplit(".", 1)
        if len(parts) != 2:
            return None
        payload_b64, sig = parts
        payload = base64.urlsafe_b64decode(payload_b64)
        expected_sig = hmac.new(JWT_SECRET.encode(), payload, hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected_sig):
            return None
        return json.loads(payload)
    except Exception:
        return None
