"""Audio-only "drive mode" classes - hundreds of eyes-free lessons.

Generates a large catalog of audio-first courses designed to be taken while
driving (or commuting / exercising): every course is narration-only, marked
``visual_required=False`` and ``drive_safe=True``, with no images, video, or
on-screen interaction required. Narration is segmented (intro -> key ideas ->
recap) so a hands-free player can autoplay and announce progress.

Two generators feed the catalog:
- language audio lessons (reuses the 26-language phrasebook): "listen & repeat"
  greetings/conversation/travel for every supported language, and
- knowledge audio lessons across many categories (history, science, business,
  finance, wellness, technology, ...).

Pure/offline + stdlib + pydantic. The curriculum service exposes it over HTTP and
the web/mobile "Drive Mode" players narrate it via on-device TTS.
"""

from __future__ import annotations

import functools
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from . import catalog_i18n
from .catalog_i18n import (
    DEFAULT_LOCALE, normalize_locale,
    localize_category, localize_heading, localize_lesson_type,
    localize_level, narration,
)
from .language_learning import LANGUAGE_META, phrases_for
from .languages import SUPPORTED_LANGUAGES

WORDS_PER_MINUTE = 150


class AudioSegment(BaseModel):
    heading: str
    text: str


class AudioCourse(BaseModel):
    id: str
    title: str
    category: str
    subject: str = ""
    level: str = "beginner"
    duration_min: int = 3
    tags: List[str] = Field(default_factory=list)
    format: str = "audio"
    visual_required: bool = False
    drive_safe: bool = True
    segments: List[AudioSegment] = Field(default_factory=list)

    @property
    def word_count(self) -> int:
        return sum(len(s.text.split()) for s in self.segments)


def _duration(segments: List[AudioSegment]) -> int:
    words = sum(len(s.text.split()) for s in segments)
    return max(3, round(words / WORDS_PER_MINUTE))


# --------------------------------------------------------------------------- #
# Language audio lessons (listen & repeat) - reuses the phrasebook.
# --------------------------------------------------------------------------- #
_LANG_LESSONS = [
    ("phrases", "Essential phrases"),
    ("conversation", "Everyday conversation"),
    ("travel", "Travel survival"),
]


def _language_courses(locale: str) -> List[AudioCourse]:
    out: List[AudioCourse] = []
    for code in SUPPORTED_LANGUAGES:
        meta = LANGUAGE_META.get(code, {"name": code, "native": code, "flag": "🏳️"})
        name_en = meta["name"]
        # In the localized course, show the language being taught in the
        # USER's locale (e.g. for an es UI, the title is "Frances: Frases
        # esenciales (audio)"). The phrasebook itself stays in the
        # target language - that's the content the user is learning.
        name_in_locale = _language_name_in_locale(code, locale, fallback=name_en)
        for category, lesson_en in _LANG_LESSONS:
            phrases = phrases_for(code, category)
            if len(phrases) < 2:
                continue
            lesson_local = localize_lesson_type(lesson_en, locale)
            segs = [AudioSegment(
                heading=localize_heading("Introduction", locale),
                text=narration("lang_intro", locale,
                               language=name_in_locale, lesson=lesson_local))]
            for p in phrases:
                say = narration("lang_phrase_say", locale,
                                language=name_in_locale, en=p["en"], target=p["target"])
                if p.get("roman"):
                    say += narration("lang_phrase_roman", locale, roman=p["roman"])
                say += narration("lang_phrase_repeat", locale, target=p["target"])
                segs.append(AudioSegment(heading=p["en"], text=say))
            recap = ", ".join(p["target"] for p in phrases)
            segs.append(AudioSegment(
                heading=localize_heading("Recap", locale),
                text=narration("lang_recap", locale,
                               language=name_in_locale, recap=recap)))
            out.append(AudioCourse(
                id=f"lang-{code}-{category}",
                title=f"{name_in_locale}: {lesson_local} (audio)",
                category=localize_category("Languages", locale),
                subject=name_in_locale,
                level=localize_level("beginner", locale),
                duration_min=_duration(segs),
                tags=[code, name_en.lower(), "language", category, "listen-and-repeat"],
                segments=segs))
    return out


