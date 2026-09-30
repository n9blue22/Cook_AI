-- Món đã kiểm duyệt (is_verified — hiện trùng khít với ViFoodRec tiếng Việt) được cộng điểm thưởng nhỏ để lên trước;
-- Food.com (tiếng Anh, chưa dịch) vẫn xuất hiện làm phần bổ sung khi khớp tốt hơn rõ rệt.
-- VERIFIED_BONUS = 0.05 chốt trước khi đo, tương đương ~0.083 độ giống embedding (SIM_WEIGHT 0.6), không đủ đảo ngược
-- một món khớp kém hẳn. Đo trước/sau trên 6 bộ nguyên liệu: xem feature-spec.
-- Chữ ký hàm giữ nguyên → create or replace, quyền (chỉ service_role) giữ nguyên.
create or replace function public.search_recipes(
  query_embedding  extensions.vector(1024),
  p_diet           text,
  p_allergens      text[],
  p_ingredient_ids int[],
  p_pantry_basic_ids int[] default '{}'
)
returns table (
  recipe_id bigint, title text, servings integer, source_url text, raw_ingredient_names text[],
  prep_minutes integer, sim double precision, coverage double precision, score double precision)
language plpgsql
stable
security invoker
set search_path = ''
as $$
declare
  SIM_WEIGHT                  constant double precision := 0.6;
  COVERAGE_WEIGHT             constant double precision := 0.4;
  VERIFIED_BONUS              constant double precision := 0.05;
  MIN_COVERAGE                constant double precision := 0.5;
  FULL_COVERAGE_MIN_REQUIRED  constant double precision := 3;
  RESULT_LIMIT                constant integer := 5;
  allowed_diets               text[];
begin
  allowed_diets := case p_diet
    when 'vegan'      then array['vegan']
    when 'vegetarian' then array['vegetarian', 'vegan']
    when 'omnivore'   then array['omnivore', 'vegetarian', 'vegan']
  end;
  if allowed_diets is null then
    raise exception 'p_diet không hợp lệ: % (cần omnivore | vegetarian | vegan)', p_diet;
  end if;

  -- ponytail: quét tuần tự + tính khoảng cách chính xác (~3k recipe, vài ms); HNSW không dùng được vì xếp theo score.
  -- Khi lên ~100k recipe: lấy trước top-N theo embedding <=> query_embedding (dùng index) rồi mới tính coverage.
  return query
  with candidates as (
    select
      r.id,
      r.title,
      r.servings,
      r.source_url,
      r.raw_ingredient_names,
      r.prep_minutes,
      r.is_verified,
      1 - (r.embedding operator(extensions.<=>) query_embedding) as sim,
      req.coverage,
      req.required_count
    from public.recipes r
    cross join lateral (
      select
        avg((ri.ingredient_id = any (p_ingredient_ids))::int)::double precision as coverage,
        count(*) as required_count
      from public.recipe_ingredients ri
      where ri.recipe_id = r.id and not ri.is_optional
        and not (ri.ingredient_id = any (p_pantry_basic_ids))
    ) req
    where r.embedding is not null
      and r.diet_type = any (allowed_diets)
      and not exists (
        select 1
        from public.recipe_allergens ra
        join public.allergens a on a.id = ra.allergen_id
        where ra.recipe_id = r.id and a.slug = any (p_allergens)
      )
  )
  select
    c.id, c.title, c.servings, c.source_url, c.raw_ingredient_names, c.prep_minutes, c.sim, c.coverage,
    SIM_WEIGHT * c.sim
      + COVERAGE_WEIGHT * c.coverage * least(1, c.required_count / FULL_COVERAGE_MIN_REQUIRED)
      + case when c.is_verified then VERIFIED_BONUS else 0 end
  from candidates c
  where c.coverage >= MIN_COVERAGE
  order by 9 desc
  limit RESULT_LIMIT;
end;
$$;
