"""Offline demo: watch the classroom react to a present -> absent -> back run.

Runs entirely offline (no network, GPU, or API key) using the xAI voice agent's
grounded fallback, so you can see the pacing + spoken reactions for:
  * Theodore-led SOLO class  (pauses when the learner steps away),
  * Theodore-led GROUP class (holds while any learner is absent),
  * SELF-teaching SOLO        (coach nudges; never pauses a lecture).

Run:  python3 -m webcam_classroom.demo
"""

from __future__ import annotations

from .session import (
    GROUP,
    SOLO,
    TEACHER_SELF,
    TEACHER_THEODORE,
    ClassroomSession,
)
from .silhouette import ABSENT, PRESENT, SilhouetteReading


def _present(coverage: float = 0.22) -> SilhouetteReading:
    return SilhouetteReading(PRESENT, True, coverage, (0.5, 0.5), 1, 0.9, "demo")


def _absent() -> SilhouetteReading:
    return SilhouetteReading(ABSENT, False, 0.0, (0.5, 0.5), 0, 0.0, "demo")


def _print_update(label: str, upd) -> None:
    ev = f"{upd.event.previous}->{upd.event.current}" if upd.event else "(no change)"
    paused = "PAUSED" if upd.paused else "live"
    line = f"  [{label}] {ev:<28} {paused:<6}"
    if upd.spoke:
        line += f'  voice: "{upd.spoken_text}"'
    print(line)


def _run_solo(teacher: str) -> None:
    who = "Theodore-led" if teacher == TEACHER_THEODORE else "Self-teaching"
    print(f"\n=== SOLO / {who} ===")
    s = ClassroomSession(mode=SOLO, teacher=teacher)
    t = 0.0
    # Present for a bit.
    for _ in range(2):
        _print_update("t=%02d" % t, s.observe(_present(), attention=0.8, now=t))
        t += 2
    # Learner steps away; cross the absent threshold (default 20s).
    for _ in range(12):
        upd = s.observe(_absent(), now=t)
        if upd.event or upd.paused:
            _print_update("t=%02d" % t, upd)
        t += 2
    # Learner returns.
    _print_update("t=%02d" % t, s.observe(_present(), attention=0.85, now=t))
    print(f"  final: {s.state()['paused'] and 'PAUSED' or 'live'}")


def _run_group() -> None:
    print("\n=== GROUP / Theodore-led (holds while ANY learner absent) ===")
    s = ClassroomSession(mode=GROUP, teacher=TEACHER_THEODORE, user_ids=["ana", "ben"])
    t = 0.0
    for _ in range(2):
        s.observe(_present(), user_id="ana", attention=0.8, now=t)
        s.observe(_present(), user_id="ben", attention=0.8, now=t)
        t += 2
    print(f"  t={t:02.0f}: both present -> {'PAUSED' if s.paused else 'live'}")
    # Ben leaves; Ana stays. Cross the absent threshold.
    for _ in range(12):
        s.observe(_present(), user_id="ana", attention=0.8, now=t)
        upd = s.observe(_absent(), user_id="ben", now=t)
        if upd.event or (upd.paused and not s.pause_reason.startswith("0")):
            _print_update("t=%02d ben" % t, upd)
        t += 2
    print(f"  t={t:02.0f}: hold reason -> {s.pause_reason!r}")
    # Ben returns.
    upd = s.observe(_present(), user_id="ben", attention=0.8, now=t)
    _print_update("t=%02d ben" % t, upd)
    print(f"  final: {'PAUSED' if s.paused else 'live'} (all present)")


def main() -> None:
    print("Webcam Classroom - offline reaction demo")
    print("(xAI voice agent using grounded fallback; set XAI_API_KEY for live Grok)")
    _run_solo(TEACHER_THEODORE)
    _run_solo(TEACHER_SELF)
    _run_group()


if __name__ == "__main__":
    main()
