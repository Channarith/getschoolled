"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import styles from "./homeConcepts.module.css";

export const conceptSlugs = [
  "aurora-story",
  "learning-worlds",
  "signal-studio",
  "human-journal",
] as const;

export type ConceptSlug = (typeof conceptSlugs)[number];

type Concept = {
  slug: ConceptSlug;
  number: string;
  name: string;
  label: string;
  summary: string;
  mood: string;
};

const concepts: Concept[] = [
  {
    slug: "aurora-story",
    number: "01",
    name: "Aurora Story",
    label: "Cinematic product narrative",
    summary: "An iridescent scroll journey that moves from personal guidance to shared live learning.",
    mood: "Luminous · premium · calm",
  },
  {
    slug: "learning-worlds",
    number: "02",
    name: "Learning Worlds",
    label: "Playful explorable campus",
    summary: "A spatial, widget-rich learning world where every path feels alive and personalized.",
    mood: "Playful · tactile · optimistic",
  },
  {
    slug: "signal-studio",
    number: "03",
    name: "Signal Studio",
    label: "Kinetic technology showcase",
    summary: "A dark, high-energy product lab built around vision, voice, games, and live signals.",
    mood: "Electric · precise · future-facing",
  },
  {
    slug: "human-journal",
    number: "04",
    name: "Human Journal",
    label: "Editorial learning manifesto",
    summary: "A warm, story-led homepage where AI supports teachers, families, and lifelong learners.",
    mood: "Human · thoughtful · credible",
  },
];

const storageKey = "salareen-home-concept-vote";

function Brand({ light = false }: { light?: boolean }) {
  return (
    <Link className={`${styles.brand} ${light ? styles.brandLight : ""}`} href="/home-concepts">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/logo-mark.webp" alt="" width={38} height={38} />
      <span>Salareen</span>
    </Link>
  );
}

function VoteButton({ slug, compact = false }: { slug: ConceptSlug; compact?: boolean }) {
  const [vote, setVote] = useState<ConceptSlug | null>(null);
  useEffect(() => {
    const current = window.localStorage.getItem(storageKey);
    if (conceptSlugs.includes(current as ConceptSlug)) setVote(current as ConceptSlug);
  }, []);
  const selected = vote === slug;
  return (
    <button
      className={`${styles.voteButton} ${compact ? styles.voteCompact : ""} ${selected ? styles.voteSelected : ""}`}
      type="button"
      aria-pressed={selected}
      onClick={() => {
        const next = selected ? null : slug;
        if (next) window.localStorage.setItem(storageKey, next);
        else window.localStorage.removeItem(storageKey);
        setVote(next);
        window.dispatchEvent(new Event("salareen-concept-vote"));
      }}
    >
      <span aria-hidden>{selected ? "●" : "○"}</span>
      {selected ? "Your favorite" : "Vote for this"}
    </button>
  );
}

function ConceptNav({ concept, dark = false }: { concept: Concept; dark?: boolean }) {
  return (
    <nav className={`${styles.conceptNav} ${dark ? styles.conceptNavDark : ""}`} aria-label="Concept navigation">
      <Brand light={dark} />
      <div className={styles.navCenter}>
        <a href="#experience">Experience</a>
        <a href="#how">How it works</a>
        <a href="#voices">Stories</a>
      </div>
      <div className={styles.navActions}>
        <span>{concept.number} / 04</span>
        <VoteButton slug={concept.slug} compact />
      </div>
    </nav>
  );
}

function ReviewRail({ active }: { active: ConceptSlug }) {
  return (
    <aside className={styles.reviewRail} aria-label="Switch homepage concept">
      <Link href="/home-concepts" aria-label="Back to all concepts">×</Link>
      {concepts.map((concept) => (
        <Link
          key={concept.slug}
          href={`/home-concepts/${concept.slug}`}
          className={concept.slug === active ? styles.reviewActive : ""}
          aria-label={`Open ${concept.name}`}
          aria-current={concept.slug === active ? "page" : undefined}
        >
          {concept.number}
        </Link>
      ))}
    </aside>
  );
}

