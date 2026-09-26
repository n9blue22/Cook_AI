-- Insert 1 công thức cùng recipe_ingredients, recipe_steps, recipe_allergens trong 1 transaction.
-- PostgREST không có transaction giữa các request → insert rời từng bảng có thể để lại recipe mồ côi.

create or replace function public.insert_recipe(
  recipe       jsonb,     -- {title, description, servings, prep_minutes, diet_type, is_verified, source_url}
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
  insert into public.recipes (title, description, servings, prep_minutes, diet_type, is_verified, source_url)
  values (
    recipe ->> 'title',
    recipe ->> 'description',
    (recipe ->> 'servings')::integer,
    (recipe ->> 'prep_minutes')::integer,
    recipe ->> 'diet_type',
    (recipe ->> 'is_verified')::boolean,
    recipe ->> 'source_url'
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

-- Chỉ script seed (secret key → service_role) được gọi; app/frontend không được ghi kho công thức.
revoke execute on function public.insert_recipe(jsonb, jsonb, jsonb, bigint[]) from public, anon, authenticated;
grant execute on function public.insert_recipe(jsonb, jsonb, jsonb, bigint[]) to service_role;
