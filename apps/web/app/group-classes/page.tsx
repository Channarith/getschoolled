"use client";

import { useEffect, useState } from "react";

import {
  checkoutGroupClass,
  confirmGroupClassPayment,
  getMe,
  getToken,
  listGroupClasses,
  listLessons,
  reviewGroupClass,
  scheduleGroupClass,
  startGroupClass,
  uploadHostPresentation,
  validateVoucher,
  type GroupClass,
  type GroupClassStart,
  type Lesson,
  type VoucherValidateResult,
} from "../lib/api";
import SignInToUse from "../components/SignInToUse";
import { friendlyError } from "../lib/errors";
import { useT } from "../lib/i18n";

const PLATFORMS = [
  { value: "salareen", label: "Salareen room (built-in)" },
  { value: "zoom", label: "Zoom" },
  { value: "teams", label: "Microsoft Teams" },
  { value: "meet", label: "Google Meet" },
];

const PLATFORM_BADGE: Record<string, { label: string; bg: string; fg: string }> = {
  salareen: { label: "Salareen", bg: "#1e293b", fg: "#e2e8f0" },
  zoom: { label: "Zoom", bg: "#e0ecff", fg: "#1d4ed8" },
  teams: { label: "Teams", bg: "#eae8ff", fg: "#5b21b6" },
  meet: { label: "Google Meet", bg: "#dcfce7", fg: "#15803d" },
};

const ATTENDEE_CODE_KEY = "salareen-attendee-code";

function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      weekday: "short", month: "short", day: "numeric",
      hour: "numeric", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

