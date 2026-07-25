"""
Auth unit tests — no live database, no HTTP requests.
Tests password hashing, JWT creation/decode, and schema validation only.
"""

import pytest
from jose import jwt

from api.routes.auth import (
    _create_token,
    _hash_password,
    _verify_password,
)
from core.config import settings


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        h = _hash_password("mypassword")
        assert h != "mypassword"

    def test_hash_starts_with_bcrypt_prefix(self):
        h = _hash_password("mypassword")
        assert h.startswith("$2b$") or h.startswith("$2a$")

    def test_correct_password_verifies(self):
        h = _hash_password("correct-horse-battery-staple")
        assert _verify_password("correct-horse-battery-staple", h) is True

    def test_wrong_password_fails(self):
        h = _hash_password("correct-horse-battery-staple")
        assert _verify_password("wrong-password", h) is False

    def test_empty_password_verifies_its_own_hash(self):
        h = _hash_password("")
        assert _verify_password("", h) is True

    def test_two_hashes_of_same_password_differ(self):
        # bcrypt uses random salt — same input should produce different outputs
        h1 = _hash_password("mypassword")
        h2 = _hash_password("mypassword")
        assert h1 != h2

    def test_both_hashes_verify_correctly(self):
        h1 = _hash_password("mypassword")
        h2 = _hash_password("mypassword")
        assert _verify_password("mypassword", h1)
        assert _verify_password("mypassword", h2)

    def test_special_characters_in_password(self):
        pwd = "P@ssw0rd!#$%^&*()"
        h = _hash_password(pwd)
        assert _verify_password(pwd, h) is True
        assert _verify_password("P@ssw0rd", h) is False


class TestJWTToken:
    def test_token_is_string(self):
        token = _create_token("user-abc-123")
        assert isinstance(token, str)
        assert len(token) > 20

    def test_token_decodes_to_correct_user_id(self):
        user_id = "user-abc-123"
        token = _create_token(user_id)
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == user_id

    def test_token_has_expiry(self):
        token = _create_token("user-xyz")
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        assert "exp" in payload

    def test_different_users_get_different_tokens(self):
        t1 = _create_token("user-001")
        t2 = _create_token("user-002")
        assert t1 != t2

    def test_token_with_wrong_secret_fails_decode(self):
        token = _create_token("user-abc")
        with pytest.raises(Exception):
            jwt.decode(token, "wrong-secret-key-minimum-32-chars-x", algorithms=[settings.jwt_algorithm])

    def test_two_tokens_for_same_user_decode_same_sub(self):
        user_id = "user-consistent"
        t1 = _create_token(user_id)
        t2 = _create_token(user_id)
        p1 = jwt.decode(t1, settings.secret_key, algorithms=[settings.jwt_algorithm])
        p2 = jwt.decode(t2, settings.secret_key, algorithms=[settings.jwt_algorithm])
        assert p1["sub"] == p2["sub"] == user_id


class TestRegisterRequestSchema:
    def test_valid_email_accepted(self):
        from api.routes.auth import RegisterRequest
        req = RegisterRequest(email="user@example.com", password="secret123")
        assert req.email == "user@example.com"

    def test_invalid_email_rejected(self):
        from pydantic import ValidationError
        from api.routes.auth import RegisterRequest
        with pytest.raises(ValidationError):
            RegisterRequest(email="not-an-email", password="secret123")

    def test_empty_email_rejected(self):
        from pydantic import ValidationError
        from api.routes.auth import RegisterRequest
        with pytest.raises(ValidationError):
            RegisterRequest(email="", password="secret123")
