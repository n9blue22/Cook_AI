# Bếp AI

## Bước 1 — bật hook chặn lộ secret (làm trước mọi bước khác)

Ngay sau khi clone, chạy 1 lần mỗi máy:

```bash
git config core.hooksPath .githooks
```

Hook `pre-commit` quét phần sắp commit và chặn nếu có API key / token (cần `python` trong PATH).

## Cài đặt chi tiết

- Backend (FastAPI): [backend/README.md](backend/README.md)
- Frontend (Expo): [frontend/README.md](frontend/README.md)
