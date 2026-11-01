import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../api";
import type { User } from "../api/types";
import { UNAUTHORIZED_EVENT, asApiError, type ApiError } from "../api/errors";

type AuthState = {
  user: User | null;
  loading: boolean;
  error: ApiError | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      setUser(await api.me());
    } catch (e) {
      const apiError = asApiError(e);
      if (apiError.status === 401) setUser(null);
      else setError(apiError);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  // انقضای نشست در میانه‌ی کار: کاربر به صفحه‌ی ورود هدایت می‌شود (Guard)
  useEffect(() => {
    const onExpired = () => {
      setUser(null);
      setError(null);
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onExpired);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onExpired);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    setError(null);
    try {
      setUser(await api.login(username, password));
    } catch (e) {
      throw asApiError(e);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
      setError(null);
    } catch (e) {
      const apiError = asApiError(e);
      setError(apiError);
      throw apiError;
    } finally {
      setUser(null);
    }
  }, []);

  const value = useMemo(
    () => ({ user, loading, error, login, logout, refresh }),
    [user, loading, error, login, logout, refresh],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("AuthProvider missing");
  return v;
}