export function ConceptGallery() {
  const [vote, setVote] = useState<ConceptSlug | null>(null);
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    const sync = () => {
      const current = window.localStorage.getItem(storageKey);
      setVote(conceptSlugs.includes(current as ConceptSlug) ? current as ConceptSlug : null);
    };
    sync();
    window.addEventListener("storage", sync);
    window.addEventListener("salareen-concept-vote", sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener("salareen-concept-vote", sync);
    };
  }, []);
  const favorite = concepts.find((concept) => concept.slug === vote);
  const summary = favorite
    ? `Salareen homepage vote: ${favorite.name} (${favorite.label}). Feedback: `
    : "Salareen homepage vote: no favorite selected yet. Feedback: ";
  return (
    <main className={styles.gallery}>
      <header className={styles.galleryHeader}>
        <Brand />
        <span>Homepage concept review · October 2026</span>
      </header>
      <section className={styles.galleryIntro}>
        <p className={styles.eyebrow}>Four futures for Salareen</p>
        <h1>Choose the feeling<br />before the finish.</h1>
        <p>Each direction is a complete, responsive homepage study with its own flow, interactions, and point of view. Open them, scroll them, then vote.</p>
      </section>
      <section className={styles.conceptGrid} aria-label="Homepage concepts">
        {concepts.map((concept) => (
          <article className={`${styles.conceptCard} ${styles[concept.slug.replace("-", "")]}`} key={concept.slug}>
            <Link className={styles.cardVisual} href={`/home-concepts/${concept.slug}`} aria-label={`Explore ${concept.name}`}>
              <span className={styles.cardNumber}>{concept.number}</span>
              <div className={styles.cardOrb} />
              <span className={styles.cardExplore}>Explore concept ↗</span>
            </Link>
            <div className={styles.cardBody}>
              <p>{concept.label}</p>
              <h2>{concept.name}</h2>
              <p>{concept.summary}</p>
              <span>{concept.mood}</span>
              <VoteButton slug={concept.slug} compact />
            </div>
          </article>
        ))}
      </section>
      <section className={styles.voteSummary} aria-live="polite">
        <div>
          <span>Your current vote</span>
          <strong>{favorite?.name ?? "Not selected"}</strong>
        </div>
        <button
          type="button"
          onClick={async () => {
            await navigator.clipboard.writeText(summary);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1600);
          }}
        >
          {copied ? "Copied" : "Copy feedback prompt"}
        </button>
      </section>
    </main>
  );
}

function AuroraStory({ concept }: { concept: Concept }) {
  return (
    <main className={`${styles.experience} ${styles.aurora}`}>
      <ConceptNav concept={concept} />
      <ReviewRail active={concept.slug} />
      <section className={styles.auroraHero}>
        <div className={styles.auroraCopy}>
          <p className={styles.eyebrow}>Learning, composed around one person</p>
          <h1>Every mind<br />has its own <em>light.</em></h1>
          <p>Salareen brings an adaptive AI tutor, immersive practice, and human-led classes into one continuous learning journey.</p>
          <div className={styles.heroActions}>
            <Link href="/demo">Start free class</Link>
            <a href="#experience">See the journey ↓</a>
          </div>
        </div>
        <div className={styles.auroraStage} aria-hidden>
          <div className={styles.auroraHalo} />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/bayon-mark.webp" alt="" />
          <span>Adapts in real time</span>
        </div>
        <div className={styles.scrollCue}>Scroll to begin <i /></div>
      </section>
      <section className={styles.auroraStatement} id="experience">
        <span>01 · Personal</span>
        <h2>Not one lesson<br />for everyone.</h2>
        <p>A tutor that notices the pause before an answer, remembers yesterday&apos;s breakthrough, and changes course without making a learner feel behind.</p>
        <div className={styles.lessonGlass}>
          <div><small>Today&apos;s learning rhythm</small><strong>Curious & focused</strong></div>
          <div className={styles.rhythm}><i /><i /><i /><i /><i /></div>
          <p>“Let&apos;s try the solar system as a story you can walk through.”</p>
        </div>
      </section>
      <section className={styles.auroraCinema} id="how">
        <div>
          <span>02 · Immersive</span>
          <h2>Knowledge becomes<br />a place you can enter.</h2>
          <p>Play, build, speak, explore. Salareen moves fluidly between explanation and experience.</p>
        </div>
        <div className={styles.cinemaCard}>
          <div className={styles.planet} />
          <strong>Orbital Lab</strong>
          <span>Drag to change gravity</span>
        </div>
        <div className={styles.cinemaCard}>
          <div className={styles.waveform}>{Array.from({ length: 18 }, (_, index) => <i key={index} />)}</div>
          <strong>Language Studio</strong>
          <span>Pronunciation is listening…</span>
        </div>
      </section>
      <section className={styles.auroraHuman} id="voices">
        <p>03 · Together</p>
        <blockquote>“Technology should make a great teacher feel closer, not farther away.”</blockquote>
        <div className={styles.liveClass}>
          <div className={styles.teacherPortrait}><span>Live</span></div>
          <div><small>Wednesday · 4:00 PM</small><h3>How cities breathe</h3><p>with Maya Chen + 8 learners</p></div>
          <Link href="/group-classes">Reserve a seat</Link>
        </div>
      </section>
      <FinalCta slug={concept.slug} title="Find your way in." dark />
    </main>
  );
}

