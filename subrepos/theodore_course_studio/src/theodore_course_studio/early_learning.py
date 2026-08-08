"""Curated, picture-led Pre-K through Grade 2 lessons.

These lessons intentionally do not summarize adult source documents. Early
learners need one concrete idea at a time, predictable repetition, visual cues,
read-aloud narration, movement, and tiny checks for understanding.

All visuals are self-contained SVG data URLs, so the lessons work offline.
The "video" asset is an animated SVG motion card: a short, silent visual clip
that pairs with Theodore's read-aloud narration without requiring an MP4.
"""

from __future__ import annotations

import html
import time
import urllib.parse
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from pydantic import BaseModel

from .child_i18n import SOUND_SPECIFIC_TOPICS, curated_languages, translate_beats
from .studio_languages import language_name, normalize_language
from .types import CategoryId, CourseSlide, StudioCourse


class EarlyLevel(str, Enum):
    PRE_K = "pre_k"
    KINDERGARTEN = "kindergarten"
    GRADE_1 = "grade_1"
    GRADE_2 = "grade_2"


LEVEL_NAMES = {
    EarlyLevel.PRE_K: "Pre-K",
    EarlyLevel.KINDERGARTEN: "Kindergarten",
    EarlyLevel.GRADE_1: "Grade 1",
    EarlyLevel.GRADE_2: "Grade 2",
}


@dataclass(frozen=True)
class LessonBeat:
    title: str
    words: str
    say: str
    symbol: str
    color: str
    activity: str


@dataclass(frozen=True)
class LessonTemplate:
    topic_id: str
    level: EarlyLevel
    subject: str
    title: str
    description: str
    beats: tuple[LessonBeat, ...]


class EarlyCourseRequest(BaseModel):
    level: EarlyLevel = EarlyLevel.PRE_K
    topic_id: str = "colors"
    language: str = "en"
    title: str | None = None
    allow_xai_translation: bool = True


class EarlyCourseOption(BaseModel):
    topic_id: str
    level: EarlyLevel
    level_name: str
    subject: str
    title: str
    description: str
    slides: int


def _beat(
    title: str,
    words: str,
    say: str,
    symbol: str,
    color: str,
    activity: str,
) -> LessonBeat:
    return LessonBeat(title, words, say, symbol, color, activity)