def _language_name_in_locale(code: str, locale: str, *, fallback: str) -> str:
    """Translate the target language NAME for the UI locale.

    We translate a handful of common language names so users browsing in
    e.g. Spanish see 'Frances' instead of 'French'. Falls back to the
    English name otherwise (which is good enough for less-common pairs).
    """
    table = _LANGUAGE_NAME_TRANSLATIONS.get(code, {})
    return table.get(locale) or fallback


# Translations for the language NAME (not the language ITSELF). Only the
# 13 fully-supported UI locales need entries. Languages not in this table
# fall through to their English name.
_LANGUAGE_NAME_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {"en": "English", "es": "Inglés", "fr": "Anglais", "de": "Englisch",
           "it": "Inglese", "pt": "Inglês", "ru": "Английский", "ar": "الإنجليزية",
           "hi": "अंग्रेज़ी", "zh": "英语", "ja": "英語", "ko": "영어", "vi": "Tiếng Anh", "km": "អង់គ្លេស"},
    "es": {"en": "Spanish", "es": "Español", "fr": "Espagnol", "de": "Spanisch",
           "it": "Spagnolo", "pt": "Espanhol", "ru": "Испанский", "ar": "الإسبانية",
           "hi": "स्पैनिश", "zh": "西班牙语", "ja": "スペイン語", "ko": "스페인어",
           "vi": "Tiếng Tây Ban Nha", "km": "អេស្ប៉ញូល"},
    "fr": {"en": "French", "es": "Francés", "fr": "Français", "de": "Französisch",
           "it": "Francese", "pt": "Francês", "ru": "Французский", "ar": "الفرنسية",
           "hi": "फ़्रेंच", "zh": "法语", "ja": "フランス語", "ko": "프랑스어",
           "vi": "Tiếng Pháp", "km": "បរាំង"},
    "de": {"en": "German", "es": "Alemán", "fr": "Allemand", "de": "Deutsch",
           "it": "Tedesco", "pt": "Alemão", "ru": "Немецкий", "ar": "الألمانية",
           "hi": "जर्मन", "zh": "德语", "ja": "ドイツ語", "ko": "독일어",
           "vi": "Tiếng Đức", "km": "អឡ្លេមង់"},
    "it": {"en": "Italian", "es": "Italiano", "fr": "Italien", "de": "Italienisch",
           "it": "Italiano", "pt": "Italiano", "ru": "Итальянский", "ar": "الإيطالية",
           "hi": "इतालवी", "zh": "意大利语", "ja": "イタリア語", "ko": "이탈리아어",
           "vi": "Tiếng Ý", "km": "អ៊ីតាលី"},
    "pt": {"en": "Portuguese", "es": "Portugués", "fr": "Portugais",
           "de": "Portugiesisch", "it": "Portoghese", "pt": "Português",
           "ru": "Португальский", "ar": "البرتغالية", "hi": "पुर्तगाली",
           "zh": "葡萄牙语", "ja": "ポルトガル語", "ko": "포르투갈어", "vi": "Tiếng Bồ Đào Nha", "km": "ព័រតុខាល់"},
    "ru": {"en": "Russian", "es": "Ruso", "fr": "Russe", "de": "Russisch",
           "it": "Russo", "pt": "Russo", "ru": "Русский", "ar": "الروسية",
           "hi": "रूसी", "zh": "俄语", "ja": "ロシア語", "ko": "러시아어",
           "vi": "Tiếng Nga", "km": "រុស្ស៊ី"},
    "ar": {"en": "Arabic", "es": "Árabe", "fr": "Arabe", "de": "Arabisch",
           "it": "Arabo", "pt": "Árabe", "ru": "Арабский", "ar": "العربية",
           "hi": "अरबी", "zh": "阿拉伯语", "ja": "アラビア語", "ko": "아랍어",
           "vi": "Tiếng Ả Rập", "km": "អារ៉ាប់"},
    "hi": {"en": "Hindi", "es": "Hindi", "fr": "Hindi", "de": "Hindi",
           "it": "Hindi", "pt": "Hindi", "ru": "Хинди", "ar": "الهندية",
           "hi": "हिन्दी", "zh": "印地语", "ja": "ヒンディー語", "ko": "힌디어",
           "vi": "Tiếng Hindi", "km": "ហីន្ដ៊ី"},
    "zh": {"en": "Chinese (Mandarin)", "es": "Chino (mandarín)",
           "fr": "Chinois (mandarin)", "de": "Chinesisch (Mandarin)",
           "it": "Cinese (mandarino)", "pt": "Chinês (mandarim)",
           "ru": "Китайский (мандарин)", "ar": "الصينية (الماندرين)",
           "hi": "चीनी (मंदारिन)", "zh": "中文（普通话）",
           "ja": "中国語（北京語）", "ko": "중국어 (만다린)",
           "vi": "Tiếng Trung (Quan Thoại)", "km": "ចិន"},
    "ja": {"en": "Japanese", "es": "Japonés", "fr": "Japonais", "de": "Japanisch",
           "it": "Giapponese", "pt": "Japonês", "ru": "Японский", "ar": "اليابانية",
           "hi": "जापानी", "zh": "日语", "ja": "日本語", "ko": "일본어",
           "vi": "Tiếng Nhật", "km": "ជីបុន"},
    "ko": {"en": "Korean", "es": "Coreano", "fr": "Coréen", "de": "Koreanisch",
           "it": "Coreano", "pt": "Coreano", "ru": "Корейский", "ar": "الكورية",
           "hi": "कोरियाई", "zh": "韩语", "ja": "韓国語", "ko": "한국어",
           "vi": "Tiếng Hàn", "km": "កូរ៉េ"},
    "vi": {"en": "Vietnamese", "es": "Vietnamita", "fr": "Vietnamien",
           "de": "Vietnamesisch", "it": "Vietnamita", "pt": "Vietnamita",
           "ru": "Вьетнамский", "ar": "الفيتنامية", "hi": "वियतनामी",
           "zh": "越南语", "ja": "ベトナム語", "ko": "베트남어", "vi": "Tiếng Việt", "km": "វៀតណាម"},
    "km": {
           "en": "Khmer", "es": "Camboyano (Jemer)", "fr": "Khmer", "de": "Khmer", "it": "Khmer", "pt": "Khmer",
           "ru": "Кхмерский", "ar": "الخميرية", "hi": "खमेर", "zh": "高棉语", "ja": "クメール語", "ko": "크메르어", "vi": "Tiếng Khmer", "km": "ខ្មែរ"},
}


