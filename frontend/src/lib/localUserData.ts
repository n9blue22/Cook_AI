// Dữ liệu người dùng lưu ở máy (AsyncStorage — trên web chính là localStorage): khoá theo user_id, và trên máy chỉ
// còn dữ liệu của đúng user đang đăng nhập. Đổi user / đăng xuất → xoá hết của người khác.
// Không import react-native: store.tsx / auth.tsx truyền AsyncStorage vào, test (localUserData.test.mjs) truyền bản giả.

export type UserDataStorage = {
  getItem(key: string): Promise<string | null>;
  getAllKeys(): Promise<readonly string[]>;
  multiRemove(keys: readonly string[]): Promise<void>;
};

// Mọi khoá dữ liệu người dùng mang tiền tố này, kể cả bản cũ khoá chung 'bepai:v1' / 'bepai:v2' (không biết của ai →
// xoá, không gán cho user nào). Phiên đăng nhập dùng 'bepai.' (sessionStore.ts) — không đụng.
const USER_DATA_PREFIX = 'bepai:';

export const userDataKey = (userId: string): string => `${USER_DATA_PREFIX}v3:${userId}`;

/** Xoá dữ liệu người dùng trên máy, trừ của keepUserId (null = xoá hết). */
export async function purgeUserData(storage: UserDataStorage, keepUserId: string | null = null): Promise<void> {
  const keep = keepUserId && userDataKey(keepUserId);
  const stale = (await storage.getAllKeys()).filter((key) => key.startsWith(USER_DATA_PREFIX) && key !== keep);
  if (stale.length) await storage.multiRemove(stale);
}

/** Dữ liệu đã lưu của userId (chuỗi JSON); trước đó xoá dữ liệu của mọi user khác và bản cũ khoá chung. */
export async function loadUserData(storage: UserDataStorage, userId: string): Promise<string | null> {
  await purgeUserData(storage, userId);
  return storage.getItem(userDataKey(userId));
}
