-- Schema lõi cho Bếp AI (feature-spec.md mục 3).
-- Người dùng do Supabase Auth quản lý (auth.users) — không tạo bảng users riêng.
-- Embedding lưu thẳng cột recipes.embedding thay cho bảng recipe_embeddings (quan hệ 1-1).

create extension if not exists vector with schema extensions;

-- ============================================================
-- Danh mục chuẩn (đọc công khai, chỉ ghi qua service role / migration)
-- ============================================================

create table public.allergens (
  id   bigint generated always as identity primary key,
  name text not null,
  slug text not null unique
);

-- Ngưỡng an toàn thực phẩm cho lớp validation 3 (gà ≥74°C, bò xay ≥71°C, heo ≥63°C...)
create table public.food_safety (
  id               bigint generated always as identity primary key,
  category         text not null unique,
  min_temp_c       numeric(5, 1) not null check (min_temp_c > 0),
  min_duration_sec integer not null default 0 check (min_duration_sec >= 0),
  note             text
);

create table public.ingredients (
  id             bigint generated always as identity primary key,
  name_vi        text not null,
  name_en        text,
  category       text not null,
  is_vegetarian  boolean not null default false,
  is_vegan       boolean not null default false,
  food_safety_id bigint references public.food_safety (id) on delete set null,
  constraint ingredients_vegan_implies_vegetarian check (not is_vegan or is_vegetarian)
);
create unique index ingredients_name_vi_key on public.ingredients (lower(name_vi));
create index ingredients_food_safety_id_idx on public.ingredients (food_safety_id);

-- Giá trị dinh dưỡng trên 100g, 1-1 với ingredients
create table public.nutrition_facts (
  ingredient_id bigint primary key references public.ingredients (id) on delete cascade,
  kcal_100g     numeric(7, 2) not null check (kcal_100g >= 0),
  protein_g     numeric(6, 2) not null check (protein_g >= 0),
  carb_g        numeric(6, 2) not null check (carb_g >= 0),
  fat_g         numeric(6, 2) not null check (fat_g >= 0),
  source        text not null
);

-- ============================================================
-- Kho công thức đã kiểm duyệt (nguồn cho RAG)
-- ============================================================

create table public.recipes (
  id           bigint generated always as identity primary key,
  title        text not null,
  description  text,
  servings     integer not null check (servings > 0),
  prep_minutes integer check (prep_minutes >= 0),
  difficulty   text check (difficulty in ('easy', 'medium', 'hard')),
  diet_type    text not null check (diet_type in ('omnivore', 'vegetarian', 'vegan')),
  is_verified  boolean not null default false,
  source_url   text,
  embedding    extensions.vector(1024),  -- bge-m3 (dense, 1024 chiều)
  created_at   timestamptz not null default now()
);
create index recipes_diet_type_idx on public.recipes (diet_type);
create index recipes_embedding_idx on public.recipes
  using hnsw (embedding extensions.vector_cosine_ops);

create table public.recipe_ingredients (
  recipe_id     bigint not null references public.recipes (id) on delete cascade,
  ingredient_id bigint not null references public.ingredients (id) on delete restrict,
  amount        numeric(10, 2) check (amount > 0),
  unit          text,
  is_optional   boolean not null default false,
  primary key (recipe_id, ingredient_id)
);
create index recipe_ingredients_ingredient_id_idx on public.recipe_ingredients (ingredient_id);

create table public.recipe_steps (
  recipe_id        bigint not null references public.recipes (id) on delete cascade,
  step_no          integer not null check (step_no > 0),
  instruction      text not null,
  min_temp_c       numeric(5, 1) check (min_temp_c > 0),
  min_duration_sec integer check (min_duration_sec >= 0),
  primary key (recipe_id, step_no)
);

-- Tính sẵn để lọc dị ứng ngay trong WHERE (lớp validation 2)
create table public.recipe_allergens (
  recipe_id  bigint not null references public.recipes (id) on delete cascade,
  allergen_id bigint not null references public.allergens (id) on delete restrict,
  primary key (recipe_id, allergen_id)
);
create index recipe_allergens_allergen_id_idx on public.recipe_allergens (allergen_id);

-- ============================================================
-- Dữ liệu riêng của từng user
-- ============================================================

create table public.user_profiles (
  user_id         uuid primary key references auth.users (id) on delete cascade,
  diet_type       text not null default 'omnivore'
                  check (diet_type in ('omnivore', 'vegetarian', 'vegan')),
  daily_kcal_goal integer check (daily_kcal_goal > 0),
  created_at      timestamptz not null default now()
);

create table public.user_allergens (
  user_id     uuid not null references auth.users (id) on delete cascade,
  allergen_id bigint not null references public.allergens (id) on delete cascade,
  primary key (user_id, allergen_id)
);
create index user_allergens_allergen_id_idx on public.user_allergens (allergen_id);

