# Deploy backend lên Azure Container Apps — giai đoạn 1 (chỉ backend)

Vùng: **Malaysia West**. Tài liệu này chỉ là kế hoạch: chưa tạo tài nguyên Azure, chưa đẩy image, chưa sửa code.
Ký hiệu: ✅ đã kiểm trong repo / máy dev · ⚠️ **chưa kiểm chứng** (phải xác nhận lúc deploy).

---

## 1. Kiểm Dockerfile hiện tại (`backend/Dockerfile`)

| Mục | Hiện tại | Nguồn |
|---|---|---|
| Cổng | `${PORT:-8000}` → 8000 (Container Apps không tự đặt `PORT`, ⚠️) ; `EXPOSE 8000` | Dockerfile |
| Lệnh chạy | `sh -c "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"` — 1 worker | Dockerfile |
| Health | `GET /api/v1/health` (router health + prefix `/api/v1`) | `app/main.py:75`, `app/api/v1/health.py:16` |
| Người dùng | `appuser` (không root), tạo bằng `useradd --no-create-home` | Dockerfile |
| Model | bge-m3 đóng sẵn trong image ở `/opt/huggingface`, `HF_HUB_OFFLINE=1` | Dockerfile |

Health thật làm gì (✅ đọc mã):
- Gọi Supabase `GET /auth/v1/health` (timeout 5 s). Supabase lỗi → vẫn **HTTP 200** với `status: "degraded"` → probe
  không coi là hỏng (tốt: Supabase chập chờn không làm Azure khởi động lại container).
- Có rate limit theo IP: `default_ip` = 30 lượt/phút (`app/services/rate_limit.py`). Probe gọi đường này sẽ tính vào bộ đếm
  của IP nguồn của probe.
- Không có endpoint health "nhẹ" riêng (không gọi Supabase). → Đề xuất probe TCP, xem mục 3.

Cờ uvicorn (✅ đọc mã uvicorn 0.53.0 trong `backend/venv`):
- `--proxy-headers` **đã bật mặc định** (`uvicorn/main.py:232`, `default=True`), nhưng chỉ tin proxy trong
  `FORWARDED_ALLOW_IPS`, mặc định `127.0.0.1,::1` (`uvicorn/config.py:363`). Envoy của Container Apps không phải
  127.0.0.1 → uvicorn bỏ qua `X-Forwarded-For` → `request.client.host` = IP của Envoy → **mọi người dùng chung một bộ
  đếm theo IP**. Comment trong Dockerfile ("chưa có --proxy-headers") đúng về hậu quả, sai về nguyên nhân.
- Lifespan (nạp bge-m3) chạy **trước** khi mở socket (`uvicorn/server.py:115-116` gọi `lifespan.startup()`, sau đó
  mới `create_server`) → cổng 8000 chỉ mở khi model đã nạp xong. Probe TCP vì vậy là đủ để biết "đã sẵn sàng".

Chỗ cần đổi:
1. **Bắt buộc:** đặt `FORWARDED_ALLOW_IPS` (biến môi trường, không cần sửa Dockerfile) — mục 4.
2. ✅ **Đã làm:** thêm `exec` vào CMD để uvicorn là PID 1 và nhận SIGTERM khi Azure dừng bản. Kiểm 2026-10-12 (image
   dựng lại, env giả, `--network none`): PID 1 = `uvicorn`, `docker stop` xong sau 2,9 s (< 10 s hạn SIGKILL),
   `ExitCode=0`, log có `Shutting down` → `Application shutdown complete` → `Finished server process [1]`.
3. **Tuỳ:** `requirements.txt` gộp cả `pytest`, `kaggle` (chỉ dùng cho test / script) → image to hơn, không ảnh hưởng chạy.
4. **Tuỳ:** không ghim phiên bản (`>=`) → build lại có thể kéo bản mới khác lúc test local. Nên build 1 lần, dùng đúng
   image đó cho cả test local và Azure.
5. ✅ Chạy dưới `appuser`, bge-m3 nạp offline từ `/opt/huggingface` và lifespan hoàn tất (lần chạy kiểm ở trên, env
   giả, không mạng). Chưa kiểm lượt encode đầu tiên.

