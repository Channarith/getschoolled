"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  changePassword,
  clearToken,
  createStudent,
  getPortfolio,
  getRewards,
  getToken,
  listStudents,
  setMembershipTier,
  setStudentMastery,
  type Portfolio,
  type StudentProfile,
} from "../lib/api";

const TIERS = ["free", "basic", "pro", "premium"];
const STATUS_ORDER = ["in_progress", "enrolled", "saved", "passed", "failed"];
const STATUS_LABEL: Record<string, string> = {
  in_progress: "In progress", enrolled: "Enrolled", saved: "My list",
  passed: "Passed", failed: "Failed",
};

export default function AccountPage() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [error, setError] = useState("");
  const [pwMsg, setPwMsg] = useState("");
  const [cur, setCur] = useState("");
  const [next, setNext] = useState("");
  const [loggedIn, setLoggedIn] = useState<boolean>(false);
  const [points, setPoints] = useState<number | null>(null);
  const [students, setStudents] = useState<StudentProfile[]>([]);
  const [newStudent, setNewStudent] = useState("");

  async function refresh() {
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
      setStudents((await listStudents()).students);
    } catch {
      setStudents([]);
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
    const skill = window.prompt("Skill name (e.g. algebra):");
    if (!skill) return;
    const valStr = window.prompt("Mastery 0-1 (e.g. 0.3):", "0.3");
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
  }, []);

  if (!loggedIn) {
    return (
      <main className="container">
        <h1>My account</h1>
        <div className="card">
          <p>Please <Link href="/login">sign in</Link> to view your portfolio, courses, and membership.</p>
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
      setPwMsg("Password updated.");
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
      <h1>My account</h1>
      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{error}</div></div>}

      {portfolio && (
        <>
          <div className="card">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <div>
                <strong>{portfolio.account.display_name}</strong>
                <div className="muted">{portfolio.account.email}</div>
              </div>
              <button onClick={logout}>Sign out</button>
            </div>
            {points != null && (
              <div className="muted" style={{ marginTop: 8 }}>
                ⭐ {points} reward points — <Link href="/rewards">redeem for discounts or prizes</Link>
              </div>
            )}
          </div>

          <div className="card">
            <h3>Membership</h3>
            <div className="row" style={{ gap: 8 }}>
              {TIERS.map((t) => (
                <button key={t} onClick={() => onTier(t)}
                  style={{ fontWeight: portfolio.tier === t ? 700 : 400,
                           outline: portfolio.tier === t ? "2px solid #6ea8fe" : "none" }}>
                  {t}
                </button>
              ))}
            </div>
            <p className="muted" style={{ marginTop: 6 }}>
              Current plan: <strong>{portfolio.tier}</strong>. Manage payments on the billing page.
            </p>
          </div>

          <div className="card">
            <h3>My courses</h3>
            {portfolio.enrollments.length === 0 && (
              <p className="muted">No courses yet. <Link href="/browse">Browse the catalog</Link>.</p>
            )}
            {STATUS_ORDER.filter((s) => (portfolio.by_status[s] || []).length).map((s) => (
              <div key={s} style={{ marginBottom: 8 }}>
                <strong>{STATUS_LABEL[s] || s}</strong> ({portfolio.counts[s]})
                <ul>
                  {portfolio.by_status[s].map((e) => (
                    <li key={e.course_id}>
                      {e.title || e.course_id}
                      {e.score != null && <span className="muted"> — score {Math.round(e.score * 100)}%</span>}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <div className="card">
            <h3>Student profiles</h3>
            <p className="muted">One account, multiple learners. Each profile gets its own
              mastery and <Link href="/recommended">Foresight recommendations</Link>.</p>
            <ul>
              {students.map((s) => (
                <li key={s.id}>
                  <strong>{s.display_name}</strong> ({s.age_band}) — skills: {Object.keys(s.mastery).length}
                  {" "}
                  <button onClick={() => bumpMastery(s.id)} style={{ fontSize: 12 }}>+ mastery</button>
                </li>
              ))}
            </ul>
            <div className="row">
              <input placeholder="New learner name" value={newStudent}
                onChange={(e) => setNewStudent(e.target.value)} style={{ padding: 8 }} />
              <button onClick={addStudent}>Add profile</button>
            </div>
          </div>

          <div className="card">
            <h3>Security</h3>
            <form onSubmit={onChangePassword}>
              <input type="password" placeholder="Current password" value={cur}
                onChange={(e) => setCur(e.target.value)} style={{ padding: 8, marginRight: 8 }} />
              <input type="password" placeholder="New password (min 8)" value={next}
                onChange={(e) => setNext(e.target.value)} style={{ padding: 8, marginRight: 8 }} />
              <button type="submit">Change password</button>
            </form>
            {pwMsg && <p className="muted">{pwMsg}</p>}
          </div>
        </>
      )}
    </main>
  );
}
