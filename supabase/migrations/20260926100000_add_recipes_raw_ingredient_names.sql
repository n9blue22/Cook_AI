-- Tên nguyên liệu gốc (nguyên văn từ dataset) KHÔNG map được về bảng ingredients.
-- Trước đây bị bỏ qua âm thầm → có món mất cả nguyên liệu chính ("seaweed salad" không có rong biển).
alter table public.recipes
  add column raw_ingredient_names text[] not null default '{}';

comment on column public.recipes.raw_ingredient_names is
  'Tên nguyên liệu gốc không map được về ingredients (nguyên văn nguồn); phần đã map nằm ở recipe_ingredients.';

-- insert_recipe nhận thêm recipe.raw_ingredient_names (mảng JSON), vẫn trong 1 transaction.
create or replace function public.insert_recipe(
  recipe       jsonb,     -- {title, description, servings, prep_minutes, diet_type, is_verified, source_url, raw_ingredient_names}
  ingredients  jsonb,     -- [{ingredient_id, amount, unit}]
  steps        jsonb,     -- [{step_no, instruction}]
  allergen_ids bigint[]
)
returns bigint
language plpgsql
set search_path = ''
as $$
declare
  new_recipe_id bigint;
begin
  insert into public.recipes (
    title, description, servings, prep_minutes, diet_type, is_verified, source_url, raw_ingredient_names
  )
  values (
    recipe ->> 'title',
    recipe ->> 'description',
    (recipe ->> 'servings')::integer,
    (recipe ->> 'prep_minutes')::integer,
    recipe ->> 'diet_type',
    (recipe ->> 'is_verified')::boolean,
    recipe ->> 'source_url',
    coalesce(
      array(select jsonb_array_elements_text(recipe -> 'raw_ingredient_names')),
      '{}'
    )
  )
  returning id into new_recipe_id;

  insert into public.recipe_ingredients (recipe_id, ingredient_id, amount, unit)
  select new_recipe_id, item.ingredient_id, item.amount, item.unit
  from jsonb_to_recordset(ingredients) as item (ingredient_id bigint, amount numeric, unit text);

  insert into public.recipe_steps (recipe_id, step_no, instruction)
  select new_recipe_id, step.step_no, step.instruction
  from jsonb_to_recordset(steps) as step (step_no integer, instruction text);

  insert into public.recipe_allergens (recipe_id, allergen_id)
  select new_recipe_id, allergen_id
  from unnest(allergen_ids) as allergen_id;

  return new_recipe_id;
end;
$$;

revoke execute on function public.insert_recipe(jsonb, jsonb, jsonb, bigint[]) from public, anon, authenticated;
grant execute on function public.insert_recipe(jsonb, jsonb, jsonb, bigint[]) to service_role;
