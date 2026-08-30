"""Application error hierarchy mapped to the standard error envelope.

Services raise these; API handlers in app.main translate them. Route handlers
should not raise HTTPException directly for business failures.
"""


class AppError(Exception):
    status_code = 500
    code = "INTERNAL_ERROR"

    def __init__(self, message: str = "", *, field: str | None = None):
        super().__init__(message or self.code)
        self.message = message or self.code
        self.field = field


class ValidationAppError(AppError):
    status_code = 400
    code = "VALIDATION_ERROR"


class UnauthenticatedError(AppError):
    status_code = 401
    code = "UNAUTHENTICATED"


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"


class BusinessRuleError(AppError):
    status_code = 422
    code = "BUSINESS_RULE_VIOLATION"


class RateLimitedError(AppError):
    status_code = 429
    code = "RATE_LIMITED"
