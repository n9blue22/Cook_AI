// Dữ liệu mock — sẽ thay bằng API. Bộ lọc chế độ ăn/dị ứng là ràng buộc cứng (loại hẳn), không phải gợi ý.

export type Diet = 'man' | 'chay' | 'thuanchay';
export type Allergen = 'haisan' | 'dauphong' | 'suabo' | 'gluten';

export const DIETS: { id: Diet; label: string }[] = [
  { id: 'man', label: 'Mặn' },
  { id: 'chay', label: 'Chay' },
  { id: 'thuanchay', label: 'Thuần chay' },
];

export const ALLERGENS: { id: Allergen; label: string }[] = [
  { id: 'haisan', label: 'Hải sản' },
  { id: 'dauphong', label: 'Đậu phộng' },
  { id: 'suabo', label: 'Sữa bò' },
  { id: 'gluten', label: 'Gluten' },
];

export type Step = {
  text: string;
  timerSec?: number;
  // Bước cần đủ thời gian để chín an toàn: không cho qua bước khi chưa chạy hết giờ.
  safetyMinSec?: number;
  uses?: string[];
};

export type Recipe = {
  id: string;
  name: string;
  minutes: number;
  serves: number;
  level: string;
  price: number;
  diet: Diet; // mức chặt nhất món đáp ứng: thuần chay ⊂ chay ⊂ mặn
  allergens: Allergen[];
  kcal: number;
  protein: number;
  carbs: number;
  fat: number;
  ingredients: { key: string; name: string; amount: string }[];
  steps: Step[];
};

