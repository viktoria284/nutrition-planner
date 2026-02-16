import { createContext, useEffect, useMemo, useState } from "react";
import type { User } from "../api/auth";
import * as authApi from "../api/auth";
import { ApiError } from "../api/http";

const TOKEN_KEY = "access_token";

type AuthState = {
  token: string | null;
  user: User | null;
  isLoading: boolean;
  error: string | null;
  setError: (msg: string | null) => void;
  login: (identifier: string, password: string) => Promise<void>;
  register: (data: { email: string; username: string; password: string; display_name?: string | null }) => Promise<void>;
  logout: () => void;
  refreshMe: (tokenOverride?: string | null) => Promise<void>;
};

export const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
    setError(null);
  };

  const refreshMe = async (tokenOverride?: string | null) => {
    const activeToken = tokenOverride ?? token;
    if (!activeToken) {
      setUser(null);
      return;
    }

    try {
      const u = await authApi.me(activeToken);
      setUser(u);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) logout();
      else setError(e instanceof Error ? e.message : "Ошибка /auth/me");
    }
  };

  useEffect(() => {
    (async () => {
      setIsLoading(true);
      await refreshMe();
      setIsLoading(false);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const doLogin = async (identifier: string, password: string) => {
    setError(null);
    const t = await authApi.login(identifier, password);
    localStorage.setItem(TOKEN_KEY, t.access_token);
    setToken(t.access_token);
    await refreshMe(t.access_token);
  };

  const doRegister = async (data: { email: string; username: string; password: string; display_name?: string | null }) => {
    setError(null);
    await authApi.register(data);
    await doLogin(data.email || data.username, data.password);
  };

  const value = useMemo<AuthState>(
    () => ({
      token,
      user,
      isLoading,
      error,
      setError,
      login: doLogin,
      register: doRegister,
      logout,
      refreshMe,
    }),
    [token, user, isLoading, error],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
