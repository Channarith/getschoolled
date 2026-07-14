homework (AOEP / Salareen)
==========================

What this is
  An offline CLI worker (NOT an HTTP service) over the aoep_shared.homework
  library: generate homework from a lesson, OCR-scan a photographed/handwritten
  submission, run an authorship (AI-vs-student) check, and autograde with
  rationale + citations. The same capabilities are exposed over HTTP by the
  curriculum service at /homework/* for the apps.

Entrypoint
  homework  ->  services/homework/src/homework/run.py   (argparse CLI)
Port
  none (worker)

Common modes
  --generate     build a homework set from a lesson/topic
  --scan         OCR a submission image
  --authorship   estimate whether work is the student's own
  --grade        autograde a submission
  --instructions print usage detail

Run
  python3 services/homework/src/homework/run.py --generate ...
  make homework-generate        make homework-grade
  Output under output/homework/

Test
  cd services/homework && PYTHONPATH=src python -m pytest    # or: make test

See also: services/curriculum (/homework/* HTTP mirror), docs/api-reference.txt.
