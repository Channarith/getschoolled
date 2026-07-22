"use client";

import Link from "next/link";

import { useT } from "../lib/i18n";

// Shown when a feature requires sign-in. Always redirects to /login — no
// anonymous/preview access is permitted.
export default function SignInToUse({ body }: { body?: string }) {
  const { t } = useT();
  return (
    <div className="card" style={{ borderColor: "#f59e0b" }}>
      <strong>🔒 {t("preview.lockedTitle")}</strong>
      <div className="muted" style={{ marginTop: 4 }}>
        {body || "Sign in to access this feature."}
      </div>
      <div className="row" style={{ marginTop: 10 }}>
        <Link href="/login"><button style={{ background: "#e50914", color: "#fff" }}>{t("preview.signIn")}</button></Link>
      </div>
    </div>
  );
}
