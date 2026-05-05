from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.sanitizer import sanitize_text
from app.models.engineer_report import EngineerReport


class ReportService:
    _EXTENSION_CONTENT_TYPES: dict[str, str] = {
        ".pdf": "application/pdf",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".txt": "text/plain; charset=utf-8",
        ".md": "text/plain; charset=utf-8",
        ".rtf": "application/rtf",
        ".csv": "text/csv; charset=utf-8",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }
    _INLINE_PREVIEW_MIME_PREFIXES: tuple[str, ...] = (
        "image/jpeg",
        "image/png",
        "text/plain",
        "text/csv",
    )
    _INLINE_PREVIEW_MIME_EXACT: set[str] = {"application/pdf"}

    DEFAULT_TEMPLATE_TEXT = """Engineer Report Template

Task ID:
Facility:
Engineer:
Start Time:
Finish Time:
Work Performed:
Detected Issues:
Used Parts and Materials:
Result:
Recommendations:
Attachments:
Signature:
Date:
"""

    @staticmethod
    def _storage_root() -> Path:
        base = Path(settings.reports_storage_dir)
        if not base.is_absolute():
            base = Path.cwd() / base
        return base.resolve()

    @classmethod
    def _templates_dir(cls) -> Path:
        return cls._storage_root() / "templates"

    @classmethod
    def _uploads_dir(cls) -> Path:
        return cls._storage_root() / "uploads"

    @classmethod
    def ensure_template_exists(cls) -> Path:
        templates_dir = cls._templates_dir()
        templates_dir.mkdir(parents=True, exist_ok=True)
        template_name = Path(settings.report_template_filename).name or "engineer_report_template.txt"
        template_path = templates_dir / template_name
        if not template_path.exists():
            extension = template_path.suffix.lower()
            if extension in {".txt", ".md", ".csv", ".rtf"}:
                template_path.write_text(cls.DEFAULT_TEMPLATE_TEXT, encoding="utf-8")
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Report template file is missing: {template_name}",
                )
        return template_path

    @classmethod
    def template_media_type(cls, template_path: Path) -> str:
        return cls.resolve_safe_content_type(filename=template_path.name)

    @staticmethod
    def _sanitize_filename(filename: str | None) -> str:
        original = Path((filename or "report.txt").strip()).name
        stem = Path(original).stem
        suffix = Path(original).suffix.lower()
        safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("._-")
        safe_stem = safe_stem or "report"
        safe_suffix = re.sub(r"[^A-Za-z0-9.]+", "", suffix).lower()
        return f"{safe_stem}{safe_suffix}"

    @staticmethod
    def _validate_extension(filename: str) -> str:
        extension = Path(filename).suffix.lower()
        if extension not in set(settings.reports_allowed_extensions):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported report file extension: {extension or '<none>'}",
            )
        return extension

    @classmethod
    def _safe_content_type_for_extension(cls, extension: str) -> str:
        return cls._EXTENSION_CONTENT_TYPES.get(extension.lower(), "application/octet-stream")

    @classmethod
    def resolve_safe_content_type(
        cls,
        *,
        filename: str | None,
        fallback: str | None = None,
    ) -> str:
        extension = Path(filename or "").suffix.lower()
        if extension:
            return cls._safe_content_type_for_extension(extension)
        if isinstance(fallback, str) and fallback.strip():
            normalized_fallback = fallback.strip().lower()
            allowed_values = {value.lower() for value in cls._EXTENSION_CONTENT_TYPES.values()}
            if normalized_fallback in allowed_values:
                return normalized_fallback
        return "application/octet-stream"

    @classmethod
    def is_inline_preview_content_type(cls, content_type: str | None) -> bool:
        if not content_type:
            return False
        normalized = content_type.strip().lower()
        if normalized in cls._INLINE_PREVIEW_MIME_EXACT:
            return True
        return any(normalized.startswith(prefix) for prefix in cls._INLINE_PREVIEW_MIME_PREFIXES)

    @classmethod
    def save_uploaded_file(cls, task_id: int, report_file: UploadFile) -> dict[str, object]:
        cls.ensure_template_exists()

        safe_filename = cls._sanitize_filename(report_file.filename)
        extension = cls._validate_extension(safe_filename)
        safe_content_type = cls._safe_content_type_for_extension(extension)

        task_dir = cls._uploads_dir() / f"task_{task_id}"
        task_dir.mkdir(parents=True, exist_ok=True)

        stored_filename = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex}{extension}"
        destination = task_dir / stored_filename

        max_size = settings.report_upload_max_size_bytes
        current_size = 0
        sha256 = hashlib.sha256()
        try:
            with destination.open("wb") as out:
                while True:
                    chunk = report_file.file.read(1024 * 1024)
                    if not chunk:
                        break
                    current_size += len(chunk)
                    if current_size > max_size:
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"Report file is too large. Max size: {max_size} bytes",
                        )
                    sha256.update(chunk)
                    out.write(chunk)
        except HTTPException:
            destination.unlink(missing_ok=True)
            raise
        except Exception as exc:  # noqa: BLE001
            destination.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save uploaded report file",
            ) from exc

        relative_path = destination.relative_to(cls._storage_root()).as_posix()
        return {
            "original_filename": safe_filename,
            "stored_filename": stored_filename,
            "stored_relative_path": relative_path,
            "content_type": safe_content_type,
            "size_bytes": current_size,
            "sha256": sha256.hexdigest(),
        }

    @classmethod
    def save_sample_text_file(
        cls,
        task_id: int,
        report_text: str,
        original_filename: str | None = None,
    ) -> dict[str, object]:
        cls.ensure_template_exists()

        safe_filename = cls._sanitize_filename(original_filename or f"sample_task_{task_id}.txt")
        extension = cls._validate_extension(safe_filename)

        payload = report_text.encode("utf-8")
        if len(payload) > settings.report_upload_max_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Sample report exceeds max size: {settings.report_upload_max_size_bytes} bytes",
            )

        task_dir = cls._uploads_dir() / f"task_{task_id}"
        task_dir.mkdir(parents=True, exist_ok=True)

        stored_filename = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex}{extension}"
        destination = task_dir / stored_filename
        destination.write_bytes(payload)

        relative_path = destination.relative_to(cls._storage_root()).as_posix()
        return {
            "original_filename": safe_filename,
            "stored_filename": stored_filename,
            "stored_relative_path": relative_path,
            "content_type": cls._safe_content_type_for_extension(extension),
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }

    @classmethod
    def metadata_to_text(
        cls,
        metadata: dict[str, object],
        uploaded_by_engineer_id: int,
        notes: str | None = None,
        idempotency_key: str | None = None,
    ) -> str:
        payload: dict[str, str | int | None] = {
            "source": "uploaded_file",
            "uploaded_by_engineer_id": uploaded_by_engineer_id,
            "uploaded_at": datetime.now(UTC).isoformat(),
            "original_filename": str(metadata["original_filename"]),
            "stored_filename": str(metadata["stored_filename"]),
            "stored_relative_path": str(metadata["stored_relative_path"]),
            "content_type": str(metadata["content_type"]),
            "size_bytes": int(metadata["size_bytes"]),
            "sha256": str(metadata["sha256"]) if metadata.get("sha256") else None,
            "notes": sanitize_text(notes),
            "idempotency_key": idempotency_key,
        }
        return json.dumps(payload, ensure_ascii=False)

    @classmethod
    def parse_uploaded_file_metadata(cls, report_text: str | None) -> dict[str, str | int | None] | None:
        if not report_text:
            return None
        try:
            parsed = json.loads(report_text)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
        if parsed.get("source") != "uploaded_file":
            return None
        if "stored_relative_path" not in parsed:
            return None
        return parsed

    @classmethod
    def _resolve_stored_file_path_from_metadata(cls, metadata: dict[str, object] | None) -> Path | None:
        if not metadata:
            return None

        relative_path = metadata.get("stored_relative_path")
        if not isinstance(relative_path, str) or not relative_path.strip():
            return None

        root = cls._storage_root()
        candidate = (root / relative_path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return None
        if not candidate.exists() or not candidate.is_file():
            return None
        return candidate

    @staticmethod
    def _file_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file_obj:
            while True:
                chunk = file_obj.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    @classmethod
    def _extract_sha256(cls, metadata: dict[str, object] | None) -> str | None:
        if not metadata:
            return None
        sha256 = metadata.get("sha256")
        if isinstance(sha256, str) and sha256.strip():
            return sha256.strip().lower()

        file_path = cls._resolve_stored_file_path_from_metadata(metadata)
        if file_path is None:
            return None
        try:
            return cls._file_sha256(file_path)
        except OSError:
            return None

    @staticmethod
    def _extract_size(metadata: dict[str, object] | None) -> int | None:
        if not metadata:
            return None
        size = metadata.get("size_bytes")
        if isinstance(size, int):
            return size
        if isinstance(size, str) and size.isdigit():
            return int(size)
        return None

    @classmethod
    def metadata_represents_same_file(
        cls,
        first: dict[str, object] | None,
        second: dict[str, object] | None,
    ) -> bool:
        first_hash = cls._extract_sha256(first)
        second_hash = cls._extract_sha256(second)
        first_size = cls._extract_size(first)
        second_size = cls._extract_size(second)
        if not first_hash or not second_hash:
            return False
        if first_size is None or second_size is None:
            return False
        return first_hash == second_hash and first_size == second_size

    @classmethod
    def delete_stored_file_by_metadata(cls, metadata: dict[str, object] | None) -> bool:
        file_path = cls._resolve_stored_file_path_from_metadata(metadata)
        if file_path is None:
            return False
        try:
            file_path.unlink(missing_ok=True)
            return True
        except OSError:
            return False

    @classmethod
    def resolve_stored_file_path(cls, report: EngineerReport) -> Path | None:
        metadata = cls.parse_uploaded_file_metadata(report.report_text)
        return cls._resolve_stored_file_path_from_metadata(metadata)

    @staticmethod
    def create_report(db: Session, task_id: int, engineer_id: int, report_text: str) -> EngineerReport:
        report = EngineerReport(task_id=task_id, engineer_id=engineer_id, report_text=report_text)
        db.add(report)
        db.commit()
        db.refresh(report)
        return report

    @staticmethod
    def upsert_report_text(
        db: Session,
        task_id: int,
        engineer_id: int,
        report_text: str,
        *,
        commit: bool = True,
    ) -> EngineerReport:
        report = db.query(EngineerReport).filter(EngineerReport.task_id == task_id).first()
        if report is None:
            report = EngineerReport(task_id=task_id, engineer_id=engineer_id, report_text=report_text)
        else:
            report.engineer_id = engineer_id
            report.report_text = report_text
        db.add(report)
        if commit:
            db.commit()
            db.refresh(report)
        else:
            db.flush()
        return report
