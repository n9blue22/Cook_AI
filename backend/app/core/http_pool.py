"""Pool HTTP dùng chung ra Supabase: giữ kết nối rảnh lâu hơn mặc định 5 s của httpx (đỡ bắt tay TCP + TLS lại),
và GET gặp kết nối cũ đã bị phía bên kia đóng thì tự thử lại 1 lần."""

import logging

import httpx

# Đo 2026-10-02 (feature-spec mục Hiệu năng): kết nối rảnh tới Supabase vẫn tái dùng được ≥ 120 s → ~2/3, trần 60 s.
KEEPALIVE_EXPIRY_SEC = 60.0
MAX_CONNECTIONS, MAX_KEEPALIVE_CONNECTIONS = 100, 20  # như mặc định của httpx.AsyncClient
STALE_CONNECTION_ERRORS = (httpx.RemoteProtocolError, httpx.ReadError)
RETRYABLE_METHOD = "GET"  # POST/PATCH/DELETE có thể đã tới server → không tự gửi lại

logger = logging.getLogger(__name__)


class RetryStaleGetTransport(httpx.AsyncBaseTransport):
    """Bọc transport thật: GET lỗi vì kết nối cũ bị đóng → gửi lại đúng 1 lần (pool tự bỏ kết nối hỏng, mở cái mới)."""

    def __init__(self, inner: httpx.AsyncBaseTransport) -> None:
        self._inner = inner

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        try:
            return await self._inner.handle_async_request(request)
        except STALE_CONNECTION_ERRORS as error:
            if request.method != RETRYABLE_METHOD:
                raise
            logger.warning("GET %s gặp kết nối cũ đã đóng (%s) → thử lại 1 lần", request.url.path, type(error).__name__)
            return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


def create_shared_http_client(timeout_sec: float, http2: bool = False) -> httpx.AsyncClient:
    """httpx.AsyncClient dùng chung, không header mặc định nào (token luôn gắn theo từng request)."""
    limits = httpx.Limits(
        max_connections=MAX_CONNECTIONS, max_keepalive_connections=MAX_KEEPALIVE_CONNECTIONS,
        keepalive_expiry=KEEPALIVE_EXPIRY_SEC,
    )
    transport = RetryStaleGetTransport(httpx.AsyncHTTPTransport(limits=limits, http2=http2))
    return httpx.AsyncClient(timeout=timeout_sec, transport=transport)
