"""Standard response envelope (docs/api-guidelines.md)."""

from typing import Any

from pydantic import BaseModel

from app.core.context import request_id_ctx


class ErrorItem(BaseModel):
    code: str
    message: str
    field: str | None = None


class Meta(BaseModel):
    request_id: str | None = None
    page: int | None = None
    page_size: int | None = None
    total: int | None = None


class Envelope[T](BaseModel):
    data: T | None = None
    meta: Meta = Meta()
    errors: list[ErrorItem] = []


def success(data: Any, *, page: int | None = None, page_size: int | None = None,
            total: int | None = None) -> dict:
    return {
        "data": data,
        "meta": {
            "request_id": request_id_ctx.get(),
            **({"page": page, "page_size": page_size, "total": total}
               if page is not None else {}),
        },
        "errors": [],
    }


def failure(code: str, message: str, *, field: str | None = None,
            errors: list[dict] | None = None) -> dict:
    return {
        "data": None,
        "meta": {"request_id": request_id_ctx.get()},
        "errors": errors or [{"code": code, "message": message,
                              **({"field": field} if field else {})}],
    }
