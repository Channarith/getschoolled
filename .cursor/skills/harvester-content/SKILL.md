---
name: harvester-content
description: How the harvester ingests course material (online crawl or local files) and turns it into reviewable, catalog-ready courses split into lesson-sized decks. Use for scraping/crawling OER, generating a course from a PDF/HTML/DB, slides/lessons, the .pptx export requirement, the harvest corpus/RAG, or partitioning oversized material into "Lesson N" chunks. A lesson targets ~20-30 minutes (~20 slides); big sources must be partitioned, never one 1000-slide deck.
---

# Harvester content pipeline

## Entry points
- Worker CLI: `services/harvester/src/harvester/run.py` — `--generate <file>` (local),
  `--crawl --topic/--seeds` (online, `--daemon` for 24/7), `--critique`,
  `--corpus-search`. Shared engine: `packages/shared/src/aoep_shared/harvest/`.
- Pipeline per source: `extract` (extractors.py) → `generate_course` (generate.py)
  → **partition into lessons** → `export_course_package` (export.py, writes
  `.course.json` + REQUIRED `.pptx`) → catalog/corpus (`corpus_store.py`) +
  knowledge packs (`knowledge_bridge.py`). Online path: `crawl.py::_process_record`.

## Lesson partitioning (do not emit giant decks)
`generate_course` builds one slide per input section, which can explode to 100s-1000s
of slides for a big page/file — far too much for one lesson. Use
`partition_course_into_lessons(course, max_slides=MAX_SLIDES_PER_LESSON)` (generate.py):
- `MAX_SLIDES_PER_LESSON = 20` (target ≈ 30 min), hard ceiling 40.
- Splits into evenly-balanced lessons titled `"<title> — Lesson i of N"` (no tiny
  trailing stub; 43 slides → 15/14/14), each with its own `course_id`, rebuilt
  composition, and `lesson_index`/`lesson_count`. Courses at/under the cap stay a
  single lesson unchanged. `generate_lessons(doc, ...)` = generate + partition.
- Both run paths honor it: file path uses `--max-slides-per-lesson` (one output
  dir per lesson); crawl exports + catalogs each lesson (`lesson_index`/`_count`),
  keeping source-level corpus indexing once per URL.

## Hard rules
- **Every run must write a `.pptx`** alongside `*.course.json` (narration in
  speaker notes). `export_course_package(..., write_pptx=True)` is mandatory;
  needs `python-pptx` (`pip install -e 'packages/shared[harvest]'`). Crawl output:
  `output/harvest/courses/<course_id>/`. Present: `python3 scripts/present_course.py
  <*.course.json> --with-media`.
- Content packs (`aoep_shared/content_packs.py`) grow knowledge/slang/scenarios/
  courses by dropping JSON/JSONL files — no code change.

## Tests
`packages/shared/tests/test_harvest_*.py` (incl. `test_harvest_partition.py`).
Construct a `GeneratedCourse` with N `GeneratedSlide`s and assert the partition
count/balance/titles. E2E: run `run.py --generate` on a many-section file and
confirm multiple `lesson-NN/` output dirs.
