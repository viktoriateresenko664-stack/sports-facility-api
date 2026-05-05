from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.routes import reports as reports_routes
from app.models.enums import AccountType
from app.models.enums import BackgroundJobStatus


def test_user_sees_only_own_requests(client, tokens, auth_header):
    response = client.get("/bff/web/user-requests/my", headers=auth_header(tokens["user"]))
    assert response.status_code == 200
    payload = response.json()
    assert payload, "Expected at least one request for authenticated user"
    assert all(item["user_id"] == 100 for item in payload)


def test_engineer_sees_only_own_assigned_tasks(client, tokens, auth_header):
    response = client.get("/bff/mobile/tasks", headers=auth_header(tokens["engineer"]))
    assert response.status_code == 200
    task_ids = [item["task_id"] for item in response.json()["tasks"]]
    assert 11 in task_ids
    assert 12 not in task_ids


def test_engineer_cannot_upload_report_for_foreign_task(client, tokens, auth_header):
    response = client.post(
        "/reports/upload",
        headers=auth_header(tokens["engineer"]),
        data={"task_id": "12", "notes": "done"},
        files={"report_file": ("report.txt", b"ok", "text/plain")},
    )
    assert response.status_code == 404


def test_reports_job_status_forbidden_for_foreign_owner(client, tokens, auth_header, monkeypatch):
    foreign_job = SimpleNamespace(
        job_id=uuid4(),
        owner_id=2,
        owner_type=AccountType.EMPLOYEE,
        status="PENDING",
        result=None,
        error=None,
    )
    monkeypatch.setattr(reports_routes.job_service, "get_job", lambda db, job_id: foreign_job)
    response = client.get(f"/reports/jobs/{foreign_job.job_id}", headers=auth_header(tokens["engineer"]))
    assert response.status_code == 404


def test_reports_upload_accepts_report_file(client, tokens, auth_header, monkeypatch):
    now = datetime.now(UTC)
    task = SimpleNamespace(task_id=11, facility_id=1, assigned_engineer_id=1)

    monkeypatch.setattr(reports_routes, "_get_accessible_task_or_404", lambda *args, **kwargs: task)
    monkeypatch.setattr(
        reports_routes.ReportService,
        "save_uploaded_file",
        lambda task_id, report_file: {
            "original_filename": "report.txt",
            "stored_filename": "report.txt",
            "stored_relative_path": "uploads/task_11/report.txt",
            "content_type": "text/plain; charset=utf-8",
            "size_bytes": 12,
            "sha256": "abc",
        },
    )
    monkeypatch.setattr(reports_routes.incident_recovery_service, "normalize_facility_sensors", lambda *a, **k: {})
    monkeypatch.setattr(reports_routes.LogService, "log_action", lambda *a, **k: None)
    monkeypatch.setattr(reports_routes.cache, "invalidate", lambda *a, **k: None)
    monkeypatch.setattr(reports_routes.task_stream_service, "publish_event", lambda *a, **k: None)
    monkeypatch.setattr(
        reports_routes.ReportService,
        "upsert_report_text",
        lambda db, task_id, engineer_id, report_text, commit=False: SimpleNamespace(
            report_id=77,
            task_id=task_id,
            engineer_id=engineer_id,
            report_text=report_text,
            created_at=now,
        ),
    )

    response = client.post(
        "/reports/upload",
        headers=auth_header(tokens["engineer"]),
        data={"task_id": "11", "notes": "fixed"},
        files={"report_file": ("report.txt", b"hello report", "text/plain")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["report_id"] == 77
    assert payload["task_id"] == 11
    assert payload["source"] == "uploaded_file"


def test_reports_upload_wrong_file_key_returns_422(client, tokens, auth_header):
    response = client.post(
        "/reports/upload",
        headers=auth_header(tokens["engineer"]),
        data={"task_id": "11", "notes": "fixed"},
        files={"file": ("report.txt", b"hello report", "text/plain")},
    )
    assert response.status_code == 422


def test_reports_generate_delayed_returns_job_id_and_status(
    client,
    tokens,
    auth_header,
    fake_background_job,
    monkeypatch,
):
    task = SimpleNamespace(task_id=11, facility_id=1, assigned_engineer_id=1)
    event = SimpleNamespace(event_id=uuid4())

    monkeypatch.setattr(reports_routes, "_get_accessible_task_or_404", lambda *args, **kwargs: task)
    monkeypatch.setattr(reports_routes.job_service, "create_job", lambda *args, **kwargs: fake_background_job)
    monkeypatch.setattr(reports_routes.LogService, "log_action", lambda *a, **k: None)
    monkeypatch.setattr(reports_routes.DomainEventService, "publish", lambda *a, **k: event)
    monkeypatch.setattr(reports_routes.DomainEventService, "enqueue", lambda *a, **k: None)
    monkeypatch.setattr(reports_routes.cache, "invalidate", lambda *a, **k: None)
    monkeypatch.setattr(reports_routes.generate_engineer_report_task, "apply_async", lambda *a, **k: None)

    response = client.post(
        "/reports/generate-delayed",
        headers=auth_header(tokens["engineer"]),
        json={"task_id": 11, "delay_seconds": 5, "report_type": "standard"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"]
    assert payload["status"] == "PENDING"


@pytest.mark.parametrize(
    ("raw_status", "expected_status"),
    [
        ("PENDING", "CREATED"),
        ("PROCESSING", "ACTIVE"),
        ("SUCCESS", "COMPLETED"),
        ("FAILED", "CANCELLED"),
    ],
)
def test_reports_job_status_mapping(client, tokens, auth_header, monkeypatch, raw_status, expected_status):
    own_job = SimpleNamespace(
        job_id=uuid4(),
        owner_id=1,
        owner_type=AccountType.EMPLOYEE,
        status=raw_status,
        result={"report_id": 50},
        error=None,
    )
    monkeypatch.setattr(reports_routes.job_service, "get_job", lambda db, job_id: own_job)
    response = client.get(f"/reports/jobs/{own_job.job_id}", headers=auth_header(tokens["engineer"]))
    assert response.status_code == 200
    assert response.json()["status"] == expected_status


def test_security_without_token_returns_401(client):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_security_wrong_role_returns_403(client, tokens, auth_header):
    response = client.get("/bff/mobile/tasks", headers=auth_header(tokens["user"]))
    assert response.status_code == 403


def test_security_missing_resource_returns_404(client, tokens, auth_header):
    response = client.get("/sports-facilities/999", headers=auth_header(tokens["user"]))
    assert response.status_code == 404


def test_security_conflict_returns_409(client, tokens, auth_header):
    response = client.post(
        "/bff/desktop/requests/201/assign",
        headers=auth_header(tokens["operator"]),
        json={"assigned_engineer_id": 1, "operator_comment": "assign"},
    )
    assert response.status_code == 409


def test_security_invalid_body_returns_422(client):
    response = client.post("/auth/login", json={"email": "user100@example.com"})
    assert response.status_code == 422
