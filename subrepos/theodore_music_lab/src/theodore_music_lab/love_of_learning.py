"""Local karaoke: Love of Learning (Khmer + English).

Source video: data/video/love_of_learning_khmer.mp4 (~227s). Each lyric line is a
pause point so a learner can read Khmer, English, or any of the other 25
supported languages before continuing.
"""

from __future__ import annotations

from typing import Any

# duration from ffprobe; leave a short trailer after the last line.
DURATION_SEC = 227.2
LEAD_IN_SEC = 3.0
TRAIL_SEC = 4.0

# (section, source_lang, text, text_en, text_km, weight)
# text = what appears on the karaoke (source script). text_en is always the
# English gloss used for translation into other languages. text_km is the Khmer
# form when we have one (source or a hand gloss of an English line).
_RAW: tuple[tuple[str, str, str, str, str, float], ...] = (
    # ---- Verse 1 -----------------------------------------------------------
    ("verse", "en", "My life, was not worth much.",
     "My life was not worth much.",
     "ជីវិតខ្ញុំ គ្មានតម្លៃប៉ុន្មានទេ។", 1.1),
    ("verse", "en", "I was down--no lunch, no luck.",
     "I was down — no lunch, no luck.",
     "ខ្ញុំធ្លាក់ចុះ — គ្មានអាហារថ្ងៃត្រង់ គ្មានសំណាង។", 1.1),
    ("verse", "km", "ធំធាត់ក្នុងផ្ទះបាយចាស់",
     "Growing up in a house of leftover rice",
     "ធំធាត់ក្នុងផ្ទះបាយចាស់", 1.0),
    ("verse", "km", "ជញ្ជាំងបែកៗ ខ្យល់ចូលតាមរន្ធ",
     "Cracked walls, wind coming in through the holes",
     "ជញ្ជាំងបែកៗ ខ្យល់ចូលតាមរន្ធ", 1.0),
    ("verse", "km", "ម្តាយដេរខោអាវក្រោមភ្លើងស្រអាប់",
     "Mother sewed clothes under dim light",
     "ម្តាយដេរខោអាវក្រោមភ្លើងស្រអាប់", 1.0),
    ("verse", "km", "ឪពុកកាន់ដៃខ្ញុំ ពេលជំងឺមកលើគ្រែ",
     "Father held my hand when illness put me on the bed",
     "ឪពុកកាន់ដៃខ្ញុំ ពេលជំងឺមកលើគ្រែ", 1.15),
    ("verse", "km", "ស្រុកខ្មែរ​មានភក់ក្រោយភ្លៀង",
     "Khmer land has mud after the rain",
     "ស្រុកខ្មែរ​មានភក់ក្រោយភ្លៀង", 1.0),
    ("verse", "km", "មានអង្ករបន្តិច ក្នុងចានលើតុឈើ",
     "A little rice in a bowl on a wooden table",
     "មានអង្ករបន្តិច ក្នុងចានលើតុឈើ", 1.0),
    ("verse", "km", "តែខ្ញុំឃើញអក្សរលើក្តារខៀន",
     "But I saw letters on the blackboard",
     "តែខ្ញុំឃើញអក្សរលើក្តារខៀន", 1.0),
    ("verse", "km", "ដូចពន្លឺតូចមួយ កណ្ដាលថ្ងៃងងឹត",
     "Like a small light in the middle of a dark day",
     "ដូចពន្លឺតូចមួយ កណ្ដាលថ្ងៃងងឹត", 1.1),
    # ---- Pre-chorus --------------------------------------------------------
    ("pre", "km", "ពេលខ្យល់បោកទ្វារ",
     "When the wind slammed the door",
     "ពេលខ្យល់បោកទ្វារ", 0.85),
    ("pre", "km", "ខ្ញុំនៅតែបើកសៀវភៅ",
     "I still opened the book",
     "ខ្ញុំនៅតែបើកសៀវភៅ", 0.85),
    ("pre", "km", "ពេលទឹកភ្នែកហូរ",
     "When tears flowed",
     "ពេលទឹកភ្នែកហូរ", 0.85),
    ("pre", "km", "ខ្ញុំសរសេរឈ្មោះខ្លួនឯងឲ្យច្បាស់",
     "I wrote my own name clearly",
     "ខ្ញុំសរសេរឈ្មោះខ្លួនឯងឲ្យច្បាស់", 1.0),
    # ---- Chorus ------------------------------------------------------------
    ("chorus", "km", "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ",
     "The love of learning",
     "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ", 0.9),
    ("chorus", "km", "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ",
     "The love of learning",
     "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ", 0.9),
    ("chorus", "km", "វាជាព្រលឹងខ្ញុំ (ព្រលឹងខ្ញុំ)",
     "It is my soul (my soul)",
     "វាជាព្រលឹងខ្ញុំ (ព្រលឹងខ្ញុំ)", 1.0),
    ("chorus", "km", "វាជាថាមពលខ្ញុំ (ថាមពលខ្ញុំ)",
     "It is my power (my power)",
     "វាជាថាមពលខ្ញុំ (ថាមពលខ្ញុំ)", 1.0),
    ("chorus", "km", "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ",
     "The love of learning",
     "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ", 0.9),
    ("chorus", "km", "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ",
     "The love of learning",
     "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ", 0.9),
    ("chorus", "km", "ពីក្រីក្រឡើងទៅមុខ",
     "From poverty rising forward",
     "ពីក្រីក្រឡើងទៅមុខ", 1.0),
    ("chorus", "km", "ខ្ញុំមិនឈប់សុបិនទេ",
     "I never stop dreaming",
     "ខ្ញុំមិនឈប់សុបិនទេ", 1.0),
    # ---- Verse 2 -----------------------------------------------------------
    ("verse", "en", "I had a life not worth living.",
     "I had a life not worth living.",
     "ខ្ញុំមានជីវិតដែលមិនសមនឹងរស់។", 1.1),
    ("verse", "en", "I had a world--no beginning.",
     "I had a world — no beginning.",
     "ខ្ញុំមានពិភពមួយ — គ្មានការចាប់ផ្ដើម។", 1.1),
    ("verse", "km", "ខ្ញុំដើរឆ្លងសាលាបឋម",
     "I walked through primary school",
     "ខ្ញុំដើរឆ្លងសាលាបឋម", 1.0),
    ("verse", "km", "ស្បែកជើងជ្រាបទឹក ក្បាលកាន់តែខ្ពស់",
     "Shoes soaking wet, head held higher",
     "ស្បែកជើងជ្រាបទឹក ក្បាលកាន់តែខ្ពស់", 1.05),
    ("verse", "km", "នៅពេលមិត្តៗខ្លះសើចថាខ្ញុំយឺត",
     "When some friends laughed that I was slow",
     "នៅពេលមិត្តៗខ្លះសើចថាខ្ញុំយឺត", 1.05),
    ("verse", "km", "ខ្ញុំឆ្លើយតបដោយអក្សរលើក្រដាស",
     "I answered with letters on paper",
     "ខ្ញុំឆ្លើយតបដោយអក្សរលើក្រដាស", 1.0),
    ("verse", "km", "បណ្ណាល័យជាផ្ទះទីពីរ",
     "The library was my second home",
     "បណ្ណាល័យជាផ្ទះទីពីរ", 1.0),
    ("verse", "km", "ក្លិនក្រដាសចាស់ លាយនឹងចិត្តស្ងប់",
     "Smell of old paper mixed with a calm heart",
     "ក្លិនក្រដាសចាស់ លាយនឹងចិត្តស្ងប់", 1.05),
    ("verse", "km", "មុខវិជ្ជាខ្ញុំដូចស្ពានតូចៗ",
     "My subjects were like little bridges",
     "មុខវិជ្ជាខ្ញុំដូចស្ពានតូចៗ", 1.0),
    ("verse", "km", "ឆ្លងពីអតីតកាល ទៅថ្ងៃស្អែក",
     "Crossing from the past to tomorrow",
     "ឆ្លងពីអតីតកាល ទៅថ្ងៃស្អែក", 1.05),
    # ---- Pre-chorus 2 ------------------------------------------------------
    ("pre", "km", "ទោះខ្លួនឈឺ",
     "Even when my body hurt",
     "ទោះខ្លួនឈឺ", 0.8),
    ("pre", "km", "ខ្ញុំនៅតែចង់ដឹង",
     "I still wanted to know",
     "ខ្ញុំនៅតែចង់ដឹង", 0.85),
    ("pre", "km", "ទោះហត់ខ្លាំង",
     "Even when exhausted",
     "ទោះហត់ខ្លាំង", 0.8),
    ("pre", "km", "ខ្ញុំនៅតែទៅជួបពន្លឺ",
     "I still went to meet the light",
     "ខ្ញុំនៅតែទៅជួបពន្លឺ", 1.0),
    # ---- Chorus 2 ----------------------------------------------------------
    ("chorus", "km", "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ",
     "The love of learning",
     "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ", 0.9),
    ("chorus", "km", "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ",
     "The love of learning",
     "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ", 0.9),
    ("chorus", "km", "វាជាព្រលឹងខ្ញុំ (ព្រលឹងខ្ញុំ)",
     "It is my soul (my soul)",
     "វាជាព្រលឹងខ្ញុំ (ព្រលឹងខ្ញុំ)", 1.0),
    ("chorus", "km", "វាជាថាមពលខ្ញុំ (ថាមពលខ្ញុំ)",
     "It is my power (my power)",
     "វាជាថាមពលខ្ញុំ (ថាមពលខ្ញុំ)", 1.0),
    ("chorus", "km", "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ",
     "The love of learning",
     "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ", 0.9),
    ("chorus", "km", "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ",
     "The love of learning",
     "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ", 0.9),
    ("chorus", "km", "ពីក្រីក្រឡើងទៅមុខ",
     "From poverty rising forward",
     "ពីក្រីក្រឡើងទៅមុខ", 1.0),
    ("chorus", "km", "ខ្ញុំមិនឈប់សុបិនទេ",
     "I never stop dreaming",
     "ខ្ញុំមិនឈប់សុបិនទេ", 1.0),
    # ---- Bridge ------------------------------------------------------------
    ("bridge", "km", "ខ្ញុំមិនភ្លេចដីក្រហមក្រោមជើង",
     "I do not forget the red earth under my feet",
     "ខ្ញុំមិនភ្លេចដីក្រហមក្រោមជើង", 1.1),
    ("bridge", "km", "មិនភ្លេចដងស្ទឹង បាត់បង់ពេលភ្លៀងធ្លាក់",
     "Do not forget the river lost when rain fell",
     "មិនភ្លេចដងស្ទឹង បាត់បង់ពេលភ្លៀងធ្លាក់", 1.1),
    ("bridge", "km", "ប៉ុន្តែខ្ញុំយកឈ្មោះខ្ញុំ",
     "But I take my name",
     "ប៉ុន្តែខ្ញុំយកឈ្មោះខ្ញុំ", 0.95),
    ("bridge", "km", "ទៅដាក់លើទំព័របន្ទាប់",
     "And place it on the next page",
     "ទៅដាក់លើទំព័របន្ទាប់", 0.95),
    ("bridge", "km", "ឲ្យក្មេងតូចៗបានឃើញ",
     "So little children can see",
     "ឲ្យក្មេងតូចៗបានឃើញ", 1.0),
    ("bridge", "km", "ថាផ្លូវឆ្ងាយក៏ទៅដល់",
     "That a long road can still be reached",
     "ថាផ្លូវឆ្ងាយក៏ទៅដល់", 1.0),
    ("bridge", "km", "បើបេះដូងនៅតែស្រឡាញ់",
     "If the heart still loves",
     "បើបេះដូងនៅតែស្រឡាញ់", 1.0),
    ("bridge", "km", "ការស្រាវជ្រាវ និងការរៀន",
     "Research and learning",
     "ការស្រាវជ្រាវ និងការរៀន", 1.05),
    # ---- Final chorus ------------------------------------------------------
    ("chorus", "km", "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ",
     "The love of learning",
     "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ", 0.9),
    ("chorus", "km", "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ",
     "The love of learning",
     "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ", 0.9),
    ("chorus", "km", "វាជាព្រលឹងខ្ញុំ (ព្រលឹងខ្ញុំ)",
     "It is my soul (my soul)",
     "វាជាព្រលឹងខ្ញុំ (ព្រលឹងខ្ញុំ)", 1.0),
    ("chorus", "km", "វាជាថាមពលខ្ញុំ (ថាមពលខ្ញុំ)",
     "It is my power (my power)",
     "វាជាថាមពលខ្ញុំ (ថាមពលខ្ញុំ)", 1.0),
    ("chorus", "km", "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ",
     "The love of learning",
     "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ", 0.9),
    ("chorus", "km", "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ",
     "The love of learning",
     "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ", 0.9),
    ("chorus", "km", "ពីស្រុកខ្មែរ ទៅថ្ងៃថ្មី",
     "From Khmer land to a new day",
     "ពីស្រុកខ្មែរ ទៅថ្ងៃថ្មី", 1.05),
    ("chorus", "km", "ខ្ញុំកើតមកដើម្បីរៀន",
     "I was born to learn",
     "ខ្ញុំកើតមកដើម្បីរៀន", 1.15),
)