function LearningWorlds({ concept }: { concept: Concept }) {
  const [path, setPath] = useState<"explore" | "make" | "connect">("explore");
  const copy = {
    explore: ["Curiosity trail", "Ocean life → ecosystems → climate", "3 quests ready"],
    make: ["Creator trail", "Geometry → design → 3D worlds", "2 projects ready"],
    connect: ["Community trail", "Spanish → food → conversation", "Live room open"],
  }[path];
  return (
    <main className={`${styles.experience} ${styles.worlds}`}>
      <ConceptNav concept={concept} />
      <ReviewRail active={concept.slug} />
      <section className={styles.worldsHero}>
        <div className={styles.worldsCopy}>
          <p className={styles.eyebrow}>Your learning world is ready</p>
          <h1>Where do you<br />want to go <em>today?</em></h1>
          <p>Pick a spark. Salareen turns it into a path made of teachers, games, projects, and surprising connections.</p>
          <div className={styles.pathTabs} role="group" aria-label="Choose a learning path">
            {(["explore", "make", "connect"] as const).map((item) => (
              <button key={item} type="button" aria-pressed={path === item} onClick={() => setPath(item)}>{item}</button>
            ))}
          </div>
          <div className={styles.pathCard} aria-live="polite">
            <span>{copy[0]}</span><strong>{copy[1]}</strong><small>{copy[2]} · Begin →</small>
          </div>
        </div>
        <div className={styles.worldMap} aria-label="Illustrated learning world">
          <div className={`${styles.worldNode} ${styles.nodeScience}`}><b>⚗</b><span>Science garden</span></div>
          <div className={`${styles.worldNode} ${styles.nodeGames}`}><b>◇</b><span>Play arcade</span></div>
          <div className={`${styles.worldNode} ${styles.nodeLive}`}><b>◉</b><span>Live studio</span></div>
          <div className={styles.mapPath} />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/bayon-mark.webp" alt="Salareen Bayon Buddy" />
        </div>
      </section>
      <section className={styles.widgetBoard} id="experience">
        <div className={styles.widgetIntro}><span>Made for momentum</span><h2>Your day,<br />beautifully in motion.</h2></div>
        <article className={styles.streakWidget}><span>7 day spark</span><strong>Keep it glowing</strong><div>{[1,2,3,4,5,6,7].map((n) => <i key={n}>{n}</i>)}</div></article>
        <article className={styles.tutorWidget}><small>Your tutor noticed</small><p>You learn fractions faster when you can move the pieces.</p><button type="button">Try a visual lesson</button></article>
        <article className={styles.liveWidget}><span>Live now</span><div className={styles.faces}><i>A</i><i>M</i><i>K</i><i>+5</i></div><strong>Build a tiny weather station</strong><Link href="/group-classes">Join room →</Link></article>
        <article className={styles.questWidget}><small>Next quest</small><strong>Can coral reefs talk?</strong><span>12 min · Biology · Story</span><button type="button">Start</button></article>
      </section>
      <section className={styles.worldsFlow} id="how">
        <div><span>1</span><h3>Tell us what lights you up.</h3><p>A subject, a goal, or simply a question.</p></div>
        <div><span>2</span><h3>Meet your adaptive guide.</h3><p>One tutor remembers how you think and grow.</p></div>
        <div><span>3</span><h3>Learn across worlds.</h3><p>Move between games, projects, voice, and live teachers.</p></div>
      </section>
      <section className={styles.worldVoices} id="voices">
        <p>“I came for geometry and somehow built a skate park.”</p>
        <span>Amir, 13 · Learning path: Make</span>
        <p>“For the first time, homework starts with ‘want to see something cool?’”</p>
        <span>Jules, parent</span>
      </section>
      <FinalCta slug={concept.slug} title="Choose your first world." />
    </main>
  );
}

