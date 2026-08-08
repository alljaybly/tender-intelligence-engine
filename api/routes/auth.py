"""Production authentication routes for Tender Engine Phase 1."""
from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from ..services.auth import (
    MAX_FAILED_LOGIN_ATTEMPTS,
    create_access_token,
    create_refresh_token_payload,
    decode_access_token,
    decode_refresh_token,
    generate_session_id,
    hash_password,
    hash_refresh_token,
    is_account_locked,
    next_lock_expiry,
    password_is_strong,
    session_expiry,
    utcnow,
)
from ..services.database import close_db, get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


def _request_context(request: Request, user_agent: Optional[str]) -> tuple[str, str]:
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "")
    return ip, user_agent or request.headers.get("user-agent", "")


async def _write_auth_audit(
    *,
    action: str,
    user_id: Optional[int],
    actor_user_id: Optional[int],
    session_id: Optional[str],
    ip_address: str,
    user_agent: str,
    details: dict,
) -> None:
    db = await get_db()
    try:
        await db.execute(
            """
            INSERT INTO auth_audit_log (user_id, actor_user_id, action, session_id, ip_address, user_agent, details_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, actor_user_id, action, session_id, ip_address, user_agent, json.dumps(details)),
        )
        await db.commit()
    finally:
        await close_db(db)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    auth_header_received = credentials is not None
    jwt_decoded = False
    user_id = None
    session_id = None
    session_found = False
    revoked_at_is_null = False
    reason = None

    if not auth_header_received:
        reason = "Authorization header missing"
        logger.warning(
            "[AUTH DEBUG] auth_header_received=%s jwt_decoded=%s user_id=%s session_id=%s session_found=%s revoked_at_is_null=%s reason=%s",
            auth_header_received, jwt_decoded, user_id, session_id, session_found, revoked_at_is_null, reason,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})

    payload = decode_access_token(credentials.credentials)
    jwt_decoded = payload is not None
    if not jwt_decoded:
        reason = "JWT expired or signature invalid"
        logger.warning(
            "[AUTH DEBUG] auth_header_received=%s jwt_decoded=%s user_id=%s session_id=%s session_found=%s revoked_at_is_null=%s reason=%s",
            auth_header_received, jwt_decoded, user_id, session_id, session_found, revoked_at_is_null, reason,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})

    user_id = payload.get("sub")
    session_id = payload.get("sid")
    if user_id is None or session_id is None:
        reason = "Invalid token payload"
        logger.warning(
            "[AUTH DEBUG] auth_header_received=%s jwt_decoded=%s user_id=%s session_id=%s session_found=%s revoked_at_is_null=%s reason=%s",
            auth_header_received, jwt_decoded, user_id, session_id, session_found, revoked_at_is_null, reason,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (int(user_id),))
        row = await cursor.fetchone()
        if row is None:
            reason = "User not found"
            logger.warning(
                "[AUTH DEBUG] auth_header_received=%s jwt_decoded=%s user_id=%s session_id=%s session_found=%s revoked_at_is_null=%s reason=%s",
                auth_header_received, jwt_decoded, user_id, session_id, session_found, revoked_at_is_null, reason,
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        user = dict(row)
        if not user.get("is_active"):
            reason = "Account is disabled"
            logger.warning(
                "[AUTH DEBUG] auth_header_received=%s jwt_decoded=%s user_id=%s session_id=%s session_found=%s revoked_at_is_null=%s reason=%s",
                auth_header_received, jwt_decoded, user_id, session_id, session_found, revoked_at_is_null, reason,
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

        session_cursor = await db.execute(
            "SELECT * FROM auth_sessions WHERE session_id = ? AND user_id = ? AND revoked_at IS NULL",
            (session_id, int(user_id)),
        )
        session_row = await session_cursor.fetchone()
        if session_row is None:
            revoke_check = await db.execute(
                "SELECT revoked_at FROM auth_sessions WHERE session_id = ? AND user_id = ?",
                (session_id, int(user_id)),
            )
            revoke_row = await revoke_check.fetchone()
            if revoke_row:
                revoked_at = revoke_row["revoked_at"] if hasattr(revoke_row, "keys") else revoke_row[0]
                revoked_at_is_null = revoked_at is None
                reason = "Session revoked" if revoked_at is not None else "Session not found"
            else:
                reason = "Session not found"
            logger.warning(
                "[AUTH DEBUG] auth_header_received=%s jwt_decoded=%s user_id=%s session_id=%s session_found=%s revoked_at_is_null=%s reason=%s",
                auth_header_received, jwt_decoded, user_id, session_id, session_found, revoked_at_is_null, reason,
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session not found or expired")
        else:
            session_found = True
            revoked_at_is_null = True

        await db.execute(
            "UPDATE auth_sessions SET last_active_at = CURRENT_TIMESTAMP WHERE session_id = ?",
            (session_id,),
        )
        await db.commit()

        user["session_id"] = session_id
        user["impersonated_by"] = payload.get("impersonated_by")
        return user
    finally:
        await close_db(db)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[dict]:
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    user_agent: Optional[str] = Header(default=None),
):
    if payload.password != payload.confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")
    if not password_is_strong(payload.password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters and include upper, lower, and numeric characters")

    db = await get_db()
    try:
        cursor = await db.execute("SELECT id FROM users WHERE lower(email) = lower(?)", (payload.email.strip(),))
        existing = await cursor.fetchone()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")

        hashed = hash_password(payload.password)
        cursor = await db.execute(
            """
            INSERT INTO users (email, hashed_password, full_name, company_name, role, email_verified, plan)
            VALUES (?, ?, ?, ?, 'customer',  TRUE, 'free')
            """,
            (payload.email.strip(), hashed, payload.full_name.strip(), payload.company_name.strip()),
        )
        await db.commit()
        user_id = int(cursor.lastrowid)

        session_id = generate_session_id()
        remember_me = True
        refresh_token, refresh_expires = create_refresh_token_payload(
            user_id=user_id,
            session_id=session_id,
            remember_me=remember_me,
        )
        ip_address, user_agent_value = _request_context(request, user_agent)
        await db.execute(
            """
            INSERT INTO auth_sessions (user_id, session_id, refresh_token_hash, user_agent, ip_address, remember_me, expires_at, last_active_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                user_id,
                session_id,
                hash_refresh_token(refresh_token),
                user_agent_value,
                ip_address,
                remember_me,
                session_expiry(remember_me),
            ),
        )
        await db.commit()

        access_token, access_expires = create_access_token(
            user={"id": user_id, "email": payload.email.strip(), "role": "customer"},
            session_id=session_id,
        )

        await _write_auth_audit(
            action="register",
            user_id=user_id,
            actor_user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent_value,
            details={"email": payload.email.strip(), "company_name": payload.company_name.strip(), "remember_me": remember_me},
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=int((access_expires - utcnow()).total_seconds()),
            refresh_expires_in=int((refresh_expires - utcnow()).total_seconds()),
            remember_me=remember_me,
            user=UserResponse(
                id=user_id,
                email=payload.email.strip(),
                full_name=payload.full_name.strip(),
                company_name=payload.company_name.strip(),
                role="customer",
                plan="free",
                is_active=True,
                email_verified=True,
                created_at=None,
            ),
        )
    finally:
        await close_db(db)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    user_agent: Optional[str] = Header(default=None),
):
    db = await get_db()
    ip_address, user_agent_value = _request_context(request, user_agent)
    try:
        cursor = await db.execute("SELECT * FROM users WHERE lower(email) = lower(?)", (payload.email.strip(),))
        row = await cursor.fetchone()
        if row is None:
            logger.warning("[AUTH] 401 reason=Invalid email or password, email=%s", payload.email.strip())
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        user = dict(row)

        if not user.get("is_active"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
        if is_account_locked(user):
            raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Account temporarily locked due to repeated failed login attempts")

        from ..services.auth import verify_password
        if not verify_password(payload.password, user["hashed_password"]):
            failed_attempts = int(user.get("failed_login_attempts") or 0) + 1
            if failed_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
                await db.execute(
                    "UPDATE users SET failed_login_attempts = ?, locked_until = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (failed_attempts, next_lock_expiry(), user["id"]),
                )
            else:
                await db.execute(
                    "UPDATE users SET failed_login_attempts = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (failed_attempts, user["id"]),
                )
            await db.commit()
            await _write_auth_audit(
                action="login_failed",
                user_id=user["id"],
                actor_user_id=user["id"],
                session_id=None,
                ip_address=ip_address,
                user_agent=user_agent_value,
                details={"failed_login_attempts": failed_attempts},
            )
            logger.warning("[AUTH] 401 reason=Invalid email or password, email=%s, failed_attempts=%s", payload.email.strip(), failed_attempts)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

        session_id = generate_session_id()
        remember_me = bool(payload.remember_me)
        refresh_token, refresh_expires = create_refresh_token_payload(
            user_id=int(user["id"]),
            session_id=session_id,
            remember_me=remember_me,
        )
        await db.execute(
            """
            INSERT INTO auth_sessions (user_id, session_id, refresh_token_hash, user_agent, ip_address, remember_me, expires_at, last_active_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                user["id"],
                session_id,
                hash_refresh_token(refresh_token),
                user_agent_value,
                ip_address,
                remember_me,
                session_expiry(remember_me).replace(tzinfo=None),
            ),
        )
        await db.execute(
            "UPDATE users SET failed_login_attempts = 0, locked_until = NULL, last_login_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (user["id"],),
        )
        await db.commit()

        access_token, access_expires = create_access_token(user=user, session_id=session_id)
        await _write_auth_audit(
            action="login_success",
            user_id=user["id"],
            actor_user_id=user["id"],
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent_value,
            details={"remember_me": remember_me},
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=int((access_expires - utcnow()).total_seconds()),
            refresh_expires_in=int((refresh_expires - utcnow()).total_seconds()),
            remember_me=remember_me,
            user=UserResponse(
                id=int(user["id"]),
                email=user["email"],
                full_name=user.get("full_name", ""),
                company_name=user.get("company_name", ""),
                role=user.get("role", "customer"),
                plan=user.get("plan", "free"),
                is_active=bool(user.get("is_active", True)),
                email_verified=bool(user.get("email_verified", True)),
                created_at=user["created_at"].isoformat() if user.get("created_at") else "",
            ),
        )
    finally:
        await close_db(db)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: RefreshRequest,
    request: Request,
    user_agent: Optional[str] = Header(default=None),
):
    token_payload = decode_refresh_token(payload.refresh_token)
    if token_payload is None:
        logger.warning("[AUTH] 401 reason=Refresh token expired or signature invalid")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is invalid or expired")

    user_id = int(token_payload["sub"])
    session_id = str(token_payload["sid"])
    ip_address, user_agent_value = _request_context(request, user_agent)

    db = await get_db()
    try:
        session_cursor = await db.execute(
            "SELECT * FROM auth_sessions WHERE session_id = ? AND user_id = ? AND revoked_at IS NULL",
            (session_id, user_id),
        )
        session_row = await session_cursor.fetchone()
        if session_row is None:
            logger.warning("[AUTH] 401 reason=Session not active, session_id=%s, user_id=%s", session_id, user_id)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is no longer active")
        session = dict(session_row)

        if session["refresh_token_hash"] != hash_refresh_token(payload.refresh_token):
            logger.warning("[AUTH] 401 reason=Refresh token rotation check failed, session_id=%s, user_id=%s", session_id, user_id)
            await db.execute("UPDATE auth_sessions SET revoked_at = CURRENT_TIMESTAMP WHERE session_id = ?", (session_id,))
            await db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token rotation check failed")

        user_cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user_row = await user_cursor.fetchone()
        if user_row is None:
            logger.warning("[AUTH] 401 reason=User not found, user_id=%s", user_id)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        user = dict(user_row)
        if not user.get("is_active"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

        remember_me = bool(session.get("remember_me"))
        new_refresh_token, refresh_expires = create_refresh_token_payload(
            user_id=user_id,
            session_id=session_id,
            remember_me=remember_me,
            impersonated_by=session.get("impersonated_by"),
        )
        access_token, access_expires = create_access_token(
            user=user,
            session_id=session_id,
            impersonated_by=session.get("impersonated_by"),
        )
        await db.execute(
            """
            UPDATE auth_sessions
            SET refresh_token_hash = ?, user_agent = ?, ip_address = ?, expires_at = ?, last_active_at = CURRENT_TIMESTAMP
            WHERE session_id = ?
            """,
            (hash_refresh_token(new_refresh_token), user_agent_value, ip_address, session_expiry(remember_me), session_id),
        )
        await db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=int((access_expires - utcnow()).total_seconds()),
            refresh_expires_in=int((refresh_expires - utcnow()).total_seconds()),
            remember_me=remember_me,
            user=UserResponse(
                id=user_id,
                email=user["email"],
                full_name=user.get("full_name", ""),
                company_name=user.get("company_name", ""),
                role=user.get("role", "customer"),
                plan=user.get("plan", "free"),
                is_active=bool(user.get("is_active", True)),
                email_verified=bool(user.get("email_verified", True)),
                created_at=user["created_at"].isoformat() if user.get("created_at") else "",
            ),
        )
    finally:
        await close_db(db)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: dict = Depends(get_current_user)):
    db = await get_db()
    try:
        await db.execute("UPDATE auth_sessions SET revoked_at = CURRENT_TIMESTAMP WHERE session_id = ?", (current_user["session_id"],))
        await db.commit()
    finally:
        await close_db(db)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(current_user: dict = Depends(get_current_user)):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE auth_sessions SET revoked_at = CURRENT_TIMESTAMP WHERE user_id = ? AND revoked_at IS NULL",
            (current_user["id"],),
        )
        await db.commit()
    finally:
        await close_db(db)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        id=int(current_user["id"]),
        email=current_user["email"],
        full_name=current_user.get("full_name", ""),
        company_name=current_user.get("company_name", ""),
        role=current_user.get("role", "customer"),
        plan=current_user.get("plan", "free"),
        is_active=bool(current_user.get("is_active", True)),
        email_verified=bool(current_user.get("email_verified", True)),
        created_at=current_user.get("created_at"),
    )