# --------------------------------------------------------------------------- #
# Knowledge audio lessons across many categories.
# Curated topics carry real key points; others use a coherent learning outline.
# --------------------------------------------------------------------------- #
_TOPICS: Dict[str, List[str]] = {
    "History": [
        "Ancient Egypt", "The Roman Empire", "The Silk Road", "The Renaissance",
        "The Industrial Revolution", "World War II in Brief", "The Cold War",
        "The Age of Exploration", "Ancient Greece", "The French Revolution",
        "The American Revolution", "The Ottoman Empire", "Feudal Japan",
        "The Maya Civilization", "The Space Race", "The Civil Rights Movement",
    ],
    "Science & Nature": [
        "How the Solar System Works", "The Water Cycle", "Photosynthesis Explained",
        "DNA and Genetics", "The Theory of Evolution", "Plate Tectonics",
        "How Vaccines Work", "The Human Brain", "Climate and Weather",
        "Black Holes Explained", "The Periodic Table", "Ecosystems and Food Chains",
        "How the Immune System Works", "Quantum Physics for Beginners",
        "The Carbon Cycle", "How Electricity Works",
    ],
    "Business & Career": [
        "Negotiation Basics", "Effective Communication", "Leadership 101",
        "Building a Personal Brand", "Time Management at Work", "Networking Skills",
        "Giving Great Presentations", "Emotional Intelligence at Work",
        "Project Management Basics", "Marketing Fundamentals", "Sales Essentials",
        "Running Effective Meetings", "Customer Service Excellence",
        "Entrepreneurship 101", "Decision Making", "Conflict Resolution",
    ],
    "Personal Finance": [
        "Budgeting Basics", "Understanding Credit Scores", "Saving for Retirement",
        "Investing 101", "How Compound Interest Works", "Getting Out of Debt",
        "Emergency Funds", "Understanding Taxes", "Index Funds Explained",
        "Buying vs Renting", "Insurance Basics", "Building Wealth Habits",
    ],
    "Health & Wellness": [
        "The Basics of Good Sleep", "Mindful Breathing", "Stress Management",
        "Nutrition Fundamentals", "Building an Exercise Habit", "Hydration and Health",
        "Understanding Mental Health", "Habits That Stick", "Gratitude Practice",
        "Posture and Back Care", "Healthy Eating on a Budget", "Managing Screen Time",
    ],
    "Technology": [
        "How the Internet Works", "What Is Artificial Intelligence",
        "Cybersecurity Basics", "How GPS Works", "Cloud Computing Explained",
        "What Is Blockchain", "How Search Engines Work", "Understanding Data Privacy",
        "How Smartphones Work", "What Are Algorithms", "How Wi-Fi Works",
        "Intro to Machine Learning",
    ],
    "Focus & Philosophy": [
        "An Introduction to Stoicism", "What Is Focused Attention", "The Art of Focus",
        "Understanding Happiness", "Dealing with Uncertainty", "The Power of Habits",
        "Ethics in Everyday Life", "Comparing Philosophical Traditions",
        "The Meaning of Resilience", "Living with Intention",
    ],
    "Arts & Culture": [
        "The Story of Jazz", "Understanding Classical Music", "A Tour of Impressionism",
        "The History of Cinema", "Folklore Around the World", "The Origins of Theater",
        "Architecture Through the Ages", "The Evolution of Pop Music",
        "Famous Painters and Their Styles", "Poetry for Everyone",
    ],
    "Productivity & Study": [
        "How to Learn Anything Faster", "Beating Procrastination",
        "The Pomodoro Technique", "Note-Taking That Works", "Memory Techniques",
        "Setting Goals That Work", "Deep Work Basics", "Building a Morning Routine",
        "Reading More Effectively", "Focus in a Distracted World",
    ],
    "True Stories & Biographies": [
        "The Life of Leonardo da Vinci", "Marie Curie's Discoveries",
        "The Wright Brothers", "Nelson Mandela's Journey", "The Story of Steve Jobs",
        "Ada Lovelace, First Programmer", "The Voyages of Magellan",
        "Frida Kahlo's Art and Life", "The Apollo 11 Mission", "Rosa Parks and Courage",
    ],
    "Geography & World": [
        "The Seven Continents", "How Mountains Form", "The World's Great Rivers",
        "Deserts of the World", "Understanding Time Zones", "The Oceans Explained",
        "Capital Cities of the World", "Volcanoes and Earthquakes", "The Amazon Rainforest",
        "Climate Zones", "Famous Landmarks", "How Maps Work",
    ],
    "World Cultures": [
        "Festivals Around the World", "Tea Cultures of the World", "World Cultural Traditions",
        "Etiquette for Travelers", "The Story of Coffee", "Global Music Traditions",
        "Wedding Traditions Worldwide", "Street Food Around the World",
        "Body Language Across Cultures", "Gift-Giving Customs",
    ],
    "Cooking & Food": [
        "Knife Skills Explained", "The Science of Baking", "Understanding Spices",
        "How to Build Flavor", "Food Safety Basics", "The Maillard Reaction",
        "Meal Planning Made Simple", "Wine and Food Pairing", "Fermentation Basics",
        "Reading a Recipe Like a Chef",
    ],
    "Civics & Law": [
        "How Laws Are Made", "Your Rights as a Citizen", "How Elections Work",
        "Understanding the Court System", "What Is a Constitution",
        "How Taxes Fund Government", "Local vs National Government",
        "Understanding Contracts", "Consumer Rights Basics", "How Juries Work",
    ],
    "Sports & Games": [
        "The Rules of Soccer", "Chess Strategy Basics", "How Scoring Works in Tennis",
        "The History of the Olympics", "Basketball Fundamentals", "Understanding Cricket",
        "The Science of Running", "Poker Odds Explained", "Stretching and Mobility Basics",
        "The Mental Game in Sports",
    ],
}

