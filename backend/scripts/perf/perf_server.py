"""Chạy backend thật kèm đo từng giai đoạn (monkeypatch lúc chạy, không đổi code app). Ghi JSONL vào PERF_LOG
(mặc định thư mục tạm). Tắt LLM chỉnh món (SUGGEST_LLM_ADAPT_COUNT=0) → không gọi Groq. Embed 1 câu lúc khởi động
để lượt /recipes/suggest đầu không tính thời gian nạp lazy của bge-m3.
Chạy (cwd = backend): venv\\Scripts\\python.exe scripts/perf/perf_server.py"""

import contextlib
import contextvars
import functools
import json
import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.getcwd())
os.environ["SUGGEST_LLM_ADAPT_COUNT"] = "0"
LOG = os.environ.get("PERF_LOG", os.path.join(tempfile.gettempdir(), "perf_log.jsonl"))
T0 = time.perf_counter()

import httpx  # noqa: E402

current = contextvars.ContextVar("req", default=None)
_lock = threading.Lock()


def emit(record):
    with _lock, open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def stage(name, fn):
    if hasattr(fn, "__wrapped_perf__"):
        return fn
    if asyncio_iscoro(fn):
        @functools.wraps(fn)
        async def wrapper(*a, **k):
            t = time.perf_counter()
            try:
                return await fn(*a, **k)
            finally:
                note(name, t)
    else:
        @functools.wraps(fn)
        def wrapper(*a, **k):
            t = time.perf_counter()
            try:
                return fn(*a, **k)
            finally:
                note(name, t)
    wrapper.__wrapped_perf__ = True
    return wrapper


def asyncio_iscoro(fn):
    import inspect
    return inspect.iscoroutinefunction(fn)


def note(name, t):
    ms = (time.perf_counter() - t) * 1000
    req = current.get()
    if req is not None:
        req["stages"].append([name, round(ms, 1), round((t - req["t0"]) * 1000, 1)])


# Đếm round trip HTTP ra ngoài (Supabase REST/RPC/Storage/Auth, Gemini, JWKS…)
_orig_send = httpx.AsyncClient.send


async def counting_send(self, request, *a, **k):
    t = time.perf_counter()
    try:
        return await _orig_send(self, request, *a, **k)
    finally:
        req = current.get()
        if req is not None:
            ms = (time.perf_counter() - t) * 1000
            req["http"].append([request.method, request.url.host.split(".")[0], request.url.path, round(ms, 1),
                                round((t - req["t0"]) * 1000, 1)])


httpx.AsyncClient.send = counting_send
_orig_sync_send = httpx.Client.send


def counting_sync_send(self, request, *a, **k):
    t = time.perf_counter()
    try:
        return _orig_sync_send(self, request, *a, **k)
    finally:
        emit({"sync_http": [request.method, request.url.path, round((time.perf_counter() - t) * 1000, 1)],
              "thread": threading.current_thread().name})


httpx.Client.send = counting_sync_send

# urllib (PyJWKClient tải JWKS bằng urllib)
import urllib.request  # noqa: E402

_orig_urlopen = urllib.request.urlopen


def timed_urlopen(*a, **k):
    t = time.perf_counter()
    try:
        return _orig_urlopen(*a, **k)
    finally:
        emit({"urllib": str(a[0] if not hasattr(a[0], "full_url") else a[0].full_url)[:80],
              "ms": round((time.perf_counter() - t) * 1000, 1)})


urllib.request.urlopen = timed_urlopen

from app.api.routes import ai  # noqa: E402
from app.services import pipeline, rate_limit, auth_tokens, ingredient_normalizer, recipe_results  # noqa: E402
from app.services.embedding import bge_m3  # noqa: E402
from app.services.vision import gemini  # noqa: E402
from app.services import recipe_repository  # noqa: E402

ai.prepare_image_for_vision = stage("prepare_image(Pillow)", ai.prepare_image_for_vision)
ai.load_ingredient_catalog = stage("load_catalog", ai.load_ingredient_catalog)
pipeline.load_ingredient_catalog = stage("load_catalog", pipeline.load_ingredient_catalog)
ai.recognize_ingredients = stage("recognize_ingredients(total vision+normalize)", ai.recognize_ingredients)
gemini.GeminiVisionProvider.detect_ingredients = stage("gemini_vision", gemini.GeminiVisionProvider.detect_ingredients)
ingredient_normalizer.IngredientNormalizer.__init__ = stage("normalizer_build", ingredient_normalizer.IngredientNormalizer.__init__)
ingredient_normalizer.IngredientNormalizer.normalize = stage("normalize", ingredient_normalizer.IngredientNormalizer.normalize)
bge_m3.BgeM3Provider.embed = stage("embed(to_thread)", bge_m3.BgeM3Provider.embed)
bge_m3.BgeM3Provider.encode = stage("encode(in thread)", bge_m3.BgeM3Provider.encode)
pipeline.search_recipes = stage("search_recipes_rpc", pipeline.search_recipes)
pipeline.load_original_recipes = stage("load_original_recipes", pipeline.load_original_recipes)
pipeline.original_result = stage("build_original_result", pipeline.original_result)
ai.suggest_recipes = stage("suggest_recipes(total pipeline)", ai.suggest_recipes)
rate_limit.RateLimiter.ensure_daily_available = stage("quota_check", rate_limit.RateLimiter.ensure_daily_available)
rate_limit.RateLimiter.record_daily_after_success = stage("quota_record", rate_limit.RateLimiter.record_daily_after_success)
rate_limit.RateLimiter.consume_daily = stage("quota_consume", rate_limit.RateLimiter.consume_daily)
rate_limit.RateLimiter.check = stage("ratelimit_memory_check", rate_limit.RateLimiter.check)
auth_tokens.JwtVerifier.verify = stage("jwt_verify", auth_tokens.JwtVerifier.verify)

from app.main import app  # noqa: E402


_probe = None
_app_lifespan = app.router.lifespan_context


@contextlib.asynccontextmanager
async def lifespan_with_warmup(application):
    async with _app_lifespan(application):
        await application.state.ai_services.embedder.embed(["khởi động"])
        emit({"warmup_done_s": round(time.perf_counter() - T0, 2)})
        yield


app.router.lifespan_context = lifespan_with_warmup


@app.middleware("http")
async def perf_mw(request, call_next):
    global _probe
    if _probe is None:
        import asyncio
        _probe = asyncio.get_running_loop().create_task(loop_lag_probe())
    req = {"t0": time.perf_counter(), "stages": [], "http": []}
    token = current.set(req)
    try:
        response = await call_next(request)
        status = response.status_code
    finally:
        current.reset(token)
    total = (time.perf_counter() - req["t0"]) * 1000
    emit({"path": request.url.path, "method": request.method, "status": status, "total_ms": round(total, 1),
          "stages": req["stages"], "http": req["http"], "n_http": len(req["http"])})
    return response


# Đo nghẽn event loop: task ngủ 50ms, ghi độ trễ thức dậy vượt ngưỡng
async def loop_lag_probe():
    import asyncio
    while True:
        t = time.perf_counter()
        await asyncio.sleep(0.05)
        lag = (time.perf_counter() - t) * 1000 - 50
        if lag > 30:
            emit({"loop_lag_ms": round(lag, 1), "at": round(time.perf_counter() - T0, 2)})




if __name__ == "__main__":
    import uvicorn

    emit({"boot_import_s": round(time.perf_counter() - T0, 2)})
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8000")), log_level="warning")
