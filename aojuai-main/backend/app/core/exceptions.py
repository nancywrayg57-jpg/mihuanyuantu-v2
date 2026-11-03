"""
AOJU Backend - Custom Exceptions
"""
from typing import Any


class AOJUException(Exception):
    """Base exception for AOJU"""

    def __init__(
        self,
        message: str = "An error occurred",
        code: str = "ERROR",
        status_code: int = 500,
        details: Any = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class NotFoundError(AOJUException):
    """Resource not found

    Backward compatible with callers that pass `resource` and `resource_id`.
    """

    def __init__(
        self,
        message: str = "Resource not found",
        details: Any = None,
        resource: str | None = None,
        resource_id: Any = None,
    ):
        resolved_message = message
        resolved_details = details

        if resource is not None:
            if message == "Resource not found":
                resolved_message = (
                    f"{resource} not found"
                    if resource_id is None
                    else f"{resource} not found: {resource_id}"
                )

            if resolved_details is None:
                resolved_details = {"resource": resource, "resource_id": resource_id}

        super().__init__(
            message=resolved_message,
            code="NOT_FOUND",
            status_code=404,
            details=resolved_details,
        )


class ValidationError(AOJUException):
    """Validation error"""

    def __init__(self, message: str = "Validation failed", details: Any = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            details=details,
        )


class UnauthorizedError(AOJUException):
    """Authentication required"""

    def __init__(self, message: str = "Not authenticated", details: Any = None):
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=401,
            details=details,
        )


class ForbiddenError(AOJUException):
    """Permission denied"""

    def __init__(self, message: str = "Permission denied", details: Any = None):
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=403,
            details=details,
        )


class TooManyRequestsError(AOJUException):
    """Rate limit exceeded."""

    def __init__(self, message: str = "Too many requests", details: Any = None):
        super().__init__(
            message=message,
            code="TOO_MANY_REQUESTS",
            status_code=429,
            details=details,
        )


class ConflictError(AOJUException):
    """Resource conflict"""

    def __init__(self, message: str = "Resource conflict", details: Any = None):
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=409,
            details=details,
        )


class BusinessError(AOJUException):
    """Business logic error"""

    def __init__(self, message: str = "Business error", code: str = "BUSINESS_ERROR", details: Any = None):
        super().__init__(
            message=message,
            code=code,
            status_code=400,
            details=details,
        )


class FeatureDisabledError(AOJUException):
    """Tenant-level feature/module is disabled"""

    def __init__(
        self,
        feature: str,
        message: str | None = None,
        details: Any = None,
    ):
        super().__init__(
            message=message or f"Feature '{feature}' is disabled",
            code="FEATURE_DISABLED",
            status_code=403,
            details=details if details is not None else {"feature": feature},
        )
