"""On-demand lesson visuals (SVG scenes / comparison panels / short animations).

Generates offline, deterministic teaching visuals from a student question so the
audio agent can narrate while the screen shows matching examples — e.g. state
driver's-license differences as a two-panel comparison.

No Stable Diffusion / paid image API. Uses cert_storyboard sprites + SVG.
A "video" here is a sequenced multi-frame SVG animation with narration beats
that clients play in sync with TTS.
"""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .cert_storyboard.generic import build_generic_storyboard, experience_dict
from .cert_storyboard.render import render_scene_svg
from .cert_storyboard.types import ObjectCallout, Scene

# Triggers that request an on-screen visual alongside the spoken answer.
_VISUAL_CUES = (
    "show me",
    "show us",
    "visualize",
    "visualise",
    "diagram",
    "illustration",
    "on the screen",
    "picture",
    "animation",
    "animate",
    "compare",
    "comparison",
    "difference",
    "differences",
    "versus",
    " vs ",
    "vs.",
    "example",
    "examples",
    "how does",
    "what does",
    "look like",
)

_COMPARE_CUES = (
    "compare",
    "comparison",
    "difference",
    "differences",
    "versus",
    " vs ",
    "vs.",
    "between",
)

_US_STATES: Tuple[Tuple[str, str], ...] = (
    ("alabama", "AL"), ("alaska", "AK"), ("arizona", "AZ"), ("arkansas", "AR"),
    ("california", "CA"), ("colorado", "CO"), ("connecticut", "CT"),
    ("delaware", "DE"), ("florida", "FL"), ("georgia", "GA"), ("hawaii", "HI"),
    ("idaho", "ID"), ("illinois", "IL"), ("indiana", "IN"), ("iowa", "IA"),
    ("kansas", "KS"), ("kentucky", "KY"), ("louisiana", "LA"), ("maine", "ME"),
    ("maryland", "MD"), ("massachusetts", "MA"), ("michigan", "MI"),
    ("minnesota", "MN"), ("mississippi", "MS"), ("missouri", "MO"),
    ("montana", "MT"), ("nebraska", "NE"), ("nevada", "NV"),
    ("new hampshire", "NH"), ("new jersey", "NJ"), ("new mexico", "NM"),
    ("new york", "NY"), ("north carolina", "NC"), ("north dakota", "ND"),
    ("ohio", "OH"), ("oklahoma", "OK"), ("oregon", "OR"), ("pennsylvania", "PA"),
    ("rhode island", "RI"), ("south carolina", "SC"), ("south dakota", "SD"),
    ("tennessee", "TN"), ("texas", "TX"), ("utah", "UT"), ("vermont", "VT"),
    ("virginia", "VA"), ("washington", "WA"), ("west virginia", "WV"),
    ("wisconsin", "WI"), ("wyoming", "WY"), ("district of columbia", "DC"),
)

# Curated teaching points for common DMV / license comparison topics.
_LICENSE_POINTS = (
    ("Minimum age", "Varies by state (often 15.5–16 with permit)"),
    ("Permit practice hours", "Many require 30–50 supervised hours"),
    ("Night driving limit", "Common for provisional licenses"),
    ("Passenger limits", "Often restricted for new teen drivers"),
    ("Real ID", "Federal standard; states phase in differently"),
    ("Renewal cycle", "Typically 4–8 years; check your DMV"),
)


@dataclass
class VisualFrame:
    """One beat of an animated visual sequence (SVG + narration cue)."""

    svg: str
    narration: str
    duration_s: float = 4.0
    title: str = ""
    kind: str = "scene"  # scene | compare | callout

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LessonVisual:
    """Payload attached to a tutor answer for on-screen teaching."""

    kind: str  # scene | compare | sequence
    title: str
    svg: str
    narration: str
    concept: str = ""
    examples: List[str] = field(default_factory=list)
    frames: List[VisualFrame] = field(default_factory=list)
    sync: str = "with_audio"  # client hint: play frames while TTS speaks
    topic: str = ""
    source: str = "lesson_visuals"

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "title": self.title,
            "svg": self.svg,
            "narration": self.narration,
            "concept": self.concept,
            "examples": list(self.examples),
            "frames": [f.to_dict() for f in self.frames],
            "sync": self.sync,
            "topic": self.topic,
            "source": self.source,
            "has_animation": bool(self.frames) or "@keyframes" in (self.svg or ""),
        }


def wants_visual(question: str) -> bool:
    q = f" {(question or '').lower()} "
    if any(c in q for c in _VISUAL_CUES):
        return True
    # Domain topics that benefit from a diagram even without an explicit ask.
    if any(t in q for t in ("license", "dmv", "permit", "traffic", "intersection", "food safety")):
        return True
    return False