---

## 2. Biến môi trường

Đối chiếu `backend/.env.example` và mọi chỗ đọc env trong `app/` (`require_env`, `os.getenv`).

**Secret** (Container Apps → Secrets, rồi tham chiếu `secretref:`):

| Tên | Bắt buộc lúc khởi động? |
|---|---|
| `SUPABASE_URL` | có (`config.py`) |
| `SUPABASE_PUBLISHABLE_KEY` | có |
| `SUPABASE_SECRET_KEY` | có |
| `GEMINI_API_KEY` | có — `GeminiVisionProvider()` dựng trong lifespan ⚠️ (xem ghi chú) |
| `GROQ_API_KEY` | có — `create_recipe_llm()` dựng trong lifespan ⚠️ |
| `CF_ACCOUNT_ID` | có — `CloudflareFluxProvider()` đọc trong `__init__` |
| `CF_API_TOKEN` | có |
| `USDA_API_KEY` | ⚠️ có trong `.env.example` nhưng **không có chỗ nào trong `app/` đọc** (chỉ script seed?) → có thể bỏ |

`SUPABASE_URL` / `SUPABASE_PUBLISHABLE_KEY` không thật sự bí mật, nhưng để chung chỗ secret cho gọn.
Ghi chú ⚠️: chưa đọc từng provider xem có đọc key ngay lúc dựng hay để tới lúc gọi; cứ đặt đủ cả 7 là chắc chạy.

**Không bí mật** (env thường):

| Tên | Giá trị lần thử đầu | Ghi chú |
|---|---|---|
| `ENV` | `production` | |
| `CORS_ORIGINS` | `http://localhost:8081` | Giai đoạn 1 chưa có web; đổi khi deploy frontend. Không dùng `*` |
| `FRONTEND_URL` | `http://localhost:8081` | Đích link email — xem mục 7 |
| `FORWARDED_ALLOW_IPS` | xem mục 4 | **Bắt buộc** |
| `SUGGEST_LLM_ADAPT_COUNT` | `0` | Không gọi Groq trong `/recipes/suggest` (`pipeline.py:143`, `max(0, …)` nên 0 hợp lệ) |
| `RECOGNIZE_DAILY_CAP` | `200` | như `.env.example` |
| `SUGGEST_DAILY_CAP` | `15` | |
| `IMAGE_DAILY_CAP` | `50` | |
| `HF_HUB_OFFLINE` | `1` | Đã có `ENV` trong Dockerfile; đặt lại cũng không sao |

Không đặt `PORT` (để mặc định 8000, khớp target port của ingress).

---

## 3. Cấu hình đề xuất

- **Tài nguyên:** 2 vCPU / 4 GiB (Consumption cho phép cặp này ⚠️ kiểm lại trong portal vùng Malaysia West).
  Số đo cũ (feature-spec mục 7.12): RAM ~1,9 GB sau lượt tìm đầu → 4 GiB dư.
- **Replicas:** min 1, max 1 khi thử. Rate limit cửa sổ ngắn đếm trong RAM → >1 bản thì mỗi bản đếm riêng.
- ⚠️ **Chi phí:** min 1 × 2 vCPU chạy cả tháng vượt xa phần miễn phí Consumption (180 000 vCPU-giây/tháng ≈ 25 giờ ở
  2 vCPU). Thử xong nên đặt lại min 0 hoặc dừng revision. Số liệu miễn phí phải kiểm lại trên trang giá hiện tại.
- **Ingress:** external, HTTP, target port 8000, chỉ HTTPS (Azure mặc định chuyển hướng 80 → 443).

**Probe** — giới hạn theo REST spec `ContainerAppProbe` (2025-07-01): `initialDelaySeconds` 1–60,
`periodSeconds` 1–240, `failureThreshold` 1–10, `timeoutSeconds` 1–240.
⚠️ Mâu thuẫn: trang Health probes nói probe startup mặc định của portal có `failureThreshold: 240`, trái với max 10 của
spec. Cấu hình dưới đây nằm trong giới hạn spec cho an toàn.

