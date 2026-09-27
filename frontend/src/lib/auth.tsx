// Đăng nhập / session. Access token chỉ nằm trong bộ nhớ, tự làm mới trước khi hết hạn.
// Session tối đa 30 ngày kể từ lúc đăng nhập (Supabase gói Free không tự ép được → ép ở client).
import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from 'react';
import { ApiError, apiRequest } from './api';
import { CLIENT_KIND, clearSession, loadSession, saveRefreshToken, saveSession } from './sessionStore';

const SESSION_MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;
const REFRESH_BEFORE_EXPIRY_MS = 60_000;
const RETRY_REFRESH_MS = 30_000;
const UNAUTHORIZED = 401;

type SessionOut = { access_token: string; expires_in: number; user_id: string; email: string; refresh_token: string | null };
type MessageOut = { message: string };

export type AuthStatus = 'loading' | 'signedOut' | 'signedIn';

class SessionManager {
  private access: { token: string; expiresAt: number } | null = null;
  private refreshToken: string | null = null;
  private signedInAt = 0;
  private timer: ReturnType<typeof setTimeout> | undefined;

  constructor(private readonly onChange: (email: string | null) => void) {}

  restore = async (): Promise<void> => {
    const saved = await loadSession();
    if (!saved || Date.now() - saved.signedInAt > SESSION_MAX_AGE_MS) return this.signOutLocally();
    this.refreshToken = saved.refreshToken;
    this.signedInAt = saved.signedInAt;
    try {
      await this.refresh();
      this.onChange(saved.email);
    } catch (error) {
      console.warn('Khôi phục phiên đăng nhập thất bại', error);
      await this.signOutLocally();
    }
  };

  login = async (email: string, password: string): Promise<void> => {
    const out = await apiRequest<SessionOut>('/auth/login', { method: 'POST', body: { email, password, client: CLIENT_KIND } });
    this.signedInAt = Date.now();
    this.apply(out);
    await saveSession({ refreshToken: out.refresh_token, signedInAt: this.signedInAt, email: out.email });
    this.onChange(out.email);
  };

  logout = async (): Promise<void> => {
    const token = this.access?.token;
    try {
      if (token) await apiRequest('/auth/logout', { method: 'POST', token });
    } catch (error) {
      console.warn('Huỷ phiên phía server thất bại — vẫn đăng xuất trên máy', error);
    }
    await this.signOutLocally();
  };

  // Token còn hạn cho request tiếp theo; sắp hết hạn thì làm mới trước.
  getAccessToken = async (): Promise<string | null> => {
    if (!this.access) return null;
    if (Date.now() > this.access.expiresAt - REFRESH_BEFORE_EXPIRY_MS) await this.refresh();
    return this.access?.token ?? null;
  };

  dispose = (): void => clearTimeout(this.timer);

  private refresh = async (): Promise<void> => {
    if (Date.now() - this.signedInAt > SESSION_MAX_AGE_MS) return this.signOutLocally();
    const body = { client: CLIENT_KIND, refresh_token: this.refreshToken };
    const out = await apiRequest<SessionOut>('/auth/refresh', { method: 'POST', body });
    this.apply(out);
    await saveRefreshToken(out.refresh_token);
  };

  private apply(out: SessionOut): void {
    this.access = { token: out.access_token, expiresAt: Date.now() + out.expires_in * 1000 };
    if (out.refresh_token) this.refreshToken = out.refresh_token;
    this.schedule(out.expires_in * 1000 - REFRESH_BEFORE_EXPIRY_MS);
  }

  private schedule(delayMs: number): void {
    clearTimeout(this.timer);
    this.timer = setTimeout(() => {
      this.refresh().catch((error: unknown) => {
        console.warn('Tự làm mới phiên thất bại', error);
        // Phiên bị thu hồi / hết hạn → đăng xuất; lỗi mạng → thử lại sau
        if (error instanceof ApiError && error.status === UNAUTHORIZED) void this.signOutLocally();
        else this.schedule(RETRY_REFRESH_MS);
      });
    }, Math.max(delayMs, 0));
  }

  private signOutLocally = async (): Promise<void> => {
    clearTimeout(this.timer);
    this.access = null;
    this.refreshToken = null;
    await clearSession();
    this.onChange(null);
  };
}

// Các thao tác không cần session.
export const registerAccount = (email: string, password: string) =>
  apiRequest<MessageOut>('/auth/register', { method: 'POST', body: { email, password } }).then((out) => out.message);

export const requestPasswordReset = (email: string) =>
  apiRequest<MessageOut>('/auth/forgot-password', { method: 'POST', body: { email } }).then((out) => out.message);

export const resetPassword = (recoveryToken: string, newPassword: string) =>
  apiRequest<MessageOut>('/auth/reset-password', {
    method: 'POST',
    body: { access_token: recoveryToken, new_password: newPassword },
  }).then((out) => out.message);

type AuthContextValue = {
  status: AuthStatus;
  email: string | null;
  login: SessionManager['login'];
  logout: SessionManager['logout'];
  getAccessToken: SessionManager['getAccessToken'];
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<{ status: AuthStatus; email: string | null }>({ status: 'loading', email: null });
  const manager = useMemo(
    () => new SessionManager((email) => setState(email ? { status: 'signedIn', email } : { status: 'signedOut', email: null })),
    [],
  );

  useEffect(() => {
    void manager.restore();
    return manager.dispose;
  }, [manager]);

  const value = useMemo(
    () => ({ ...state, login: manager.login, logout: manager.logout, getAccessToken: manager.getAccessToken }),
    [state, manager],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth phải nằm trong AuthProvider');
  return value;
}
