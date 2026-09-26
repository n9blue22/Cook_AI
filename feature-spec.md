# Bếp AI — Feature & Architecture Spec

> Claude Code đọc file này để hiểu **cái gì cần build** và **theo thứ tự nào**.
> UI/styling xem `design/design-spec.md`. File này nói về chức năng, dữ liệu và luồng xử lý.

---

## 0. Sản phẩm là gì

Người dùng chụp ảnh **nguyên liệu thô** → AI nhận diện → hệ thống gợi ý **công thức nấu** phù hợp với chế độ ăn và dị ứng của họ, kèm **giá trị dinh dưỡng**, và (tuỳ chọn, tạo sau) **ảnh minh hoạ món sau khi nấu**. Người dùng lưu / sao chép / xoá công thức, và khi nấu xong có thể ghi vào nhật ký dinh dưỡng.

**Không phải** app log calo món đã nấu xong (đó là hướng ngược lại). Điểm khác biệt: đi từ nguyên liệu đang có → quyết định nấu gì.

**Nguyên tắc xuyên suốt:** LLM **không tự sáng tác công thức từ đầu**. Công thức lấy từ kho đã kiểm duyệt trong DB (RAG), LLM chỉ **chọn lọc + điều chỉnh** (thay nguyên liệu thiếu, đổi khẩu phần). Mọi output đều qua lớp validation trước khi hiển thị.

---

## 1. Stack

| Tầng | Công nghệ |
|---|---|
| Mobile + Web | React Native (Expo), export web qua `react-native-web`, PWA |
| Backend | FastAPI (Python), async |
| Database | PostgreSQL + pgvector (Supabase) |
| Auth | Supabase Auth |
| Lưu ảnh | Supabase Storage |
| LLM / Vision | Vision: Gemini (`gemini-3.5-flash-lite`); LLM: API free tier (Groq / OpenRouter / HuggingFace) — có thể đổi provider |
| Deploy | Backend: Render · Web: Vercel |

**Bắt buộc:** tầng gọi model phải nằm sau một interface trừu tượng (`services/llm/provider.py`) để đổi provider mà không sửa business logic.

---

## 2. Tính năng theo mức ưu tiên

### P0 — Bắt buộc có (MVP, đủ để bảo vệ đồ án)

| # | Tính năng | Mô tả |
|---|---|---|
| 1 | Đăng ký / đăng nhập | Email + password qua Supabase Auth |
| 2 | Chụp / upload ảnh nguyên liệu | Camera (mobile) hoặc dropzone (web); nhiều nguyên liệu trong 1 ảnh |
| 3 | Nhận diện nguyên liệu | Vision model trả về nguyên liệu chắc chắn (`ingredients`) + chưa chắc chắn (`uncertain`) |
| 4 | Xác nhận & chỉnh sửa | User tick/bỏ tick, sửa tên, thêm nguyên liệu thủ công |
| 5 | Bộ lọc chế độ ăn & dị ứng | Mặn / chay / thuần chay + danh sách dị ứng — **ràng buộc cứng ở tầng query** |
| 6 | Gợi ý công thức (RAG) | Vector search trên kho công thức, lọc theo tag, LLM điều chỉnh theo nguyên liệu thực có |
| 7 | Hiển thị dinh dưỡng | kcal + đạm/tinh bột/béo mỗi phần, tính từ bảng thành phần thực phẩm trong DB |
| 8 | Lớp validation an toàn | Xem mục 5 — chặn công thức không an toàn trước khi trả về |
| 9 | Lưu / sao chép / xoá công thức | CRUD trên công thức đã lưu, có tìm kiếm |
| 10 | Chế độ nấu từng bước | Hiển thị từng bước + timer, không cho rút ngắn dưới ngưỡng an toàn |

### P1 — Nên có (tăng giá trị thực tế, khác biệt với chatbot thường)

