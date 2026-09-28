// Đăng nhập / session cho React: SessionManager (session.ts) giữ token + quyết định khi nào đăng xuất.
import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from 'react';
import { apiRequest } from './api';
import { purgeUserData } from './localUserData';
import { SessionManager, SessionUser } from './session';
import { CLIENT_KIND, clearSession, loadSession, saveRefreshToken, saveSession } from './sessionStore';

type MessageOut = { message: string };
type Nullable<T> = { [K in keyof T]: T[K] | null };

export type AuthStatus = 'loading' | 'signedOut' | 'signedIn';

const SESSION_DEPS = {
  request: apiRequest,
  storage: {
    load: loadSession,
    save: saveSession,
    saveRefreshToken,
    // Mọi đường đăng xuất (bấm Đăng xuất, refresh bị 401/403, quá 30 ngày) đều qua đây → xoá cả dữ liệu người dùng.
    clear: async () => {
      await Promise.all([clearSession(), purgeUserData(AsyncStorage)]);
    },
  },
  clientKind: CLIENT_KIND,
};

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
  userId: string | null;
  login: SessionManager['login'];
  logout: SessionManager['logout'];
  getAccessToken: SessionManager['getAccessToken'];
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<{ status: AuthStatus } & Nullable<SessionUser>>({ status: 'loading', email: null, userId: null });
  const manager = useMemo(
    () =>
      new SessionManager(SESSION_DEPS, (user) =>
        setState(user ? { status: 'signedIn', ...user } : { status: 'signedOut', email: null, userId: null }),
      ),
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
