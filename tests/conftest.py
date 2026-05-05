from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.db.session import get_db
from app.main import app
from app.models.employee import Employee
from app.models.enums import AccountType
from app.models.enums import AvailabilityStatus
from app.models.enums import BackgroundJobStatus
from app.models.enums import RequestStatus
from app.models.enums import TaskStatus
from app.models.user import User


@dataclass
class DummyResult:
    rows: list[dict[str, Any]]

    def mappings(self) -> "DummyResult":
        return self

    def one(self) -> dict[str, Any]:
        if not self.rows:
            raise AssertionError("Expected one row, got none")
        return self.rows[0]

    def all(self) -> list[dict[str, Any]]:
        return self.rows

    def first(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None


class DummyQuery:
    def __init__(self, db: "DummyDB", model: type) -> None:
        self.db = db
        self.model = model
        self.criteria: list[Any] = []
        self._offset = 0
        self._limit: int | None = None

    def filter(self, *criteria: Any) -> "DummyQuery":
        self.criteria.extend(criteria)
        return self

    def with_for_update(self) -> "DummyQuery":
        return self

    def order_by(self, *_: Any) -> "DummyQuery":
        return self

    def join(self, *_: Any, **__: Any) -> "DummyQuery":
        return self

    def offset(self, value: int) -> "DummyQuery":
        self._offset = value
        return self

    def limit(self, value: int) -> "DummyQuery":
        self._limit = value
        return self

    def count(self) -> int:
        return len(self._apply())

    def first(self) -> Any | None:
        rows = self._apply()
        return rows[0] if rows else None

    def all(self) -> list[Any]:
        return self._apply()

    def _apply(self) -> list[Any]:
        if self.model.__name__ == "EngineerTask":
            rows = list(self.db.tasks.values())
        elif self.model.__name__ == "EngineerReport":
            rows = list(self.db.reports.values())
        elif self.model.__name__ == "User":
            rows = list(self.db.users.values())
        else:
            rows = []

        for criterion in self.criteria:
            left = getattr(criterion, "left", None)
            right = getattr(criterion, "right", None)
            operator = getattr(criterion, "operator", None)
            key = getattr(left, "key", None)
            value = getattr(right, "value", None)
            if key is None or value is None or operator is None:
                continue
            rows = [row for row in rows if operator(getattr(row, key, None), value)]

        if self._offset:
            rows = rows[self._offset :]
        if self._limit is not None:
            rows = rows[: self._limit]
        return rows


class DummyDB:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.users: dict[int, User] = {
            100: User(
                user_id=100,
                username="user100",
                email="user100@example.com",
                password_hash="hash",
                phone="+70000000000",
                is_active=True,
                created_at=now,
            ),
            101: User(
                user_id=101,
                username="user101",
                email="user101@example.com",
                password_hash="hash",
                phone="+71111111111",
                is_active=True,
                created_at=now,
            ),
        }
        self.employees: dict[int, Employee] = {
            1: Employee(
                employee_id=1,
                employee_key="ENG001",
                first_name="Eng",
                last_name="One",
                middle_name=None,
                phone="+79990000001",
                email="eng1@example.com",
                position="Engineer",
                password_hash="hash",
                availability_status=AvailabilityStatus.AVAILABLE,
                is_active=True,
                created_at=now,
            ),
            2: Employee(
                employee_id=2,
                employee_key="ENG002",
                first_name="Eng",
                last_name="Two",
                middle_name=None,
                phone="+79990000002",
                email="eng2@example.com",
                position="Engineer",
                password_hash="hash",
                availability_status=AvailabilityStatus.AVAILABLE,
                is_active=True,
                created_at=now,
            ),
            3: Employee(
                employee_id=3,
                employee_key="OPR001",
                first_name="Op",
                last_name="Main",
                middle_name=None,
                phone="+79990000003",
                email="operator@example.com",
                position="Operator",
                password_hash="hash",
                availability_status=AvailabilityStatus.AVAILABLE,
                is_active=True,
                created_at=now,
            ),
            4: Employee(
                employee_id=4,
                employee_key="CHIEF001",
                first_name="Chief",
                last_name="Main",
                middle_name=None,
                phone="+79990000004",
                email="chief@example.com",
                position="Chief engineer",
                password_hash="hash",
                availability_status=AvailabilityStatus.AVAILABLE,
                is_active=True,
                created_at=now,
            ),
        }
        self.tasks: dict[int, SimpleNamespace] = {
            11: SimpleNamespace(
                task_id=11,
                request_id=201,
                facility_id=1,
                assigned_engineer_id=1,
                created_by_employee_id=3,
                description="Task for engineer 1",
                operator_comment=None,
                status=TaskStatus.ACTIVE,
                created_at=now,
                started_at=None,
                completed_at=None,
            ),
            12: SimpleNamespace(
                task_id=12,
                request_id=202,
                facility_id=2,
                assigned_engineer_id=2,
                created_by_employee_id=3,
                description="Task for engineer 2",
                operator_comment=None,
                status=TaskStatus.CREATED,
                created_at=now,
                started_at=None,
                completed_at=None,
            ),
        }
        self.reports: dict[int, SimpleNamespace] = {}
        self.requests: list[dict[str, Any]] = [
            {
                "request_id": 201,
                "user_id": 100,
                "facility_id": 1,
                "title": "Leak in hall",
                "description": "Need fix",
                "status": "CREATED",
                "created_at": now,
            },
            {
                "request_id": 202,
                "user_id": 101,
                "facility_id": 2,
                "title": "Noise in room",
                "description": "Need check",
                "status": "ACTIVE",
                "created_at": now,
            },
        ]
        self.request_objects: dict[int, SimpleNamespace] = {
            201: SimpleNamespace(
                request_id=201,
                user_id=100,
                facility_id=1,
                title="Leak in hall",
                description="Need fix",
                status=RequestStatus.CREATED,
                created_at=now,
            ),
            202: SimpleNamespace(
                request_id=202,
                user_id=101,
                facility_id=2,
                title="Noise in room",
                description="Need check",
                status=RequestStatus.ACTIVE,
                created_at=now,
            ),
        }
        self.facilities: list[dict[str, Any]] = [
            {
                "id": 1,
                "name": "Facility One",
                "type": "Sports hall",
                "address": "Main st 1",
                "status": "ACTIVE",
                "latitude": 55.75,
                "longitude": 37.61,
            },
            {
                "id": 2,
                "name": "Facility Two",
                "type": "Pool",
                "address": "Main st 2",
                "status": "ACTIVE",
                "latitude": 55.76,
                "longitude": 37.62,
            },
        ]

    def query(self, model: type) -> DummyQuery:
        return DummyQuery(self, model)

    def get(self, model: type, identifier: Any) -> Any:
        if model.__name__ == "User":
            return self.users.get(int(identifier))
        if model.__name__ == "Employee":
            return self.employees.get(int(identifier))
        if model.__name__ == "EngineerTask":
            return self.tasks.get(int(identifier))
        if model.__name__ == "UserRequest":
            return self.request_objects.get(int(identifier))
        if model.__name__ == "SportsFacility":
            for row in self.facilities:
                if row["id"] == int(identifier):
                    return SimpleNamespace(
                        facility_id=row["id"],
                        name=row["name"],
                        facility_type=row["type"],
                        address=row["address"],
                        status=row["status"],
                        latitude=row["latitude"],
                        longitude=row["longitude"],
                        description="test description",
                        opening_date=None,
                        created_at=datetime.now(UTC),
                    )
            return None
        return None

    def execute(self, query: Any, params: dict[str, Any] | None = None) -> DummyResult:
        sql = str(query)
        params = params or {}

        if "FROM sports_facilities" in sql and "facility_id AS id" in sql:
            return DummyResult(self.facilities)

        if "COUNT(*) AS total_tasks" in sql and "FROM engineer_tasks" in sql:
            employee_id = int(params["employee_id"])
            rows = [t for t in self.tasks.values() if t.assigned_engineer_id == employee_id]
            total = len(rows)
            active = sum(1 for t in rows if str(t.status.value) == "ACTIVE")
            completed = sum(1 for t in rows if str(t.status.value) == "COMPLETED")
            created = sum(1 for t in rows if str(t.status.value) == "CREATED")
            cancelled = sum(1 for t in rows if str(t.status.value) == "CANCELLED")
            return DummyResult(
                [
                    {
                        "total_tasks": total,
                        "active_tasks": active,
                        "completed_tasks": completed,
                        "created_tasks": created,
                        "cancelled_tasks": cancelled,
                    }
                ]
            )

        if "FROM engineer_tasks et" in sql and "request_title" in sql:
            employee_id = int(params["employee_id"])
            rows: list[dict[str, Any]] = []
            for task in self.tasks.values():
                if task.assigned_engineer_id != employee_id:
                    continue
                rows.append(
                    {
                        "task_id": task.task_id,
                        "request_id": task.request_id,
                        "request_title": f"Request {task.request_id}",
                        "facility_id": task.facility_id,
                        "facility_name": f"Facility {task.facility_id}",
                        "facility_address": f"Address {task.facility_id}",
                        "description": task.description,
                        "operator_comment": task.operator_comment,
                        "status": task.status.value,
                        "created_at": task.created_at,
                        "started_at": task.started_at,
                        "completed_at": task.completed_at,
                    }
                )
            return DummyResult(rows)

        if "FROM user_requests ur" in sql and "WHERE ur.user_id = :user_id" in sql:
            user_id = int(params["user_id"])
            rows = [row for row in self.requests if int(row["user_id"]) == user_id]
            return DummyResult(rows)

        if "SELECT task_id FROM engineer_tasks WHERE request_id = :request_id" in sql:
            request_id = int(params["request_id"])
            for task in self.tasks.values():
                if int(task.request_id) == request_id:
                    return DummyResult([{"task_id": task.task_id}])
            return DummyResult([])

        if "FROM employees" in sql and "employee_id AS id" in sql:
            rows = []
            for emp in self.employees.values():
                rows.append(
                    {
                        "id": emp.employee_id,
                        "name": f"{emp.last_name} {emp.first_name}",
                        "phone": emp.phone or "",
                        "email": emp.email,
                        "position": emp.position,
                    }
                )
            return DummyResult(rows)

        return DummyResult([])

    def add(self, *_: Any, **__: Any) -> None:
        return None

    def add_all(self, *_: Any, **__: Any) -> None:
        return None

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        return None

    def refresh(self, *_: Any) -> None:
        return None

    def rollback(self) -> None:
        return None


@pytest.fixture(autouse=True)
def disable_background_autogen() -> None:
    settings.sensor_autogen_enabled = False
    settings.enable_bff_cache = False
    settings.enable_request_metrics = False


@pytest.fixture
def dummy_db() -> DummyDB:
    return DummyDB()


@pytest.fixture
def client(dummy_db: DummyDB):
    def override_get_db():
        yield dummy_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def tokens() -> dict[str, str]:
    user_token = create_access_token(subject=100, account_type=AccountType.USER.value, roles=["USER"])
    engineer_token = create_access_token(subject=1, account_type=AccountType.EMPLOYEE.value, roles=["ENGINEER"])
    engineer2_token = create_access_token(subject=2, account_type=AccountType.EMPLOYEE.value, roles=["ENGINEER"])
    operator_token = create_access_token(subject=3, account_type=AccountType.EMPLOYEE.value, roles=["OPERATOR"])
    chief_token = create_access_token(subject=4, account_type=AccountType.EMPLOYEE.value, roles=["CHIEF_ENGINEER"])
    admin_token = create_access_token(subject=4, account_type=AccountType.EMPLOYEE.value, roles=["ADMIN"])
    refresh_token = create_refresh_token(subject=100, account_type=AccountType.USER.value, roles=["USER"])
    return {
        "user": user_token,
        "engineer": engineer_token,
        "engineer2": engineer2_token,
        "operator": operator_token,
        "chief": chief_token,
        "admin": admin_token,
        "refresh": refresh_token,
    }


@pytest.fixture
def auth_header() -> Any:
    def _make(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture
def fake_background_job() -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        job_id=uuid4(),
        owner_id=1,
        owner_type=AccountType.EMPLOYEE,
        task_id=11,
        task_name="generate_engineer_report_delayed",
        status=BackgroundJobStatus.PENDING,
        payload={"task_id": 11, "delay_seconds": 5},
        result=None,
        error=None,
        created_at=now,
        started_at=None,
        finished_at=None,
        updated_at=now,
    )