| # | Tính năng | Mô tả |
|---|---|---|
| 11 | Tủ lạnh ảo | Lưu nguyên liệu đang có, cảnh báo sắp hết hạn, gợi ý món dùng đồ sắp hỏng |
| 12 | Nhật ký dinh dưỡng | "Đã nấu xong" → tự ghi kcal vào nhật ký ngày; mục tiêu calo cá nhân |
| 13 | Ảnh minh hoạ AI | Lazy — chỉ gọi khi user bấm; luôn gắn nhãn "ảnh do AI dựng" |
| 14 | Danh sách đi chợ | Nguyên liệu còn thiếu của công thức → gom thành shopping list |
| 15 | Hồ sơ cá nhân | Dị ứng + chế độ ăn mặc định, mục tiêu calo — áp tự động cho mọi lần tìm |
| 16 | Offline (PWA) | Công thức đã lưu xem được khi mất mạng (service worker cache) |

### P2 — Nếu còn thời gian

| # | Tính năng |
|---|---|
| 17 | Ước tính chi phí nguyên liệu theo giá thị trường VN |
| 18 | Lên thực đơn tuần |
| 19 | Hỏi tiếp về công thức ("không có nồi chiên thì sao") — multi-turn |
| 20 | Đánh giá / chia sẻ công thức giữa người dùng |
| 21 | Xếp hạng công thức chưa phân biệt món chính với nước chấm/gia vị — công thức ít nguyên liệu thuộc nhóm này vẫn có thể lọt top 5 nếu user có đủ nguyên liệu. Cần thêm phân loại category món (main dish / condiment) để xử lý triệt để. |

---

## 3. Database schema (phác thảo)

```sql
-- Người dùng & hồ sơ
users(id, email, created_at)                       -- Supabase Auth quản lý
user_profiles(user_id PK/FK, diet_type, daily_kcal_goal, created_at)
user_allergens(user_id FK, allergen_id FK)         -- nhiều-nhiều

-- Danh mục chuẩn
allergens(id, name, slug)
ingredients(id, name_vi, name_en, category, is_vegetarian, is_vegan)
nutrition_facts(ingredient_id FK, kcal_100g, protein_g, carb_g, fat_g, source)

-- Kho công thức (đã kiểm duyệt, là nguồn cho RAG)
recipes(id, title, description, servings, prep_minutes, difficulty,
        diet_type, is_verified, source_url, created_at)
recipe_ingredients(recipe_id FK, ingredient_id FK, amount, unit, is_optional)
recipe_steps(recipe_id FK, step_no, instruction, min_temp_c, min_duration_sec)
recipe_allergens(recipe_id FK, allergen_id FK)     -- tính sẵn để lọc nhanh
recipe_embeddings(recipe_id FK, embedding vector(768))  -- pgvector

-- Tủ lạnh & lưu trữ của user
pantry_items(id, user_id FK, ingredient_id FK, quantity, unit, expires_on)
saved_recipes(id, user_id FK, recipe_id FK, custom_payload jsonb, saved_at)
meal_logs(id, user_id FK, recipe_id FK, kcal, protein_g, carb_g, fat_g, logged_at)

-- Ảnh
uploads(id, user_id FK, storage_path, kind)        -- kind: 'ingredient' | 'ai_dish'
```

**Index cần có:** `recipe_embeddings` dùng ivfflat/hnsw cho vector; `recipe_allergens(allergen_id)`; `recipes(diet_type)`; `pantry_items(user_id, expires_on)`.

---

## 4. Workflow chính (chụp ảnh → công thức)

```
[1] Client upload ảnh
      ↓ POST /api/v1/recognize  (multipart)
[2] Backend lưu ảnh vào Supabase Storage
      ↓
[3] Gọi vision model → {ingredients: [tên VI], uncertain: [tên VI]} (không có điểm confidence số)
      ↓
[4] Map tên nhận diện → bảng `ingredients` (fuzzy match)
      ├─ Không map được / nằm trong `uncertain` → đánh dấu "chưa chắc chắn"
      └─ Không có nguyên liệu thực phẩm nào → TRẢ LỖI, không đi tiếp
      ↓
[5] Client hiển thị để user xác nhận + chọn diet/allergen
      ↓ POST /api/v1/recipes/suggest  {ingredient_ids, diet_type, allergens (slug)}
[6] Tạo embedding từ tập nguyên liệu đã xác nhận
      ↓
[7] Vector search TRÊN TẬP ĐÃ LỌC CỨNG:
      WHERE diet_type phù hợp
        AND recipe_id NOT IN (công thức chứa allergen user khai)
      ORDER BY embedding <=> query_embedding LIMIT 10
      ↓
[8] LLM điều chỉnh top-k công thức theo nguyên liệu thực có
      → BẮT BUỘC trả JSON có cấu trúc (xem mục 5)
      → 429/timeout: gpt-oss-120b → gpt-oss-20b → Gemini → hết thì trả công thức gốc
      → mỗi công thức trả kèm `source`: "adapted" (LLM chỉnh + validate pass) | "original" (fallback)
      ↓
[9] LỚP VALIDATION (mục 5) — fail thì fallback về công thức gốc
      ↓
[10] Tính dinh dưỡng từ `nutrition_facts` theo khẩu phần → trả client
```

