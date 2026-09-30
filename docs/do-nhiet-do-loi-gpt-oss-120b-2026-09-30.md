# Đo nhiệt độ lõi gpt-oss-120b — main vs thu/tach-nhiet-do-loi

Đo 2026-09-30, cùng một phiên, gọi thẳng `openai/gpt-oss-120b` (429 thì chờ rồi gọi lại chính 120b, không fallback;
model thực tế ghi trong từng dòng). 3 công thức (2287, 2754, 2429) × 3 lượt cho mỗi bản:
- **main**: schema `temperature_c` hiện tại.
- **split**: schema tách `core_temp_c` / `heat_setting_c`, code thử ở tag `experiment/split-core-temp-2026-09-30`
  (không merge).

Kết luận và lý do chốt: xem feature-spec.md, mục "Đã chốt — giữ schema `temperature_c` hiện tại".

## Tổng hợp (adapted / số lần)

| Bản | 2287 | 2754 | 2429 | Tổng | Trượt vì core_temp_c null, heat_setting_c có giá trị (bản tách) | Ghi nhiệt độ lò/dầu (>100°C) vào ô nhiệt độ lõi (bản main) |
|---|---|---|---|---|---|---|
| split | 0/3 | 1/3 | 1/3 | 2/9 | 4/9 | — |
| main | 2/3 | 2/3 | 3/3 | 7/9 | — | 1/9 |

## Từng lần

| Bản | Công thức | Lượt | Model thực tế | Kết quả | Lý do validation | Bước đáng ngờ | Token | Giây | 429 |
|---|---|---|---|---|---|---|---|---|---|
| split | 2287 | 1 | openai/gpt-oss-120b | original | Có nguyên liệu cần nấu chín (['whole_cut']) nhưng không còn bước nấu | — | 5239 | 6.7 | 0 |
| split | 2754 | 1 | openai/gpt-oss-120b | original | Có nguyên liệu cần nấu chín (['poultry']) nhưng không còn bước nấu | — | 4437 | 13.3 | 1 |
| split | 2429 | 1 | openai/gpt-oss-120b | original | Có nguyên liệu cần nấu chín (['fish_shellfish']) nhưng không còn bước nấu | — | 4361 | 22.4 | 1 |
| split | 2287 | 2 | openai/gpt-oss-120b | original | Có nguyên liệu cần nấu chín (['whole_cut']) nhưng không còn bước nấu | — | 5416 | 15.8 | 0 |
| split | 2754 | 2 | openai/gpt-oss-120b | original | Có nguyên liệu cần nấu chín (['poultry']) nhưng không còn bước nấu | — | 4245 | 38.5 | 2 |
| split | 2429 | 2 | openai/gpt-oss-120b | adapted |  | — | 4843 | 24.0 | 1 |
| split | 2287 | 3 | openai/gpt-oss-120b | original | Có nguyên liệu cần nấu chín (['whole_cut']) nhưng không còn bước nấu | — | 5453 | 43.3 | 1 |
| split | 2754 | 3 | openai/gpt-oss-120b | adapted |  | — | 3927 | 20.1 | 2 |
| split | 2429 | 3 | openai/gpt-oss-120b | original | Có nguyên liệu cần nấu chín (['fish_shellfish']) nhưng không còn bước nấu | — | 4191 | 33.4 | 1 |
| main | 2287 | 1 | openai/gpt-oss-120b | original | Có nguyên liệu cần nấu chín (['whole_cut']) nhưng không còn bước nấu | — | 4734 | 21.3 | 1 |
| main | 2754 | 1 | openai/gpt-oss-120b | adapted |  | bước 5: câu không có chữ "lõi"; bước 7: câu không có chữ "lõi"; bước 8: câu không có chữ "lõi" | 4158 | 32.3 | 2 |
| main | 2429 | 1 | openai/gpt-oss-120b | adapted |  | bước 1: câu không có chữ "lõi"; bước 2: câu không có chữ "lõi"; bước 5: câu không có chữ "lõi"; bước 6: câu không có chữ "lõi" | 4300 | 36.9 | 1 |
| main | 2287 | 2 | openai/gpt-oss-120b | adapted |  | bước 2: câu không có chữ "lõi"; bước 13: câu không có chữ "lõi"; bước 14: câu không có chữ "lõi" | 4772 | 33.6 | 2 |
| main | 2754 | 2 | openai/gpt-oss-120b | adapted |  | bước 4: câu không có chữ "lõi"; bước 7: câu không có chữ "lõi"; bước 8: câu không có chữ "lõi" | 3757 | 32.2 | 2 |
| main | 2429 | 2 | openai/gpt-oss-120b | adapted |  | bước 1: câu không có chữ "lõi"; bước 2: câu không có chữ "lõi"; bước 5: câu không có chữ "lõi"; bước 6: câu không có chữ "lõi" | 4867 | 33.7 | 2 |
| main | 2287 | 3 | openai/gpt-oss-120b | adapted |  | bước 2: câu không có chữ "lõi"; bước 13: câu không có chữ "lõi"; bước 14: câu không có chữ "lõi"; bước 15: câu không có chữ "lõi" | 5606 | 30.4 | 3 |
| main | 2754 | 3 | openai/gpt-oss-120b | original | Bước 7: temperature_c=150.0°C vượt nhiệt độ lõi tối đa 100.0°C — là nhiệt độ lò/dầu, không phải lõi | bước 7: câu không có chữ "lõi"; bước 8: câu không có chữ "lõi"; bước 9: câu không có chữ "lõi" | 3508 | 40.0 | 2 |
| main | 2429 | 3 | openai/gpt-oss-120b | adapted |  | bước 1: câu không có chữ "lõi"; bước 2: câu không có chữ "lõi"; bước 5: câu không có chữ "lõi"; bước 6: câu không có chữ "lõi" | 5196 | 34.3 | 1 |

Output thô, header rate-limit và body 429 không giữ lại trong repo (file tạm đã xoá sau khi đọc bảng).
