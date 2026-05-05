from sqlalchemy.orm import Session

from app.models.employee import Employee


class EmployeeRepository:
    def get_by_id(self, db: Session, employee_id: int) -> Employee | None:
        return db.get(Employee, employee_id)

    def get_by_employee_key(self, db: Session, employee_key: str) -> Employee | None:
        return db.query(Employee).filter(Employee.employee_key == employee_key).first()

    def create(self, db: Session, employee: Employee) -> Employee:
        db.add(employee)
        db.flush()
        return employee
