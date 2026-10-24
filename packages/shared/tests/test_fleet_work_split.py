"""work_split planner: placement rules on fake inventories, plus the inventory helper and result merge. No ssh, no GPU."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[3]
FLEET = REPO / "scripts" / "fleet"


def _load(name: str):
    sys.path.insert(0, str(FLEET))
    spec = importlib.util.spec_from_file_location(name, FLEET / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ws = _load("work_split")
inv_mod = _load("inventory")


def machine(name, *, cuda, avail, total, os_name="Linux", lock=False, reserve=8.0, caps=None):
    inv = {"name": name, "os": os_name, "cuda": cuda, "mem_avail_gb": avail, "mem_total_gb": total, "gpu_lock_held": lock}
    default = {"gpu": 1 if cuda else 0, "cpu": 2}
    return ws.Machine(name, inv, reserve, caps or default)


def fleet(**over):
    ms = {
        "spark": machine("spark", cuda=True, avail=80, total=121, reserve=16),
        "kalel": machine("kalel", cuda=True, avail=40, total=64, reserve=8),
        "mac": machine("mac", cuda=False, avail=20, total=36, os_name="Darwin", caps={"gpu": 0, "cpu": 1}),
    }
    ms.update(over)
    return ms


CATALOG = ws.build_catalog(day="2026-10-25")


def placed(result):
    return {row["item"].id: name for name, w in result["waves"].items() for lab in ("now", "next") for row in w[lab]}


def test_catalog_covers_every_demo_workstream():
    ids = {i.id for i in CATALOG}
    assert {"voice-agent-train", "voice-agent-eval", "demo-voice-clone", "demo-edge-voices", "voice-ingest"} <= ids
    assert any(i.startswith("translate-km-th-vi") for i in ids), "Khmer, Thai and Vietnamese are translated first"


def test_spark_only_jobs_never_leave_the_spark():
    where = placed(ws.plan(CATALOG, fleet()))
    for item in CATALOG:
        if item.roles == ("spark",):
            assert where[item.id] == "spark", item.id


def test_cuda_jobs_never_land_without_cuda():
    ms = fleet()
    where = placed(ws.plan(CATALOG, ms))
    for item in CATALOG:
        if item.cuda and item.id in where:
            assert ms[where[item.id]].has_cuda, f"{item.id} on {where[item.id]}"
    assert ms["mac"].has_cuda is False


def test_mac_only_gets_cpu_work():
    result = ws.plan(CATALOG, fleet())
    for w in result["waves"]["mac"].values():
        for row in w:
            assert row["item"].lane == "cpu" and not row["item"].cuda


def test_spark_training_is_first_in_its_lane():
    result = ws.plan(CATALOG, fleet())
    rows = result["waves"]["spark"]["now"] + result["waves"]["spark"]["next"]
    gpu = [r for r in rows if r["item"].lane == "gpu"]
    assert gpu[0]["item"].id == "voice-agent-train" and gpu[0]["start_min"] == 0
    for r in gpu[1:]:
        assert r["start_min"] >= gpu[0]["finish_min"], f"{r['item'].id} would share the Spark GPU with training"


def test_cpu_only_work_stays_off_the_spark_when_another_machine_can_take_it():
    where = placed(ws.plan(CATALOG, fleet()))
    assert where["demo-edge-voices"] in {"mac", "kalel"}
    spark_only_fleet = {"spark": fleet()["spark"]}
    assert placed(ws.plan(CATALOG, spark_only_fleet))["demo-edge-voices"] == "spark", "still runs when it is the only machine"


def test_validation_is_pinned_to_the_mac_where_collect_puts_the_files():
    by = {i.id: i for i in CATALOG}
    assert by["validate-translations"].roles == ("mac",)
    assert placed(ws.plan(CATALOG, fleet()))["validate-translations"] == "mac"


def test_translation_spills_to_kalel_while_spark_trains():
    where = placed(ws.plan(CATALOG, fleet()))
    translate = [m for i, m in where.items() if i.startswith("translate-")]
    assert "kalel" in translate, "iBuyPower should take translation shards while the Spark trains"


def test_nothing_started_now_exceeds_the_memory_budget():
    ms = fleet(spark=machine("spark", cuda=True, avail=60, total=121, reserve=16))
    result = ws.plan(CATALOG, ms)
    for name, w in result["waves"].items():
        m = ms[name]
        assert sum(r["item"].mem_gb for r in w["now"]) <= m.start_budget_gb + 1e-9, name


def test_machine_below_its_reserve_starts_nothing():
    ms = fleet(spark=machine("spark", cuda=True, avail=10, total=121, reserve=16))
    result = ws.plan(CATALOG, ms)
    assert result["waves"]["spark"]["now"] == []
    assert result["waves"]["spark"]["next"], "the work is still queued behind the memory gate"


def test_held_gpu_lock_defers_gpu_jobs_but_not_cpu_jobs():
    ms = fleet(kalel=machine("kalel", cuda=True, avail=40, total=64, lock=True))
    now = ws.plan(CATALOG, ms)["waves"]["kalel"]["now"]
    assert all(r["item"].lane != "gpu" for r in now)


def test_unreachable_machine_is_skipped():
    ms = fleet()
    ms["kalel"].inv["reachable"] = False
    where = placed(ws.plan(CATALOG, ms))
    assert "kalel" not in where.values()


def test_no_cuda_anywhere_leaves_gpu_work_unplaced_with_a_reason():
    ms = {"mac": machine("mac", cuda=False, avail=20, total=36, os_name="Darwin", caps={"gpu": 0, "cpu": 1})}
    result = ws.plan(CATALOG, ms)
    ids = {u["id"] for u in result["unplaced"]}
    assert "voice-agent-train" in ids
    assert all("needs CUDA" in u["reasons"]["mac"] or "only on" in u["reasons"]["mac"] for u in result["unplaced"])


def test_commands_run_under_gs_run_with_the_gpu_lock():
    by = {i.id: i for i in CATALOG}
    line = ws.command_line(by["translate-km-th-vi"])
    assert line.startswith("scripts/gs_run.sh --name translate-") and " --gpu " in line
    assert "langs:" in line
    cpu = ws.command_line(by["demo-edge-voices"])
    assert "--gpu" not in cpu and cpu.startswith("scripts/gs_run.sh")
    assert ws.command_line(by["demo-voice-clone"]).startswith("MODELS=voxcpm2"), "run_voice_clone.sh wraps itself"


def test_apply_without_yes_only_prints(monkeypatch):
    ran = []
    out = ws.apply(ws.plan(CATALOG, fleet()), fleet(), False, runner=lambda *a, **k: ran.append(a))
    assert not ran and out and all(line.startswith("[dry-run]") for line in out)


def test_apply_skips_nothing_silently_and_reports_failures():
    def runner(cmd, **kw):
        return SimpleNamespace(returncode=255, stderr="Permission denied (publickey)", stdout="")
    out = ws.apply(ws.plan(CATALOG, fleet()), fleet(), True, runner=runner)
    assert out and any("FAILED" in line for line in out)


def test_gather_uses_batchmode_and_records_unreachable(tmp_path, monkeypatch):
    calls = []

    def runner(cmd, **kw):
        calls.append(cmd)
        if cmd[0] == "ssh" and "nvidia@192.168.1.107" in cmd:
            return SimpleNamespace(returncode=0, stdout=json.dumps({"name": "spark", "cuda": True, "mem_avail_gb": 70, "mem_total_gb": 121}))
        return SimpleNamespace(returncode=255, stdout="", stderr="no route")

    monkeypatch.setattr(ws, "HOSTS_CONF", REPO / "scripts" / "fleet" / "hosts.conf")
    status = ws.gather(tmp_path, runner=runner)
    assert status["spark"] is True and status["kalel"] is False
    assert json.loads((tmp_path / "kalel.json").read_text())["reachable"] is False
    for cmd in calls:
        if cmd[0] == "ssh":
            assert "BatchMode=yes" in cmd, "key-based only: ssh must never prompt for a password"


def test_inventory_reports_the_fields_the_planner_reads():
    inv = inv_mod.collect("mac")
    for key in ("hostname", "os", "mem_total_gb", "mem_avail_gb", "disk_free_gb", "gpu", "cuda", "gpu_lock_held", "python"):
        assert key in inv
    assert inv["mem_total_gb"] > 0
    json.dumps(inv)


def test_inventory_lock_probe_sees_a_held_lock(tmp_path):
    import fcntl
    lock = tmp_path / "gpu.lock"
    with open(lock, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        assert inv_mod.lock_held(str(lock)) is True
    assert inv_mod.lock_held(str(lock)) is False


def test_inventory_is_read_only(tmp_path):
    before = sorted(p.name for p in tmp_path.iterdir())
    subprocess.run([sys.executable, str(FLEET / "inventory.py")], cwd=tmp_path, capture_output=True, timeout=120, check=True)
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_translate_script_accepts_an_explicit_language_list():
    text = (REPO / "scripts" / "translate_on_machine.sh").read_text()
    assert "langs:*)" in text
    out = subprocess.run(["bash", "-c", 'langs_for(){ case "${1:-all}" in langs:*) echo "${1#langs:}" | tr "," " " ;; esac; }; langs_for langs:km,th'],
                         capture_output=True, text=True).stdout.strip()
    assert out == "km th"


def test_collect_merges_only_current_files_and_never_overwrites(tmp_path, monkeypatch):
    from aoep_shared import translation_v2 as tv2

    src = SimpleNamespace(course_id="course-a", sha="abc", segments=[])
    monkeypatch.setattr(tv2, "audio_sources", lambda: [src])
    monkeypatch.setattr(tv2, "studio_sources", lambda: [])
    verdicts = {"good": (True, "current"), "stale": (False, "source_changed")}

    def fake_is_current(record, source, lang, **kw):
        if not record:
            return False, "missing"
        return verdicts[record["mark"]]

    monkeypatch.setattr(tv2, "is_current", fake_is_current)
    saved = []
    from aoep_shared import course_translation_library as lib
    monkeypatch.setattr(lib, "save_translation", lambda record, root=None: saved.append(record["mark"] + ":" + record["language"]))
    incoming = tmp_path / "data"
    (incoming / "_incoming_kalel" / "course-a").mkdir(parents=True)
    (incoming / "_incoming_kalel" / "course-a" / "km.json").write_text(json.dumps({"mark": "good", "language": "km"}))
    (incoming / "_incoming_kalel" / "course-a" / "th.json").write_text(json.dumps({"mark": "stale", "language": "th"}))
    (incoming / "_incoming_kalel" / "ghost").mkdir()
    (incoming / "_incoming_kalel" / "ghost" / "km.json").write_text("{}")
    monkeypatch.setenv("FLEET_HOST_KALEL", "local")
    result = ws.collect("kalel", False, incoming, library=tmp_path / "lib")
    assert result["merged"] == 1 and result["rejected"] == 1 and result["unknown_course"] == 1 and saved == []
    assert result["rejected_sample"][0]["why"] == "source_changed"
    ws.collect("kalel", True, incoming, library=tmp_path / "lib")
    assert saved == ["good:km"]


def test_collect_rsync_never_deletes(tmp_path):
    seen = []

    def runner(cmd, **kw):
        seen.append(cmd)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    ws.collect("kalel", False, tmp_path, library=tmp_path / "lib", runner=runner)
    rsync = next(c for c in seen if c[0] == "rsync")
    assert "--ignore-existing" in rsync and not any(a.startswith("--delete") for a in rsync)
