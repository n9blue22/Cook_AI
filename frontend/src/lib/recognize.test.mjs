// Chạy: npm test. Kết quả /recognize → dòng hiển thị ở Confirm.
import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { ApiError } from './api.ts';
import { recognizeImage, toScanResult } from './recognize.ts';

const realFetch = globalThis.fetch;
afterEach(() => (globalThis.fetch = realFetch));

const OUT = {
  accepted_ids: [1, 2],
  uncertain: [
    { raw_name: 'cà chua bi', ingredient_id: 1 }, // trùng món đã chắc chắn → bỏ
    { raw_name: 'gân bò', ingredient_id: 3 },
    { raw_name: 'hành', ingredient_id: 3 }, // trùng món chưa chắc → bỏ
  ],
  unmatched_names: ['sô cô la'],
  names: { 1: 'Cà chua', 2: 'Trứng gà', 3: 'Bơ' },
};

test('toScanResult: chắc chắn trước, chưa chắc sau, gộp trùng theo ingredient_id', () => {
  assert.deepEqual(toScanResult(OUT), {
    items: [
      { ingredientId: 1, name: 'Cà chua', sure: true },
      { ingredientId: 2, name: 'Trứng gà', sure: true },
      { ingredientId: 3, name: 'Bơ', sure: false, seenAs: 'gân bò' },
    ],
    unmatched: ['sô cô la'],
  });
});

test('recognizeImage: gửi multipart kèm token; lỗi server giữ nguyên câu của backend', async () => {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    if (String(url).startsWith('data:')) return realFetch(url);
    calls.push(init);
    return new Response(JSON.stringify({ detail: 'Không nhận diện được ảnh, thử lại' }), { status: 503 });
  };
  await assert.rejects(recognizeImage('data:image/jpeg;base64,AAAA', 'tok'), (e) => e instanceof ApiError && e.status === 503 && e.message === 'Không nhận diện được ảnh, thử lại');
  assert.ok(calls[0].body instanceof FormData && calls[0].body.get('image') instanceof Blob);
  assert.equal(calls[0].headers.Authorization, 'Bearer tok');
  assert.equal(calls[0].headers['Content-Type'], undefined);
});
