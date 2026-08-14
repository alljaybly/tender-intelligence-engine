"""
Regression tests for GET /api/auth/me datetime serialization.

Root cause (confirmed in production):
  `get_me()` in api/routes/auth.py previously passed the raw `created_at`
  value from the database row directly into `UserResponse`, whose
  `created_at` field is `Optional[str]`.

  - SQLite returns TIMESTAMP columns as str  ->  /me worked
  - PostgreSQL (asyncpg) returns TIMESTAMP as datetime.datetime  ->
    Pydantic v2 raised ValidationError inside the route, producing a 500
    that the browser surfaced as a misleading CORS/ERR_FAILED error.
  This is the SAME class of bug that was already fixed for /api/auth/login
  and /api/auth/register in commit e8f7829 (which introduced
  `_serialize_optional_datetime`), but get_me was missed.

Tests:
  1. _serialize_optional_datetime handles None / datetime / str.
  2. UserResponse rejects a raw datetime for created_at (original failure).
  3. UserResponse accepts a datetime after _serialize_optional_datetime.
  4. get_me uses _serialize_optional_datetime (static source check).
  5. Integration: /api/auth/me returns 200 with a valid token and the
     created_at field is a JSON string (never a raw datetime).
  6. Integration: /api/auth/me returns 401 without or with bad tokens.

The integration tests use their own isolated SQLite database so they never
collide with tests/test_auth.py's DB_PATH lifecycle.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["JWT_SECRET_KEY"] = "test-jwt-secret"
os.environ["MAX_FAILED_LOGIN_ATTEMPTS"] = "5"
os.environ["ACCOUNT_LOCK_MINUTES"] = "15"

from api.main import app
from api.routes.auth import _serialize_optional_datetime, get_me
from api.schemas.auth import UserResponse
from api.services import database as database_module


_ME_DB_PATH = Path(__file__).resolve().parents[1] / "test_tender_engine_auth_me.db"


def _setup_me_db() -> None:
    if _ME_DB_PATH.exists():
        _ME_DB_PATH.unlink()
    database_module.DB_PATH = str(_ME_DB_PATH)
    from api.services.database import init_db
    init_db()


def _teardown_me_db() -> None:
    if _ME_DB_PATH.exists():
        _ME_DB_PATH.unlink()


_REGISTER_PAYLOAD = {
    "full_name": "Me Tester",
    "company_name": "Me Co",
    "email": "me@example.com",
    "password": "SecurePass123",
    "confirm_password": "SecurePass123",
}


class TestSerializeOptionalDatetime:
    def test_none_passes_through(self):
        assert _serialize_optional_datetime(None) is None

    def test_naive_datetime_isoformat(self):
        value = datetime(2026, 8, 14, 10, 0, 0)
        assert _serialize_optional_datetime(value) == "2026-08-14T10:00:00"

    def test_aware_datetime_isoformat(self):
        value = datetime(2026, 8, 14, 10, 0, 0, tzinfo=timezone.utc)
        assert _serialize_optional_datetime(value) == "2026-08-14T10:00:00+00:00"

    def test_string_passthrough(self):
        assert _serialize_optional_datetime("2026-08-14 10:00:00") == "2026-08-14 10:00:00"


class TestUserResponseDatetimeRejection:
    def test_raw_datetime_raises_validation_error(self):
        """Reproduces the original production failure for UserResponse."""
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            UserResponse(
                id=1,
                email="u@x.com",
                full_name="U",
                company_name="C",
                role="customer",
                plan="free",
                is_active=True,
                email_verified=True,
                created_at=datetime(2026, 8, 14, 10, 0, 0),
            )

    def test_normalised_datetime_is_accepted(self):
        """After normalisation, the same value passes schema validation."""
        user = UserResponse(
            id=1,
            email="u@x.com",
            full_name="U",
            company_name="C",
            role="customer",
            plan="free",
            is_active=True,
            email_verified=True,
            created_at=_serialize_optional_datetime(datetime(2026, 8, 14, 10, 0, 0)),
        )
        assert user.created_at == "2026-08-14T10:00:00"


class TestGetMeUsesHelper:
    def test_get_me_source_uses_serialize_optional_datetime(self):
        """get_me must normalise created_at via the helper, not pass raw."""
        import inspect

        source = inspect.getsource(get_me)
        assert "_serialize_optional_datetime(current_user.get(\"created_at\"))" in source
        # Make sure no leftover raw assignment remains.
        assert "created_at=current_user.get(\"created_at\")" not in source


class TestMeEndpointIntegration:
    def setup_method(self):
        _setup_me_db()

    def teardown_method(self):
        _teardown_me_db()

    def test_me_returns_200_with_valid_token(self):
        client = TestClient(app)
        reg = client.post("/api/auth/register", json=_REGISTER_PAYLOAD)
        assert reg.status_code == 201, reg.text
        token = reg.json()["access_token"]

        me = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me.status_code == 200, me.text
        body = me.json()
        assert body["email"] == "me@example.com"
        assert body["role"] == "customer"
        # created_at must be a string (never a raw datetime) on the response
        assert isinstance(body["created_at"], str)
        assert body["created_at"]

    def test_me_returns_401_without_token(self):
        client = TestClient(app)
        me = client.get("/api/auth/me")
        assert me.status_code == 401

    def test_me_returns_401_with_invalid_token(self):
        client = TestClient(app)
        me = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert me.status_code == 401


if __name__ == "__main__":
    import pytest
    try:
        _setup_me_db()
        raise SystemExit(pytest.main([__file__, "-v", "-p", "no:warnings"]))
    finally:
        _teardown_me_db()
