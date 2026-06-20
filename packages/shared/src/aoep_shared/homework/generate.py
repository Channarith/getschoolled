"""Homework generation (Phase 6).

Builds an assignment (MCQ + short-answer + an essay prompt) from curriculum
passages, reusing the assessment item generator. Deterministic/offline; an LLM
can author richer items behind the same shapes in production.
"""

from __future__ import annotations

from typing import Dict, List, Sequence

from ..adaptive import Difficulty
from ..assessment import definition_items_from_passages
from .models import Assignment, Question, QuestionType


# Localized prompt + rubric templates for the homework generator.
# 14 fully-translated locales (en + 13). The orchestrator passes
# locale=<student-ui-language> when invoking /homework/generate so the
# student sees prompts in their own language. Falls back to English
# cleanly for unsupported locales.
_PROMPT_I18N: Dict[str, Dict[str, str]] = {
    "en": {
        "short_explain":  "In your own words, explain: {term}.",
        "essay":          "Write a short paragraph connecting the key ideas in this {subject} lesson.",
        "rubric_short_1": "mentions the key idea",
        "rubric_short_2": "accurate",
        "rubric_short_3": "in the student's own words",
        "rubric_essay_1": "covers >=2 concepts",
        "rubric_essay_2": "coherent",
        "rubric_essay_3": "uses correct terminology",
    },
    "es": {
        "short_explain":  "Con tus propias palabras, explica: {term}.",
        "essay":          "Escribe un párrafo breve conectando las ideas clave de esta lección de {subject}.",
        "rubric_short_1": "menciona la idea clave",
        "rubric_short_2": "es preciso",
        "rubric_short_3": "con las propias palabras del estudiante",
        "rubric_essay_1": "cubre >=2 conceptos",
        "rubric_essay_2": "es coherente",
        "rubric_essay_3": "usa la terminología correcta",
    },
    "fr": {
        "short_explain":  "Avec tes propres mots, explique : {term}.",
        "essay":          "Écris un court paragraphe reliant les idées clés de cette leçon de {subject}.",
        "rubric_short_1": "mentionne l'idée clé",
        "rubric_short_2": "exact",
        "rubric_short_3": "avec les propres mots de l'élève",
        "rubric_essay_1": "couvre >=2 concepts",
        "rubric_essay_2": "cohérent",
        "rubric_essay_3": "utilise la terminologie correcte",
    },
    "de": {
        "short_explain":  "Erkläre in eigenen Worten: {term}.",
        "essay":          "Schreibe einen kurzen Absatz, der die Kernideen dieser {subject}-Lektion verbindet.",
        "rubric_short_1": "nennt die Kernidee",
        "rubric_short_2": "korrekt",
        "rubric_short_3": "in eigenen Worten des Schülers",
        "rubric_essay_1": "deckt >=2 Konzepte ab",
        "rubric_essay_2": "kohärent",
        "rubric_essay_3": "verwendet korrekte Begriffe",
    },
    "it": {
        "short_explain":  "Con parole tue, spiega: {term}.",
        "essay":          "Scrivi un breve paragrafo collegando le idee chiave di questa lezione di {subject}.",
        "rubric_short_1": "menziona l'idea chiave",
        "rubric_short_2": "accurato",
        "rubric_short_3": "con le parole dello studente",
        "rubric_essay_1": "copre >=2 concetti",
        "rubric_essay_2": "coerente",
        "rubric_essay_3": "usa la terminologia corretta",
    },
    "pt": {
        "short_explain":  "Com tuas próprias palavras, explica: {term}.",
        "essay":          "Escreve um parágrafo curto ligando as ideias-chave desta aula de {subject}.",
        "rubric_short_1": "menciona a ideia-chave",
        "rubric_short_2": "exato",
        "rubric_short_3": "com as próprias palavras do aluno",
        "rubric_essay_1": "cobre >=2 conceitos",
        "rubric_essay_2": "coerente",
        "rubric_essay_3": "usa a terminologia correta",
    },
    "ru": {
        "short_explain":  "Своими словами объясни: {term}.",
        "essay":          "Напиши короткий абзац, связывающий ключевые идеи этого урока по {subject}.",
        "rubric_short_1": "упоминает ключевую идею",
        "rubric_short_2": "точно",
        "rubric_short_3": "своими словами ученика",
        "rubric_essay_1": "охватывает >=2 понятий",
        "rubric_essay_2": "связно",
        "rubric_essay_3": "использует правильную терминологию",
    },
    "ar": {
        "short_explain":  "\u0628\u0623\u0633\u0644\u0648\u0628\u0643\u060c \u0627\u0634\u0631\u062d\u003a {term}.",
        "essay":          "\u0627\u0643\u062a\u0628 \u0641\u0642\u0631\u0629 \u0642\u0635\u064a\u0631\u0629 \u062a\u0631\u0628\u0637 \u0628\u064a\u0646 \u0627\u0644\u0623\u0641\u0643\u0627\u0631 \u0627\u0644\u0631\u0626\u064a\u0633\u064a\u0629 \u0641\u064a \u062f\u0631\u0633 {subject}.",
        "rubric_short_1": "\u064a\u0630\u0643\u0631 \u0627\u0644\u0641\u0643\u0631\u0629 \u0627\u0644\u0631\u0626\u064a\u0633\u064a\u0629",
        "rubric_short_2": "\u062f\u0642\u064a\u0642",
        "rubric_short_3": "\u0628\u0643\u0644\u0645\u0627\u062a \u0627\u0644\u0637\u0627\u0644\u0628 \u0627\u0644\u062e\u0627\u0635\u0629",
        "rubric_essay_1": "\u064a\u063a\u0637\u064a \u0645\u0641\u0647\u0648\u0645\u064a\u0646 \u0639\u0644\u0649 \u0627\u0644\u0623\u0642\u0644",
        "rubric_essay_2": "\u0645\u062a\u0631\u0627\u0628\u0637",
        "rubric_essay_3": "\u064a\u0633\u062a\u062e\u062f\u0645 \u0627\u0644\u0645\u0635\u0637\u0644\u062d\u0627\u062a \u0627\u0644\u0635\u062d\u064a\u062d\u0629",
    },
    "hi": {
        "short_explain":  "\u0905\u092a\u0928\u0947 \u0936\u092c\u094d\u0926\u094b\u0902 \u092e\u0947\u0902 \u0938\u092e\u091d\u093e\u090f\u0902\u003a {term}.",
        "essay":          "\u0907\u0938 {subject} \u092a\u093e\u0920 \u0915\u0947 \u092e\u0941\u0916\u094d\u092f \u0935\u093f\u091a\u093e\u0930\u094b\u0902 \u0915\u094b \u091c\u094b\u0921\u093c\u0924\u0947 \u0939\u0941\u090f \u090f\u0915 \u091b\u094b\u091f\u093e \u0905\u0928\u0941\u091a\u094d\u091b\u0947\u0926 \u0932\u093f\u0916\u0947\u0902\u0964",
        "rubric_short_1": "\u092e\u0941\u0916\u094d\u092f \u0935\u093f\u091a\u093e\u0930 \u0915\u093e \u0909\u0932\u094d\u0932\u0947\u0916 \u0939\u094b",
        "rubric_short_2": "\u0938\u091f\u0940\u0915",
        "rubric_short_3": "\u091b\u093e\u0924\u094d\u0930 \u0915\u0947 \u0905\u092a\u0928\u0947 \u0936\u092c\u094d\u0926\u094b\u0902 \u092e\u0947\u0902",
        "rubric_essay_1": ">=2 \u0905\u0935\u0927\u093e\u0930\u0923\u093e\u090f\u0901",
        "rubric_essay_2": "\u0938\u0941\u0938\u0902\u0917\u0924",
        "rubric_essay_3": "\u0938\u0939\u0940 \u0936\u092c\u094d\u0926\u093e\u0935\u0932\u0940",
    },
    "zh": {
        "short_explain":  "\u7528\u4f60\u81ea\u5df1\u7684\u8bdd\u89e3\u91ca\uff1a{term}\u3002",
        "essay":          "\u5199\u4e00\u4e2a\u7b80\u77ed\u7684\u6bb5\u843d\uff0c\u5c06\u672c\u8282{subject}\u8bfe\u4e2d\u7684\u5173\u952e\u601d\u60f3\u8054\u7cfb\u8d77\u6765\u3002",
        "rubric_short_1": "\u63d0\u53ca\u5173\u952e\u8981\u70b9",
        "rubric_short_2": "\u51c6\u786e",
        "rubric_short_3": "\u7528\u5b66\u751f\u81ea\u5df1\u7684\u8bdd",
        "rubric_essay_1": "\u8986\u76d6 >=2 \u4e2a\u6982\u5ff5",
        "rubric_essay_2": "\u8fde\u8d2f",
        "rubric_essay_3": "\u4f7f\u7528\u6b63\u786e\u672f\u8bed",
    },
    "ja": {
        "short_explain":  "\u81ea\u5206\u306e\u8a00\u8449\u3067\u8aac\u660e\u3057\u3066\u304f\u3060\u3055\u3044\uff1a{term}\u3002",
        "essay":          "\u3053\u306e{subject}\u306e\u30ec\u30c3\u30b9\u30f3\u306e\u4e3b\u8981\u306a\u8003\u3048\u3092\u3064\u306a\u3050\u77ed\u3044\u6bb5\u843d\u3092\u66f8\u3044\u3066\u304f\u3060\u3055\u3044\u3002",
        "rubric_short_1": "\u4e3b\u8981\u30dd\u30a4\u30f3\u30c8\u306b\u8a00\u53ca",
        "rubric_short_2": "\u6b63\u78ba",
        "rubric_short_3": "\u751f\u5f92\u81ea\u8eab\u306e\u8a00\u8449\u3067",
        "rubric_essay_1": "2\u3064\u4ee5\u4e0a\u306e\u6982\u5ff5\u3092\u30ab\u30d0\u30fc",
        "rubric_essay_2": "\u4e00\u8cab\u6027\u304c\u3042\u308b",
        "rubric_essay_3": "\u6b63\u3057\u3044\u7528\u8a9e\u3092\u4f7f\u7528",
    },
    "ko": {
        "short_explain":  "\uc790\uc2e0\uc758 \ub9d0\ub85c \uc124\uba85\ud558\uc138\uc694: {term}.",
        "essay":          "\uc774 {subject} \uc218\uc5c5\uc758 \ud575\uc2ec \uc544\uc774\ub514\uc5b4\ub97c \uc5f0\uacb0\ud558\ub294 \uc9e7\uc740 \ub2e8\ub77d\uc744 \uc4f0\uc138\uc694.",
        "rubric_short_1": "\ud575\uc2ec \uc544\uc774\ub514\uc5b4 \uc5b8\uae09",
        "rubric_short_2": "\uc815\ud655\ud568",
        "rubric_short_3": "\ud559\uc0dd \uc790\uc2e0\uc758 \ub9d0\ub85c",
        "rubric_essay_1": "2\uac1c \uc774\uc0c1\uc758 \uac1c\ub150\uc744 \ub2e4\ub8e8\uae30",
        "rubric_essay_2": "\uc77c\uad00\uc131",
        "rubric_essay_3": "\uc62c\ubc14\ub978 \uc6a9\uc5b4 \uc0ac\uc6a9",
    },
    "vi": {
        "short_explain":  "Hãy dùng lời của em để giải thích: {term}.",
        "essay":          "Viết một đoạn ngắn nối kết các ý chính trong bài học {subject} này.",
        "rubric_short_1": "đề cập ý chính",
        "rubric_short_2": "chính xác",
        "rubric_short_3": "bằng lời của học sinh",
        "rubric_essay_1": "đề cập >=2 khái niệm",
        "rubric_essay_2": "mạch lạc",
        "rubric_essay_3": "dùng đúng thuật ngữ",
    },
    "km": {
        "short_explain":  "\u179f\u17bc\u1798\u1796\u1793\u17d2\u1799\u179b\u17cb\u178a\u17c4\u1799\u1796\u17b6\u1780\u17d2\u1799\u179a\u1794\u179f\u17cb\u17a2\u17d2\u1793\u1780\u17d4 \u003a {term}\u17d4",
        "essay":          "\u179f\u17bc\u1798\u179f\u179a\u179f\u17c1\u179a\u1780\u1795\u17d2\u1793\u17c2\u1780\u1781\u17d2\u179b\u17b8\u1798\u17bd\u1799\u178a\u17c4\u1799\u1791\u17b6\u1780\u17cb\u1791\u1784\u178f\u17b6\u1798\u1782\u17c6\u1793\u17b7\u178f\u179f\u17c6\u1781\u17b6\u1793\u17cb\u200b\u200b\u200b\u17c3\u1796\u17b8\u1798\u17c1\u179a\u17c0\u1793 {subject} \u1793\u17c1\u17c7\u17d4",
        "rubric_short_1": "\u1794\u17b6\u1793\u1794\u1784\u17d2\u17a0\u17b6\u1789\u1782\u17c6\u1793\u17b7\u178f\u179f\u17c6\u1781\u17b6\u1793\u17cb",
        "rubric_short_2": "\u178f\u17d2\u179a\u17ba\u1798\u178f\u17d2\u179a\u17bc\u179c",
        "rubric_short_3": "\u178f\u17b6\u1798\u1796\u17b6\u1780\u17d2\u1799\u179a\u1794\u179f\u17cb\u179f\u17b7\u179f\u17d2\u179f\u1781\u17d2\u179b\u17bd\u1793",
        "rubric_essay_1": "\u179a\u17c0\u1794\u179a\u17b6\u1794\u17cb\u1782\u17c6\u1793\u17b7\u178f >=2",
        "rubric_essay_2": "\u179f\u1798\u17a0\u17c1\u178f\u17bb\u1795\u179b",
        "rubric_essay_3": "\u1794\u17d2\u179a\u17be\u1796\u17b6\u1780\u17d2\u1799\u179f\u17c6\u178e\u17bd\u179b\u178f\u17d2\u179a\u17ba\u1798\u178f\u17d2\u179a\u17bc\u179c",
    },
}


