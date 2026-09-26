-- Bucket cache ảnh AI minh hoạ món (POST /api/v1/recipes/{id}/image): 1 file / recipe, tên {recipe_id}.jpg.
-- Đọc public (client hiển thị qua public URL). KHÔNG có policy ghi: chỉ backend ghi bằng secret key (bỏ qua RLS),
-- nên publishable key trong app client không upload được gì vào đây.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('ai-dish-images', 'ai-dish-images', true, 5242880, array['image/jpeg']);
