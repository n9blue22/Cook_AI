-- Dị ứng theo nguyên liệu: nguồn để tính sẵn recipe_allergens khi seed công thức (lớp validation 2).

create table public.ingredient_allergens (
  ingredient_id bigint not null references public.ingredients (id) on delete cascade,
  allergen_id   bigint not null references public.allergens (id) on delete restrict,
  primary key (ingredient_id, allergen_id)
);
create index ingredient_allergens_allergen_id_idx on public.ingredient_allergens (allergen_id);

alter table public.ingredient_allergens enable row level security;
grant select on public.ingredient_allergens to anon, authenticated;
create policy "catalog readable" on public.ingredient_allergens for select to anon, authenticated using (true);

-- 10 nhóm dị ứng chính (EU 14 rút gọn cho món Việt + Âu phổ biến).
insert into public.allergens (name, slug) values
  ('Giáp xác (tôm, cua)', 'shellfish'),
  ('Nhuyễn thể (mực, nghêu, sò, hàu)', 'molluscs'),
  ('Cá', 'fish'),
  ('Trứng', 'egg'),
  ('Sữa', 'dairy'),
  ('Đậu phộng', 'peanut'),
  ('Hạt cây (điều, óc chó, hồ đào)', 'tree_nuts'),
  ('Đậu nành', 'soy'),
  ('Lúa mì (gluten)', 'wheat'),
  ('Mè', 'sesame')
on conflict (slug) do nothing;
