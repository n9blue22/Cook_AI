-- 1) Công thức ít nguyên liệu bắt buộc (ớt ngâm nước mắm, ớt bột…) dễ đạt coverage = 1 và lấn món chính:
--    coverage chỉ được tính đủ trọng số khi có >= 3 nguyên liệu bắt buộc, ít hơn thì nhân n/3.
--    Lọc MIN_COVERAGE vẫn dùng coverage thô (user phải có đủ phần lớn nguyên liệu).
-- 2) Trả thêm source_url + raw_ingredient_names: pipeline gọi bằng publishable key, RLS chặn đọc recipes.
-- Đổi kiểu trả về → drop rồi tạo lại; giữ SECURITY DEFINER + search_path = '' như bản trước.
drop function public.search_recipes(extensions.vector, text, text[], int[]);

create function public.search_recipes(
  query_embedding  extensions.vector(1024),
  p_diet           text,     -- 'omnivore' | 'vegetarian' | 'vegan'
  p_allergens      text[],   -- allergens.slug user khai; null/rỗng = không lọc
  p_ingredient_ids int[]     -- nguyên liệu user đang có
)
returns table (
  recipe_id bigint, title text, servings integer, source_url text, raw_ingredient_names text[],
  sim double precision, coverage double precision, score double precision)
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  SIM_WEIGHT                  constant double precision := 0.6;
  COVERAGE_WEIGHT             constant double precision := 0.4;
  MIN_COVERAGE                constant double precision := 0.5;
  FULL_COVERAGE_MIN_REQUIRED  constant double precision := 3;
  RESULT_LIMIT                constant integer := 5;
  allowed_diets               text[];
begin
  -- Diet chặt hơn được phép: user chay ăn được món thuần chay, user mặn ăn được mọi món.
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
      1 - (r.embedding operator(extensions.<=>) query_embedding) as sim,
      req.coverage,  -- null khi recipe không có nguyên liệu bắt buộc → bị loại ở WHERE dưới
      req.required_count
    from public.recipes r
    cross join lateral (
      select
        avg((ri.ingredient_id = any (p_ingredient_ids))::int)::double precision as coverage,
        count(*) as required_count
      from public.recipe_ingredients ri
      where ri.recipe_id = r.id and not ri.is_optional
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
    c.id, c.title, c.servings, c.source_url, c.raw_ingredient_names, c.sim, c.coverage,
    SIM_WEIGHT * c.sim
      + COVERAGE_WEIGHT * c.coverage * least(1, c.required_count / FULL_COVERAGE_MIN_REQUIRED)
  from candidates c
  where c.coverage >= MIN_COVERAGE
  order by 8 desc
  limit RESULT_LIMIT;
end;
$$;
