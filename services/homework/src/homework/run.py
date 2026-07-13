#!/usr/bin/env python3
"""Homework CLI — generate, scan (OCR), authorship-check, and grade homework.

Mirrors the harvester CLI (services/harvester/src/harvester/run.py): one flat
argparse front-end over the aoep_shared.homework library, mode-selected by flags,
so the homework subtool runs offline from the command line exactly like the
harvester — no server, no keys required for the default (mock/offline) path.

Modes (dispatch order):
  --instructions           print the usage recipe and exit
  --generate PATH          build an assignment from a local file (text/html/pdf/
                           pptx/docx/json-slides) -> writes <id>.assignment.json
  --content TEXT           build an assignment from inline text (alt to --generate)
  --scan FILE              OCR a scanned/typed submission -> Submission JSON
  --authorship             AI-vs-human signal for a submission -> verdict JSON
  --grade ASSIGNMENT_JSON  autograde answers against an assignment -> grade JSON

Output convention (matches harvester):
  * stdout : machine-readable JSON (the assignment / submission / verdict / grade)
  * stderr : human progress + the written artifact path
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Allow running from a clean checkout without manually setting PYTHONPATH.
_REPO = Path(__file__).resolve().parents[4]
for _p in (_REPO / "packages" / "shared" / "src", Path(__file__).resolve().parents[1]):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from aoep_shared.adaptive import Difficulty  # noqa: E402
from aoep_shared.config import load_config  # noqa: E402
from aoep_shared.factory import ProviderFactory  # noqa: E402
from aoep_shared.homework import (  # noqa: E402
    Assignment,
    assignment_from_slides,
    detect_authorship,
    generate_assignment,
    grade_submission,
    ocr_to_submission,
    segment_answers,
)

DEFAULT_OUT_DIR = _REPO / "output" / "homework"

INSTRUCTIONS = """\
Homework CLI — offline generate / scan / authorship / grade.

Generate an assignment from a local file (auto-splits paragraphs into questions):
  python3 services/homework/src/homework/run.py --generate notes.txt \\
      --title "Cell Biology HW" --subject biology --num-questions 6

Generate from inline text or a harvested course deck:
  python3 services/homework/src/homework/run.py --content "Photosynthesis: ..." --title HW
  python3 services/homework/src/homework/run.py --generate course.course.json --source-type slides

Scan a submission (Tesseract if installed, else offline mock OCR of UTF-8 bytes):
  python3 services/homework/src/homework/run.py --scan answers.txt --expected 5

Authorship (AI-vs-human) signal — probabilistic, routes borderline cases to HIL:
  python3 services/homework/src/homework/run.py --authorship --submission-file answers.txt

Autograde a submission against a generated assignment:
  python3 services/homework/src/homework/run.py --grade hw.assignment.json \\
      --submission-file answers.txt              # or: --answers "a" "b" "c"
