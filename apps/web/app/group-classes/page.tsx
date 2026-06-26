"use client";

import { useEffect, useState } from "react";

import {
  getToken,
  groupClassCalendarUrl,
  listGroupClasses,
  listLessons,
  registerGroupClass,
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
  const [showForm, setShowForm] = useState(false);
  const [started, setStarted] = useState<GroupClassStart | null>(null);
  const [loggedIn, setLoggedIn] = useState(true);   // resolved on mount

  // schedule form
  const [title, setTitle] = useState("");
  const [lessonId, setLessonId] = useState("");
  const [platform, setPlatform] = useState("salareen");
  const [meetingUrl, setMeetingUrl] = useState("");
  const [startTime, setStartTime] = useState(defaultStart());
  const [duration, setDuration] = useState(60);
  const [capacity, setCapacity] = useState(100);

  const offline = t("error.offline");

  async function refresh() {
    try {
      setClasses(await listGroupClasses(true));
    } catch (e) {
      setError(friendlyError(e, offline));
    }
  }

  useEffect(() => {
    setLoggedIn(Boolean(getToken()));
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
        capacity,
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

  async function onRegister(gc: GroupClass) {
    if (!requireAccount()) return;
    const name = window.prompt(t("group.registerPrompt"));
    if (!name) return;
    const email = window.prompt("Email for calendar invite (optional):") || "";
    setBusy(true);
    try {
      await registerGroupClass(gc.id, name, email);
      const calUrl = groupClassCalendarUrl(gc.id, name, email);
      if (window.confirm("Added to class! Download a calendar invite (.ics)?")) {
        window.open(calUrl, "_blank", "noopener");
      }
      await refresh();
    } catch (e) {
      setError(friendlyError(e, offline));
    } finally {
      setBusy(false);
    }
  }

  function onJoin(gc: GroupClass) {
    if (!requireAccount()) return;
    if (gc.needs_bridge && gc.meeting_url) {
      window.open(gc.meeting_url, "_blank", "noopener");
    } else {
      window.location.href = "/class";
    }
  }

  async function onStart(gc: GroupClass) {
    if (!requireAccount()) return;
    setError("");
    setBusy(true);
    try {
      const res = await startGroupClass(gc.id);
      setStarted(res);
      await refresh();
    } catch (e) {
      setError(friendlyError(e, offline));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="container">
      <h1>{t("group.title")}</h1>
      <p className="muted" style={{ maxWidth: 720 }}>
        {t("group.intro")}
      </p>

      {!loggedIn && <SignInToUse />}

      {error && (
        <div className="card" style={{ borderColor: "#ff6b6b" }}>
          <strong>{t("group.errorTitle")}</strong>
          <div className="muted">{error}</div>
        </div>
      )}

      <div className="row" style={{ margin: "12px 0" }}>
        <button onClick={() => setShowForm((s) => !s)}>
          {showForm ? t("group.hideForm") : t("group.scheduleCta")}
        </button>
      </div>

      {showForm && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>{t("group.scheduleCta")}</h3>
          <div style={{ display: "grid", gap: 10, maxWidth: 560 }}>
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
              <label style={{ width: 110 }}>
                <div className="muted">{t("group.fCapacity")}</div>
                <input type="number" min={1} style={{ width: "100%" }} value={capacity}
                  onChange={(e) => setCapacity(Number(e.target.value))} />
              </label>
            </div>
            <div className="row">
              <button onClick={onSchedule} disabled={busy || !lessonId}
                style={{ background: "#111", color: "#fff" }}>
                {t("group.scheduleSubmit")}
              </button>
            </div>
          </div>
        </div>
      )}

      <h3>{t("group.upcoming")}</h3>
      {classes.length === 0 && (
        <div className="card"><div className="muted">{t("group.empty")}</div></div>
      )}

      <div style={{ display: "grid", gap: 12 }}>
        {classes.map((gc) => {
          const badge = PLATFORM_BADGE[gc.platform] ?? PLATFORM_BADGE.salareen;
          return (
            <div key={gc.id} className="card">
              <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
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
                  <h3 style={{ margin: "8px 0 2px" }}>{gc.title}</h3>
                  <div className="muted">{fmtTime(gc.start_time)} · {gc.duration_min} min · {gc.host}</div>
                  <div className="muted">
                    {t("group.seatsLeft")}: {gc.seats_left} / {gc.capacity}
                  </div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <button onClick={() => onRegister(gc)} disabled={busy || gc.seats_left <= 0}>
                    {gc.seats_left <= 0 ? t("group.full") : t("group.register")}
                  </button>
                  <button onClick={() => onJoin(gc)} disabled={busy}>
                    {t("group.join")}
                  </button>
                  <button onClick={() => onStart(gc)} disabled={busy}
                    title={t("group.startHint")}
                    style={{ background: "#0ea5e9", color: "#fff" }}>
                    {t("group.start")}
                  </button>
                </div>
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
              <button onClick={() => (window.location.href = "/class")}
                style={{ background: "#111", color: "#fff" }}>
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
