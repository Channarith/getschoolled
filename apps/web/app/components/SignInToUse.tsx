"use client";

import Link from "next/link";

import { useT } from "../lib/i18n";

// Shown in place of (or above) an interactive action when the visitor is in
// view-only preview / not signed in. Preview lets people browse and Watch, but
// taking classes or audio lessons requires an account.
export default function SignInToUse({ body }: { body?: string }) {
  const { t } = useT();
  return (
    <div className="card" style={{ borderColor: "#f59e0b" }}>
      <strong>🔒 {t("preview.lockedTitle")}</strong>
      <div className="muted" style={{ marginTop: 4 }}>
        {body || t("preview.lockedBody")}
      </div>
      <div className="row" style={{ marginTop: 10, gap: 12 }}>
        <Link href="/login"><button style={{ background: "#e50914", color: "#fff" }}>{t("preview.signIn")}</button></Link>
        <Link href="/watch" style={{ alignSelf: "center" }}>{t("preview.watchInstead")}</Link>
      </div>
    </div>
  );
}
