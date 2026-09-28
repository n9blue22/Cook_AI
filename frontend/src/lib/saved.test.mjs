// Chạy: npm test. GET/DELETE /saved → danh sách màn Đã lưu, bộ lọc "Nhanh" / "Chay".
import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { ApiError } from './api.ts';
import { deleteSaved, listSaved, matchesFilter, saveRecipe } from './saved.ts';
import { toRecipe } from './suggest.ts';

const realFetch = globalThis.fetch;
afterEach(() => (globalThis.fetch = realFetch));

const savedOut = (id, diet_type, prep_minutes) => ({
  id,
  recipe_id: 100 + id,
  saved_at: '2026-09-28T03:00:00+00:00',
  diet_type,
  recipe: {
    recipe_id: 100 + id, source: 'original', title: `Món ${id}`, servings: 2,
    ingredients: [{ ingredient_id: 93, name: 'Ức gà', amount: 300, unit: 'g' }],
    steps: [{ step_no: 1, action: 'Xào', temperature_c: null, duration_sec: null }],
    rest_sec: 0, nutrition_per_serving: null, has_unmapped_ingredients: false, unmapped_ingredients_warning: null,
    language: 'vi', prep_minutes, raw_ingredient_note: null,
  },
});

function stubFetch(status, body) {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url, method: init.method });
    return new Response(status === 204 ? null : JSON.stringify(body), { status });
  };
  return calls;
}

test('listSaved gửi q đã mã hoá, map sang công thức hiển thị kèm "đang có" theo tủ', async () => {
  const calls = stubFetch(200, [savedOut(1, 'vegan', 15)]);
  const [item] = await listSaved('  gà & sả ', [93], 'tok');

  assert.match(calls[0].url, /\/saved\?q=g%C3%A0%20%26%20s%E1%BA%A3$/);
  assert.equal(item.savedId, 1);
  assert.equal(item.recipe.id, '101');
  assert.equal(item.recipe.ingredients[0].have, true);
  assert.equal(item.savedAt, Date.parse('2026-09-28T03:00:00+00:00'));
});

test('ô tìm rỗng → GET /saved không kèm q', async () => {
  const calls = stubFetch(200, []);
  await listSaved('   ', [], 'tok');
  assert.match(calls[0].url, /\/saved$/);
});

test('bộ lọc: Chay gồm chay + thuần chay, Nhanh cần có thời gian < 20′, không đoán khi thiếu dữ liệu', async () => {
  stubFetch(200, [savedOut(1, 'vegetarian', 30), savedOut(2, 'vegan', null), savedOut(3, 'omnivore', 10), savedOut(4, null, 19)]);
  const items = await listSaved('', [], 'tok');
  const ids = (filter) => items.filter((x) => matchesFilter(x, filter)).map((x) => x.savedId);

  assert.deepEqual(ids('all'), [1, 2, 3, 4]);
  assert.deepEqual(ids('veg'), [1, 2]);
  assert.deepEqual(ids('quick'), [3, 4]);
});

test('saveRecipe gửi NGUYÊN VĂN công thức suggest đã trả (kể cả bản AI chỉnh), trả dòng đã lưu', async () => {
  const suggested = { ...savedOut(0, null, 25).recipe, source: 'adapted', raw_ingredient_note: null };
  const recipe = toRecipe(suggested, []); // công thức đang hiển thị ở màn Recipe
  const sent = [];
  globalThis.fetch = async (url, init) => {
    sent.push({ url, method: init.method, body: JSON.parse(init.body) });
    return new Response(JSON.stringify(savedOut(9, 'omnivore', 25)), { status: 201 });
  };

  const saved = await saveRecipe(recipe.payload, [], 'tok');
  assert.equal(saved.savedId, 9);
  assert.equal(saved.recipe.id, '109');
  assert.equal(sent[0].method, 'POST');
  assert.match(sent[0].url, /\/saved$/);
  assert.deepEqual(sent[0].body, { recipe: suggested });
});

test('401 và lỗi xoá ném ApiError, không trả dữ liệu giả', async () => {
  stubFetch(401, { detail: 'Phiên đăng nhập không hợp lệ' });
  await assert.rejects(listSaved('', [], 'hết hạn'), (e) => e instanceof ApiError && e.status === 401);

  const calls = stubFetch(204);
  await deleteSaved(7, 'tok');
  assert.deepEqual(calls.map((c) => [c.method, c.url.replace(/^.*\/api\/v1/, '')]), [['DELETE', '/saved/7']]);
});
