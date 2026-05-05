from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException

from app.models.enums import AccountType
from app.schemas.auth import AuthMeResponse, TokenResponse
from app.schemas.auth import UpdateUserProfileRequest
from app.services.auth_service import AuthService


def _auth_me_response(subject_id: int, role: str) -> AuthMeResponse:
    return AuthMeResponse(
        account_type=AccountType.USER if role == "USER" else AccountType.EMPLOYEE,
        subject_id=subject_id,
        username="user100" if role == "USER" else None,
        email="user100@example.com" if role == "USER" else "emp@example.com",
        phone="+70000000000" if role == "USER" else None,
        employee_key="ENG001" if role != "USER" else None,
        roles=[role],
        is_active=True,
        created_at=datetime.now(UTC),
    )


def test_auth_register(client, monkeypatch):
    monkeypatch.setattr(AuthService, "register_user", lambda db, payload: db.users[100])
    monkeypatch.setattr(AuthService, "me_for_user", lambda db, user: _auth_me_response(user.user_id, "USER"))

    response = client.post(
        "/auth/register",
        json={
            "username": "new_user",
            "email": "new_user@example.com",
            "password": "StrongPass123",
            "phone": "+79998887766",
        },
    )
    assert response.status_code == 200
    assert response.json()["subject_id"] == 100
    assert response.json()["account_type"] == "USER"


def test_auth_login(client, monkeypatch):
    monkeypatch.setattr(
        AuthService,
        "login_user",
        lambda db, payload, client_ip="unknown": TokenResponse(access_token="a", refresh_token="b"),
    )
    response = client.post("/auth/login", json={"email": "user100@example.com", "password": "StrongPass123"})
    assert response.status_code == 200
    assert response.json()["access_token"] == "a"
    assert response.json()["refresh_token"] == "b"


def test_auth_employee_login(client, monkeypatch):
    monkeypatch.setattr(
        AuthService,
        "login_employee",
        lambda db, payload, client_ip="unknown": TokenResponse(access_token="ea", refresh_token="er"),
    )
    response = client.post("/auth/employee-login", json={"employee_key": "ENG001", "password": "StrongPass123"})
    assert response.status_code == 200
    assert response.json()["access_token"] == "ea"
    assert response.json()["refresh_token"] == "er"


def test_auth_refresh(client, monkeypatch, tokens):
    monkeypatch.setattr(
        AuthService,
        "refresh_tokens",
        lambda db, refresh_token: TokenResponse(access_token="new_access", refresh_token="new_refresh"),
    )
    response = client.post("/auth/refresh", json={"refresh_token": tokens["refresh"]})
    assert response.status_code == 200
    assert response.json()["access_token"] == "new_access"
    assert response.json()["refresh_token"] == "new_refresh"


def test_auth_logout(client, monkeypatch, tokens):
    called = {"value": False}

    def _logout(db, refresh_token):
        called["value"] = True
        return None

    monkeypatch.setattr(AuthService, "logout", _logout)
    response = client.post("/auth/logout", json={"refresh_token": tokens["refresh"]})
    assert response.status_code == 204
    assert called["value"] is True


def test_auth_me_get(client, monkeypatch, tokens, auth_header):
    monkeypatch.setattr(AuthService, "me_for_user", lambda db, user: _auth_me_response(user.user_id, "USER"))
    response = client.get("/auth/me", headers=auth_header(tokens["user"]))
    assert response.status_code == 200
    assert response.json()["subject_id"] == 100
    assert response.json()["roles"] == ["USER"]


def test_auth_me_post_update(client, monkeypatch, tokens, auth_header):
    monkeypatch.setattr(AuthService, "update_user_profile", lambda db, user, payload: _auth_me_response(user.user_id, "USER"))
    response = client.post(
        "/auth/me",
        headers=auth_header(tokens["user"]),
        json={"phone": "+79990001122"},
    )
    assert response.status_code == 200
    assert response.json()["subject_id"] == 100


def test_auth_service_detects_duplicate_phone_with_normalization(dummy_db):
    duplicate = AuthService._find_user_with_same_phone(dummy_db, phone="8 (000) 000-00-00")
    assert duplicate is not None
    assert duplicate.user_id == 100


def test_auth_service_update_profile_rejects_duplicate_phone(dummy_db):
    user = dummy_db.users[100]
    payload = UpdateUserProfileRequest(phone="+7 (111) 111-11-11")
    try:
        AuthService.update_user_profile(dummy_db, user=user, payload=payload)
        assert False, "Expected HTTPException for duplicate phone"
    except HTTPException as exc:
        assert exc.status_code == 409
        assert exc.detail == "Phone already registered"
