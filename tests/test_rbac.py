from __future__ import annotations

import pytest
from starlette.websockets import WebSocketDisconnect


def test_user_cannot_open_desktop_bff(client, tokens, auth_header):
    response = client.get("/bff/desktop/dashboard", headers=auth_header(tokens["user"]))
    assert response.status_code == 403


def test_engineer_cannot_open_desktop_bff(client, tokens, auth_header):
    response = client.get("/bff/desktop/dashboard", headers=auth_header(tokens["engineer"]))
    assert response.status_code == 403


def test_engineer_cannot_open_ws_tasks(client, tokens):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/tasks?token={tokens['engineer']}"):
            pass


def test_engineer_cannot_open_ws_sensors(client, tokens):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/sensors?token={tokens['engineer']}"):
            pass


def test_operator_can_open_desktop_bff(client, tokens, auth_header):
    response = client.get("/bff/desktop/dashboard", headers=auth_header(tokens["operator"]))
    assert response.status_code == 200
    assert "facilities" in response.json()


def test_chief_engineer_can_open_desktop_bff(client, tokens, auth_header):
    response = client.get("/bff/desktop/dashboard", headers=auth_header(tokens["chief"]))
    assert response.status_code == 200
    assert "facilities" in response.json()


def test_engineer_can_open_mobile_tasks(client, tokens, auth_header):
    response = client.get("/bff/mobile/tasks", headers=auth_header(tokens["engineer"]))
    assert response.status_code == 200
    assert "tasks" in response.json()


def test_user_cannot_open_mobile_tasks(client, tokens, auth_header):
    response = client.get("/bff/mobile/tasks", headers=auth_header(tokens["user"]))
    assert response.status_code == 403
