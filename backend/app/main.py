import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from app.schemas.envelope import failure

logger = logging.getLogger("app")

_HTTP_CODE_MAP = {
    400: "VALIDATION_ERROR",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "BUSINESS_RULE_VIOLATION",
    429: "RATE_LIMITED",
}


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/api/docs" if not settings.is_production else None,
        openapi_url="/api/openapi.json" if not settings.is_production else None,
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=failure(exc.code, exc.message, field=exc.field),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {
                "code": "VALIDATION_ERROR",
                "message": e.get("msg", "Invalid value"),
                "field": ".".join(str(loc) for loc in e.get("loc", []) if loc != "body"),
            }
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=400,
            content=failure("VALIDATION_ERROR", "Request validation failed", errors=errors),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = _HTTP_CODE_MAP.get(exc.status_code, "INTERNAL_ERROR")
        return JSONResponse(
            status_code=exc.status_code, content=failure(code, str(exc.detail))
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=failure("INTERNAL_ERROR", "An unexpected error occurred"),
        )

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
