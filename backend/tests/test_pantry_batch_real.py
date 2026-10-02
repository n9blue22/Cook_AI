"""POST /pantry/batch với Supabase thật, 2 user: 1 lượt upsert, tên map qua cache danh mục, mục lạ không làm hỏng
cả lô, mục trùng được gộp, trường không gửi giữ nguyên, RLS đúng, lô sai kích thước / kiểu → 422."""

import asyncio

import httpx

from tests.real_users import app_on_shared_pool, signed_in_users

CHICKEN_ID = 93  # Ức gà
OTHER_ID = 16
MISSING_ID = 999_999_999
MAX_ITEMS = 50


def _upserts(sent: list[httpx.Request], since: int) -> list[httpx.Request]:
    return [r for r in sent[since:] if r.method == "POST" and r.url.path.endswith("/pantry_items")]


async def _check_mixed_batch(client: httpx.AsyncClient, sent: list[httpx.Request], a: dict) -> None:
    before = len(sent)
    body = {"items": [
        {"ingredient_id": CHICKEN_ID, "quantity": 2, "unit": "miếng"},
        {"name": "xyzzy không phải đồ ăn"},
        {"ingredient_id": MISSING_ID},
        {"ingredient_id": OTHER_ID},
        {"name": "ức gà", "expires_on": "2026-10-09"},  # trùng CHICKEN_ID → gộp, mục sau ghi đè trường nó gửi
    ]}
    response = await client.post("/pantry/batch", headers=a, json=body)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["unmatched_names"] == ["xyzzy không phải đồ ăn"] and result["unknown_ids"] == [MISSING_ID]
    chicken, other = result["items"]
    assert (chicken["ingredient_id"], chicken["name"], chicken["quantity"], chicken["unit"], chicken["expires_on"]) == (
        CHICKEN_ID, "Ức gà", 2, "miếng", "2026-10-09")
    assert other["ingredient_id"] == OTHER_ID and other["quantity"] is None
    assert len(_upserts(sent, before)) == 1  # đúng 1 lượt upsert cho cả lô
    assert sorted((await client.get("/pantry", headers=a)).json(), key=lambda i: i["id"]) == sorted(
        result["items"], key=lambda i: i["id"])  # không nhân đôi, giống GET


async def _check_unsent_fields_kept(client: httpx.AsyncClient, sent: list[httpx.Request], a: dict) -> None:
    """Lô chỉ gửi id (ca Confirm) và lô lẫn lộn trường: số lượng / hạn đã có không bị ghi null."""
    only_ids = await client.post("/pantry/batch", headers=a, json={"items": [{"ingredient_id": CHICKEN_ID}]})
    assert only_ids.json()["items"][0]["quantity"] == 2
    before = len(sent)
    mixed = await client.post("/pantry/batch", headers=a, json={"items": [
        {"ingredient_id": OTHER_ID, "quantity": 5}, {"ingredient_id": CHICKEN_ID, "unit": "khay"}]})
    other, chicken = mixed.json()["items"]
    assert other["quantity"] == 5 and other["unit"] is None
    assert (chicken["quantity"], chicken["unit"], chicken["expires_on"]) == (2, "khay", "2026-10-09")
    assert len(_upserts(sent, before)) == 1


async def _check_rls(client: httpx.AsyncClient, a: dict, b: dict) -> None:
    a_before = (await client.get("/pantry", headers=a)).json()
    b_result = (await client.post("/pantry/batch", headers=b, json={"items": [{"ingredient_id": CHICKEN_ID}]})).json()
    assert b_result["items"][0]["quantity"] is None  # dòng riêng của B, không thấy số lượng của A
    assert b_result["items"][0]["id"] not in {item["id"] for item in a_before}
    assert (await client.get("/pantry", headers=a)).json() == a_before  # của A nguyên vẹn
    assert [i["ingredient_id"] for i in (await client.get("/pantry", headers=b)).json()] == [CHICKEN_ID]


async def _check_rejects(client: httpx.AsyncClient, a: dict) -> None:
    too_many = {"items": [{"ingredient_id": CHICKEN_ID}] * (MAX_ITEMS + 1)}
    bad_bodies = [
        too_many, {"items": []}, {"items": [{"ingredient_id": "abc"}]}, {"items": [{"name": "x" * 101}]},
        {"items": [{"ingredient_id": CHICKEN_ID, "name": "ức gà"}]}, {"items": [{"quantity": 1}]}, {},
    ]
    for body in bad_bodies:
        assert (await client.post("/pantry/batch", headers=a, json=body)).status_code == 422, body
    full = {"items": [{"ingredient_id": CHICKEN_ID}] * MAX_ITEMS}
    assert (await client.post("/pantry/batch", headers=a, json=full)).status_code == 200  # đúng 50 thì nhận
    all_bad = await client.post("/pantry/batch", headers=a, json={"items": [{"name": "xyzzy"}, {"ingredient_id": MISSING_ID}]})
    assert all_bad.json() == {"items": [], "unmatched_names": ["xyzzy"], "unknown_ids": [MISSING_ID]}
    assert (await client.post("/pantry/batch", json={"items": [{"ingredient_id": CHICKEN_ID}]})).status_code == 401


async def _run(a: dict[str, str], b: dict[str, str]) -> None:
    async with app_on_shared_pool() as (client, _shared_http, sent):
        await _check_mixed_batch(client, sent, a)
        await _check_unsent_fields_kept(client, sent, a)
        await _check_rls(client, a, b)
        await _check_rejects(client, a)


def test_pantry_batch_one_upsert_partial_results_rls_and_limits() -> None:
    with signed_in_users("batch", 2) as (a, b):
        asyncio.run(_run(a, b))