_FACTS: Dict[str, List[str]] = {
    "Budgeting Basics": [
        "A budget is simply a plan for your money: income in, expenses out, the rest saved.",
        "A popular rule is fifty-thirty-twenty - needs, wants, and savings or debt.",
        "Track spending for one month and you'll quickly spot easy places to cut.",
    ],
    "How Compound Interest Works": [
        "Compound interest means you earn interest on your interest, not just your deposit.",
        "Time is the magic ingredient - starting early beats investing more later.",
        "The rule of seventy-two estimates years to double: divide seventy-two by the rate.",
    ],
    "An Introduction to Stoicism": [
        "Stoicism teaches focusing only on what you can control - your actions and judgments.",
        "Negative events are neutral; our opinions about them cause distress.",
        "A daily practice is to rehearse challenges calmly before they happen.",
    ],
    "What Is Artificial Intelligence": [
        "A.I. is software that learns patterns from data instead of being explicitly programmed.",
        "Machine learning improves with more examples, much like practice.",
        "Today's large language models predict the next word to generate helpful text.",
    ],
    "The Pomodoro Technique": [
        "Work in focused twenty-five minute sprints called pomodoros.",
        "Take a five minute break after each, and a longer break every four.",
        "It beats procrastination by making starting feel small and finite.",
    ],
    "Photosynthesis Explained": [
        "Plants turn sunlight, water, and carbon dioxide into sugar and oxygen.",
        "Chlorophyll in the leaves captures the light energy.",
        "This process is the foundation of almost every food chain on Earth.",
    ],
}


