// Chạy: npm test. Phiên chỉ bị huỷ khi server trả 401/403 — mất mạng / timeout / lỗi server phải giữ phiên.
import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { ApiError, apiRequest, isAuthRejection, NO_RESPONSE } from './api.ts';
import { retryDelayMs, SessionManager } from './session.ts';

const EMAIL = 'a@example.com';
const USER = { userId: 'u-1', email: EMAIL };
const SESSION_OUT = { access_token: 'at-2', expires_in: 3600, user_id: 'u-1', email: EMAIL, refresh_token: 'rt-2' };
const managers = [];
const realFetch = globalThis.fetch;

afterEach(() => {
  managers.forEach((m) => m.dispose()); // huỷ hẹn giờ làm mới để node thoát được
  globalThis.fetch = realFetch;
});

// refreshResults: kết quả lần lượt của từng lần gọi /auth/refresh (Error → ném, object → trả về).
function setup(...refreshResults) {
  const saved = { refreshToken: 'rt-1', signedInAt: Date.now(), ...USER };
  const state = { stored: saved, changes: [], refreshCalls: 0, cleared: false };
  const request = async (path) => {
    assert.equal(path, '/auth/refresh');
    state.refreshCalls += 1;
    const next = refreshResults.shift();
    if (next instanceof Error) throw next;
    return next;
  };
  const storage = {
    load: async () => state.stored,
    save: async (s) => (state.stored = s),
    saveRefreshToken: async () => {},
    clear: async () => {
      state.stored = null;
      state.cleared = true; // auth.tsx: clear() xoá phiên + dữ liệu người dùng trong localStorage
    },
  };
  const manager = new SessionManager({ request, storage, clientKind: 'native' }, (user) => state.changes.push(user));
  managers.push(manager);
  return { manager, state };
}

const offline = () => new ApiError(NO_RESPONSE, 'Không kết nối được máy chủ');

test('mất mạng lúc mở app → vẫn đăng nhập, không xoá phiên đã lưu', async () => {
  const { manager, state } = setup(offline());
  await manager.restore();
  assert.deepEqual(state.changes, [USER]);
  assert.notEqual(state.stored, null);
});

test('mở app lúc mất mạng, có mạng lại → lấy được token, không phải đăng nhập lại', async () => {
  const { manager, state } = setup(offline(), offline(), SESSION_OUT);
  await manager.restore();
  await assert.rejects(manager.getAccessToken(), (e) => e instanceof ApiError && e.status === NO_RESPONSE);
  assert.equal(await manager.getAccessToken(), 'at-2');
  assert.deepEqual(state.changes, [USER]); // chưa lần nào bị đá ra
});

test('lỗi phía server (502, 429) không phải lỗi xác thực → giữ phiên', async () => {
  for (const status of [502, 429]) {
    const { manager, state } = setup(new ApiError(status, 'lỗi'));
    await manager.restore();
    assert.deepEqual(state.changes, [USER], `status ${status}`);
  }
});

test('refresh trả 429 → không đăng xuất, không xoá dữ liệu máy, thử lại đúng sau Retry-After', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const { manager, state } = setup(new ApiError(429, 'Bạn thao tác quá nhanh', 12), SESSION_OUT);
  await manager.restore();
  assert.deepEqual(state.changes, [USER]);
  assert.equal(state.cleared, false);
  assert.notEqual(state.stored, null);

  t.mock.timers.tick(11_999);
  assert.equal(state.refreshCalls, 1); // chưa tới giờ server cho phép
  t.mock.timers.tick(1);
  await new Promise(setImmediate); // lượt làm mới đã hẹn chạy xong
  assert.equal(state.refreshCalls, 2);
  assert.equal(state.cleared, false);
  assert.deepEqual(state.changes, [USER]);
});

test('429 không có Retry-After / mất mạng → thử lại sau 30s', () => {
  assert.equal(retryDelayMs(new ApiError(429, 'x', 7)), 7000);
  assert.equal(retryDelayMs(new ApiError(429, 'x')), 30_000);
  assert.equal(retryDelayMs(offline()), 30_000);
});

test('server trả 401 / 403 → đăng xuất và xoá phiên đã lưu', async () => {
  for (const status of [401, 403]) {
    const { manager, state } = setup(new ApiError(status, 'Phiên đăng nhập đã hết hạn'));
    await manager.restore();
    assert.deepEqual(state.changes, [null], `status ${status}`);
    assert.equal(state.stored, null);
  }
});

test('đang dùng app, làm mới bị server từ chối → đăng xuất', async () => {
  const { manager, state } = setup(offline(), new ApiError(401, 'hết hạn'));
  await manager.restore();
  await assert.rejects(manager.getAccessToken());
  assert.deepEqual(state.changes, [USER, null]);
});

test('làm mới trả user khác (tab khác đã đổi tài khoản) → chuyển sang user mới, lưu lại phiên của user mới', async () => {
  const other = { ...SESSION_OUT, user_id: 'u-2', email: 'b@example.com' };
  const { manager, state } = setup(offline(), other);
  await manager.restore();
  assert.equal(await manager.getAccessToken(), 'at-2');
  assert.deepEqual(state.changes, [USER, { userId: 'u-2', email: 'b@example.com' }]);
  assert.equal(state.stored.userId, 'u-2');
});

// apiRequest thật với fetch giả: phân loại đúng từ nguồn lỗi.
test('apiRequest: fetch lỗi mạng / timeout → status 0; 401 trong response → lỗi xác thực', async () => {
  globalThis.fetch = async () => {
    throw new TypeError('Failed to fetch');
  };
  const network = await apiRequest('/x').catch((e) => e);
  assert.equal(network.status, NO_RESPONSE);
  assert.equal(isAuthRejection(network), false);

  globalThis.fetch = (_url, { signal }) =>
    new Promise((_resolve, reject) => signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError'))));
  const timeout = await apiRequest('/x', { timeoutMs: 20 }).catch((e) => e);
  assert.equal(timeout.status, NO_RESPONSE);
  assert.match(timeout.message, /quá lâu/);
  assert.equal(isAuthRejection(timeout), false);

  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Phiên đăng nhập đã hết hạn' }), { status: 401 });
  const rejected = await apiRequest('/x').catch((e) => e);
  assert.equal(isAuthRejection(rejected), true);
});

test('apiRequest: 429 đọc header Retry-After (số giây); không có hoặc sai dạng → null', async () => {
  const limited = (headers) => async () => new Response(JSON.stringify({ detail: 'quá nhanh' }), { status: 429, headers });
  globalThis.fetch = limited({ 'Retry-After': '42' });
  const withHeader = await apiRequest('/x').catch((e) => e);
  assert.equal(withHeader.retryAfterSec, 42);
  assert.equal(isAuthRejection(withHeader), false);
  globalThis.fetch = limited({});
  assert.equal((await apiRequest('/x').catch((e) => e)).retryAfterSec, null);
  globalThis.fetch = limited({ 'Retry-After': 'Wed, 21 Oct 2026 07:28:00 GMT' });
  assert.equal((await apiRequest('/x').catch((e) => e)).retryAfterSec, null);
});
