## Design
UI theo `design/design-spec.md` — đọc file này trước khi viết bất kỳ component nào.
Mockup gốc từng màn: `design/artboards/*.dc.html` (mở bằng trình duyệt để xem layout).
Không tự chọn màu/font khác với token trong spec.
## AI Pipeline
Đọc feature-spec.md trước khi code bất kỳ phần AI nào.
Tất cả API key lấy từ biến môi trường, không hardcode.
Tầng gọi model phải nằm sau interface trừu tượng trong services/.


## Code Quality — bắt buộc tuân theo mọi lúc

**Function:**
- Mỗi function chỉ làm **một việc**. Dài quá ~40 dòng → tách nhỏ.
- Route handler (FastAPI) **không chứa business logic** — chỉ nhận request, gọi service, trả response. Logic thật nằm trong `services/`.
- Không nesting if/for quá 3 cấp — dùng early return thay vì if lồng nhau.

**Trùng lặp:**
- Thấy đoạn code giống nhau xuất hiện ≥2 lần → dừng lại, tách thành hàm/module dùng chung trước khi viết tiếp.
- Trước khi thêm function mới, tìm trong codebase xem đã có cái tương tự chưa — ưu tiên tái dùng/mở rộng thay vì viết lại.

**Đặt tên:**
- Tên function/biến phải nói rõ nó làm gì, không viết tắt mơ hồ (`process_data` ❌, `normalize_ingredient_name` ✅).
- Không magic number/string — đặt hằng số có tên (`MIN_TEMP_C = 74`, không viết thẳng số `74` rải trong code).

**Kiểu & lỗi:**
- Python: mọi function public có type hint đầy đủ + docstring 1-2 dòng nói mục đích.
- TypeScript/RN: không dùng `any`, định nghĩa type/interface rõ ràng cho props và API response.
- Không bao giờ viết `except Exception: pass` hoặc `catch {}` nuốt lỗi âm thầm — luôn log hoặc xử lý cụ thể.

**Kích thước file:**
- File vượt quá ~300 dòng → đề xuất tách trước khi viết thêm, không im lặng viết tiếp cho dài ra.

**Sau mỗi tính năng:**
- Trước khi báo "xong", tự đọc lại phần vừa viết một lượt: có đơn giản hoá được không, có phần nào thừa không, có tên nào cần đổi không.
## Git commits
Không thêm bất kỳ dòng attribution nào (Co-Authored-By, Generated with,
Claude-Session...) vào commit message. Sau mỗi commit, tự kiểm tra bằng
grep và amend nếu lỡ có.