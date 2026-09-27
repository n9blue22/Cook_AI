// Chạy: npm test. Kết quả /recipes/suggest → công thức hiển thị ở màn Recipe / Cook.
import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { ApiError } from './api.ts';
import { suggestRecipes, toRecipe } from './suggest.ts';

const realFetch = globalThis.fetch;
afterEach(() => (globalThis.fetch = realFetch));

const ORIGINAL = {
  recipe_id: 12,
  source: 'original',
  title: 'Gà xào sả ớt',
  servings: 2,
  ingredients: [
    { ingredient_id: 93, name: 'Ức gà', amount: 300, unit: 'g' },
    { ingredient_id: 5, name: 'Sả', amount: 0.5, unit: 'bó' },
    { ingredient_id: 7, name: 'Muối', amount: null, unit: null },
  ],
  steps: [
    { step_no: 2, action: 'Xào gà đến khi chín hẳn', temperature_c: 75, duration_sec: 420 },
    { step_no: 1, action: 'Thái gà miếng vừa ăn', temperature_c: null, duration_sec: null },
    { step_no: 3, action: 'Ngâm sả', temperature_c: null, duration_sec: 60 },
  ],
  rest_sec: 180,
  nutrition_per_serving: null,
  has_unmapped_ingredients: true,
  unmapped_ingredients_warning: 'Một số nguyên liệu ... kiểm tra chín kỹ trước khi ăn',
  language: 'vi',
  score: 0.8,
};

test('toRecipe: giữ nguyên số liệu thật, không bịa phần API không có', () => {
  const r = toRecipe(ORIGINAL, [93]);
  assert.equal(r.id, '12');
  assert.equal(r.source, 'original');
  assert.equal(r.nutrition, null); // gốc không ghi gram → không tự tính
  assert.equal(r.minutes, undefined);
  assert.equal(r.warning, ORIGINAL.unmapped_ingredients_warning);
  assert.equal(r.restSec, 180);
  assert.deepEqual(r.ingredients.map((i) => [i.amount, i.have]), [['300 g', true], ['0,5 bó', false], ['', false]]);
  assert.deepEqual(r.steps, [
    { text: 'Thái gà miếng vừa ăn', timerSec: undefined, safetyMinSec: undefined },
    { text: 'Xào gà đến khi chín hẳn', timerSec: 420, safetyMinSec: 420 }, // bước nấu chín → bắt chạy đủ giờ
    { text: 'Ngâm sả', timerSec: 60, safetyMinSec: undefined }, // có giờ nhưng không có nhiệt → chỉ hẹn giờ
  ]);
});

test('toRecipe: dinh dưỡng làm tròn, bản adapted', () => {
  const r = toRecipe({ ...ORIGINAL, source: 'adapted', nutrition_per_serving: { kcal: 412.6, protein_g: 35.4, carb_g: 8.5, fat_g: 20.2 } }, []);
  assert.equal(r.source, 'adapted');
  assert.deepEqual(r.nutrition, { kcal: 413, protein: 35, carbs: 9, fat: 20 });
});

test('suggestRecipes: gửi đúng body + token; 429 hết lượt giữ nguyên câu backend', async () => {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url: String(url), init });
    return new Response(JSON.stringify({ detail: 'Đã dùng hết lượt hôm nay, quay lại vào ngày mai' }), { status: 429 });
  };
  const query = { ingredientIds: [93, 5], diet: 'vegetarian', avoid: ['peanut'] };
  await assert.rejects(suggestRecipes(query, 'tok'), (e) => e instanceof ApiError && e.status === 429 && e.message === 'Đã dùng hết lượt hôm nay, quay lại vào ngày mai');
  assert.ok(calls[0].url.endsWith('/recipes/suggest'));
  assert.deepEqual(JSON.parse(calls[0].init.body), { ingredient_ids: [93, 5], diet_type: 'vegetarian', allergens: ['peanut'] });
  assert.equal(calls[0].init.headers.Authorization, 'Bearer tok');
});
