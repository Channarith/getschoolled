"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import {
  getToken,
  reviewCourses,
  reviewNext,
  reviewOverview,
  reviewSubmit,
  type ReviewCourse,
  type ReviewCourses,
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
  const [loaded, setLoaded] = useState(false);
  const [expired, setExpired] = useState(false);
  const [tab, setTab] = useState<"review" | "courses">("review");
  const [courses, setCourses] = useState<ReviewCourses | null>(null);

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
      .then((res) => {
        setLangs(res.languages);
        const first = res.languages.find((r) => r.translated !== false && r.units_total > 0);
        if (first) setLang(first.lang);
        setLoaded(true);
      })
      .catch((e) => {
        const msg = String(e.message || e);
        setDenied(/403|reviewers only/i.test(msg));
        setExpired(/401|expired|session|sign in/i.test(msg));
        setLoaded(true);
      });
  }, []);

  useEffect(() => {
    if (tab !== "courses" || courses) return;
    reviewCourses().then(setCourses).catch((e) => setError(String(e.message || e)));
  }, [tab, courses]);

  useEffect(() => { if (lang) { setSkipped([]); void load(lang, []); } }, [lang, load]);

  if (signedIn === null) return <main className="container"><p className="muted">Loading…</p></main>;
  if (!signedIn) return <main className="container"><p>Please <Link href="/login">sign in</Link> to continue.</p></main>;
  if (denied) return <main className="container"><p className="muted">This page is for Salareen staff.</p></main>;
  if (expired) return <main className="container"><p>Your session has ended. Please <Link href="/login">sign in again</Link>.</p></main>;

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

      <div role="tablist" aria-label="Views" style={{ display: "flex", gap: 8, margin: "16px 0 8px" }}>
        <button type="button" role="tab" aria-selected={tab === "review"} onClick={() => setTab("review")}
          className={tab === "review" ? "" : "secondary"}>Review</button>
        <button type="button" role="tab" aria-selected={tab === "courses"} onClick={() => setTab("courses")}
          className={tab === "courses" ? "" : "secondary"}>Courses and languages</button>
      </div>

      {tab === "courses" ? (
        <CoursesView data={courses} error={error} />
      ) : !langs.some((r) => r.units_total > 0) ? (
        <div className="card">
          <strong>No translations to review yet.</strong>
          <p className="muted" style={{ marginBottom: 0 }}>
            Passages appear here as machine translations are added for each language. Check back soon.
          </p>
        </div>
      ) : (
        <>
      <label style={{ display: "block", margin: "16px 0" }}>
        Language{" "}
        <select value={lang} onChange={(e) => setLang(e.target.value)} aria-label="Language">
          {langs.map((r) => (
            <option key={r.lang} value={r.lang} disabled={r.units_total === 0}>
              {LANG_NAMES[r.lang] || r.lang}
              {r.units_total > 0 ? ` (${r.units_reviewed}/${r.units_total})` : " — no translation yet"}
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
        </>
      )}
    </main>
  );
}

function Chip({ lang, info }: { lang: string; info: { units: number; reviewed: number; complete: boolean } }) {
  const pct = info.units ? Math.round((info.reviewed / info.units) * 100) : 0;
  const color = info.complete ? "#166534" : info.reviewed > 0 ? "#b45309" : "#475569";
  return (
    <span
      title={`${LANG_NAMES[lang] || lang}: ${info.reviewed} of ${info.units} passages reviewed`}
      style={{
        display: "inline-block", margin: "2px 4px 2px 0", padding: "2px 8px", borderRadius: 99,
        background: color, color: "#fff", fontSize: 12, fontWeight: 700,
      }}
    >
      {lang.toUpperCase()}{info.complete ? " ✓" : ` ${pct}%`}
    </span>
  );
}

function CourseRow({ course }: { course: ReviewCourse }) {
  return (
    <div style={{ padding: "8px 0", borderTop: "1px solid #e5e7eb" }}>
      <strong>{course.title}</strong>
      <div>
        {course.translated.map((lang) => <Chip key={lang} lang={lang} info={course.languages[lang]} />)}
      </div>
    </div>
  );
}

function CoursesView({ data, error }: { data: ReviewCourses | null; error: string }) {
  if (error && !data) return <div className="card" style={{ borderColor: "#dc2626" }}>{error}</div>;
  if (!data) return <p className="muted">Loading courses…</p>;
  const t = data.totals;
  return (
    <div>
      <div className="card">
        <div><strong>{t.courses_completed}</strong> of {t.courses} courses completed (every translated language reviewed)</div>
        <div className="muted">
          {t.courses_translated} courses have at least one translation · {t.courses_not_started} not started ·
          {" "}{t.languages_supported} languages supported
        </div>
        <div style={{ marginTop: 6 }}>
          <Bar done={t.courses_completed} total={t.courses} />
        </div>
      </div>

      <h2 style={{ marginTop: 18 }}>Completed ({data.completed.length})</h2>
      {data.completed.length === 0 ? (
        <p className="muted">No course is fully reviewed yet. Finish one course at a time: the review queue keeps going in the same course until it is done.</p>
      ) : (
        <div className="card">{data.completed.map((c) => <CourseRow key={c.id} course={c} />)}</div>
      )}

      <h2 style={{ marginTop: 18 }}>In progress ({data.in_progress.length})</h2>
      {data.in_progress.length === 0 ? (
        <p className="muted">Nothing in progress.</p>
      ) : (
        <div className="card">{data.in_progress.map((c) => <CourseRow key={c.id} course={c} />)}</div>
      )}
      <p className="muted" style={{ marginTop: 12 }}>
        {t.courses_not_started} courses have no translation yet and are not listed.
      </p>
    </div>
  );
}
