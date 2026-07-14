harvester (AOEP / Salareen)
===========================

What this is
  A long-running CLI worker (NOT an HTTP service) that crawls / ingests source
  material and generates catalog-ready courses over the aoep_shared.harvest
  pipeline: scrape -> compose (PCS) -> score/tag -> partition into lesson-sized
  decks -> export. Every run MUST write a .pptx alongside *.course.json (the
  narration rides in the slide speaker notes). It can post generated decks to the
  curriculum service and keep a corpus for RAG.

Entrypoint
  harvester  ->  services/harvester/src/harvester/run.py   (argparse CLI)
Port
  none (worker; in compose it has no published ports)

Common modes
  --crawl        crawl configured sources on a schedule
  --once         one crawl pass and exit
  --generate     generate a course from a local file / DB / prompt
  --critique     run the critique/improve loop
  --corpus-search  query the harvest RAG corpus
  --instructions   print the full live generation recipe

Run
  python3 services/harvester/src/harvester/run.py --once ...
  make harvest-crawl            make harvest-crawl-daemon      make harvest-search
  # PPTX export needs python-pptx: pip install -e 'packages/shared[harvest]'

Output
  output/harvest/courses/<course_id>/   (*.course.json + *.pptx)
  Present a course: python3 scripts/present_course.py <path/*.course.json> --with-media

Test
  cd services/harvester && PYTHONPATH=src python -m pytest    # or: make test

See also: services/harvester/RUNBOOK.txt (operational guide),
.cursor/skills/harvester-content.
