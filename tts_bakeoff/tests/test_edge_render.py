import asyncio
import json

import pytest

from tts_bakeoff.demo_voice import edge_plan as plan
from tts_bakeoff.demo_voice import edge_render as er
from tts_bakeoff.demo_voice.clip_hash import clip_hash


def _item(tone="neutral", edge="en-US-AriaNeural", text="Hello there, this is a test line."):
    return plan.Item(1, "drivers_ed", "en", text, clip_hash("en", text), edge, tone)


def test_tones_are_22_and_prosody_is_edge_tts_formatted():
    assert len(plan.TONES) == 22 and plan.NEUTRAL not in plan.TONES
    assert plan.prosody("neutral") == {}
    p = plan.prosody("anime")
    assert p == {"rate": "+18%", "pitch": "+40Hz", "volume": "+10%"}
    mix = plan.prosody("blend-professional50-cute50")
    assert mix["rate"].endswith("%") and mix["pitch"].endswith("Hz") and mix["volume"].endswith("%")
    with pytest.raises(KeyError):
        plan.prosody("blend-nope")


def test_variant_dirs_and_paths():
    assert plan.variant_dir("en-US-AriaNeural") == "edge.en-US-AriaNeural"
    assert plan.variant_dir("en-US-AriaNeural", "cute") == "edge.en-US-AriaNeural~cute"
    it = _item("cute")
    assert it.rel == f"edge.en-US-AriaNeural~cute/en/{it.hash}.mp3"


def test_catalog_voices_unique_per_language_and_cantonese_is_yue():
    v = plan.catalog_voices()
    edge_names = [x.edge for vs in v.values() for x in vs]
    assert len(edge_names) == len(set(edge_names))                       # one entry per real edge voice
    assert any(x.edge.startswith("zh-HK") for x in v["yue"])             # Hong Kong voices belong to the yue clips
    assert not any(x.edge.startswith("zh-HK") for x in v.get("zh", []))
    pair = plan.default_pair(v["en"])
    assert [x.gender for x in pair] == ["female", "male"]
    assert "en-US-AndrewNeural" in [x.edge for x in plan.tone_voices("en", v["en"])]


def test_tier1_count_is_lines_times_voices_plus_tone_voices_times_22():
    items = plan.build((1,))
    v = plan.catalog_voices()["en"]
    lines = {it.hash for it in items}
    per_line = len(v) + len(plan.tone_voices("en", v)) * len(plan.TONES)
    assert len(items) == len(lines) * per_line
    assert {it.demo for it in items} == {"drivers_ed"} and {it.lang for it in items} == {"en"}
    assert len({it.rel for it in items}) == len(items)                   # no duplicate clip path


def test_summary_sizes_scale_with_text():
    short, long = _item(text="Hi."), _item(text="This is a much longer sentence that takes a while to say out loud.")
    assert plan.estimate_bytes("en", long.text) > plan.estimate_bytes("en", short.text)
    assert plan.estimate_bytes("zh", "你好你好你好") > plan.estimate_bytes("en", "你好你好你好") / 4
    s = plan.summarize([short, long])
    assert s["clips"] == 2 and s["tiers"][1]["clips"] == 2


def _run(items, tmp_path, synth_fn, **kw):
    async def nosleep(_):
        return None

    return asyncio.run(er.run_items(items, tmp_path, synth_fn=synth_fn, progress_every=3600, sleep=nosleep, **kw))


def test_run_writes_clips_and_resumes_without_rerendering(tmp_path):
    items = [_item(text=f"Line number {i} for the test.") for i in range(6)]
    calls = []

    async def fake(text, voice, tone):
        calls.append(text)
        return b"ID3" + b"x" * 2000

    stats, failed = _run(items, tmp_path, fake, workers=3)
    assert stats.done == 6 and not failed and len(calls) == 6
    assert all(er.present(tmp_path, it) for it in items)
    assert not list(tmp_path.rglob(".tmp-*"))                            # atomic: no temp files left
    stats2, _ = _run(items, tmp_path, fake, workers=3)
    assert stats2.done == 0 and stats2.skipped == 6 and len(calls) == 6  # resumable: nothing re-rendered
    assert json.loads((tmp_path / er.PROGRESS).read_text())["total"] == 6


def test_failures_are_retried_then_listed_and_throttle_pauses(tmp_path):
    items = [_item(text="Always fails."), _item(text="Fails once then works.")]
    seen = {}

    async def flaky(text, voice, tone):
        seen[text] = seen.get(text, 0) + 1
        if text == "Always fails.":
            raise RuntimeError("No audio was received")
        if seen[text] == 1:
            raise RuntimeError("403 Forbidden")
        return b"x" * 2000

    stats, failed = _run(items, tmp_path, flaky, workers=2, attempts=3)
    assert [f.text for f in failed] == ["Always fails."]
    assert stats.done == 1 and stats.failed == 1 and stats.throttled >= 1 and stats.retries >= 4
    assert stats.pause_until > 0                                         # a 403 opens a shared pause for every worker
    assert er.present(tmp_path, items[1]) and not er.present(tmp_path, items[0])


def test_status_index_and_verify(tmp_path):
    a, b = _item("neutral"), _item("cute")

    async def fake(text, voice, tone):
        return b"x" * 2000

    _run([a, b], tmp_path, fake, workers=2)
    st = er.status([a, b, _item(text="not rendered")], tmp_path)
    assert st["tiers"][1] == [2, 3]
    lines = []
    er.print_status(st, lines.append)
    assert any("2/3" in x for x in lines) and "RUNNING" in lines[-1]
    out = er.index_variants(tmp_path)
    assert out["variants"] == 2
    idx = json.loads((tmp_path / "edge.en-US-AriaNeural~cute" / "index.json").read_text())
    assert idx["clips"]["en"] == [b.hash]
    cat = json.loads((tmp_path / er.CATALOG).read_text())
    assert cat["voices"]["en-US-AriaNeural"]["tones"].keys() == {"neutral", "cute"}
    assert cat["by_catalog_id"]["en_us_f"] == "en-US-AriaNeural"
    assert "anime" in cat["tones"] and cat["tones"][0] == "neutral"


def test_probe_skips_voices_that_return_no_audio():
    items = [_item(edge="en-US-DavisNeural"), _item(edge="en-US-AriaNeural")]

    async def fake(text, voice, tone):
        if voice == "en-US-DavisNeural":
            raise RuntimeError("No audio was received")
        return b"x" * 2000

    dead = asyncio.run(er.probe_voices(items, synth_fn=fake, attempts=1))
    assert list(dead) == ["en-US-DavisNeural"]


def test_status_does_not_count_unavailable_voices(tmp_path):
    a, dead = _item(), _item(edge="en-US-DavisNeural")
    (tmp_path / er.UNAVAILABLE).write_text(json.dumps({"en-US-DavisNeural": "NoAudioReceived"}))

    async def fake(text, voice, tone):
        return b"x" * 2000

    _run([a], tmp_path, fake, workers=1)
    assert er.status([a, dead], tmp_path)["tiers"][1] == [1, 1]
