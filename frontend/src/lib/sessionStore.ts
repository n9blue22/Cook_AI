// Lưu session lâu dài. Access token KHÔNG lưu xuống máy (chỉ giữ trong bộ nhớ, sống ~1 giờ).
// - Điện thoại: refresh token trong expo-secure-store (Keychain / Keystore) — KHÔNG dùng AsyncStorage.
// - Web: SecureStore không chạy trên web → refresh token nằm trong cookie httpOnly do backend đặt (JS không đọc được).
//   Ở đây chỉ lưu thời điểm đăng nhập + email + user_id (không bí mật) vào localStorage để ép đăng nhập lại sau 30 ngày.
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

export const IS_WEB = Platform.OS === 'web';
export const CLIENT_KIND: 'web' | 'native' = IS_WEB ? 'web' : 'native';

const KEY_REFRESH = 'bepai.refresh_token';
const KEY_SIGNED_IN_AT = 'bepai.signed_in_at';
const KEY_EMAIL = 'bepai.email';
const KEY_USER_ID = 'bepai.user_id'; // khoá dữ liệu người dùng trên máy (localUserData.ts), kể cả khi mở app lúc mất mạng

export type PersistedSession = {
  refreshToken: string | null; // null trên web (nằm trong cookie)
  signedInAt: number;
  email: string;
  userId: string;
};

export async function loadSession(): Promise<PersistedSession | null> {
  const [refreshToken, signedInAt, email, userId] = await Promise.all([
    IS_WEB ? null : SecureStore.getItemAsync(KEY_REFRESH),
    readPlain(KEY_SIGNED_IN_AT),
    readPlain(KEY_EMAIL),
    readPlain(KEY_USER_ID),
  ]);
  // Phiên lưu từ bản cũ chưa có user_id → coi như chưa đăng nhập (đăng nhập lại 1 lần).
  if (!signedInAt || !email || !userId || (!IS_WEB && !refreshToken)) return null;
  return { refreshToken, signedInAt: Number(signedInAt), email, userId };
}

export async function saveSession(session: PersistedSession): Promise<void> {
  if (!IS_WEB && session.refreshToken) await SecureStore.setItemAsync(KEY_REFRESH, session.refreshToken);
  await writePlain(KEY_SIGNED_IN_AT, String(session.signedInAt));
  await writePlain(KEY_EMAIL, session.email);
  await writePlain(KEY_USER_ID, session.userId);
}

// Chỉ đổi refresh token mới (mỗi lần làm mới Supabase cấp token mới, token cũ hết hiệu lực).
export async function saveRefreshToken(refreshToken: string | null): Promise<void> {
  if (!IS_WEB && refreshToken) await SecureStore.setItemAsync(KEY_REFRESH, refreshToken);
}

export async function clearSession(): Promise<void> {
  if (!IS_WEB) await SecureStore.deleteItemAsync(KEY_REFRESH);
  await removePlain(KEY_SIGNED_IN_AT);
  await removePlain(KEY_EMAIL);
  await removePlain(KEY_USER_ID);
}

// Giá trị không bí mật: web → localStorage (có thể bị chặn ở chế độ riêng tư), native → SecureStore cho gọn.
async function readPlain(key: string): Promise<string | null> {
  if (!IS_WEB) return SecureStore.getItemAsync(key);
  try {
    return window.localStorage.getItem(key);
  } catch (error) {
    console.warn('Không đọc được localStorage', error);
    return null;
  }
}

async function writePlain(key: string, value: string): Promise<void> {
  if (!IS_WEB) return SecureStore.setItemAsync(key, value);
  try {
    window.localStorage.setItem(key, value);
  } catch (error) {
    console.warn('Không ghi được localStorage', error);
  }
}

async function removePlain(key: string): Promise<void> {
  if (!IS_WEB) return SecureStore.deleteItemAsync(key);
  try {
    window.localStorage.removeItem(key);
  } catch (error) {
    console.warn('Không xoá được localStorage', error);
  }
}
