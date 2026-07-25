"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  clearTokens,
  getAccessToken,
  request,
  storeTokens,
} from "./api";

export type CurrentUser = {
  id: string;
  email: string;
  display_name: string;
  roles: string[];
};

type AuthValue = {
  user: CurrentUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    display_name: string,
    password: string
  ) => Promise<void>;
  logout: () => void;
  hasRole: (...roles: string[]) => boolean;
};

const AuthContext = createContext<AuthValue | null>(null);

type AuthResponse = {
  user: CurrentUser;
  access_token: string;
  refresh_token: string;
};

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshMe = useCallback(async () => {
    // الموقع الثابت بلا مصادقة ولا خدمة: الطلب هنا يخطئ حتمًا
    // ويؤخّر أول رسم على كل صفحة عامة.
    if (process.env.NEXT_PUBLIC_QSP_STATIC === "1") {
      setUser(null);
      setLoading(false);
      return;
    }
    if (!getAccessToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await request<CurrentUser>("/auth/me", { auth: true });
      setUser(me);
    } catch {
      clearTokens();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshMe();
  }, [refreshMe]);

  const login = useCallback(async (email: string, password: string) => {
    const data = await request<AuthResponse>("/auth/login", {
      method: "POST",
      body: { email, password },
    });
    storeTokens(data.access_token, data.refresh_token);
    setUser(data.user);
  }, []);

  const register = useCallback(
    async (email: string, display_name: string, password: string) => {
      const data = await request<AuthResponse>("/auth/register", {
        method: "POST",
        body: { email, display_name, password },
      });
      storeTokens(data.access_token, data.refresh_token);
      setUser(data.user);
    },
    []
  );

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
  }, []);

  const hasRole = useCallback(
    (...roles: string[]) =>
      !!user && roles.some((r) => user.roles.includes(r)),
    [user]
  );

  const value = useMemo(
    () => ({ user, loading, login, register, logout, hasRole }),
    [user, loading, login, register, logout, hasRole]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export const ROLE_LABELS: Record<string, string> = {
  researcher: "باحث",
  linguistic_reviewer: "مراجع لغوي",
  sharia_reviewer: "مراجع شرعي",
  text_officer: "مسؤول النص",
  quality_manager: "مدير الجودة",
  tech_admin: "مدير تقني",
  arbitration_committee: "لجنة الحسم",
};
