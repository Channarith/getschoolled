from pathlib import Path

from reboot_policy import ingest_workers, voice_train_allowed

ROOT = Path(__file__).resolve().parents[2]


def test_ingest_stays_off_while_the_exam_is_alive():
    assert ingest_workers(80000, True) == 0
    assert ingest_workers(20000, False) == 1
    assert ingest_workers(80000, False) == 2
    script = (ROOT / "training" / "systemd" / "voice-ingest-forever.sh").read_text(encoding="utf-8")
    assert "ingest held while the exam is using memory" in script


def test_khmer_does_not_start_while_the_hold_file_is_present():
    assert voice_train_allowed(True) is False
    assert voice_train_allowed(False) is True


def test_translation_does_the_demo_in_every_language_before_the_catalog():
    script = (ROOT / "training" / "systemd" / "translate-forever.sh").read_text(encoding="utf-8")
    demo = script.index('DEMO_COURSE="audio-intro-to-machine-learning"')
    demo_call = script.index("--course \"$DEMO_COURSE\"")
    catalog_call = script.index("=== translate batch start")
    assert demo < demo_call < catalog_call
    assert "NLLB_DEVICE=cpu" in script
    assert 'CUDA_VISIBLE_DEVICES=""' in script
    assert "--concurrency 1" in script
    demo_langs = script.split("DEMO_LANGS=(", 1)[1].split(")", 1)[0].split()
    assert len(demo_langs) == 27
    assert demo_langs[:3] == ["zh", "yue", "km"]
    for code in ("th", "id", "sw", "el", "cs", "es", "ja"):
        assert code in demo_langs
