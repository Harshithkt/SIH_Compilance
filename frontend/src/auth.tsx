import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError, clearToken, getToken, request, setToken, setUnauthorizedHandler } from "./api";

export type Role = "officer" | "supervisor" | "admin";

export interface AuthUser {
  id: string;
  username: string;
  full_name: string;
  role: Role;
  is_active: boolean;
}

interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_at: string;
  user: AuthUser;
}

/** Ranked to match the backend: each role holds every permission of the ones before it. */
const RANK: Record<Role, number> = { officer: 0, supervisor: 1, admin: 2 };

interface AuthValue {
  user: AuthUser | null;
  /** "loading" only while an existing token is being revalidated on start-up. */
  status: "loading" | "authenticated" | "anonymous";
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  /** True when the signed-in account holds `role` or a role above it. */
  can: (role: Role) => boolean;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<AuthValue["status"]>("loading");

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
    setStatus("anonymous");
  }, []);

  // A token that the server no longer honours (expired, or the account was
  // deactivated mid-session) must end the session everywhere at once, not just on
  // whichever screen happened to make the call.
  useEffect(() => {
    setUnauthorizedHandler(logout);
  }, [logout]);

  useEffect(() => {
    // Nothing stored means there is no session to revalidate — going straight to the
    // sign-in screen avoids a round trip that could only ever come back 401.
    if (!getToken()) {
      setStatus("anonymous");
      return;
    }

    let cancelled = false;
    request<AuthUser>("/auth/me")
      .then((me) => {
        if (cancelled) return;
        setUser(me);
        setStatus("authenticated");
      })
      .catch(() => {
        if (cancelled) return;
        setUser(null);
        setStatus("anonymous");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const result = await request<LoginResponse>("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: username.trim(), password }),
    });
    setToken(result.access_token);
    setUser(result.user);
    setStatus("authenticated");
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      user,
      status,
      login,
      logout,
      can: (role: Role) => (user ? RANK[user.role] >= RANK[role] : false),
    }),
    [user, status, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}

export function loginErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Could not reach the server. Check your connection and try again.";
}