_TEMPLATES: tuple[LessonTemplate, ...] = (
    LessonTemplate(
        "colors",
        EarlyLevel.PRE_K,
        "Colors",
        "My First Colors",
        "Name red, blue, yellow, and green.",
        (
            _beat("Hello, colors!", "We will find four colors.", "Hello, little learner! Today we will find four bright colors.", "🌈", "#7c3aed", "Wave hello to the colors."),
            _beat("Red", "Red is bright.", "This is red. Red can look like an apple.", "🍎", "#ef4444", "Find something red."),
            _beat("Blue", "Blue is cool.", "This is blue. Blue can look like the sky.", "☁", "#3b82f6", "Point up to the blue sky."),
            _beat("Yellow", "Yellow can shine.", "This is yellow. Yellow can look like the sun.", "☀", "#facc15", "Make a big sun with your arms."),
            _beat("Green", "Green grows.", "This is green. Green can look like a leaf.", "🌿", "#22c55e", "Pretend to grow like a plant."),
            _beat("Color hunt", "Can you find a color?", "Look around. Find one red, blue, yellow, or green thing.", "🔎", "#f97316", "Say the color you found."),
            _beat("Great job!", "Red. Blue. Yellow. Green.", "You learned four colors! Say them with me: red, blue, yellow, green.", "⭐", "#ec4899", "Give yourself a clap."),
        ),
    ),
    LessonTemplate(
        "shapes",
        EarlyLevel.PRE_K,
        "Shapes",
        "Circle, Square, Triangle",
        "See and name three basic shapes.",
        (
            _beat("Hello, shapes!", "Shapes are all around us.", "Today we will meet a circle, a square, and a triangle.", "✨", "#8b5cf6", "Draw a big shape in the air."),
            _beat("Circle", "A circle is round.", "A circle is round. It has no corners.", "●", "#ef4444", "Make a circle with your arms."),
            _beat("Square", "A square has four sides.", "A square has four equal sides and four corners.", "■", "#3b82f6", "Count four sides with your finger."),
            _beat("Triangle", "A triangle has three sides.", "A triangle has three sides and three corners.", "▲", "#facc15", "Hold up three fingers."),
            _beat("Shape hunt", "What shape do you see?", "Find something round, something square, or something shaped like a triangle.", "🔎", "#22c55e", "Point to one shape."),
            _beat("Great job!", "Circle. Square. Triangle.", "You learned three shapes. Circle, square, triangle!", "⭐", "#ec4899", "Clap three times."),
        ),
    ),
    LessonTemplate(
        "counting_1_10",
        EarlyLevel.KINDERGARTEN,
        "Math",
        "Count from 1 to 10",
        "Count objects and connect numbers to amounts.",
        (
            _beat("Let's count!", "Numbers tell how many.", "Today we will count from one to ten.", "🔢", "#7c3aed", "Tap your knees and get ready."),
            _beat("One and two", "One sun. Two shoes.", "One means one thing. Two means two things.", "1  2", "#ef4444", "Show one finger, then two."),
            _beat("Three and four", "Three stars. Four blocks.", "Count slowly: one, two, three. Now count four blocks.", "3  4", "#f97316", "Show three fingers, then four."),
            _beat("Five and six", "Five fingers. Six dots.", "One hand has five fingers. Add one more to make six.", "5  6", "#facc15", "Wiggle five fingers."),
            _beat("Seven and eight", "Seven days. Eight legs.", "A week has seven days. A spider has eight legs.", "7  8", "#22c55e", "Count seven claps."),
            _beat("Nine and ten", "Nine stars. Ten toes.", "Nine comes before ten. You have ten toes.", "9  10", "#3b82f6", "Count to ten with Theodore."),
            _beat("Your turn", "How many dots?", "Count each dot once. Say the last number.", "● ● ● ● ●", "#8b5cf6", "Count the five dots."),
            _beat("We counted!", "1 2 3 4 5 6 7 8 9 10", "Wonderful counting! You counted all the way to ten.", "⭐", "#ec4899", "Take a number bow."),
        ),
    ),
    LessonTemplate(
        "letter_sounds",
        EarlyLevel.KINDERGARTEN,
        "Reading",
        "Meet A, B, and C",
        "Connect three letters to their first sounds.",
        (
            _beat("Letters make sounds", "We will hear A, B, and C.", "Letters have names and sounds. Today we meet A, B, and C.", "ABC", "#7c3aed", "Sing A, B, C."),
            _beat("A says /a/", "A is for apple.", "A can make the short a sound, like apple. A, apple.", "A 🍎", "#ef4444", "Say apple slowly."),
            _beat("B says /b/", "B is for ball.", "B makes the b sound, like ball. B, ball.", "B ⚽", "#3b82f6", "Bounce an imaginary ball."),
            _beat("C says /k/", "C is for cat.", "C can make the k sound, like cat. C, cat.", "C 🐱", "#facc15", "Pretend to be a cat."),
            _beat("Sound match", "Which letter starts ball?", "Listen: ball. Ball starts with the b sound. Which letter is it?", "A  B  C", "#22c55e", "Point to B."),
            _beat("Read with me", "A apple. B ball. C cat.", "Read with me: A apple. B ball. C cat.", "📖", "#f97316", "Say each pair aloud."),
            _beat("Letter star!", "You know A, B, and C.", "Great listening! You met three letters and their sounds.", "⭐", "#ec4899", "Draw your favorite letter."),
        ),
    ),
    LessonTemplate(
        "sight_words",
        EarlyLevel.GRADE_1,
        "Reading",
        "Read Five Sight Words",
        "Read I, see, the, a, and is in short sentences.",
        (
            _beat("Words we know fast", "Sight words are words we remember.", "Sight words help us read smoothly. We will learn five.", "👀", "#7c3aed", "Point to your eyes."),
            _beat("I", "I means me.", "The word I means me. Read: I can hop.", "I", "#ef4444", "Say: I can hop."),
            _beat("See", "See means look.", "The word see means look. Read: I see a cat.", "see", "#3b82f6", "Point and say: I see."),
            _beat("The", "The points to one thing.", "Read this word: the. Read: The sun is hot.", "the", "#facc15", "Find the word the."),
            _beat("A", "A can mean one.", "The word a can mean one. Read: A dog can run.", "a", "#22c55e", "Say: a dog."),
            _beat("Is", "Is tells about now.", "Read this word: is. Read: The cat is soft.", "is", "#f97316", "Say: is soft."),
            _beat("Read a sentence", "I see a cat.", "Now read the whole sentence with me: I see a cat.", "📖", "#8b5cf6", "Read it two times."),
            _beat("Word star!", "I. See. The. A. Is.", "You read five sight words. Practice them again tomorrow.", "⭐", "#ec4899", "Give yourself a high five."),
        ),
    ),
    LessonTemplate(
        "addition_to_10",
        EarlyLevel.GRADE_1,
        "Math",
        "Add Within 10",
        "Join small groups and find the total.",
        (
            _beat("Addition joins", "Addition puts groups together.", "When we add, we join groups to find how many in all.", "＋", "#7c3aed", "Bring your hands together."),
            _beat("One plus one", "1 + 1 = 2", "One apple plus one apple makes two apples.", "🍎 + 🍎", "#ef4444", "Show one finger on each hand."),
            _beat("Two plus one", "2 + 1 = 3", "Two dots plus one more dot makes three dots.", "●● + ●", "#3b82f6", "Count all three dots."),
            _beat("Two plus two", "2 + 2 = 4", "Two blocks plus two blocks makes four blocks.", "■■ + ■■", "#facc15", "Count: one, two, three, four."),
            _beat("Three plus two", "3 + 2 = 5", "Start with three. Add two more. Now there are five.", "●●● + ●●", "#22c55e", "Count on: four, five."),
            _beat("Your turn", "4 + 1 = ?", "Four stars plus one more star. How many stars in all?", "★★★★ + ★", "#f97316", "Say the answer: five."),
            _beat("Addition star!", "Join. Count. Total.", "You can add: join the groups, count all, and say the total.", "⭐", "#ec4899", "Make a plus sign with your arms."),
        ),
    ),
    LessonTemplate(
        "story_sequence",
        EarlyLevel.GRADE_2,
        "Reading",
        "First, Next, Last",
        "Put story events in order and retell them.",
        (
            _beat("Stories have order", "Events happen in a sequence.", "A story has events in order. We can say first, next, and last.", "📚", "#7c3aed", "Hold up one, two, three fingers."),
            _beat("First", "First, Mia planted a seed.", "First tells what happened at the beginning. Mia planted a seed.", "1 🌱", "#ef4444", "Say: first, she planted."),
            _beat("Next", "Next, Mia watered it.", "Next tells what happened after that. Mia gave the seed water.", "2 💧", "#3b82f6", "Pretend to water a seed."),
            _beat("Last", "Last, a flower bloomed.", "Last tells how the story ended. A bright flower bloomed.", "3 🌼", "#facc15", "Open your hands like a flower."),
            _beat("Tell it in order", "Plant. Water. Bloom.", "Retell the story: first plant, next water, last bloom.", "🌱 → 💧 → 🌼", "#22c55e", "Point left to right as you tell it."),
            _beat("Why order matters", "Order helps a story make sense.", "If we mix up events, the story is confusing. Sequence makes it clear.", "🧩", "#f97316", "Name the first event."),
            _beat("Story star!", "First. Next. Last.", "You can put story events in order and retell them.", "⭐", "#ec4899", "Retell the seed story once more."),
        ),
    ),
    LessonTemplate(
        "animal_habitats",
        EarlyLevel.GRADE_2,
        "Science",
        "Where Animals Live",
        "Match animals to forest, ocean, desert, and polar habitats.",
        (
            _beat("A habitat is a home", "Animals need food, water, and shelter.", "A habitat is a living thing's home. It gives animals what they need.", "🏡", "#7c3aed", "Say: habitat means home."),
            _beat("Forest", "Forests have many trees.", "Deer and owls can live in a forest. Trees give food and shelter.", "🦌 🌲", "#22c55e", "Pretend to be a tall tree."),
            _beat("Ocean", "Oceans are salt water.", "Fish and whales live in the ocean. Their bodies help them swim.", "🐟 🌊", "#3b82f6", "Move your hands like fins."),
            _beat("Desert", "Deserts are very dry.", "Camels can live in dry deserts. They can go a long time without water.", "🐪 ☀", "#f59e0b", "Pretend to walk on hot sand."),
            _beat("Polar habitat", "Polar places are cold.", "Polar bears have thick fur and fat that help them stay warm.", "🐻‍❄️ ❄", "#60a5fa", "Hug yourself to stay warm."),
            _beat("Match the home", "Where does a fish live?", "Think about what a fish needs. A fish lives in water, so it matches the ocean.", "🐟 → ?", "#f97316", "Say: the fish lives in the ocean."),
            _beat("Habitat scientist!", "Forest. Ocean. Desert. Polar.", "You matched animals to four habitats. Every habitat meets special needs.", "⭐", "#ec4899", "Name one animal and its habitat."),
        ),
    ),
)


