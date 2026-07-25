"use client";

import { useEffect, useRef, useState } from "react";
import {
  adminListFlags,
  adminListFlagsSession,
  adminSetFlag,
  adminSetFlagSession,
  adminSurveyInsights,
  adminListBugReports,
  adminListVouchers,
  adminCreateVoucher,
  getAdRevenue,
  getAllTelemetry,
  getMe,
  getServiceErrors,
  getServiceVersions,
  getToken,
  listLessons,
  SERVICE_URLS,
  type AdRevenueReport,
  type FlagSpec,
  type Lesson,
  type ServiceVersion,
  type TelemetryError,
  type TelemetrySummary,
  type BugReportRow,
  type VoucherRecord,
} from "../lib/api";
import { SALES_DEMO_COURSES } from "../lib/salesDemo";
import MascotPreviewPanel from "../components/MascotPreviewPanel";
import { EyeIcon } from "../components/EyeIcon";
import { APP_VERSION } from "../lib/version";

type Insights = Awaited<ReturnType<typeof adminSurveyInsights>>;

function worstP95(t: TelemetrySummary): number {
  const routes = t.routes ?? {};
  let m = 0;
  for (const r of Object.values(routes)) m = Math.max(m, r.p95_ms);
  return Math.round(m);
}

const CATEGORY_LABELS: Record<string, string> = {
  engagement: "Engagement & Feedback",
  sales_demo: "Sales Demo",
  data: "Data & Data Mining",
  access: "Access & User Levels",
  monetization: "Monetization",
  ai: "AI Behavior",
  ux: "UX Experiments",
  ops: "Operations (kill-switches)",
};

// ---------------------------------------------------------------------------
// CoursePicker — searchable multi-select for sales_demo.featured_courses
// ---------------------------------------------------------------------------

