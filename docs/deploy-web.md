# Deploy web + API cùng một container — giai đoạn 2 (kế hoạch)

Nối tiếp `docs/deploy-azure.md`. Chỉ là kế hoạch: **chưa sửa mã, chưa dựng image, chưa đụng Azure / Supabase.**
Ký hiệu: ✅ đã kiểm (đọc mã trong repo / thư viện trong `backend/venv`) · ⚠️ **chưa kiểm chứng**.
Phiên bản đọc được: FastAPI 0.141.1, Starlette 1.6.0, uvicorn 0.53.0, Expo 57.0.24, Node máy dev 25.2.1.

---

## 1. `ENV` và các biến cấu hình (`backend/app/core/config.py`)

✅ `ENV` đọc bằng `os.getenv("ENV", "development")` — **không kiểm giá trị**, chuỗi nào cũng nhận. Cả backend chỉ dùng
nó ở **một** chỗ: trả về trong `GET /api/v1/health` (`health.py:23`). Không có nhánh nào rẽ theo `ENV`:

| Hạng mục | `development` | `production` | Thực tế đang quyết định bởi |
|---|---|---|---|
| Cookie refresh | Secure, SameSite=None | giống hệt | hằng trong `auth.py:110,143` |
| CORS | theo `CORS_ORIGINS` | giống hệt | `CORS_ORIGINS` (mặc định `http://localhost:8081`) |
| `/docs`, `/redoc`, `/openapi.json` | bật | **vẫn bật** | `FastAPI(...)` không truyền `docs_url`/`openapi_url` |
| Log | như nhau | như nhau | không có `logging.basicConfig` trong `app/` (xem dưới) |

Log ✅ (đọc mã): uvicorn chỉ cấu hình logger `uvicorn.*`; logger `app.*` không có handler nên rơi vào handler dự phòng
của Python → **chỉ in WARNING trở lên**, không định dạng. Ví dụ `logger.info("401 …")` trong `errors.py` không bao giờ
hiện trên Azure. Không phụ thuộc `ENV`.

Biến bắt buộc lúc khởi động (thiếu → lifespan lỗi → container không mở cổng) ✅:
`SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY` (`config.py`), `GEMINI_API_KEY`
(`create_gemini_client()` gọi trong `__init__` của provider vision + LLM dự phòng), `GROQ_API_KEY` (`GroqAdapter.__init__`),
`CF_ACCOUNT_ID`, `CF_API_TOKEN` (`CloudflareFluxProvider.__init__`). → Đóng được 2 mục ⚠️ số 7 của `deploy-azure.md`.

**`USDA_API_KEY`: không cần lúc chạy server** ✅ — chỉ `scripts/seed_ingredients.py:136` đọc. Không đặt trên Azure.

Tuỳ chọn: `CORS_ORIGINS`, `FRONTEND_URL`, `SUGGEST_LLM_ADAPT_COUNT`, `*_DAILY_CAP`, `*_OVERRIDE`, `FORWARDED_ALLOW_IPS`.

**Gợi ý trên Azure: `ENV=production`.** Lý do duy nhất là nhãn trong `/health` để nhìn biết đang gọi đúng bản deploy
(lệnh kiểm mục 6 của `deploy-azure.md` đã mong đợi `"environment":"production"`). Đặt gì cũng không đổi hành vi — đừng
dựa vào `ENV` để tưởng `/docs` đã tắt hay cookie đã đổi.

---

## 2. Phục vụ bản web Expo ngay trong container FastAPI

### 2.1 Địa chỉ API phía frontend

