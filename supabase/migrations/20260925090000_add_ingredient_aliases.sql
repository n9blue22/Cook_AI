-- Tên gọi khác của nguyên liệu (vd "Xì dầu" cho "Nước tương") — dùng khi map tên nhận diện/nhập tay về 1 dòng chuẩn.
alter table public.ingredients
  add column if not exists aliases text[] not null default '{}';