create table public.pantry_items (
  id            bigint generated always as identity primary key,
  user_id       uuid not null references auth.users (id) on delete cascade,
  ingredient_id bigint not null references public.ingredients (id) on delete restrict,
  quantity      numeric(10, 2) check (quantity >= 0),
  unit          text,
  expires_on    date
);
create index pantry_items_user_id_expires_on_idx on public.pantry_items (user_id, expires_on);
create index pantry_items_ingredient_id_idx on public.pantry_items (ingredient_id);

create table public.saved_recipes (
  id             bigint generated always as identity primary key,
  user_id        uuid not null references auth.users (id) on delete cascade,
  recipe_id      bigint not null references public.recipes (id) on delete cascade,
  custom_payload jsonb,
  saved_at       timestamptz not null default now()
);
create index saved_recipes_user_id_saved_at_idx on public.saved_recipes (user_id, saved_at desc);
create index saved_recipes_recipe_id_idx on public.saved_recipes (recipe_id);

create table public.meal_logs (
  id        bigint generated always as identity primary key,
  user_id   uuid not null references auth.users (id) on delete cascade,
  recipe_id bigint references public.recipes (id) on delete set null,
  kcal      numeric(7, 2) not null check (kcal >= 0),
  protein_g numeric(6, 2) not null check (protein_g >= 0),
  carb_g    numeric(6, 2) not null check (carb_g >= 0),
  fat_g     numeric(6, 2) not null check (fat_g >= 0),
  logged_at timestamptz not null default now()
);
create index meal_logs_user_id_logged_at_idx on public.meal_logs (user_id, logged_at);
create index meal_logs_recipe_id_idx on public.meal_logs (recipe_id);

-- kind 'ai_dish' gắn với recipe_id để cache ảnh AI, không sinh lại
create table public.uploads (
  id           bigint generated always as identity primary key,
  user_id      uuid not null references auth.users (id) on delete cascade,
  recipe_id    bigint references public.recipes (id) on delete cascade,
  storage_path text not null,
  kind         text not null check (kind in ('ingredient', 'ai_dish')),
  created_at   timestamptz not null default now(),
  constraint uploads_ai_dish_has_recipe check (kind <> 'ai_dish' or recipe_id is not null)
);
create index uploads_user_id_idx on public.uploads (user_id);
create index uploads_recipe_id_idx on public.uploads (recipe_id);

-- ============================================================
-- RLS + quyền truy cập Data API
-- ============================================================

alter table public.allergens          enable row level security;
alter table public.food_safety        enable row level security;
alter table public.ingredients        enable row level security;
alter table public.nutrition_facts    enable row level security;
alter table public.recipes            enable row level security;
alter table public.recipe_ingredients enable row level security;
alter table public.recipe_steps       enable row level security;
alter table public.recipe_allergens   enable row level security;
alter table public.user_profiles      enable row level security;
alter table public.user_allergens     enable row level security;
alter table public.pantry_items       enable row level security;
alter table public.saved_recipes      enable row level security;
alter table public.meal_logs          enable row level security;
alter table public.uploads            enable row level security;

-- Danh mục: ai cũng đọc được, không ai ghi qua API (không có policy ghi)
grant select on public.allergens, public.food_safety, public.ingredients,
  public.nutrition_facts, public.recipes, public.recipe_ingredients,
  public.recipe_steps, public.recipe_allergens
  to anon, authenticated;

create policy "catalog readable" on public.allergens          for select to anon, authenticated using (true);
create policy "catalog readable" on public.food_safety        for select to anon, authenticated using (true);
create policy "catalog readable" on public.ingredients        for select to anon, authenticated using (true);
create policy "catalog readable" on public.nutrition_facts    for select to anon, authenticated using (true);
create policy "catalog readable" on public.recipe_ingredients for select to anon, authenticated using (true);
create policy "catalog readable" on public.recipe_steps       for select to anon, authenticated using (true);
create policy "catalog readable" on public.recipe_allergens   for select to anon, authenticated using (true);
create policy "verified recipes readable" on public.recipes   for select to anon, authenticated using (is_verified);

-- Dữ liệu user: chỉ chủ sở hữu đọc/ghi
grant select, insert, update, delete on public.user_profiles, public.user_allergens,
  public.pantry_items, public.saved_recipes, public.meal_logs, public.uploads
  to authenticated;

do $$
declare
  owned_table text;
begin
  foreach owned_table in array array[
    'user_profiles', 'user_allergens', 'pantry_items', 'saved_recipes', 'meal_logs', 'uploads'
  ] loop
    execute format(
      'create policy "owner select" on public.%I for select to authenticated using ((select auth.uid()) = user_id)',
      owned_table);
    execute format(
      'create policy "owner insert" on public.%I for insert to authenticated with check ((select auth.uid()) = user_id)',
      owned_table);
    execute format(
      'create policy "owner update" on public.%I for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id)',
      owned_table);
    execute format(
      'create policy "owner delete" on public.%I for delete to authenticated using ((select auth.uid()) = user_id)',
      owned_table);
  end loop;
end
$$;
