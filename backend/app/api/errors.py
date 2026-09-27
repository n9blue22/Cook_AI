"""Handler lỗi dùng chung: không bao giờ trả stack trace, tên bảng, câu SQL hay đường dẫn file ra client.
Chi tiết chỉ ghi log phía server."""

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.services.auth_service import AuthError
from app.services.auth_tokens import UnauthenticatedError
from app.services.rate_limit import RateLimitedError

logger = logging.getLogger(__name__)

INTERNAL_ERROR_MESSAGE = "Lỗi hệ thống, thử lại sau"
UNAUTHENTICATED_MESSAGE = "Cần đăng nhập để dùng tính năng này"
# Trường lỗi validation được trả client; bỏ "input" (có thể là mật khẩu vừa gõ), "ctx", "url".
SAFE_VALIDATION_FIELDS = ("loc", "msg", "type")


def register_common_error_handlers(app: FastAPI) -> None:
    """Gắn handler cho lỗi auth, rate limit, validation và mọi lỗi chưa bắt."""
    app.add_exception_handler(AuthError, _auth_error)
    app.add_exception_handler(UnauthenticatedError, _unauthenticated)
    app.add_exception_handler(RateLimitedError, _rate_limited)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unhandled)


async def _auth_error(request: Request, error: AuthError) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content={"detail": str(error)})


async def _unauthenticated(request: Request, error: UnauthenticatedError) -> JSONResponse:
    logger.info("401 %s %s: %s", request.method, request.url.path, error)
    return JSONResponse(
        status_code=401, content={"detail": UNAUTHENTICATED_MESSAGE}, headers={"WWW-Authenticate": "Bearer"},
    )


async def _rate_limited(request: Request, error: RateLimitedError) -> JSONResponse:
    return JSONResponse(
        status_code=429, content={"detail": str(error)}, headers={"Retry-After": str(error.retry_after)},
    )


async def _validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    errors = [{key: item[key] for key in SAFE_VALIDATION_FIELDS if key in item} for item in error.errors()]
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})


async def _unhandled(request: Request, error: Exception) -> JSONResponse:
    logger.exception("Lỗi chưa xử lý %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": INTERNAL_ERROR_MESSAGE})
