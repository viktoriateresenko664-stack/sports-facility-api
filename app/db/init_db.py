from datetime import date

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.background_job import BackgroundJob
from app.models.employee import Employee
from app.models.engineer_task import EngineerTask
from app.models.equipment import Equipment
from app.models.enums import (
    AccountType,
    AvailabilityStatus,
    BackgroundJobStatus,
    FacilityStatus,
    RequestStatus,
    SensorStatus,
    TaskStatus,
)
from app.models.sensor import Sensor
from app.models.role import EmployeeRole, Role, UserRole
from app.models.sports_facility import SportsFacility
from app.models.user import User
from app.models.user_request import UserRequest


TEST_PASSWORD = "Password123!"


def seed_roles(db: Session) -> dict[str, Role]:
    role_codes = ["USER", "ENGINEER", "OPERATOR", "CHIEF_ENGINEER", "ADMIN"]
    out: dict[str, Role] = {}
    for code in role_codes:
        role = db.query(Role).filter(Role.role_code == code).first()
        if not role:
            role = Role(role_code=code, role_name=code.title(), description=f"{code} role")
            db.add(role)
            db.flush()
        out[code] = role
    return out


def seed_users(db: Session, roles: dict[str, Role]) -> list[User]:
    users_data = [
        ("user1", "user1@test.com", TEST_PASSWORD, "+79000000001"),
        ("user2", "user2@test.com", TEST_PASSWORD, "+79000000002"),
    ]
    users: list[User] = []
    for username, email, password, phone in users_data:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                username=username,
                email=email,
                password_hash=get_password_hash(password),
                phone=phone,
                is_active=True,
            )
            db.add(user)
            db.flush()
        user.username = username
        user.phone = phone
        user.is_active = True
        user_role = db.query(UserRole).filter(
            UserRole.user_id == user.user_id,
            UserRole.role_id == roles["USER"].role_id,
        ).first()
        if not user_role:
            db.add(UserRole(user_id=user.user_id, role_id=roles["USER"].role_id))
        users.append(user)
    return users


def seed_employees(db: Session, roles: dict[str, Role]) -> list[Employee]:
    data = [
        ("ENG001", "Petr", "Sidorov", "A", "petr@sport.local", "Engineer", "ENGINEER"),
        ("ENG002", "Anna", "Smirnova", "B", "anna@sport.local", "Engineer", "ENGINEER"),
        ("OP001", "Sergey", "Volkov", "C", "sergey@sport.local", "Operator", "OPERATOR"),
        ("CH001", "Maria", "Kuznetsova", "D", "maria@sport.local", "Chief Engineer", "CHIEF_ENGINEER"),
        ("ADM001", "Alex", "Orlov", "E", "alex@sport.local", "Administrator", "ADMIN"),
    ]
    employees: list[Employee] = []
    for key, first, last, middle, email, position, role_code in data:
        created_now = False
        employee = db.query(Employee).filter(Employee.employee_key == key).first()
        if not employee:
            employee = db.query(Employee).filter(Employee.email == email).first()
        if not employee:
            created_now = True
            employee = Employee(
                employee_key=key,
                first_name=first,
                last_name=last,
                middle_name=middle,
                phone="+79001112233",
                email=email,
                position=position,
                password_hash=get_password_hash(TEST_PASSWORD),
                availability_status=AvailabilityStatus.AVAILABLE,
                is_active=True,
            )
            db.add(employee)
            db.flush()
        employee.employee_key = key
        employee.first_name = first
        employee.last_name = last
        employee.middle_name = middle
        employee.email = email
        employee.position = position
        # Keep existing password unchanged; set initial seed password only for newly created accounts.
        if created_now or not employee.password_hash:
            employee.password_hash = get_password_hash(TEST_PASSWORD)
        employee.availability_status = AvailabilityStatus.AVAILABLE
        employee.is_active = True
        db.query(EmployeeRole).filter(EmployeeRole.employee_id == employee.employee_id).delete(synchronize_session=False)
        db.add(EmployeeRole(employee_id=employee.employee_id, role_id=roles[role_code].role_id))
        employees.append(employee)
    return employees


