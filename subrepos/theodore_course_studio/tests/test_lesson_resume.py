"""Coming back to the lesson resumes it once, from the server's slide, unless the learner paused."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from theodore_course_studio.generate import CourseBuilder
from theodore_course_studio.studio_page import STUDIO_JS, render_studio_page
from theodore_course_studio.types import CourseSlide, StudioCourse

LIVE_AUDIO_JS = (
    Path(__file__).resolve().parents[3]
    / "packages" / "shared" / "src" / "aoep_shared" / "static" / "lab_live_audio.js"
)


def _factory_source() -> str:
    start = STUDIO_JS.index("function createLessonLifecycle(io)")
    depth = 0
    for pos in range(STUDIO_JS.index("{", start), len(STUDIO_JS)):
        char = STUDIO_JS[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return STUDIO_JS[start:pos + 1]
    raise AssertionError("createLessonLifecycle has no closing brace")


# A fake page: records every call so each scenario can count continues and failures.
_HARNESS = """
const results = {};
function makeIo(over) {
  const io = {
    hidden: false, playing: true, paused: false, played: 'played', verifyOk: true,
    calls: { away: 0, refresh: 0, restore: 0, reconcile: 0, cont: 0, verify: 0, fail: 0, clear: 0 },
    isHidden() { return io.hidden; },
    isPlaying() { return io.playing; },
    isPaused() { return io.paused; },
    onAway() { io.calls.away += 1; },
    refresh() { io.calls.refresh += 1; },
    async restoreMedia() { io.calls.restore += 1; if (io.restoreGate) await io.restoreGate; },
    async reconcile() { io.calls.reconcile += 1; return { path_pos: 3 }; },
    async continueLesson() { io.calls.cont += 1; return io.played; },
    async verify() { io.calls.verify += 1; return io.verifyOk; },
    showFailure() { io.calls.fail += 1; },
    clearFailure() { io.calls.clear += 1; },
  };
  return Object.assign(io, over || {});
}

