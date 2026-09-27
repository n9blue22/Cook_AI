-- POST /pantry và POST /saved là upsert: thêm lại cùng nguyên liệu / cùng công thức thì cập nhật dòng cũ,
-- không nhân đôi (bấm 2 lần, quét ảnh thấy lại món đã có trong tủ).
alter table public.pantry_items
  add constraint pantry_items_user_ingredient_key unique (user_id, ingredient_id);

alter table public.saved_recipes
  add constraint saved_recipes_user_recipe_key unique (user_id, recipe_id);
