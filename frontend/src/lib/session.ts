// Phiên đăng nhập: access token chỉ nằm trong bộ nhớ, tự làm mới trước khi hết hạn.
// Session tối đa 30 ngày kể từ lúc đăng nhập (Supabase gói Free không tự ép được → ép ở client).
// Chỉ đăng xuất khi server trả 401/403 (isAuthRejection). Mất mạng / timeout → giữ phiên, thử lại sau.
// Không import expo / react-native: auth.tsx truyền request + storage vào, test (session.test.mjs) truyền bản giả.
import { isAuthRejection, type ApiOptions } from './api.ts'; // đuôi .ts: node --test cần, Metro/tsc cũng nhận
import type { PersistedSession } from './sessionStore';

const SESSION_MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;
const REFRESH_BEFORE_EXPIRY_MS = 60_000;
const RETRY_REFRESH_MS = 30_000;
const REFRESH_TIMEOUT_MS = 15_000; // treo quá lâu thì coi như mất mạng, không để splash chờ mãi

type SessionOut = { access_token: string; expires_in: number; user_id: string; email: string; refresh_token: string | null };

export type SessionDeps = {
  request: <T>(path: string, options?: ApiOptions) => Promise<T>;
  storage: {
    load: () => Promise<PersistedSession | null>;
    save: (session: PersistedSession) => Promise<void>;
    saveRefreshToken: (refreshToken: string | null) => Promise<void>;
    clear: () => Promise<void>;
  };
  clientKind: 'web' | 'native';
};

export class SessionManager {
  private access: { token: string; expiresAt: number } | null = null;
  private refreshToken: string | null = null;
  private signedInAt = 0; // 0 = không có phiên
  private timer: ReturnType<typeof setTimeout> | undefined;
  private readonly deps: SessionDeps;
  private readonly onChange: (email: string | null) => void;

  constructor(deps: SessionDeps, onChange: (email: string | null) => void) {
    this.deps = deps;
    this.onChange = onChange;
  }

  restore = async (): Promise<void> => {
    const saved = await this.deps.storage.load();
    if (!saved || Date.now() - saved.signedInAt > SESSION_MAX_AGE_MS) return this.signOutLocally();
    this.refreshToken = saved.refreshToken;
    this.signedInAt = saved.signedInAt;
    try {
      await this.refreshOrSignOut();
    } catch (error) {
      if (isAuthRejection(error)) return; // refreshOrSignOut đã đăng xuất
      // Mất mạng lúc mở app: vẫn vào app (dữ liệu sẽ báo "không tải được, thử lại"), làm mới lại sau.
      console.warn('Chưa làm mới được phiên (không tới được máy chủ) — giữ phiên, thử lại sau', error);
      this.schedule(RETRY_REFRESH_MS);
    }
    this.onChange(saved.email);
  };

  login = async (email: string, password: string): Promise<void> => {
    const body = { email, password, client: this.deps.clientKind };
    const out = await this.deps.request<SessionOut>('/auth/login', { method: 'POST', body });
    this.signedInAt = Date.now();
    this.apply(out);
    await this.deps.storage.save({ refreshToken: out.refresh_token, signedInAt: this.signedInAt, email: out.email });
    this.onChange(out.email);
  };

  logout = async (): Promise<void> => {
    const token = this.access?.token;
    try {
      if (token) await this.deps.request('/auth/logout', { method: 'POST', token });
    } catch (error) {
      console.warn('Huỷ phiên phía server thất bại — vẫn đăng xuất trên máy', error);
    }
    await this.signOutLocally();
  };

  // Token còn hạn cho request tiếp theo; chưa có (mở app lúc mất mạng) hoặc sắp hết hạn thì làm mới trước.
  // Làm mới lỗi mạng → ném ApiError cho màn gọi hiện "thử lại"; bị từ chối → đăng xuất rồi ném.
  getAccessToken = async (): Promise<string | null> => {
    if (!this.signedInAt) return null;
    if (!this.access || Date.now() > this.access.expiresAt - REFRESH_BEFORE_EXPIRY_MS) await this.refreshOrSignOut();
    return this.access?.token ?? null;
  };

  dispose = (): void => clearTimeout(this.timer);

  // Làm mới; server từ chối (401/403) → đăng xuất. Mọi lỗi đều ném tiếp để nơi gọi quyết định thử lại hay báo lỗi.
  private refreshOrSignOut = async (): Promise<void> => {
    if (Date.now() - this.signedInAt > SESSION_MAX_AGE_MS) return this.signOutLocally();
    try {
      const body = { client: this.deps.clientKind, refresh_token: this.refreshToken };
      const out = await this.deps.request<SessionOut>('/auth/refresh', { method: 'POST', body, timeoutMs: REFRESH_TIMEOUT_MS });
      this.apply(out);
      await this.deps.storage.saveRefreshToken(out.refresh_token);
    } catch (error) {
      if (isAuthRejection(error)) await this.signOutLocally();
      throw error;
    }
  };

  private apply(out: SessionOut): void {
    this.access = { token: out.access_token, expiresAt: Date.now() + out.expires_in * 1000 };
    if (out.refresh_token) this.refreshToken = out.refresh_token;
    this.schedule(out.expires_in * 1000 - REFRESH_BEFORE_EXPIRY_MS);
  }

  private schedule(delayMs: number): void {
    clearTimeout(this.timer);
    this.timer = setTimeout(() => {
      this.refreshOrSignOut().catch((error: unknown) => {
        console.warn('Tự làm mới phiên thất bại', error);
        if (!isAuthRejection(error)) this.schedule(RETRY_REFRESH_MS); // mất mạng → thử lại; bị từ chối → đã đăng xuất
      });
    }, Math.max(delayMs, 0));
  }

  private signOutLocally = async (): Promise<void> => {
    clearTimeout(this.timer);
    this.access = null;
    this.refreshToken = null;
    this.signedInAt = 0;
    await this.deps.storage.clear();
    this.onChange(null);
  };
}
