-- Xoá user thì dọn luôn quota theo user (bucket 'user:<uuid>:<policy>', rate_limit.py). Giữ nguyên 'global:*':
-- trần tổng phản ánh chi phí AI đã tiêu thật, xoá user không trả lại lượt dùng chung.
-- Không kèm câu dọn một lần: lúc viết không còn dòng nào của user đã xoá.
create function public.delete_quota_usage_of_deleted_user()
returns trigger
language plpgsql
security definer          -- lệnh xoá auth.users chạy bằng supabase_auth_admin, role này không có quyền trên api_quota_usage
set search_path = ''
as $$
begin
  -- starts_with thay LIKE: khớp tiền tố chính xác, không lo ký tự đại diện _ %. Giữ hàm đơn giản vì trigger lỗi
  -- thì rollback cả lệnh xoá user.
  delete from public.api_quota_usage
  where starts_with(bucket, 'user:' || old.id::text || ':');
  return null;            -- AFTER trigger, giá trị trả về bị bỏ qua
end;
$$;
revoke execute on function public.delete_quota_usage_of_deleted_user() from public, anon, authenticated;

create trigger on_auth_user_deleted_cleanup_quota
  after delete on auth.users
  for each row execute function public.delete_quota_usage_of_deleted_user();
