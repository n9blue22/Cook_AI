"""Phục vụ bản web Expo (expo export, output "single") cùng địa chỉ với API: fallback SPA, cache theo loại file, gzip."""

import os
from pathlib import Path, PurePosixPath

from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from app.core.config import BACKEND_DIR

WEB_DIST_DIR = BACKEND_DIR / "web"  # Dockerfile chép dist vào đây; chạy dev không có → không mount
SPA_INDEX = "index.html"
API_PATH = "api"
# expo export đặt hash nội dung vào tên file ở hai thư mục này → cache vĩnh viễn, deploy mới là tên mới.
HASHED_ASSET_PREFIXES = ("_expo/static/", "assets/")
CACHE_IMMUTABLE = "public, max-age=31536000, immutable"
CACHE_REVALIDATE = "no-cache"  # index.html, favicon…: luôn hỏi lại (ETag → 304), deploy mới thấy ngay
GZIP_MIN_BYTES = 1024
GZIP_LEVEL = 6  # mặc định 9 chậm hơn rõ mà file chỉ nhỏ hơn vài %


class SpaStaticFiles(StaticFiles):
    """File tĩnh của SPA: đường dẫn không đuôi (/recipe/123) → index.html; /api/* và file có đuôi thiếu → 404."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        """Trả file; đường dẫn route của SPA thì trả index.html; gắn Cache-Control theo loại file."""
        url_path = path.replace(os.sep, "/")  # StaticFiles đưa vào đường dẫn kiểu hệ điều hành
        if url_path == API_PATH or url_path.startswith(f"{API_PATH}/"):
            raise HTTPException(status_code=404)  # API gõ sai → 404 JSON như cũ, không bao giờ trả HTML
        try:
            response = await super().get_response(path, scope)
        except HTTPException as error:
            if error.status_code != 404 or PurePosixPath(url_path).suffix:
                raise  # thiếu .js/.css/.png thật → 404, không trả HTML thay cho file
            url_path = SPA_INDEX
            response = await super().get_response(SPA_INDEX, scope)
        is_hashed = url_path.startswith(HASHED_ASSET_PREFIXES)
        response.headers["Cache-Control"] = CACHE_IMMUTABLE if is_hashed else CACHE_REVALIDATE
        return response


def mount_web(app: FastAPI, dist_dir: Path = WEB_DIST_DIR) -> None:
    """Gắn web vào "/" — gọi SAU mọi router: route API, /docs, /openapi.json được khớp trước mount này.
    Gzip chỉ bọc phần tĩnh (JSON của API không nén: nhỏ, và có access token)."""
    if not dist_dir.is_dir():
        return
    static = SpaStaticFiles(directory=dist_dir)
    app.mount("/", GZipMiddleware(static, minimum_size=GZIP_MIN_BYTES, compresslevel=GZIP_LEVEL), name="web")
