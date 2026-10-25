"""The fixed lines the apps say out loud that are not course text, so the default voice (Sage) speaks them too.

  python3 -m tts_bakeoff.demo_voice.fixed_lines --capture [--api https://salareen.com]   # rewrite tts_manifest/fixed_spoken_lines.json
  python3 -m tts_bakeoff.demo_voice.fixed_lines --check                                  # spoken keys in the source vs this list

What is spoken, found by reading the code (apps/web/app/components/OnTheGo.tsx), not guessed: the spoken answers to voice commands
(pause, resume, skip, repeat, restart, speed), the course announcements ("Playing <title>.", "Next course: <title>.", the short course list),
the question-limit messages, and the away/back prompts. Their English text is the app's own i18n string, so the audio and the screen cannot
drift. Lines that carry a run-time value are expanded over the values that can occur: the playback speeds (0.7 to 1.6), the retry seconds
(1 to 60) and the titles of the curated demo courses. What cannot be enumerated (a spoken answer built from the course text, a course name
the visitor made up) is not here: those lines fall back to an edge-tts voice of the same gender, as before.

Not spoken today, so not here: the game and demo tutorials (text overlays), the friendly mascot error messages and the widget status text.
The tutorial lines of the Vision Play JS and the quiz bank come in through manifest.vision_play().
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXED = ROOT / "tts_manifest" / "fixed_spoken_lines.json"
I18N_PAGES = ROOT / "apps" / "web" / "app" / "lib" / "i18n-pages.ts"
CATALOG = ROOT / "apps" / "web" / "app" / "lib" / "onTheGoCatalog.ts"
VOICE_COMMANDS = ROOT / "apps" / "web" / "app" / "lib" / "voiceCommands.ts"
ON_THE_GO = ROOT / "apps" / "web" / "app" / "components" / "OnTheGo.tsx"
DEMO = "on_the_go_fixed"

# i18n keys the code speaks with no run-time value.
STATIC_KEYS = (
    "drive.pausedAnswer", "drive.resumingAnswer", "drive.skipAnswer", "drive.repeatAnswer", "drive.restartAnswer",
    "drive.backToCourse", "drive.limitSession", "drive.awayPaused", "drive.backResume",
)
TITLE_KEYS = ("drive.coursePlaying", "drive.courseNextIs")   # {title}: one line per curated demo course
SPEED_KEY = "drive.speedAnswer"                               # {rate}
LIMIT_KEY = "drive.limitRate"                                 # {seconds}
LIST_KEY = "drive.courseList"                                 # {titles}: the first five curated titles, the way handleCourseCommand builds it
SKIPPED_KEYS = {                                              # spoken, but built from run-time text: cannot be enumerated
    "drive.courseUnknown": "{name} is whatever the visitor said",
    "drive.groundedAnswer": "{snippet} is a passage of the course text",
}
# Keys that are only a status label on screen today. They are included because the presence prompts may be voiced; the guard ignores them.
_STATUS_ONLY = {"drive.awayPaused", "drive.backResume"}


def en_string(key: str, path: Path = I18N_PAGES) -> str:
    """The English text of an i18n key: the first definition in the file (the English dictionary comes first)."""
    m = re.search(r'^\s*"' + re.escape(key) + r'":\s*("(?:[^"\\\n]|\\.)*")\s*,?\s*$', path.read_text(encoding="utf-8"), re.M)
    if not m:
        raise KeyError(f"i18n key {key!r} not found in {path}")
    return json.loads(m.group(1))


def js_number(x: float) -> str:
    """How JavaScript prints a number in a template ("1", "0.85", "1.5"): the speed answer is spoken from this text."""
    r = round(x, 2)
    return str(int(r)) if r == int(r) else f"{r:g}"


def playback_rates() -> list[str]:
    src = VOICE_COMMANDS.read_text(encoding="utf-8")
    lo = float(re.search(r"MIN_PLAYBACK_RATE\s*=\s*([\d.]+)", src).group(1))
    hi = float(re.search(r"MAX_PLAYBACK_RATE\s*=\s*([\d.]+)", src).group(1))
    out, x = [], lo
    while x <= hi + 1e-9:
        out.append(js_number(x))
        x = round(x + 0.05, 2)
    return out


def demo_course_ids(path: Path = CATALOG) -> list[str]:
    block = path.read_text(encoding="utf-8").split("DEMO_COURSE_IDS", 1)[1].split("];", 1)[0]
    return re.findall(r'"(audio-[a-z0-9-]+)"', block)


def clean_title(title: str) -> str:
    return re.sub(r"\s*\(audio\)\s*$", "", title or "", flags=re.I).strip()   # same as cleanTitle() in onTheGoCatalog.ts


def capture_titles(api: str = "https://salareen.com", ids: list[str] | None = None) -> dict[str, str]:
    titles = {}
    for cid in ids or demo_course_ids():
        with urllib.request.urlopen(f"{api.rstrip('/')}/curriculum/audio/courses/{cid}?locale=en", timeout=30) as r:
            titles[cid] = json.load(r)["title"]
    return titles


def fill(template: str, **values) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: str(values[m.group(1)]), template)


def build(titles: dict[str, str]) -> list[dict]:
    """The committed list: [{"demo", "source", "text"}], in a stable order, no duplicates."""
    rows: list[dict] = []

    def add(source: str, text: str):
        rows.append({"demo": DEMO, "source": source, "text": text})

    for key in STATIC_KEYS:
        add(key, en_string(key))
    for rate in playback_rates():
        add(SPEED_KEY, fill(en_string(SPEED_KEY), rate=rate))
    for seconds in range(1, 61):
        add(LIMIT_KEY, fill(en_string(LIMIT_KEY), seconds=seconds))
    ordered = [clean_title(titles[i]) for i in demo_course_ids() if i in titles]
    for key in TITLE_KEYS:
        for title in ordered:
            add(key, fill(en_string(key), title=title))
    if ordered:
        add(LIST_KEY, fill(en_string(LIST_KEY), titles=", ".join(ordered[:5])))
    seen, out = set(), []
    for r in rows:
        if r["text"] not in seen:
            seen.add(r["text"])
            out.append(r)
    return out


def load(path: Path = FIXED) -> list[dict]:
    if not Path(path).is_file():
        return []
    return json.loads(Path(path).read_text(encoding="utf-8")).get("lines", [])


def spoken_keys_in_source(path: Path = ON_THE_GO) -> set[str]:
    """Every i18n key OnTheGo.tsx hands to a speaking helper: announceThen(t("k"...)), say("k"...), speak(t("k"...)), and the
    `go(id, "k")` course announcements. The test compares this with what this module knows, so a new spoken line cannot slip by."""
    src = path.read_text(encoding="utf-8")
    keys: set[str] = set()
    for m in re.finditer(r"announceThen\(", src):
        keys |= set(re.findall(r't\(\s*"(drive\.[A-Za-z]+)"', src[m.end():m.end() + 240].split(" () =>")[0]))
    keys |= set(re.findall(r'\bsay\(\s*"(drive\.[A-Za-z]+)"', src))
    keys |= set(re.findall(r'\bspeak\(\s*t\(\s*"(drive\.[A-Za-z]+)"', src))
    keys |= set(re.findall(r'"(drive\.course(?:Playing|NextIs))"', src))
    return keys


def known_keys() -> set[str]:
    return set(STATIC_KEYS) | set(TITLE_KEYS) | {SPEED_KEY, LIMIT_KEY, LIST_KEY} | set(SKIPPED_KEYS)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture", action="store_true", help="fetch the demo course titles and rewrite tts_manifest/fixed_spoken_lines.json")
    ap.add_argument("--api", default="https://salareen.com")
    ap.add_argument("--check", action="store_true", help="exit 1 when OnTheGo.tsx speaks a key this module does not know")
    args = ap.parse_args(argv)
    if args.capture:
        titles = capture_titles(args.api)
        rows = build(titles)
        FIXED.write_text(json.dumps({"source": "apps/web/app/components/OnTheGo.tsx + i18n-pages.ts + onTheGoCatalog.ts",
                                     "titles": titles, "skipped": SKIPPED_KEYS, "lines": rows}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        by: dict[str, int] = {}
        for r in rows:
            by[r["source"]] = by.get(r["source"], 0) + 1
        print(f"{len(rows)} fixed spoken lines -> {FIXED}")
        for k, v in sorted(by.items()):
            print(f"  {k:26s} {v}")
        return 0
    if args.check:
        unknown = sorted(spoken_keys_in_source() - known_keys())
        if unknown:
            print("OnTheGo.tsx speaks keys fixed_lines.py does not know:", ", ".join(unknown))
            return 1
        print("every spoken key is accounted for")
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
