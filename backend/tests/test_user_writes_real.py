"""POST /pantry, POST /saved với Supabase thật, 2 user: ghi + đọc lại trong 1 lượt (upsert kèm select).

Kiểm: đúng 1 request tới Supabase mỗi lần ghi; upsert trùng cặp không nhân đôi; phản hồi y như GET đọc lại;
RLS vẫn đúng (B không thấy / không ghi đè được dữ liệu của A).
"""

import asyncio

import httpx

from tests.real_users import app_on_shared_pool, saved_recipe_body, signed_in_users

CHICKEN_ID = 93  # Ức gà
REVIEWED_RECIPE_ID = 2648
HIDDEN_RECIPE_ID = 391  # Food.com chưa kiểm duyệt: RLS ẩn dòng recipes → diet_type None


async def _post_counting(
    client: httpx.AsyncClient, sent: list[httpx.Request], path: str, headers: dict[str, str], body: dict,
) -> tuple[httpx.Response, int]:
    before = len(sent)
    response = await client.post(path, headers=headers, json=body)
    return response, len(sent) - before


async def _check_pantry(client: httpx.AsyncClient, sent: list[httpx.Request], a: dict, b: dict) -> None:
    first, calls = await _post_counting(client, sent, "/pantry", a, {"ingredient_id": CHICKEN_ID, "quantity": 2, "unit": "miếng"})
    assert first.status_code == 201 and calls == 1
    again, calls = await _post_counting(client, sent, "/pantry", a, {"name": "ức gà", "expires_on": "2026-10-09"})
    assert again.status_code == 201 and calls == 2  # tên gõ tay: đọc danh mục + upsert
    assert again.json() == first.json() | {"expires_on": "2026-10-09"}  # cùng dòng, trường không gửi giữ nguyên
    assert (await client.get("/pantry", headers=a)).json() == [again.json()]  # không nhân đôi, giống GET

    b_item, _ = await _post_counting(client, sent, "/pantry", b, {"ingredient_id": CHICKEN_ID})
    assert b_item.status_code == 201 and b_item.json()["id"] != first.json()["id"]  # dòng riêng của B
    assert b_item.json()["quantity"] is None  # không đè / không thấy số lượng của A
    assert (await client.get("/pantry", headers=a)).json() == [again.json()]  # của A nguyên vẹn


async def _check_saved(client: httpx.AsyncClient, sent: list[httpx.Request], a: dict, b: dict) -> None:
    first, calls = await _post_counting(client, sent, "/saved", a, {"recipe": saved_recipe_body(REVIEWED_RECIPE_ID, "Bản 1")})
    assert first.status_code == 201 and calls == 1
    again, _ = await _post_counting(client, sent, "/saved", a, {"recipe": saved_recipe_body(REVIEWED_RECIPE_ID, "Bản 2")})
    assert again.json()["id"] == first.json()["id"] and again.json()["recipe"]["title"] == "Bản 2"
    assert again.json()["diet_type"] in ("omnivore", "vegetarian", "vegan")  # bảng nhúng recipes có trong 1 lượt
    assert (await client.get("/saved", headers=a)).json() == [again.json()]

    hidden, _ = await _post_counting(client, sent, "/saved", a, {"recipe": saved_recipe_body(HIDDEN_RECIPE_ID, "Ẩn")})
    assert hidden.status_code == 201 and hidden.json()["diet_type"] is None

    assert (await client.get("/saved", headers=b)).json() == []  # RLS: B không thấy món A lưu
    b_saved, _ = await _post_counting(client, sent, "/saved", b, {"recipe": saved_recipe_body(REVIEWED_RECIPE_ID, "Của B")})
    assert b_saved.json()["id"] != again.json()["id"]
    assert [s["recipe"]["title"] for s in (await client.get("/saved", headers=a)).json()] == ["Ẩn", "Bản 2"]


async def _run(a: dict[str, str], b: dict[str, str]) -> None:
    async with app_on_shared_pool() as (client, _shared_http, sent):
        await _check_pantry(client, sent, a, b)
        await _check_saved(client, sent, a, b)


def test_pantry_and_saved_write_in_one_request_keep_rls_and_dedupe() -> None:
    with signed_in_users("writes", 2) as (a, b):
        asyncio.run(_run(a, b))
