import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "stage_translations.py"
ES = "Los impresionistas pintaron la luz al aire libre en el siglo diecinueve y los críticos se rieron mucho."
KM = "អ្នកគូរប្រាណនិយមគូររូបភាពពន្លឺខាងក្រៅនៅសតវត្សទីដប់ប្រាំបួន ហើយអ្នករិះគន់សើចយ៉ាងខ្លាំង។"


def put(root, course, lang, text):
    path = root / course / f"{lang}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"course_id": course, "language": lang, "segments": [{"heading": "T", "text": text, "kind": "narration"}]}, ensure_ascii=False), encoding="utf-8")


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, cwd=ROOT)


def test_stages_only_chosen_valid_files(tmp_path):
    lib = tmp_path / "lib"
    put(lib, "audio-a", "es", ES)
    put(lib, "audio-a", "km", KM)
    put(lib, "other-b", "es", ES)
    put(lib, "audio-c", "es", "los cuadros " * 20)  # degenerate loop: must not ship
    (lib / "audio-a" / "zh.partial").write_text("{}", encoding="utf-8")
    target = tmp_path / "staged"
    wanted = tmp_path / "courses.txt"
    wanted.write_text("# picked\naudio-a\naudio-c\n", encoding="utf-8")
    result = run(lib, "--languages", "es", "--courses", wanted, "--target", target, "--tar", tmp_path / "s.tgz")
    assert result.returncode == 0, result.stderr
    assert (target / "audio-a" / "es.json").is_file()
    assert not (target / "audio-a" / "km.json").exists()
    assert not (target / "other-b").exists()
    assert not (target / "audio-c").exists()
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    assert [(f["course_id"], f["language"]) for f in manifest["files"]] == [("audio-a", "es")]
    assert manifest["totals"]["files"] == 1 and manifest["files"][0]["sha256"]
    assert (tmp_path / "s.tgz").stat().st_size > 0
    assert "image impact" in result.stdout


def test_dry_run_copies_nothing_and_max_mb_refuses(tmp_path):
    lib = tmp_path / "lib"
    put(lib, "audio-a", "es", ES)
    dry = run(lib, "--courses", "all", "--target", tmp_path / "t", "--dry-run")
    assert dry.returncode == 0 and not (tmp_path / "t").exists()
    refused = run(lib, "--courses", "all", "--target", tmp_path / "t2", "--max-mb", "0.000001")
    assert refused.returncode == 3 and not (tmp_path / "t2").exists()
