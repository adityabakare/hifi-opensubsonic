import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { fetchJson } from "@/lib/api";
import type { AuthContextType, AuthUser } from "@/types/auth";

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  checkAuth: async () => {},
  logout: async () => {},
});

interface MeResponse {
  status: string;
  username: string;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const checkAuth = async () => {
    try {
      const data = await fetchJson<MeResponse>("/api/me");
      if (data.status === "ok") {
        setUser({ username: data.username });
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    try {
      await fetch("/api/logout", { method: "POST" });
    } finally {
      setUser(null);
    }
  };

  useEffect(() => {
    void checkAuth();
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      checkAuth,
      logout,
    }),
    [user, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
