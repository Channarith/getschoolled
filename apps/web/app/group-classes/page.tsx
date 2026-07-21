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
  type GroupClass,
  type GroupClassStart,
  type Lesson,
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

  // schedule form
  const [title, setTitle] = useState("");
  const [lessonId, setLessonId] = useState("");
  const [platform, setPlatform] = useState("salareen");
  const [meetingUrl, setMeetingUrl] = useState("");
  const [startTime, setStartTime] = useState(defaultStart());
  const [duration, setDuration] = useState(60);
  const [capacity, setCapacity] = useState(5);
  const [roomSize, setRoomSize] = useState(6);

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
    setLoggedIn(Boolean(getToken()));
    if (getToken()) {
      void getMe().then((a) => setIsAdmin(Boolean(a.is_admin))).catch(() => setIsAdmin(false));
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
      const lesson = lessons.find((l) => l.lesson_id === lessonId);
      await scheduleGroupClass({
        title: title.trim() || (lesson ? lesson.title : "Group class"),
        lesson_id: lessonId,
        platform,
        meeting_url: meetingUrl.trim(),
        start_time: new Date(startTime).toISOString(),
        duration_min: duration,
        capacity: platform === "salareen" ? roomSize - 1 : capacity,
        room_size: platform === "salareen" ? roomSize : undefined,
        language: lesson?.language ?? "en",
      });
      setTitle("");
      setMeetingUrl("");
      setShowForm(false);
      await refresh();
    } catch (e) {
      setError(friendlyError(e, offline));
    } finally {
      setBusy(false);
    }
  }

  // One button does it all: the first person to join opens the class (and hosts
  // it); anyone joining an already-live class just drops into the running room.
  // No separate register/start step — first join comes in.
  async function onJoin(gc: GroupClass) {
    if (!requireAccount()) return;
    if (gc.needs_bridge && gc.meeting_url) {
      window.open(gc.meeting_url, "_blank", "noopener");
      return;
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
          const paid = await confirmGroupClassPayment(gc.id, checkout.checkout.session_id);
          attendeeCode = paid.attendee_code;
          sessionStorage.setItem(codeKey, attendeeCode);
        }
      }
      const wasLive = gc.status === "live" || Boolean(gc.live_room_id);
      const res = await startGroupClass(gc.id);   // idempotent: opens the room
      const roomId = res.bridge.live_room_id || res.bridge.livekit?.room || `class-${gc.id}`;
      const attendeeCode = sessionStorage.getItem(`${ATTENDEE_CODE_KEY}:${gc.id}`) || "";
      if (attendeeCode) {
        sessionStorage.setItem(`${ATTENDEE_CODE_KEY}:${roomId}`, attendeeCode);
      }
      // Only the first joiner (class wasn't live yet) becomes the host/moderator;
      // later arrivals join as learners.
      if (!wasLive && res.bridge.moderator_key) {
        sessionStorage.setItem(`salareen-live-moderator:${roomId}`, res.bridge.moderator_key);
      }
      if (!res.bridge.needs_bridge) {
        window.location.href = `/live-room/${encodeURIComponent(roomId)}`;
        return;
      }
      setStarted(res);
      await refresh();
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
      {/* Hero: Host a Class CTA */}
      <div style={{
        background: "linear-gradient(135deg,#1e293b 0%,#0f172a 100%)",
        borderRadius: 16,
        padding: "28px 32px",
        marginBottom: 24,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 20,
        flexWrap: "wrap",
      }}>
        <div>
          <h1 style={{ margin: 0, color: "#fff", fontSize: 26 }}>🎓 Host a Class</h1>
          <p style={{ margin: "6px 0 0", color: "#94a3b8", fontSize: 14, lineHeight: 1.5 }}>
            Schedule your own live class with the AI teacher. Students join, you facilitate — AI handles the content.
          </p>
        </div>
        <button
          onClick={() => setShowForm((s) => !s)}
          style={{
            background: showForm ? "rgba(255,255,255,0.1)" : "#6366f1",
            color: "#fff",
            border: "none",
            borderRadius: 10,
            padding: "10px 22px",
            fontWeight: 700,
            cursor: "pointer",
            whiteSpace: "nowrap",
          }}
        >
          {showForm ? "▲ Hide form" : "🎓 Host a Class"}
        </button>
      </div>

      {!loggedIn && <SignInToUse />}

      {error && (
        <div className="card" style={{ borderColor: "#ff6b6b" }}>
          <strong>{t("group.errorTitle")}</strong>
          <div className="muted">{error}</div>
        </div>
      )}

      {showForm && (
        <div className="card group-schedule-panel">
          <h3 style={{ marginTop: 0 }}>Schedule your class</h3>
          <div style={{ display: "grid", gap: 10 }}>
            <label>
              <div className="muted">{t("group.fTitle")}</div>
              <input style={{ width: "100%" }} value={title}
                placeholder={t("group.fTitlePlaceholder")}
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
            {platform === "salareen" && (
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
            </div>
            {platform === "salareen" && (
              <div className="muted" style={{ fontSize: 13 }}>
                Salareen live room: Theodore hosts; learners join the multi-user grid.
              </div>
            )}
            <div className="row">
              <button onClick={onSchedule} disabled={busy || !lessonId}
                style={{ background: "#111", color: "#fff" }}>
                {t("group.scheduleSubmit")}
              </button>
            </div>
          </div>
        </div>
      )}

      <h3 style={{ marginTop: 20 }}>{t("group.upcoming")}</h3>
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
              <div className="group-class-actions">
                {/* One button: first join opens (and hosts) the class; later
                    joins drop into the running room. A full class is grayed out
                    for everyone except the platform admin (who can monitor). */}
                <button
                  onClick={() => onJoin(gc)}
                  disabled={busy || (gc.seats_left <= 0 && !isAdmin)}
                  title={gc.seats_left <= 0 && !isAdmin ? t("group.full") : undefined}
                  style={{ background: "#0ea5e9", color: "#fff" }}
                >
                  {gc.seats_left <= 0 && !isAdmin ? t("group.full") : t("group.join")}
                </button>
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
    </main>
  );
}
