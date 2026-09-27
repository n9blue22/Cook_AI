-- Auth + bảo mật (feature-spec mục 2 P0#1, 3, 6, 9).

-- 1. Tự tạo user_profiles khi có user mới — kể cả user đăng ký thẳng qua Supabase Auth, không qua backend.
create function public.handle_new_user()
returns trigger
language plpgsql
security definer          -- ghi user_profiles thay user chưa có session; chỉ chạy qua trigger
set search_path = ''
as $$
begin
  insert into public.user_profiles (user_id) values (new.id) on conflict (user_id) do nothing;
  return new;
end;
$$;
revoke execute on function public.handle_new_user() from public, anon, authenticated;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

insert into public.user_profiles (user_id) select id from auth.users on conflict (user_id) do nothing;

-- 2. search_recipes: chỉ backend (service_role, đã có rate limit) được gọi. Trước đây anon gọi thẳng qua PostgREST
--    được, bỏ qua mọi giới hạn (TODO mục 9). service_role bỏ qua RLS nên không cần SECURITY DEFINER nữa.
alter function public.search_recipes(extensions.vector, text, text[], int[]) security invoker;
revoke execute on function public.search_recipes(extensions.vector, text, text[], int[]) from public, anon, authenticated;
grant execute on function public.search_recipes(extensions.vector, text, text[], int[]) to service_role;

-- 3. Quota theo ngày (giờ VN) cho endpoint tốn quota AI. Lưu DB vì Render free tắt server khi rảnh → bộ đếm
--    trong RAM về 0. Chỉ backend (service_role) đọc/ghi.
create table public.api_quota_usage (
  bucket     text    not null,  -- 'user:<uuid>:suggest' | 'global:suggest'
  usage_date date    not null,
  used       integer not null default 0 check (used >= 0),
  primary key (bucket, usage_date)
);
alter table public.api_quota_usage enable row level security;  -- không policy: anon/authenticated không thấy gì
revoke all on public.api_quota_usage from anon, authenticated;
grant select, insert, update on public.api_quota_usage to service_role;

-- Tăng tất cả bucket 1 đơn vị nếu MỌI bucket còn dưới hạn mức; ngược lại không tăng gì (all-or-nothing,
-- để user bị chặn không ăn mất quota tổng và ngược lại). Trả true = được dùng.
create function public.consume_daily_quota(p_buckets text[], p_limits integer[])
returns boolean
language plpgsql
security invoker
set search_path = ''
as $$
declare
  today date := (now() at time zone 'Asia/Ho_Chi_Minh')::date;
begin
  if array_length(p_buckets, 1) is distinct from array_length(p_limits, 1) then
    raise exception 'p_buckets và p_limits phải cùng độ dài';
  end if;

  insert into public.api_quota_usage (bucket, usage_date)
  select b, today from unnest(p_buckets) as b
  on conflict (bucket, usage_date) do nothing;

  -- Khoá theo thứ tự bucket để 2 request đồng thời không deadlock
  perform 1 from public.api_quota_usage
  where usage_date = today and bucket = any (p_buckets)
  order by bucket
  for update;

  if exists (
    select 1
    from unnest(p_buckets, p_limits) as q (bucket, quota_limit)
    join public.api_quota_usage u on u.bucket = q.bucket and u.usage_date = today
    where u.used >= q.quota_limit
  ) then
    return false;
  end if;

  update public.api_quota_usage set used = used + 1
  where usage_date = today and bucket = any (p_buckets);
  return true;
end;
$$;
revoke execute on function public.consume_daily_quota(text[], integer[]) from public, anon, authenticated;
grant execute on function public.consume_daily_quota(text[], integer[]) to service_role;

-- 4. Đổi danh sách dị ứng của CHÍNH user đang gọi trong 1 giao dịch (xoá cũ + thêm mới). SECURITY INVOKER:
--    RLS owner-only của user_allergens vẫn áp dụng. Slug lạ bị bỏ qua (API đã validate slug trước).
create function public.set_my_allergens(p_slugs text[])
returns void
language sql
security invoker
set search_path = ''
as $$
  delete from public.user_allergens where user_id = (select auth.uid());
  insert into public.user_allergens (user_id, allergen_id)
  select (select auth.uid()), a.id from public.allergens a where a.slug = any (p_slugs);
$$;
revoke execute on function public.set_my_allergens(text[]) from public, anon;
grant execute on function public.set_my_allergens(text[]) to authenticated;
