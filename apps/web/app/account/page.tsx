"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  adminListAccounts,
  changePassword,
  clearToken,
  deleteAccount,
  createStudent,
  getMe,
  getPortfolio,
  getRewards,
  getToken,
  listStudents,
  startBillingCheckout,
  subscribeToPlan,
  setStudentMastery,
  getConsumerPlans,
  type Account,
  type ConsumerPlan,
  type Portfolio,
  type StudentProfile,
} from "../lib/api";
import { isAdminUnlocked } from "../lib/api";
import { COURSE_UNLOCK_PRICE_LABEL } from "../lib/courseStudio";
import { formatMonthlyPrice, orderedConsumerPlans } from "../lib/consumerPlansDisplay";
import { useFlag } from "../lib/flags";
import { OPEN_LEARNING_PROFILE_EVENT } from "../components/LearningProfileSurvey";
import { playIntro, INTRO_AUTOPLAY_KEY } from "../components/IntroSequence";
import { INTRO_VARIANTS } from "../lib/introAnimations";
import { useT } from "../lib/i18n";
import LanguagePicker from "../components/LanguagePicker";
// AvatarPicker (the grid of ~20 face thumbnails + the "realistic" style
// toggle) is intentionally NOT imported here. The user asked us to hide the
// avatar grid in profile settings because the current palette looked
// racially coded; the field stays in the schema so previously-chosen avatars
// still render elsewhere in the app, we just stop offering the chooser here.
// Replaced below with a neutral monogram built from the display name.

const STATUS_ORDER = ["paid", "in_progress", "enrolled", "saved", "passed", "failed"];

