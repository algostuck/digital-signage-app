import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  api,
  getStoredRefreshToken,
  restoreSession,
  setSessionExpiredHandler,
  setTokens,
} from "./api";

export interface SessionUser {
  id: string;
  organization_id: string;
  active_organization_id: string | null;
  email: string;
  full_name: string;
  status: string;
  is_superuser: boolean;
  roles: { id: string; name: string; is_system: boolean }[];
  permissions: string[];
}

interface TokenPair {
  access_token: string;
  refresh_token: string;
  user: SessionUser;
}

interface AuthContextValue {
  user: SessionUser | null;
  initializing: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  switchTenant: (organizationId: string) => Promise<void>;
  hasPermission: (code: string) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [initializing, setInitializing] = useState(true);

  // Restore the session from the stored refresh token on first load.
  // `restoreSession` is single-flight and lock-guarded: this effect runs
  // twice under StrictMode, and a second refresh with the same token would
  // be read by the server as token reuse and end the session.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const envelope = await restoreSession();
        if (!cancelled && envelope?.data) setUser(envelope.data.user as SessionUser);
      } finally {
        if (!cancelled) setInitializing(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setSessionExpiredHandler(() => setUser(null));
    return () => setSessionExpiredHandler(null);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const envelope = await api.post<TokenPair>("/auth/login", { email, password });
    const data = envelope.data!;
    setTokens(data.access_token, data.refresh_token);
    setUser(data.user);
  }, []);

  const switchTenant = useCallback(async (organizationId: string) => {
    const stored = getStoredRefreshToken();
    if (!stored) throw new Error("No session to switch");
    const envelope = await api.post<TokenPair>("/auth/switch-tenant", {
      organization_id: organizationId,
      refresh_token: stored,
    });
    const data = envelope.data!;
    setTokens(data.access_token, data.refresh_token);
    setUser(data.user);
  }, []);

  const logout = useCallback(async () => {
    const stored = getStoredRefreshToken();
    if (stored) {
      await api.post("/auth/logout", { refresh_token: stored }).catch(() => undefined);
    }
    setTokens(null, null);
    setUser(null);
  }, []);

  const hasPermission = useCallback(
    (code: string) =>
      user != null && (user.is_superuser || user.permissions.includes(code)),
    [user],
  );

  const value = useMemo(
    () => ({ user, initializing, login, logout, switchTenant, hasPermission }),
    [user, initializing, login, logout, switchTenant, hasPermission],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
