// Chạy: npm test. Trên máy chỉ còn dữ liệu của user đang đăng nhập; bản cũ khoá chung bị xoá, không gán cho ai.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { loadUserData, purgeUserData, userDataKey } from './localUserData.ts';

// Giả AsyncStorage (web: localStorage chung với khoá phiên 'bepai.*' và khoá của thư viện khác).
function fakeStorage(entries) {
  const map = new Map(Object.entries(entries));
  return {
    map,
    getItem: async (key) => map.get(key) ?? null,
    getAllKeys: async () => [...map.keys()],
    multiRemove: async (keys) => keys.forEach((key) => map.delete(key)),
  };
}

const SESSION_KEYS = { 'bepai.email': 'b@x.com', 'bepai.user_id': 'B', 'expo-other': '1' };

test('đọc dữ liệu user B: xoá của A và bản cũ khoá chung, không đụng khoá phiên / khoá lạ', async () => {
  const storage = fakeStorage({
    ...SESSION_KEYS,
    'bepai:v1': '{"pantry":[]}',
    'bepai:v2': '{"results":["của A"]}',
    [userDataKey('A')]: '{"results":["của A"]}',
    [userDataKey('B')]: '{"results":["của B"]}',
  });
  assert.equal(await loadUserData(storage, 'B'), '{"results":["của B"]}');
  assert.deepEqual([...storage.map.keys()].sort(), [...Object.keys(SESSION_KEYS), userDataKey('B')].sort());
});

test('user mới trên máy có bản cũ khoá chung → không nhận được gì (không gán cho ai)', async () => {
  const storage = fakeStorage({ 'bepai:v2': '{"results":["của A"]}' });
  assert.equal(await loadUserData(storage, 'B'), null);
  assert.equal(storage.map.size, 0);
});

test('đăng xuất → xoá hết dữ liệu người dùng', async () => {
  const storage = fakeStorage({ ...SESSION_KEYS, [userDataKey('A')]: '{}' });
  await purgeUserData(storage);
  assert.deepEqual([...storage.map.keys()].sort(), Object.keys(SESSION_KEYS).sort());
});
