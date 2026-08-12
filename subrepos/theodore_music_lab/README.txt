Theodore Music Lab (learn through songs)
========================================

Private quality lab for line-by-line song learning before promoting into
language_learning / content packs.

  • 100+ original / Suno-style educational songs (data/songs.jsonl)
  • Play → pause → repeat per line; continuous mode skips the pause gate
  • Meaning / translation hints for 26+ platform languages
  • Import schema for additional original packs (JSON/JSONL)

APIs on :8097 — see /health and /api/music/*

Quick check
  PYTHONPATH=subrepos/theodore_music_lab/src:packages/shared/src \
    python3 -m pytest subrepos/theodore_music_lab/tests -q