export const RECIPES: Recipe[] = [
  {
    id: 'trung-chien-ca-chua',
    name: 'Trứng chiên cà chua',
    minutes: 15, serves: 2, level: 'Dễ nấu', price: 32000,
    diet: 'man', allergens: [],
    kcal: 320, protein: 18, carbs: 9, fat: 23,
    ingredients: [
      { key: 'cà chua', name: 'Cà chua chín', amount: '3 quả' },
      { key: 'trứng gà', name: 'Trứng gà', amount: '4 quả' },
      { key: 'hành lá', name: 'Hành lá', amount: '2 nhánh' },
      { key: 'nước mắm', name: 'Nước mắm', amount: '1 thìa' },
    ],
    steps: [
      { text: 'Rửa cà chua, thái múi cau. Đập trứng, đánh tan với chút muối.', uses: ['Cà chua · 3 quả', 'Trứng gà · 4 quả'] },
      { text: 'Phi thơm hành, cho cà chua vào xào mềm khoảng 3 phút.', timerSec: 180, uses: ['Cà chua · 3 quả', 'Hành lá · 2 nhánh'] },
      { text: 'Đổ trứng vào, đảo đều đến khi trứng chín hẳn, không còn phần lỏng.', timerSec: 120, safetyMinSec: 120, uses: ['Trứng gà · 4 quả'] },
      { text: 'Nêm nước mắm, rắc hành lá, tắt bếp và dọn ra đĩa.', uses: ['Nước mắm · 1 thìa', 'Hành lá · 2 nhánh'] },
    ],
  },
  {
    id: 'canh-chua-ca-loc',
    name: 'Canh chua cá lóc',
    minutes: 35, serves: 3, level: 'Vừa', price: 85000,
    diet: 'man', allergens: ['haisan'],
    kcal: 280, protein: 26, carbs: 14, fat: 12,
    ingredients: [
      { key: 'cá lóc', name: 'Cá lóc', amount: '500 g' },
      { key: 'cà chua', name: 'Cà chua', amount: '2 quả' },
      { key: 'dứa', name: 'Dứa', amount: '1/4 quả' },
      { key: 'giá đỗ', name: 'Giá đỗ', amount: '100 g' },
      { key: 'me', name: 'Me chua', amount: '30 g' },
    ],
    steps: [
      { text: 'Làm sạch cá, cắt khúc, ướp chút muối và tiêu 10 phút.', timerSec: 600 },
      { text: 'Đun sôi nước với me, lọc lấy nước chua.', timerSec: 300 },
      { text: 'Thả cá vào nồi, nấu đến khi thịt cá chín trắng đều.', timerSec: 480, safetyMinSec: 480 },
      { text: 'Cho cà chua, dứa, giá; nêm nếm vừa ăn rồi tắt bếp.' },
    ],
  },
  {
    id: 'dau-hu-sot-ca',
    name: 'Đậu hũ sốt cà',
    minutes: 20, serves: 2, level: 'Dễ nấu', price: 25000,
    diet: 'thuanchay', allergens: [],
    kcal: 210, protein: 14, carbs: 12, fat: 11,
    ingredients: [
      { key: 'đậu hũ', name: 'Đậu hũ', amount: '3 bìa' },
      { key: 'cà chua', name: 'Cà chua', amount: '3 quả' },
      { key: 'hành lá', name: 'Hành lá', amount: '2 nhánh' },
      { key: 'nước tương', name: 'Nước tương', amount: '2 thìa' },
    ],
    steps: [
      { text: 'Cắt đậu hũ miếng vừa ăn, chiên vàng các mặt.', timerSec: 360 },
      { text: 'Xào cà chua đến khi nhuyễn thành sốt.', timerSec: 240 },
      { text: 'Cho đậu vào sốt, nêm nước tương, rim nhỏ lửa 3 phút.', timerSec: 180 },
      { text: 'Rắc hành lá và tắt bếp.' },
    ],
  },
  {
    id: 'thit-kho-trung',
    name: 'Thịt ba chỉ kho trứng',
    minutes: 60, serves: 4, level: 'Vừa', price: 120000,
    diet: 'man', allergens: [],
    kcal: 540, protein: 32, carbs: 8, fat: 42,
    ingredients: [
      { key: 'thịt ba chỉ', name: 'Thịt ba chỉ', amount: '500 g' },
      { key: 'trứng gà', name: 'Trứng gà', amount: '4 quả' },
      { key: 'nước dừa', name: 'Nước dừa', amount: '500 ml' },
      { key: 'nước mắm', name: 'Nước mắm', amount: '3 thìa' },
    ],
    steps: [
      { text: 'Luộc trứng 10 phút, bóc vỏ.', timerSec: 600 },
      { text: 'Thái thịt miếng vuông, ướp nước mắm và đường 15 phút.', timerSec: 900 },
      { text: 'Xào săn thịt, đổ nước dừa, kho lửa nhỏ đến khi thịt chín mềm.', timerSec: 1800, safetyMinSec: 1800 },
      { text: 'Cho trứng vào kho thêm 10 phút cho thấm.', timerSec: 600 },
    ],
  },
  {
    id: 'rau-muong-xao-toi',
    name: 'Rau muống xào tỏi',
    minutes: 10, serves: 2, level: 'Dễ nấu', price: 15000,
    diet: 'thuanchay', allergens: [],
    kcal: 120, protein: 4, carbs: 10, fat: 7,
    ingredients: [
      { key: 'rau muống', name: 'Rau muống', amount: '1 bó' },
      { key: 'tỏi', name: 'Tỏi', amount: '5 tép' },
      { key: 'nước tương', name: 'Nước tương', amount: '1 thìa' },
    ],
    steps: [
      { text: 'Nhặt rau muống, rửa sạch, để ráo.' },
      { text: 'Phi thơm tỏi, cho rau vào xào lửa lớn 2 phút.', timerSec: 120 },
      { text: 'Nêm nước tương, đảo đều và tắt bếp.' },
    ],
  },
  {
    id: 'mi-xao-bo',
    name: 'Mì xào bò',
    minutes: 25, serves: 2, level: 'Vừa', price: 70000,
    diet: 'man', allergens: ['gluten'],
    kcal: 610, protein: 34, carbs: 68, fat: 20,
    ingredients: [
      { key: 'mì', name: 'Mì trứng', amount: '2 vắt' },
      { key: 'thịt bò', name: 'Thịt bò', amount: '200 g' },
      { key: 'cải ngọt', name: 'Cải ngọt', amount: '1 bó' },
      { key: 'tỏi', name: 'Tỏi', amount: '3 tép' },
    ],
    steps: [
      { text: 'Trụng mì qua nước sôi, để ráo.', timerSec: 120 },
      { text: 'Xào bò lửa lớn đến khi chín tới.', timerSec: 150, safetyMinSec: 150 },
      { text: 'Cho cải và mì vào, đảo đều, nêm nếm.', timerSec: 180 },
    ],
  },
  {
    id: 'sua-chua-chuoi',
    name: 'Sữa chua chuối yến mạch',
    minutes: 5, serves: 1, level: 'Dễ nấu', price: 20000,
    diet: 'chay', allergens: ['suabo', 'gluten'],
    kcal: 260, protein: 9, carbs: 42, fat: 6,
    ingredients: [
      { key: 'sữa chua', name: 'Sữa chua', amount: '1 hũ' },
      { key: 'chuối', name: 'Chuối', amount: '1 quả' },
      { key: 'yến mạch', name: 'Yến mạch', amount: '30 g' },
    ],
    steps: [
      { text: 'Thái chuối lát mỏng.' },
      { text: 'Cho sữa chua ra bát, xếp chuối và rắc yến mạch lên trên.' },
    ],
  },
  {
    id: 'goi-cuon-chay',
    name: 'Gỏi cuốn chay sốt đậu phộng',
    minutes: 30, serves: 3, level: 'Vừa', price: 45000,
    diet: 'thuanchay', allergens: ['dauphong'],
    kcal: 300, protein: 11, carbs: 44, fat: 9,
    ingredients: [
      { key: 'bánh tráng', name: 'Bánh tráng', amount: '10 lá' },
      { key: 'đậu hũ', name: 'Đậu hũ', amount: '2 bìa' },
      { key: 'rau sống', name: 'Rau sống', amount: '1 rổ' },
      { key: 'đậu phộng', name: 'Đậu phộng', amount: '50 g' },
    ],
    steps: [
      { text: 'Chiên đậu hũ, cắt thanh dài.', timerSec: 360 },
      { text: 'Làm ướt bánh tráng, cuốn rau và đậu hũ.' },
      { text: 'Giã đậu phộng, pha với nước tương làm sốt chấm.' },
    ],
  },
];

