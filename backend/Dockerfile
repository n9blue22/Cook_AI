# Backend Bếp AI. Build từ thư mục backend/: docker build -t bepai-backend .
# Chạy: docker run --env-file .env -p 8000:8000 bepai-backend  (env truyền lúc chạy, không đóng vào image)
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/opt/huggingface
WORKDIR /app

# torch bản CPU trước: để pip tự chọn thì kéo bản CUDA (~vài GB thư viện GPU không dùng tới)
COPY requirements.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

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

COPY app ./app

RUN useradd --no-create-home appuser
USER appuser
EXPOSE 8000
# ponytail: chưa có --proxy-headers; thêm khi deploy kèm --forwarded-allow-ips của nền tảng (feature-spec mục 7.12)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
