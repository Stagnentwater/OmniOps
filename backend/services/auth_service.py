"""Authentication, password cryptography, and token validation service."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from config.settings import get_settings

logger = logging.getLogger(__name__)

# Default PBKDF2 iterations adhering to OWASP guidelines for SHA-256
_PBKDF2_ITERATIONS = 600_000
_SALT_BYTES = 16


class AuthError(Exception):
    """Base exception for authentication errors."""


class InvalidCredentialsError(AuthError):
    """Raised when authentication credentials do not match."""


class InvalidTokenError(AuthError):
    """Raised when a token signature or format is invalid."""


class ExpiredTokenError(AuthError):
    """Raised when a valid token has expired."""


def _base64url_encode(data: bytes) -> str:
    """Encode bytes to URL-safe base64 string without padding."""
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _base64url_decode(data: str) -> bytes:
    """Decode URL-safe base64 string with optional padding."""
    rem = len(data) % 4
    if rem > 0:
        data += "=" * (4 - rem)
    return base64.urlsafe_b64decode(data.encode("utf-8"))


class AuthService:
    """Service providing password hashing, verification, and HMAC-signed JWT token management."""

    def __init__(
        self,
        secret_key: str | None = None,
        algorithm: str = "HS256",
        access_token_expire_minutes: int | None = None,
    ) -> None:
        settings = get_settings()
        self._secret_key = secret_key or settings.auth.secret_key
        self._algorithm = algorithm or settings.auth.algorithm
        self._expire_minutes = (
            access_token_expire_minutes
            if access_token_expire_minutes is not None
            else settings.auth.access_token_expire_minutes
        )

    # ── Password Cryptography ──────────────────────────────────────────────

    def hash_password(self, password: str) -> str:
        """Hash a plaintext password using salted PBKDF2-HMAC-SHA256."""
        if not password:
            raise ValueError("Password cannot be empty")

        salt = secrets.token_bytes(_SALT_BYTES)
        derived = hashlib.pbkdf2_hmac(
            hash_name="sha256",
            password=password.encode("utf-8"),
            salt=salt,
            iterations=_PBKDF2_ITERATIONS,
        )
        return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${derived.hex()}"

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plaintext password against a stored PBKDF2 hash using constant-time comparison."""
        if not plain_password or not hashed_password:
            return False

        try:
            parts = hashed_password.split("$")
            if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
                return False

            iterations = int(parts[1])
            salt = bytes.fromhex(parts[2])
            expected_hash = bytes.fromhex(parts[3])

            actual_hash = hashlib.pbkdf2_hmac(
                hash_name="sha256",
                password=plain_password.encode("utf-8"),
                salt=salt,
                iterations=iterations,
            )
            return hmac.compare_digest(actual_hash, expected_hash)
        except Exception as e:
            logger.warning("Error during password verification: %s", e)
            return False

    # ── Token Generation & Decoding ────────────────────────────────────────

    def create_access_token(
        self,
        user_id: str,
        email: str,
        expires_delta: timedelta | None = None,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        """Generate a signed URL-safe JWT bearer token."""
        now = datetime.now(timezone.utc)
        delta = (
            expires_delta
            if expires_delta is not None
            else timedelta(minutes=self._expire_minutes)
        )
        expire = now + delta

        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": user_id,
            "email": email,
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
        }
        if extra_claims:
            payload.update(extra_claims)

        header_b64 = _base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        payload_b64 = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))

        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        signature = hmac.new(
            key=self._secret_key.encode("utf-8"),
            msg=signing_input,
            digestmod=hashlib.sha256,
        ).digest()
        signature_b64 = _base64url_encode(signature)

        return f"{header_b64}.{payload_b64}.{signature_b64}"

    def decode_access_token(self, token: str) -> dict[str, Any]:
        """Validate and decode a signed JWT bearer token.
        
        Raises:
            InvalidTokenError: If structure or cryptographic signature is invalid.
            ExpiredTokenError: If token has expired.
        """
        if not token or not isinstance(token, str):
            raise InvalidTokenError("Token is empty or invalid type")

        parts = token.strip().split(".")
        if len(parts) != 3:
            raise InvalidTokenError("Malformed token structure (must contain 3 segments)")

        header_b64, payload_b64, signature_b64 = parts

        # Verify signature
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_sig = hmac.new(
            key=self._secret_key.encode("utf-8"),
            msg=signing_input,
            digestmod=hashlib.sha256,
        ).digest()

        try:
            actual_sig = _base64url_decode(signature_b64)
        except Exception as e:
            raise InvalidTokenError("Invalid token signature encoding") from e

        if not hmac.compare_digest(actual_sig, expected_sig):
            raise InvalidTokenError("Invalid token cryptographic signature")

        # Decode payload
        try:
            payload_json = _base64url_decode(payload_b64).decode("utf-8")
            payload = json.loads(payload_json)
        except Exception as e:
            raise InvalidTokenError("Invalid token payload encoding") from e

        # Expiry check
        exp = payload.get("exp")
        if exp is None:
            raise InvalidTokenError("Token missing required expiration claim ('exp')")

        now_ts = int(datetime.now(timezone.utc).timestamp())
        if now_ts > int(exp):
            raise ExpiredTokenError("Token has expired")

        return payload


def get_auth_service() -> AuthService:
    """Dependency provider returning an initialized AuthService instance."""
    return AuthService()