def extract_us_states(question: str, *, limit: int = 4) -> List[Tuple[str, str]]:
    """Return [(full_name, abbr), ...] mentioned in the question (order preserved)."""
    q = (question or "").lower()
    found: List[Tuple[str, str]] = []
    seen_abbr: set[str] = set()
    # Longer names first so "new york" wins over bare fragments.
    for name, abbr in sorted(_US_STATES, key=lambda r: -len(r[0])):
        if abbr in seen_abbr:
            continue
        if name in q or re.search(rf"\b{re.escape(abbr.lower())}\b", q):
            display = "District of Columbia" if name == "district of columbia" else name.title()
            found.append((display, abbr))
            seen_abbr.add(abbr)
        if len(found) >= limit:
            break
    return found


def _esc(text: str) -> str:
    return html.escape(text or "", quote=False)


def _seed(text: str) -> int:
    return int(hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:8], 16)


def _comparison_svg(
    left: Tuple[str, str],
    right: Tuple[str, str],
    *,
    topic: str,
    points: Sequence[Tuple[str, str]],
) -> str:
    """Two-panel comparison card (deterministic SVG, no external assets)."""
    rows = ""
    for i, (label, detail) in enumerate(points[:5]):
        y = 200 + i * 52
        rows += (
            f'<text x="48" y="{y}" fill="#e2e8f0" font-size="15" font-family="system-ui,sans-serif">'
            f"{_esc(label)}</text>"
            f'<text x="48" y="{y + 20}" fill="#94a3b8" font-size="13" font-family="system-ui,sans-serif">'
            f"{_esc(detail)}</text>"
        )
    left_name, left_abbr = left
    right_name, right_abbr = right
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540" width="960" height="540">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0f172a"/><stop offset="100%" stop-color="#1e3a5f"/>
    </linearGradient>
    <style><![CDATA[
      .panel {{ animation: rise 0.7s ease-out both; }}
      .panel.right {{ animation-delay: 0.15s; }}
      .pulse {{ animation: pulse 2.2s ease-in-out infinite; }}
      @keyframes rise {{ from {{ opacity:0; transform: translateY(12px); }} to {{ opacity:1; transform: none; }} }}
      @keyframes pulse {{ 0%,100% {{ opacity:.85; }} 50% {{ opacity:1; }} }}
    ]]></style>
  </defs>
  <rect width="960" height="540" fill="url(#bg)"/>
  <text x="40" y="48" fill="#38bdf8" font-size="22" font-weight="700" font-family="system-ui,sans-serif">
    {_esc(topic[:72])}
  </text>
  <g class="panel">
    <rect x="32" y="72" width="430" height="420" rx="18" fill="#0b1220" stroke="#334155"/>
    <text x="56" y="118" fill="#f8fafc" font-size="28" font-weight="700" font-family="system-ui,sans-serif">{_esc(left_name)}</text>
    <text class="pulse" x="56" y="152" fill="#38bdf8" font-size="18" font-family="ui-monospace,monospace">{_esc(left_abbr)}</text>
    {rows}
  </g>
  <g class="panel right">
    <rect x="498" y="72" width="430" height="420" rx="18" fill="#0b1220" stroke="#334155"/>
    <text x="522" y="118" fill="#f8fafc" font-size="28" font-weight="700" font-family="system-ui,sans-serif">{_esc(right_name)}</text>
    <text class="pulse" x="522" y="152" fill="#fbbf24" font-size="18" font-family="ui-monospace,monospace">{_esc(right_abbr)}</text>
    <text x="522" y="220" fill="#e2e8f0" font-size="15" font-family="system-ui,sans-serif">Check local DMV rules</text>
    <text x="522" y="248" fill="#94a3b8" font-size="13" font-family="system-ui,sans-serif">Ages, hours, and limits differ by state</text>
    <text x="522" y="300" fill="#e2e8f0" font-size="15" font-family="system-ui,sans-serif">Same goal: safe licensed driving</text>
    <text x="522" y="328" fill="#94a3b8" font-size="13" font-family="system-ui,sans-serif">Always verify with the official handbook</text>
  </g>
