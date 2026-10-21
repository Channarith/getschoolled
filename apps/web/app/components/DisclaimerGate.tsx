"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { acceptLegal, DISCLAIMER_ACCEPTED_EVENT, getMe, getToken } from "../lib/api";

// One-time AI & consent + legal disclaimer, shown ONCE AFTER LOGIN. Anonymous
// visitors can browse the catalog freely; the consent/legal acknowledgement
// appears the first time a signed-in user is seen and is then remembered in
// localStorage (and best-effort recorded on the backend acceptance store).
const STORAGE_KEY = "aoep_disclaimer_accepted_v1";
const REQUIRED = ["disclaimer", "terms", "privacy", "aup"];

/** Legal/consent routes must remain readable under the gate (no overlay). */
const LEGAL_PATH_PREFIXES = [
  "/legal",
  "/privacy",
  "/terms",
  "/data-deletion",
  "/consent",
  "/transparency",
];

function isLegalPath(pathname: string | null): boolean {
  if (!pathname) return false;
  return LEGAL_PATH_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`),
  );
}

export default function DisclaimerGate() {
  const [open, setOpen] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const pathname = usePathname();

  // Re-evaluate on every route change so it triggers right after login (which
  // redirects, changing the pathname). Exempt legal pages so users can read
  // the notices the gate itself links to.
  useEffect(() => {
    if (isLegalPath(pathname)) {
      setOpen(false);
      return;
    }
    try {
      const accepted = Boolean(localStorage.getItem(STORAGE_KEY));
      setOpen(Boolean(getToken()) && !accepted);
    } catch {
      setOpen(false);
    }
  }, [pathname]);

  // showModal() puts this notice in the browser top layer, above the
  // setup-assistant WebGL mascot. A plain z-index overlay loses: the
  // mascot canvas is the next hit target under the frosted card, so the
  // consent click starts a drag on the character instead of the button.
  useLayoutEffect(() => {
    const dialog = dialogRef.current;
    if (!open || !dialog) return;
    if (!dialog.open) dialog.showModal();
    return () => {
      if (dialog.open) dialog.close();
    };
  }, [open]);

  async function onConsent() {
    try {
      localStorage.setItem(STORAGE_KEY, new Date().toISOString());
    } catch {
      /* ignore storage errors */
    }
    // Best-effort server-side record with the real account id (not a sentinel).
    try {
      const me = await getMe();
      await acceptLegal(me.id, REQUIRED);
    } catch {
      /* offline / unsigned — UI still proceeds */
    }
    setOpen(false);
    try {
      window.dispatchEvent(new Event(DISCLAIMER_ACCEPTED_EVENT));
    } catch {
      /* no window */
    }
  }

  if (!open) return null;

  return (
    <dialog
      ref={dialogRef}
      className="aoep-disclaimer-dialog"
      aria-label="AI and consent disclaimer"
      onCancel={(event) => event.preventDefault()}
    >
      <style>{`
        .aoep-disclaimer-dialog {
          border: none;
          padding: 0;
          margin: auto;
          background: transparent;
          width: min(640px, calc(100vw - 32px));
          max-height: 86vh;
          overflow: visible;
        }
        .aoep-disclaimer-dialog::backdrop {
          background: rgba(0, 0, 0, 0.6);
        }
      `}</style>
      <div
        className="card"
        style={{
          margin: 0,
          maxHeight: "86vh",
          overflowY: "auto",
          background: "var(--panel, #ffffff)",
          backdropFilter: "none",
          WebkitBackdropFilter: "none",
        }}
      >
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
          <Link href="/legal">Terms, Privacy Notice, and Acceptable Use Policy</Link>
          {" "}(<Link href="/terms">Terms</Link>, <Link href="/privacy">Privacy</Link>,{" "}
          <Link href="/data-deletion">Data deletion</Link>).
          For minors, a parent/guardian or the school must have provided consent.
        </p>
        <div className="row" style={{ marginTop: 12, gap: 8 }}>
          <button type="button" onClick={onConsent}>I understand and consent</button>
          <Link href="/legal" style={{ alignSelf: "center" }}>Review full notices</Link>
        </div>
        <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          One-time notice. This summary does not replace the full notices and is
          not legal advice.
        </p>
      </div>
    </dialog>
  );
}
