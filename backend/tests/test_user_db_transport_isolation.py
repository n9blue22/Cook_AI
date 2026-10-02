"""Chống rò rỉ token ở mức giao vận: 2 user dùng CHUNG 1 httpx.AsyncClient (vai trò main.lifespan), xen kẽ thật.

Mỗi người dựng client PostgREST (auth_tokens.user_db) rồi `await` tới khi người kia cũng dựng xong mới gửi; transport
giả ghi lại header Authorization nhận được. Nếu token nằm ở header mặc định của client dùng chung, người dựng sau
sẽ đè lên người dựng trước → request của A mang token của B → test fail. Không gọi mạng.
"""

import asyncio

import httpx

from app.services.auth_tokens import CurrentUser, user_db

SUPABASE_URL, PUBLISHABLE_KEY = "https://example.supabase.co", "pk-test"
USERS = {"a": CurrentUser(id="user-a", access_token="token-a"), "b": CurrentUser(id="user-b", access_token="token-b")}
ROUNDS = 5


async def _call_as(name: str, http: httpx.AsyncClient, all_built: asyncio.Barrier) -> None:
    db = user_db(SUPABASE_URL, PUBLISHABLE_KEY, USERS[name], http)
    await all_built.wait()  # người kia dựng header xong rồi mới gửi
    await db.from_(f"probe_{name}").select("*").execute()  # tên bảng cho transport biết ai là người gọi


async def _run() -> tuple[list[tuple[str, str | None]], httpx.Headers]:
    received: list[tuple[str, str | None]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0)  # nhường event loop giữa lúc nhận và lúc trả lời → các request chồng lên nhau
        caller = request.url.path.rsplit("probe_", 1)[1]
        received.append((caller, request.headers.get("authorization")))
        return httpx.Response(200, json=[])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as shared_http:
        for _ in range(ROUNDS):
            barrier = asyncio.Barrier(len(USERS))
            await asyncio.gather(*(_call_as(name, shared_http, barrier) for name in USERS))
        return received, shared_http.headers


def test_each_request_carries_its_callers_token_when_users_interleave() -> None:
    received, shared_headers = asyncio.run(_run())
    assert len(received) == ROUNDS * len(USERS)
    for caller, authorization in received:
        assert authorization == f"Bearer {USERS[caller].access_token}", f"request của {caller} mang {authorization}"
    assert "authorization" not in shared_headers  # pool dùng chung không bao giờ mang token
