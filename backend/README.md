# Bếp AI — backend (FastAPI)

## Cài đặt

```bash
git clone <repo-url> && cd Cook_AI
git config core.hooksPath .githooks   # bật hook chặn commit lộ API key — chạy 1 lần mỗi máy, ngay sau clone
cd backend
python -m venv venv
./venv/Scripts/pip install -r requirements.txt   # macOS/Linux: ./venv/bin/pip
cp .env.example .env                              # rồi điền key thật
```

## Chạy dev

```bash
./venv/Scripts/python -m uvicorn app.main:app --port 8000
./venv/Scripts/python -m pytest
```
