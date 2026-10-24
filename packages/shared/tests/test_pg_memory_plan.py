"""The catalog VM memory plan: resident cap, monotonic scaling, rendering, refusal of unsafe machines."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("pg_memory_plan", ROOT / "scripts" / "db" / "pg_memory_plan.py")
mp = importlib.util.module_from_spec(SPEC)
sys.modules["pg_memory_plan"] = mp
SPEC.loader.exec_module(mp)

SIZES = [(7.7, 4), (8, 4), (16, 6), (32, 8), (64, 16), (128, 32)]


def mb(value: str) -> int:
    return int(value.removesuffix("MB"))


@pytest.mark.parametrize("gb,cores", SIZES)
def test_worst_case_resident_never_exceeds_the_cap(gb, cores):
    p = mp.plan(int(gb * 1024), cores)
    assert p.resident_worst_pct <= mp.RESIDENT_CAP_PCT
    assert p.resident_worst_mb == sum(p.budget_mb.values())
    assert p.resident_worst_mb + p.page_cache_room_mb <= p.target_mb or p.page_cache_room_mb == 0
    # the 90% target is met through page cache: room is what is left between resident and 90%
    assert p.page_cache_room_mb == p.target_mb - p.resident_worst_mb


@pytest.mark.parametrize("gb,cores", SIZES)
def test_memory_settings_stay_in_their_bands(gb, cores):
    ram = int(gb * 1024)
    s = mp.plan(ram, cores).settings
    assert 0.35 <= mb(s["shared_buffers"]) / ram <= 0.40
    assert 0.85 <= mb(s["effective_cache_size"]) / ram <= 0.90
    assert mb(s["maintenance_work_mem"]) == 2048 or 0.02 * ram <= mb(s["maintenance_work_mem"]) <= 0.05 * ram
    assert mb(s["autovacuum_work_mem"]) <= 1024
    assert 4 <= mb(s["work_mem"]) <= 256
    assert int(s["max_connections"]) <= 100
    assert s["huge_pages"] == "try"
    assert int(s["autovacuum_max_workers"]) == 3


def test_settings_scale_monotonically_with_ram():
    plans = [mp.plan(int(g * 1024), c) for g, c in [(8, 4), (16, 6), (32, 8), (64, 16)]]
    for key in ("shared_buffers", "effective_cache_size", "work_mem", "maintenance_work_mem", "autovacuum_work_mem"):
        values = [mb(p.settings[key]) for p in plans]
        assert values == sorted(values) and values[0] < values[-1], key
    pools = [p.pgbouncer_pool_size for p in plans]
    assert pools == sorted(pools)
    assert [p.nr_hugepages_estimate for p in plans] == sorted(p.nr_hugepages_estimate for p in plans)
    assert [p.resident_worst_pct for p in plans] == sorted((p.resident_worst_pct for p in plans), reverse=True)


def test_work_mem_budget_is_about_eight_percent_of_ram_in_the_worst_case():
    ram = 16 * 1024
    p = mp.plan(ram, 6)
    assert p.budget_mb["work_mem_all_nodes"] <= 0.08 * ram * 1.05


def test_hugepages_cover_shared_buffers_with_margin():
    p = mp.plan(8192, 4)
    assert p.nr_hugepages_estimate * 2 >= mb(p.settings["shared_buffers"]) * 1.07
    assert p.sysctl["vm.nr_hugepages"] == str(p.nr_hugepages_estimate)


def test_os_protection_settings():
    p = mp.plan(8192, 4)
    assert p.sysctl["vm.swappiness"] == "1"
    assert p.sysctl["vm.overcommit_memory"] == "0"  # 2 is unsafe with huge pages and the postmaster fork pattern
    assert 1024 <= p.swap_file_mb <= 4096


def test_a_4gb_vm_is_refused_not_squeezed():
    # fixed overheads (OS, backends, autovacuum workers, a 4 MB work_mem floor) leave no safe plan at 4 GB
    with pytest.raises(mp.PlanError, match="over the"):
        mp.plan(4096, 2)


def test_too_small_machines_are_refused_loudly():
    with pytest.raises(mp.PlanError, match="too small"):
        mp.plan(1024, 1)
    with pytest.raises(mp.PlanError, match="over the"):
        mp.plan(2048, 8, pool_size=60)  # a pool this big cannot fit a 2 GB machine


def test_a_tighter_cap_fails_instead_of_printing_unsafe_numbers():
    with pytest.raises(mp.PlanError):
        mp.plan(8192, 4, resident_cap_pct=50)


def test_cli_exit_codes_and_formats(tmp_path):
    script = str(ROOT / "scripts" / "db" / "pg_memory_plan.py")
    ok = subprocess.run([sys.executable, script, "--ram-gb", "8", "--cores", "4", "--format", "conf"], capture_output=True, text=True)
    assert ok.returncode == 0
    lines = {ln.split(" = ")[0]: ln.split(" = ")[1] for ln in ok.stdout.splitlines() if " = " in ln}
    assert lines["shared_buffers"] == "3072MB" and lines["effective_cache_size"] == "7168MB"
    env = subprocess.run([sys.executable, script, "--ram-gb", "8", "--cores", "4", "--format", "env"], capture_output=True, text=True).stdout
    assert "PGB_POOL_SIZE=12" in env and "PG_MEMORY_HIGH_MB=7536" in env and "PG_MEMORY_MAX_MB=7946" in env
    sysctl = subprocess.run([sys.executable, script, "--ram-gb", "8", "--cores", "4", "--format", "sysctl"], capture_output=True, text=True).stdout
    assert "vm.swappiness = 1" in sysctl
    bad = subprocess.run([sys.executable, script, "--ram-gb", "1"], capture_output=True, text=True)
    assert bad.returncode == 2 and "REFUSING" in bad.stderr and bad.stdout == ""


def test_meminfo_reader(tmp_path):
    f = tmp_path / "meminfo"
    f.write_text("MemTotal:        8000000 kB\nMemFree: 1 kB\n")
    assert mp.read_meminfo_mb(str(f)) == 7812
    f.write_text("nothing\n")
    with pytest.raises(mp.PlanError):
        mp.read_meminfo_mb(str(f))


def test_the_real_vm_reports_less_than_the_plan_ram_and_still_fits():
    # a "8 GB" Vultr VM shows about 7.7 GB in MemTotal; the planner runs on that number at first boot
    assert mp.plan(7800, 4).resident_worst_pct <= 65


# ---------------------------------------------------------------- the rendered provisioning files
def test_cloud_init_embeds_the_planner_and_setup_uses_it():
    render = ROOT / "scripts" / "db" / "render_cloud_init.py"
    out = subprocess.run([sys.executable, str(render), "--vpc-cidr", "10.12.96.0/20", "--admin-cidr", "1.2.3.4/32", "--redact"],
                         capture_output=True, text=True, check=True).stdout
    import yaml

    doc = yaml.safe_load(out)
    files = {f["path"]: f for f in doc["write_files"]}
    assert "/usr/local/bin/catalog-db-memplan" in files
    assert "class PlanError" in files["/usr/local/bin/catalog-db-memplan"]["content"]
    setup = files["/usr/local/bin/catalog-db-setup"]["content"]
    assert "catalog-db-memplan" in setup and "20-catalog-memory.conf" in setup
    assert "shared_buffers = " not in setup.split("20-catalog-memory")[0].split("10-catalog.conf")[1]  # no hardcoded memory knobs left
    assert "OOMScoreAdjust=-900" in setup and "PG_OOM_ADJUST_VALUE=0" in setup and "MemoryHigh=" in setup
    assert "vm.nr_hugepages" in setup and "swapon" in setup
    assert len(out.encode()) < 45_000  # Vultr user data limit is 64 KB after base64


def test_setup_and_health_scripts_are_valid_bash():
    for name in ("catalog_db_setup.sh", "catalog_db_health.sh"):
        assert subprocess.run(["bash", "-n", str(ROOT / "scripts" / "db" / name)], capture_output=True).returncode == 0
    health = (ROOT / "scripts" / "db" / "catalog_db_health.sh").read_text()
    for needle in ("smaps_rollup", "resident_pct", "oom_kills", "pg_stat_bgwriter", "swap_used_kb", "used_incl_cache_pct"):
        assert needle in health
