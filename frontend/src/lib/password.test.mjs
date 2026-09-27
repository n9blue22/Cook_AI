// Chạy: npm test (node --test, Node ≥ 22.18 tự bỏ kiểu TypeScript). Cùng bộ ca với backend tests/test_security.py.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { isStrongPassword, isValidEmail, passwordRules } from './password.ts';

test('mật khẩu đủ mạnh qua hết luật', () => {
  assert.equal(isStrongPassword('Dung-mat-khau-1!'), true);
});

test('báo đúng từng luật còn thiếu', () => {
  const missing = passwordRules('abcdefgh').filter((rule) => !rule.ok).map((rule) => rule.label);
  assert.deepEqual(missing, ['Ít nhất 1 chữ hoa', 'Ít nhất 1 chữ số', 'Ít nhất 1 ký tự đặc biệt']);
  assert.equal(passwordRules('Ab1!')[0].ok, false); // dưới 8 ký tự
});

test('giới hạn 72 byte tính theo byte, không theo ký tự (tiếng Việt có dấu tốn 2-3 byte)', () => {
  assert.equal(isStrongPassword('Ặ1!a'.repeat(10)), false); // 40 ký tự nhưng > 72 byte
});

test('kiểm tra email cơ bản', () => {
  assert.equal(isValidEmail(' ban@example.com '), true);
  assert.equal(isValidEmail('khong-phai-email'), false);
});