function CoursePicker({
  value,
  onChange,
}: {
  value: string[];
  onChange: (ids: string[]) => void;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [allLessons, setAllLessons] = useState<Lesson[] | null>(null);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropRef = useRef<HTMLDivElement>(null);

  async function loadOnce() {
    if (allLessons !== null || loading) return;
    setLoading(true);
    try { setAllLessons(await listLessons()); }
    catch { setAllLessons([]); }
    finally { setLoading(false); }
  }

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (!dropRef.current?.contains(e.target as Node) &&
          !inputRef.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const q = query.trim().toLowerCase();
  const candidates = (allLessons ?? []).filter((l) => !value.includes(l.lesson_id));
  const filtered = q
    ? candidates.filter(
        (l) => l.title.toLowerCase().includes(q) || l.lesson_id.toLowerCase().includes(q)
      ).slice(0, 20)
    : [];

  function displayName(id: string): string {
    const lesson = allLessons?.find((l) => l.lesson_id === id);
    if (lesson) return lesson.title;
    return SALES_DEMO_COURSES.find((c) => c.id === id)?.title ?? id;
  }

  function add(id: string) {
    onChange([...value, id]);
    setQuery("");
    inputRef.current?.focus();
  }

  function remove(id: string) {
    onChange(value.filter((v) => v !== id));
  }

  return (
    <div style={{ width: "100%", maxWidth: 560 }}>
      {/* Selected course chips */}
      {value.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
          {value.map((id) => (
            <span
              key={id}
              style={{
                display: "inline-flex", alignItems: "center", gap: 5,
                padding: "4px 10px 4px 12px", borderRadius: 999,
                background: "#e0e7ff", color: "#3730a3",
                fontSize: 13, fontWeight: 600, maxWidth: 300,
              }}
              title={id}
            >
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {displayName(id)}
              </span>
              <button
                type="button"
                onClick={() => remove(id)}
                aria-label={`Remove ${displayName(id)}`}
                style={{
                  background: "none", border: "none", cursor: "pointer",
                  color: "#4338ca", fontSize: 16, lineHeight: 1, padding: 0,
                  flexShrink: 0,
                }}
              >×</button>
            </span>
          ))}
        </div>
      )}

      {/* Search input */}
      <div style={{ position: "relative" }}>
        <input
          ref={inputRef}
          type="text"
          placeholder={`Search courses to add… (${(allLessons ?? []).length || "1000+"} available)`}
          value={query}
          onFocus={() => { setOpen(true); void loadOnce(); }}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); void loadOnce(); }}
          onKeyDown={(e) => {
            if (e.key === "Escape") { setQuery(""); setOpen(false); }
            if (e.key === "Enter" && filtered.length === 1) add(filtered[0].lesson_id);
          }}
          style={{
            width: "100%", padding: "8px 12px", boxSizing: "border-box",
            border: "1px solid #d1d5db", borderRadius: 8, fontSize: 14,
            background: "#fafafa",
          }}
        />
        {loading && (
          <span style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)", fontSize: 12, color: "#9ca3af" }}>
            Loading…
          </span>
        )}
      </div>

      {/* Dropdown */}
      {open && query && (
        <div
          ref={dropRef}
          style={{
            position: "absolute", zIndex: 80,
            background: "#fff", border: "1px solid #e5e7eb", borderRadius: 10,
            boxShadow: "0 6px 24px rgba(0,0,0,.12)", maxHeight: 300,
            overflowY: "auto", marginTop: 4, width: "min(560px, 90vw)",
          }}
        >
          {filtered.length === 0 ? (
            <div style={{ padding: "12px 16px", fontSize: 13, color: "#6b7280" }}>
              {loading ? "Loading courses…" : "No matching courses. Try a different keyword."}
            </div>
          ) : (
            <>
              {filtered.map((l) => (
                <button
                  key={l.lesson_id}
                  type="button"
                  onClick={() => add(l.lesson_id)}
                  style={{
                    display: "block", width: "100%", padding: "10px 16px",
                    textAlign: "left", background: "none", border: "none",
                    borderBottom: "1px solid #f3f4f6", cursor: "pointer",
                  }}
                  onMouseEnter={(e) => { (e.currentTarget.style.background = "#f0f5ff"); }}
                  onMouseLeave={(e) => { (e.currentTarget.style.background = "none"); }}
                >
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{l.title}</div>
                  <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 2 }}>{l.lesson_id}</div>
                </button>
              ))}
              {candidates.length > 20 && (
                <div style={{ padding: "8px 16px", fontSize: 12, color: "#9ca3af", borderTop: "1px solid #e5e7eb" }}>
                  Showing top 20 of {candidates.length} matches — refine your search for more.
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default function AdminPage() {
  const [secret, setSecret] = useState("");
  const [showSecret, setShowSecret] = useState(false);
  const [flags, setFlags] = useState<FlagSpec[]>([]);
  const [authed, setAuthed] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string>("");
  const [insights, setInsights] = useState<Insights | null>(null);
  const [versions, setVersions] = useState<ServiceVersion[] | null>(null);
  const [telemetry, setTelemetry] = useState<TelemetrySummary[] | null>(null);
  const [errorsFor, setErrorsFor] = useState<string>("");
  const [svcErrors, setSvcErrors] = useState<TelemetryError[]>([]);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [readinessSummary, setReadinessSummary] = useState<{
    count?: number;
    audience?: Record<string, unknown>;
    learners?: Array<Record<string, unknown>>;
  } | null>(null);
  const [adRevenue, setAdRevenue] = useState<AdRevenueReport | null>(null);
  const [bugReports, setBugReports] = useState<BugReportRow[] | null>(null);

  // Voucher management
  const [vouchers, setVouchers] = useState<VoucherRecord[] | null>(null);
  const [voucherBusy, setVoucherBusy] = useState(false);
  const [voucherError, setVoucherError] = useState("");
  const [newVoucher, setNewVoucher] = useState({ code: "", kind: "coupon", value: 0, max_uses: 1, expires_days: "", class_id: "", note: "" });

  // Logged-in operator admins skip the secret prompt (BFF uses server ADMIN_SECRET).
  useEffect(() => {
    if (!getToken()) return;
    getMe()
      .then(async (me) => {
        if (!me.is_admin) return;
        try {
          const f = await adminListFlagsSession();
          setFlags(f);
          setAuthed(true);
        } catch {
          /* fall back to manual secret entry */
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (authed) getServiceVersions().then(setVersions).catch(() => setVersions([]));
  }, [authed]);

  useEffect(() => {
    if (!authed) return;
    const load = () => {
      getAllTelemetry().then(setTelemetry).catch(() => setTelemetry([]));
      getAdRevenue().then(setAdRevenue).catch(() => setAdRevenue(null));
    };
    load();
    if (!autoRefresh) return;
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [authed, autoRefresh]);

  async function viewErrors(name: string) {
    setErrorsFor(name);
    const url = SERVICE_URLS[name];
    setSvcErrors(url ? await getServiceErrors(name, url, 25) : []);
  }

  async function load(s: string) {
    setError("");
    try {
      // Prefer the operator-admin session (server-side secret, no typing needed)
      // when signed in; fall back to the manually entered admin secret.
      let f: FlagSpec[];
      if (getToken()) {
        try {
          f = await adminListFlagsSession();
        } catch {
          f = await adminListFlags(s);
        }
      } else {
        f = await adminListFlags(s);
      }
      setFlags(f);
      setAuthed(true);
    } catch (e) {
      setError(
        "Could not load flags. Sign in as an operator admin (admin@salareen.com), or enter the correct admin secret."
      );
      setAuthed(false);
      void e;
    }
  }

  async function loadInsights() {
    try {
      setInsights(await adminSurveyInsights(secret));
    } catch (e) {
      setError(`Could not load survey insights: ${String(e)}`);
    }
  }

  async function loadBugReports() {
    try {
      const body = await adminListBugReports(secret, 40);
      setBugReports(body.reports ?? []);
    } catch (e) {
      setError(`Could not load bug reports: ${String(e)}`);
    }
  }

  async function loadReadiness() {
    try {
      const headers: Record<string, string> = { Accept: "application/json" };
      if (secret) headers["X-Admin-Secret"] = secret;
      if (getToken()) headers.Authorization = `Bearer ${getToken()}`;
      const res = await fetch(`${SERVICE_URLS.identity}/admin/readiness/summary`, {
        headers,
        cache: "no-store",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setReadinessSummary(await res.json());
    } catch (e) {
      setError(`Could not load readiness summary: ${String(e)}`);
    }
  }

  async function patch(key: string, p: Parameters<typeof adminSetFlag>[2]) {
    setBusy(key);
    try {
      // Prefer the operator-admin session (BFF) when signed in, but fall back to
      // the direct memory path with the entered secret if the BFF is unavailable
      // (e.g. expired session, or a web build without the /api/admin route).
      let updated: FlagSpec;
      if (getToken()) {
        try {
          updated = await adminSetFlagSession(key, p);
        } catch {
          updated = await adminSetFlag(secret, key, p);
        }
      } else {
        updated = await adminSetFlag(secret, key, p);
      }
      setFlags((prev) => prev.map((f) => (f.key === key ? updated : f)));
    } catch (e) {
      setError(
        `Update failed for ${key}. If your session expired, enter the admin secret (88888888) above and try again. (${String(e)})`,
      );
    } finally {
      setBusy("");
    }
  }

  if (!authed) {
    return (
      <main style={{ maxWidth: 480, margin: "0 auto", padding: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 4 }}>
          <h1 style={{ margin: 0 }}>Admin · Feature Flags</h1>
          <a href="/admin/presence" style={{ marginLeft: "auto", background: "#0369a1", color: "#fff", borderRadius: 8, padding: "7px 16px", fontSize: 13, fontWeight: 700, textDecoration: "none" }}>
            📡 Live Presence
          </a>
        </div>
        <p style={{ color: "#666" }}>
          Sign in as an operator admin account (e.g. admin@salareen.com) to manage flags
          automatically — no secret needed. Otherwise enter the administrative secret below.
        </p>
        <span style={{ position: "relative", display: "block", marginTop: 8 }}>
          <input
            type={showSecret ? "text" : "password"} placeholder="Admin secret" value={secret}
            onChange={(e) => setSecret(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load(secret)}
            style={{ width: "100%", padding: 10, paddingRight: 56, boxSizing: "border-box" }}
          />
          <button type="button" onClick={() => setShowSecret((s) => !s)}
            aria-label={showSecret ? "Hide admin secret" : "Show admin secret"}
            aria-pressed={showSecret}
            title={showSecret ? "Hide admin secret" : "Show admin secret"}
            style={{
              position: "absolute", right: 4, top: 0, bottom: 0,
              display: "flex", alignItems: "center", justifyContent: "center",
              width: 48, border: 0, background: "transparent",
              cursor: "pointer", color: "#9aa4b2",
            }}>
            <EyeIcon off={showSecret} size={26} />
          </button>
        </span>
        <button onClick={() => load(secret)}
          style={{ marginTop: 12, padding: "8px 18px", background: "#111", color: "#fff", border: 0, borderRadius: 6, cursor: "pointer" }}>
          Unlock
        </button>
        {error && <p style={{ color: "#b00", marginTop: 10 }}>{error}</p>}
      </main>
    );
  }

  const byCat: Record<string, FlagSpec[]> = {};
  for (const f of flags) (byCat[f.category] ??= []).push(f);

  return (
    <main style={{ maxWidth: 920, margin: "0 auto", padding: 24 }}>
      <h1>Admin · Console</h1>
      <p style={{ color: "#666" }}>
        Toggle features, run percentage rollouts, target membership tiers. Changes apply immediately.
      </p>
      {error && <p style={{ color: "#b00" }}>{error}</p>}

      <MascotPreviewPanel flags={flags} onPatch={patch} busy={busy} />

      <section style={{ marginTop: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, borderBottom: "2px solid #eee", paddingBottom: 6 }}>
          <h2 style={{ fontSize: 18, margin: 0, flex: 1 }}>Audience readiness (XR / Theodore)</h2>
          <button
            type="button"
            onClick={() => void loadReadiness()}
            style={{ padding: "6px 12px", cursor: "pointer" }}
          >
            Refresh
          </button>
        </div>
        <p style={{ fontSize: 13, color: "#666" }}>
          Composite readiness + dimensions for learners Theodore adapts to. Peer scores stay
          private; this view is admin-only.
        </p>
        {readinessSummary ? (
          <div style={{ fontSize: 14 }}>
            <p>
              Learners: <strong>{readinessSummary.count ?? 0}</strong>
              {readinessSummary.audience && (
                <>
                  {" "}· mean readiness{" "}
                  <strong>{String((readinessSummary.audience as { mean_readiness?: number }).mean_readiness ?? "—")}</strong>
                </>
              )}
            </p>
            <pre style={{ background: "#f7f7f7", padding: 12, overflow: "auto", fontSize: 12 }}>
              {JSON.stringify(readinessSummary.audience ?? {}, null, 2)}
            </pre>
            <details>
              <summary>Per-learner snapshots (up to 100)</summary>
              <pre style={{ background: "#f7f7f7", padding: 12, overflow: "auto", fontSize: 11 }}>
                {JSON.stringify(readinessSummary.learners ?? [], null, 2)}
              </pre>
            </details>
          </div>
        ) : (
          <p style={{ color: "#666", fontSize: 13 }}>Click Refresh to load readiness aggregates from identity.</p>
        )}
      </section>

      <section style={{ marginTop: 16 }}>
        <h2 style={{ fontSize: 18, borderBottom: "2px solid #eee", paddingBottom: 6 }}>
          System &amp; Versions
        </h2>
        <p style={{ fontSize: 13, color: "#666" }}>
          Web app <code>v{APP_VERSION}</code>. Each service also reports <code>/version</code> and
          a <code>/__meta</code> route index for automation.
        </p>
        {(() => {
          const reachable = (versions ?? []).filter((v) => v.reachable);
          const distinct = new Set(reachable.map((v) => v.version));
          return distinct.size > 1 ? (
            <p style={{ color: "#b45309" }}>⚠ Version mismatch across services: {[...distinct].join(", ")}</p>
          ) : reachable.length > 0 ? (
            <p style={{ color: "#16a34a" }}>✓ All reachable services on the same version.</p>
          ) : null;
        })()}
        <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 14 }}>
          <thead>
            <tr style={{ textAlign: "left", background: "#f7f7f7" }}>
              <th style={{ padding: 6 }}>Service</th><th style={{ padding: 6 }}>Status</th>
              <th style={{ padding: 6 }}>Version</th><th style={{ padding: 6 }}>API</th>
              <th style={{ padding: 6 }}>Mode</th><th style={{ padding: 6 }}>Git</th>
            </tr>
          </thead>
          <tbody>
            <tr style={{ borderTop: "1px solid #eee" }}>
              <td style={{ padding: 6 }}>web</td>
              <td style={{ padding: 6, color: "#16a34a" }}>● up</td>
              <td style={{ padding: 6 }}><code>{APP_VERSION}</code></td>
              <td style={{ padding: 6 }}>—</td><td style={{ padding: 6 }}>—</td><td style={{ padding: 6 }}>—</td>
            </tr>
            {(versions ?? []).map((v) => (
              <tr key={v.service} style={{ borderTop: "1px solid #eee" }}>
                <td style={{ padding: 6 }}>{v.service}</td>
                <td style={{ padding: 6, color: v.reachable ? "#16a34a" : "#b00" }}>
                  {v.reachable ? "● up" : "○ down"}
                </td>
                <td style={{ padding: 6 }}>{v.version ? <code>{v.version}</code> : "—"}</td>
                <td style={{ padding: 6 }}>{v.api_version ?? "—"}</td>
                <td style={{ padding: 6 }}>{v.deploy_mode ?? "—"}</td>
                <td style={{ padding: 6 }}>{v.git_sha || "—"}</td>
              </tr>
            ))}
            {versions === null && (
              <tr><td colSpan={6} style={{ padding: 6, color: "#666" }}>Loading service versions…</td></tr>
            )}
          </tbody>
        </table>
      </section>

      <section style={{ marginTop: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, borderBottom: "2px solid #eee", paddingBottom: 6 }}>
          <h2 style={{ fontSize: 18, margin: 0, flex: 1 }}>Observability &amp; Telemetry</h2>
          <label style={{ fontSize: 13 }}>
            <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} />
            &nbsp;Auto-refresh (5s)
          </label>
          <button onClick={() => getAllTelemetry().then(setTelemetry)} style={{ padding: "4px 12px", cursor: "pointer" }}>
            Refresh
          </button>
        </div>
        <p style={{ fontSize: 13, color: "#666" }}>
          Per-service performance, memory and error telemetry for root-cause analysis.
          Each service also exposes a Prometheus <code>/metrics</code> endpoint for cloud scraping.
        </p>
        <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 14 }}>
          <thead>
            <tr style={{ textAlign: "left", background: "#f7f7f7" }}>
              <th style={{ padding: 6 }}>Service</th><th style={{ padding: 6 }}>Mem (MB)</th>
              <th style={{ padding: 6 }}>Threads</th><th style={{ padding: 6 }}>Uptime</th>
              <th style={{ padding: 6 }}>Requests</th><th style={{ padding: 6 }}>Err rate</th>
              <th style={{ padding: 6 }}>Worst p95</th><th style={{ padding: 6 }}>In-flight</th>
              <th style={{ padding: 6 }}>Export</th><th style={{ padding: 6 }}>Errors</th>
            </tr>
          </thead>
          <tbody>
            {(telemetry ?? []).map((t) => {
              const errRate = t.totals?.error_rate ?? 0;
              return (
                <tr key={t.service} style={{ borderTop: "1px solid #eee" }}>
                  <td style={{ padding: 6 }}>{t.service}{!t.reachable && " (down)"}</td>
                  <td style={{ padding: 6 }}>{t.process?.rss_mb ?? "—"}</td>
                  <td style={{ padding: 6 }}>{t.process?.threads ?? "—"}</td>
                  <td style={{ padding: 6 }}>{t.uptime_s != null ? `${Math.round(t.uptime_s)}s` : "—"}</td>
                  <td style={{ padding: 6 }}>{t.totals?.requests ?? "—"}</td>
                  <td style={{ padding: 6, color: errRate > 0 ? "#b00" : "#16a34a" }}>
                    {t.reachable ? `${(errRate * 100).toFixed(1)}%` : "—"}
                  </td>
                  <td style={{ padding: 6 }}>{t.reachable ? `${worstP95(t)} ms` : "—"}</td>
                  <td style={{ padding: 6 }}>{t.totals?.inflight ?? "—"}</td>
                  <td style={{ padding: 6, fontSize: 12 }}>
                    {t.exporters ? `${t.exporters.sentry ? "sentry " : ""}${t.exporters.otlp ? "otlp" : ""}`.trim() || "—" : "—"}
                  </td>
                  <td style={{ padding: 6 }}>
                    {t.reachable
                      ? <button onClick={() => viewErrors(t.service)} style={{ fontSize: 12, padding: "2px 8px", cursor: "pointer" }}>
                          {t.error_count ?? 0} ▸
                        </button>
                      : "—"}
                  </td>
                </tr>
              );
            })}
            {telemetry === null && (
              <tr><td colSpan={10} style={{ padding: 6, color: "#666" }}>Loading telemetry…</td></tr>
            )}
          </tbody>
        </table>

        {errorsFor && (
          <div style={{ marginTop: 12 }}>
            <h4 style={{ marginBottom: 6 }}>Recent errors — {errorsFor}
              <button onClick={() => { setErrorsFor(""); setSvcErrors([]); }}
                style={{ marginLeft: 10, fontSize: 12, cursor: "pointer" }}>close</button>
            </h4>
            {svcErrors.length === 0 ? (
              <p className="muted" style={{ color: "#16a34a" }}>No recent errors. 🎉</p>
            ) : (
              svcErrors.map((e, i) => (
                <details key={i} style={{ border: "1px solid #eee", borderRadius: 6, padding: 8, marginBottom: 6 }}>
                  <summary style={{ cursor: "pointer" }}>
                    <code style={{ color: "#b00" }}>{e.type}</code> · {e.method} {e.route} · {e.status}
                    {" "}· {new Date(e.ts * 1000).toLocaleTimeString()} · req {e.request_id}
                  </summary>
                  <pre style={{ background: "#0b1020", color: "#fca5a5", padding: 10, borderRadius: 6,
                    fontSize: 12, overflowX: "auto", marginTop: 8 }}>{e.message}{"\n\n"}{e.traceback}</pre>
                </details>
              ))
            )}
          </div>
        )}
      </section>

      <section style={{ marginTop: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, borderBottom: "2px solid #eee", paddingBottom: 6 }}>
          <h2 style={{ fontSize: 18, margin: 0, flex: 1 }}>Ad Revenue (monetization)</h2>
          <button onClick={() => getAdRevenue().then(setAdRevenue).catch(() => {})} style={{ padding: "4px 12px", cursor: "pointer" }}>
            Refresh
          </button>
        </div>
        <p style={{ fontSize: 13, color: "#666" }}>
          Estimated ad earnings from impression/click beacons (web + mobile). Network of record:{" "}
          <code>{adRevenue?.active_network ?? "—"}</code>. Real payout is reconciled in the ad
          network&rsquo;s own dashboard; this is our in-app estimate + funnel.
        </p>
        {adRevenue ? (
          <>
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap", margin: "8px 0 14px" }}>
              {([
                ["Revenue (est.)", `$${adRevenue.totals.revenue_usd.toFixed(4)}`],
                ["Impressions", adRevenue.totals.impressions.toLocaleString()],
                ["Clicks", adRevenue.totals.clicks.toLocaleString()],
                ["CTR", `${(adRevenue.totals.ctr * 100).toFixed(2)}%`],
                ["eCPM", `$${adRevenue.totals.ecpm_usd.toFixed(2)}`],
              ] as const).map(([label, val]) => (
                <div key={label} style={{ background: "#f7f7f7", borderRadius: 8, padding: "10px 16px", minWidth: 110 }}>
                  <div style={{ fontSize: 12, color: "#666" }}>{label}</div>
                  <div style={{ fontSize: 20, fontWeight: 700 }}>{val}</div>
                </div>
              ))}
            </div>
            {adRevenue.by_placement.length > 0 ? (
              <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 14 }}>
                <thead>
                  <tr style={{ textAlign: "left", background: "#f7f7f7" }}>
                    <th style={{ padding: 6 }}>Placement</th><th style={{ padding: 6 }}>Impr.</th>
                    <th style={{ padding: 6 }}>Clicks</th><th style={{ padding: 6 }}>CTR</th>
                    <th style={{ padding: 6 }}>eCPM</th><th style={{ padding: 6 }}>Revenue (est.)</th>
                  </tr>
                </thead>
                <tbody>
                  {adRevenue.by_placement.map((r) => (
                    <tr key={r.key} style={{ borderTop: "1px solid #eee" }}>
                      <td style={{ padding: 6 }}><code>{r.key}</code></td>
                      <td style={{ padding: 6 }}>{r.impressions.toLocaleString()}</td>
                      <td style={{ padding: 6 }}>{r.clicks.toLocaleString()}</td>
                      <td style={{ padding: 6 }}>{(r.ctr * 100).toFixed(2)}%</td>
                      <td style={{ padding: 6 }}>${r.ecpm_usd.toFixed(2)}</td>
                      <td style={{ padding: 6 }}>${r.revenue_usd.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="muted" style={{ fontSize: 13 }}>
                No ad events yet. Ads show for Standard/free tiers — open <code>/watch</code>, the home feed,
                <code>/class</code> or Drive Mode on a basic account (or append <code>?ads=1</code> to force ads on any account).
              </p>
            )}
          </>
        ) : (
          <p style={{ color: "#666" }}>Loading ad revenue…</p>
        )}
      </section>

      {Object.entries(byCat).map(([cat, items]) => (
        <section key={cat} style={{ marginTop: 24 }}>
          <h2 style={{ fontSize: 18, borderBottom: "2px solid #eee", paddingBottom: 6 }}>
            {CATEGORY_LABELS[cat] ?? cat}
          </h2>
          {items.map((f) => {
            const isJson = f.type === "json";
            return (
              <div key={f.key} style={{
                display: "flex", flexDirection: isJson ? "column" : "row",
                gap: isJson ? 10 : 14,
                alignItems: isJson ? "flex-start" : "center",
                padding: "10px 0", borderBottom: "1px solid #f3f3f3",
                opacity: busy === f.key ? 0.5 : 1,
              }}>
                <div style={{ flex: 1 }}>
                  <code style={{ fontWeight: 600 }}>{f.key}</code>
                  {f.admin_only && <span style={{ marginLeft: 8, fontSize: 11, background: "#fee2e2",
                    color: "#991b1b", padding: "1px 6px", borderRadius: 4 }}>hidden</span>}
                  <div style={{ fontSize: 13, color: "#666" }}>{f.description}</div>
                </div>

                {f.type === "bool" && (
                  <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <input type="checkbox" checked={Boolean(f.value)}
                      onChange={(e) => patch(f.key, { enabled: true, value: e.target.checked })} />
                    {f.value ? "On" : "Off"}
                  </label>
                )}

                {f.type === "percent" && (
                  <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 180 }}>
                    <input type="range" min={0} max={100}
                      defaultValue={f.rollout_pct ?? Number(f.value) ?? 0}
                      onMouseUp={(e) => patch(f.key, { enabled: true, rollout_pct: Number((e.target as HTMLInputElement).value) })} />
                    <span style={{ fontSize: 12, width: 36 }}>{f.rollout_pct ?? f.value as number}%</span>
                  </div>
                )}

                {f.type === "string" && (
                  <select value={String(f.value)}
                    onChange={(e) => patch(f.key, { enabled: true, value: e.target.value })}
                    style={{ padding: 6 }}>
                    {f.options.map((o) => <option key={o} value={o}>{o}</option>)}
                  </select>
                )}

                {f.type === "int" && (
                  <input type="number" defaultValue={Number(f.value)}
                    onBlur={(e) => patch(f.key, { enabled: true, value: Number(e.target.value) })}
                    style={{ width: 80, padding: 6 }} />
                )}

                {isJson && (
                  <div style={{ position: "relative", width: "100%" }}>
                    <CoursePicker
                      value={Array.isArray(f.value) ? (f.value as string[]) : []}
                      onChange={(ids) => patch(f.key, { enabled: true, value: ids })}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </section>
      ))}

      <section style={{ marginTop: 32 }}>
        <h2 style={{ fontSize: 18, borderBottom: "2px solid #eee", paddingBottom: 6 }}>
          User bug reports (free QA)
        </h2>
        <p style={{ fontSize: 13, color: "#666" }}>
          In-app submissions from web/mobile with screenshots, client logs, and a route snapshot.
          Attachments are stored on the memory service under <code>AOEP_BUG_REPORT_DIR</code>.
        </p>
        <button onClick={() => void loadBugReports()}
          style={{ padding: "6px 14px", marginTop: 8, cursor: "pointer" }}>
          Load bug reports
        </button>
        {bugReports && (
          <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 13, marginTop: 12 }}>
            <thead>
              <tr style={{ textAlign: "left", background: "#f7f7f7" }}>
                <th style={{ padding: 6 }}>When</th>
                <th style={{ padding: 6 }}>Platform</th>
                <th style={{ padding: 6 }}>Screen</th>
                <th style={{ padding: 6 }}>Category</th>
                <th style={{ padding: 6 }}>Description</th>
                <th style={{ padding: 6 }}>Logs</th>
                <th style={{ padding: 6 }}>Shots</th>
                <th style={{ padding: 6 }}>Delivery</th>
              </tr>
            </thead>
            <tbody>
              {bugReports.map((r) => (
                <tr key={r.id} style={{ borderTop: "1px solid #eee", verticalAlign: "top" }}>
                  <td style={{ padding: 6, whiteSpace: "nowrap" }}>
                    {new Date(r.created_at * 1000).toLocaleString()}
                    <div><code>{r.id}</code></div>
                  </td>
                  <td style={{ padding: 6 }}>{r.platform} v{r.app_version}</td>
                  <td style={{ padding: 6 }}><code>{r.screen || "—"}</code></td>
                  <td style={{ padding: 6 }}>{r.category}</td>
                  <td style={{ padding: 6, maxWidth: 280 }}>{r.description}</td>
                  <td style={{ padding: 6, minWidth: 90 }}>
                    <div>{r.logs?.length ?? 0} events</div>
                    <details>
                      <summary style={{ cursor: "pointer" }}>Diagnostics</summary>
                      <pre style={{
                        maxWidth: 520, maxHeight: 320, overflow: "auto",
                        whiteSpace: "pre-wrap", fontSize: 11,
                      }}>
                        {JSON.stringify({ snapshot: r.snapshot, logs: r.logs }, null, 2)}
                      </pre>
                    </details>
                  </td>
                  <td style={{ padding: 6 }}>
                    {(r.attachments ?? []).map((name) => (
                      <div key={name}>
                        <a
                          href={`${SERVICE_URLS.memory}/admin/bugs/${encodeURIComponent(r.id)}/attachments/${encodeURIComponent(name)}`}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => {
                            e.preventDefault();
                            void fetch(
                              `${SERVICE_URLS.memory}/admin/bugs/${encodeURIComponent(r.id)}/attachments/${encodeURIComponent(name)}`,
                              { headers: { "X-Admin-Secret": secret } },
                            )
                              .then((resp) => resp.blob())
                              .then((blob) => {
                                const url = URL.createObjectURL(blob);
                                window.open(url, "_blank", "noopener,noreferrer");
                              })
                              .catch(() => undefined);
                          }}
                        >
                          {name}
                        </a>
                      </div>
                    ))}
                  </td>
                  <td style={{ padding: 6 }}>
                    {r.private_issue_url ? (
                      <div>
                        <a href={r.private_issue_url} target="_blank" rel="noreferrer">
                          Private issue + evidence ↗
                        </a>
                      </div>
                    ) : null}
                    {r.public_issue_url ? (
                      <div>
                        <a href={r.public_issue_url} target="_blank" rel="noreferrer">
                          Public redacted issue ↗
                        </a>
                      </div>
                    ) : null}
                    {!r.private_issue_url && !r.public_issue_url && r.external_url ? (
                      <a href={r.external_url} target="_blank" rel="noreferrer">
                        GitHub issue ↗
                      </a>
                    ) : null}
                    {r.delivery_error ? (
                      <span title={r.delivery_error}>QA inbox (GitHub retry needed)</span>
                    ) : !r.private_issue_url && !r.public_issue_url && !r.external_url ? (
                      <span>{r.destination || "QA inbox"}</span>
                    ) : null}
                  </td>
                </tr>
              ))}
              {bugReports.length === 0 && (
                <tr><td colSpan={8} style={{ padding: 8, color: "#666" }}>No reports yet.</td></tr>
              )}
            </tbody>
          </table>
        )}
      </section>

      <section style={{ marginTop: 32 }}>
        <h2 style={{ fontSize: 18, borderBottom: "2px solid #eee", paddingBottom: 6 }}>
          Survey Insights (multi-dimensional data mining)
        </h2>
        <button onClick={loadInsights}
          style={{ padding: "6px 14px", marginTop: 8, cursor: "pointer" }}>
          Load insights
        </button>
        {insights && (
          <div style={{ marginTop: 12 }}>
            <p>
              <strong>{insights.datamart.total_responses}</strong> responses ·
              data-mining flag: {insights.data_mining_enabled ? "on" : "off"}
            </p>
            <h4 style={{ marginBottom: 4 }}>By course × class type × rating</h4>
            <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 14 }}>
              <thead>
                <tr style={{ textAlign: "left", background: "#f7f7f7" }}>
                  <th style={{ padding: 6 }}>Course</th><th style={{ padding: 6 }}>Class type</th>
                  <th style={{ padding: 6 }}>Rating bucket</th><th style={{ padding: 6 }}>Responses</th>
                  <th style={{ padding: 6 }}>Avg</th>
                </tr>
              </thead>
              <tbody>
                {insights.datamart.cells.map((c, i) => (
                  <tr key={i} style={{ borderTop: "1px solid #eee" }}>
                    <td style={{ padding: 6 }}>{c.course_id}</td>
                    <td style={{ padding: 6 }}>{c.class_type}</td>
                    <td style={{ padding: 6 }}>{c.rating_bucket}</td>
                    <td style={{ padding: 6 }}>{c.responses}</td>
                    <td style={{ padding: 6 }}>{c.avg_overall}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {insights.datamart.top_suggestions.length > 0 && (
              <p style={{ marginTop: 10 }}>
                <strong>Mined suggestion themes:</strong>{" "}
                {insights.datamart.top_suggestions.map((t) => `${t.term} (${t.count})`).join(", ")}
              </p>
            )}
          </div>
        )}
      </section>

      {/* ── Voucher Management ──────────────────────────────────────────────── */}
      <section style={{ marginTop: 32 }}>
        <h2 style={{ fontSize: 18, borderBottom: "2px solid #eee", paddingBottom: 6 }}>
          Voucher / Coupon / Gift Code Management
        </h2>

        {/* Create new voucher form */}
        <div style={{ background: "#f8fafc", borderRadius: 10, padding: 20, marginTop: 16, marginBottom: 20 }}>
          <h3 style={{ margin: "0 0 12px", fontSize: 15 }}>Create New Voucher</h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 10, marginBottom: 12 }}>
            <div>
              <label style={{ fontSize: 12, fontWeight: 700, display: "block", marginBottom: 4 }}>Code *</label>
              <input value={newVoucher.code} onChange={(e) => setNewVoucher((v) => ({ ...v, code: e.target.value.toUpperCase() }))}
                placeholder="SAVE20" style={{ width: "100%", padding: "8px 10px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 13, boxSizing: "border-box" }} />
            </div>
            <div>
              <label style={{ fontSize: 12, fontWeight: 700, display: "block", marginBottom: 4 }}>Kind</label>
              <select value={newVoucher.kind} onChange={(e) => setNewVoucher((v) => ({ ...v, kind: e.target.value }))}
                style={{ width: "100%", padding: "8px 10px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 13, boxSizing: "border-box" }}>
                <option value="coupon">Coupon (% off)</option>
                <option value="gift_code">Gift Code ($)</option>
                <option value="free_pass">Free Pass</option>
              </select>
            </div>
            <div>
              <label style={{ fontSize: 12, fontWeight: 700, display: "block", marginBottom: 4 }}>
                Value {newVoucher.kind === "coupon" ? "(% off)" : newVoucher.kind === "gift_code" ? "($)" : "(ignored)"}
              </label>
              <input type="number" value={newVoucher.value} onChange={(e) => setNewVoucher((v) => ({ ...v, value: parseFloat(e.target.value) || 0 }))}
                min={0} style={{ width: "100%", padding: "8px 10px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 13, boxSizing: "border-box" }} />
            </div>
            <div>
              <label style={{ fontSize: 12, fontWeight: 700, display: "block", marginBottom: 4 }}>Max Uses (0=unlimited)</label>
              <input type="number" value={newVoucher.max_uses} onChange={(e) => setNewVoucher((v) => ({ ...v, max_uses: parseInt(e.target.value) || 1 }))}
                min={0} style={{ width: "100%", padding: "8px 10px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 13, boxSizing: "border-box" }} />
            </div>
            <div>
              <label style={{ fontSize: 12, fontWeight: 700, display: "block", marginBottom: 4 }}>Expires in Days (blank=never)</label>
              <input type="number" value={newVoucher.expires_days} onChange={(e) => setNewVoucher((v) => ({ ...v, expires_days: e.target.value }))}
                min={1} placeholder="e.g. 30" style={{ width: "100%", padding: "8px 10px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 13, boxSizing: "border-box" }} />
            </div>
            <div>
              <label style={{ fontSize: 12, fontWeight: 700, display: "block", marginBottom: 4 }}>Class ID (free_pass only)</label>
              <input value={newVoucher.class_id} onChange={(e) => setNewVoucher((v) => ({ ...v, class_id: e.target.value }))}
                placeholder="optional" style={{ width: "100%", padding: "8px 10px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 13, boxSizing: "border-box" }} />
            </div>
            <div style={{ gridColumn: "span 2" }}>
              <label style={{ fontSize: 12, fontWeight: 700, display: "block", marginBottom: 4 }}>Note / internal label</label>
              <input value={newVoucher.note} onChange={(e) => setNewVoucher((v) => ({ ...v, note: e.target.value }))}
                placeholder="e.g. promo for summer campaign" style={{ width: "100%", padding: "8px 10px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 13, boxSizing: "border-box" }} />
            </div>
          </div>
          {voucherError && <p style={{ color: "#dc2626", fontSize: 13, margin: "0 0 10px" }}>{voucherError}</p>}
          <button
            disabled={voucherBusy || !newVoucher.code.trim()}
            onClick={async () => {
              setVoucherBusy(true); setVoucherError("");
              try {
                await adminCreateVoucher({
                  code: newVoucher.code.trim(),
                  kind: newVoucher.kind,
                  value: newVoucher.value,
                  max_uses: newVoucher.max_uses,
                  expires_days: newVoucher.expires_days ? parseInt(newVoucher.expires_days) : null,
                  class_id: newVoucher.class_id.trim() || null,
                  note: newVoucher.note.trim(),
                });
                setNewVoucher({ code: "", kind: "coupon", value: 0, max_uses: 1, expires_days: "", class_id: "", note: "" });
                const res = await adminListVouchers();
                setVouchers(res.vouchers);
              } catch (e) {
                setVoucherError(e instanceof Error ? e.message : "Failed to create voucher");
              }
              setVoucherBusy(false);
            }}
            style={{ padding: "8px 20px", background: voucherBusy ? "#9ca3af" : "#6366f1", color: "#fff", border: "none", borderRadius: 8, fontWeight: 700, cursor: voucherBusy ? "default" : "pointer" }}>
            {voucherBusy ? "Creating..." : "Create Voucher"}
          </button>
        </div>

        {/* Existing vouchers table */}
        <button
          onClick={async () => { const res = await adminListVouchers(); setVouchers(res.vouchers); }}
          style={{ padding: "6px 14px", cursor: "pointer", marginBottom: 12 }}>
          Refresh Voucher List
        </button>
        {vouchers !== null && (
          <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 13 }}>
            <thead>
              <tr style={{ textAlign: "left", background: "#f7f7f7" }}>
                <th style={{ padding: 6 }}>Code</th>
                <th style={{ padding: 6 }}>Kind</th>
                <th style={{ padding: 6 }}>Value</th>
                <th style={{ padding: 6 }}>Uses</th>
                <th style={{ padding: 6 }}>Expires</th>
                <th style={{ padding: 6 }}>Class ID</th>
                <th style={{ padding: 6 }}>Note</th>
              </tr>
            </thead>
            <tbody>
              {vouchers.length === 0 && (
                <tr><td colSpan={7} style={{ padding: 8, color: "#666" }}>No vouchers yet.</td></tr>
              )}
              {vouchers.map((v) => (
                <tr key={v.code} style={{ borderTop: "1px solid #eee" }}>
                  <td style={{ padding: 6, fontWeight: 700, fontFamily: "monospace" }}>{v.code}</td>
                  <td style={{ padding: 6 }}>{v.kind}</td>
                  <td style={{ padding: 6 }}>
                    {v.kind === "coupon" ? `${v.value}%` : v.kind === "gift_code" ? `$${v.value.toFixed(2)}` : "—"}
                  </td>
                  <td style={{ padding: 6 }}>{v.uses} / {v.max_uses === 0 ? "∞" : v.max_uses}</td>
                  <td style={{ padding: 6 }}>
                    {v.expires_at ? new Date(v.expires_at * 1000).toLocaleDateString() : "Never"}
                  </td>
                  <td style={{ padding: 6 }}>{v.class_id || "—"}</td>
                  <td style={{ padding: 6 }}>{v.note || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
