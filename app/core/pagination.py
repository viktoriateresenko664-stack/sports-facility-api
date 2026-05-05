from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status

from app.core.config import settings


@dataclass(frozen=True)
class Pagination:
    page: int
    limit: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


def resolve_pagination(page: int | None, limit: int | None) -> Pagination | None:
    if page is None and limit is None:
        return None

    resolved_page = page or 1
    resolved_limit = limit or settings.pagination_default_limit
    if resolved_page < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="page must be >= 1")
    if resolved_limit < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="limit must be >= 1")
    if resolved_limit > settings.pagination_max_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"limit must be <= {settings.pagination_max_limit}",
        )
    return Pagination(page=resolved_page, limit=resolved_limit)
