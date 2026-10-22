"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import {
  getToken,
  reviewNext,
  reviewOverview,
  reviewSubmit,
  type ReviewStats,
  type ReviewUnit,
} from "../../lib/api";

const LANG_NAMES: Record<string, string> = {
  es: "Spanish", fr: "French", de: "German", it: "Italian", pt: "Portuguese", nl: "Dutch",
  pl: "Polish", ru: "Russian", uk: "Ukrainian", tr: "Turkish", ar: "Arabic", he: "Hebrew",
  hi: "Hindi", bn: "Bengali", ur: "Urdu", fa: "Persian", zh: "Chinese", ja: "Japanese",
  ko: "Korean", vi: "Vietnamese", th: "Thai", id: "Indonesian", sw: "Swahili", el: "Greek",
  cs: "Czech", km: "Khmer",
};

const CHOICES = [
  { id: "correct", label: "A  Correct as written" },
  { id: "small_fix", label: "B  Needs a small fix" },
  { id: "source_wrong", label: "C  The English itself is wrong or off topic" },
  { id: "better", label: "D  I'll type a better translation" },
] as const;

function Bar({ done, total }: { done: number; total: number }) {
  const pct = total ? Math.round((done / total) * 100) : 0;
  return (
    <div aria-label={`${pct}% done`} style={{ background: "#e5e7eb", borderRadius: 8, height: 10, overflow: "hidden" }}>
      <div style={{ width: `${pct}%`, background: "#16a34a", height: "100%" }} />
    </div>
  );
}

