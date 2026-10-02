"""http_pool.RetryStaleGetTransport: GET gặp kết nối cũ đã đóng thì thử lại đúng 1 lần; POST không bao giờ gửi lại."""

import asyncio

import httpx
import pytest

from app.core.http_pool import RetryStaleGetTransport


def _flaky_transport(failures: int, error: type[httpx.TransportError]) -> tuple[RetryStaleGetTransport, list[str]]:
    """Transport thật bị thay bằng transport giả: `failures` lượt đầu ném `error`, sau đó trả 200."""
    attempts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request.method)
        if len(attempts) <= failures:
            raise error("kết nối cũ đã bị đóng", request=request)
        return httpx.Response(200)

    return RetryStaleGetTransport(httpx.MockTransport(handler)), attempts


async def _send(transport: RetryStaleGetTransport, method: str) -> httpx.Response:
    async with httpx.AsyncClient(transport=transport) as client:
        return await client.request(method, "https://example.supabase.co/rest/v1/pantry")


@pytest.mark.parametrize("error", [httpx.RemoteProtocolError, httpx.ReadError])
def test_get_retries_once_on_stale_connection(error: type[httpx.TransportError]) -> None:
    transport, attempts = _flaky_transport(failures=1, error=error)
    assert asyncio.run(_send(transport, "GET")).status_code == 200
    assert attempts == ["GET", "GET"]


def test_get_gives_up_after_one_retry() -> None:
    transport, attempts = _flaky_transport(failures=2, error=httpx.RemoteProtocolError)
    with pytest.raises(httpx.RemoteProtocolError):
        asyncio.run(_send(transport, "GET"))
    assert attempts == ["GET", "GET"]


def test_post_is_never_retried() -> None:
    transport, attempts = _flaky_transport(failures=1, error=httpx.RemoteProtocolError)
    with pytest.raises(httpx.RemoteProtocolError):
        asyncio.run(_send(transport, "POST"))
    assert attempts == ["POST"]


def test_other_transport_errors_are_not_retried() -> None:
    transport, attempts = _flaky_transport(failures=1, error=httpx.ConnectTimeout)
    with pytest.raises(httpx.ConnectTimeout):
        asyncio.run(_send(transport, "GET"))
    assert attempts == ["GET"]
