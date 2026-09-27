-- Ghi rõ quyền DELETE của service_role trên api_quota_usage. Supabase đã ngầm cấp (default privileges của schema
-- public cho service_role) — đã dùng thật để xoá dòng quota của tài khoản test 2026-09-28 — nhưng migration
-- auth_profiles_quota_lockdown chỉ ghi select/insert/update, đọc lại dễ hiểu nhầm là service_role không xoá được.
-- Không đổi quyền thật; anon/authenticated vẫn không có quyền nào.
grant delete on public.api_quota_usage to service_role;
