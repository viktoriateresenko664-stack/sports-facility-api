from __future__ import annotations

from datetime import UTC, datetime

from app.models.enums import AccountType
from app.schemas.auth import AuthMeResponse
from app.schemas.bff import MobileTaskSummary, MobileTasksResponse, WebDashboardResponse
from app.services.commands.auth_commands import AuthCommandService
from app.services.queries.mobile_tasks_queries import MobileTasksQueryService
from app.services.queries.web_dashboard_queries import WebDashboardQueryService


def test_auth_me_post_uses_auth_command_service(client, tokens, auth_header, monkeypatch):
    called = {"value": False}

    def _fake_update_profile(db, *, user, payload):
        called["value"] = True
        return AuthMeResponse(
            account_type=AccountType.USER,
            subject_id=user.user_id,
            username=user.username,
            email=user.email,
            phone=payload.phone,
            employee_key=None,
            roles=["USER"],
            is_active=True,
            created_at=datetime.now(UTC),
        )

    monkeypatch.setattr(AuthCommandService, "update_profile", staticmethod(_fake_update_profile))
    response = client.post(
        "/auth/me",
        headers=auth_header(tokens["user"]),
        json={"phone": "+79990001122"},
    )
    assert response.status_code == 200
    assert called["value"] is True
    assert response.json()["phone"] == "+79990001122"


def test_web_dashboard_uses_query_service(client, tokens, auth_header, monkeypatch):
    called = {"value": False}

    def _fake_dashboard(db, *, user_id):
        called["value"] = True
        return WebDashboardResponse(
            summary="web dashboard",
            widgets=["facilities", "active_tasks", "alerts"],
            total_tasks=10,
            active_tasks=3,
            completed_tasks=7,
        )

    monkeypatch.setattr(WebDashboardQueryService, "get_dashboard", staticmethod(_fake_dashboard))
    response = client.get("/bff/web/dashboard", headers=auth_header(tokens["user"]))
    assert response.status_code == 200
    assert called["value"] is True
    assert response.json()["total_tasks"] == 10


def test_mobile_tasks_uses_query_service(client, tokens, auth_header, monkeypatch):
    called = {"value": False}

    def _fake_mobile_tasks(db, *, employee_id, role, account_type):
        called["value"] = True
        return MobileTasksResponse(
            total=1,
            active=1,
            completed=0,
            created=0,
            cancelled=0,
            summary=MobileTaskSummary(total=1, active=1, completed=0, created=0, cancelled=0),
            tasks=[],
            quick_actions=["start", "finish", "cancel"],
        )

    monkeypatch.setattr(MobileTasksQueryService, "get_tasks", staticmethod(_fake_mobile_tasks))
    response = client.get("/bff/mobile/tasks", headers=auth_header(tokens["engineer"]))
    assert response.status_code == 200
    assert called["value"] is True
    assert response.json()["summary"]["total"] == 1
