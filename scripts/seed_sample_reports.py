from datetime import UTC, datetime
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.session import SessionLocal
from app.models.engineer_task import EngineerTask
from app.services.report_service import ReportService


def seed_sample_reports(limit: int = 3) -> None:
    db = SessionLocal()
    try:
        tasks = db.query(EngineerTask).order_by(EngineerTask.task_id.asc()).limit(limit).all()
        if not tasks:
            print("No engineer tasks found. Nothing to seed.")
            return

        for task in tasks:
            sample_text = (
                "Sample engineer report\n"
                f"Task ID: {task.task_id}\n"
                f"Facility ID: {task.facility_id}\n"
                f"Assigned engineer ID: {task.assigned_engineer_id}\n"
                f"Seeded at (UTC): {datetime.now(UTC).isoformat()}\n"
                "Summary: Seeded sample report for frontend integration.\n"
            )
            metadata = ReportService.save_sample_text_file(
                task_id=task.task_id,
                report_text=sample_text,
                original_filename=f"seed_sample_task_{task.task_id}.txt",
            )
            report_text = ReportService.metadata_to_text(
                metadata=metadata,
                uploaded_by_engineer_id=task.assigned_engineer_id,
                notes="Seed script sample report",
            )
            report = ReportService.upsert_report_text(
                db=db,
                task_id=task.task_id,
                engineer_id=task.assigned_engineer_id,
                report_text=report_text,
            )
            print(f"Seeded report_id={report.report_id} for task_id={task.task_id}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_sample_reports()
