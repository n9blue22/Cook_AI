// Chạy: npm test (node --test, Node ≥ 22.18 tự bỏ kiểu TypeScript). Cùng bộ ca với backend tests/test_security.py.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { isPasswordTooLong, isStrongPassword, isValidEmail, PASSWORD_TOO_LONG_MESSAGE, passwordRules } from './password.ts';

const byteLength = (text) => new TextEncoder().encode(text).length;

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

test('mật khẩu 20 ký tự ASCII hợp lệ thì qua', () => {
  const password = 'Abcdefgh1!Abcdefgh1!';
  assert.equal(password.length, 20);
  assert.equal(isPasswordTooLong(password), false);
  assert.equal(isStrongPassword(password), true);
});

test('30 ký tự toàn chữ có dấu (vượt 72 byte) bị từ chối, có thông báo', () => {
  const password = 'ẶẤỀ'.repeat(10);
  assert.equal(password.length, 30);
  assert.ok(byteLength(password) > 72);
  assert.equal(isPasswordTooLong(password), true);
  assert.equal(isStrongPassword(password), false);
  assert.equal(PASSWORD_TOO_LONG_MESSAGE, 'Mật khẩu quá dài, hãy rút ngắn lại.');
});

test('đúng 72 byte thì qua, 73 byte thì bị từ chối', () => {
  const at72 = 'Ab1!' + 'x'.repeat(68);
  const at73 = at72 + 'x';
  assert.equal(byteLength(at72), 72);
  assert.equal(isStrongPassword(at72), true);
  assert.equal(byteLength(at73), 73);
  assert.equal(isPasswordTooLong(at73), true);
  assert.equal(isStrongPassword(at73), false);
});

test('danh sách luật hiển thị không còn dòng 72 byte', () => {
  const labels = passwordRules('Ab1!').map((rule) => rule.label);
  assert.equal(labels.some((label) => label.includes('72')), false);
  assert.equal(labels.length, 5);
});

test('kiểm tra email cơ bản', () => {
  assert.equal(isValidEmail(' ban@example.com '), true);
  assert.equal(isValidEmail('khong-phai-email'), false);
});