**Ảnh AI (tách riêng, lazy):** `POST /api/v1/recipes/{id}/image` — chỉ gọi khi user bấm nút, kết quả cache vào `uploads` để không sinh lại.

---

## 5. Lớp validation an toàn (KHÔNG ĐƯỢC BỎ QUA)

### Lớp 1 — Chặn ở đầu vào
- Nguyên liệu nhận diện phải map được vào bảng `ingredients` (whitelist thực phẩm).
- Không map được nguyên liệu nào → từ chối, trả thông báo, **không gọi LLM sinh công thức**.

### Lớp 2 — Ràng buộc cứng ở tầng query
- `diet_type` và `allergens` (slug) đưa vào **WHERE clause của SQL**, KHÔNG nhét vào prompt.
- Kết quả RAG trả về đã đúng nhóm ăn kiêng trước khi LLM nhìn thấy.

### Lớp 3 — Validate output của LLM
LLM phải trả JSON theo schema:
```json
{
  "title": "string",
  "servings": 2,
  "ingredients": [{"ingredient_id": 1, "amount": 3, "unit": "quả"}],
  "steps": [{"step_no": 1, "action": "string", "temperature_c": 75, "duration_sec": 180}]
}
```
Kiểm tra bằng **code, không hỏi lại LLM**:
1. Mọi `ingredient_id` phải tồn tại trong DB.
2. Không có nguyên liệu nào thuộc allergen user đã khai.
3. Với nguyên liệu thịt/hải sản/trứng: `temperature_c` và `duration_sec` phải ≥ ngưỡng an toàn thực phẩm trong bảng tra cứu (gà ≥74°C, bò xay ≥71°C, heo ≥63°C...). Thiếu hoặc thấp hơn → nâng về mức tối thiểu hoặc reject.
4. Số bước ≥ 1 và có ít nhất một bước nấu chín nếu công thức chứa nguyên liệu sống.

**TODO:** Validation hiện chỉ kiểm tra CÓ tồn tại bước đạt ngưỡng an toàn, chưa xác nhận đúng bước đó áp dụng cho
đúng nguyên liệu cần nấu chín. Cải tiến sau: `AdaptedRecipe.steps` thêm field `ingredient_ids: list[int]` để bước nấu
gắn rõ với nguyên liệu nào.

**Fallback:** fail bất kỳ kiểm tra nào → trả **công thức gốc chưa chỉnh sửa** từ DB (đã kiểm duyệt), không trả bản lỗi, không cố nhờ LLM sửa tiếp.

---

## 6. API endpoints

```
POST   /api/v1/auth/register
POST   /api/v1/auth/login

POST   /api/v1/recognize                 # ảnh → nguyên liệu chắc chắn + chưa chắc chắn
POST   /api/v1/recipes/suggest           # nguyên liệu + bộ lọc → danh sách công thức
GET    /api/v1/recipes/{id}              # chi tiết công thức + dinh dưỡng
POST   /api/v1/recipes/{id}/image        # tạo ảnh AI (lazy, có cache)

GET    /api/v1/saved                     # danh sách đã lưu, hỗ trợ ?q= tìm kiếm
POST   /api/v1/saved                     # lưu công thức
DELETE /api/v1/saved/{id}                # xoá

GET    /api/v1/pantry                    # tủ lạnh ảo
POST   /api/v1/pantry
DELETE /api/v1/pantry/{id}

POST   /api/v1/logs                      # ghi vào nhật ký dinh dưỡng
GET    /api/v1/logs?date=YYYY-MM-DD      # tổng hợp theo ngày

GET    /api/v1/profile
PATCH  /api/v1/profile                   # diet_type, allergens, mục tiêu calo
```

