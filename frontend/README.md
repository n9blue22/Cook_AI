# Bếp AI — frontend (Expo)

## Chạy dev

```bash
npx expo start --web --port 8081   # web (PWA); bỏ --web để chạy Expo Go / simulator
npx tsc --noEmit                    # typecheck
npx expo lint                       # lint
```

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
