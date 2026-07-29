"""Authentication integration tests for the Phase 1 production auth flow."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

TEST_DB_PATH = Path(__file__).resolve().parents[1] / "test_tender_engine_auth.db"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret"
os.environ["MAX_FAILED_LOGIN_ATTEMPTS"] = "5"
os.environ["ACCOUNT_LOCK_MINUTES"] = "15"

from api.main import app
from api.services import database as database_module
from api.services.database import init_db


def setup_function() -> None:
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    database_module.DB_PATH = str(TEST_DB_PATH)
    init_db()


def teardown_function() -> None:
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


def _register_payload(email: str = "owner@example.com") -> dict:
    return {
        "full_name": "Test Owner",
        "company_name": "Tender Engine QA",
        "email": email,
        "password": "SecurePass123",
        "confirm_password": "SecurePass123",
    }


def test_register_returns_session_tokens_and_me_works() -> None:
    client = TestClient(app)

    response = client.post("/api/auth/register", json=_register_payload())
    assert response.status_code == 201, response.text
    data = response.json()

    assert data["access_token"]
    assert data["refresh_token"]
    assert data["remember_me"] is True
    assert data["user"]["email"] == "owner@example.com"
    assert data["user"]["company_name"] == "Tender Engine QA"

    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert me.status_code == 200, me.text
    me_data = me.json()
    assert me_data["email"] == "owner@example.com"
    assert me_data["role"] == "customer"


def test_login_refresh_logout_and_session_revocation_flow() -> None:
    client = TestClient(app)
    register = client.post("/api/auth/register", json=_register_payload("flow@example.com"))
    assert register.status_code == 201, register.text

    login = client.post(
        "/api/auth/login",
        json={
            "email": "flow@example.com",
            "password": "SecurePass123",
            "remember_me": True,
        },
    )
    assert login.status_code == 200, login.text
    login_data = login.json()

    first_access = login_data["access_token"]
    first_refresh = login_data["refresh_token"]
    assert first_refresh
    assert login_data["remember_me"] is True

    refresh = client.post(
        "/api/auth/refresh",
        json={"refresh_token": first_refresh},
    )
    assert refresh.status_code == 200, refresh.text
    refresh_data = refresh.json()
    assert refresh_data["access_token"]
    assert refresh_data["refresh_token"]
    assert refresh_data["refresh_token"] != first_refresh

    logout = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {refresh_data['access_token']}"},
    )
    assert logout.status_code == 204, logout.text

    me_after_logout = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {refresh_data['access_token']}"},
    )
    assert me_after_logout.status_code == 401, me_after_logout.text

    refresh_after_logout = client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_data["refresh_token"]},
    )
    assert refresh_after_logout.status_code == 401, refresh_after_logout.text

    old_access_still_revoked = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {first_access}"},
    )
    assert old_access_still_revoked.status_code == 401, old_access_still_revoked.text


def test_logout_all_revokes_all_active_sessions() -> None:
    client = TestClient(app)
    register = client.post("/api/auth/register", json=_register_payload("all@example.com"))
    assert register.status_code == 201, register.text

    login_one = client.post(
        "/api/auth/login",
        json={
            "email": "all@example.com",
            "password": "SecurePass123",
            "remember_me": False,
        },
    )
    assert login_one.status_code == 200, login_one.text
    token_one = login_one.json()["access_token"]

    login_two = client.post(
        "/api/auth/login",
        json={
            "email": "all@example.com",
            "password": "SecurePass123",
            "remember_me": True,
        },
    )
    assert login_two.status_code == 200, login_two.text
    login_two_data = login_two.json()

    logout_all = client.post(
        "/api/auth/logout-all",
        headers={"Authorization": f"Bearer {login_two_data['access_token']}"},
    )
    assert logout_all.status_code == 204, logout_all.text

    me_one = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_one}"})
    assert me_one.status_code == 401, me_one.text

    me_two = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {login_two_data['access_token']}"},
    )
    assert me_two.status_code == 401, me_two.text

    refresh_two = client.post(
        "/api/auth/refresh",
        json={"refresh_token": login_two_data["refresh_token"]},
    )
    assert refresh_two.status_code == 401, refresh_two.text


def test_login_rejects_invalid_password() -> None:
    client = TestClient(app)
    register = client.post("/api/auth/register", json=_register_payload("invalid@example.com"))
    assert register.status_code == 201, register.text

    login = client.post(
        "/api/auth/login",
        json={
            "email": "invalid@example.com",
            "password": "WrongPass123",
            "remember_me": False,
        },
    )
    assert login.status_code == 401, login.text
    error_body = login.json()
    assert error_body["message"] == "Invalid email or password"
    assert error_body["code"] == "unauthorized"