def _knowledge_course(category: str, title: str, locale: str) -> AudioCourse:
    # Knowledge-course titles + factual content are English-origin and
    # not auto-translated here; the templated narration around them
    # (intro, recap headings, "key idea" framing) IS localized so the
    # player feels native in the chosen locale even when the body text
    # is the original.
    points = _FACTS.get(title)
    cat_local = localize_category(category, locale)
    intro_heading = localize_heading("Introduction", locale)
    recap_heading = localize_heading("Recap", locale)
    key_idea_label = localize_heading("Key idea", locale)
    segs = [AudioSegment(
        heading=intro_heading,
        text=narration("know_intro", locale, title=title))]
    if points:
        for i, p in enumerate(points, start=1):
            segs.append(AudioSegment(heading=f"{key_idea_label} {i}", text=p))
        recap_text = " ".join(points)
        segs.append(AudioSegment(
            heading=recap_heading,
            text=narration("know_recap", locale, title=title, recap=recap_text)))
    else:
        segs += [
            AudioSegment(heading=localize_heading("Why it matters", locale),
                         text=f"First, let's set the scene for {title} and why it's worth knowing."),
            AudioSegment(heading=localize_heading("Core ideas", locale),
                         text=f"Next, the main concepts behind {title}, explained simply with "
                              f"everyday examples you can picture without looking."),
            AudioSegment(heading=localize_heading("Going deeper", locale),
                         text=f"Then we connect {title} to things you already know, and clear up "
                              f"a common misunderstanding."),
            AudioSegment(heading=recap_heading,
                         text=f"To recap {title}: we covered why it matters, the core ideas, and "
                              f"how it connects to daily life. Great job learning while you drive."),
        ]
    slug = title.lower().replace(" ", "-").replace(",", "").replace("'", "")
    return AudioCourse(
        id=f"audio-{slug}", title=f"{title} (audio)", category=cat_local,
        subject=cat_local, level=localize_level("beginner", locale),
        duration_min=_duration(segs),
        tags=[category.lower().split(" ")[0], "audio", "drive-safe"],
        segments=segs)