Add --online to corroborate open answers against trusted web sources.
"""


def _resolve_repo_path(path: str | Path) -> Path:
    """Resolve a repo-relative path regardless of the process cwd."""
    p = Path(path).expanduser()
    if p.is_file():
        return p.resolve()
    under_repo = (_REPO / p).resolve()
    if under_repo.is_file():
        return under_repo
    return p.resolve() if p.is_absolute() else under_repo


def _split_passages(text: str) -> list[str]:
    """Split source text into passages (blank-line or newline separated)."""
    return [p.strip() for p in re.split(r"\n\s*\n|\n", text) if p.strip()]


def _load_source(args: argparse.Namespace):
    """Return ``(passages, slides, source_label)`` for generation.

    Exactly one of ``passages`` / ``slides`` is populated. Mirrors the
    harvester's --source-type handling so text/html/pdf/pptx/docx and JSON
    slide decks all work from the CLI.
    """
    if args.content:
        return _split_passages(args.content), None, "content"

    path = _resolve_repo_path(args.generate)
    if not path.is_file():
        raise SystemExit(f"source file not found: {args.generate!r} (resolved: {path})")
    st = args.source_type

    # JSON slide deck (e.g. a harvested *.course.json or a [{title,body}] list).
    if st in ("slides", "json") or (st is None and path.suffix == ".json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        slides = data.get("slides", data) if isinstance(data, dict) else data
        if not isinstance(slides, list):
            raise SystemExit("JSON source must be a list of slides or an object with 'slides'")
        return None, slides, str(args.generate)

    # Rich document types: reuse the harvester extractors -> (heading, text) sections.
    if st in ("html", "pdf", "pptx", "docx"):
        from aoep_shared.harvest import extract

        raw = path.read_bytes() if st in ("pdf", "pptx", "docx") \
            else path.read_text(encoding="utf-8", errors="replace")
        doc = extract(st, raw, default_title=args.title or path.stem)
        passages = [f"{h}: {t}" for h, t in doc.nonempty_sections()]
        if not passages:
            passages = [t for _, t in doc.sections if (t or "").strip()]
        return passages, None, str(args.generate)

    # Plain text / markdown / inferred.
    return _split_passages(path.read_text(encoding="utf-8", errors="replace")), None, str(args.generate)


def _generate(args: argparse.Namespace) -> Assignment:
    passages, slides, source = _load_source(args)
    if slides is not None:
        if not slides:
            raise SystemExit("no slides in JSON source to generate from")
        return assignment_from_slides(
            slides, title=args.title, subject=args.subject, source=source,
            num_questions=args.num_questions, locale=args.locale,
        )
    if not passages:
        raise SystemExit("no usable content to generate from")
    return generate_assignment(
        passages, title=args.title, subject=args.subject, source=source,
        num_questions=args.num_questions, difficulty=Difficulty(args.difficulty),
        locale=args.locale,
    )


def _emit_assignment(assignment: Assignment, *, out_dir: str) -> Path:
    """Write the assignment JSON artifact and print a human summary to stderr."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{assignment.assignment_id}.assignment.json"
    path.write_text(assignment.model_dump_json(indent=2), encoding="utf-8")
    by_type: dict[str, int] = {}
    for q in assignment.questions:
        by_type[q.type.value] = by_type.get(q.type.value, 0) + 1
    print(
        f"\nWrote {len(assignment.questions)}-question assignment "
        f"{assignment.assignment_id!r} ({by_type}) to {path}",
        file=sys.stderr,
    )
    return path


def _load_submission_text(args: argparse.Namespace) -> str:
    if getattr(args, "submission_text", None):
        return args.submission_text
    if getattr(args, "submission_file", None):
        p = _resolve_repo_path(args.submission_file)
        if not p.is_file():
            raise SystemExit(f"submission file not found: {args.submission_file!r} (resolved: {p})")
        return p.read_text(encoding="utf-8", errors="replace")
    return ""


def _scan(args: argparse.Namespace) -> int:
    path = _resolve_repo_path(args.scan)
    if not path.is_file():
        raise SystemExit(f"scan file not found: {args.scan!r} (resolved: {path})")
    factory = ProviderFactory(load_config())
    ocr = factory.ocr()
    hint = "handwritten" if args.handwritten else None
    try:
        result = ocr.read(path.read_bytes(), hint=hint)
    except NotImplementedError as exc:
        raise SystemExit(f"OCR unavailable: {exc}") from exc
    sub = ocr_to_submission(result, expected=args.expected)
    print(f"OCR via {ocr.impl}: {len(sub.segments)} answer segment(s), "
          f"confidence {sub.confidence}", file=sys.stderr)
    print(json.dumps(sub.model_dump(), indent=2))
    return 0


def _authorship(args: argparse.Namespace) -> int:
    text = _load_submission_text(args)
    if not text.strip():
        raise SystemExit("provide --submission-text or --submission-file for --authorship")
    verdict = detect_authorship(text, handwritten=args.handwritten)
    print(json.dumps({
        "label": verdict.label,
        "ai_probability": verdict.ai_probability,
        "signals": verdict.signals,
        "note": "Probabilistic signal, not proof; borderline cases route to human review.",
    }, indent=2))
    return 0