Thời gian cần chờ: máy dev đo 37 s tới `/health` 200 (nạp model ~12 s). Trên 2 vCPU chậm hơn ⚠️ chưa đo → để ngân sách
startup ~6 phút. Thời gian kéo image (~vài GB) xảy ra **trước** khi container chạy, không tính vào probe.

```yaml
probes:
  - type: Startup          # TCP: cổng chỉ mở sau khi lifespan nạp xong bge-m3 (mục 1)
    tcpSocket: { port: 8000 }
    initialDelaySeconds: 30
    periodSeconds: 30
    failureThreshold: 10   # 30 + 30×10 ≈ 330 s
    timeoutSeconds: 5
  - type: Liveness         # TCP: không gọi Supabase, không tính vào rate limit
    tcpSocket: { port: 8000 }
    periodSeconds: 30
    failureThreshold: 3
    timeoutSeconds: 5
```

Vì sao TCP thay vì `GET /api/v1/health`: health gọi Supabase mỗi lần và trừ bộ đếm `default_ip` 30/phút; liveness vẫn
trả 200 khi Supabase hỏng nên HTTP không cho thêm thông tin gì để khởi động lại. Muốn dùng HTTP thì
`path: /api/v1/health`, period ≥ 30 s (2 lượt/phút, xa ngưỡng 30). Không thêm readiness: 1 bản, portal tự thêm
readiness TCP mặc định ⚠️ (chỉ khi tạo bằng portal).

---

## 4. `--proxy-headers` / `--forwarded-allow-ips`

