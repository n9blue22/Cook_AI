-- search_recipes trả thêm servings: pipeline gọi bằng publishable key, RLS chặn đọc recipes chưa kiểm duyệt
-- nên không tự lấy được servings (cần để LLM chỉnh khẩu phần + chia dinh dưỡng theo suất).
-- Đổi kiểu trả về → phải drop rồi tạo lại; giữ SECURITY DEFINER + search_path = '' như bản trước.
drop function public.search_recipes(extensions.vector, text, text[], int[]);

create function public.search_recipes(
  query_embedding  extensions.vector(1024),
  p_diet           text,     -- 'omnivore' | 'vegetarian' | 'vegan'
  p_allergens      text[],   -- allergens.slug user khai; null/rỗng = không lọc
  p_ingredient_ids int[]     -- nguyên liệu user đang có
)
returns table (
  recipe_id bigint, title text, servings integer, sim double precision, coverage double precision, score double precision)
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  SIM_WEIGHT      constant double precision := 0.6;
  COVERAGE_WEIGHT constant double precision := 0.4;
  MIN_COVERAGE    constant double precision := 0.5;
  RESULT_LIMIT    constant integer := 5;
  allowed_diets   text[];
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
      1 - (r.embedding operator(extensions.<=>) query_embedding) as sim,
      (
        select avg((ri.ingredient_id = any (p_ingredient_ids))::int)::double precision
        from public.recipe_ingredients ri
        where ri.recipe_id = r.id and not ri.is_optional
      ) as coverage  -- null khi recipe không có nguyên liệu bắt buộc → bị loại ở WHERE dưới
    from public.recipes r
    where r.embedding is not null
      and r.diet_type = any (allowed_diets)
      and not exists (
        select 1
        from public.recipe_allergens ra
        join public.allergens a on a.id = ra.allergen_id
        where ra.recipe_id = r.id and a.slug = any (p_allergens)
      )
  )
  select c.id, c.title, c.servings, c.sim, c.coverage, SIM_WEIGHT * c.sim + COVERAGE_WEIGHT * c.coverage
  from candidates c
  where c.coverage >= MIN_COVERAGE
  order by 6 desc
  limit RESULT_LIMIT;
end;
$$;
