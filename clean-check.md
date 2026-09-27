---
description: Rà soát code vừa viết theo chuẩn clean code trước khi báo hoàn thành
---

Xem lại các file vừa thay đổi (dùng `git diff` hoặc `git status` để biết file nào) theo checklist sau, và **sửa trực tiếp** nếu vi phạm — không chỉ liệt kê rồi để đó:

1. Function nào dài hơn ~40 dòng hoặc làm nhiều hơn 1 việc → tách nhỏ
2. Có đoạn code nào lặp lại ≥2 lần → tách thành hàm/module dùng chung
3. Có nesting if/for sâu hơn 3 cấp → dùng early return để làm phẳng
4. Có magic number/string nào không rõ nghĩa → đặt hằng số có tên
5. Route/controller (FastAPI) có chứa business logic không → chuyển sang service layer
6. Có `except`/`catch` nào nuốt lỗi âm thầm không → xử lý hoặc log rõ ràng
7. Tên biến/hàm có mơ hồ, viết tắt khó hiểu không → đổi tên rõ nghĩa
8. File nào vượt quá 300 dòng → đề xuất tách file
9. Type hint (Python) / type rõ ràng (TypeScript) có đầy đủ không

Sau khi rà xong, báo cáo ngắn gọn:
- Đã sửa gì (liệt kê 1 dòng mỗi chỗ)
- Nếu không sửa gì, nói rõ vì sao (ví dụ: đã đủ đơn giản, không có vi phạm)

**Không được:** tự ý đổi kiến trúc lớn, đổi tên public API/endpoint, hay đổi behavior của tính năng mà không hỏi trước — đây chỉ là dọn dẹp code, không phải viết lại.