// Default the schedule form to one hour from now, rounded to the next 5 minutes,
// formatted for a <input type="datetime-local">.
function defaultStart(): string {
  const d = new Date(Date.now() + 60 * 60 * 1000);
  d.setMinutes(Math.ceil(d.getMinutes() / 5) * 5, 0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function GroupClassesPage() {
  const { t } = useT();
  const [classes, setClasses] = useState<GroupClass[]>([]);
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showForm, setShowForm] = useState(true); // open by default — this page IS the host-a-class page
  const [started, setStarted] = useState<GroupClassStart | null>(null);
  const [loggedIn, setLoggedIn] = useState(true);   // resolved on mount
  const [isAdmin, setIsAdmin] = useState(false);    // platform admin can join a full class to monitor
  const [myAccountId, setMyAccountId] = useState("");

  // schedule form
  const [title, setTitle] = useState("");
  const [lessonId, setLessonId] = useState("");
  const [platform, setPlatform] = useState("salareen");
  const [meetingUrl, setMeetingUrl] = useState("");
  const [startTime, setStartTime] = useState(defaultStart());
  const [duration, setDuration] = useState(60);
  const [capacity, setCapacity] = useState(5);
  const [roomSize, setRoomSize] = useState(6);
  const [pricePerUser, setPricePerUser] = useState("");
  const [presentationFile, setPresentationFile] = useState<File | null>(null);
  // Session type: 1-on-1 private tutoring vs full group class
  const [sessionType, setSessionType] = useState<"private" | "group">("group");
  // Teach vs Join tab
  const [activeTab, setActiveTab] = useState<"teach" | "join">("join");

  // Payment method selection modal
  const [checkoutTarget, setCheckoutTarget] = useState<GroupClass | null>(null);
  const [paymentMethod, setPaymentMethod] = useState("card");
  const [voucherCode, setVoucherCode] = useState("");
  const [voucherResult, setVoucherResult] = useState<VoucherValidateResult | null>(null);
  const [voucherBusy, setVoucherBusy] = useState(false);

  const offline = t("error.offline");
  const paidLabel = "Paid class";
  const ratingLabel = "Instructor rating";

  async function refresh() {
    try {
      setClasses(await listGroupClasses(true));
    } catch (e) {
      setError(friendlyError(e, offline));
    }
  }

  useEffect(() => {
    // Auto-open teach tab if linked from class page with ?tab=teach
    if (typeof window !== "undefined") {
      const p = new URLSearchParams(window.location.search);
      if (p.get("tab") === "teach") setActiveTab("teach");
    }
    setLoggedIn(Boolean(getToken()));
    if (getToken()) {
      void getMe().then((a) => {
        setIsAdmin(Boolean(a.is_admin));
        setMyAccountId(a.id || "");
      }).catch(() => { setIsAdmin(false); setMyAccountId(""); });
    }
    refresh();
    listLessons()
      .then((ls) => {
        setLessons(ls);
        if (ls.length) setLessonId(ls[0].lesson_id);
      })
      .catch((e) => setError(friendlyError(e, offline)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function requireAccount(): boolean {
    if (getToken()) return true;
    setLoggedIn(false);
    if (typeof window !== "undefined") window.scrollTo({ top: 0, behavior: "smooth" });
    return false;
  }

  async function onSchedule() {
    if (!requireAccount()) return;
    setError("");
    setBusy(true);
    try {
      let chosenLessonId = lessonId;
      let presentationFilename = "";
      const lesson = lessons.find((l) => l.lesson_id === lessonId);
      if (presentationFile) {
        const imported = await uploadHostPresentation(presentationFile, {
          title: title.trim() || lesson?.title,
          language: lesson?.language ?? "en",
        });
        chosenLessonId = imported.lesson_id;
        presentationFilename = imported.presentation_filename;
        setLessons(await listLessons());
      }
      const priceRaw = Number(pricePerUser.trim());
      const price = pricePerUser.trim() && !Number.isNaN(priceRaw) ? priceRaw : undefined;
      await scheduleGroupClass({
        title: title.trim() || (lesson ? lesson.title : "Group class"),
        lesson_id: chosenLessonId,
        platform,
        meeting_url: meetingUrl.trim(),
        start_time: new Date(startTime).toISOString(),
        duration_min: duration,
        capacity: platform === "salareen" ? roomSize - 1 : capacity,
        room_size: platform === "salareen" ? roomSize : undefined,
        language: lesson?.language ?? "en",
        price_per_user_usd: price,
        payment_required: price != null && price > 0,
        attendee_code_required: price != null && price > 0,
        presentation_filename: presentationFilename || undefined,
      });
      setTitle("");
      setMeetingUrl("");
      setPricePerUser("");
      setPresentationFile(null);
      await refresh();
    } catch (e) {
      setError(friendlyError(e, offline));
    } finally {
      setBusy(false);
    }
  }


  async function onScheduleAsStudent() {
    if (!requireAccount()) return;
    setError("");
    setBusy(true);
    try {
      const lesson = lessons.find((l) => l.lesson_id === lessonId);
      await scheduleGroupClass({
        title: (lesson ? `${lesson.title} — Study Group` : "Study Group"),
        lesson_id: lessonId,
        platform: "salareen",
        meeting_url: "",
        start_time: new Date(startTime).toISOString(),
        duration_min: duration,
        capacity: roomSize - 1,
        room_size: roomSize,
        language: lesson?.language ?? "en",
        price_per_user_usd: undefined,
        payment_required: false,
        attendee_code_required: false,
      });
      await refresh();
      setActiveTab("join"); // return to class list so student can join their new session
    } catch (e) {
      setError(friendlyError(e, offline));
    } finally {
      setBusy(false);
    }
  }

  function isHost(gc: GroupClass): boolean {
    if (!myAccountId) return false;
    return myAccountId === gc.instructor_account_id || myAccountId === gc.created_by_account_id;
  }

  async function openSalareenRoom(res: GroupClassStart, gc: GroupClass, asHost: boolean) {
    const roomId = res.bridge.live_room_id || res.bridge.livekit?.room || `class-${gc.id}`;
    const attendeeCode = sessionStorage.getItem(`${ATTENDEE_CODE_KEY}:${gc.id}`) || "";
    if (attendeeCode) {
      sessionStorage.setItem(`${ATTENDEE_CODE_KEY}:${roomId}`, attendeeCode);
    }
    if (asHost && res.bridge.moderator_key) {
      sessionStorage.setItem(`salareen-live-moderator:${roomId}`, res.bridge.moderator_key);
    }
    if (!res.bridge.needs_bridge) {
      window.location.href = `/live-room/${encodeURIComponent(roomId)}`;
      return;
    }
    setStarted(res);
    await refresh();
  }

  async function onStartHost(gc: GroupClass) {
    if (!requireAccount()) return;
    setError("");
    setBusy(true);
    try {
      const res = await startGroupClass(gc.id);
      await openSalareenRoom(res, gc, true);
    } catch (e) {
      setError(friendlyError(e, offline));
    } finally {
      setBusy(false);
    }
  }

  async function onJoin(gc: GroupClass) {
    if (!requireAccount()) return;
    if (isHost(gc)) {
      await onStartHost(gc);
      return;
    }
    if (gc.needs_bridge && gc.meeting_url) {
      window.open(gc.meeting_url, "_blank", "noopener");
      return;
    }
    // For paid classes, open the payment selection modal instead of immediately checking out
    if ((gc.payment_required || gc.attendee_code_required) && (gc.price_per_user_usd ?? 0) > 0) {
      const codeKey = `${ATTENDEE_CODE_KEY}:${gc.id}`;
      const existingCode = sessionStorage.getItem(codeKey);
      if (!existingCode) {
        setCheckoutTarget(gc);
        setPaymentMethod("card");
        setVoucherCode("");
        setVoucherResult(null);
        return;
      }
    }
    setError("");
    setBusy(true);
    try {
      if (gc.payment_required || gc.attendee_code_required) {
        const codeKey = `${ATTENDEE_CODE_KEY}:${gc.id}`;
        let attendeeCode = sessionStorage.getItem(codeKey) || "";
        if (!attendeeCode) {
          const me = await getMe();
          const checkout = await checkoutGroupClass(
            gc.id,
            me.display_name || me.email || "Learner",
            me.email || "",
          );
          const priceLabel = gc.price_per_user_usd ? `$${gc.price_per_user_usd.toFixed(2)}` : "the listed price";
          const proceed = window.confirm(`Pay ${priceLabel} per seat to attend this class?`);
          if (!proceed) return;
          const paid = await confirmGroupClassPayment(gc.id, checkout.checkout.session_id);
          attendeeCode = paid.attendee_code;
          sessionStorage.setItem(codeKey, attendeeCode);
        }
      }
      const wasLive = gc.status === "live" || Boolean(gc.live_room_id);
      if (wasLive) {
        const roomId = gc.live_room_id || `class-${gc.id}`;
        window.location.href = `/live-room/${encodeURIComponent(roomId)}`;
        return;
      }
      const res = await startGroupClass(gc.id);
      await openSalareenRoom(res, gc, false);
    } catch (e) {
      setError(friendlyError(e, offline));
    } finally {
      setBusy(false);
    }
  }

  async function onRate(gc: GroupClass) {
    if (!requireAccount()) return;
    const raw = window.prompt("Rate this instructor (1-5):", "5");
    if (!raw) return;
    const rating = Number(raw);
    if (!Number.isFinite(rating) || rating < 1 || rating > 5) {
      setError("Rating must be between 1 and 5.");
      return;
    }
    const comment = window.prompt("Optional review comment:", "") || "";
    setBusy(true);
    setError("");
    try {
      await reviewGroupClass(gc.id, Math.round(rating), comment);
      await refresh();
    } catch (e) {
      setError(friendlyError(e, offline));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="container page-one group-page">
      <h1 style={{ fontSize: 24, fontWeight: 900, marginBottom: 20 }}>Group Class</h1>

      {!loggedIn && <SignInToUse />}

      {error && (
        <div className="card" style={{ borderColor: "#ff6b6b" }}>
          <strong>{t("group.errorTitle")}</strong>
          <div className="muted">{error}</div>
        </div>
      )}

      {/* ── Teach / Join tab bar ───────────────────────────────────────── */}
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        <button type="button" onClick={() => setActiveTab("teach")}
          style={{ flex: 1, padding: "14px 20px", borderRadius: 10, border: "2px solid",
            borderColor: activeTab === "teach" ? "#6366f1" : "rgba(0,0,0,0.1)",
            background: activeTab === "teach" ? "#6366f1" : "#fff",
            color: activeTab === "teach" ? "#fff" : "#111", fontWeight: 700, fontSize: 15, cursor: "pointer" }}>
          🎓 Teach a Class
        </button>
        <button type="button" onClick={() => setActiveTab("join")}
          style={{ flex: 1, padding: "14px 20px", borderRadius: 10, border: "2px solid",
            borderColor: activeTab === "join" ? "#6366f1" : "rgba(0,0,0,0.1)",
            background: activeTab === "join" ? "#6366f1" : "#fff",
            color: activeTab === "join" ? "#fff" : "#111", fontWeight: 700, fontSize: 15, cursor: "pointer" }}>
          📚 Join a Class
        </button>
      </div>

      {activeTab === "teach" && (
        <div className="card group-schedule-panel">
          <h3 style={{ marginTop: 0 }}>Schedule your class</h3>

          {/* Session type picker */}
          <div style={{ display: "flex", gap: 10, marginBottom: 18 }}>
            <button
              type="button"
              onClick={() => { setSessionType("private"); setRoomSize(2); setCapacity(1); }}
              style={{
                flex: 1, padding: "14px 16px", borderRadius: 12, cursor: "pointer",
                border: `2px solid ${sessionType === "private" ? "#6366f1" : "rgba(0,0,0,0.12)"}`,
                background: sessionType === "private" ? "#eef2ff" : "#fff",
                textAlign: "left",
              }}
            >
              <div style={{ fontWeight: 700, fontSize: 15, color: sessionType === "private" ? "#4338ca" : "#1e293b" }}>
                👤 1-on-1 Private Lesson
              </div>
              <div style={{ fontSize: 12, color: "#64748b", marginTop: 3 }}>
                You and one student. Private room, personal tutoring.
              </div>
            </button>
            <button
              type="button"
              onClick={() => { setSessionType("group"); setRoomSize(6); setCapacity(5); }}
              style={{
                flex: 1, padding: "14px 16px", borderRadius: 12, cursor: "pointer",
                border: `2px solid ${sessionType === "group" ? "#6366f1" : "rgba(0,0,0,0.12)"}`,
                background: sessionType === "group" ? "#eef2ff" : "#fff",
                textAlign: "left",
              }}
            >
              <div style={{ fontWeight: 700, fontSize: 15, color: sessionType === "group" ? "#4338ca" : "#1e293b" }}>
                👥 Group Class
              </div>
              <div style={{ fontSize: 12, color: "#64748b", marginTop: 3 }}>
                Multiple paying students. Salareen room, Zoom, Teams, or Meet.
              </div>
            </button>
          </div>

          <div style={{ display: "grid", gap: 10 }}>
            <label>
              <div className="muted">{t("group.fTitle")}</div>
              <input style={{ width: "100%" }} value={title}
                placeholder={sessionType === "private" ? "e.g. Private Math Tutoring — Algebra" : t("group.fTitlePlaceholder")}
                onChange={(e) => setTitle(e.target.value)} />
            </label>
            <label>
              <div className="muted">{t("group.fLesson")}</div>
              <select style={{ width: "100%" }} value={lessonId}
                onChange={(e) => setLessonId(e.target.value)}>
                {lessons.map((l) => (
                  <option key={l.lesson_id} value={l.lesson_id}>{l.title}</option>
                ))}
              </select>
            </label>
            <label>
              <div className="muted">{t("group.fPlatform")}</div>
              <select style={{ width: "100%" }} value={platform}
                onChange={(e) => setPlatform(e.target.value)}>
                {PLATFORMS.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </label>
            {platform === "salareen" && sessionType === "private" && (
              <div style={{ background: "#f0fdf4", border: "1px solid #86efac", borderRadius: 10, padding: "10px 14px", fontSize: 14, color: "#15803d" }}>
                🔒 Private room · 2 seats (you + 1 student)
              </div>
            )}
            {platform === "salareen" && sessionType === "group" && (
              <label>
                <div className="muted">Room size (including AI host)</div>
                <select
                  style={{ width: "100%" }}
                  value={roomSize}
                  onChange={(e) => {
                    const size = Number(e.target.value);
                    setRoomSize(size);
                    setCapacity(size - 1);
                  }}
                >
                  <option value={4}>4 seats (3 learners + Theodore)</option>
                  <option value={6}>6 seats (5 learners + Theodore)</option>
                  <option value={9}>9 seats (8 learners + Theodore)</option>
                </select>
              </label>
            )}
            {platform !== "salareen" && (
              <label>
                <div className="muted">{t("group.fMeetingUrl")}</div>
                <input style={{ width: "100%" }} value={meetingUrl}
                  placeholder="https://zoom.us/j/123…  ·  meet.google.com/abc-defg-hij"
                  onChange={(e) => setMeetingUrl(e.target.value)} />
              </label>
            )}
            <div className="row">
              <label style={{ flex: 1 }}>
                <div className="muted">{t("group.fStart")}</div>
                <input type="datetime-local" style={{ width: "100%" }} value={startTime}
                  onChange={(e) => setStartTime(e.target.value)} />
              </label>
              <label style={{ width: 110 }}>
                <div className="muted">{t("group.fDuration")}</div>
                <input type="number" min={5} step={5} style={{ width: "100%" }} value={duration}
                  onChange={(e) => setDuration(Number(e.target.value))} />
              </label>
            {platform !== "salareen" && (
              <label style={{ width: 110 }}>
                <div className="muted">{t("group.fCapacity")}</div>
                <input type="number" min={1} style={{ width: "100%" }} value={capacity}
                  onChange={(e) => setCapacity(Number(e.target.value))} />
              </label>
            )}
            <label style={{ width: 140 }}>
              <div className="muted">{sessionType === "private" ? "Session fee (USD, paid by student)" : "Price per student (USD)"}</div>
              <input type="number" min={0} step={0.01} style={{ width: "100%" }} value={pricePerUser}
                placeholder="0 = free"
                onChange={(e) => setPricePerUser(e.target.value)} />
            </label>
          </div>
          <label>
            <div className="muted">Your presentation (PDF or PPTX) <span style={{ color: "#6366f1", fontSize: 11, fontWeight: 700 }}>Optional</span></div>
            <input
              type="file"
              accept=".pdf,.pptx,application/pdf,application/vnd.openxmlformats-officedocument.presentationml.presentation"
              onChange={(e) => setPresentationFile(e.target.files?.[0] ?? null)}
            />
            <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
              Optional — upload your PDF or PPTX to use your own slides. Without a file, the selected catalog lesson above is used and you (the host) advance slides manually. Theodore will not narrate when you are hosting.
            </div>
          </label>
          {platform === "salareen" && (
              <div className="muted" style={{ fontSize: 13 }}>
                {sessionType === "private"
                  ? "Private 1-on-1 room: you teach, Theodore assists on request. Upload slides or use a catalog lesson — you control Next Slide."
                  : "Group room: you teach, students join. Use your own slides or a catalog lesson — you control Next Slide. Theodore stays silent unless called."}
              </div>
            )}
            <div className="row">
              <button onClick={onSchedule} disabled={busy || !lessonId}
                style={{ background: sessionType === "private" ? "#059669" : "#111", color: "#fff", borderRadius: 10, padding: "12px 28px", fontWeight: 700, fontSize: 15, border: "none", cursor: "pointer" }}>
                {sessionType === "private" ? "📅 Schedule Private Lesson" : t("group.scheduleSubmit")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Student: request a custom class slot */}
      {activeTab === "join" && (
        <div className="card" style={{ marginBottom: 20, background: "linear-gradient(135deg,#f0f9ff 0%,#e0f2fe 100%)", border: "1px solid #bae6fd" }}>
          <h3 style={{ marginTop: 0, color: "#0369a1" }}>📅 Schedule a Class for Your Group</h3>
          <p className="muted" style={{ marginTop: 0, marginBottom: 16 }}>
            Don&apos;t see a time that works? Create your own session — pick a topic, set a time, and share the link with your group. AI teaches.
          </p>
          <div style={{ display: "grid", gap: 10 }}>
            <label>
              <div className="muted">Topic / Lesson</div>
              <select style={{ width: "100%" }} value={lessonId} onChange={(e) => setLessonId(e.target.value)}>
                {lessons.map((l) => (
                  <option key={l.lesson_id} value={l.lesson_id}>{l.title}</option>
                ))}
              </select>
            </label>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <label>
                <div className="muted">Date &amp; time</div>
                <input type="datetime-local" style={{ width: "100%" }} value={startTime}
                  onChange={(e) => setStartTime(e.target.value)} />
              </label>
              <label>
                <div className="muted">Duration (minutes)</div>
                <select style={{ width: "100%" }} value={duration} onChange={(e) => setDuration(Number(e.target.value))}>
                  <option value={30}>30 min</option>
                  <option value={60}>60 min</option>
                  <option value={90}>90 min</option>
                </select>
              </label>
            </div>
            <label>
              <div className="muted">Expected students (including you)</div>
              <select style={{ width: "100%" }} value={roomSize} onChange={(e) => { setRoomSize(Number(e.target.value)); setCapacity(Number(e.target.value) - 1); }}>
                <option value={2}>Just me (solo)</option>
                <option value={4}>Me + 3 friends (4 total)</option>
                <option value={6}>Me + 5 friends (6 total)</option>
                <option value={9}>Me + 8 friends (9 total)</option>
              </select>
            </label>
            <div className="row">
              <button onClick={onScheduleAsStudent} disabled={busy || !lessonId}
                style={{ background: "#0369a1", color: "#fff", borderRadius: 10, padding: "11px 24px", fontWeight: 700, fontSize: 15, border: "none", cursor: "pointer" }}>
                {busy ? "Creating…" : "📅 Create My Group Session"}
              </button>
            </div>
            <div className="muted" style={{ fontSize: 12 }}>
              After creating, you&apos;ll get a join link to share with your group. The AI teacher will be waiting.
            </div>
          </div>
        </div>
      )}

      {/* ─── Join tab: student section ─────────────────────────────────────── */}
      {activeTab === "join" && (
      <div>
      {/* ─── Student section separator ─── */}
      <div style={{
        borderTop: "2px solid var(--border)",
        marginTop: 28,
        paddingTop: 20,
        marginBottom: 4,
      }}>
        <h3 style={{ margin: 0 }}>📚 Browse classes to join as a student</h3>
        <p style={{ margin: "6px 0 16px", color: "var(--muted)", fontSize: 14, lineHeight: 1.5 }}>
          Sign up as a student below — AI or your instructor leads the session.
        </p>
      </div>

      {classes.length === 0 && (
        <div className="card"><div className="muted">{t("group.empty")}</div></div>
      )}

      <div className="group-class-list">
        {classes.map((gc) => {
          const badge = PLATFORM_BADGE[gc.platform] ?? PLATFORM_BADGE.salareen;
          return (
            <div key={gc.id} className="card group-class-card">
              <div className="group-class-meta">
                <div className="row" style={{ gap: 8, alignItems: "center" }}>
                  <span style={{ fontSize: 12, padding: "2px 10px", borderRadius: 999,
                    background: badge.bg, color: badge.fg, fontWeight: 600 }}>
                    {badge.label}
                  </span>
                  {gc.status === "live" && (
                    <span style={{ fontSize: 12, padding: "2px 10px", borderRadius: 999,
                      background: "#fee2e2", color: "#b91c1c", fontWeight: 600 }}>
                      ● {t("group.live")}
                    </span>
                  )}
                </div>
                <h3>{gc.title}</h3>
                <div className="muted" style={{ fontSize: 13 }}>
                  {fmtTime(gc.start_time)} · {gc.duration_min} min · {gc.host}
                </div>
                <div className="muted" style={{ fontSize: 13 }}>
                  {t("group.seatsLeft")}: {gc.seats_left} / {gc.capacity}
                  {gc.platform === "salareen" && gc.room_size ? ` · ${gc.room_size}-seat room` : ""}
                </div>
                <div className="muted" style={{ fontSize: 13 }}>
                  {ratingLabel}: {gc.instructor_stats?.review_avg ?? gc.review_avg ?? 0} / 5
                  {" · "}
                  {gc.instructor_stats?.review_count ?? gc.review_count ?? 0} reviews
                  {" · "}
                  {gc.instructor_stats?.courses_taught ?? 0} classes taught
                </div>
                {(gc.payment_required || gc.attendee_code_required) && (
                  <div className="muted" style={{ fontSize: 13 }}>
                    {paidLabel}
                    {gc.price_per_user_usd ? ` · $${gc.price_per_user_usd.toFixed(2)} per seat` : ""}
                    {" · "}Salareen commission {(100 * (gc.commission_rate ?? 0.15)).toFixed(0)}%
                  </div>
                )}
                {gc.audit_required && gc.audit_status !== "approved" && (
                  <div className="muted" style={{ fontSize: 13, color: "#b45309" }}>
                    Pending Salareen audit approval.
                  </div>
                )}
                {gc.platform === "teams" && gc.external_camera_ingest_supported && (
                  <div className="muted" style={{ fontSize: 13 }}>
                    Teams room-device camera ingest ready
                    {gc.device_profile ? ` (${gc.device_profile})` : ""}
                    {gc.camera_source_count ? ` · ${gc.camera_source_count} camera source(s)` : ""}
                  </div>
                )}
              </div>
            <div className="row" style={{ flexWrap: "wrap", gap: 8, alignItems: "center" }}>
              {isHost(gc) ? (
                <button
                  onClick={() => void onStartHost(gc)}
                  disabled={busy}
                  style={{ background: "#6366f1", color: "#fff" }}
                >
                  🎓 Start My Class
                </button>
              ) : (
                <button
                  onClick={() => onJoin(gc)}
                  disabled={busy || (gc.seats_left <= 0 && !isAdmin)}
                  title={gc.seats_left <= 0 && !isAdmin ? t("group.full") : undefined}
                  style={{ background: "#0ea5e9", color: "#fff" }}
                >
                  {gc.seats_left <= 0 && !isAdmin ? t("group.full") : t("group.join")}
                </button>
              )}
              <button onClick={() => onRate(gc)} disabled={busy}>
                Rate instructor
              </button>
            </div>
            </div>
          );
        })}
      </div>

      {started && (
        <div role="dialog" aria-modal="true"
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.55)",
            display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50, padding: 16 }}>
          <div className="card" style={{ maxWidth: 560, width: "100%", background: "#fff" }}>
            <h3 style={{ marginTop: 0 }}>{t("group.startedTitle")}</h3>
            <p className="muted">{started.bridge.note}</p>
            <div className="card" style={{ background: "#f8fafc" }}>
              <div><strong>{started.class.title}</strong></div>
              <div className="muted">
                {t("group.firstSlide")}: {started.session.slide.title}
              </div>
              <div className="muted">LiveKit room: {started.bridge.livekit?.room}</div>
              {started.bridge.needs_bridge && (
                <div className="muted">
                  {t("group.bridgeVia")} {started.bridge.platform} → {started.bridge.connect_endpoint}
                </div>
              )}
            </div>
            <div className="row" style={{ marginTop: 12 }}>
              {started.bridge.needs_bridge && started.class.meeting_url && (
                <button onClick={() => window.open(started.class.meeting_url, "_blank", "noopener")}>
                  {t("group.openMeeting")}
                </button>
              )}
              <button
                onClick={() => {
                  const roomId = started.bridge.live_room_id || started.bridge.livekit?.room || `class-${started.class.id}`;
                  if (started.bridge.moderator_key) {
                    sessionStorage.setItem(`salareen-live-moderator:${roomId}`, started.bridge.moderator_key);
                  }
                  window.location.href = `/live-room/${encodeURIComponent(roomId)}`;
                }}
                style={{ background: "#111", color: "#fff" }}
              >
                {t("group.openClass")}
              </button>
              <button onClick={() => setStarted(null)}>{t("group.close")}</button>
            </div>
          </div>
        </div>
      )}
    </div>
      )}

      {/* ── Payment method selection modal ───────────────────────────────────── */}
      {checkoutTarget && (checkoutTarget.price_per_user_usd ?? 0) > 0 && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
          <div style={{ background: "#fff", borderRadius: 16, padding: 32, maxWidth: 480, width: "100%", boxShadow: "0 20px 60px rgba(0,0,0,0.3)", overflowY: "auto", maxHeight: "90vh" }}>
            <h2 style={{ margin: "0 0 6px" }}>Pay for Class</h2>
            <p className="muted" style={{ margin: "0 0 20px" }}>{checkoutTarget.title} &middot; ${(checkoutTarget.price_per_user_usd ?? 0).toFixed(2)}/seat</p>

            {/* Payment method grid */}
            <div style={{ marginBottom: 20 }}>
              <div className="muted" style={{ marginBottom: 10, fontWeight: 700 }}>Choose payment method</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
                {[
                  { id: "card", label: "Credit / Debit Card" },
                  { id: "apple_pay", label: "Apple Pay" },
                  { id: "google_pay", label: "Google Pay" },
                  { id: "paypal", label: "PayPal" },
                  { id: "venmo", label: "Venmo" },
                  { id: "cashapp", label: "Cash App" },
                  { id: "zelle", label: "Zelle" },
                  { id: "klarna", label: "Klarna" },
                  { id: "afterpay", label: "Afterpay" },
                ].map((m) => (
                  <button key={m.id} type="button"
                    onClick={() => setPaymentMethod(m.id)}
                    style={{ padding: "10px 8px", borderRadius: 10, border: `2px solid ${paymentMethod === m.id ? "#6366f1" : "rgba(0,0,0,0.12)"}`,
                      background: paymentMethod === m.id ? "#eef2ff" : "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer", textAlign: "center" }}>
                    {m.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Zelle manual instructions */}
            {paymentMethod === "zelle" && (
              <div style={{ background: "#fefce8", border: "1px solid #fde047", borderRadius: 10, padding: 14, marginBottom: 16, fontSize: 13 }}>
                <strong>Zelle Instructions:</strong><br />
                Send <strong>${(checkoutTarget.price_per_user_usd ?? 0).toFixed(2)}</strong> to <strong>payments@salareen.com</strong><br />
                Include your name and class title in the memo.<br />
                Email <a href="mailto:support@salareen.com">support@salareen.com</a> with your payment confirmation &mdash; we will grant access within 1 hour.
              </div>
            )}

            {/* Voucher / coupon code */}
            <div style={{ marginBottom: 20 }}>
              <div className="muted" style={{ marginBottom: 8, fontWeight: 700 }}>Have a coupon or gift code?</div>
              <div style={{ display: "flex", gap: 8 }}>
                <input value={voucherCode}
                  onChange={(e) => { setVoucherCode(e.target.value.toUpperCase()); setVoucherResult(null); }}
                  placeholder="e.g. SAVE20 or GIFT50"
                  style={{ flex: 1, padding: "10px 12px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 14 }} />
                <button
                  onClick={async () => {
                    if (!voucherCode.trim() || !checkoutTarget) return;
                    setVoucherBusy(true);
                    try {
                      const result = await validateVoucher(voucherCode.trim(), checkoutTarget.price_per_user_usd ?? 0, checkoutTarget.id);
                      setVoucherResult(result);
                    } catch {
                      setVoucherResult({ valid: false, error: "Could not validate code" });
                    }
                    setVoucherBusy(false);
                  }}
                  disabled={voucherBusy}
                  style={{ padding: "10px 16px", borderRadius: 8, background: "#6366f1", color: "#fff", border: "none", fontWeight: 700, cursor: "pointer" }}>
                  {voucherBusy ? "..." : "Apply"}
                </button>
              </div>
              {voucherResult && (
                <div style={{ marginTop: 8, padding: "8px 12px", borderRadius: 8, background: voucherResult.valid ? "#f0fdf4" : "#fef2f2", border: `1px solid ${voucherResult.valid ? "#86efac" : "#fca5a5"}`, fontSize: 13 }}>
                  {voucherResult.valid
                    ? <>{voucherResult.description} &mdash; <strong>Final: ${voucherResult.final_price?.toFixed(2)}</strong> (saves ${voucherResult.savings?.toFixed(2)})</>
                    : <>{voucherResult.error}</>}
                </div>
              )}
            </div>

            {/* Price summary */}
            <div style={{ background: "#f8fafc", borderRadius: 10, padding: 14, marginBottom: 20, fontSize: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Class price</span><span>${(checkoutTarget.price_per_user_usd ?? 0).toFixed(2)}</span>
              </div>
              {voucherResult?.valid && (
                <div style={{ display: "flex", justifyContent: "space-between", color: "#16a34a" }}>
                  <span>Discount</span><span>-${voucherResult.savings?.toFixed(2)}</span>
                </div>
              )}
              <div style={{ display: "flex", justifyContent: "space-between", fontWeight: 900, marginTop: 6, borderTop: "1px solid #e2e8f0", paddingTop: 6 }}>
                <span>Total</span>
                <span>${(voucherResult?.valid ? voucherResult.final_price : checkoutTarget.price_per_user_usd ?? 0)?.toFixed(2)}</span>
              </div>
            </div>

            <div style={{ display: "flex", gap: 10 }}>
              <button
                onClick={() => { setCheckoutTarget(null); setVoucherCode(""); setVoucherResult(null); setPaymentMethod("card"); }}
                style={{ flex: 1, padding: "12px", borderRadius: 10, border: "1px solid #d1d5db", background: "#fff", fontWeight: 700, cursor: "pointer" }}>
                Cancel
              </button>
              {paymentMethod !== "zelle" ? (
                <button
                  onClick={async () => {
                    const gc = checkoutTarget;
                    if (!gc) return;
                    setBusy(true); setError("");
                    try {
                      const me = await getMe();
                      const data = await checkoutGroupClass(
                        gc.id,
                        me.display_name || me.email || "Learner",
                        me.email || "",
                        { payment_method: paymentMethod, voucher_code: voucherResult?.valid ? voucherCode : "" },
                      );
                      setCheckoutTarget(null);
                      if (data.free) {
                        alert("Free access granted! Check your classes.");
                        await refresh();
                      } else if (data.checkout?.url) {
                        window.location.href = data.checkout.url;
                      } else {
                        // Non-redirect checkout (e.g. sandbox) — try confirm immediately
                        const paid = await confirmGroupClassPayment(gc.id, data.checkout.session_id);
                        const codeKey = `${ATTENDEE_CODE_KEY}:${gc.id}`;
                        sessionStorage.setItem(codeKey, paid.attendee_code);
                        await refresh();
                      }
                    } catch (e) { setError(friendlyError(e, offline)); }
                    setBusy(false);
                  }}
                  disabled={busy}
                  style={{ flex: 2, padding: "12px", borderRadius: 10, background: busy ? "#9ca3af" : "#6366f1", color: "#fff", border: "none", fontWeight: 700, cursor: busy ? "default" : "pointer", fontSize: 15 }}>
                  {busy ? "Processing..." : `Pay $${(voucherResult?.valid ? voucherResult.final_price : checkoutTarget.price_per_user_usd ?? 0)?.toFixed(2)}`}
                </button>
              ) : (
                <button
                  onClick={() => { setCheckoutTarget(null); }}
                  style={{ flex: 2, padding: "12px", borderRadius: 10, background: "#ca8a04", color: "#fff", border: "none", fontWeight: 700, cursor: "pointer", fontSize: 15 }}>
                  {"I've sent the Zelle payment"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
