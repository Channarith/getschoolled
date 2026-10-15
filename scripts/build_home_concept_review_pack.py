#!/usr/bin/env python3
"""Build a single-file homepage-concept review pack for Telegram.

The HTML embeds the concept CSS and artwork, so it opens from a download
without the Salareen app or a local server.
"""

from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "apps/web/public"
CSS = ROOT / "apps/web/app/components/home-concepts/homeConcepts.module.css"
OUT_DIR = ROOT / "docs/reviews"
HTML_NAME = "salareen-home-concepts-review.html"


def _uri(path: Path, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def _teacher_uri() -> str:
    image = Image.open(PUBLIC / "themes/corporate.png").convert("RGB")
    image.thumbnail((900, 1200))
    buffer = io.BytesIO()
    image.save(buffer, "WEBP", quality=72, method=6)
    encoded = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/webp;base64,{encoded}"


def _css() -> str:
    css = CSS.read_text()
    replacements = {
        "/landing-concepts/aurora-story.webp": _uri(PUBLIC / "landing-concepts/aurora-story.webp", "image/webp"),
        "/landing-concepts/learning-worlds.webp": _uri(PUBLIC / "landing-concepts/learning-worlds.webp", "image/webp"),
        "/landing-concepts/signal-studio.webp": _uri(PUBLIC / "landing-concepts/signal-studio.webp", "image/webp"),
        "/landing-concepts/human-journal.webp": _uri(PUBLIC / "landing-concepts/human-journal.webp", "image/webp"),
        "/themes/corporate.png": _teacher_uri(),
    }
    for source, uri in replacements.items():
        css = css.replace(f'url("{source}")', f'url("{uri}")')
    return css


HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Salareen homepage concepts — review pack</title>
<style>
html,body{margin:0;background:#f4f0e8}
body{font-family:Arial,sans-serif}
button,a{font-family:inherit}
.reviewNote{margin:0;padding:10px 4vw;background:#171519;color:#f8f5ee;font-size:12px;letter-spacing:.04em}
__CSS__
</style>
</head>
<body>
<p class="reviewNote">Salareen homepage review pack. Open any concept, scroll the full page, then vote. This file works offline.</p>
<div data-view="gallery"></div>
<script id="views" type="application/json">__VIEWS__</script>
<script id="clips" type="application/json">__CLIPS__</script>
<script>
const names = {"aurora-story":"Aurora Story","learning-worlds":"Learning Worlds","signal-studio":"Signal Studio","human-journal":"Human Journal"};
const key = "salareen-home-concept-vote";
const views = JSON.parse(document.getElementById("views").textContent);
const clipData = JSON.parse(document.getElementById("clips").textContent);
const clipUrls = {};
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const root = document.querySelector("[data-view]");
function clipUrl(id) {
  if (!clipUrls[id] && clipData[id]) {
    const bytes = Uint8Array.from(atob(clipData[id]), (c) => c.charCodeAt(0));
    clipUrls[id] = URL.createObjectURL(new Blob([bytes], { type: "video/mp4" }));
  }
  return clipUrls[id];
}
const clipObserver = new IntersectionObserver((entries) => {
  entries.forEach(({ target, isIntersecting }) => {
    const visible = isIntersecting && !target.closest("[hidden]");
    if (visible && !reduceMotion.matches) {
      if (!target.src) target.src = clipUrl(target.dataset.clip);
      target.play().catch(() => {});
    } else {
      target.pause();
    }
  });
}, { threshold: 0.25 });
function wireClips() {
  clipObserver.disconnect();
  document.querySelectorAll("video[data-clip]").forEach((video) => clipObserver.observe(video));
}
function vote() { return localStorage.getItem(key); }
function paintVotes() {
  const current = vote();
  document.querySelectorAll("[data-vote]").forEach((button) => {
    const selected = button.dataset.vote === current;
    button.setAttribute("aria-pressed", String(selected));
    button.classList.toggle("voteSelected", selected);
    button.innerHTML = `<span aria-hidden>${selected ? "●" : "○"}</span> ${selected ? "Your favorite" : "Vote for this"}`;
  });
  const label = document.querySelector("[data-favorite]");
  if (label) label.textContent = names[current] || "Not selected";
}
function show(id) {
  root.innerHTML = views[id] || views.gallery;
  root.dataset.view = views[id] ? id : "gallery";
  paintVotes();
  wireClips();
  window.scrollTo(0, 0);
}
document.body.addEventListener("click", async (event) => {
  const voteButton = event.target.closest("[data-vote]");
  if (voteButton) {
    const next = vote() === voteButton.dataset.vote ? "" : voteButton.dataset.vote;
    if (next) localStorage.setItem(key, next); else localStorage.removeItem(key);
    paintVotes();
    return;
  }
  const path = event.target.closest("[data-path]");
  if (path) {
    const copy = {explore:["Curiosity trail","Ocean life → ecosystems → climate","3 quests ready"],make:["Creator trail","Geometry → design → 3D worlds","2 projects ready"],connect:["Community trail","Spanish → food → conversation","Live room open"]}[path.dataset.path];
    document.querySelectorAll("[data-path]").forEach((item) => item.setAttribute("aria-pressed", String(item === path)));
    document.querySelector("[data-path-card]").innerHTML = `<span>${copy[0]}</span><strong>${copy[1]}</strong><small>${copy[2]} · Begin →</small>`;
    return;
  }
  const channel = event.target.closest("[data-channel]");
  if (channel) {
    const copy = {vision:["VISION / 01","Your camera becomes a learning surface.","Explore objects, gestures, experiments, and real-world problems.","https://salareen.com/vision"],voice:["VOICE / 02","Conversation without the interface.","Ask, interrupt, translate, and keep learning while life keeps moving.","https://salareen.com/languages"],play:["PLAY / 03","Mastery disguised as momentum.","Adaptive challenges react to skill, speed, strategy, and curiosity.","https://salareen.com/arcade"]}[channel.dataset.channel];
    document.querySelectorAll("[data-channel]").forEach((item) => item.setAttribute("aria-selected", String(item === channel)));
    document.querySelector("[data-channel-copy]").innerHTML = `<small>${copy[0]}</small><h2>${copy[1]}</h2><p>${copy[2]}</p><a href="${copy[3]}">Launch module ↗</a>`;
    document.querySelectorAll(".scanner [data-clip-box]").forEach((box) => {
      const active = box.dataset.clipBox === `signal-${channel.dataset.channel}`;
      box.hidden = !active;
      const video = box.querySelector("video");
      if (active && !reduceMotion.matches) {
        if (!video.src) video.src = clipUrl(video.dataset.clip);
        video.play().catch(() => {});
      } else {
        video.pause();
      }
    });
    return;
  }
  const belief = event.target.closest("[data-belief]");
  if (belief) {
    document.querySelectorAll("[data-belief]").forEach((item) => {
      const open = item === belief;
      item.setAttribute("aria-expanded", String(open));
      item.querySelector("i").textContent = open ? "−" : "+";
      item.nextElementSibling.hidden = !open;
    });
    return;
  }
  const copy = event.target.closest("[data-copy-vote]");
  if (copy) {
    const favorite = names[vote()] || "no favorite selected yet";
    const text = `Salareen homepage vote: ${favorite}. Feedback: `;
    try { await navigator.clipboard.writeText(text); copy.textContent = "Copied"; }
    catch { window.prompt("Copy this feedback prompt:", text); }
    setTimeout(() => { copy.textContent = "Copy feedback prompt"; }, 1600);
  }
});
window.addEventListener("hashchange", () => show(location.hash.slice(1) || "gallery"));
show(location.hash.slice(1) || "gallery");
</script>
</body>
</html>
"""


CLIPS_DIR = PUBLIC / "landing-concepts/clips"


def _clip(clip_id: str, label: str, caption: str, extra: str, hidden: bool = False) -> str:
    hide = " hidden" if hidden else ""
    return (
        f'<figure class="clip {extra}" data-clip-box="{clip_id}"{hide}>'
        f'<video data-clip="{clip_id}" poster="__POSTER_{clip_id}__" muted loop playsinline preload="none" aria-label="{label}: {caption}"></video>'
        f'<figcaption><span class="clipLive"><i aria-hidden="true"></i>{label}</span><span>{caption}</span></figcaption></figure>'
    )


def _vote(slug: str) -> str:
    return f'<button class="voteButton voteCompact" type="button" data-vote="{slug}" aria-pressed="false"><span aria-hidden>○</span> Vote for this</button>'


def _nav(number: str, slug: str, dark: bool = False) -> str:
    tone = " conceptNavDark" if dark else ""
    light = " brandLight" if dark else ""
    return f'''<nav class="conceptNav{tone}" aria-label="Concept navigation"><a class="brand{light}" href="#gallery"><img src="__LOGO__" alt="" width="38" height="38"><span>Salareen</span></a><div class="navCenter"><a href="#experience">Experience</a><a href="#how">How it works</a><a href="#voices">Stories</a></div><div class="navActions"><span>{number} / 04</span>{_vote(slug)}</div></nav>'''


def _rail(active: str) -> str:
    links = ['<a href="#gallery" aria-label="Back to all concepts">×</a>']
    for number, slug in (("01", "aurora-story"), ("02", "learning-worlds"), ("03", "signal-studio"), ("04", "human-journal")):
        current = ' class="reviewActive" aria-current="page"' if slug == active else ""
        links.append(f'<a href="#{slug}"{current} aria-label="Open concept {number}">{number}</a>')
    return f'<aside class="reviewRail" aria-label="Switch homepage concept">{"".join(links)}</aside>'


def _final(slug: str, title: str, dark: bool = False) -> str:
    tone = " finalCtaDark" if dark else ""
    return f'''<section class="finalCta{tone}"><img src="__BAYON__" alt=""><p>A lifetime of learning can start small.</p><h2>{title}</h2><div><a href="https://salareen.com/demo">Start free class</a>{_vote(slug)}</div><a href="#gallery">← Compare all four concepts</a></section>'''


def _views() -> dict[str, str]:
    cards = [
        ("01", "aurora-story", "aurorastory", "Cinematic product narrative", "Aurora Story", "An iridescent scroll journey that moves from personal guidance to shared live learning.", "Luminous · premium · calm"),
        ("02", "learning-worlds", "learningworlds", "Playful explorable campus", "Learning Worlds", "A spatial, widget-rich learning world where every path feels alive and personalized.", "Playful · tactile · optimistic"),
        ("03", "signal-studio", "signalstudio", "Kinetic technology showcase", "Signal Studio", "A dark, high-energy product lab built around vision, voice, games, and live signals.", "Electric · precise · future-facing"),
        ("04", "human-journal", "humanjournal", "Editorial learning manifesto", "Human Journal", "A warm, story-led homepage where AI supports teachers, families, and lifelong learners.", "Human · thoughtful · credible"),
    ]
    card_html = []
    for number, slug, style, label, name, summary, mood in cards:
        card_html.append(f'''<article class="conceptCard {style}"><a class="cardVisual" href="#{slug}" aria-label="Explore {name}"><span class="cardNumber">{number}</span><div class="cardOrb"></div><span class="cardExplore">Explore concept ↗</span></a><div class="cardBody"><p>{label}</p><h2>{name}</h2><p>{summary}</p><span>{mood}</span>{_vote(slug)}</div></article>''')
    gallery = f'''<main class="gallery"><header class="galleryHeader"><a class="brand" href="#gallery"><img src="__LOGO__" alt="" width="38" height="38"><span>Salareen</span></a><span>Homepage concept review · October 2026</span></header><section class="galleryIntro"><p class="eyebrow">Four futures for Salareen</p><h1>Choose the feeling<br>before the finish.</h1><p>Each direction is a complete, responsive homepage study with its own flow, interactions, and point of view. Open them, scroll them, then vote.</p></section><section class="conceptGrid" aria-label="Homepage concepts">{"".join(card_html)}</section><section class="voteSummary" aria-live="polite"><div><span>Your current vote</span><strong data-favorite>Not selected</strong></div><button type="button" data-copy-vote>Copy feedback prompt</button></section></main>'''
    waves = "".join("<i></i>" for _ in range(18))
    aurora = f'''<main class="experience aurora">{_nav("01","aurora-story")}{_rail("aurora-story")}<section class="auroraHero"><div class="auroraCopy"><p class="eyebrow">Learning, composed around one person</p><h1>Every mind<br>has its own <em>light.</em></h1><p>Salareen brings an adaptive AI tutor, immersive practice, and human-led classes into one continuous learning journey.</p><div class="heroActions"><a href="https://salareen.com/demo">Start free class</a><a href="#experience">See the journey ↓</a></div></div><div class="auroraStage" aria-hidden="true"><div class="auroraHalo"></div><img src="__BAYON__" alt=""><span>Adapts in real time</span></div><div class="scrollCue">Scroll to begin <i></i></div></section><section class="auroraStatement" id="experience"><span>01 · Personal</span><h2>Not one lesson<br>for everyone.</h2><p>A tutor that notices the pause before an answer, remembers yesterday’s breakthrough, and changes course without making a learner feel behind.</p><div class="lessonGlass">{_clip("aurora-student","1:1 lesson","Maya, 15 · Astronomy","clipInset")}<div><small>Today’s learning rhythm</small><strong>Curious & focused</strong></div><div class="rhythm"><i></i><i></i><i></i><i></i><i></i></div><p>“Let’s try the solar system as a story you can walk through.”</p></div></section><section class="auroraCinema" id="how"><div><span>02 · Immersive</span><h2>Knowledge becomes<br>a place you can enter.</h2><p>Play, build, speak, explore. Salareen moves fluidly between explanation and experience.</p></div><div class="cinemaCard">{_clip("aurora-avatar","Sala · AI teacher","Explaining orbits","clipCard")}<strong>Orbital Lab</strong><span>Drag to change gravity</span></div><div class="cinemaCard"><div class="waveform">{waves}</div><strong>Language Studio</strong><span>Pronunciation is listening…</span></div></section><section class="auroraHuman" id="voices"><p>03 · Together</p><blockquote>“Technology should make a great teacher feel closer, not farther away.”</blockquote>{_clip("aurora-group","Live class · 6 learners","How cities breathe","clipWide")}<div class="liveClass"><div class="teacherPortrait"><span>Live</span></div><div><small>Wednesday · 4:00 PM</small><h3>How cities breathe</h3><p>with Maya Chen + 8 learners</p></div><a href="https://salareen.com/group-classes">Reserve a seat</a></div></section>{_final("aurora-story","Find your way in.",True)}</main>'''
    worlds = f'''<main class="experience worlds">{_nav("02","learning-worlds")}{_rail("learning-worlds")}<section class="worldsHero"><div class="worldsCopy"><p class="eyebrow">Your learning world is ready</p><h1>Where do you<br>want to go <em>today?</em></h1><p>Pick a spark. Salareen turns it into a path made of teachers, games, projects, and surprising connections.</p><div class="pathTabs" role="group" aria-label="Choose a learning path"><button type="button" data-path="explore" aria-pressed="true">explore</button><button type="button" data-path="make" aria-pressed="false">make</button><button type="button" data-path="connect" aria-pressed="false">connect</button></div><div class="pathCard" data-path-card aria-live="polite"><span>Curiosity trail</span><strong>Ocean life → ecosystems → climate</strong><small>3 quests ready · Begin →</small></div></div><div class="worldMap" aria-label="Illustrated learning world"><div class="worldNode nodeScience"><b>⚗</b><span>Science garden</span></div><div class="worldNode nodeGames"><b>◇</b><span>Play arcade</span></div><div class="worldNode nodeLive"><b>◉</b><span>Live studio</span></div><div class="mapPath"></div><img src="__BAYON__" alt="Salareen Bayon Buddy"></div></section><section class="widgetBoard" id="experience"><div class="widgetIntro"><span>Made for momentum</span><h2>Your day,<br>beautifully in motion.</h2></div><article class="streakWidget"><span>7 day spark</span><strong>Keep it glowing</strong><div><i>1</i><i>2</i><i>3</i><i>4</i><i>5</i><i>6</i><i>7</i></div></article><article class="tutorWidget">{_clip("worlds-avatar","Sala · tutor","Fractions you can move","clipWidget")}<small>Your tutor noticed</small><p>You learn fractions faster when you can move the pieces.</p><button type="button">Try a visual lesson</button></article><article class="liveWidget">{_clip("worlds-group","Live now","Weather station build","clipWidget")}<span>Live now</span><div class="faces"><i>A</i><i>M</i><i>K</i><i>+5</i></div><strong>Build a tiny weather station</strong><a href="https://salareen.com/group-classes">Join room →</a></article><article class="questWidget">{_clip("worlds-play","Vision Play","Spot it, name it","clipWidget")}<small>Next quest</small><strong>Can coral reefs talk?</strong><span>12 min · Biology · Story</span><button type="button">Start</button></article></section><section class="worldsFlow" id="how"><div><span>1</span><h3>Tell us what lights you up.</h3><p>A subject, a goal, or simply a question.</p></div><div><span>2</span><h3>Meet your adaptive guide.</h3><p>One tutor remembers how you think and grow.</p></div><div><span>3</span><h3>Learn across worlds.</h3><p>Move between games, projects, voice, and live teachers.</p></div></section><section class="worldVoices" id="voices"><p>“I came for geometry and somehow built a skate park.”</p><span>Amir, 13 · Learning path: Make</span><p>“For the first time, homework starts with ‘want to see something cool?’”</p><span>Jules, parent</span></section>{_final("learning-worlds","Choose your first world.")}</main>'''
    signal = f'''<main class="experience signal">{_nav("03","signal-studio",True)}{_rail("signal-studio")}<section class="signalHero"><div class="signalStatus"><i></i> SALAREEN SYSTEM ONLINE <span>PERSONAL SIGNAL 98%</span></div><h1>LEARNING<br><em>RESPONDS.</em></h1><p>One adaptive intelligence across vision, voice, play, and live instruction.</p><div class="signalActions"><a href="https://salareen.com/demo">ENTER THE LAB ↗</a><a href="#experience">EXPLORE SIGNALS ↓</a></div><div class="signalSphere" aria-hidden="true"><i></i><i></i><i></i></div><div class="ticker"><span>VISION PLAY</span><span>LIVE AUDIO</span><span>ADAPTIVE GAMES</span><span>HUMAN CLASSES</span><span>27 LANGUAGES</span></div></section><section class="channelSection" id="experience"><div class="channelTabs" role="tablist" aria-label="Product channels"><button role="tab" data-channel="vision" aria-selected="true">01<span>vision</span></button><button role="tab" data-channel="voice" aria-selected="false">02<span>voice</span></button><button role="tab" data-channel="play" aria-selected="false">03<span>play</span></button></div><div class="channelDemo"><div class="scanner">{_clip("signal-vision","VISION / LIVE","Reading handwritten math","clipFill")}{_clip("signal-voice","VOICE / LIVE","Spanish conversation practice","clipFill",True)}{_clip("signal-play","PLAY / LIVE","Adaptive geometry challenge","clipFill",True)}<i></i><i></i><i></i><i></i></div><div data-channel-copy aria-live="polite"><small>VISION / 01</small><h2>Your camera becomes a learning surface.</h2><p>Explore objects, gestures, experiments, and real-world problems.</p><a href="https://salareen.com/vision">Launch module ↗</a></div></div></section><section class="metrics" id="how"><div><strong>01</strong><span>learner</span><p>A unique model of pace, interests, strengths, and goals.</p></div><div><strong>27</strong><span>languages</span><p>Natural learning support that travels across cultures.</p></div><div><strong>∞</strong><span>paths</span><p>No fixed track. Every interaction can open a better route.</p></div><div><strong>LIVE</strong><span>human signal</span><p>Real educators remain present where connection matters most.</p></div></section><section class="signalQuote" id="voices"><span>LEARNER SIGNAL / 8472</span><blockquote>“It doesn’t wait for me to fail before it changes the lesson.”</blockquote><p>Nia · systems engineering learner</p></section>{_final("signal-studio","TUNE INTO YOUR NEXT IDEA.",True)}</main>'''
    beliefs = [
        ("AI should make learning more personal, not less human.", "Salareen handles repetition, adaptation, and recall so teachers can spend more time on judgment, encouragement, and connection.", False),
        ("A learner is more than a score.", "Interests, confidence, language, pace, and context all shape the right next step. The system pays attention to the whole story.", True),
        ("Play is serious learning.", "Simulation and games create room to experiment, fail safely, and discover why an idea matters before memorizing its name.", True),
    ]
    belief_html = []
    for index, (title, body, hidden) in enumerate(beliefs):
        state = "false" if hidden else "true"
        mark = "+" if hidden else "−"
        hide = " hidden" if hidden else ""
        belief_html.append(f'<article><button type="button" data-belief aria-expanded="{state}"><span>0{index + 1}</span><strong>{title}</strong><i>{mark}</i></button><p{hide}>{body}</p></article>')
    journal = f'''<main class="experience journal">{_nav("04","human-journal")}{_rail("human-journal")}<section class="journalHero"><p class="issue">The learning issue · No. 01</p><h1>We built an AI tutor.<br><em>Then we taught it to care.</em></h1><div class="journalLead"><p>Salareen is a learning platform designed around a simple belief: technology works best when it helps people feel seen.</p><a href="https://salareen.com/demo">Experience a free class →</a></div><div class="journalImage">{_clip("journal-student","Evening study","Marcus · on his own schedule","clipFill")}</div></section><section class="editorialGrid" id="experience"><aside><span>In this story</span><a href="#beliefs">01 · What we believe</a><a href="#teacher">02 · Teacher, amplified</a><a href="#voices">03 · Learner notes</a></aside><div class="dropcap"><p><b>L</b>earning is intimate. It asks us to admit what we do not know, to try in public, and to trust that effort will become understanding. That is why Salareen begins with the learner—not the syllabus.</p><blockquote>One tutor per student.<br>A whole world behind them.</blockquote></div></section><section class="beliefs" id="beliefs"><p class="sectionLabel">What we believe</p>{"".join(belief_html)}</section><section class="teacherStory" id="teacher">{_clip("journal-group","Maya Chen · live science","Sala flags who needs help","clipEditorial")}<div><p class="sectionLabel">Teacher, amplified</p><h2>“I can finally see who needs me before they raise a hand.”</h2><p>During every live class, Salareen quietly tracks questions, misconceptions, and moments of momentum. Maya sees the room more clearly. Learners get more of Maya.</p><a href="https://salareen.com/group-classes">Step inside a live class →</a></div></section><section class="learnerNotes" id="voices"><div><p class="sectionLabel">Notes from learners</p>{_clip("journal-avatar","Sala · AI teacher","Patient, every time","clipEditorial")}</div><div><blockquote>“It remembered the space project I abandoned last summer—and helped me finish it.”</blockquote><span>Leila · 16</span></div><div><blockquote>“I learn on my commute. It feels like calling the smartest, most patient friend I know.”</blockquote><span>Marcus · 38</span></div></section>{_final("human-journal","Begin with one question.")}</main>'''
    return {"gallery": gallery, "aurora-story": aurora, "learning-worlds": worlds, "signal-studio": signal, "human-journal": journal}


def main() -> int:
    import json
    logo = _uri(PUBLIC / "logo-mark.webp", "image/webp")
    bayon = _uri(PUBLIC / "bayon-mark.webp", "image/webp")
    payload = json.dumps(_views()).replace("__LOGO__", logo).replace("__BAYON__", bayon)
    clips = {}
    for video in sorted(CLIPS_DIR.glob("*.mp4")):
        clips[video.stem] = base64.b64encode(video.read_bytes()).decode()
        payload = payload.replace(f"__POSTER_{video.stem}__", _uri(video.with_suffix(".webp"), "image/webp"))
    html = (
        HTML.replace("__CSS__", _css())
        .replace("__CLIPS__", json.dumps(clips))
        .replace("__VIEWS__", payload.replace("</", "<\\/"))
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html_path = OUT_DIR / HTML_NAME
    zip_path = OUT_DIR / "salareen-home-concepts-review.zip"
    html_path.write_text(html)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(html_path, HTML_NAME)
    print(f"html {html_path} ({html_path.stat().st_size} bytes)")
    print(f"zip  {zip_path} ({zip_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