SUPPORTED_HOMEWORK_LOCALES: tuple[str, ...] = tuple(_PROMPT_I18N.keys())


def _norm_locale(locale: str) -> str:
    base = (locale or "en").lower().split("-")[0].split("_")[0]
    return base if base in _PROMPT_I18N else "en"


def _hwt(key: str, locale: str, **fmt) -> str:
    """Localized template lookup, English fallback."""
    table = _PROMPT_I18N.get(_norm_locale(locale)) or _PROMPT_I18N["en"]
    tpl = table.get(key) or _PROMPT_I18N["en"].get(key) or key
    try:
        return tpl.format(**fmt)
    except (KeyError, IndexError):
        return tpl


def _split(passage: str):
    if ":" in passage:
        term, body = passage.split(":", 1)
        return term.strip(), body.strip()
    return None


def generate_assignment(
    passages: Sequence[str],
    *,
    title: str,
    subject: str = "general",
    source: str = "",
    num_questions: int = 4,
    difficulty: Difficulty = Difficulty.MEDIUM,
    locale: str = "en",
) -> Assignment:
    """Generate an assignment localized for the student's UI language.

    Short-answer + essay prompts and rubrics render in ``locale`` when
    it's one of the 14 supported homework locales (English fallback
    otherwise). MCQ stems still come from the assessment generator
    upstream, which is English-only today; an LLM author can wrap the
    MCQ pass to fully localize multiple-choice items in production.
    """
    questions: List[Question] = []

    # MCQs from the assessment generator (definition checks).
    mcqs = definition_items_from_passages(
        list(passages), subject, max_items=max(1, num_questions // 2), difficulty=difficulty
    )
    for item in mcqs:
        questions.append(Question(
            type=QuestionType.MCQ, topic=item.topic, prompt=item.prompt,
            options=item.options, answer_index=item.answer_index, difficulty=difficulty,
        ))

    rubric_short = [_hwt(k, locale) for k in ("rubric_short_1", "rubric_short_2", "rubric_short_3")]
    rubric_essay = [_hwt(k, locale) for k in ("rubric_essay_1", "rubric_essay_2", "rubric_essay_3")]

    # Short-answer questions from term/definition passages.
    for passage in passages:
        if len(questions) >= num_questions:
            break
        parsed = _split(passage)
        if not parsed:
            continue
        term, definition = parsed
        questions.append(Question(
            type=QuestionType.SHORT, topic=term,
            prompt=_hwt("short_explain", locale, term=term),
            answer_key=definition,
            rubric=rubric_short,
            difficulty=difficulty,
        ))

    # One essay prompt to round it out.
    if passages:
        questions.append(Question(
            type=QuestionType.ESSAY, topic=subject,
            prompt=_hwt("essay", locale, subject=subject),
            rubric=rubric_essay,
            difficulty=difficulty,
        ))

    return Assignment(title=title, subject=subject, source=source, questions=questions)


def assignment_from_slides(slides, *, title: str, subject: str = "general",
                           source: str = "", num_questions: int = 4,
                           locale: str = "en") -> Assignment:
    """slides: objects/dicts with .title/.body (or ['title']/['body'])."""
    passages = []
    for s in slides:
        st = getattr(s, "title", None) if not isinstance(s, dict) else s.get("title")
        sb = getattr(s, "body", None) if not isinstance(s, dict) else s.get("body")
        if st:
            passages.append(f"{st}: {sb or ''}")
    return generate_assignment(passages, title=title, subject=subject, source=source,
                               num_questions=num_questions, locale=locale)