def seed_facilities(db: Session) -> list[SportsFacility]:
    data = [
        (
            "Дворец спорта «Москвич»",
            "Дворец спорта",
            "ул. Люблинская, 15/46, стр. 7",
            "Многофункциональный комплекс: кёрлинг-центр, дворец бильярда, теннисные корты, футбольные поля, легкоатлетические сектора.",
            FacilityStatus.ACTIVE,
        ),
        (
            "Дворец спорта «Некрасовка»",
            "Дворец спорта",
            "ул. Покровская, 22",
            "Крупный спортивный кластер, открыт в 2023 году. Бассейны, залы хореографии, тренажёрный зал.",
            FacilityStatus.ACTIVE,
        ),
        (
            "Дворец спорта «Квант»",
            "Дворец спорта",
            "г. Троицк, Октябрьский пр-т, 16Б",
            "Современный комплекс в Троицком округе Москвы. Секции и группы для взрослых и детей.",
            FacilityStatus.ACTIVE,
        ),
        (
            "СК «Олимпийский»",
            "Спортивный комплекс",
            "Олимпийский пр-т, 16 (м. Проспект Мира)",
            "Закрыт на реконструкцию. Открытие планируется не ранее конца 2026 года.",
            FacilityStatus.MAINTENANCE,
        ),
        (
            "Дворец спорта «Динамо» (Крылатское)",
            "Дворец спорта",
            "ул. Островная, 7",
            "Крытый велотрек, ледовая арена, секции. Действующий олимпийский объект.",
            FacilityStatus.ACTIVE,
        ),
        (
            "УСК «Крылья Советов»",
            "Универсальный спортивный комплекс",
            "ул. Толбухина, 10-12, стр. 1",
            "Построен к Олимпиаде-80, до сих пор работает.",
            FacilityStatus.ACTIVE,
        ),
        (
            "Дворец спорта «Измайлово»",
            "Дворец спорта",
            "Сиреневый б-р, 2",
            "Один из крупнейших в мире дворцов для тяжёлой атлетики, также проводятся тренировки по другим видам спорта.",
            FacilityStatus.ACTIVE,
        ),
    ]
    coordinates: list[tuple[float | None, float | None]] = [
        (55.7070, 37.7303),
        (55.7088, 37.9286),
        (55.4874, 37.3080),
        (55.7828, 37.6200),
        (55.7639, 37.4303),
        (55.7233, 37.4008),
        (55.8063, 37.7809),
    ]
    facilities: list[SportsFacility] = []
    existing = db.query(SportsFacility).order_by(SportsFacility.facility_id.asc()).all()

    for idx, (name, ftype, address, description, status) in enumerate(data):
        latitude, longitude = coordinates[idx] if idx < len(coordinates) else (None, None)
        facility = existing[idx] if idx < len(existing) else None
        if facility is None:
            facility = SportsFacility(
                name=name,
                facility_type=ftype,
                address=address,
                latitude=latitude,
                longitude=longitude,
                description=description,
                opening_date=date(2020, 1, 1),
                status=status,
            )
            db.add(facility)
            db.flush()
        facility.name = name
        facility.facility_type = ftype
        facility.address = address
        facility.latitude = latitude
        facility.longitude = longitude
        facility.description = description
        facility.status = status
        db.add(facility)
        facilities.append(facility)

    # If there are extra old facilities, mark them as inactive to keep referential integrity.
    for extra in existing[len(data):]:
        extra.status = FacilityStatus.INACTIVE
        extra.description = (extra.description or "") + " [ARCHIVED_BY_SEED]"
        db.add(extra)

    return facilities


