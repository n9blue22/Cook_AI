# Chef AI: backend FastAPI + bản web Expo trong cùng một image, cùng một địa chỉ.
# Dựng từ GỐC repo (cần thấy cả frontend/; loại trừ theo .dockerignore ở gốc):
#   docker build -f backend/Dockerfile -t bepai-backend:v2 .
# Chạy: docker run --env-file backend/.env -p 8000:8000 bepai-backend:v2  (env truyền lúc chạy, không đóng vào image)

# ---- Giai đoạn 1: dựng web — chỉ dist được mang sang image cuối ----
# Node đúng bản máy dev (frontend/package.json không khai engines): node:22 (npm 10.9) từ chối package-lock.json do npm 11
# sinh ra ("Missing: @emnapi/core … from lock file").
FROM node:25.2.1-slim AS web
ENV EXPO_NO_TELEMETRY=1
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# "/" → API_BASE = "/api/v1" (cùng địa chỉ). Chỉ là tham số lúc dựng image: dev (expo start) vẫn gọi localhost:8000.
RUN EXPO_PUBLIC_API_URL=/ npx expo export --platform web --output-dir dist

# ---- Giai đoạn 2: backend ----
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/opt/huggingface
WORKDIR /app

# Lớp nặng chỉ phụ thuộc requirements-ml.txt (ghim phiên bản) → sửa requirements.txt không dựng lại torch / bge-m3.
# Index CPU của PyTorch: để pip tự chọn trên PyPI thì kéo bản CUDA (~vài GB thư viện GPU không dùng tới).
ARG TORCH_CPU_INDEX=https://download.pytorch.org/whl/cpu
COPY backend/requirements-ml.txt .
RUN pip install --no-cache-dir -r requirements-ml.txt --extra-index-url "$TORCH_CPU_INDEX"

# Đóng sẵn bge-m3 (~2,2 GB) vào image: host free xoá ổ đĩa mỗi lần khởi động lại → tải lúc chạy là mỗi lần cold start
# tải lại 2,2 GB. transformers kéo cả pytorch_model.bin (snapshot main) lẫn model.safetensors (nhánh tự chuyển đổi, cùng
# trọng số) → xoá safetensors (offline transformers chỉ đọc snapshot main),
# rồi nạp lại ở chế độ offline ngay lúc build để chắc chắn bản còn lại đủ dùng.
ARG LOAD_BGE_M3="from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"
RUN python -c "$LOAD_BGE_M3" \
    && weights="$(find "$HF_HOME" -path '*/snapshots/*/model.safetensors')" \
    && rm "$(readlink -f "$weights")" "$weights" \
    && HF_HUB_OFFLINE=1 python -c "$LOAD_BGE_M3"
ENV HF_HUB_OFFLINE=1

# Phần còn lại (requirements.txt gộp lại requirements-ml.txt bằng -r: đã cài nên pip bỏ qua). Sau đó kiểm:
# không xung đột phiên bản, torch vẫn là bản CPU, không lọt gói nvidia, bge-m3 vẫn nạp offline được.
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip check \
    && python -c "import torch; assert torch.__version__.endswith('+cpu'), torch.__version__" \
    && ! pip list 2>/dev/null | grep -qi '^nvidia' \
    && python -c "$LOAD_BGE_M3"

COPY --from=web /web/dist ./web
COPY backend/app ./app

# Dựng từ /mnt/e (ổ Windows qua WSL) thì file COPY mang quyền 777, file .lock/.refs của cache HF là 666 → appuser sửa
# được mã / cache đang chạy. Chỉ chmod đúng các mục ghi được (chmod -R cả blob 2,2 GB sẽ nhân đôi lớp model);
# bỏ qua symlink (quyền luôn 777, không có ý nghĩa; cache HF có link trỏ tới safetensors đã xoá).
# (COPY --chmod cần BuildKit; máy dựng dùng builder cũ.)
RUN find /app "$HF_HOME" ! -type l -perm /go+w -exec chmod go-w {} + && useradd --no-create-home appuser
USER appuser
EXPOSE 8000
# ponytail: chưa có --proxy-headers; thêm khi deploy kèm --forwarded-allow-ips của nền tảng (feature-spec mục 7.12)
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