✅ `frontend/src/lib/api.ts:4`:
```ts
API_BASE = `${(process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')}/api/v1`
```
Đặt lúc dựng web **`EXPO_PUBLIC_API_URL=/`** → `"/".replace(/\/$/, "")` = `""` → `API_BASE = "/api/v1"` (đường dẫn
tương đối, cùng nguồn). **Không cần sửa `api.ts`.** Không dùng giá trị rỗng: `""` vẫn qua được `??` nhưng ⚠️ chưa chắc
Expo inline biến rỗng giống biến có giá trị; `/` thì chắc chắn là chuỗi khác rỗng.
⚠️ Kiểm sau khi dựng: `grep -r "localhost:8000" dist/` phải không có kết quả.
Bản native (APK/IPA) không dùng được đường dẫn tương đối — khi dựng native thì đặt URL tuyệt đối `https://<fqdn>`.
Không có `frontend/.env` trong repo ✅ (nếu sau này có, `.dockerignore` mục 2.4 chặn nó vào image).

### 2.2 Dockerfile nhiều giai đoạn

Build context phải đổi từ `backend/` sang **gốc repo** (để thấy `frontend/`). Lệnh: `docker build -f backend/Dockerfile .`
✅ Máy dựng không có buildx (`deploy-azure.md` mục 5) → docker 27 chạy **builder cũ**: hỗ trợ multi-stage và
`.dockerignore`, **không** hỗ trợ `--build-context`, `RUN --mount=type=cache`, `COPY --link`, `Dockerfile.dockerignore`.
Bản dưới chỉ dùng cú pháp builder cũ chạy được.

```dockerfile
# ---- Giai đoạn 1: dựng web (chỉ dist được mang sang image cuối) ----
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV EXPO_PUBLIC_API_URL=/
RUN npx expo export --platform web --output-dir dist

# ---- Giai đoạn 2: backend ----
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/opt/huggingface
WORKDIR /app

# Lớp nặng KHÔNG phụ thuộc requirements.txt (mục 4)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir "sentence-transformers>=3.0"
ARG LOAD_BGE_M3="..."            # giữ nguyên khối tải + xoá safetensors + nạp offline hiện tại
RUN python -c "$LOAD_BGE_M3" && ...
ENV HF_HUB_OFFLINE=1

# Lớp nhẹ, đổi thường xuyên
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --from=web /web/dist ./web
COPY backend/app ./app

RUN useradd --no-create-home appuser
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```
- `node:22-slim`: ⚠️ chưa kiểm Expo 57 yêu cầu Node tối thiểu bao nhiêu; máy dev đang chạy Node 25 nên chưa từng
  dựng bằng 22. Nếu lỗi thì dùng đúng `node:25-slim`.
- Giai đoạn `web` cache riêng: đổi mã frontend chỉ chạy lại `expo export`; đổi `package-lock.json` mới chạy lại `npm ci`.
- `useradd` để sau `COPY` như cũ: các file do root sở hữu, appuser chỉ đọc — đúng ý.

### 2.3 Mount tĩnh có fallback cho đường dẫn sâu

✅ `app.json`: `web.output = "single"` → SPA, một `index.html` + JS. Đường dẫn như `/reset-password#access_token=…`,
`/login?verified=1`, `/recipe/123` không có file thật → phải trả `index.html`.
✅ `StaticFiles(html=True)` của Starlette **không** làm việc này (chỉ trả `index.html` cho thư mục, còn lại 404) → cần
lớp con nhỏ. Đặt ở `app/core/web_static.py` (hạ tầng, không phải business logic), ~30 dòng:

```python
WEB_DIST_DIR = BACKEND_DIR / "web"                 # chỉ có trong image; chạy dev không có → bỏ qua mount
IMMUTABLE_PREFIXES = ("_expo/static/",)           # tên file có hash nội dung ⚠️ (+ "assets/" nếu cũng có hash)
CACHE_IMMUTABLE = "public, max-age=31536000, immutable"
CACHE_REVALIDATE = "no-cache"                     # index.html, favicon, manifest: luôn hỏi lại (có ETag → 304)

class SpaStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        if path.startswith("api/"):               # API sai đường dẫn → 404 JSON, không bao giờ trả index.html
            raise HTTPException(404)
        try:
            response = await super().get_response(path, scope)
        except HTTPException as error:
            if error.status_code != 404 or "." in path.rsplit("/", 1)[-1]:
                raise                             # thiếu file .js/.png thật → 404, không trả HTML giả
            response = await super().get_response("index.html", scope)
        response.headers["Cache-Control"] = CACHE_IMMUTABLE if path.startswith(IMMUTABLE_PREFIXES) else CACHE_REVALIDATE
        return response

def mount_web(app: FastAPI) -> None:
    if WEB_DIST_DIR.is_dir():
        app.mount("/", GZipMiddleware(SpaStaticFiles(directory=WEB_DIST_DIR), minimum_size=1024, compresslevel=6))
```
`create_app` gọi `mount_web(application)` **sau cùng**, sau mọi `include_router`.

Vì sao không đè lên `/api`, `/docs`, `/openapi.json`: ✅ FastAPI đăng ký `/openapi.json`, `/docs`,
`/docs/oauth2-redirect`, `/redoc` ngay trong `FastAPI.__init__`; router `/api/v1/*` thêm sau đó; Starlette duyệt route
theo thứ tự → mount `/` ở cuối chỉ nhận những gì không route nào khớp. Lớp chặn `api/` thêm một lần nữa cho đường dẫn
API gõ sai.

Đã kiểm khi làm: lớp chặn `api/` chạy trước bước kiểm method nên `POST`/`PATCH`/`DELETE` vào API sai đường dẫn vẫn ra 404 JSON (test `test_non_get_on_unknown_api_path_is_still_json_404`).

**Gzip:** bọc `GZipMiddleware` **chỉ quanh phần tĩnh**, không quanh cả app:
- Bundle 3,36 MB (số anh đưa, ⚠️ chưa tự đo; `dist/` chưa có trong repo) → JS nén gzip thường còn ~25–30% ⚠️.
- Starlette 1.6 ✅ nén body ≥128 KiB trong thread (`thread_minimum_size`) → không chặn event loop. `compresslevel=6`
  thay mặc định 9: nén nhanh hơn rõ, file to hơn vài %. Nén lại mỗi lần tải, nhưng với cache `immutable` mỗi trình
  duyệt chỉ tải một lần mỗi bản deploy. Cần hơn thì nén sẵn `.gz` lúc dựng — chưa cần.
- Không nén API: JSON nhỏ, và tránh trường hợp BREACH (body nén chứa cả `access_token` lẫn dữ liệu người dùng gửi lên).
- ⚠️ Chưa kiểm Envoy của Container Apps có tự nén hay đổi `Content-Encoding` không. Kiểm bằng
  `curl -sI -H "Accept-Encoding: gzip" $URL/_expo/static/js/web/<file>.js`.

**Header cache:**
| Đường dẫn | `Cache-Control` | Lý do |
|---|---|---|
| `/_expo/static/**` | `public, max-age=31536000, immutable` | tên có hash ⚠️ kiểm trong `dist/` |
| `/assets/**` (font, ảnh) | như trên **nếu** tên có hash, không thì `no-cache` | ⚠️ chưa thấy `dist/` |
| `index.html`, fallback SPA, favicon, manifest | `no-cache` | deploy mới thấy ngay; ✅ StaticFiles có ETag/Last-Modified → 304 |
| `/api/**` | không đụng | |

### 2.4 `.dockerignore` ở gốc repo

Context đổi sang gốc → `backend/.dockerignore` **không còn tác dụng** (Docker chỉ đọc file ở gốc context). Thay bằng
`.dockerignore` gốc kiểu danh sách cho phép (an toàn hơn cho secret), xoá file cũ để khỏi nhầm:
```
*
!backend/requirements.txt
!backend/app
!frontend
frontend/node_modules
frontend/dist
frontend/.expo
**/.env
**/*.env
**/.env.*
**/.kaggle
**/__pycache__
**/*.pyc
```
⚠️ Chưa kiểm kích thước context thật; nên chạy một lần và xem dòng `Sending build context to Docker daemon` (phải cỡ vài MB,
không phải hàng trăm MB do lọt `node_modules`/`venv`).

---

## 3. Cookie đăng nhập và CORS khi cùng nguồn

Hiện tại ✅ (`auth.py`): cookie `bepai_refresh`, `HttpOnly`, `Secure`, `SameSite=None`, `Path=/api/v1/auth`, 30 ngày.
Frontend gọi `fetch(..., credentials: 'include')` (`api.ts:54`). Comment dòng 143 ghi "Vercel và Render khác domain" —
đã lỗi thời nếu web và API cùng một địa chỉ Azure.

**Có bắt buộc đổi không? Không.** Cùng nguồn thì `SameSite=None; Secure` vẫn chạy trên HTTPS; mọi request web là
same-origin nên trình duyệt không gửi preflight và CORS không tham gia.

**Đề xuất đổi (1 dòng × 2 chỗ): `samesite="lax"`** ở `set_cookie` và `delete_cookie` (phải khớp nhau mới xoá được).
- Lợi: trang khác site gửi `POST /auth/refresh` không còn kèm cookie → hết kiểu ép xoay refresh token (CSRF) từ site lạ;
  không phụ thuộc chính sách chặn cookie bên thứ ba của trình duyệt.
- Dev vẫn chạy: `http://localhost:8081` → `http://localhost:8000` là **cùng site** (site không tính cổng) → Lax vẫn gửi.
  `Secure` trên `http://localhost`: Chrome/Firefox chấp nhận, đúng như hiện tại; ⚠️ Safari chưa kiểm (rủi ro này có sẵn từ trước, không mới).
- Mất gì: nếu sau này lại tách web sang domain khác (Vercel…) thì phải quay về `None`. Ghi rõ trong comment.
- Native không ảnh hưởng (refresh token nằm trong body + SecureStore).
- Không đổi tên cookie (đổi tên = mọi người dùng web bị đăng xuất, không được gì).

**CORS trên Azure: `CORS_ORIGINS=https://<fqdn>` — chỉ đúng địa chỉ đó, không thêm `localhost:8081`.**
Rủi ro nếu để mặc định `http://localhost:8081` ở production: bất kỳ trang nào chạy ở `localhost:8081` trên máy người
dùng (kể cả phần mềm lạ) được phép đọc response kèm cookie → gọi `/auth/refresh` và **đọc được access token**
(với `SameSite=None` hiện tại). Đổi sang Lax chặn thêm lớp thứ hai (localhost và `azurecontainerapps.io` khác site).
Middleware CORS vẫn giữ — cần cho dev web chạy hai cổng.

**Biến môi trường backend:** `FRONTEND_URL=https://<fqdn>`, `CORS_ORIGINS=https://<fqdn>`.

**Supabase → Authentication → URL Configuration** (✅ link email trỏ về `FRONTEND_URL`: `auth.py:78,122`):
- **Site URL:** `https://<fqdn>`
- **Redirect URLs:** `https://<fqdn>/login?verified=1`, `https://<fqdn>/reset-password`
  (hoặc gộp `https://<fqdn>/**`); giữ `http://localhost:8081/**` nếu còn dev local.
- `<fqdn>` dạng `<app>.<env-suffix>.malaysiawest.azurecontainerapps.io` ⚠️ — chỉ có sau khi tạo Container App. Tạo app
  trước (bản API cũ cũng được) → lấy FQDN → đặt env + Supabase → deploy bản có web.
- Rủi ro: đổi Site URL thì các link email đã gửi trước đó vẫn trỏ địa chỉ cũ. Chưa có người dùng thật nên không đáng kể.

---

## 4. Giữ lớp nặng (torch, bge-m3) không bị dựng lại

Hiện tại ✅: `COPY requirements.txt` → **một** `RUN` cài cả torch lẫn requirements → `RUN` tải bge-m3. Cache của builder
cũ khoá theo nội dung file COPY → **sửa một ký tự trong `requirements.txt` là dựng lại torch và tải lại bge-m3 2,2 GB.**

✅ `requirements.txt` vừa đổi `kaggle>=2.2.4` → `kaggle>=1.7.0` trong commit `2a0af9e` (12/10), **sau** lần dựng kiểm
ở commit `1b17f7b`. Vậy với Dockerfile hiện tại, lần dựng tới chắc chắn dựng lại toàn bộ. Với Dockerfile mới (mục 2.2)
cũng dựng lại **một lần cuối** (chuỗi lệnh đổi). Không có cách sạch nào tái dùng lớp cũ — chấp nhận một lần.
(Đổi này chỉ hạ mức tối thiểu; pip vẫn chọn kaggle mới nhất nên bản cài thực tế gần như chắc không đổi ⚠️.)

Sau khi tách (mục 2.2), từ lần thứ hai:
| Thay đổi | Lớp dựng lại | Phải đẩy lại lên ACR |
|---|---|---|
| Mã backend (`app/`) | `COPY app` | < 1 MB |
| Mã frontend | `expo export` + `COPY --from=web` + `COPY app` | ~3–5 MB ⚠️ |
| `requirements.txt` | `pip install -r` + 2 lớp trên | vài chục–vài trăm MB ⚠️ (gói mới; torch/sentence-transformers đã có nên pip bỏ qua) |
| Đổi lệnh torch / sentence-transformers / bge-m3 | gần hết | ~3–4 GB ⚠️ |

Điều kiện để thật sự **không** đẩy lại lớp nặng:
1. Dựng trên **cùng một dockerd** (WSL `kali-linux`) — không `docker system prune`, không `docker builder prune`.
   Lớp dựng lại từ đầu dù lệnh y hệt vẫn ra digest khác (thời gian file khác) → đẩy lại toàn bộ.
2. Push vào **cùng repository** ACR (`bepai-backend`): blob đã có sẽ báo `Layer already exists`. Không đổi tên repository
   khi đổi tên sản phẩm (mục 5) — ⚠️ chưa kiểm ACR có tự gắn blob chéo repository khi push bằng docker CLI.
3. Mất cache local: `docker pull <acr>/bepai-backend:<tag cũ>` rồi `docker build --cache-from <acr>/bepai-backend:<tag cũ> …`
   (builder cũ hỗ trợ `--cache-from` với image đã pull) ⚠️ chưa thử.

`sentence-transformers` cài không ghim ở lớp nặng: khoá cache theo **chuỗi lệnh**, không theo phiên bản trên PyPI → giữ
nguyên tới khi sửa dòng đó. Đổi lại, phiên bản trong image có thể khác venv dev (rủi ro đã có từ trước, mục 1.4 của
`deploy-azure.md`).

Ước tính lần đẩy đầu (⚠️ toàn bộ là ước tính, chưa đo): python slim ~150 MB, torch CPU ~0,8–1 GB, phần còn lại của
requirements ~0,4–0,8 GB, bge-m3 ~2,3 GB (nén gần như không giảm), web vài MB → **~3,5–4,5 GB**. Đo thật sau lần dựng
đầu: `docker history --format "{{.Size}}\t{{.CreatedBy}}" <image>`. Đã từng đẩy image lên ACR chưa? Nếu chưa thì lần
dựng lại bắt buộc nói trên không làm mất gì thêm.

---

## 5. Gom vào cùng lần dựng: Swagger Authorize, mô tả mã lỗi, tên sản phẩm

### 5.1 Nút Authorize (giữ nguyên hành vi)

✅ Hiện `require_user` (`deps.py`) tự tách header → OpenAPI không biết có Bearer → Swagger không có nút Authorize.
Đổi sang `HTTPBearer(auto_error=False)`:
```python
BEARER_AUTH = HTTPBearer(auto_error=False, description="Access token từ POST /api/v1/auth/login")

async def require_user(
    credentials: HTTPAuthorizationCredentials | None = Security(BEARER_AUTH),
    verifier: JwtVerifier = Depends(get_jwt_verifier),
) -> CurrentUser:
    if credentials is None:
        raise UnauthenticatedError("Thiếu access token")
    return await verifier.verify(credentials.credentials)
```
Vì sao giữ nguyên hành vi ✅ (đọc `fastapi/security/http.py` 0.141.1): `HTTPBearer.__call__` tách bằng
`partition(" ")` rồi `strip()` token — đúng như mã hiện tại; trả `None` khi thiếu header, scheme khác `bearer`
(không phân biệt hoa thường) hoặc token rỗng — đúng ba trường hợp đang ném `UnauthenticatedError`. Với
`auto_error=False` FastAPI không tự trả 401/403 của nó → vẫn đi qua handler `_unauthenticated` (cùng body, cùng header
`WWW-Authenticate: Bearer`). Xoá hằng `BEARER_SCHEME` không còn dùng. Mọi endpoint qua `limit_user` tự có ổ khoá.
Kiểm: chạy lại test 401 sẵn có trong `backend/tests` (không gọi AI).

### 5.2 Mô tả mã lỗi

Thêm vào `app/api/errors.py` (cạnh các handler tạo ra chính các mã này):
```python
class ValidationIssue(BaseModel): loc: list[str | int]; msg: str; type: str
class ErrorOut(BaseModel): detail: str | list[ValidationIssue]

ERROR_DESCRIPTIONS = {401: "...", 413: "...", 415: "...", 422: "...", 429: "... kèm header Retry-After (giây)", 503: "..."}

def error_responses(*codes: int) -> dict[int | str, dict[str, Any]]:
    """Khối `responses=` cho OpenAPI: mô tả + schema lỗi chung."""
    return {code: {"model": ErrorOut, "description": ERROR_DESCRIPTIONS[code]} for code in codes}
```
✅ Khai báo 422 riêng thì FastAPI không thêm 422 mặc định (`HTTPValidationError`) nữa — tốt, vì handler của mình bỏ
trường `input`/`ctx` và có lúc trả `detail` là chuỗi.

Gắn ở đâu (đã đối chiếu từng chỗ ném lỗi):
| Endpoint | Mã |
|---|---|
| Router profile / pantry / logs / saved (một lần ở `include_router(..., responses=)` trong `main.py`) | 401, 422, 429 |
| `POST /saved` thêm | 413 (`PayloadTooLargeError`) |
| `POST /recognize` | 401, 413, 415, 422, 429, 503 |
| `POST /recipes/suggest` | 401, 422, 429 |
| `POST /recipes/{id}/image` | 401, 422, 429, 503 |
| `/auth/login`, `/auth/refresh`, `/auth/reset-password` | 401, 422, 429, 503 |
| `/auth/register`, `/auth/forgot-password` | 422, 429, 503 |
| `/auth/logout` | 401, 429, 503 |
| `/health` | 429 |

Ngoài 6 mã anh liệt kê, mã thật còn có: **404** (xoá pantry/logs/saved, ảnh món không có công thức), **403** (một mã
lỗi Supabase Auth trong `_KNOWN_ERRORS`, ⚠️ chưa xem là lỗi nào — có thể "email chưa xác minh" lúc login), **502**
(Supabase Auth trả mã lạ). **Anh đã chọn thêm cả ba (12/10)** — bổ sung vào bảng trên đúng endpoint có ném.

### 5.3 Tên sản phẩm — **anh đã chọn "Chef AI"** (12/10)

Việc cần làm: đổi "Bếp AI" → "Chef AI" ở `README.md`, `backend/README.md`, `feature-spec.md`, `design/design-spec.md`,
chú thích đầu `backend/Dockerfile`. Phần người dùng thấy đã là "Chef AI" sẵn. Hiện trạng trước khi chọn:

Hiện có hai tên:
- **"Chef AI"** — mọi chỗ người dùng thấy: `app.json` (name, web.name/shortName, câu xin quyền camera/ảnh), `BrandMark.tsx`,
  `BottomTabBar.tsx` ("Cài Chef AI vào máy"), tiêu đề Swagger (`main.py:68`). Commit mới nhất `9f569cb` ghi "rebrand to Chef AI".
- **"Bếp AI"** — chỉ trong tài liệu/chú thích: `README.md`, `backend/README.md`, `feature-spec.md`, `design/design-spec.md`,
  dòng chú thích đầu `backend/Dockerfile`.

Đề xuất **không đổi** các khoá nội bộ `bepai_refresh` (cookie), `bepai.*` / `bepai:` (SecureStore, localStorage), tên
image `bepai-backend`, scheme `chefai`: người dùng không thấy; đổi là đăng xuất mọi người / mất dữ liệu cục bộ / mất cache
lớp trên ACR. ⚠️ Chưa kiểm: `<title>` của trang web sau `expo export` lấy từ đâu; mẫu email trong dashboard Supabase
(không có trong repo) có ghi tên không.

---

## 6. Thứ tự làm khi anh duyệt

1. ✅ Đã chốt: tên "Chef AI", mô tả thêm 404/403/502.
2. Sửa mã: `deps.py` (5.1), `errors.py` + `main.py` + routers (5.2), `web_static.py` + `main.py` (2.3), `auth.py` SameSite (3),
   đổi tên hiển thị (5.3). Chạy `pytest` (không gọi AI).
3. Dockerfile mới + `.dockerignore` gốc, xoá `backend/.dockerignore` (2.2, 2.4). Cập nhật lệnh dựng trong `deploy-azure.md` mục 5.
4. Dựng một lần, kiểm local bằng env giả + `--network none` như lần trước: `/` ra `index.html`, `/reset-password` ra
   `index.html`, `/api/v1/khong-co` ra 404 JSON, `/docs` có nút Authorize, `/_expo/static/...` có `immutable` + gzip.
   Đo `docker history`.
5. Push, đặt env (`ENV`, `CORS_ORIGINS`, `FRONTEND_URL`), Supabase URL Configuration, kiểm theo `deploy-azure.md` mục 6.

---

## 7. Tóm tắt chỗ chưa kiểm chứng

1. Bundle 3,36 MB và tỉ lệ nén gzip — số của anh, chưa đo; `dist/` chưa có trong repo.
2. Tên file trong `dist/_expo/static/` và `dist/assets/` có hash nội dung hay không (quyết định header `immutable`).
3. `EXPO_PUBLIC_API_URL=/` được inline đúng vào bundle (kiểm bằng grep `localhost:8000`).
4. Expo 57 dựng được trên `node:22-slim` (máy dev dùng Node 25).
5. Envoy của Container Apps có nén lại / bỏ `Content-Encoding` không.
6. Kích thước từng lớp image và tổng dung lượng lần đẩy đầu (chỉ là ước tính).
7. ACR có tránh đẩy lại blob khi đổi tên repository; `--cache-from` với builder cũ khi mất cache local.
8. Mã 403 trong `_KNOWN_ERRORS` của auth là lỗi gì.
9. Cookie `Secure` trên `http://localhost` với Safari (rủi ro có từ trước).
10. `<title>` trang web và mẫu email Supabase có chứa tên sản phẩm không.
11. Đã từng đẩy image lên ACR chưa (ảnh hưởng việc lần dựng lại bắt buộc có tốn thêm gì không).
