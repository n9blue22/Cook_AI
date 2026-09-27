# Bếp AI — frontend (Expo)

## Chạy dev

```bash
npx expo start --web --port 8081   # web (PWA); bỏ --web để chạy Expo Go / simulator
npx tsc --noEmit                    # typecheck
npx expo lint                       # lint
npm test                            # test logic thuần (node --test, không cần thư viện)
```

Backend mặc định ở `http://localhost:8000`. Trỏ sang backend khác bằng `EXPO_PUBLIC_API_URL` (vd trong
`frontend/.env`: `EXPO_PUBLIC_API_URL=https://api.example.com`). Backend phải có domain frontend trong `CORS_ORIGINS`.

Chạy backend (thư mục `backend/`):

```bash
./venv/Scripts/python -m uvicorn app.main:app --port 8000
# Sau proxy (Render…): thêm --proxy-headers --forwarded-allow-ips="*" để rate limit theo IP thấy IP thật của user
```

## Đăng nhập & session

- Mọi màn app bị chặn khi chưa đăng nhập (`Stack.Protected` trong `src/app/_layout.tsx`); màn nào mới thêm phải
  khai báo trong nhóm Protected, không khai báo thì expo-router tự thêm NGOÀI lớp chặn.
- Điện thoại: refresh token trong `expo-secure-store`. Web: SecureStore không chạy → refresh token nằm trong cookie
  httpOnly do backend đặt; access token chỉ giữ trong bộ nhớ, không bao giờ ghi xuống máy.

## Tắt Metro triệt để

Dừng lệnh `npx expo start` (Ctrl+C, hoặc tắt task chạy nền của editor/agent) **có thể không tắt tiến trình
`node` Metro bên dưới**. Metro sót lại vẫn giữ cổng 8081 và phục vụ bundle cũ (chạy với `CI=1` thì không
theo dõi file, sửa code không thấy thay đổi). Lần `expo start` sau sẽ báo cổng bận / `Skipping dev server`.

Luôn tắt theo cổng, rồi kiểm tra lại cổng đã trống:

**Windows — PowerShell**
```powershell
# Xem tiến trình nào giữ cổng 8081
Get-NetTCPConnection -LocalPort 8081 -State Listen |
  ForEach-Object { Get-CimInstance Win32_Process -Filter "ProcessId=$($_.OwningProcess)" | Select-Object ProcessId, CommandLine }

# Tắt hẳn
Get-NetTCPConnection -LocalPort 8081 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess }
```

**Windows — cmd / Git Bash**
```bash
netstat -ano | findstr :8081    # cột cuối là PID
taskkill /PID <PID> /F
```

**macOS / Linux**
```bash
lsof -ti tcp:8081 | xargs kill
```

Kiểm tra: chạy lại lệnh xem cổng — không còn dòng `LISTENING` trên 8081 là đã sạch.
