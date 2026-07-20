"""Audio-only "drive mode" classes - hundreds of eyes-free lessons.

Generates a large catalog of audio-first courses designed to be taken while
driving (or commuting / exercising): every course is narration-only, marked
``visual_required=False`` and ``drive_safe=True``, with no images, video, or
on-screen interaction required. Knowledge lessons are framed with an
advance-organizer Overview and an extractive Key-takeaways recap (built only
from the lesson's own headings + lead sentences — no fabricated facts) so each
lesson orients the learner and runs long enough to actually teach something.

Two generators feed the catalog:
    - language audio lessons (reuses the 26-language phrasebook): "listen & repeat"
      greetings/conversation/travel for every supported language, and
    - knowledge audio lessons across many categories (history, science, business,
      finance, wellness, technology, ...), each backed by substantive sections
      in ``audio_topic_data.TOPIC_SECTIONS`` (history, usage, algorithms, pros/cons).

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
    localize_category, localize_lesson_type,
    localize_level, narration,
)
from .training_content_i18n import (
    audio_title_suffix, localize_course_title,
    normalize_training_locale, translate_body,
)
from .audio_topic_data import TOPIC_SECTIONS
from .language_learning import LANGUAGE_META, phrases_for
from .languages import SUPPORTED_LANGUAGES

WORDS_PER_MINUTE = 120
MIN_AUDIO_MINUTES = 1           # honest floor for very short audio snippets
MIN_DRIVE_SEGMENTS = 31         # loop exits at == so threshold must be one above the claimed minimum
MIN_DRIVE_MINUTES = 30
# Half-minute buffer so round(words/WPM) always yields > MIN_DRIVE_MINUTES, not just ==
MIN_DRIVE_WORDS = MIN_DRIVE_MINUTES * WORDS_PER_MINUTE + WORDS_PER_MINUTE // 2 + 1  # 3661


class AudioSegment(BaseModel):
    heading: str
    text: str
    kind: str = "narration"


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
    body_locale: str = "en"

    @property
    def word_count(self) -> int:
        return sum(len(s.text.split()) for s in self.segments)


def _narration_words(segments: List[AudioSegment]) -> int:
    return sum(len(s.text.split()) for s in segments if s.kind != "quiz")


def _duration(segments: List[AudioSegment], *, min_minutes: int = MIN_AUDIO_MINUTES) -> int:
    words = _narration_words(segments)
    return max(min_minutes, round(words / WORDS_PER_MINUTE))


def _oxford_join(items: List[str]) -> str:
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def _first_sentence(text: str) -> str:
    """The lead sentence of a section (sections are newline-separated sentences)."""
    line = (text or "").strip().split("\n", 1)[0].strip()
    return line


def _deepen_en_segments(title: str, segs: List[AudioSegment]) -> List[AudioSegment]:
    """Wrap an authored (English) knowledge lesson with an advance-organizer
    Overview and an extractive Key-takeaways recap.

    This adds genuine instructional structure — stating the learning objectives
    up front and recapping them at the end aids comprehension and retention —
    and gives each lesson enough runtime to actually teach something. It uses
    ONLY the lesson's own section headings and lead sentences, so it introduces
    no new (unverified) facts.
    """
    if not segs:
        return segs
    headings = [s.heading for s in segs]
    heading_sample = headings[:12]
    heading_list = _oxford_join(heading_sample)
    if len(headings) > len(heading_sample):
        heading_list += ", followed by additional related context"
    overview = (
        f"Welcome. In this lesson we explore {title}. "
        f"We'll cover {len(segs)} parts, beginning with {heading_list}. "
        "As you listen, notice how each part builds on the one before it — "
        "you don't need to take notes, just follow along."
    )
    # A long-form course can contain 80+ source sections. Recapping every
    # section would nearly replay the full lesson, so cap the closing summary.
    recap_source = segs if len(segs) <= 20 else segs[:12]
    recap_lines = [f"{s.heading}. {_first_sentence(s.text)}" for s in recap_source]
    takeaways = (
        "Key takeaways. Let's recap the main points. "
        + " ".join(recap_lines)
        + (
            " The remaining sections added broader context and connections."
            if len(segs) > len(recap_source) else ""
        )
        + " Keep these in mind, and you'll have a solid working grasp of "
        f"{title}. That's the end of this lesson — thanks for listening."
    )
    return [
        AudioSegment(heading="Overview", text=overview, kind="narration"),
        *segs,
        AudioSegment(heading="Key takeaways", text=takeaways, kind="narration"),
    ]


def _extended_knowledge_segments(
    category: str,
    title: str,
    primary: List[tuple],
) -> List[AudioSegment]:
    """Build an honest 30+ minute course from authored, related material.

    The selected topic comes first. If its standalone source is too short, add
    clearly-labelled context from other authored topics in the same category,
    then other categories only if needed. This avoids fabricated padding and
    keeps every narration body unique while guaranteeing substantial Drive
    lessons even when the optional harvest cache is unavailable.
    """
    ordered_topics = [title]
    ordered_topics.extend(t for t in _TOPICS.get(category, []) if t != title)
    ordered_topics.extend(
        t
        for cat, titles in _TOPICS.items()
        if cat != category
        for t in titles
    )

    segments: List[AudioSegment] = []
    for topic in ordered_topics:
        sections = primary if topic == title else TOPIC_SECTIONS.get(topic, [])
        for heading, text in sections:
            clean = " ".join((text or "").replace("\n", " ").split())
            if not clean:
                continue
            segments.append(AudioSegment(
                heading=heading if topic == title else f"Related context — {topic}: {heading}",
                text=clean,
            ))
        framed = _deepen_en_segments(title, segments)
        if (
            len(framed) >= MIN_DRIVE_SEGMENTS
            and _narration_words(framed) >= MIN_DRIVE_WORDS
        ):
            break

    return _deepen_en_segments(title, segments)


# --------------------------------------------------------------------------- #
# Language audio lessons (listen & repeat) - reuses the phrasebook.
# --------------------------------------------------------------------------- #
_LANG_LESSONS = [
    ("phrases", "Essential phrases"),
    ("conversation", "Everyday conversation"),
    ("travel", "Travel survival"),
]


def _language_practice_segments(
    language: str,
    phrases: List[dict],
    locale: str,
) -> List[AudioSegment]:
    """Create a 30+ minute eyes-free spaced-practice language lesson.

    Repetition is intentional for language acquisition, but each round changes
    the phrase pairing and retrieval task rather than duplicating narration.
    """
    segments: List[AudioSegment] = []
    round_no = 1
    while len(segments) < MIN_DRIVE_SEGMENTS or _narration_words(segments) < MIN_DRIVE_WORDS:
        current = phrases[(round_no - 1) % len(phrases)]
        following = phrases[round_no % len(phrases)]
        say = narration(
            "lang_phrase_say",
            locale,
            language=language,
            en=current["en"],
            target=current["target"],
        )
        if current.get("roman"):
            say += narration("lang_phrase_roman", locale, roman=current["roman"])
        repeat = narration("lang_phrase_repeat", locale, target=current["target"])
        bridge = narration(
            "lang_phrase_say",
            locale,
            language=language,
            en=following["en"],
            target=following["target"],
        )
        text = (
            f"Practice round {round_no}. {say}{repeat} "
            f"Now connect it to the next useful expression. {bridge} "
            f"First say {current['target']} slowly, then at a natural conversational pace. "
            f"Pause and recall the meaning, {current['en']}, without looking at a screen. "
            f"Next say {following['target']}, meaning {following['en']}. "
            f"Imagine a brief real-world exchange where the first phrase is followed by "
            f"the second. Say both expressions together: {current['target']}. "
            f"{following['target']}. Repeat the pair once more with a calm, clear rhythm. "
            "Listen for the sound pattern, retrieve the meaning, and answer aloud. "
            "This cycle builds pronunciation, recognition, and fast recall while keeping "
            "the practice completely hands-free."
        )
        segments.append(AudioSegment(
            heading=f"Practice round {round_no}: {current['en']}",
            text=text,
        ))
        round_no += 1
    return segments


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
        all_phrases: List[dict] = []
        seen = set()
        for source_category, _ in _LANG_LESSONS:
            for phrase in phrases_for(code, source_category):
                key = (phrase["en"], phrase["target"])
                if key not in seen:
                    seen.add(key)
                    all_phrases.append(phrase)
        for category, lesson_en in _LANG_LESSONS:
            focus = phrases_for(code, category)
            if len(focus) < 2:
                continue
            lesson_local = localize_lesson_type(lesson_en, locale)
            # Lead with this course's focus phrases, then rotate through the
            # complete phrasebook for substantial spaced retrieval practice.
            focused_keys = {(p["en"], p["target"]) for p in focus}
            ordered = focus + [
                p for p in all_phrases
                if (p["en"], p["target"]) not in focused_keys
            ]
            segs = _language_practice_segments(name_in_locale, ordered, locale)
            out.append(AudioCourse(
                id=f"lang-{code}-{category}",
                title=f"{name_in_locale}: {lesson_local} (audio)",
                category=localize_category("Languages", locale),
                subject=name_in_locale,
                level=localize_level("beginner", locale),
                duration_min=_duration(segs, min_minutes=MIN_DRIVE_MINUTES),
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
    "Arts & Film": [
        "How Movies Are Made", "Film Directing Basics", "How to Write a Screenplay",
        "The Art of Cinematography", "Film Editing Fundamentals", "Documentary Filmmaking",
        "Animation Basics", "History of Hollywood", "Independent Filmmaking",
        "Acting Techniques", "Film Scoring and Music", "Visual Storytelling",
    ],
    "Music & Instruments": [
        "How to Play Guitar", "Learning Piano Basics", "Music Theory Fundamentals",
        "How to Sing", "Rhythm and Drumming", "How to Read Music",
        "Music Production Basics", "The History of Jazz", "Classical Music Appreciation",
        "How to Play Bass Guitar", "Electronic Music Making", "Songwriting 101",
    ],
    "Business & Finance": [
        "How to Write a CV", "Job Interview Skills", "Personal Budgeting",
        "Stock Market Investing", "Cryptocurrency Basics", "Understanding XRP",
        "Accounting Fundamentals", "Starting a Business", "Business Plan Writing",
        "Financial Planning for Beginners", "Understanding Taxes", "Entrepreneurship 101",
    ],
    "TED Talks": [
        "The Power of Vulnerability", "How Great Leaders Inspire Action",
        "Your Body Language May Shape Who You Are", "The Surprising Science of Happiness",
        "Inside the Mind of a Master Procrastinator", "How to Speak So People Want to Listen",
        "The Puzzle of Motivation", "Do Schools Kill Creativity",
        "What Makes a Good Life", "The Art of Asking",
        "Why We Do What We Do", "Grit: The Power of Passion and Perseverance",
    ],
    "Programming & Software": [
        "Python for Beginners", "JavaScript Fundamentals", "Web Development Basics",
        "Introduction to Java", "C++ Essentials", "SQL and Databases",
        "Git and Version Control", "APIs and REST", "Object-Oriented Programming",
        "Functional Programming Concepts", "Mobile App Development", "Cloud Computing Basics",
    ],
    "Data Science & AI": [
        "Introduction to Machine Learning", "Data Analysis with Python",
        "Statistics for Data Science", "Neural Networks Explained",
        "Natural Language Processing", "Computer Vision Basics",
        "Data Visualization", "Big Data Fundamentals", "Reinforcement Learning",
        "AI Ethics and Society", "Deep Learning Overview", "Feature Engineering",
    ],
    "Psychology": [
        "Introduction to Psychology", "Cognitive Psychology", "Developmental Psychology",
        "Social Psychology", "Abnormal Psychology", "Positive Psychology",
        "Behavioral Psychology", "Neuropsychology Basics", "Motivation and Emotion",
        "Perception and Sensation", "Memory and Learning", "Personality Theories",
    ],
    "Law & Legal Studies": [
        "Introduction to Law", "Contract Law Basics", "Criminal Law Overview",
        "Constitutional Law", "Intellectual Property Law", "Employment Law",
        "Family Law Fundamentals", "Tort Law Explained", "International Law",
        "Business Law Essentials", "Legal Rights and Responsibilities", "The Court System",
    ],
    "Healthcare & Medicine": [
        "Human Anatomy Overview", "Physiology Fundamentals", "First Aid and CPR",
        "Nutrition and Health", "Mental Health Awareness", "Public Health Basics",
        "Common Diseases Explained", "Pharmacology Basics", "Medical Terminology",
        "Women's Health", "Child Health and Development", "Aging and Geriatrics",
    ],
    "Engineering Fundamentals": [
        "Introduction to Engineering", "Mechanical Engineering Basics",
        "Electrical Engineering Overview", "Civil Engineering Concepts",
        "Chemical Engineering Introduction", "Aerospace Engineering Basics",
        "Biomedical Engineering", "Environmental Engineering", "Materials Science",
        "Thermodynamics Explained", "Fluid Mechanics Overview", "Structural Analysis Basics",
    ],
    "Writing & Communication": [
        "Creative Writing Fundamentals", "Technical Writing Skills",
        "Persuasive Writing", "Journalism Basics", "Academic Writing",
        "Storytelling Techniques", "Public Speaking Mastery", "Business Writing",
        "Script and Screenplay Writing", "Grant Writing Basics",
        "Editing and Proofreading", "Writing for the Web",
    ],
    "Environment & Sustainability": [
        "Climate Change Explained", "Renewable Energy Sources",
        "Sustainable Living", "Environmental Science Basics",
        "Ocean Conservation", "Biodiversity and Ecosystems",
        "Circular Economy", "Carbon Footprint Reduction",
        "Green Building and Architecture", "Sustainable Agriculture",
        "Water Conservation", "Plastic Pollution Solutions",
    ],
    "Social Sciences": [
        "Introduction to Sociology", "Cultural Anthropology",
        "Political Science Fundamentals", "Social Inequality and Justice",
        "International Relations", "Media Studies",
        "Gender Studies Overview", "Human Geography",
        "Urban Planning Basics", "Demography and Population",
        "Social Research Methods", "Globalization and Society",
    ],
    "Space & Astronomy": [
        "Our Solar System", "Stars and Stellar Evolution",
        "Galaxies and the Universe", "Black Holes Explained",
        "The Big Bang Theory", "Space Exploration History",
        "Exoplanets and the Search for Life", "Dark Matter and Dark Energy",
        "Cosmology Fundamentals", "Telescopes and Observatories",
        "Rockets and Space Travel", "Mars and Future Colonization",
    ],
    "Mathematics Advanced": [
        "Number Theory Fundamentals", "Abstract Algebra Introduction",
        "Real Analysis Basics", "Complex Analysis Overview",
        "Combinatorics and Graph Theory", "Topology Introduction",
        "Mathematical Logic", "Probability Theory",
        "Numerical Methods", "Game Theory Basics",
        "Mathematical Modeling", "Set Theory Fundamentals",
    ],
    "Parenting & Child Development": [
        "Understanding Child Development Stages", "Positive Parenting Techniques",
        "Early Childhood Education", "Emotional Intelligence in Children",
        "Discipline vs Punishment", "Screen Time and Children",
        "Raising Resilient Kids", "Educational Games and Play",
        "Supporting Learning Differences", "Nutrition for Children",
        "Teenage Brain and Behavior", "Building Strong Family Bonds",
    ],
    "Finance & Investing": [
        "Stock Market Investing Basics", "Cryptocurrency and Blockchain",
        "Understanding XRP and Ripple", "Mutual Funds and ETFs",
        "Real Estate Investing", "Retirement Planning",
        "Tax Planning Strategies", "Options and Derivatives Basics",
        "Value Investing Principles", "Technical Analysis",
        "Portfolio Management", "Financial Risk Management",
    ],
    "Entrepreneurship": [
        "Starting a Business", "Business Plan Writing",
        "Startup Funding and Venture Capital", "Marketing for Entrepreneurs",
        "Product Development and MVP", "Building a Team",
        "Sales Strategies for Startups", "Legal Basics for Business Owners",
        "E-commerce and Online Business", "Scaling a Business",
        "Franchise vs Independent Business", "Exit Strategies and Acquisitions",
    ],
    "Language & Linguistics": [
        "How Language Works", "Etymology and Word Origins",
        "The Science of Language Learning", "Phonetics and Phonology",
        "Grammar Across Languages", "Sociolinguistics",
        "Language and Identity", "Writing Systems of the World",
        "Language Acquisition", "Translation and Interpretation",
        "Endangered Languages", "Sign Language Overview",
    ],
    "Architecture & Design": [
        "History of Architecture", "Architectural Design Principles",
        "Sustainable Architecture", "Interior Design Fundamentals",
        "Urban Design and City Planning", "Famous Buildings and Architects",
        "Graphic Design Basics", "Typography and Layout",
        "Color Theory in Design", "Industrial Design",
        "Landscape Architecture", "Heritage and Preservation",
    ],
    "Nutrition & Food Science": [
        "Macronutrients Explained", "Micronutrients and Vitamins",
        "How the Gut Works", "Diets and Evidence", "Sports Nutrition",
        "Food Safety and Handling", "Plant-Based Eating",
        "Sugar and Metabolic Health", "Reading Food Labels",
        "Cooking Techniques and Nutrition", "Food Allergies and Intolerances",
        "The Mediterranean Diet",
    ],
    "Film & Media Studies": [
        "History of Cinema", "Film Directing Techniques",
        "Cinematography and Visual Storytelling", "Film Editing and Montage",
        "Screenwriting Structure", "Documentary Filmmaking",
        "Animation History and Techniques", "Sound Design in Film",
        "Film Genres and Their Conventions", "Independent Cinema",
        "Streaming and the Future of Film", "Film Criticism and Analysis",
    ],
    "Music Theory & History": [
        "Reading Music and Notation", "Harmony and Chord Progressions",
        "Rhythm and Meter", "Melody Writing",
        "Counterpoint Basics", "Music Form and Structure",
        "The History of Classical Music", "The History of Jazz",
        "Rock and Roll History", "Electronic Music and Synthesis",
        "World Music Traditions", "Music Production and Recording",
    ],
    "Personal Development": [
        "Goal Setting and Achievement", "Building Self-Discipline",
        "Time Management Mastery", "Overcoming Procrastination",
        "Building Confidence", "Networking and Relationships",
        "Financial Independence", "Mindset and Success",
        "Negotiation Skills", "Decision Making Under Uncertainty",
        "Managing Failure and Setbacks", "Creating Habits That Last",
    ],
    "Workplace Compliance & Safety": [
        "Sexual Harassment Prevention", "Workplace Violence Prevention",
        "OSHA General Industry Safety", "OSHA Construction Safety",
        "Fire Safety and Prevention", "Hazard Communication (HazCom/GHS)",
        "Bloodborne Pathogens Training", "Lockout Tagout (LOTO) Procedures",
        "Personal Protective Equipment", "Ergonomics in the Workplace",
        "Emergency Action Plans", "Electrical Safety Basics",
    ],
    "Food Safety & Sanitation": [
        "ServSafe Food Handler Basics", "HACCP Food Safety Principles",
        "Food Allergen Awareness", "Safe Food Temperatures",
        "Personal Hygiene for Food Workers", "Preventing Cross-Contamination",
        "Cleaning and Sanitizing Food Areas", "Food Storage Best Practices",
        "Pest Control in Food Service", "Food Safety for Managers",
        "Restaurant Inspection Preparation", "Foodborne Illness Prevention",
    ],
    "Healthcare Compliance": [
        "HIPAA Privacy and Security", "OSHA for Healthcare Workers",
        "Infection Control Basics", "Standard Precautions in Healthcare",
        "Patient Rights and Ethics", "Medicare and Medicaid Compliance",
        "Documentation and Charting Standards", "Workplace Safety in Hospitals",
        "Handling Hazardous Drugs", "Fall Prevention in Healthcare",
        "Restraint Reduction", "Cultural Competence in Healthcare",
    ],
    "Financial Literacy": [
        "How to Build a Budget", "Understanding Credit Cards",
        "Student Loan Repayment Strategies", "How to Save for a Home",
        "Understanding Your Paycheck", "401k and Retirement Basics",
        "The Emergency Fund", "How to Negotiate a Raise",
        "Understanding Insurance Basics", "Avoiding Financial Scams",
        "Side Hustle Income Tax", "Investing Your First $1000",
    ],
    "Career Development": [
        "How to Write a Winning Resume", "Mastering the Job Interview",
        "LinkedIn Profile Optimization", "Networking for Introverts",
        "How to Ask for a Promotion", "Remote Work Best Practices",
        "Managing Up at Work", "Giving and Receiving Feedback",
        "Dealing with Difficult Coworkers", "Workplace Etiquette",
        "Time Management at Work", "Building a Personal Brand Online",
    ],
    "Real Estate": [
        "How to Buy Your First Home", "Understanding Mortgage Types",
        "Real Estate Investing Basics", "How to Read a Lease Agreement",
        "Renters Rights and Responsibilities", "Home Inspection Basics",
        "Understanding Property Taxes", "HOA Rules and Your Rights",
        "How to Sell Your Home", "Real Estate Market Analysis",
        "Flipping Houses 101", "Commercial Real Estate Overview",
    ],
    "Automotive & Transportation": [
        "How a Car Engine Works", "Basic Car Maintenance",
        "Understanding Car Insurance", "Buying a Used Car Safely",
        "Electric Vehicles Explained", "Defensive Driving Techniques",
        "Winter Driving Safety", "Motorcycle Safety Basics",
        "Understanding Traffic Laws", "Car Financing Basics",
        "Road Trip Planning", "Fleet Management Basics",
    ],
    "Home Improvement & DIY": [
        "Basic Plumbing Repairs", "Electrical Safety at Home",
        "Painting Your Home Like a Pro", "Basic Drywall Repair",
        "Understanding Home Insulation", "Flooring Installation Basics",
        "Landscaping and Lawn Care", "Smart Home Technology",
        "Home Security Basics", "Energy Efficiency at Home",
        "Roof Maintenance Basics", "Basement Waterproofing",
    ],
    "Science (Expanded)": [
        "Organic Chemistry Basics", "Introduction to Genetics",
        "Nuclear Physics Overview", "The Human Immune System",
        "Materials Science Basics", "Nanotechnology Introduction",
        "Environmental Chemistry", "How Vaccines Work",
        "The Science of Sleep", "Neuroscience of Learning",
        "Geology and Earth Science", "Introduction to Botany",
    ],
    "Mathematics (Applied)": [
        "Mental Math Tricks", "Math for Everyday Life",
        "Fractions Decimals Percentages", "Algebra for Adults",
        "Business Mathematics", "Math for Nursing and Healthcare",
        "Financial Mathematics", "Statistics in Daily Life",
        "Geometry in Architecture", "Calculus in Real Life",
        "Math Anxiety and How to Overcome It", "Math for Coding",
    ],
    "Government & Civic Services": [
        "How to Apply for Federal Benefits", "Understanding Social Security",
        "Medicare Enrollment Guide", "How to File Taxes Step by Step",
        "Small Business Government Contracts", "Veteran Benefits Overview",
        "Disability Benefits (SSDI/SSI)", "Understanding FAFSA",
        "Green Card and Citizenship Process", "How Government Programs Work",
        "Local Government and Zoning", "Public Records and FOIA Requests",
    ],
    "Parenting & Family (Expanded)": [
        "Newborn Care Basics", "Sleep Training Methods",
        "How to Talk to Teenagers", "Managing Screen Time",
        "Homeschooling Basics", "ADHD Parenting Strategies",
        "Raising Bilingual Children", "Teen Mental Health",
        "Divorce and Co-Parenting", "College Preparation for Parents",
        "Teaching Kids About Money", "Bullying Prevention",
    ],
    "Animal Care & Veterinary": [
        "Dog Training Basics", "Cat Behavior and Care",
        "Small Animal First Aid", "Understanding Pet Nutrition",
        "Horse Care Fundamentals", "Aquarium Basics",
        "Exotic Pet Care", "Wildlife and Conservation",
        "Animal Anatomy Overview", "Veterinary Assistant Basics",
        "Pet Insurance Explained", "Breeding Basics",
    ],
    "Sports Science & Fitness": [
        "Exercise Physiology Basics", "Strength Training Fundamentals",
        "Cardio and Heart Health", "Flexibility and Mobility Training",
        "Sports Nutrition Essentials", "Injury Prevention in Sports",
        "Mental Performance in Athletics", "Running Technique",
        "Swimming for Fitness", "Youth Sports Coaching",
        "Recovery Science", "Periodization Training",
    ],
    "Communication & Interpersonal": [
        "Active Listening Skills", "Assertiveness Training",
        "How to Resolve Conflicts", "Body Language Mastery",
        "Cross-Cultural Communication", "Email Etiquette",
        "How to Run Effective Meetings", "Presenting Data Clearly",
        "Storytelling for Business", "Building Rapport",
        "Difficult Conversations", "Persuasion and Influence",
    ],
    "Artificial Intelligence (Applied)": [
        "Using AI at Work", "Prompt Engineering Basics",
        "AI in Healthcare", "AI in Education",
        "AI Ethics and Bias", "AI for Small Business",
        "Generative AI Tools Overview", "AI in Finance",
        "AI and the Future of Jobs", "AI in Creative Industries",
        "AI for Lawyers and Legal", "Responsible AI Use",
    ],
    "History (Expanded)": [
        "The American Civil War", "World War I Causes and Effects",
        "The Holocaust and Its Lessons", "History of the Civil Rights Movement",
        "The Cold War Explained", "History of the Internet",
        "The Roman Republic", "Ancient Mesopotamia",
        "The Ming Dynasty", "The Age of Imperialism",
        "History of Medicine", "Women in History",
    ],
    "Languages (Advanced Topics)": [
        "How to Learn a Language Fast", "Language Exchange Tips",
        "Reading in a Foreign Language", "Writing in a Second Language",
        "Watching TV to Learn Languages", "Immersion Without Travel",
        "Understanding Accents", "Language and Culture Connection",
        "Grammar vs Fluency Debate", "Bilingualism Benefits",
        "How Children Learn Language", "Language Learning Apps Compared",
    ],
}


def _knowledge_course(
    category: str, title: str, locale: str, training_locale: str,
) -> AudioCourse:
    """Build a knowledge audio lesson.

    ``locale`` localizes category labels for the UI. ``training_locale`` is
    applied to the complete body by ``_maybe_translate`` when a translator is
    available; otherwise the honest English source and locale are returned.

    Content priority for English body:
      1. Harvested rich content from the drive_content_cache.db SQLite store
         (28 segments × ~125 words ≈ 30 min — populated by the drive_topic_harvest
         CLI or the POST /admin/harvest-drive-topic endpoint).
      2. Authored TOPIC_SECTIONS, extended with clearly-labelled related
         context until the lesson reaches at least 30 minutes.

    Either way the lesson is wrapped with an Overview + Key-takeaways by
    ``_deepen_en_segments`` and must contain at least 30 segments.
    """
    tloc = normalize_training_locale(training_locale)
    display_title = localize_course_title(title, tloc)
    cat_local = localize_category(category, locale)
    # A few locales have three translated summary facts. Those are useful as
    # previews, but they are not a complete Drive lesson; using them here was
    # the source of the reported 3-segment courses. Build the substantial
    # English source first, then _maybe_translate() translates the full body
    # when a body translator is available (otherwise it honestly stays English).
    rich = _get_harvested_sections(title)
    source = rich if rich else list(TOPIC_SECTIONS.get(title, []))
    candidate = [AudioSegment(heading=h, text=t) for h, t in source]
    framed = _deepen_en_segments(title, candidate)
    if (
        len(framed) >= MIN_DRIVE_SEGMENTS
        and _narration_words(framed) >= MIN_DRIVE_WORDS
    ):
        segs = framed
    else:
        segs = _extended_knowledge_segments(category, title, source)
    body_loc = "en"
    slug = title.lower().replace(" ", "-").replace(",", "").replace("'", "")
    return AudioCourse(
        id=f"audio-{slug}",
        title=f"{display_title} {audio_title_suffix(tloc)}",
        category=cat_local,
        subject=cat_local,
        level=localize_level("beginner", locale),
        duration_min=_duration(segs, min_minutes=MIN_DRIVE_MINUTES),
        tags=[category.lower().split(" ")[0], "audio", "drive-safe"],
        segments=segs,
        body_locale=body_loc,
    )


def _get_harvested_sections(title: str) -> Optional[List[tuple]]:
    """Return cached harvested sections for *title*, or ``None`` on miss/error."""
    try:
        from .drive_topic_harvest import get_cached_segments, MIN_SEGMENTS_TO_ACCEPT
        segs = get_cached_segments(title)
        if segs and len(segs) >= MIN_SEGMENTS_TO_ACCEPT:
            return segs
    except Exception:
        pass
    return None


@functools.lru_cache(maxsize=64)
def build_catalog(locale: str = DEFAULT_LOCALE, training_locale: Optional[str] = None) -> List[AudioCourse]:
    """Build the full audio catalog in the requested locale.

    ``locale`` drives UI-facing labels (category, level, headings).
    ``training_locale`` (en/es/zh) drives spoken lesson bodies; defaults
    from ``locale`` when omitted.
    """
    locale = normalize_locale(locale)
    tloc = normalize_training_locale(training_locale or locale)
    catalog: List[AudioCourse] = []
    catalog.extend(_language_courses(locale))
    for category, titles in _TOPICS.items():
        for title in titles:
            catalog.append(_knowledge_course(category, title, locale, tloc))
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
                 limit: int = 50, locale: str = DEFAULT_LOCALE,
                 training_locale: Optional[str] = None) -> dict:
    locale = normalize_locale(locale)
    tloc = normalize_training_locale(training_locale or locale)
    rows = build_catalog(locale, tloc)
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
        "total": total, "offset": offset, "limit": limit,
        "locale": locale, "training_locale": tloc,
        "courses": [
            {"id": c.id, "title": c.title, "category": c.category, "subject": c.subject,
             "level": c.level, "duration_min": c.duration_min, "tags": c.tags,
             "format": c.format, "visual_required": c.visual_required,
             "drive_safe": c.drive_safe, "segments": len(c.segments),
             "body_locale": c.body_locale}
            for c in page
        ],
    }


# On-demand translations of a full course into an uncurated training locale.
# Keyed by (course_id, training_locale); populated only when a body translator
# is registered (see training_content_i18n.set_body_translator).
_TRANSLATED_COURSES: Dict[tuple, AudioCourse] = {}


def _maybe_translate(course: AudioCourse, tloc: str) -> AudioCourse:
    """Return ``course`` spoken in ``tloc`` when a translator can provide it.

    When the course body already matches ``tloc`` (curated content), or the
    target is English, or no translator is available, the course is returned
    unchanged with its honest ``body_locale`` so the client narrates with a
    voice that matches the text. Language "listen & repeat" courses are never
    translated - their content is intentionally in the target language already.
    """
    if tloc == "en" or course.body_locale == tloc or course.id.startswith("lang-"):
        return course
    key = (course.id, tloc)
    cached = _TRANSLATED_COURSES.get(key)
    if cached is not None:
        return cached
    source = course.body_locale or "en"
    new_segments: List[AudioSegment] = []
    translated_any = False
    for seg in course.segments:
        text = translate_body(seg.text, tloc, source=source)
        if text:
            new_segments.append(AudioSegment(heading=seg.heading, text=text, kind=seg.kind))
            translated_any = True
        else:
            new_segments.append(seg)
    if not translated_any:
        # No translator (offline) -> keep the English body + body_locale so the
        # client speaks English text with an English voice (coherent fallback).
        return course
    localized = course.model_copy(deep=True)
    localized.segments = new_segments
    localized.body_locale = tloc
    _TRANSLATED_COURSES[key] = localized
    return localized


def get_course(course_id: str, locale: str = DEFAULT_LOCALE,
               training_locale: Optional[str] = None) -> Optional[AudioCourse]:
    locale = normalize_locale(locale)
    tloc = normalize_training_locale(training_locale or locale)
    for c in build_catalog(locale, tloc):
        if c.id == course_id:
            return _maybe_translate(c, tloc)
    return None