function SignalStudio({ concept }: { concept: Concept }) {
  const [channel, setChannel] = useState<"vision" | "voice" | "play">("vision");
  const channelCopy = {
    vision: ["VISION / 01", "Your camera becomes a learning surface.", "Explore objects, gestures, experiments, and real-world problems."],
    voice: ["VOICE / 02", "Conversation without the interface.", "Ask, interrupt, translate, and keep learning while life keeps moving."],
    play: ["PLAY / 03", "Mastery disguised as momentum.", "Adaptive challenges react to skill, speed, strategy, and curiosity."],
  }[channel];
  return (
    <main className={`${styles.experience} ${styles.signal}`}>
      <ConceptNav concept={concept} dark />
      <ReviewRail active={concept.slug} />
      <section className={styles.signalHero}>
        <div className={styles.signalStatus}><i /> SALAREEN SYSTEM ONLINE <span>PERSONAL SIGNAL 98%</span></div>
        <h1>LEARNING<br /><em>RESPONDS.</em></h1>
        <p>One adaptive intelligence across vision, voice, play, and live instruction.</p>
        <div className={styles.signalActions}><Link href="/demo">ENTER THE LAB ↗</Link><a href="#experience">EXPLORE SIGNALS ↓</a></div>
        <div className={styles.signalSphere} aria-hidden><i /><i /><i /></div>
        <div className={styles.ticker}><span>VISION PLAY</span><span>LIVE AUDIO</span><span>ADAPTIVE GAMES</span><span>HUMAN CLASSES</span><span>27 LANGUAGES</span></div>
      </section>
      <section className={styles.channelSection} id="experience">
        <div className={styles.channelTabs} role="tablist" aria-label="Product channels">
          {(["vision", "voice", "play"] as const).map((item, index) => (
            <button role="tab" aria-selected={channel === item} key={item} onClick={() => setChannel(item)}>
              0{index + 1}<span>{item}</span>
            </button>
          ))}
        </div>
        <div className={styles.channelDemo}>
          <div className={styles.scanner}>
            <i /><i /><i /><i />
            <span>{channel.toUpperCase()} SIGNAL</span>
          </div>
          <div aria-live="polite"><small>{channelCopy[0]}</small><h2>{channelCopy[1]}</h2><p>{channelCopy[2]}</p><Link href={channel === "vision" ? "/vision" : channel === "play" ? "/arcade" : "/languages"}>Launch module ↗</Link></div>
        </div>
      </section>
      <section className={styles.metrics} id="how">
        <div><strong>01</strong><span>learner</span><p>A unique model of pace, interests, strengths, and goals.</p></div>
        <div><strong>27</strong><span>languages</span><p>Natural learning support that travels across cultures.</p></div>
        <div><strong>∞</strong><span>paths</span><p>No fixed track. Every interaction can open a better route.</p></div>
        <div><strong>LIVE</strong><span>human signal</span><p>Real educators remain present where connection matters most.</p></div>
      </section>
      <section className={styles.signalQuote} id="voices"><span>LEARNER SIGNAL / 8472</span><blockquote>“It doesn&apos;t wait for me to fail before it changes the lesson.”</blockquote><p>Nia · systems engineering learner</p></section>
      <FinalCta slug={concept.slug} title="TUNE INTO YOUR NEXT IDEA." dark />
    </main>
  );
}