const DIET_RANK: Record<Diet, number> = { man: 0, chay: 1, thuanchay: 2 };

const norm = (s: string) => s.trim().toLowerCase();

export function haveIngredient(pantry: string[], key: string) {
  const k = norm(key);
  return pantry.some((p) => norm(p).includes(k) || k.includes(norm(p)));
}

// Loại cứng theo chế độ ăn + dị ứng, rồi xếp theo số nguyên liệu đang có.
export function findRecipes(pantry: string[], diet: Diet, avoid: Allergen[]) {
  return RECIPES.filter(
    (r) => DIET_RANK[r.diet] >= DIET_RANK[diet] && !r.allergens.some((a) => avoid.includes(a)),
  )
    .map((r) => ({ r, have: r.ingredients.filter((i) => haveIngredient(pantry, i.key)).length }))
    .sort((a, b) => b.have - a.have || a.r.minutes - b.r.minutes)
    .map((x) => x.r);
}

export const getRecipe = (id: string) => RECIPES.find((r) => r.id === id);

export const formatPrice = (n: number) => `≈ ${n.toLocaleString('vi-VN')}đ`;
export const formatNum = (n: number) => n.toLocaleString('vi-VN');

export function recipeToText(r: Recipe) {
  return [
    r.name,
    `${r.minutes} phút · ${r.serves} người · ${r.kcal} kcal/phần`,
    '',
    'Nguyên liệu:',
    ...r.ingredients.map((i) => `- ${i.name}: ${i.amount}`),
    '',
    'Cách nấu:',
    ...r.steps.map((s, i) => `${i + 1}. ${s.text}`),
  ].join('\n');
}
