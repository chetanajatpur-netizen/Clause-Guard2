"""Custom exceptions and FastAPI exception handlers."""
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class ClauseGuardError(Exception):
    """Base exception for ClauseWise."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


ClauseWiseError = ClauseGuardError


class FileValidationError(ClauseGuardError):
    """Raised when uploaded file fails validation."""

    def __init__(self, message: str) -> None:
        super().__init__(code="FILE_VALIDATION_ERROR", message=message, status_code=400)


class FileTooLargeError(ClauseGuardError):
    """Raised when uploaded file exceeds size limit."""

    def __init__(self, max_mb: int) -> None:
        super().__init__(
            code="FILE_TOO_LARGE",
            message=f"File exceeds maximum size of {max_mb} MB",
            status_code=413,
        )


class UnsupportedFileTypeError(ClauseGuardError):
    """Raised when file type is not supported."""

    def __init__(self, file_type: str) -> None:
        super().__init__(
            code="UNSUPPORTED_FILE_TYPE",
            message=f"Unsupported file type: {file_type}. Supported: PDF, DOCX, TXT",
            status_code=400,
        )


class NoTextExtractedError(ClauseGuardError):
    """Raised when no text could be extracted (e.g., scanned PDF)."""

    def __init__(self) -> None:
        super().__init__(
            code="NO_TEXT_EXTRACTED",
            message="No text could be extracted. The file may be a scanned PDF without OCR.",
            status_code=422,
        )


class DocumentNotFoundError(ClauseGuardError):
    """Raised when a document is not found."""

    def __init__(self, document_id: str) -> None:
        super().__init__(
            code="DOCUMENT_NOT_FOUND",
            message=f"Document {document_id} not found",
            status_code=404,
        )


class ModelNotLoadedError(ClauseGuardError):
    """Raised when ML model is not loaded."""

    def __init__(self) -> None:
        super().__init__(
            code="MODEL_NOT_LOADED",
            message="ML model is not loaded. Please check server startup logs.",
            status_code=503,
        )


from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers with FastAPI app."""

    @app.exception_handler(ClauseGuardError)
    async def clauseguard_error_handler(
        request: Request, exc: ClauseGuardError
    ) -> JSONResponse:
        logger.warning("ClauseGuard error: %s - %s", exc.code, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code_map = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            413: "FILE_TOO_LARGE",
            422: "UNPROCESSABLE_ENTITY",
            500: "INTERNAL_ERROR",
            502: "BAD_GATEWAY",
            503: "SERVICE_UNAVAILABLE",
        }
        code = code_map.get(exc.status_code, f"HTTP_{exc.status_code}")
        detail_msg = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": code, "message": detail_msg}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = exc.errors()
        msg = errors[0].get("msg", "Validation error") if errors else "Validation error"
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "VALIDATION_ERROR", "message": msg}},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(exc) if str(exc) else "An unexpected error occurred",
                }
            },
        )