export default function AccountPage() {
  const { t } = useT();
  const consoleOn = useFlag<boolean>("access.educator_console", true);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [error, setError] = useState("");
  const [pwMsg, setPwMsg] = useState("");
  const [cur, setCur] = useState("");
  const [next, setNext] = useState("");
  const [loggedIn, setLoggedIn] = useState<boolean>(false);
  const [points, setPoints] = useState<number | null>(null);
  const [students, setStudents] = useState<StudentProfile[]>([]);
  const [newStudent, setNewStudent] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [adminUnlocked, setAdminUnlocked] = useState(false);
  const [showAdminTools, setShowAdminTools] = useState(false);
  const [allAccounts, setAllAccounts] = useState<Account[]>([]);
  const [primaryStudent, setPrimaryStudent] = useState<StudentProfile | null>(null);
  const [introAutoplay, setIntroAutoplay] = useState(true);
  const [membershipPlans, setMembershipPlans] = useState<ConsumerPlan[]>([]);

  useEffect(() => {
    try { setIntroAutoplay(localStorage.getItem(INTRO_AUTOPLAY_KEY) !== "off"); } catch { /* */ }
  }, []);

  function toggleIntroAutoplay(on: boolean) {
    setIntroAutoplay(on);
    try { localStorage.setItem(INTRO_AUTOPLAY_KEY, on ? "on" : "off"); } catch { /* */ }
  }

  async function refresh() {
    try {
      const [me, planCatalog] = await Promise.all([
        getMe(),
        getConsumerPlans().catch(() => ({} as Record<string, ConsumerPlan>)),
      ]);
      setMembershipPlans(orderedConsumerPlans(planCatalog));
      setIsAdmin(Boolean(me.is_admin));
      setAdminUnlocked(Boolean(me.is_admin) || isAdminUnlocked());
      if (me.is_admin) {
        try {
          setAllAccounts((await adminListAccounts()).accounts);
        } catch {
          setAllAccounts([]);
        }
      }
    } catch {
      setIsAdmin(false);
    }
    try {
      setPortfolio(await getPortfolio());
    } catch (e) {
      setError(String(e));
    }
    try {
      setPoints((await getRewards()).balance);
    } catch {
      setPoints(null);
    }
    try {
      const listed = (await listStudents()).students;
      setStudents(listed);
      setPrimaryStudent(listed[0] ?? null);
    } catch {
      setStudents([]);
      setPrimaryStudent(null);
    }
  }

  async function addStudent() {
    if (!newStudent.trim()) return;
    try {
      await createStudent(newStudent.trim());
      setNewStudent("");
      await refresh();
    } catch (e) {
      setError(String(e));
    }
  }

  async function bumpMastery(studentId: string) {
    const skill = window.prompt(t("account.promptSkill"));
    if (!skill) return;
    const valStr = window.prompt(t("account.promptMastery"), "0.3");
    if (valStr == null) return;
    try {
      await setStudentMastery(studentId, skill, parseFloat(valStr) || 0);
      await refresh();
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    setLoggedIn(Boolean(getToken()));
    if (getToken()) refresh();
    function onProfileSaved() {
      if (getToken()) refresh();
    }
    window.addEventListener("aoep-learning-profile-saved", onProfileSaved);
    return () => window.removeEventListener("aoep-learning-profile-saved", onProfileSaved);
  }, []);

  if (!loggedIn) {
    return (
      <main className="container">
        <h1>{t("account.title")}</h1>
        <div className="card">
          <p>
            {t("account.signInBefore")}{" "}
            <Link href="/login">{t("account.signIn")}</Link>{" "}
            {t("account.signInAfter")}
          </p>
        </div>
      </main>
    );
  }

  async function onTier(tier: string) {
    // Fix for the user-reported "membership upgrade is broken" bug:
    //
    // The old flow always called subscribeToPlan(tier). In cloud mode the
    // identity service's POST /membership/subscribe rejects paid tiers with
    // HTTP 402 "paid tiers require verified payment; complete checkout or
    // wait for billing sync" (see _self_serve_paid_tiers_allowed() — only
    // local/dev/sandbox mode lets the user upgrade without paying). The 402
    // surfaced to the user as a cryptic red error on the account page and
    // the tier never flipped, which is exactly what the user described.
    //
    // The onboarding step already did the right thing (startBillingCheckout
    // for paid tiers, selectOnboardingPlan for free). Mirror that here:
    //   - "free"             → direct subscribeToPlan("free")
    //   - everything else    → startBillingCheckout → redirect to session URL
    //                          (sandbox provider returns a Stripe-like URL
    //                          that confirms immediately; cloud sends through
    //                          the real payment provider's hosted checkout).
    setError("");
    try {
      if (!tier || tier === "free") {
        await subscribeToPlan("free");
        await refresh();
        return;
      }
      const me = await getMe();
      const session = await startBillingCheckout(me.id, tier);
      if (session.url && /^https?:\/\//i.test(session.url)) {
        window.location.href = session.url;
        return;
      }
      // No hosted-checkout URL means we are in sandbox mode where the backend
      // has already activated the subscription; just refresh to show the new
      // tier.
      await subscribeToPlan(tier).catch(() => undefined);
      await refresh();
    } catch (e) {
      setError(String(e));
    }
  }

  function formatNextBill(ts: number | null | undefined): string {
    if (!ts) return "";
    return new Date(ts * 1000).toLocaleDateString(undefined, {
      month: "short", day: "numeric", year: "numeric",
    });
  }

  async function onChangePassword(e: React.FormEvent) {
    e.preventDefault();
    setPwMsg("");
    try {
      await changePassword(cur, next);
      setPwMsg(t("account.passwordUpdated"));
      setCur(""); setNext("");
    } catch (err) {
      setPwMsg(String(err));
    }
  }

  function logout() {
    clearToken();
    setLoggedIn(false);
    setPortfolio(null);
  }

  return (
    <main className="container">
      <h1>{t("account.title")}</h1>
      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{error}</div></div>}

      {portfolio && (
        <>
          <div className="card">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <div>
                <strong>{portfolio.account.display_name}</strong>
                <div className="muted">{portfolio.account.email}</div>
              </div>
              <button onClick={logout}>{t("account.signOut")}</button>
            </div>
            {points != null && (
              <div className="muted" style={{ marginTop: 8 }}>
                {t("account.rewardPoints", { points })}{" "}
                <Link href="/rewards">{t("account.redeem")}</Link>
              </div>
            )}
          </div>


          {/* Avatar grid is intentionally hidden. The previous palette of
              illustrated faces could be read as stereotyping across skin tone /
              gender, and the user asked us to remove it while we rework the
              set. We still render a neutral monogram chip (first letter of
              the display name on a solid accent background) so the account
              card has an identity cue — the avatar_id field is preserved in
              the API so an older choice still shows up in group-class tiles
              or chat bubbles that read the account record. */}
          <div className="card" data-testid="avatar-monogram">
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <div
                aria-hidden="true"
                style={{
                  width: 72,
                  height: 72,
                  borderRadius: "50%",
                  background: "linear-gradient(135deg, #6366f1, #22d3ee)",
                  color: "#fff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontFamily: "'Fraunces', Georgia, serif",
                  fontWeight: 600,
                  fontSize: 32,
                  letterSpacing: 1,
                  boxShadow: "0 6px 16px rgba(99,102,241,0.25)",
                }}
              >
                {(portfolio.account.display_name || portfolio.account.email || "?")
                  .trim()
                  .charAt(0)
                  .toUpperCase()}
              </div>
              <div>
                <h3 style={{ margin: 0 }}>Your profile picture</h3>
                <p className="muted" style={{ margin: "4px 0 0" }}>
                  We&apos;re redesigning the avatar set. For now your profile shows a
                  simple monogram taken from your display name. Rename yourself
                  below under <strong>Security</strong> to change it.
                </p>
              </div>
            </div>
          </div>

          <div
            className="card"
            style={{
              border: "2px solid #0ea5e9",
              background: "linear-gradient(135deg, #0b1020 0%, #0f2744 100%)",
              color: "#e8ecf6",
            }}
          >
            <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start", gap: 16, flexWrap: "wrap" }}>
              <div style={{ flex: 1, minWidth: 220 }}>
                <h3 style={{ margin: "0 0 6px", fontSize: 20 }}>
                  {t("account.cameraCheckTitle")}
                </h3>
                <p style={{ margin: 0, opacity: 0.85, lineHeight: 1.45 }}>
                  {t("account.cameraCheckDesc")}
                </p>
              </div>
              <Link href="/account/camera-check">
                <button
                  type="button"
                  style={{
                    padding: "14px 22px",
                    fontSize: 16,
                    fontWeight: 700,
                    background: "#0ea5e9",
                    color: "#fff",
                    border: "2px solid #38bdf8",
                    borderRadius: 12,
                    boxShadow: "0 4px 14px rgba(14,165,233,0.45)",
                    cursor: "pointer",
                  }}
                >
                  📷 {t("account.cameraCheckCta")}
                </button>
              </Link>
            </div>
          </div>

          <div className="card" id="course-language">
            {/* Pared-down Settings & Tools section. The user asked "what's the
                point?" of the old grid that mixed everyday prefs with ops
                buttons (Dashboard, Service Console, Admin). The top-nav already
                exposes Dashboard and Admin for the people who need them, so we
                dropped those two buttons here and kept only the account-scoped
                prefs. Service Console + Admin tools (the ops-y ones) live in a
                collapsed disclosure below that only renders when the viewer is
                admin or has unlocked admin via ADMIN_SECRET. */}
            <h3>{t("account.settingsTools")}</h3>
            <p className="muted" style={{ marginTop: 0 }}>
              Course language for On the Go. Sala listens in any language and teaches in this one.
            </p>
            <LanguagePicker />
            <div className="row" style={{ gap: 8, flexWrap: "wrap", marginTop: 10 }}>
              <Link href="/backgrounds"><button>{t("account.themes")}</button></Link>
              <Link href="/transparency"><button>{t("account.transparency")}</button></Link>
              <Link href="/legal"><button>{t("account.legal")}</button></Link>
              <Link href="/security"><button>Sign-in security</button></Link>
            </div>
            {adminUnlocked && (
              <div style={{ marginTop: 14, borderTop: "1px solid var(--border)", paddingTop: 10 }}>
                <button
                  type="button"
                  onClick={() => setShowAdminTools((v) => !v)}
                  style={{
                    background: "transparent",
                    border: 0,
                    color: "var(--muted)",
                    cursor: "pointer",
                    fontSize: 13,
                    padding: 0,
                  }}
                  aria-expanded={showAdminTools}
                >
                  {showAdminTools ? "▾" : "▸"} Admin tools
                </button>
                {showAdminTools && (
                  <div className="row" style={{ gap: 8, flexWrap: "wrap", marginTop: 8 }}>
                    <Link href="/dashboard"><button>{t("account.dashboard")}</button></Link>
                    {consoleOn && <Link href="/console"><button>{t("account.console")}</button></Link>}
                    <Link href="/admin"><button>{t("account.admin")}</button></Link>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="card">
            <h3>🎬 Intro animation</h3>
            <p className="muted" style={{ marginTop: 0 }}>
              Replay the branded intro (with its jingle). We rotate through {INTRO_VARIANTS.length} high-quality
              animations at random — or pick one below.
            </p>
            <div className="row" style={{ gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
              <button
                type="button"
                onClick={() => playIntro()}
                style={{ background: "#7c3aed", color: "#fff", fontWeight: 600 }}
              >
                ▶ Play random intro
              </button>
              {INTRO_VARIANTS.map((v) => (
                <button key={v.id} type="button" onClick={() => playIntro(v.id)}>
                  {v.name}
                </button>
              ))}
            </div>
            <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={introAutoplay}
                onChange={(e) => toggleIntroAutoplay(e.target.checked)}
              />
              <span className="muted">Play automatically the first time I open the app each session</span>
            </label>
          </div>

          <div className="card">
            <h3>{t("account.learningProfile")}</h3>
            {primaryStudent?.onboarding_completed_at ? (
              <p className="muted" style={{ marginTop: 0 }}>
                {t("account.profileSaved")}
                {primaryStudent.learner_category && primaryStudent.learner_category !== "skipped" ? (
                  <> — <strong>{primaryStudent.learner_category.replace(/_/g, " ")}</strong> {t("account.learnerSuffix")}</>
                ) : primaryStudent.learner_category === "skipped" ? (
                  <> — {t("account.profileSkipped")}</>
                ) : null}
              </p>
            ) : (
              <p className="muted" style={{ marginTop: 0 }}>{t("account.profilePending")}</p>
            )}
            <button
              type="button"
              onClick={() => window.dispatchEvent(new CustomEvent(OPEN_LEARNING_PROFILE_EVENT))}
            >
              {primaryStudent?.onboarding_completed_at ? t("account.updateProfile") : t("account.completeProfile")}
            </button>
          </div>

          <div className="card">
            <h3>{t("account.membership")}</h3>
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              {membershipPlans.map((plan) => (
                <button key={plan.tier} onClick={() => onTier(plan.tier)}
                  style={{ fontWeight: portfolio.tier === plan.tier ? 700 : 400,
                           outline: portfolio.tier === plan.tier ? "2px solid #6ea8fe" : "none",
                           minWidth: 120 }}>
                  <div>{plan.display_name}</div>
                  <div className="muted" style={{ fontSize: 12 }}>{formatMonthlyPrice(plan)}</div>
                  <div className="muted" style={{ fontSize: 11 }}>{plan.ads ? "With ads" : "No ads"}</div>
                </button>
              ))}
            </div>
            <p className="muted" style={{ marginTop: 6 }}>
              Membership is billed monthly (Standard $19/month). Unlocking a full course is a separate
              one-time {COURSE_UNLOCK_PRICE_LABEL} charge.
            </p>
            <p className="muted" style={{ marginTop: 6 }}>
              {t("account.currentPlan", { tier: portfolio.tier })}{" "}
              <Link href="/billing">Billing</Link>
            </p>
            {portfolio.account.subscription?.next_billing_at && (
              <p className="muted" style={{ fontSize: 13 }}>
                Next bill: {formatNextBill(portfolio.account.subscription.next_billing_at)}
                {portfolio.account.subscription.billing_anchor_day
                  ? ` (day ${portfolio.account.subscription.billing_anchor_day} each month)`
                  : ""}
              </p>
            )}
          </div>

          <div className="card">
            <h3>{t("account.myCourses")}</h3>
            {portfolio.enrollments.length === 0 && (
              <p className="muted">{t("account.noCourses")} <Link href="/browse">{t("account.browseCatalog")}</Link>.</p>
            )}
            {STATUS_ORDER.filter((s) => (portfolio.by_status[s] || []).length).map((s) => (
              <div key={s} style={{ marginBottom: 8 }}>
                <strong>{t(`account.status.${s}` as "account.status.enrolled")}</strong> ({portfolio.counts[s]})
                <ul>
                  {portfolio.by_status[s].map((e) => (
                    <li key={e.course_id}>
                      {e.title || e.course_id}
                      {e.score != null && (
                        <span className="muted"> — {t("account.score", { pct: Math.round(e.score * 100) })}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <div className="card">
            <h3>{t("account.studentProfiles")}</h3>
            <p className="muted">
              {t("account.studentProfilesLead")}{" "}
              <Link href="/recommended">{t("account.foresight")}</Link>.
            </p>
            <ul>
              {students.map((s) => (
                <li key={s.id}>
                  <strong>{s.display_name}</strong> ({s.age_band}) — {t("account.skills")}: {Object.keys(s.mastery).length}
                  {" "}
                  <button onClick={() => bumpMastery(s.id)} style={{ fontSize: 12 }}>{t("account.masteryBtn")}</button>
                </li>
              ))}
            </ul>
            <div className="row">
              <input placeholder={t("account.newLearner")} value={newStudent}
                onChange={(e) => setNewStudent(e.target.value)} style={{ padding: 8 }} />
              <button onClick={addStudent}>{t("account.addProfile")}</button>
            </div>
          </div>

          <div className="card">
            <h3>{t("account.security")}</h3>
            <form onSubmit={onChangePassword} className="row">
              <input type="password" placeholder={t("account.currentPassword")} value={cur}
                onChange={(e) => setCur(e.target.value)} style={{ padding: 8, flex: "1 1 160px", minWidth: 0 }} />
              <input type="password" placeholder={t("account.newPassword")} value={next}
                onChange={(e) => setNext(e.target.value)} style={{ padding: 8, flex: "1 1 160px", minWidth: 0 }} />
              <button type="submit">{t("account.changePassword")}</button>
            </form>
            {pwMsg && <p className="muted">{pwMsg}</p>}
          </div>

          {isAdmin && (
            <div className="card">
              <h3>{t("account.adminTitle")}</h3>
              <p className="muted">
                {t("account.adminDesc", { count: allAccounts.length, flag: "access.homework_grader" })}{" "}
                <Link href="/admin">{t("account.admin")} → Feature flags</Link>.
              </p>
              {allAccounts.length === 0 ? (
                <p className="muted">{t("account.noAccounts")}</p>
              ) : (
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: "left", padding: "6px 4px" }}>{t("account.tableEmail")}</th>
                      <th style={{ textAlign: "left", padding: "6px 4px" }}>{t("account.tableName")}</th>
                      <th style={{ textAlign: "left", padding: "6px 4px" }}>{t("account.tableTier")}</th>
                      <th style={{ textAlign: "left", padding: "6px 4px" }}>{t("account.tableAdmin")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {allAccounts.map((a) => (
                      <tr key={a.id}>
                        <td style={{ padding: "6px 4px" }}>{a.email}</td>
                        <td style={{ padding: "6px 4px" }}>{a.display_name}</td>
                        <td style={{ padding: "6px 4px" }}>{a.tier}</td>
                        <td style={{ padding: "6px 4px" }}>{a.is_admin ? "yes" : ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
          <DeleteAccountCard onDeleted={() => { clearToken(); window.location.href = "/"; }} />
        </>
      )}
    </main>
  );
}

function DeleteAccountCard({ onDeleted }: { onDeleted: () => void }) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <div className="card">
      <h3>Delete account</h3>
      <p className="muted">Type DELETE and your password. This removes the account from Salareen.</p>
      <input aria-label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" style={{ display: "block", marginBottom: 8, padding: 8 }} />
      <input aria-label="Type DELETE to confirm" value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="DELETE" style={{ display: "block", marginBottom: 8, padding: 8 }} />
      {error ? <p role="alert">{error}</p> : null}
      <button type="button" disabled={busy || confirm.trim().toUpperCase() !== "DELETE"} onClick={() => {
        setBusy(true);
        setError("");
        void deleteAccount(password, confirm).then(() => onDeleted()).catch((e) => {
          setError(String(e));
          setBusy(false);
        });
      }}>Delete my account</button>
    </div>
  );
}
