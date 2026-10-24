"""Write tts_bakeoff/sentences/<lang>.jsonl from sentences_master.py (deterministic).

  python3 -m tts_bakeoff.build_sentences            # rewrite the committed files
  python3 -m tts_bakeoff.build_sentences --check    # fail if the committed files differ
  python3 -m tts_bakeoff.build_sentences --from-translations DIR --lang km --count 20
      # print extra domain sentences drawn deterministically from a course
      # translation library (data/course_translations layout); never added to the fixed set.
"""
import argparse
import json
import sys
from pathlib import Path

from .sentences_master import CATEGORIES, LANGS, SENTENCES

HERE = Path(__file__).resolve().parent
OUT = HERE / "sentences"


def ordered_ids() -> list[str]:
    """Round-robin over categories (S, M, L, N, D, P, V, Q), so --limit N always gives a representative mix."""
    groups = {c: sorted(s for s in SENTENCES if s[0] == c) for c in "SMLNDPVQ"}
    out = []
    for i in range(max(len(g) for g in groups.values())):
        out.extend(groups[c][i] for c in "SMLNDPVQ" if i < len(groups[c]))
    return out


def rows(lang: str) -> list[dict]:
    out = []
    for sid in ordered_ids():
        row = SENTENCES[sid]
        out.append({
            "id": sid,
            "lang": lang,
            "category": CATEGORIES[sid[0]],
            "text": row[lang],
            "ref_en": row["en"],
            "source": "authored-v1" if lang == "en" else "authored-v1-translation",
            "review_status": "master" if lang == "en" else "unreviewed",
        })
    return out


def render(lang: str) -> str:
    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows(lang))


def load(lang: str, limit: int | None = None) -> list[dict]:
    path = OUT / f"{lang}.jsonl"
    items = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return items[:limit] if limit else items


def sample_from_translations(root: Path, lang: str, count: int, min_chars: int = 25, max_chars: int = 220) -> list[dict]:
    """Deterministic domain sentences from a translation library (sorted courses, first fit)."""
    picked = []
    for course in sorted(p for p in root.iterdir() if p.is_dir()):
        f = course / f"{lang}.json"
        if not f.exists():
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        for i, seg in enumerate(data.get("segments", [])):
            text = " ".join(str(seg.get("text", "")).split())
            if min_chars <= len(text) <= max_chars:
                picked.append({"id": f"X-{course.name}-{i}", "lang": lang, "category": "course", "text": text,
                               "source": "course_translations", "review_status": "machine"})
                break
        if len(picked) >= count:
            break
    return picked


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--from-translations")
    ap.add_argument("--lang", default="km")
    ap.add_argument("--count", type=int, default=20)
    args = ap.parse_args()
    if args.from_translations:
        for r in sample_from_translations(Path(args.from_translations), args.lang, args.count):
            print(json.dumps(r, ensure_ascii=False))
        return 0
    OUT.mkdir(exist_ok=True)
    bad = 0
    for lang in LANGS:
        path = OUT / f"{lang}.jsonl"
        text = render(lang)
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                print(f"DIFFERS: {path}")
                bad += 1
        else:
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path.name}: {len(SENTENCES)} sentences")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