async function main() {
  {
    const io = makeIo(); const life = createLessonLifecycle(io);
    io.hidden = true; life.away('hidden');
    io.hidden = false;
    results.basic = { result: await life.back('visible'), cont: io.calls.cont, away: io.calls.away };
  }
  {
    const io = makeIo(); const life = createLessonLifecycle(io);
    life.away('hidden');
    const runs = [life.back('visible'), life.back('focus'), life.back('pageshow'), life.back('camera-playing')];
    const out = await Promise.all(runs);
    const after = await life.back('focus');
    results.repeated = { out, after, cont: io.calls.cont, reconcile: io.calls.reconcile, refresh: io.calls.refresh, same: runs[0] === runs[3] };
  }
  {
    const io = makeIo({ playing: false }); const life = createLessonLifecycle(io);
    life.away('hidden');
    results.pausedBefore = { result: await life.back('visible'), cont: io.calls.cont };
  }
  {
    const io = makeIo(); const life = createLessonLifecycle(io);
    life.away('hidden'); io.paused = true;
    results.pausedWhileAway = { result: await life.back('visible'), cont: io.calls.cont };
  }
  {
    const io = makeIo({ verifyOk: false }); const life = createLessonLifecycle(io);
    life.away('hidden');
    const first = await life.back('visible');
    const failed = life.failed();
    const focus = await life.back('focus');
    io.verifyOk = true;
    const tap = await life.back('tap', { force: true });
    results.retry = { first, failed, focus, tap, fail: io.calls.fail, failedAfter: life.failed(), cont: io.calls.cont };
  }
  {
    let release; const gate = new Promise((r) => { release = r; });
    const io = makeIo({ restoreGate: gate }); const life = createLessonLifecycle(io);
    life.away('hidden');
    const firstRun = life.back('visible');
    await Promise.resolve();
    life.away('hidden');
    io.restoreGate = null;
    const second = life.back('visible');
    release();
    results.stale = { first: await firstRun, second: await second, cont: io.calls.cont };
  }
  {
    const io = makeIo({ hidden: true }); const life = createLessonLifecycle(io);
    life.away('hidden');
    const ignored = await life.back('focus');
    io.hidden = false;
    results.hiddenBack = { ignored, then: await life.back('visible'), cont: io.calls.cont };
  }
  {
    const io = makeIo(); const life = createLessonLifecycle(io);
    life.away('hidden'); life.away('pagehide'); life.away('freeze');
    results.repeatedAway = { away: io.calls.away };
  }
  {
    const io = makeIo(); const life = createLessonLifecycle(io);
    life.away('pagehide');
    results.bfcache = { result: await life.back('pageshow-bfcache'), cont: io.calls.cont };
  }
  {
    const io = makeIo({ played: 'quiet' }); const life = createLessonLifecycle(io);
    life.away('app-background');
    results.quiet = { result: await life.back('app-active'), verify: io.calls.verify };
  }
  {
    const io = makeIo(); const life = createLessonLifecycle(io);
    io.continueLesson = async () => { throw new Error('network'); };
    life.away('sleep');
    results.thrown = { result: await life.back('wake'), fail: io.calls.fail, failed: life.failed() };
  }
  console.log(JSON.stringify(results));
}
main().catch((error) => { console.error(error); process.exit(1); });
"""


@pytest.fixture(scope="module")
def lifecycle(tmp_path_factory) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("lifecycle") / "run.js"
    script.write_text(_factory_source() + "\n" + _HARNESS, encoding="utf-8")
    done = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=30, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_coming_back_resumes_once(lifecycle):
    assert lifecycle["basic"] == {"result": "resumed", "cont": 1, "away": 1}


def test_repeated_focus_events_share_one_resume(lifecycle):
    run = lifecycle["repeated"]
    assert run["out"] == ["resumed"] * 4
    assert run["same"] is True
    assert run["cont"] == 1 and run["reconcile"] == 1
    assert run["after"] == "steady"
    assert run["refresh"] == 1


def test_an_intentional_pause_stays_paused(lifecycle):
    assert lifecycle["pausedBefore"] == {"result": "paused", "cont": 0}
    assert lifecycle["pausedWhileAway"] == {"result": "paused", "cont": 0}


def test_a_failed_resume_waits_for_one_tap(lifecycle):
    run = lifecycle["retry"]
    assert run["first"] == "failed" and run["failed"] is True
    # A plain focus event retries too, since the lesson was playing when it failed.
    assert run["focus"] == "failed"
    assert run["tap"] == "resumed"
    assert run["failedAfter"] is False
    assert run["fail"] == 2


def test_leaving_mid_resume_drops_the_stale_run(lifecycle):
    run = lifecycle["stale"]
    assert run["first"] == "stale"
    assert run["second"] == "resumed"
    assert run["cont"] == 1


def test_focus_while_still_hidden_is_ignored(lifecycle):
    assert lifecycle["hiddenBack"] == {"ignored": "hidden", "then": "resumed", "cont": 1}


def test_repeated_leave_events_pause_once(lifecycle):
    assert lifecycle["repeatedAway"] == {"away": 1}


def test_bfcache_and_app_foreground_resume(lifecycle):
    assert lifecycle["bfcache"] == {"result": "resumed", "cont": 1}
    assert lifecycle["quiet"] == {"result": "resumed", "verify": 0}
    assert lifecycle["thrown"] == {"result": "failed", "fail": 1, "failed": True}


def test_every_return_path_is_wired():
    for needle in (
        "addEventListener('visibilitychange'",
        "addEventListener('pagehide'",
        "addEventListener('pageshow'",
        "event.persisted ? 'pageshow-bfcache'",
        "addEventListener('freeze'",
        "addEventListener('resume'",
        "addEventListener('focus'",
        "addEventListener('salareen-app-state'",
        "data.type === 'salareen-app-state'",
        "on('student-cam-video', 'playing'",
        "on('student-cam-video', 'loadeddata'",
        "track.addEventListener('mute'",
        "track.addEventListener('unmute'",
        "track.addEventListener('ended'",
        "lessonLife.away('sleep')",
        "lifecycleReturn('wake')",
        "WAKE_GAP_MS",
        "/api/studio/teach/current",
        "on('resume-retry', 'click'",
    ):
        assert needle in STUDIO_JS, needle
    assert 'id="resume-retry"' in render_studio_page()


def test_stale_work_cannot_double_play():
    assert "if (lessonLife.isAway()) return;" in STUDIO_JS
    assert "if (after && gen === speechGen) after();" in STUDIO_JS
    assert "if (token === lessonLife.token() && !lessonLife.isAway()) renderTeach(data);" in STUDIO_JS
    assert "syncVoiceToSlide(lastTeachPayload, { force: true })" in STUDIO_JS


def test_live_audio_exposes_resume_and_wakes_its_context():
    source = LIVE_AUDIO_JS.read_text(encoding="utf-8")
    assert "async resumeAudio()" in source
    assert "status()" in source
    assert "wakeAudio" in source


def test_current_reports_the_slide_without_advancing(tmp_path):
    import theodore_course_studio.main as main_mod

    old_builder = main_mod._builder
    old_teach_builder = main_mod._teach._builder
    shared = CourseBuilder(data_dir=tmp_path / "data")
    main_mod._builder = shared
    main_mod._teach._builder = shared
    try:
        course = StudioCourse(
            course_id="resume-mini",
            title="Resume Mini",
            category="other",
            slides=[CourseSlide(index=i, title=f"Slide {i}", body=f"Body {i}.") for i in range(3)],
        )
        shared.save_course(course)
        client = TestClient(main_mod.app)
        started = client.post("/api/studio/teach/start", json={
            "session_id": "resume-1", "course_id": course.course_id, "use_voice_agent": False,
        })
        assert started.status_code == 200, started.text
        moved = client.post("/api/studio/teach/advance", json={"session_id": "resume-1"}).json()
        first = client.post("/api/studio/teach/current", json={"session_id": "resume-1"})
        second = client.post("/api/studio/teach/current", json={"session_id": "resume-1"})
        assert first.status_code == 200, first.text
        assert first.json()["path_pos"] == moved["path_pos"] == second.json()["path_pos"]
        assert first.json()["turn"]["title"] == moved["turn"]["title"]
        missing = client.post("/api/studio/teach/current", json={"session_id": "nope"})
        assert missing.status_code == 404
        assert "missing" in missing.json()["detail"]
    finally:
        main_mod._builder = old_builder
        main_mod._teach._builder = old_teach_builder
