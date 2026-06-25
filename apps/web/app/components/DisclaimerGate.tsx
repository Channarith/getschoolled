"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { acceptLegal, DISCLAIMER_ACCEPTED_EVENT, getToken } from "../lib/api";

// One-time AI & consent + legal disclaimer, shown ONCE AFTER LOGIN. Anonymous
// visitors can browse the catalog freely; the consent/legal acknowledgement
// appears the first time a signed-in user is seen and is then remembered in
// localStorage (and best-effort recorded on the backend acceptance store).
const STORAGE_KEY = "aoep_disclaimer_accepted_v1";
const REQUIRED = ["disclaimer", "terms", "privacy", "aup"];

export default function DisclaimerGate() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  // Re-evaluate on every route change so it triggers right after login (which
  // redirects, changing the pathname).
  useEffect(() => {
    try {
      const accepted = Boolean(localStorage.getItem(STORAGE_KEY));
      setOpen(Boolean(getToken()) && !accepted);
    } catch {
      setOpen(false);
    }
  }, [pathname]);

  async function onConsent() {
    try {
      localStorage.setItem(STORAGE_KEY, new Date().toISOString());
    } catch {
      /* ignore storage errors */
    }
    // Best-effort server-side record; UI proceeds regardless.
    acceptLegal("current-user", REQUIRED).catch(() => undefined);
    setOpen(false);
    try {
      window.dispatchEvent(new Event(DISCLAIMER_ACCEPTED_EVENT));
    } catch {
      /* no window */
    }
  }

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="AI and consent disclaimer"
      style={{
        position: "fixed", inset: 0, zIndex: 1000, display: "flex",
        alignItems: "center", justifyContent: "center",
        background: "rgba(0,0,0,0.6)", padding: 16,
      }}
    >
      <div className="card" style={{ maxWidth: 640, maxHeight: "86vh", overflowY: "auto" }}>
        <h2>Before you begin</h2>
        <p>
          <strong>This is an AI-driven course experience.</strong> Instruction,
          answers, and grading are conducted or assisted by artificial
          intelligence. AI output can be incorrect and is an educational aid, not
          professional, legal, medical, or accredited advice; a human reviews
          content where required and you may request human review.
        </p>
        <p>
          This platform is designed to meet applicable regulatory requirements for
          AI in education (e.g. FERPA, COPPA, GDPR, BIPA, and the EU AI Act), and
          region-restricted features are enforced automatically.
        </p>
        <p>
          By choosing <strong>&ldquo;I understand and consent&rdquo;</strong> you confirm you
          are taking this course voluntarily, fully aware of the associated legal
          terms, responsibilities, and liabilities, and that you agree to the{" "}
          <Link href="/legal">Terms, Privacy Notice, and Acceptable Use Policy</Link>.
          For minors, a parent/guardian or the school must have provided consent.
        </p>
        <div className="row" style={{ marginTop: 12, gap: 8 }}>
          <button onClick={onConsent}>I understand and consent</button>
          <Link href="/legal" style={{ alignSelf: "center" }}>Review full notices</Link>
        </div>
        <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          One-time notice. This summary does not replace the full notices and is
          not legal advice.
        </p>
      </div>
    </div>
  );
}