Tài liệu chính thức, bảng *HTTP headers* trong
[Ingress in Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/ingress-overview#http-headers):
`X-Forwarded-For` — "If specified in initial request, it is appended to. **Only the rightmost IP is provided by Azure
Container Apps.** Any other values must be validated by the user to prevent IP spoofing."

Uvicorn 0.53 (✅ `proxy_headers.py:169-187`): duyệt `X-Forwarded-For` **từ phải sang trái**, lấy IP đầu tiên không
nằm trong danh sách tin cậy. Chỉ khi đặt `*` nó lấy IP **trái nhất** (do client tự gửi được).

Đề xuất: đặt env, không sửa CMD (uvicorn đọc `FORWARDED_ALLOW_IPS` khi không truyền cờ):

```
FORWARDED_ALLOW_IPS=10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,100.64.0.0/10
```

Hoạt động: kết nối tới từ Envoy (IP nội bộ, nằm trong dải trên) → tin header → đi từ phải, IP phải nhất là IP công khai
do Azure ghi → không nằm trong dải riêng → đó là IP client. Client gửi `X-Forwarded-For: 1.2.3.4` giả thì giá trị đó
nằm bên trái, không bao giờ được chọn. Probe gọi thẳng, không có header → giữ IP nguồn của probe.

⚠️ **Chưa kiểm chứng:** IP nguồn thật của Envoy trong environment Consumption không có VNet tự chọn. Microsoft không
công bố dải này cho trường hợp không VNet. Cách xác nhận sau deploy (không tốn quota): xem access log uvicorn (mục 6) —
dòng log in `IP:port` **sau** khi đã xử lý proxy header. Nếu thấy IP công khai của máy anh → đúng. Nếu thấy IP nội bộ
(10.x, 100.x…) → Envoy nằm ngoài dải đã tin, thêm đúng dải đó.

Rủi ro nếu đặt sai:
- **Không đặt / dải sai (trường hợp mặc định hiện tại):** mọi request đều có IP Envoy → toàn app chung một bộ đếm theo
  IP: `refresh` 20/phút, `login` 5/phút, `register` 3/giờ, `forgot_password` 3/giờ, `health` 30/phút **cho tất cả người
  dùng cộng lại**. Vài người mở app cùng lúc là bị 429.
- **Đặt `*`:** uvicorn lấy IP trái nhất = do client tự viết → đổi header là né mọi rate limit theo IP và có thể dồn bộ
  đếm của người khác (đúng cảnh báo trong tài liệu Azure ở trên và feature-spec mục 7.12).
- **Có >1 Envoy/bản:** không ảnh hưởng tới dải tin cậy; chỉ ảnh hưởng bộ đếm trong RAM (mục 3).

---

## 5. Dựng, tag, push image tới ACR bằng docker (không dùng `az acr build`)

Trạng thái máy (✅ kiểm 2026-10-12): WSL `kali-linux` (WSL2, `systemd=true`), Docker CLI 27.3.1, **dockerd đang tắt**,
`systemctl` báo `docker.service` **not-found**: daemon là bản tĩnh ở `/usr/local/bin/dockerd`, không có unit systemd. Chưa có
`buildx`, chưa có `az` trong WSL. Đang chạy dưới `root`.

**Khởi động dockerd** (chọn cái chạy được):
```powershell
# ✅ đã dùng 2026-10-12: chạy nền, tách khỏi phiên wsl (đóng phiên không giết daemon)
wsl -d kali-linux -- sh -c "setsid nohup /usr/local/bin/dockerd > /var/log/dockerd.log 2>&1 < /dev/null &"
wsl -d kali-linux -- docker info --format "{{.ServerVersion}}"   # 27.3.1
```
Lưu ý: `wsl --shutdown` hoặc tắt máy là dockerd tắt theo, phải chạy lại dòng trên.

**Đăng nhập ACR** (`az` chỉ có trên Windows, nên lấy token ở PowerShell rồi đưa sang WSL):
```powershell
az login
az acr login --name <acr> --expose-token --query accessToken -o tsv > $env:TEMP\acr.tok
wsl -d kali-linux -- sh -c "docker login <acr>.azurecr.io -u 00000000-0000-0000-0000-000000000000 --password-stdin < /mnt/c/Users/ASUS/AppData/Local/Temp/acr.tok"
Remove-Item $env:TEMP\acr.tok
```
(Token hết hạn sau ~3 giờ. Cách khác: bật admin user của ACR rồi `docker login` bằng user/password đó — đơn giản hơn
nhưng là mật khẩu dài hạn, tắt lại sau khi xong.)

**Dựng, kiểm local, push** (trong WSL, thư mục `backend/`):
```sh
cd /mnt/e/Project_AI_cooking/backend
TAG=$(git rev-parse --short HEAD)
docker build --platform linux/amd64 -t <acr>.azurecr.io/bepai-backend:$TAG .
# kiểm local trước khi đẩy (dùng .env local, không đóng vào image):
docker run --rm --env-file .env -e SUGGEST_LLM_ADAPT_COUNT=0 -p 8000:8000 <acr>.azurecr.io/bepai-backend:$TAG
#   → máy khác: curl -s localhost:8000/api/v1/health
docker push <acr>.azurecr.io/bepai-backend:$TAG
```
Không dùng tag `latest`: Container Apps chỉ tạo revision mới khi tham chiếu image đổi.
⚠️ Image ~vài GB (torch CPU + bge-m3 2,2 GB): push lần đầu lâu; ACR Basic có 10 GiB lưu trữ kèm gói — vài tag là đầy,
xoá tag cũ. Build trong `/mnt/e` (ổ Windows) chậm hơn ổ Linux của WSL, chạy được nhưng lâu.

---

## 6. Kiểm sau deploy — không tốn quota AI

Đặt `URL=https://<app>.<env-suffix>.malaysiawest.azurecontainerapps.io` ⚠️ (lấy đúng FQDN từ portal / `az containerapp show`).

```sh
# 1. Health + Supabase (gọi Supabase Auth health, không gọi AI)
curl -s $URL/api/v1/health                    # mong đợi {"status":"ok","environment":"production","supabase":"ok"}
# 2. Xác thực hoạt động: không token → 401 (không gọi Supabase)
curl -s -o /dev/null -w "%{http_code}\n" $URL/api/v1/pantry
# 3. CORS preflight từ origin được phép → có Access-Control-Allow-Origin
curl -s -i -X OPTIONS $URL/api/v1/pantry -H "Origin: http://localhost:8081" -H "Access-Control-Request-Method: GET" | grep -i access-control
# 4. HTTP → HTTPS
curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" http://<fqdn>/api/v1/health
```
```powershell
# 5. Log: thấy "Application startup complete", thời gian nạp model, và IP client trong access log (mục 4)
az containerapp logs show -n <app> -g <rg> --tail 100
# 6. RAM / CPU thật sau vài request
az monitor metrics list --resource <app-resource-id> --metric WorkingSetBytes --interval PT1M
```
7. Kiểm IP thật: gọi health từ máy anh, xem access log in IP công khai của máy (không phải 10.x/100.x). Sau đó gọi từ
   mạng khác (4G điện thoại) → IP khác. Gọi `health` 31 lần trong 1 phút từ một mạng → lần 31 bị 429, mạng kia vẫn 200.
8. Tuỳ chọn, đăng nhập bằng tài khoản thử (`POST /api/v1/auth/login`) rồi `GET /api/v1/pantry` có token → kiểm JWT +
   PostgREST. Chỉ gọi Supabase.

**Không gọi:** `/recognize` (Gemini), `/recipes/{id}/image` (Cloudflare), `/recipes/suggest` khi
`SUGGEST_LLM_ADAPT_COUNT` ≠ 0 (Groq).
Ghi chú: với `SUGGEST_LLM_ADAPT_COUNT=0`, `/recipes/suggest` chỉ chạy bge-m3 local + Postgres, không gọi API AI nào ⚠️
(đọc `pipeline.py:116-117`, chưa chạy thử), nhưng vẫn trừ quota ngày trong DB (`SUGGEST_DAILY_CAP`). Đây là cách duy nhất
kiểm bge-m3 thật sự chạy trên Azure — dùng 1 lượt nếu anh đồng ý.

---

## 7. Supabase sau khi có địa chỉ

✅ Đọc mã: link trong email xác minh / đặt lại mật khẩu trỏ về **`FRONTEND_URL`**
(`auth.py:78` → `{FRONTEND_URL}/login?verified=1`, `auth.py:122` → `{FRONTEND_URL}/reset-password`), **không** trỏ về
backend. Vậy:

- **Giai đoạn 1 (chỉ backend):** địa chỉ backend **không cần** thêm vào Supabase. Giữ `FRONTEND_URL=http://localhost:8081`
  thì link email vẫn mở về web dev local — đủ để thử.
- **Khi deploy frontend (giai đoạn 2):** Supabase → Authentication → URL Configuration:
  - **Site URL:** `https://<domain-frontend>`
  - **Redirect URLs:** `https://<domain-frontend>/login?verified=1`, `https://<domain-frontend>/reset-password`
    (hoặc `https://<domain-frontend>/**`). Giữ `http://localhost:8081/**` nếu vẫn dev local.
  - Cùng lúc đổi env backend: `FRONTEND_URL=https://<domain-frontend>`, `CORS_ORIGINS=https://<domain-frontend>`.
- Frontend trỏ về backend qua `EXPO_PUBLIC_API_URL` (`frontend/src/lib/api.ts:4`) = URL Container Apps (không kèm `/api/v1`).

---

## 8. Tóm tắt chỗ chưa kiểm chứng

1. Dải IP nguồn của Envoy trong environment Consumption không VNet → xác nhận bằng access log (mục 4).
2. Thời gian khởi động thật trên 2 vCPU (chỉ có số đo máy dev 37 s).
3. Cặp 2 vCPU / 4 GiB và giá / phần miễn phí ở Malaysia West cho gói Azure for Students.
4. Mâu thuẫn `failureThreshold` 240 (trang probe) và max 10 (REST spec).
5. Lượt encode đầu tiên dưới `appuser` (khởi động đã kiểm, encode chưa).
6. `az` chưa có trong WSL (đăng nhập ACR theo cách lấy token bên PowerShell, chưa thử).
7. `USDA_API_KEY` có thật sự thừa ở backend runtime không; Gemini/Groq có đọc key ngay lúc khởi động không.
8. `/recipes/suggest` với `SUGGEST_LLM_ADAPT_COUNT=0` không gọi Groq — mới đọc mã, chưa chạy.
9. Gói Azure for Students có chặn `az acr build` hay không (theo lời anh, chưa thử).