**`POST /api/v1/recipes/suggest` — body:**
```json
{ "ingredient_ids": [16, 93], "diet_type": "vegetarian", "allergens": ["egg", "soy"] }
```
- `allergens` là **slug** trong bảng `allergens` (`shellfish`, `molluscs`, `fish`, `egg`, `dairy`, `peanut`,
  `tree_nuts`, `soy`, `wheat`, `sesame`), **KHÔNG phải id số**. Truyền thẳng vào `p_allergens` của
  Postgres function `search_recipes` — không đổi slug ↔ id ở tầng service.
- `diet_type` ∈ `omnivore | vegetarian | vegan`; giá trị khác → `search_recipes` báo lỗi.

---

## 7. Thứ tự build (làm tuần tự, commit từng bước)

1. **Hạ tầng**: repo structure, FastAPI skeleton, kết nối Supabase, `.env` mẫu, healthcheck endpoint.
2. **Schema + seed**: migration tạo bảng (mục 3), seed `ingredients` + `nutrition_facts` + ~30 công thức Việt mẫu đã kiểm duyệt.
3. **Auth + profile**: đăng ký/đăng nhập, CRUD hồ sơ (diet, allergens).
4. **CRUD công thức đã lưu**: chưa cần AI, dùng dữ liệu seed — để có luồng chạy thật sớm.
5. **UI Expo**: theme + component dùng chung, rồi màn 1 → 6 với dữ liệu mock.
6. **Nối UI với API CRUD** (bước 3–4).
7. **Vector search / RAG**: sinh embedding cho công thức seed, endpoint `/recipes/suggest` với lọc cứng.
8. **Vision**: endpoint `/recognize`, map tên → `ingredients`.
   - **Đã xử lý:** `GeminiVisionProvider` đổi lỗi API / timeout / sai schema thành `VisionUnavailableError`;
     `pipeline.recognize_ingredients` log lại và ném tiếp cho route trả "không nhận diện được ảnh, thử lại".
     Ảnh không có thực phẩm → `NoUsableIngredientsError` — hai trường hợp khác nhau, route phải trả thông báo khác nhau.
9. **Lớp validation** (mục 5) + test cho từng lớp.
10. **Ảnh AI lazy** + cache.
11. **PWA**: manifest, service worker, cache công thức đã lưu.
12. **CI/CD**: GitHub Actions chạy test + deploy Render/Vercel.

---

## 8. Test bắt buộc

- Validation lớp 3: công thức thiếu nhiệt độ → bị chặn; công thức chứa allergen → bị loại.
- Query lọc cứng: user chọn "chay" → không có công thức chứa thịt trong kết quả.
- Tính dinh dưỡng: khẩu phần 2 → 4 người thì kcal nhân đôi.
- Fallback: LLM trả JSON sai schema → API vẫn trả công thức gốc, không 500.

---

## 9. Ràng buộc kỹ thuật

- **Không hardcode API key** — tất cả qua biến môi trường, có `.env.example`.
- Mọi endpoint gọi model AI phải **async** và có timeout + retry.
- Ảnh upload: giới hạn dung lượng, resize trước khi gửi lên model để tiết kiệm token.
- Số liệu dinh dưỡng **luôn lấy từ `nutrition_facts`**, không bao giờ để LLM tự sinh số.
- Log lại mọi lần validation fail để phân tích và cải thiện prompt.
- **TODO (bắt buộc trước khi deploy public):** `search_recipes` cần thêm rate limit theo IP/user trước khi deploy public
  — dùng Supabase Edge Function hoặc middleware FastAPI, không để PostgREST RPC mở tự do không giới hạn.
  (Function là `SECURITY DEFINER`, anon gọi được và mỗi lần gọi quét toàn bảng `recipes`.)
