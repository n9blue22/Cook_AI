-- Tách thời gian nghỉ sau khi tắt bếp (rest) khỏi thời gian nấu tối thiểu.
-- rest_sec là hướng dẫn hiển thị cho user, KHÔNG phải điều kiện validate bước nấu.
alter table public.food_safety
  add column rest_sec integer not null default 0 check (rest_sec >= 0);

comment on column public.food_safety.min_duration_sec is 'Thời gian tối thiểu của bước nấu ở nhiệt độ ≥ min_temp_c';
comment on column public.food_safety.rest_sec is 'Thời gian để nghỉ sau khi tắt bếp (USDA FSIS), chỉ để hiển thị';

-- Nguyên miếng / giăm bông sống: 3 phút là thời gian nghỉ, không phải thời gian nấu.
update public.food_safety
set min_duration_sec = 0, rest_sec = 180
where category in ('whole_cut', 'ham_raw');
