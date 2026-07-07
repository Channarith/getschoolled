"""Training narration content for spoken lesson bodies.

Drive Mode and audio courses use this module for *spoken* lesson bodies
(key facts and generic segments). UI chrome (categories, levels) still
comes from :mod:`catalog_i18n`; this layer covers the training text that
TTS reads aloud.

Training locales now span the full platform set (see
:data:`aoep_shared.languages.SUPPORTED_LANGUAGES`). A locale is served with
authentic, human-authored content when a curated fact set exists (English,
Spanish, Chinese today) and otherwise via a pluggable body translator
(register one with :func:`set_body_translator`, e.g. NLLB-200 behind the
SpeechProvider). When no curated content and no translator are available the
body gracefully falls back to English text with ``body_locale == "en"`` so the
client always narrates with a voice that matches the actual text language.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from .languages import SUPPORTED_LANGUAGES

# Every platform-supported language can be requested as a training (spoken)
# locale. Delivery is authentic where curated content or a translator exists,
# English-fallback otherwise (see module docstring).
TRAINING_LOCALES: tuple[str, ...] = tuple(SUPPORTED_LANGUAGES)
DEFAULT_TRAINING_LOCALE = "en"

# Locales with fully-curated, hand-authored spoken content in this module.
CURATED_TRAINING_LOCALES: tuple[str, ...] = ("en", "es", "zh")

# Localized "(audio)" title suffix; unlisted locales use the neutral default.
_AUDIO_SUFFIX: Dict[str, str] = {
    "en": "(audio)", "es": "(audio)", "zh": "（音频）", "ja": "（音声）",
    "ko": "(오디오)", "ar": "(صوت)", "ru": "(аудио)", "el": "(ήχος)",
}


def normalize_training_locale(locale: Optional[str]) -> str:
    """Map UI or user choice to a supported training locale.

    Any of the platform-supported languages is accepted; anything else
    collapses to English.
    """
    if not locale:
        return DEFAULT_TRAINING_LOCALE
    base = locale.lower().split("-")[0].split("_")[0]
    if base in SUPPORTED_LANGUAGES:
        return base
    return DEFAULT_TRAINING_LOCALE


def audio_title_suffix(locale: str) -> str:
    loc = normalize_training_locale(locale)
    return _AUDIO_SUFFIX.get(loc, "(audio)")


# --------------------------------------------------------------------------- #
# Pluggable body translator.
#
# Curated content covers a few locales with authentic text. To speak the full
# catalog in every supported language, a deployment can register a translator
# (source English -> target locale), e.g. one backed by NLLB-200 via the
# SpeechProvider. It is optional: offline / when unset, bodies fall back to
# English and ``body_locale`` reports ``en`` so the voice matches the text.
# --------------------------------------------------------------------------- #
BodyTranslator = Callable[[str, str, str], Optional[str]]  # (text, source, target)

_body_translator: Optional[BodyTranslator] = None
_translator_disabled = False


def set_body_translator(fn: Optional[BodyTranslator]) -> None:
    """Register (or clear) the spoken-body translator used for uncurated locales."""
    global _body_translator, _translator_disabled
    _body_translator = fn
    _translator_disabled = False


def has_body_translator() -> bool:
    return _body_translator is not None and not _translator_disabled


def translate_body(text: str, target: str, *, source: str = "en") -> Optional[str]:
    """Translate one spoken-body string; ``None`` when unavailable.

    Never raises: a translator that is missing, disabled, or fails (including
    ``NotImplementedError`` when no MT model is loaded) simply yields ``None``
    so callers fall back to the English body. The first hard failure disables
    further attempts to avoid hammering an unavailable backend.
    """
    global _translator_disabled
    target = normalize_training_locale(target)
    if (
        not text
        or not text.strip()
        or target == source
        or _translator_disabled
        or _body_translator is None
    ):
        return None
    try:
        out = _body_translator(text, source, target)
    except NotImplementedError:
        _translator_disabled = True
        return None
    except Exception:
        return None
    return out or None


# English canonical title -> {es, zh}
COURSE_TITLES: Dict[str, Dict[str, str]] = {
    "Budgeting Basics": {
        "es": "Fundamentos del presupuesto",
        "zh": "预算基础",
    },
    "How Compound Interest Works": {
        "es": "Cómo funciona el interés compuesto",
        "zh": "复利如何运作",
    },
    "An Introduction to Stoicism": {
        "es": "Introducción al estoicismo",
        "zh": "斯多葛主义入门",
    },
    "What Is Artificial Intelligence": {
        "es": "Qué es la inteligencia artificial",
        "zh": "什么是人工智能",
    },
    "The Pomodoro Technique": {
        "es": "La técnica Pomodoro",
        "zh": "番茄工作法",
    },
    "Photosynthesis Explained": {
        "es": "La fotosíntesis explicada",
        "zh": "光合作用详解",
    },
}

# English canonical title -> locale -> fact bullets (spoken key ideas)
COURSE_FACTS: Dict[str, Dict[str, List[str]]] = {
    "Budgeting Basics": {
        "en": [
            "A budget is simply a plan for your money: income in, expenses out, the rest saved.",
            "A popular rule is fifty-thirty-twenty - needs, wants, and savings or debt.",
            "Track spending for one month and you'll quickly spot easy places to cut.",
        ],
        "es": [
            "Un presupuesto es un plan para tu dinero: entradas, gastos y lo que sobra se ahorra.",
            "Una regla popular es cincuenta-treinta-veinte: necesidades, deseos y ahorro o deudas.",
            "Registra tus gastos un mes y verás rápido dónde puedes recortar.",
        ],
        "zh": [
            "预算就是钱的计划：收入进来，支出出去，剩下的存起来。",
            "常用规则是五三二：需要、想要，以及储蓄或还债。",
            "记录一个月的开销，你很快就会发现容易削减的地方。",
        ],
    },
    "How Compound Interest Works": {
        "en": [
            "Compound interest means you earn interest on your interest, not just your deposit.",
            "Time is the magic ingredient - starting early beats investing more later.",
            "The rule of seventy-two estimates years to double: divide seventy-two by the rate.",
        ],
        "es": [
            "El interés compuesto significa ganar interés sobre el interés, no solo sobre el depósito.",
            "El tiempo es clave: empezar pronto supera invertir más tarde.",
            "La regla del setenta y dos estima cuántos años para duplicar: divide setenta y dos entre la tasa.",
        ],
        "zh": [
            "复利意味着利息生利息，而不只是本金生息。",
            "时间是关键——早开始比晚点多投更有效。",
            "七十二法则估算翻倍年数：用七十二除以利率。",
        ],
    },
    "An Introduction to Stoicism": {
        "en": [
            "Stoicism teaches focusing only on what you can control - your actions and judgments.",
            "Negative events are neutral; our opinions about them cause distress.",
            "A daily practice is to rehearse challenges calmly before they happen.",
        ],
        "es": [
            "El estoicismo enseña a centrarse solo en lo que controlas: tus actos y juicios.",
            "Los eventos negativos son neutros; lo que nos angustia son nuestras opiniones.",
            "Una práctica diaria es ensayar con calma los retos antes de que ocurran.",
        ],
        "zh": [
            "斯多葛主义教你只关注能控制的事——你的行为和判断。",
            "负面事件本身是中性的；是我们的看法带来痛苦。",
            "每日练习是在挑战发生前平静地预演它们。",
        ],
    },
    "What Is Artificial Intelligence": {
        "en": [
            "A.I. is software that learns patterns from data instead of being explicitly programmed.",
            "Machine learning improves with more examples, much like practice.",
            "Today's large language models predict the next word to generate helpful text.",
        ],
        "es": [
            "La I.A. es software que aprende patrones de datos en lugar de programarse paso a paso.",
            "El aprendizaje automático mejora con más ejemplos, como la práctica.",
            "Los grandes modelos de lenguaje predicen la siguiente palabra para generar texto útil.",
        ],
        "zh": [
            "人工智能是从数据中学习模式的软件，而不是逐步硬编码。",
            "机器学习像练习一样，例子越多越进步。",
            "当今的大语言模型通过预测下一个词来生成有用的文本。",
        ],
    },
    "The Pomodoro Technique": {
        "en": [
            "Work in focused twenty-five minute sprints called pomodoros.",
            "Take a five minute break after each, and a longer break every four.",
            "It beats procrastination by making starting feel small and finite.",
        ],
        "es": [
            "Trabaja en sprints de veinticinco minutos llamados pomodoros.",
            "Descansa cinco minutos después de cada uno y más tiempo cada cuatro.",
            "Vence la procrastinación porque empezar se siente pequeño y acotado.",
        ],
        "zh": [
            "以二十五分钟的专注冲刺（一个番茄钟）来工作。",
            "每个番茄钟后休息五分钟，每四个番茄钟休息更久。",
            "它让开始变得小而有限，从而战胜拖延。",
        ],
    },
    "Photosynthesis Explained": {
        "en": [
            "Plants turn sunlight, water, and carbon dioxide into sugar and oxygen.",
            "Chlorophyll in the leaves captures the light energy.",
            "This process is the foundation of almost every food chain on Earth.",
        ],
        "es": [
            "Las plantas convierten luz, agua y dióxido de carbono en azúcar y oxígeno.",
            "La clorofila en las hojas captura la energía lumínica.",
            "Este proceso sustenta casi todas las cadenas alimentarias en la Tierra.",
        ],
        "zh": [
            "植物把阳光、水和二氧化碳变成糖和氧气。",
            "叶子里的叶绿素捕获光能。",
            "这个过程是地球上几乎整条食物链的基础。",
        ],
    },
}


def localize_course_title(title_en: str, training_locale: str) -> str:
    loc = normalize_training_locale(training_locale)
    if loc == "en":
        return title_en
    return COURSE_TITLES.get(title_en, {}).get(loc, title_en)


def localize_facts(title_en: str, training_locale: str) -> Tuple[Optional[List[str]], str]:
    """Return (bullet points or None, body_locale actually used)."""
    loc = normalize_training_locale(training_locale)
    row = COURSE_FACTS.get(title_en)
    if not row:
        return None, DEFAULT_TRAINING_LOCALE
    if loc in row:
        return row[loc], loc
    return row.get("en"), DEFAULT_TRAINING_LOCALE