function HumanJournal({ concept }: { concept: Concept }) {
  const [open, setOpen] = useState(0);
  const beliefs = [
    ["AI should make learning more personal, not less human.", "Salareen handles repetition, adaptation, and recall so teachers can spend more time on judgment, encouragement, and connection."],
    ["A learner is more than a score.", "Interests, confidence, language, pace, and context all shape the right next step. The system pays attention to the whole story."],
    ["Play is serious learning.", "Simulation and games create room to experiment, fail safely, and discover why an idea matters before memorizing its name."],
  ];
  return (
    <main className={`${styles.experience} ${styles.journal}`}>
      <ConceptNav concept={concept} />
      <ReviewRail active={concept.slug} />
      <section className={styles.journalHero}>
        <p className={styles.issue}>The learning issue · No. 01</p>
        <h1>We built an AI tutor.<br /><em>Then we taught it to care.</em></h1>
        <div className={styles.journalLead}>
          <p>Salareen is a learning platform designed around a simple belief: technology works best when it helps people feel seen.</p>
          <Link href="/demo">Experience a free class →</Link>
        </div>
        <div className={styles.journalImage}><span>Learning in progress</span></div>
      </section>
      <section className={styles.editorialGrid} id="experience">
        <aside><span>In this story</span><a href="#beliefs">01 · What we believe</a><a href="#teacher">02 · Teacher, amplified</a><a href="#voices">03 · Learner notes</a></aside>
        <div className={styles.dropcap}><p><b>L</b>earning is intimate. It asks us to admit what we do not know, to try in public, and to trust that effort will become understanding. That is why Salareen begins with the learner—not the syllabus.</p><blockquote>One tutor per student.<br />A whole world behind them.</blockquote></div>
      </section>
      <section className={styles.beliefs} id="beliefs">
        <p className={styles.sectionLabel}>What we believe</p>
        {beliefs.map(([title, body], index) => (
          <article key={title}>
            <button type="button" aria-expanded={open === index} onClick={() => setOpen(index)}>
              <span>0{index + 1}</span><strong>{title}</strong><i>{open === index ? "−" : "+"}</i>
            </button>
            {open === index && <p>{body}</p>}
          </article>
        ))}
      </section>
      <section className={styles.teacherStory} id="teacher">
        <div className={styles.teacherImage}><span>Maya Chen<br />Live science educator</span></div>
        <div><p className={styles.sectionLabel}>Teacher, amplified</p><h2>“I can finally see who needs me before they raise a hand.”</h2><p>During every live class, Salareen quietly tracks questions, misconceptions, and moments of momentum. Maya sees the room more clearly. Learners get more of Maya.</p><Link href="/group-classes">Step inside a live class →</Link></div>
      </section>
      <section className={styles.learnerNotes} id="voices">
        <p className={styles.sectionLabel}>Notes from learners</p>
        <div><blockquote>“It remembered the space project I abandoned last summer—and helped me finish it.”</blockquote><span>Leila · 16</span></div>
        <div><blockquote>“I learn on my commute. It feels like calling the smartest, most patient friend I know.”</blockquote><span>Marcus · 38</span></div>
      </section>
      <FinalCta slug={concept.slug} title="Begin with one question." />
    </main>
  );
}

function FinalCta({ slug, title, dark = false }: { slug: ConceptSlug; title: string; dark?: boolean }) {
  return (
    <section className={`${styles.finalCta} ${dark ? styles.finalCtaDark : ""}`}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/bayon-mark.webp" alt="" />
      <p>A lifetime of learning can start small.</p>
      <h2>{title}</h2>
      <div><Link href="/demo">Start free class</Link><VoteButton slug={slug} /></div>
      <Link href="/home-concepts">← Compare all four concepts</Link>
    </section>
  );
}

export function ConceptExperience({ slug }: { slug: ConceptSlug }) {
  const concept = useMemo(() => concepts.find((item) => item.slug === slug) ?? concepts[0], [slug]);
  if (slug === "learning-worlds") return <LearningWorlds concept={concept} />;
  if (slug === "signal-studio") return <SignalStudio concept={concept} />;
  if (slug === "human-journal") return <HumanJournal concept={concept} />;
  return <AuroraStory concept={concept} />;
}