@functools.lru_cache(maxsize=16)
def build_catalog(locale: str = DEFAULT_LOCALE) -> List[AudioCourse]:
    """Build the full audio catalog in the requested locale.

    LRU-cached per-locale (the catalog is ~225 courses; each locale's
    bundle is a few hundred kB at most). The first request for a new
    locale pays the build cost; everything after is dict-lookup fast.
    """
    locale = normalize_locale(locale)
    catalog: List[AudioCourse] = []
    catalog.extend(_language_courses(locale))
    for category, titles in _TOPICS.items():
        for title in titles:
            catalog.append(_knowledge_course(category, title, locale))
    return catalog


def categories(locale: str = DEFAULT_LOCALE) -> List[dict]:
    """List categories with localized labels + course counts.

    Returns ``[{category, category_id, count}, ...]`` so the UI can
    display the localized label while still filtering by the canonical
    English ID (which the rest of the API uses).
    """
    locale = normalize_locale(locale)
    counts: Dict[str, int] = {}
    for cat_en in catalog_i18n.CATEGORY.keys():
        counts[cat_en] = 0
    # Build EN catalog to count by canonical category id (so the count
    # is locale-independent).
    for c in build_catalog(DEFAULT_LOCALE):
        for cat_en in counts:
            if c.category == cat_en:
                counts[cat_en] += 1
                break
    return [
        {"category": localize_category(k, locale), "category_id": k, "count": v}
        for k, v in sorted(counts.items()) if v > 0
    ]


def list_courses(*, category: Optional[str] = None, q: Optional[str] = None,
                 max_minutes: Optional[int] = None, offset: int = 0,
                 limit: int = 50, locale: str = DEFAULT_LOCALE) -> dict:
    locale = normalize_locale(locale)
    rows = build_catalog(locale)
    if category:
        # Accept either the canonical English category id or its
        # localized label - the mobile app passes whichever it has.
        cat_lower = category.lower()
        cat_en = next(
            (k for k in catalog_i18n.CATEGORY
             if k.lower() == cat_lower
             or localize_category(k, locale).lower() == cat_lower),
            None,
        )
        if cat_en is None:
            rows = [c for c in rows if c.category.lower() == cat_lower]
        else:
            cat_local = localize_category(cat_en, locale)
            rows = [c for c in rows if c.category == cat_local]
    if q:
        ql = q.lower()
        rows = [c for c in rows if ql in c.title.lower()
                or any(ql in t for t in c.tags) or ql in c.subject.lower()]
    if max_minutes is not None:
        rows = [c for c in rows if c.duration_min <= max_minutes]
    total = len(rows)
    page = rows[offset: offset + limit]
    return {
        "total": total, "offset": offset, "limit": limit, "locale": locale,
        "courses": [
            {"id": c.id, "title": c.title, "category": c.category, "subject": c.subject,
             "level": c.level, "duration_min": c.duration_min, "tags": c.tags,
             "format": c.format, "visual_required": c.visual_required,
             "drive_safe": c.drive_safe, "segments": len(c.segments)}
            for c in page
        ],
    }


def get_course(course_id: str, locale: str = DEFAULT_LOCALE) -> Optional[AudioCourse]:
    locale = normalize_locale(locale)
    for c in build_catalog(locale):
        if c.id == course_id:
            return c
    return None
