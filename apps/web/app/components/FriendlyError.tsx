"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useT } from "../lib/i18n";
import {
  FRIENDLY_ART,
  FRIENDLY_COPY,
  FRIENDLY_KIND_MOOD,
  FRIENDLY_PAGE_CSS,
  classifyStatus,
  type FriendlyKind,
} from "../lib/friendlyError.generated";

export type FriendlyErrorProps = {
  status?: number | null;
  kind?: FriendlyKind;
  /** Return true when the thing works again. Without it the button reloads the page. */
  onRetry?: () => Promise<boolean> | boolean | void;
  /** Network-style failures retry by themselves after this many seconds (0 = never). */
  autoRetrySeconds?: number;
  /** Cover the whole page (default) or sit inline in a card. */
  inline?: boolean;
  /** Force a locale (global-error has no provider). */
  locale?: string;
  onClose?: () => void;
};

function deviceLocale(): string {
  if (typeof navigator === "undefined") return "en";
  const tags = [...(navigator.languages || []), navigator.language];
  for (const tag of tags) {
    const base = String(tag || "").toLowerCase().split("-")[0];
    if (FRIENDLY_COPY[base]) return base;
  }
  return "en";
}

/** Friendly mascot screen for 404 / 501 / 5xx / offline. Never shows a bare error string. */
export default function FriendlyError({
  status = null,
  kind: kindProp,
  onRetry,
  autoRetrySeconds = 0,
  inline = false,
  locale: localeProp,
  onClose,
}: FriendlyErrorProps) {
  const { locale: ctxLocale } = useT();
  const [deviceLoc, setDeviceLoc] = useState("en");
  useEffect(() => { setDeviceLoc(deviceLocale()); }, []);
  const wanted = localeProp || ctxLocale || deviceLoc;
  const base = String(wanted).toLowerCase().split("-")[0];
  const copy = FRIENDLY_COPY[base] || FRIENDLY_COPY.en;
  const fallback = FRIENDLY_COPY.en;
  const kind: FriendlyKind = kindProp || classifyStatus(status) || "oops";
  const text = copy[kind] || fallback[kind];
  const common = { ...fallback.common, ...(copy.common || {}) };
  const [note, setNote] = useState("");
  const [left, setLeft] = useState(0);
  const busy = useRef(false);
  const primary = useRef<HTMLButtonElement>(null);

  const tryNow = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    setNote(common.checking);
    let ok = false;
    try {
      const result = onRetry ? await onRetry() : undefined;
      ok = result !== false;
    } catch { ok = false; }
    busy.current = false;
    if (ok) {
      if (!onRetry && typeof window !== "undefined") window.location.reload();
      onClose?.();
    } else {
      setNote(common.stillDown);
      if (autoRetrySeconds > 0) setLeft(autoRetrySeconds);
    }
  }, [onRetry, onClose, common.checking, common.stillDown, autoRetrySeconds]);

  useEffect(() => { if (autoRetrySeconds > 0 && onRetry && (kind === "network" || kind === "offline")) setLeft(autoRetrySeconds); }, [autoRetrySeconds, onRetry, kind]);
  useEffect(() => {
    if (left <= 0) return undefined;
    const id = window.setTimeout(() => {
      if (left <= 1) { setLeft(0); void tryNow(); } else setLeft(left - 1);
    }, 1000);
    return () => window.clearTimeout(id);
  }, [left, tryNow]);
  useEffect(() => { if (!inline) primary.current?.focus(); }, [inline]);

  // "Try again" makes no sense for a page that does not exist or a feature that is not built yet.
  const showRetry = Boolean(onRetry) || kind === "network" || kind === "offline" || kind === "oops";
  const countdown = left > 0 ? common.retryIn.replace("{n}", String(left)) : note;
  const code = status ? common.status.replace("{code}", String(status)) : "";
  return (
    <div className={inline ? "sfe-inline" : "sfe-screen"} role="alert" data-testid="friendly-error" data-sfe-kind={kind}>
      <style dangerouslySetInnerHTML={{ __html: FRIENDLY_PAGE_CSS + ".sfe-inline{position:relative;display:grid;place-items:center;padding:28px 16px;background:radial-gradient(900px 500px at 50% 0%,#1d2a58 0%,#0b1020 70%);border-radius:20px;color:#eef2ff}" }} />
      {!inline && <div className="sfe-stars" />}
      <div className="sfe-card">
        <div aria-hidden="true" dangerouslySetInnerHTML={{ __html: FRIENDLY_ART[FRIENDLY_KIND_MOOD[kind]] }} />
        <h1 className="sfe-title">{text.title}</h1>
        <p className="sfe-body">{text.body}</p>
        <p className="sfe-hint">{text.hint}</p>
        <p className="sfe-note" aria-live="polite">{countdown}</p>
        <div className="sfe-actions">
          {showRetry && <button ref={primary} type="button" className="sfe-btn sfe-primary" onClick={() => void tryNow()}>{common.tryAgain}</button>}
          <a className={showRetry ? "sfe-btn" : "sfe-btn sfe-primary"} href="/">{common.home}</a>
          <button type="button" className="sfe-btn" onClick={() => { onClose?.(); if (typeof window !== "undefined" && window.history.length > 1) window.history.back(); }}>{common.back}</button>
        </div>
        {code && <span className="sfe-code">{code}</span>}
      </div>
    </div>
  );
}
