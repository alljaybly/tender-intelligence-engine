"""
Production authentication service for Tender Engine.

Phase 1 foundation:
- bcrypt password hashing
- JWT access + refresh tokens
- persistent auth sessions
- refresh token rotation
- remember-me sessions
- role helpers (owner/admin/customer)
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
from jose import JWTError, ExpiredSignatureError, jwt

logger = logging.getLogger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "tender-engine"
ACCESS_TOKEN_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "15"))
REFRESH_TOKEN_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_DAYS", "7"))
REMEMBER_ME_DAYS = int(os.getenv("JWT_REMEMBER_ME_DAYS", "30"))
MAX_FAILED_LOGIN_ATTEMPTS = int(os.getenv("MAX_FAILED_LOGIN_ATTEMPTS", "5"))
ACCOUNT_LOCK_MINUTES = int(os.getenv("ACCOUNT_LOCK_MINUTES", "15"))
OWNER_ROLE = "owner"
ADMIN_ROLE = "admin"
CUSTOMER_ROLE = "customer"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def hash_refresh_token(refresh_token: str) -> str:
    return hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def generate_session_id() -> str:
    return secrets.token_hex(24)


def password_is_strong(password: str) -> bool:
    if len(password) < 8:
        return False
    has_upper = any(ch.isupper() for ch in password)
    has_lower = any(ch.islower() for ch in password)
    has_digit = any(ch.isdigit() for ch in password)
    return has_upper and has_lower and has_digit


def create_access_token(*, user: dict[str, Any], session_id: str, impersonated_by: Optional[int] = None) -> tuple[str, datetime]:
    expires_at = utcnow() + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    payload: dict[str, Any] = {
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user.get("role", CUSTOMER_ROLE),
        "sid": session_id,
        "type": "access",
        "iss": JWT_ISSUER,
        "exp": expires_at,
        "iat": utcnow(),
    }
    if impersonated_by is not None:
        payload["impersonated_by"] = impersonated_by
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, expires_at


def create_refresh_token_payload(*, user_id: int, session_id: str, remember_me: bool, impersonated_by: Optional[int] = None) -> tuple[str, datetime]:
    expires_at = utcnow() + timedelta(days=REMEMBER_ME_DAYS if remember_me else REFRESH_TOKEN_DAYS)
    refresh_token = generate_refresh_token()
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "sid": session_id,
        "type": "refresh",
        "iss": JWT_ISSUER,
        "jti": generate_session_id(),
        "exp": expires_at,
        "iat": utcnow(),
    }
    if impersonated_by is not None:
        payload["impersonated_by"] = impersonated_by
    encoded = jwt.encode({**payload, "rt": refresh_token}, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded, expires_at


def decode_token(token: str, expected_type: str) -> Optional[dict[str, Any]]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], issuer=JWT_ISSUER)
        if payload.get("type") != expected_type:
            logger.warning("[AUTH] JWT type mismatch: expected=%s, got=%s", expected_type, payload.get("type"))
            return None
        return payload
    except ExpiredSignatureError as exc:
        logger.warning("[AUTH] JWT expired: %s", exc)
        return None
    except JWTError as exc:
        logger.warning("[AUTH] JWT signature invalid: %s", exc)
        return None


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    return decode_token(token, "access")


def decode_refresh_token(token: str) -> Optional[dict[str, Any]]:
    return decode_token(token, "refresh")


def session_expiry(remember_me: bool) -> datetime:
    return (
         utcnow() 
         + timedelta(days=REMEMBER_ME_DAYS if remember_me else REFRESH_TOKEN_DAYS)
    ).replace(tzinfo=None)     


def is_account_locked(user: dict[str, Any]) -> bool:
    locked_until = user.get("locked_until")
    if not locked_until:
        return False
    try:
        return datetime.fromisoformat(str(locked_until).replace("Z", "+00:00")) > utcnow()
    except ValueError:
        return False


def next_lock_expiry() -> datetime:
    return utcnow() + timedelta(minutes=ACCOUNT_LOCK_MINUTES)


def is_owner(user: Optional[dict[str, Any]]) -> bool:
    return bool(user and user.get("role") == OWNER_ROLE)


def is_admin(user: Optional[dict[str, Any]]) -> bool:
    return bool(user and user.get("role") in {OWNER_ROLE, ADMIN_ROLE})


def has_unrestricted_access(user: Optional[dict[str, Any]]) -> bool:
    return is_owner(user)