def seed_equipment_and_sensors(db: Session, facilities: list[SportsFacility]) -> None:
    if not facilities:
        return

    sensors_template = [
        ("TEMP", "temperature", "C"),
        ("HUM", "humidity", "%"),
        ("VOLT", "voltage", "V"),
        ("PRESS", "pressure", "bar"),
    ]

    for index, facility in enumerate(facilities, start=1):
        equipment_name = f"Центральный инженерный шкаф #{index}"
        equipment = (
            db.query(Equipment)
            .filter(
                Equipment.facility_id == facility.facility_id,
                Equipment.name == equipment_name,
            )
            .first()
        )
        if not equipment:
            equipment = Equipment(
                facility_id=facility.facility_id,
                name=equipment_name,
                equipment_type="Мониторинг",
                serial_number=f"RUS-CAB-{index:03d}",
                description=f"Базовый комплект мониторинга для объекта «{facility.name}».",
            )
            db.add(equipment)
            db.flush()

        for sensor_suffix, sensor_type, unit in sensors_template:
            sensor_code = f"SENS-{sensor_suffix}-{index:03d}"
            exists = db.query(Sensor).filter(Sensor.sensor_code == sensor_code).first()
            if exists:
                exists.equipment_id = equipment.equipment_id
                exists.sensor_type = sensor_type
                exists.unit = unit
                exists.status = SensorStatus.ACTIVE
                db.add(exists)
                continue

            db.add(
                Sensor(
                    equipment_id=equipment.equipment_id,
                    sensor_code=sensor_code,
                    sensor_type=sensor_type,
                    unit=unit,
                    status=SensorStatus.ACTIVE,
                )
            )


def seed_requests_tasks_jobs(db: Session, users: list[User], employees: list[Employee], facilities: list[SportsFacility]) -> None:
    if db.query(UserRequest).count() == 0:
        req1 = UserRequest(
            user_id=users[0].user_id,
            facility_id=facilities[0].facility_id,
            title="Noisy ventilation",
            description="Ventilation system makes unusual noise",
            status=RequestStatus.ASSIGNED,
        )
        req2 = UserRequest(
            user_id=users[1].user_id,
            facility_id=facilities[1].facility_id,
            title="Temperature issue",
            description="Temperature sensor on arena seems incorrect",
            status=RequestStatus.IN_WORK,
        )
        db.add_all([req1, req2])
        db.flush()

        task1 = EngineerTask(
            facility_id=facilities[0].facility_id,
            request_id=req1.request_id,
            created_by_employee_id=employees[2].employee_id,
            assigned_engineer_id=employees[0].employee_id,
            description="Inspect and fix ventilation",
            operator_comment="High priority",
            status=TaskStatus.CREATED,
        )
        task2 = EngineerTask(
            facility_id=facilities[1].facility_id,
            request_id=req2.request_id,
            created_by_employee_id=employees[2].employee_id,
            assigned_engineer_id=employees[1].employee_id,
            description="Calibrate temperature sensor",
            operator_comment="Check logs first",
            status=TaskStatus.ACTIVE,
        )
        db.add_all([task1, task2])
        db.flush()

        jobs = [
            BackgroundJob(
                owner_id=employees[0].employee_id,
                owner_type=AccountType.EMPLOYEE,
                task_id=task1.task_id,
                task_name="generate_engineer_report",
                status=BackgroundJobStatus.PENDING,
                payload={"task_id": task1.task_id},
            ),
            BackgroundJob(
                owner_id=employees[1].employee_id,
                owner_type=AccountType.EMPLOYEE,
                task_id=task2.task_id,
                task_name="generate_engineer_report",
                status=BackgroundJobStatus.SUCCESS,
                payload={"task_id": task2.task_id},
                result={"message": "ready"},
            ),
        ]
        db.add_all(jobs)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        roles = seed_roles(db)
        users = seed_users(db, roles)
        employees = seed_employees(db, roles)
        facilities = seed_facilities(db)
        seed_equipment_and_sensors(db, facilities)
        seed_requests_tasks_jobs(db, users, employees, facilities)
        db.commit()
        print("Seed completed")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