def _grade(args: argparse.Namespace) -> int:
    apath = _resolve_repo_path(args.grade)
    if not apath.is_file():
        raise SystemExit(f"assignment file not found: {args.grade!r} (resolved: {apath})")
    assignment = Assignment.model_validate(json.loads(apath.read_text(encoding="utf-8")))

    submission_text = _load_submission_text(args)
    if args.answers:
        answers = list(args.answers)
    elif submission_text:
        answers = segment_answers(submission_text)
    else:
        raise SystemExit("provide --answers or --submission-text/--submission-file to grade")

    joined = submission_text or " ".join(answers)
    authorship = detect_authorship(joined, handwritten=args.handwritten) if joined.strip() else None

    engines = []
    if args.online:
        engines = ProviderFactory(load_config()).search_engines()
    grade = grade_submission(
        assignment, answers, engines=engines, subject=args.subject or assignment.subject,
        authorship=authorship,
    )
    print(f"Graded {len(grade.items)} item(s): {grade.score}/{grade.max_score} "
          f"({grade.percentage}%) flags={grade.validity_flags}", file=sys.stderr)
    print(json.dumps({
        "score": grade.score, "max_score": grade.max_score, "percentage": grade.percentage,
        "validity_flags": grade.validity_flags, "authorship_label": grade.authorship_label,
        "items": [
            {"question_id": it.question_id, "type": it.type, "correct": it.correct,
             "score": it.score, "citations": it.citations, "rationale": it.rationale}
            for it in grade.items
        ],
    }, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Homework CLI: generate, scan (OCR), authorship-check, and grade homework.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--instructions", action="store_true",
                    help="print the usage recipe and exit")
    # Generate
    ap.add_argument("--generate", default=None, metavar="PATH",
                    help="generate an assignment from a local file")
    ap.add_argument("--content", default=None, metavar="TEXT",
                    help="generate an assignment from inline text (alt to --generate)")
    ap.add_argument("--source-type", default=None,
                    help="text|html|pdf|pptx|docx|slides|json (else inferred)")
    ap.add_argument("--title", default="Homework")
    ap.add_argument("--subject", default="general")
    ap.add_argument("--num-questions", type=int, default=4)
    ap.add_argument("--difficulty", default="medium", choices=["easy", "medium", "hard"])
    ap.add_argument("--locale", default="en", help="one of the 14 supported homework locales")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), metavar="DIR",
                    help=f"where to write <id>.assignment.json (default: {DEFAULT_OUT_DIR})")
    # Scan / authorship / grade
    ap.add_argument("--scan", default=None, metavar="FILE",
                    help="OCR a submission file into a Submission JSON")
    ap.add_argument("--authorship", action="store_true",
                    help="print an AI-vs-human authorship signal for a submission")
    ap.add_argument("--grade", default=None, metavar="ASSIGNMENT_JSON",
                    help="autograde a submission against an assignment JSON")
    ap.add_argument("--answers", nargs="*", default=None, metavar="ANSWER",
                    help="explicit per-question answers for --grade")
    ap.add_argument("--submission-text", default=None,
                    help="inline submission text for --grade/--authorship")
    ap.add_argument("--submission-file", default=None, metavar="PATH",
                    help="submission text file for --grade/--authorship")
    ap.add_argument("--handwritten", action="store_true",
                    help="treat the submission as handwritten (OCR hint + authorship prior)")
    ap.add_argument("--expected", type=int, default=None,
                    help="expected answer count for --scan segmentation")
    ap.add_argument("--online", action="store_true",
                    help="with --grade: corroborate open answers against trusted web sources")
    args = ap.parse_args(argv)

    if args.instructions:
        print(INSTRUCTIONS)
        return 0
    if args.scan:
        return _scan(args)
    if args.authorship:
        return _authorship(args)
    if args.grade:
        return _grade(args)
    if args.generate or args.content:
        assignment = _generate(args)
        _emit_assignment(assignment, out_dir=args.out_dir)
        print(assignment.model_dump_json(indent=2))
        return 0

    ap.error("choose a mode: --generate/--content, --scan, --authorship, --grade, or --instructions")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
