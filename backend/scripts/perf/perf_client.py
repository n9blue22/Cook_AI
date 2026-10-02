"""Đo thời gian phía client cho backend đang chạy ở :8000 (thường là scripts/perf/perf_server.py).

Tạo 1 tài khoản tạm (admin API, mật khẩu ngẫu nhiên chỉ giữ trong RAM), đo, rồi xoá tài khoản (cascade dọn dữ liệu).
Nhóm đo (tham số dòng lệnh, mặc định "user"):
  user      GET /profile, GET /pantry tuần tự + "Main sau đăng nhập" = 4 GET song song (profile, pantry, logs, saved)
  recognize POST /recognize × 3 (Gemini, tốn quota ngày)
  suggest   POST /recipes/suggest × 3 (tốn quota ngày; server đo phải tắt LLM → không gọi Groq)
  write     POST /pantry, POST /saved (upsert lặp lại cùng 1 dòng, không tốn quota)
  idle      GET /pantry khi ấm, rồi để backend rảnh IDLE_SEC giây, gọi lại 3 lần (kết nối trong pool có bị hỏng không)
Chạy (cwd = backend): venv\\Scripts\\python.exe scripts/perf/perf_client.py user suggest
"""

import asyncio
import os
import secrets
import statistics
import sys
import time
from datetime import date

import httpx

sys.path.insert(0, os.getcwd())
from app.core.config import require_env  # noqa: E402
from scripts.supabase_admin import create_admin_client  # noqa: E402
from tests.real_users import saved_recipe_body  # noqa: E402

API = os.environ.get("PERF_API", "http://127.0.0.1:8000/api/v1")
IMAGE = os.path.join(os.getcwd(), "tests", "fixtures", "chicken_parmesan_mise_en_place.jpg")
SUGGEST_BODY = {"ingredient_ids": [16, 18, 19, 80], "diet_type": "omnivore", "allergens": []}
USER_ROUNDS = 5
AI_ROUNDS = 3
IDLE_SEC = int(os.environ.get("PERF_IDLE_SEC", "370"))
MAIN_SCREEN_PATHS = ("/profile", "/pantry", f"/logs?date={date.today().isoformat()}", "/saved")


async def timed(client: httpx.AsyncClient, method: str, path: str, **kwargs) -> float:
    """1 request → ms; lỗi HTTP thì dừng luôn (số đo của request lỗi vô nghĩa)."""
    started = time.perf_counter()
    response = await client.request(method, API + path, **kwargs)
    response.raise_for_status()
    return (time.perf_counter() - started) * 1000


async def main_screen(client: httpx.AsyncClient) -> float:
    """4 GET song song như màn Main sau đăng nhập → ms tới khi cái chậm nhất xong."""
    started = time.perf_counter()
    await asyncio.gather(*(timed(client, "GET", path) for path in MAIN_SCREEN_PATHS))
    return (time.perf_counter() - started) * 1000


async def measure_user(client: httpx.AsyncClient) -> dict[str, list[float]]:
    await timed(client, "GET", "/profile")  # lượt đầu: JWKS + kết nối, không tính
    samples: dict[str, list[float]] = {"GET /profile": [], "GET /pantry": [], "Main (4 GET song song)": []}
    for _ in range(USER_ROUNDS):
        samples["GET /profile"].append(await timed(client, "GET", "/profile"))
        samples["GET /pantry"].append(await timed(client, "GET", "/pantry"))
        samples["Main (4 GET song song)"].append(await main_screen(client))
    return samples


async def measure_recognize(client: httpx.AsyncClient) -> dict[str, list[float]]:
    image = open(IMAGE, "rb").read()
    files = {"image": ("photo.jpg", image, "image/jpeg")}
    return {"POST /recognize": [await timed(client, "POST", "/recognize", files=files) for _ in range(AI_ROUNDS)]}


async def measure_suggest(client: httpx.AsyncClient) -> dict[str, list[float]]:
    return {
        "POST /recipes/suggest": [
            await timed(client, "POST", "/recipes/suggest", json=SUGGEST_BODY) for _ in range(AI_ROUNDS)
        ],
    }


async def measure_write(client: httpx.AsyncClient) -> dict[str, list[float]]:
    pantry_body, saved_body = {"ingredient_id": 16}, {"recipe": saved_recipe_body(2648, "Món đo hiệu năng")}
    await timed(client, "POST", "/pantry", json=pantry_body)  # lượt đầu tạo dòng, không tính
    await timed(client, "POST", "/saved", json=saved_body)
    return {
        "POST /pantry": [await timed(client, "POST", "/pantry", json=pantry_body) for _ in range(USER_ROUNDS)],
        "POST /saved": [await timed(client, "POST", "/saved", json=saved_body) for _ in range(USER_ROUNDS)],
    }


async def measure_idle(client: httpx.AsyncClient) -> dict[str, list[float]]:
    warm = [await timed(client, "GET", "/pantry") for _ in range(3)]
    await asyncio.sleep(IDLE_SEC)
    return {"GET /pantry ấm": warm, f"GET /pantry sau {IDLE_SEC}s rảnh": [await timed(client, "GET", "/pantry") for _ in range(3)]}


MEASURES = {"idle": measure_idle, "write": measure_write, "user": measure_user, "recognize": measure_recognize, "suggest": measure_suggest}


def sign_in(email: str, password: str) -> str:
    response = httpx.post(
        f"{require_env('SUPABASE_URL')}/auth/v1/token", params={"grant_type": "password"},
        headers={"apikey": require_env("SUPABASE_PUBLISHABLE_KEY")}, json={"email": email, "password": password},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["access_token"]


async def run(groups: list[str], token: str) -> dict[str, list[float]]:
    results: dict[str, list[float]] = {}
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers, timeout=120) as client:
        for group in groups:
            results.update(await MEASURES[group](client))
    return results


def print_table(results: dict[str, list[float]]) -> None:
    print("| Đo | n | min ms | trung vị ms | max ms |")
    print("|---|---|---|---|---|")
    for label, values in results.items():
        print(f"| {label} | {len(values)} | {min(values):.0f} | {statistics.median(values):.0f} | {max(values):.0f} |")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # console Windows mặc định cp1252
    groups = sys.argv[1:] or ["user"]
    unknown = set(groups) - set(MEASURES)
    if unknown:
        sys.exit(f"Nhóm đo không có: {unknown}; chọn trong {list(MEASURES)}")
    admin = create_admin_client()
    email, password = f"perf-{secrets.token_hex(4)}@example.com", "Pf-" + secrets.token_urlsafe(16)
    user_id = admin.auth.admin.create_user({"email": email, "password": password, "email_confirm": True}).user.id
    try:
        print_table(asyncio.run(run(groups, sign_in(email, password))))
    finally:
        admin.auth.admin.delete_user(user_id)


if __name__ == "__main__":
    main()
