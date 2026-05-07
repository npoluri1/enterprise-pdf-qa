"""JWT auth utilities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

import bcrypt
from jose import JWTError, jwt

from app.config import settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(subject: uuid.UUID, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {"sub": str(subject), "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID:
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise JWTError("invalid or missing sub")
    return uuid.UUID(sub)
