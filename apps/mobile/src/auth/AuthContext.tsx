import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import {
  getMe, login, signup, verify2faLogin, type Account, type LoginResult,
} from "../api";
import { clearAuthToken, getToken, loadAuthToken, setAuthToken, setPreviewMode } from "../storage";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated" | "mfa_pending";

type AuthContextValue = {
  status: AuthStatus;
  account: Account | null;
  signIn: (email: string, password: string) => Promise<void>;
  verify2fa: (code: string) => Promise<void>;
  cancel2fa: () => void;
  signUp: (email: string, password: string, displayName: string) => Promise<void>;
  signOut: () => Promise<void>;
  refreshAccount: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function is2faRequired(res: LoginResult): res is { requires_2fa: true; mfa_token: string } {
  return "requires_2fa" in res && res.requires_2fa === true;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [account, setAccount] = useState<Account | null>(null);
  const [mfaToken, setMfaToken] = useState("");

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
    if (is2faRequired(res)) {
      setMfaToken(res.mfa_token);
      setStatus("mfa_pending");
      return;
    }
    await setAuthToken(res.token);
    await setPreviewMode(false);
    setAccount(res.account);
    setStatus("authenticated");
  }, []);

  const verify2fa = useCallback(async (code: string) => {
    if (!mfaToken) throw new Error("No MFA session");
    const res = await verify2faLogin(mfaToken, code);
    setMfaToken("");
    await setAuthToken(res.token);
    await setPreviewMode(false);
    setAccount(res.account);
    setStatus("authenticated");
  }, [mfaToken]);

  const cancel2fa = useCallback(() => {
    setMfaToken("");
    setStatus("unauthenticated");
  }, []);

  const signUp = useCallback(async (email: string, password: string, displayName: string) => {
    const res = await signup(email, password, displayName);
    await setAuthToken(res.token);
    await setPreviewMode(false);
    setAccount(res.account);
    setStatus("authenticated");
  }, []);

  const signOut = useCallback(async () => {
    await clearAuthToken();
    setAccount(null);
    setMfaToken("");
    setStatus("unauthenticated");
  }, []);

  const value = useMemo(
    () => ({
      status, account, signIn, verify2fa, cancel2fa, signUp, signOut, refreshAccount,
    }),
    [status, account, signIn, verify2fa, cancel2fa, signUp, signOut, refreshAccount],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
