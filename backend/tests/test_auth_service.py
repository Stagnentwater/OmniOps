"""Unit tests for AuthService password cryptography and token validation."""

from __future__ import annotations

import unittest
from datetime import timedelta

from services.auth_service import (
    AuthService,
    ExpiredTokenError,
    InvalidTokenError,
)


class TestAuthService(unittest.TestCase):
    """Test suite for password hashing and HMAC-signed JWT token management."""

    def setUp(self) -> None:
        self.auth_service = AuthService(
            secret_key="test-secret-key-for-unit-testing-32bytes",
            algorithm="HS256",
            access_token_expire_minutes=60,
        )

    # ── Password Hashing Tests ──────────────────────────────────────────────

    def test_hash_password_format(self) -> None:
        """Verify hash format matches pbkdf2_sha256$<iterations>$<salt>$<hash>."""
        pwd_hash = self.auth_service.hash_password("RefineryPassword123!")
        parts = pwd_hash.split("$")
        self.assertEqual(len(parts), 4)
        self.assertEqual(parts[0], "pbkdf2_sha256")
        self.assertEqual(parts[1], "600000")
        self.assertEqual(len(parts[2]), 32)  # 16 bytes hex-encoded = 32 chars
        self.assertEqual(len(parts[3]), 64)  # 32 bytes SHA-256 hex = 64 chars

    def test_hash_password_random_salt(self) -> None:
        """Hashing the same password twice must produce different hashes due to unique salts."""
        h1 = self.auth_service.hash_password("Secret123")
        h2 = self.auth_service.hash_password("Secret123")
        self.assertNotEqual(h1, h2)

    def test_hash_empty_password_raises(self) -> None:
        """Hashing an empty password raises ValueError."""
        with self.assertRaises(ValueError):
            self.auth_service.hash_password("")

    def test_verify_password_correct(self) -> None:
        """Correct password verifies successfully."""
        pwd_hash = self.auth_service.hash_password("ProcessSafety2026")
        self.assertTrue(self.auth_service.verify_password("ProcessSafety2026", pwd_hash))

    def test_verify_password_incorrect(self) -> None:
        """Incorrect password fails verification."""
        pwd_hash = self.auth_service.hash_password("ProcessSafety2026")
        self.assertFalse(self.auth_service.verify_password("WrongPassword", pwd_hash))
        self.assertFalse(self.auth_service.verify_password("", pwd_hash))

    def test_verify_password_malformed_hash(self) -> None:
        """Malformed or corrupted hashes return False without crashing."""
        self.assertFalse(self.auth_service.verify_password("Pass123", "corrupted$hash"))
        self.assertFalse(self.auth_service.verify_password("Pass123", "plain_text_hash"))
        self.assertFalse(self.auth_service.verify_password("Pass123", ""))

    # ── Token Management Tests ──────────────────────────────────────────────

    def test_create_and_decode_token(self) -> None:
        """Create a token and decode claims successfully."""
        token = self.auth_service.create_access_token(
            user_id="usr_alex_chen",
            email="alex.chen@refinery.internal",
            extra_claims={"role": "Graduate Trainee"},
        )
        self.assertTrue(isinstance(token, str))
        self.assertEqual(token.count("."), 2)

        claims = self.auth_service.decode_access_token(token)
        self.assertEqual(claims["sub"], "usr_alex_chen")
        self.assertEqual(claims["email"], "alex.chen@refinery.internal")
        self.assertEqual(claims["role"], "Graduate Trainee")
        self.assertIn("iat", claims)
        self.assertIn("exp", claims)
        self.assertGreater(claims["exp"], claims["iat"])

    def test_decode_tampered_token_signature(self) -> None:
        """Altering any segment of the token causes InvalidTokenError."""
        token = self.auth_service.create_access_token(
            user_id="usr_alex",
            email="alex@refinery.internal",
        )
        header_b64, payload_b64, sig_b64 = token.split(".")
        # Tamper signature
        tampered_sig = sig_b64[:-2] + "xx"
        tampered_token = f"{header_b64}.{payload_b64}.{tampered_sig}"

        with self.assertRaises(InvalidTokenError):
            self.auth_service.decode_access_token(tampered_token)

    def test_decode_tampered_payload(self) -> None:
        """Altering the payload without updating signature causes InvalidTokenError."""
        token = self.auth_service.create_access_token(
            user_id="usr_alex",
            email="alex@refinery.internal",
        )
        header_b64, _, sig_b64 = token.split(".")
        tampered_payload_b64 = "eyJzdWIiOiAidXNyX2hhY2tlciJ9"  # {"sub": "usr_hacker"}
        tampered_token = f"{header_b64}.{tampered_payload_b64}.{sig_b64}"

        with self.assertRaises(InvalidTokenError):
            self.auth_service.decode_access_token(tampered_token)

    def test_decode_expired_token(self) -> None:
        """Expired token raises ExpiredTokenError."""
        expired_token = self.auth_service.create_access_token(
            user_id="usr_expired",
            email="expired@refinery.internal",
            expires_delta=timedelta(seconds=-10),  # expired 10 seconds ago
        )
        with self.assertRaises(ExpiredTokenError):
            self.auth_service.decode_access_token(expired_token)

    def test_decode_malformed_token_structure(self) -> None:
        """Malformed token structure raises InvalidTokenError."""
        with self.assertRaises(InvalidTokenError):
            self.auth_service.decode_access_token("not-a-token")
        with self.assertRaises(InvalidTokenError):
            self.auth_service.decode_access_token("part1.part2")
        with self.assertRaises(InvalidTokenError):
            self.auth_service.decode_access_token("")


if __name__ == "__main__":
    unittest.main()
