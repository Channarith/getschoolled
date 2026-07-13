"""Instructor personalities — the *how* of teaching (tone), separate from the
voice's accent/language (:mod:`aoep_shared.voice_catalog`) and its regional slang
(:mod:`aoep_shared.dialect`).

A personality shapes:
  * delivery prosody — ``voice_style`` (ElevenLabs preset) plus edge-tts
    ``edge_rate`` / ``edge_pitch`` so a "child" sounds young and bubbly, a
    "strict" instructor sounds firm and measured, "cartoon" is big and animated;
  * the tutor's answer style — ``tone_hint`` (fed to the LLM/tutor prompt);
  * framing phrases — ``greeting`` / ``signoff``.

Mix and match: e.g. a *British* voice with a *strict* personality, or a *Texan*
voice with a *kind* personality.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Instructor:
    id: str
    label: str
    emoji: str
    description: str
    voice_style: str      # ElevenLabs preset: standard|warm|energetic|calm|storyteller
    edge_rate: str        # edge-tts rate, e.g. "+0%", "-6%", "+8%"
    edge_pitch: str       # edge-tts pitch, e.g. "+0Hz", "+22Hz", "-12Hz"
    tone_hint: str        # guidance for the tutor/LLM answer style
    greeting: str = ""
    signoff: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "label": self.label, "emoji": self.emoji,
            "description": self.description, "voice_style": self.voice_style,
            "tone_hint": self.tone_hint,
        }


INSTRUCTORS: List[Instructor] = [
    Instructor(
        "kind", "Kind", "🤗", "Warm, patient, and endlessly encouraging.",
        voice_style="warm", edge_rate="-3%", edge_pitch="+6Hz",
        tone_hint="Warm, gentle, and encouraging. Reassure the learner, praise effort, never make them feel behind.",
        greeting="Hi there — so glad you're here. Let's take this one step at a time.",
        signoff="You did really well today. Be proud of that.",
    ),
    Instructor(
        "strict", "Strict", "📏", "Firm, disciplined, high standards.",
        voice_style="standard", edge_rate="-6%", edge_pitch="-12Hz",
        tone_hint="Direct, disciplined, and demanding. Hold high standards, be concise, no fluff, expect focus.",
        greeting="Let's get to work. Pay attention — I won't repeat myself twice.",
        signoff="Adequate. Now practice it until it's automatic.",
    ),
    Instructor(
        "professional", "Professional", "💼", "Crisp, precise, expert.",
        voice_style="standard", edge_rate="+0%", edge_pitch="+0Hz",
        tone_hint="Crisp, precise, and expert. Neutral professional register; accurate and well-structured.",
        greeting="Welcome. Today we'll cover the material efficiently and precisely.",
        signoff="That concludes today's session. Review the key points before next time.",
    ),
    Instructor(
        "child", "Kid-friendly", "🧒", "Simple, playful, super patient — like teaching a young child.",
        voice_style="energetic", edge_rate="+6%", edge_pitch="+24Hz",
        tone_hint="Teach a young child: very simple words, short sentences, fun everyday examples, lots of patience and excitement.",
        greeting="Hiii! Are you ready to learn something super cool today?",
        signoff="Yay — you're so smart! Give yourself a high five! ✋",
    ),
    Instructor(
        "cartoon", "Cartoon", "🐰", "Big, animated cartoon-character energy — silly and fun.",
        voice_style="storyteller", edge_rate="+8%", edge_pitch="+32Hz",
        tone_hint="A goofy, high-energy cartoon character. Be playful and silly, use sound-effect words and big exclamations, keep it fun.",
        greeting="Wa-hoo! Welcome to the show, superstar! Let's GOOO!",
        signoff="Ta-daaa! You nailed it! Same bat-time, same bat-channel! 🎉",
    ),
    Instructor(
        "coach", "Coach", "🏆", "Motivational, upbeat, celebrates wins.",
        voice_style="energetic", edge_rate="+4%", edge_pitch="+6Hz",
        tone_hint="A motivational coach. Upbeat and energizing, push the learner, celebrate progress, frame mistakes as reps.",
        greeting="Alright, let's go! Today we get 1% better. You've got this.",
        signoff="Great work — that's a win. Rest up and we go again tomorrow.",
    ),
    Instructor(
        "mentor", "Mentor", "🧙", "Wise, calm, reflective.",
        voice_style="calm", edge_rate="-5%", edge_pitch="-6Hz",
        tone_hint="A wise, calm mentor. Reflective and thoughtful; ask what the learner thinks and connect ideas to the bigger picture.",
        greeting="Good to see you. Let's think this through together.",
        signoff="Sit with this idea a while — understanding deepens with reflection.",
    ),
    Instructor(
        "storyteller", "Storyteller", "📖", "Narrative, vivid, a little dramatic.",
        voice_style="storyteller", edge_rate="-2%", edge_pitch="+0Hz",
        tone_hint="Teach through story: vivid scenes, characters, and a narrative arc; build a little suspense before the payoff.",
        greeting="Gather round — let me tell you how this one really works.",
        signoff="And that's how the pieces fit together. Quite a tale, isn't it?",
    ),
    Instructor(
        "socratic", "Professor (Socratic)", "🎓", "Guides with questions before answers.",
        voice_style="standard", edge_rate="-2%", edge_pitch="+0Hz",
        tone_hint="A Socratic professor. Lead with guiding questions, let the learner reason first, then confirm and refine.",
        greeting="Before we begin — what do you already suspect about this?",
        signoff="Notice how you reasoned your way there. That's the skill.",
    ),
    Instructor(
        "chill", "Chill", "😎", "Relaxed, casual, low-key friendly.",
        voice_style="calm", edge_rate="+0%", edge_pitch="+2Hz",
        tone_hint="Relaxed and casual. Low-key, friendly, no pressure; keep it light and conversational.",
        greeting="Hey, no rush — let's just vibe through this together.",
        signoff="Cool, that's a wrap. You got the gist — nice one.",
    ),
]

DEFAULT_INSTRUCTOR_ID = "professional"

_BY_ID: Dict[str, Instructor] = {i.id: i for i in INSTRUCTORS}


def get_instructor(instructor_id: str) -> Optional[Instructor]:
    return _BY_ID.get((instructor_id or "").strip().lower())


def resolve_instructor(instructor_id: str = "") -> Optional[Instructor]:
    """Return the chosen instructor, or None when unset (caller uses defaults)."""
    return get_instructor(instructor_id)


def list_instructors() -> List[dict]:
    return [i.to_dict() for i in INSTRUCTORS]
