// Kiểu công thức hiển thị (từ /recipes/suggest hoặc /saved). Bộ lọc chế độ ăn/dị ứng là ràng buộc cứng (loại hẳn), không phải gợi ý.
import type { SuggestedRecipeOut } from './suggest.ts';

// Khớp backend (services/diet_types.py) — gửi thẳng lên /profile, /recipes/suggest, không đổi mã ở giữa.
export type Diet = 'omnivore' | 'vegetarian' | 'vegan';
export type AllergenSlug =
  | 'shellfish' | 'molluscs' | 'fish' | 'egg' | 'dairy' | 'peanut' | 'tree_nuts' | 'soy' | 'wheat' | 'sesame';

export const DIETS: { id: Diet; label: string }[] = [
  { id: 'omnivore', label: 'Mặn' },
  { id: 'vegetarian', label: 'Chay' },
  { id: 'vegan', label: 'Thuần chay' },
];

export const ALLERGEN_LABELS: Record<AllergenSlug, string> = {
  shellfish: 'Tôm cua', molluscs: 'Mực, nghêu, sò', fish: 'Cá', egg: 'Trứng', dairy: 'Sữa bò',
  peanut: 'Đậu phộng', tree_nuts: 'Hạt điều, óc chó', soy: 'Đậu nành', wheat: 'Gluten', sesame: 'Mè',
};

// 4 chip như Confirm.dc.html; mỗi chip bật/tắt cả nhóm slug. Slug ngoài nhóm (vd egg đặt trong hồ sơ) vẫn giữ nguyên.
export type AllergenGroup = { id: string; label: string; slugs: AllergenSlug[] };
export const ALLERGENS: AllergenGroup[] = [
  { id: 'seafood', label: 'Hải sản', slugs: ['shellfish', 'molluscs', 'fish'] },
  { id: 'peanut', label: 'Đậu phộng', slugs: ['peanut'] },
  { id: 'dairy', label: 'Sữa bò', slugs: ['dairy'] },
  { id: 'wheat', label: 'Gluten', slugs: ['wheat'] },
];

export const isGroupAvoided = (avoid: AllergenSlug[], group: AllergenGroup) => group.slugs.every((slug) => avoid.includes(slug));

// Nhãn hiển thị: nhóm đủ slug → tên nhóm, slug lẻ → tên riêng (không bỏ sót slug nào).
export function avoidLabels(avoid: AllergenSlug[]): string[] {
  const groups = ALLERGENS.filter((g) => isGroupAvoided(avoid, g));
  const grouped = new Set(groups.flatMap((g) => g.slugs));
  return [...groups.map((g) => g.label), ...avoid.filter((slug) => !grouped.has(slug)).map((slug) => ALLERGEN_LABELS[slug])];
}

export const dietLabel = (diet: Diet) => DIETS.find((d) => d.id === diet)?.label ?? diet;

export type Step = {
  text: string;
  timerSec?: number;
  // Bước cần đủ thời gian để chín an toàn: không cho qua bước khi chưa chạy hết giờ.
  safetyMinSec?: number;
  uses?: string[];
};

export type Macros = { kcal: number; protein: number; carbs: number; fat: number };

// Công thức để hiển thị: từ /recipes/suggest (suggest.ts) hoặc /saved (saved.ts).
export type Recipe = {
  id: string;
  name: string;
  serves: number;
  minutes?: number; // thời gian chuẩn bị; không có → không hiện, không đoán
  nutrition: Macros | null; // null: công thức gốc không ghi gram → không tính được
  ingredients: { key: string; name: string; amount: string; have: boolean }[]; // have: có trong tủ (tính lúc tải công thức)
  steps: Step[];
  source: 'adapted' | 'original'; // AI đã chỉnh + qua validation / công thức gốc (fallback)
  warning?: string | null; // vd có nguyên liệu hệ thống chưa nhận diện đủ
  rawNote?: string | null; // bản gốc dùng nguyên liệu sống / chưa nấu chín (vd trứng ngâm mật ong)
  language?: 'vi' | 'en'; // en = bản gốc Food.com, không dịch
  restSec?: number; // nghỉ sau khi tắt bếp (food_safety), 0 = không cần
  // Nguyên văn /recipes/suggest trả (kể cả bản AI đã chỉnh) — gửi thẳng lên POST /saved.
  payload?: SuggestedRecipeOut;
};

export const formatNum = (n: number) => n.toLocaleString('vi-VN');

export function recipeToText(r: Recipe) {
  const meta = [
    r.minutes && `${r.minutes} phút`,
    `${r.serves} người`,
    r.nutrition && `${r.nutrition.kcal} kcal/phần`,
  ].filter(Boolean);
  return [
    r.name,
    meta.join(' · '),
    '',
    'Nguyên liệu:',
    ...r.ingredients.map((i) => (i.amount ? `- ${i.name}: ${i.amount}` : `- ${i.name}`)),
    '',
    'Cách nấu:',
    ...r.steps.map((s, i) => `${i + 1}. ${s.text}`),
  ].join('\n');
}
