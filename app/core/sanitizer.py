from __future__ import annotations

from html import escape

try:
    import bleach  # type: ignore
except Exception:  # noqa: BLE001
    bleach = None


def sanitize_text(value: str | None) -> str | None:
    if value is None:
        return None
    if bleach is not None:
        cleaned = bleach.clean(value, tags=[], attributes={}, protocols=[], strip=True)
        return cleaned.strip()
    return escape(value).strip()
