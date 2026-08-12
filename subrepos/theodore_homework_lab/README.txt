Theodore Homework Lab (50+ methodologies)
=========================================

Private quality lab wrapping and extending aoep_shared.homework before
promoting richer item types into services/homework.

Registered methodologies (must stay >= 50)
  choice, open, match, media, audio, language, reading, concept, stem,
  social, metacog, drill, game, phonics, speaking, interactive
  — see GET /api/homework/methodologies

Includes
  · multiple choice / multi-select / true-false
  · picture ID, hotspot, video comprehension / timestamps
  · listen & learn, dictation, pronunciation, minimal pairs
  · grammar, spelling, punctuation, vocabulary, idioms
  · translate phrase + translate verse line
  · summarize / paraphrase / inference / claim-evidence
  · matching, ordering, categorize, drag-drop
  · games: scramble, memory match, timed quiz, karaoke fill, hangman
  · classic shared generate path (mcq/short/essay) via /generate/shared-classic

APIs on :8098

Quick check
  PYTHONPATH=subrepos/theodore_homework_lab/src:packages/shared/src \
    python3 -m pytest subrepos/theodore_homework_lab/tests -q
  make homework-lab
