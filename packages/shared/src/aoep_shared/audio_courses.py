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


def _language_courses() -> List[AudioCourse]:
    out: List[AudioCourse] = []
    for code in SUPPORTED_LANGUAGES:
        meta = LANGUAGE_META.get(code, {"name": code, "native": code, "flag": "🏳️"})
        name = meta["name"]
        for category, lesson in _LANG_LESSONS:
            phrases = phrases_for(code, category)
            if len(phrases) < 2:
                continue
            segs = [AudioSegment(
                heading="Introduction",
                text=(f"Welcome to {name} - {lesson}. This is a hands-free audio lesson, "
                      f"so keep your eyes on the road. Just listen, then repeat each "
                      f"phrase out loud."))]
            for p in phrases:
                say = f"In {name}, '{p['en']}' is: {p['target']}."
                if p.get("roman"):
                    say += f" You can say it as: {p['roman']}."
                say += f" Now you try - repeat after me: {p['target']}. ... {p['target']}."
                segs.append(AudioSegment(heading=p["en"], text=say))
            recap = ", ".join(p["target"] for p in phrases)
            segs.append(AudioSegment(
                heading="Recap",
                text=f"Great work! Let's review what you learned in {name}: {recap}. "
                     f"Practice these on your next drive and they'll stick."))
            out.append(AudioCourse(
                id=f"lang-{code}-{category}", title=f"{name}: {lesson} (audio)",
                category="Languages", subject=name, level="beginner",
                duration_min=_duration(segs),
                tags=[code, name.lower(), "language", category, "listen-and-repeat"],
                segments=segs))
    return out


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


def _knowledge_course(category: str, title: str) -> AudioCourse:
    points = _FACTS.get(title)
    segs = [AudioSegment(
        heading="Introduction",
        text=(f"Welcome to this audio lesson on {title}. Keep your eyes on the road - "
              f"there's nothing to look at. In a few minutes you'll understand the key "
              f"ideas, just by listening."))]
    if points:
        for i, p in enumerate(points, start=1):
            segs.append(AudioSegment(heading=f"Key idea {i}", text=p))
        recap = " ".join(points)
        segs.append(AudioSegment(
            heading="Recap",
            text=f"Quick recap of {title}: {recap} Nicely done - learning on the move."))
    else:
        segs += [
            AudioSegment(heading="Why it matters",
                         text=f"First, let's set the scene for {title} and why it's worth knowing."),
            AudioSegment(heading="Core ideas",
                         text=f"Next, the main concepts behind {title}, explained simply with "
                              f"everyday examples you can picture without looking."),
            AudioSegment(heading="Going deeper",
                         text=f"Then we connect {title} to things you already know, and clear up "
                              f"a common misunderstanding."),
            AudioSegment(heading="Recap",
                         text=f"To recap {title}: we covered why it matters, the core ideas, and "
                              f"how it connects to daily life. Great job learning while you drive."),
        ]
    slug = title.lower().replace(" ", "-").replace(",", "").replace("'", "")
    return AudioCourse(
        id=f"audio-{slug}", title=f"{title} (audio)", category=category,
        subject=category, level="beginner", duration_min=_duration(segs),
        tags=[category.lower().split(" ")[0], "audio", "drive-safe"], segments=segs)


@functools.lru_cache(maxsize=1)
def build_catalog() -> List[AudioCourse]:
    catalog: List[AudioCourse] = []
    catalog.extend(_language_courses())
    for category, titles in _TOPICS.items():
        for title in titles:
            catalog.append(_knowledge_course(category, title))
    return catalog


def categories() -> List[dict]:
    counts: Dict[str, int] = {}
    for c in build_catalog():
        counts[c.category] = counts.get(c.category, 0) + 1
    return [{"category": k, "count": v} for k, v in sorted(counts.items())]


def list_courses(*, category: Optional[str] = None, q: Optional[str] = None,
                 max_minutes: Optional[int] = None, offset: int = 0,
                 limit: int = 50) -> dict:
    rows = build_catalog()
    if category:
        rows = [c for c in rows if c.category.lower() == category.lower()]
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
        "courses": [
            {"id": c.id, "title": c.title, "category": c.category, "subject": c.subject,
             "level": c.level, "duration_min": c.duration_min, "tags": c.tags,
             "format": c.format, "visual_required": c.visual_required,
             "drive_safe": c.drive_safe, "segments": len(c.segments)}
            for c in page
        ],
    }


def get_course(course_id: str) -> Optional[AudioCourse]:
    for c in build_catalog():
        if c.id == course_id:
            return c
    return None
