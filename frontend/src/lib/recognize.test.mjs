// Chạy: npm test. Kết quả /recognize → dòng hiển thị ở Confirm.
import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { ApiError } from './api.ts';
import { recognizeImage, toScanResult } from './recognize.ts';

const realFetch = globalThis.fetch;
afterEach(() => (globalThis.fetch = realFetch));

// Dạng response thật (ảnh quả): "dưa lưới" chưa chắc, khớp gần đúng vào Dứa đã chắc chắn.
const OUT = {
  accepted_ids: [1, 2],
  uncertain: [
    { raw_name: 'dưa lưới', ingredient_id: 2 }, // trùng món chắc chắn, khác tên → đưa vào unlisted
    { raw_name: 'cà chua', ingredient_id: 1 }, // trùng món chắc chắn, cùng tên → bỏ
    { raw_name: 'gân bò', ingredient_id: 3 },
    { raw_name: 'hành', ingredient_id: 3 }, // trùng món chưa chắc → unlisted
  ],
  unmatched_names: ['lê'],
  names: { 1: 'Cà chua', 2: 'Dứa', 3: 'Bơ' },
};

test('toScanResult: mỗi nguyên liệu 1 dòng, không tên nào AI thấy bị ẩn', () => {
  assert.deepEqual(toScanResult(OUT), {
    items: [
      { ingredientId: 1, name: 'Cà chua', sure: true },
      { ingredientId: 2, name: 'Dứa', sure: true },
      { ingredientId: 3, name: 'Bơ', sure: false, seenAs: 'gân bò' },
    ],
    unlisted: ['dưa lưới', 'hành', 'lê'],
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
