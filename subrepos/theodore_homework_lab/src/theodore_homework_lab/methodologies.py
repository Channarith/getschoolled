"""Registry of 50+ homework methodologies for the Theodore homework quality lab."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Tuple


class GradingMode(str, Enum):
    OBJECTIVE = "objective"  # exact / set / order match
    FUZZY = "fuzzy"  # token overlap / normalized string
    RUBRIC = "rubric"  # multi-criterion soft score
    MEDIA = "media"  # media-aware (still offline-scorable via keys)
    INTERACTIVE = "interactive"  # drag/hotspot/game state keys


@dataclass(frozen=True)
class Methodology:
    id: str
    family: str
    label: str
    grading_mode: GradingMode
    description: str = ""


# Keep this list the single source of truth (must stay >= 50).
_SPECS: Tuple[Tuple[str, str, str, GradingMode, str], ...] = (
    ("mcq", "choice", "Multiple choice", GradingMode.OBJECTIVE,
     "Pick one option from a fixed set."),
    ("multi_select", "choice", "Select all that apply", GradingMode.OBJECTIVE,
     "Select every correct option; partial credit by Jaccard."),
    ("true_false", "choice", "True / false", GradingMode.OBJECTIVE,
     "Binary factual judgment."),
    ("yes_no_explain", "choice", "Yes/No with justification", GradingMode.RUBRIC,
     "Binary choice plus a short justification against a rubric."),
    ("short_answer", "open", "Short answer", GradingMode.FUZZY,
     "One-sentence answer graded by token overlap with a key."),
    ("essay", "open", "Essay / long response", GradingMode.RUBRIC,
     "Paragraph response scored on rubric criteria."),
    ("fill_blank", "open", "Fill in the blank", GradingMode.FUZZY,
     "Complete a missing word or short phrase."),
    ("cloze", "open", "Cloze passage", GradingMode.FUZZY,
     "Several blanks in a passage; answers joined by |."),
    ("matching", "match", "Matching pairs", GradingMode.OBJECTIVE,
     "Map left items to right items (A->1 style)."),
    ("ordering", "match", "Sequence / ordering", GradingMode.OBJECTIVE,
     "Put steps or events in correct order."),
    ("categorize", "match", "Classify into categories", GradingMode.OBJECTIVE,
     "Assign each item to a category bucket."),
    ("picture_id", "media", "Picture identification", GradingMode.OBJECTIVE,
     "Name what a picture shows (keyed label)."),
    ("picture_label", "media", "Label the picture parts", GradingMode.FUZZY,
     "Label named regions of a diagram."),
    ("image_describe", "media", "Describe an image", GradingMode.RUBRIC,
     "Write a description covering required visual details."),
    ("hotspot", "media", "Click / hotspot on image", GradingMode.OBJECTIVE,
     "Select the correct hotspot id on an image."),
    ("video_comprehension", "media", "Video comprehension", GradingMode.FUZZY,
     "Answer questions about a video clip."),
    ("video_timestamp", "media", "Video timestamp quiz", GradingMode.OBJECTIVE,
     "Identify the correct timestamp / segment id."),
    ("listen_comprehension", "audio", "Listen and learn (comprehension)", GradingMode.FUZZY,
     "Answer after hearing a short narration."),
    ("listen_dictation", "audio", "Listen and write (dictation)", GradingMode.FUZZY,
     "Transcribe what was heard."),
    ("listen_choose", "audio", "Listen and choose", GradingMode.OBJECTIVE,
     "Choose the option that matches the audio."),
    ("pronunciation", "audio", "Pronunciation accuracy", GradingMode.FUZZY,
     "Score a pronunciation transcript against a target phrase."),
    ("minimal_pairs", "audio", "Minimal-pair discrimination", GradingMode.OBJECTIVE,
     "Choose which of two similar words was heard."),
    ("echo_repeat", "audio", "Listen and echo / sing-back", GradingMode.FUZZY,
     "Repeat a line; grade by transcript overlap."),
    ("spelling", "language", "Spelling", GradingMode.OBJECTIVE,
     "Spell the prompted word exactly."),
    ("grammar_correct", "language", "Grammar correction", GradingMode.FUZZY,
     "Rewrite the sentence with correct grammar."),
    ("grammar_error_id", "language", "Identify the grammar error", GradingMode.OBJECTIVE,
     "Pick which option contains / is the error."),
    ("punctuation_fix", "language", "Punctuation fix", GradingMode.FUZZY,
     "Restore correct punctuation."),
    ("capitalization", "language", "Capitalization", GradingMode.OBJECTIVE,
     "Capitalize correctly."),
    ("sentence_reorder", "language", "Reorder the sentence", GradingMode.OBJECTIVE,
     "Reorder scrambled words into a grammatical sentence."),
    ("vocabulary_context", "language", "Vocabulary in context", GradingMode.OBJECTIVE,
     "Choose the meaning that fits the sentence."),
    ("idiom_meaning", "language", "Idiom / slang meaning", GradingMode.FUZZY,
     "Explain or choose the meaning of an idiom."),
    ("translate_phrase", "language", "Translate a phrase", GradingMode.FUZZY,
     "Translate a short phrase into the target language."),
    ("translate_verse", "language", "Translate phrase from a verse", GradingMode.FUZZY,
     "Translate a line from a song verse into meaning/target language."),
    ("paraphrase", "language", "Paraphrase", GradingMode.RUBRIC,
     "Restate in own words covering key ideas."),
    ("summarize", "language", "Summarize", GradingMode.RUBRIC,
     "Condense a passage to main points."),
    ("main_idea", "reading", "Main idea", GradingMode.FUZZY,
     "State or choose the main idea."),
    ("detail_find", "reading", "Find the detail", GradingMode.FUZZY,
     "Locate a specific detail from the text."),
    ("inference", "reading", "Inferencing", GradingMode.RUBRIC,
     "Draw a supported inference."),
    ("reading_comprehension", "reading", "Reading comprehension set", GradingMode.FUZZY,
     "Answer a comprehension question about a passage."),
    ("identification", "concept", "Term / concept identification", GradingMode.FUZZY,
     "Identify the concept described."),
    ("definition_match", "concept", "Definition matching", GradingMode.OBJECTIVE,
     "Match terms to definitions."),
    ("analogy", "concept", "Analogy completion", GradingMode.FUZZY,
     "Complete A is to B as C is to ?"),
    ("cause_effect", "concept", "Cause and effect", GradingMode.FUZZY,
     "Identify cause or effect."),
    ("compare_contrast", "concept", "Compare and contrast", GradingMode.RUBRIC,
     "Explain similarities and differences."),
    ("claim_evidence", "concept", "Claim + evidence", GradingMode.RUBRIC,
     "Support a claim with evidence from the source."),
    ("problem_solve", "stem", "Problem solving (steps)", GradingMode.FUZZY,
     "Solve a multi-step problem; final answer keyed."),
    ("show_work", "stem", "Show your work", GradingMode.RUBRIC,
     "Explain reasoning steps against a rubric."),
    ("graph_interpret", "stem", "Interpret a graph / chart", GradingMode.FUZZY,
     "Read a value or trend from a graph description."),
    ("data_table", "stem", "Read a data table", GradingMode.FUZZY,
     "Extract a value from tabular data."),
    ("formula_apply", "stem", "Apply a formula", GradingMode.OBJECTIVE,
     "Compute a numeric result from a formula."),
    ("procedure_steps", "stem", "Procedure / lab steps", GradingMode.OBJECTIVE,
     "Order or select correct procedure steps."),
    ("code_trace", "stem", "Trace code output", GradingMode.OBJECTIVE,
     "Predict printed output of a snippet."),
    ("code_complete", "stem", "Complete the code", GradingMode.FUZZY,
     "Fill the missing code fragment."),
    ("timeline_place", "social", "Place on a timeline", GradingMode.OBJECTIVE,
     "Place an event at the correct timeline slot."),
    ("map_locate", "social", "Locate on a map", GradingMode.OBJECTIVE,
     "Choose the correct map region / coordinate id."),
    ("cite_source", "social", "Cite the source", GradingMode.FUZZY,
     "Produce a correct citation fragment."),
    ("debate_stance", "social", "Debate stance paragraph", GradingMode.RUBRIC,
     "Argue a stance with reasons."),
    ("roleplay_dialogue", "social", "Role-play dialogue", GradingMode.RUBRIC,
     "Write turns that fit a scenario."),
    ("reflection_journal", "metacog", "Reflection journal", GradingMode.RUBRIC,
     "Reflect on learning with required elements."),
    ("peer_review", "metacog", "Peer-review checklist", GradingMode.RUBRIC,
     "Complete a structured peer-review."),
    ("flashcard_recall", "drill", "Flashcard recall (produce)", GradingMode.FUZZY,
     "Produce the answer side of a flashcard."),
    ("flashcard_recognize", "drill", "Flashcard recognition (choose)", GradingMode.OBJECTIVE,
     "Choose the correct flashcard face."),
    ("word_scramble", "game", "Word scramble", GradingMode.OBJECTIVE,
     "Unscramble letters into the target word."),
    ("memory_match", "game", "Memory match game", GradingMode.OBJECTIVE,
     "Submit correct pair matches."),
    ("timed_quiz", "game", "Timed quiz race", GradingMode.OBJECTIVE,
     "Fast MCQ; same keying as mcq with time metadata."),
    ("hangman_style", "game", "Hangman-style letter guess", GradingMode.OBJECTIVE,
     "Guess letters / word within attempt budget."),
    ("karaoke_fill", "game", "Karaoke / lyric line fill", GradingMode.FUZZY,
     "Fill the missing lyric/line from a verse."),
    ("syllable_count", "phonics", "Count the syllables", GradingMode.OBJECTIVE,
     "Report syllable count for a word."),
    ("tone_mark", "phonics", "Tone / stress marking", GradingMode.FUZZY,
     "Mark tone or primary stress."),
    ("oral_response", "speaking", "Oral response (transcript)", GradingMode.RUBRIC,
     "Grade a spoken answer via transcript + rubric."),
    ("media_caption", "media", "Write a media caption", GradingMode.RUBRIC,
     "Caption an image/video with required facts."),
    ("alt_text", "media", "Write accessibility alt text", GradingMode.RUBRIC,
     "Write concise alt text covering key visual facts."),
    ("safety_check", "stem", "Safety check / hazard ID", GradingMode.OBJECTIVE,
     "Identify the hazard or correct safety action."),
    ("drag_drop", "interactive", "Drag and drop assembly", GradingMode.INTERACTIVE,
     "Submit final slot→item mapping."),
    ("crossword_clue", "game", "Crossword clue answer", GradingMode.FUZZY,
     "Answer a crossword-style clue."),
)

assert len(_SPECS) >= 50, f"Need >=50 methodologies, got {len(_SPECS)}"

METHODOLOGIES: Dict[str, Methodology] = {
    mid: Methodology(
        id=mid,
        family=family,
        label=label,
        grading_mode=mode,
        description=desc,
    )
    for mid, family, label, mode, desc in _SPECS
}

METHODOLOGY_IDS: List[str] = list(METHODOLOGIES.keys())


def get_methodology(method_id: str) -> Methodology:
    key = (method_id or "").strip().lower()
    if key not in METHODOLOGIES:
        raise KeyError(
            f"Unknown methodology '{method_id}'. "
            f"Known ({len(METHODOLOGIES)}): {', '.join(METHODOLOGY_IDS[:8])}…"
        )
    return METHODOLOGIES[key]


def list_methodologies(*, family: str = "") -> List[Methodology]:
    rows = list(METHODOLOGIES.values())
    if family:
        fam = family.strip().lower()
        rows = [m for m in rows if m.family == fam]
    return rows


def methodology_count() -> int:
    return len(METHODOLOGIES)