def list_early_courses(level: EarlyLevel | None = None) -> list[EarlyCourseOption]:
    rows = []
    for template in _TEMPLATES:
        if level is not None and template.level is not level:
            continue
        rows.append(
            EarlyCourseOption(
                topic_id=template.topic_id,
                level=template.level,
                level_name=LEVEL_NAMES[template.level],
                subject=template.subject,
                title=template.title,
                description=template.description,
                slides=len(template.beats),
            )
        )
    return rows


def _find_template(level: EarlyLevel, topic_id: str) -> LessonTemplate:
    for template in _TEMPLATES:
        if template.level is level and template.topic_id == topic_id:
            return template
    available = ", ".join(
        t.topic_id for t in _TEMPLATES if t.level is level
    )
    raise ValueError(
        f"unknown {LEVEL_NAMES[level]} topic '{topic_id}'; choose: {available}"
    )


def _svg_data(
    *,
    title: str,
    symbol: str,
    color: str,
    animated: bool,
) -> str:
    safe_title = html.escape(title[:34])
    safe_symbol = html.escape(symbol[:24])
    motion = (
        """
        <animateTransform attributeName="transform" type="translate"
          values="0 0;0 -18;0 0" dur="2s" repeatCount="indefinite"/>
        """
        if animated
        else ""
    )
    sparkles = (
        """
        <circle cx="80" cy="70" r="8" fill="#fff" opacity=".75">
          <animate attributeName="opacity" values=".2;1;.2" dur="1.4s"
            repeatCount="indefinite"/>
        </circle>
        <circle cx="720" cy="130" r="12" fill="#fff" opacity=".6">
          <animate attributeName="r" values="6;15;6" dur="1.8s"
            repeatCount="indefinite"/>
        </circle>
        """
        if animated
        else ""
    )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="800" height="450"
      viewBox="0 0 800 450" role="img" aria-label="{safe_title}">
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="{color}"/>
          <stop offset="1" stop-color="#172554"/>
        </linearGradient>
      </defs>
      <rect width="800" height="450" rx="32" fill="url(#bg)"/>
      {sparkles}
      <g transform="translate(0 0)">
        {motion}
        <rect x="175" y="65" width="450" height="250" rx="36"
          fill="#fff" opacity=".96"/>
        <text x="400" y="225" text-anchor="middle" font-family="Arial,sans-serif"
          font-size="108" font-weight="700" fill="#172554">{safe_symbol}</text>
      </g>
      <text x="400" y="382" text-anchor="middle" font-family="Arial,sans-serif"
        font-size="42" font-weight="700" fill="#fff">{safe_title}</text>
    </svg>"""
    return "data:image/svg+xml," + urllib.parse.quote(svg, safe="")


def picture_data_url(
    beat: LessonBeat, label: str | None = None, symbol: str | None = None
) -> str:
    return _svg_data(
        title=label or beat.title,
        symbol=symbol or beat.symbol,
        color=beat.color,
        animated=False,
    )


def motion_data_url(
    beat: LessonBeat, label: str | None = None, symbol: str | None = None
) -> str:
    return _svg_data(
        title=label or beat.title,
        symbol=symbol or beat.symbol,
        color=beat.color,
        animated=True,
    )


def build_early_course(
    *,
    level: EarlyLevel,
    topic_id: str,
    language: str = "en",
    title: str | None = None,
    data_dir: Path | None = None,
    allow_xai_translation: bool = True,
) -> StudioCourse:
    template = _find_template(level, topic_id)
    lang = normalize_language(language)

    # The spoken words and the on-screen words must be the same language, or a
    # non-English voice just mispronounces English text at the child.
    translation = translate_beats(
        topic_id=template.topic_id,
        language=lang,
        beats=tuple(
            (b.title, b.words, b.say, b.activity) for b in template.beats
        ),
        data_dir=data_dir,
        allow_xai=allow_xai_translation,
    )
    spoken_language = lang if translation.source != "english" else "en"

    slides: list[CourseSlide] = []
    for i, (beat, text) in enumerate(zip(template.beats, translation.beats)):
        # Native-script reading lessons override the picture symbol.
        symbol = text.symbol or beat.symbol
        slides.append(
            CourseSlide(
                index=i,
                title=text.title,
                body=text.words,
                narration=text.say,
                picture_url=picture_data_url(beat, label=text.title, symbol=symbol),
                picture_alt=f"Picture for {text.title}",
                video_url=motion_data_url(beat, label=text.title, symbol=symbol),
                video_caption=f"Watch the picture for {text.title} move.",
                activity_prompt=text.activity,
                tags=[
                    "early_learning",
                    level.value,
                    template.subject.lower(),
                    template.topic_id,
                ],
            )
        )
    return StudioCourse(
        course_id=f"kids-{uuid.uuid4().hex[:10]}",
        title=title or (translation.beats[0].title if lang != "en" else template.title),
        category=CategoryId.OTHER,
        language=lang,
        audience=level.value,
        subject=template.subject,
        estimated_minutes=max(8, min(20, len(slides) * 2)),
        source_ids=[f"curated:{template.topic_id}"],
        slides=slides,
        profile_adaptations={
            "mode": "early_learning",
            "one_idea_per_slide": True,
            "read_aloud": True,
            "picture_led": True,
            "motion_clip": True,
            "level_name": LEVEL_NAMES[level],
            "requested_language": lang,
            # The language the WORDS are actually in — what TTS must speak.
            "spoken_language": spoken_language,
            "translation_source": translation.source,
            "translation_note": translation.note,
            "sound_specific": template.topic_id in SOUND_SPECIFIC_TOPICS,
            "reviewed_languages": ["en", *curated_languages(template.topic_id)],
            "language_name": language_name(spoken_language),
        },
        created_at_ms=int(time.time() * 1000),
        status="ready",
    )