</svg>"""


def _scene_visual(question: str, *, language: str = "en") -> LessonVisual:
    title = (question or "Lesson example").strip()[:72] or "Lesson example"
    exp = build_generic_storyboard(
        lesson_id="ask-visual",
        slide_index=0,
        title=title,
        body=question,
        narration=f"Here is a visual example for: {title}",
        language=language,
        profile={"primary_style": "visual"},
    )
    data = experience_dict(exp)
    svg = data.get("svg") or ""
    narration = data.get("narration") or exp.segment.scene.narration
    frames = [
        VisualFrame(svg=svg, narration=narration, duration_s=5.0, title=title, kind="scene"),
    ]
    # Second beat: zoom callout style via same scene with different camera feel
    scene2 = Scene(
        scene_id=exp.segment.scene.scene_id + "-b",
        title=title,
        backdrop=exp.segment.scene.backdrop,
        camera="push-in",
        narration="Notice the labeled parts — match them to the spoken explanation.",
        cast=exp.segment.scene.cast,
        objects=exp.segment.scene.objects
        + (ObjectCallout(label="Key idea", x=480, y=80),),
        concept=exp.segment.scene.concept,
        duration_hint_s=5.0,
    )
    svg2 = render_scene_svg(scene2)
    frames.append(
        VisualFrame(
            svg=svg2,
            narration=scene2.narration,
            duration_s=5.0,
            title="Focus",
            kind="callout",
        )
    )
    return LessonVisual(
        kind="sequence",
        title=title,
        svg=svg,
        narration=narration,
        concept=exp.segment.scene.concept,
        examples=list(exp.examples),
        frames=frames,
        topic="general",
    )


def _license_compare_visual(question: str, states: Sequence[Tuple[str, str]]) -> LessonVisual:
    left = states[0] if states else ("California", "CA")
    right = states[1] if len(states) > 1 else ("Texas", "TX")
    topic = "Driver's license: state differences"
    svg = _comparison_svg(left, right, topic=topic, points=_LICENSE_POINTS)
    narration = (
        f"Let's compare {left[0]} and {right[0]}. "
        "Minimum age, practice hours, night limits, and passenger rules often differ. "
        "Always check each state's official DMV handbook for the current rules."
    )
    # Frame 2: road scene for "how it looks in practice"
    exp = build_generic_storyboard(
        lesson_id="ask-dmv-compare",
        slide_index=1,
        title="On the road",
        body=f"Provisional rules in {left[0]} vs {right[0]}",
        narration="On the road, provisional rules shape when and with whom a new driver can travel.",
        language="en",
        profile={"primary_style": "visual"},
    )
    road = experience_dict(exp)
    frames = [
        VisualFrame(svg=svg, narration=narration, duration_s=8.0, title=topic, kind="compare"),
        VisualFrame(
            svg=road.get("svg") or svg,
            narration=road.get("narration") or "Apply the safer rule when you are unsure.",
            duration_s=6.0,
            title="On the road",
            kind="scene",
        ),
    ]
    return LessonVisual(
        kind="sequence",
        title=topic,
        svg=svg,
        narration=narration,
        concept=f"{left[0]} vs {right[0]} license rules",
        examples=[
            f"{left[0]} ({left[1]}) — check local permit age and hours",
            f"{right[0]} ({right[1]}) — compare night and passenger limits",
        ],
        frames=frames,
        topic="drivers_license",
    )


def generate_lesson_visual(
    question: str,
    *,
    language: str = "en",
    answer_text: str = "",
    force: bool = False,
) -> Optional[LessonVisual]:
    """Build a visual for ``question`` when the student asks for examples / comparisons.

    Returns None when no visual is warranted (unless ``force``).
    """
    q = (question or "").strip()
    if not q:
        return None
    if not force and not wants_visual(q):
        return None

    q_l = f" {q.lower()} "
    states = extract_us_states(q)
    license_topic = any(
        t in q_l for t in ("license", "licence", "dmv", "permit", "provisional", "driver")
    )
    compare = any(c in q_l for c in _COMPARE_CUES) or len(states) >= 2

    if license_topic and (compare or states):
        return _license_compare_visual(q, states)

    if compare and states:
        # Generic state compare (non-license): still use comparison card with soft points
        left = states[0]
        right = states[1] if len(states) > 1 else ("Another state", "--")
        points = (
            ("Policy focus", "Rules and timelines can differ"),
            ("Local agency", "Confirm with the official state site"),
            ("Shared goal", "Clear, lawful practice for learners"),
        )
        topic = f"{left[0]} vs {right[0]}"
        svg = _comparison_svg(left, right, topic=topic, points=points)
        narration = (
            f"Here is a side-by-side look at {left[0]} and {right[0]}. "
            + ((answer_text or "").strip()[:220] or "Use the panels to track the differences while I explain.")
        )
        return LessonVisual(
            kind="compare",
            title=topic,
            svg=svg,
            narration=narration,
            concept=topic,
            examples=[left[0], right[0]],
            frames=[VisualFrame(svg=svg, narration=narration, duration_s=8.0, title=topic, kind="compare")],
            topic="comparison",
        )

    return _scene_visual(q, language=language)


def visual_for_ask(
    question: str,
    *,
    language: str = "en",
    answer_text: str = "",
) -> Optional[Dict[str, Any]]:
    """Convenience for API / Answer.visual field."""
    vis = generate_lesson_visual(question, language=language, answer_text=answer_text)
    return vis.to_dict() if vis else None
