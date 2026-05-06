"""Security utility unit tests."""
from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from jose import JWTError


@pytest.mark.unit
class TestPasswordHashing:
    def test_hash_password_returns_different_from_plain(self):
        from app.core.security import hash_password
        plain = "MySecurePassword123!"
        hashed = hash_password(plain)
        assert hashed != plain

    def test_verify_password_correct(self):
        from app.core.security import hash_password, verify_password
        plain = "MySecurePassword123!"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_password_wrong(self):
        from app.core.security import hash_password, verify_password
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_hash_is_deterministic_per_call(self):
        from app.core.security import hash_password
        # Two calls with same input produce different hashes (bcrypt uses random salt)
        h1 = hash_password("password")
        h2 = hash_password("password")
        assert h1 != h2


@pytest.mark.unit
class TestJWT:
    def test_create_and_decode_token(self):
        from app.core.security import create_access_token, decode_access_token
        user_id = uuid.uuid4()
        token = create_access_token(user_id)
        decoded_id = decode_access_token(token)
        assert decoded_id == user_id

    def test_expired_token_raises(self):
        from app.core.security import create_access_token, decode_access_token
        token = create_access_token(uuid.uuid4(), expires_delta=timedelta(seconds=-1))
        with pytest.raises(JWTError):
            decode_access_token(token)

    def test_tampered_token_raises(self):
        from app.core.security import decode_access_token
        with pytest.raises(JWTError):
            decode_access_token("eyJhbGciOiJIUzI1NiJ9.tampered.signature")

    def test_token_has_correct_subject(self):
        from app.core.security import create_access_token
        from jose import jwt, ALGORITHMS
        from app.config import settings

        user_id = uuid.uuid4()
        token = create_access_token(user_id)
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"
