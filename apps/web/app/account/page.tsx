"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  adminListAccounts,
  changePassword,
  clearToken,
  createStudent,
  getMe,
  getPortfolio,
  getRewards,
  getToken,
  listStudents,
  setMembershipTier,
  setStudentMastery,
  type Account,
  type Portfolio,
  type StudentProfile,
} from "../lib/api";
import { OPEN_LEARNING_PROFILE_EVENT } from "../components/LearningProfileSurvey";
import { useT } from "../lib/i18n";

const TIERS = ["free", "basic", "pro", "premium"];
const STATUS_ORDER = ["in_progress", "enrolled", "saved", "passed", "failed"];

export default function AccountPage() {
  const { t } = useT();
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
  const [allAccounts, setAllAccounts] = useState<Account[]>([]);
  const [primaryStudent, setPrimaryStudent] = useState<StudentProfile | null>(null);

  async function refresh() {
    try {
      const me = await getMe();
      setIsAdmin(Boolean(me.is_admin));
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
    try {
      await setMembershipTier(tier);
      await refresh();
    } catch (e) {
      setError(String(e));
    }
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

          <div className="card">
            <h3>{t("account.settingsTools")}</h3>
            <p className="muted">{t("account.settingsDesc")}</p>
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <Link href="/dashboard"><button>{t("account.dashboard")}</button></Link>
              <Link href="/console"><button>{t("account.console")}</button></Link>
              <Link href="/admin"><button>{t("account.admin")}</button></Link>
              <Link href="/backgrounds"><button>{t("account.themes")}</button></Link>
              <Link href="/consent"><button>{t("account.consent")}</button></Link>
              <Link href="/transparency"><button>{t("account.transparency")}</button></Link>
              <Link href="/legal"><button>{t("account.legal")}</button></Link>
            </div>
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
            <div className="row" style={{ gap: 8 }}>
              {TIERS.map((tier) => (
                <button key={tier} onClick={() => onTier(tier)}
                  style={{ fontWeight: portfolio.tier === tier ? 700 : 400,
                           outline: portfolio.tier === tier ? "2px solid #6ea8fe" : "none" }}>
                  {tier}
                </button>
              ))}
            </div>
            <p className="muted" style={{ marginTop: 6 }}>
              {t("account.currentPlan", { tier: portfolio.tier })}
            </p>
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
            <form onSubmit={onChangePassword}>
              <input type="password" placeholder={t("account.currentPassword")} value={cur}
                onChange={(e) => setCur(e.target.value)} style={{ padding: 8, marginRight: 8 }} />
              <input type="password" placeholder={t("account.newPassword")} value={next}
                onChange={(e) => setNext(e.target.value)} style={{ padding: 8, marginRight: 8 }} />
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
        </>
      )}
    </main>
  );
}
