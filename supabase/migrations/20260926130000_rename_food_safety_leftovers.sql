-- Đổi category 'leftovers' → 'leftovers_casserole' (giữ nguyên id để FK ingredients.food_safety_id không đổi).
-- DB mới: bảng còn trống lúc chạy migration → không ảnh hưởng; seed_food_safety tạo luôn tên mới.
update public.food_safety set category = 'leftovers_casserole' where category = 'leftovers';