export default function TranslationReviewPage() {
  const [signedIn, setSignedIn] = useState<boolean | null>(null);
  const [denied, setDenied] = useState(false);
  const [langs, setLangs] = useState<ReviewStats[]>([]);
  const [lang, setLang] = useState("");
  const [stats, setStats] = useState<ReviewStats | null>(null);
  const [unit, setUnit] = useState<ReviewUnit | null>(null);
  const [verdict, setVerdict] = useState<string>("");
  const [heading, setHeading] = useState("");
  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  const [skipped, setSkipped] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (language: string, skip: string[]) => {
    setBusy(true);
    setError("");
    try {
      const res = await reviewNext(language, skip);
      setStats(res.stats);
      setUnit(res.unit);
      setVerdict("");
      setHeading(res.unit?.machine.heading ?? "");
      setText(res.unit?.machine.text ?? "");
      setNote("");
    } catch (e) {
      setError(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (!getToken()) { setSignedIn(false); return; }
    setSignedIn(true);
    reviewOverview()
      .then((res) => { setLangs(res.languages); if (res.languages[0]) setLang(res.languages[0].lang); })
      .catch((e) => setDenied(/403|reviewers only/i.test(String(e.message || e))));
  }, []);

  useEffect(() => { if (lang) { setSkipped([]); void load(lang, []); } }, [lang, load]);

  if (signedIn === null) return <main className="container"><p className="muted">Loading…</p></main>;
  if (!signedIn) return <main className="container"><p>Please <Link href="/login">sign in</Link> to continue.</p></main>;
  if (denied) return <main className="container"><p className="muted">This page is for Salareen staff.</p></main>;

  const needsText = verdict === "small_fix" || verdict === "better";

  async function submit() {
    if (!unit || !verdict) return;
    setBusy(true);
    setError("");
    try {
      const res = await reviewSubmit({
        lang, key: unit.key, verdict,
        heading: needsText ? heading : "", text: needsText ? text : "", note,
      });
      setStats(res.stats);
      setLangs((rows) => rows.map((r) => (r.lang === res.stats.lang ? res.stats : r)));
      await load(lang, skipped);
    } catch (e) {
      const msg = String((e as Error).message || e);
      setError(msg);
      if (/already reviewed/i.test(msg)) await load(lang, skipped);
      setBusy(false);
    }
  }

  async function skip() {
    if (!unit) return;
    const next = [...skipped, unit.key];
    setSkipped(next);
    await load(lang, next);
  }

  const totalUnits = langs.reduce((n, r) => n + r.units_total, 0);
  const doneUnits = langs.reduce((n, r) => n + r.units_reviewed, 0);

  return (
    <main className="container" style={{ maxWidth: 900 }}>
      <h1>Translation review</h1>
      <p className="muted">
        Each item is one distinct passage. Your answer is saved for every course page that repeats it,
        and nobody else is shown it again.
      </p>

      <div className="card">
        <strong>All languages</strong>
        <div style={{ margin: "6px 0" }}><Bar done={doneUnits} total={totalUnits} /></div>
        <div className="muted">{doneUnits} of {totalUnits} passages reviewed, {totalUnits - doneUnits} remaining</div>
      </div>

      <label style={{ display: "block", margin: "16px 0" }}>
        Language{" "}
        <select value={lang} onChange={(e) => setLang(e.target.value)} aria-label="Language">
          {langs.map((r) => (
            <option key={r.lang} value={r.lang}>
              {LANG_NAMES[r.lang] || r.lang} ({r.units_reviewed}/{r.units_total})
            </option>
          ))}
        </select>
      </label>

      {stats && (
        <div className="card">
          <div className="muted">
            {stats.units_reviewed} done · {stats.units_remaining} remaining · covers {stats.pages_covered} of{" "}
            {stats.pages_total} course pages
            {stats.untranslated_units > 0 ? ` · ${stats.untranslated_units} passages not translated yet` : ""}
          </div>
          <div style={{ marginTop: 6 }}><Bar done={stats.units_reviewed} total={stats.units_total} /></div>
        </div>
      )}

      {error && <div className="card" style={{ borderColor: "#dc2626" }}>{error}</div>}

      {!unit && !busy && stats && (
        <div className="card">Nothing left to review in this language right now.</div>
      )}

      {unit && (
        <div className="card" style={{ marginTop: 16 }}>
          <p className="muted" style={{ marginTop: 0 }}>
            Used on {unit.pages} course page{unit.pages === 1 ? "" : "s"}
            {unit.courses.length ? `, for example ${unit.courses.join(", ")}` : ""}.
          </p>
          <h3 style={{ marginBottom: 4 }}>English</h3>
          <p style={{ margin: "0 0 4px" }}><strong>{unit.source.heading}</strong></p>
          <p style={{ marginTop: 0 }}>{unit.source.text}</p>

          <h3 style={{ marginBottom: 4 }}>{LANG_NAMES[lang] || lang} (machine translation)</h3>
          <p style={{ margin: "0 0 4px" }}><strong>{unit.machine.heading}</strong></p>
          <p style={{ marginTop: 0 }}>{unit.machine.text}</p>

          <div role="radiogroup" aria-label="Your verdict" style={{ display: "grid", gap: 8, margin: "14px 0" }}>
            {CHOICES.map((c) => (
              <label key={c.id} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <input type="radio" name="verdict" checked={verdict === c.id}
                  onChange={() => { setVerdict(c.id); if (c.id === "better") { setHeading(""); setText(""); } else { setHeading(unit.machine.heading); setText(unit.machine.text); } }} />
                {c.label}
              </label>
            ))}
          </div>

          {needsText && (
            <div style={{ display: "grid", gap: 8 }}>
              <input value={heading} onChange={(e) => setHeading(e.target.value)} aria-label="Heading" placeholder="Heading" />
              <textarea value={text} onChange={(e) => setText(e.target.value)} rows={8} aria-label="Corrected text" placeholder="Corrected text" />
            </div>
          )}
          {verdict === "source_wrong" && (
            <input value={note} onChange={(e) => setNote(e.target.value)} aria-label="What is wrong" placeholder="What is wrong with the English? (optional)" style={{ width: "100%" }} />
          )}

          <div className="row" style={{ marginTop: 14 }}>
            <button type="button" onClick={() => void submit()} disabled={busy || !verdict || (needsText && !text.trim())}>
              Save and next
            </button>
            <button type="button" className="secondary" onClick={() => void skip()} disabled={busy}>
              Skip
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
