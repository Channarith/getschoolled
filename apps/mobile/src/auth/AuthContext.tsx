import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { getMe, login, signup, type Account } from "../api";
import { clearAuthToken, getToken, loadAuthToken, setAuthToken } from "../storage";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

type AuthContextValue = {
  status: AuthStatus;
  account: Account | null;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, displayName: string) => Promise<void>;
  signOut: () => Promise<void>;
  refreshAccount: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [account, setAccount] = useState<Account | null>(null);

  const refreshAccount = useCallback(async () => {
    if (!getToken()) {
      setAccount(null);
      setStatus("unauthenticated");
      return;
    }
    try {
      const me = await getMe();
      setAccount(me);
      setStatus("authenticated");
    } catch {
      await clearAuthToken();
      setAccount(null);
      setStatus("unauthenticated");
    }
  }, []);

  useEffect(() => {
    void (async () => {
      await loadAuthToken();
      if (!getToken()) {
        setStatus("unauthenticated");
        return;
      }
      await refreshAccount();
    })();
  }, [refreshAccount]);

  const signIn = useCallback(async (email: string, password: string) => {
    const res = await login(email, password);
    await setAuthToken(res.token);
    setAccount(res.account);
    setStatus("authenticated");
  }, []);

  const signUp = useCallback(async (email: string, password: string, displayName: string) => {
    const res = await signup(email, password, displayName);
    await setAuthToken(res.token);
    setAccount(res.account);
    setStatus("authenticated");
  }, []);

  const signOut = useCallback(async () => {
    await clearAuthToken();
    setAccount(null);
    setStatus("unauthenticated");
  }, []);

  const value = useMemo(
    () => ({ status, account, signIn, signUp, signOut, refreshAccount }),
    [status, account, signIn, signUp, signOut, refreshAccount],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
