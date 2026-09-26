-- search_recipes chạy với quyền owner (bỏ qua RLS is_verified của người gọi): gọi bằng publishable key
-- vẫn tìm trên toàn bộ recipes; lọc diet/dị ứng vẫn nằm trong function.
-- An toàn vì search_path = '' đã cố định và function chỉ đọc, chỉ trả id/title/điểm số.
alter function public.search_recipes(extensions.vector, text, text[], int[]) security definer;