def _timed_verses() -> list[dict[str, Any]]:
    usable = max(1.0, DURATION_SEC - LEAD_IN_SEC - TRAIL_SEC)
    total_w = sum(row[5] for row in _RAW) or 1.0
    cursor = LEAD_IN_SEC
    verses: list[dict[str, Any]] = []
    for index, (section, source_lang, text, text_en, text_km, weight) in enumerate(_RAW, start=1):
        span = usable * (weight / total_w)
        start = round(cursor, 3)
        end = round(cursor + span, 3)
        cursor = end
        focus = {
            "chorus": "vocabulary",
            "pre": "grammar",
            "bridge": "comprehension",
            "verse": "vocabulary",
        }.get(section, "vocabulary")
        verses.append(
            {
                "verse_no": index,
                "section": section,
                "source_lang": source_lang,
                "start_sec": start,
                "pause_sec": end,
                "text": text,
                "text_en": text_en,
                "text_km": text_km,
                "focus": focus,
                "terms": [],
                "questions": [
                    {
                        "kind": "comprehension",
                        "prompt": "What does this line mean?",
                        "answer": text_en,
                    }
                ],
            }
        )
    return verses


def love_of_learning_embed() -> dict[str, Any]:
    """Catalogue row for the local Khmer/English karaoke MP4."""
    return {
        "embed_id": "karaoke-love-of-learning-km",
        "kind": "local-karaoke",
        "youtube_id": "",
        "video_file": "love_of_learning_khmer.mp4",
        "title": "សេចក្ដីស្រឡាញ់ការរៀនសូត្រ — Love of Learning",
        "channel": "Local karaoke",
        "url": "/api/music/video/love_of_learning_khmer.mp4",
        "playlist_url": "",
        "duration_sec": DURATION_SEC,
        "language": "km",
        "topic": "Khmer + English karaoke · poverty, school, love of learning",
        "note": (
            "Bilingual karaoke (Khmer verses with English bookends). Pause on "
            "every line to read Khmer, English, or any of 27 languages, then "
            "ask about grammar or vocabulary before continuing."
        ),
        "verses": _timed_verses(),
    }
