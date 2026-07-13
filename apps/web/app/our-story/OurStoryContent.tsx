"use client";

// Salareen "Our Story" page. Client component (scroll-reveal animation).
// Self-contained: scoped `.os-` styles + Fraunces/Inter fonts via <link>.
// The site's global nav + footer wrap this page (layout.tsx), so this
// component does NOT render its own nav.
//
// All copy comes from the i18n system (story.* keys in i18n-pages.ts) via
// t(). Copy may use lightweight markers rendered by renderRich():
//   **bold** -> <strong>, *italic* -> <em>, \n -> <br/>.
//
// Image slots are wired to existing public assets:
//   hero background  -> /wallpapers/wisdom_bodhi.webp  (same as the homepage hero)
//   mascot           -> front-page MascotImage component (locale-aware)
//   platform diagram -> on-theme HTML/SVG ecosystem (AI teacher + agent cards)

import { useEffect } from "react";

import MascotImage from "../components/MascotImage";
import { useT } from "../lib/i18n";

const styles = `
.os-root{
  --bg:#faf7f1;--bg-soft:#f3eee3;--card:#ffffff;
  --ink:#211d17;--ink-soft:#5b5447;--ink-faint:#8a8275;
  --gold:#b07d2b;--gold-bright:#c9a35e;
  --plum:#3a2b54;--plum-deep:#241a38;
  --line:rgba(176,125,43,0.22);--line-faint:rgba(33,29,23,0.10);
  --serif:'Fraunces',Georgia,serif;--sans:'Inter',system-ui,sans-serif;
  --maxw:1080px;
  background:var(--bg);color:var(--ink);font-family:var(--sans);line-height:1.7;
}
.os-root *{box-sizing:border-box}

/* HERO — full-width mission statement over the temple/tree photo */
.os-hero{position:relative;color:#fff;padding:120px 32px 92px;overflow:hidden;
  background:linear-gradient(95deg, rgba(36,26,56,.86) 0%, rgba(46,33,74,.55) 50%, rgba(58,43,84,.35) 100%), var(--hero-img);
  background-size:cover;background-position:center}
.os-hero::after{content:"";position:absolute;left:0;right:0;bottom:0;height:80px;background:linear-gradient(to bottom, transparent, var(--bg))}
.os-hero-inner{max-width:var(--maxw);margin:0 auto;position:relative;z-index:2}
.os-eyebrow{font-size:12px;letter-spacing:.32em;text-transform:uppercase;color:var(--gold-bright);margin-bottom:20px;font-weight:500;display:flex;align-items:center;gap:14px}
.os-eyebrow::before{content:"";width:34px;height:1px;background:var(--gold-bright)}
.os-hero h1{font-family:var(--serif);font-weight:500;font-size:clamp(26px,3.2vw,40px);line-height:1.18;letter-spacing:-.2px;max-width:760px;margin:0}
.os-hero h1 em{font-style:italic;color:var(--gold-bright)}
.os-hero h1 strong{color:var(--gold-bright);font-weight:600;font-size:1.18em;letter-spacing:-.5px}

.os-wrap{max-width:var(--maxw);margin:0 auto;padding:0 32px}

.os-opener{padding:54px 0 30px;border-bottom:1px solid var(--line-faint)}
.os-believe-label{font-size:13px;letter-spacing:.28em;text-transform:uppercase;color:var(--gold);font-weight:600;margin-bottom:14px}
.os-believe{font-size:19px;color:var(--ink-soft);line-height:1.6;max-width:780px}
.os-believe strong{color:var(--ink);font-weight:600}

.os-section{padding:56px 0;border-top:1px solid var(--line-faint)}
.os-marker{display:flex;align-items:baseline;gap:16px;margin-bottom:18px}
.os-marker .num{font-family:var(--serif);font-style:italic;font-size:36px;font-weight:500;color:var(--gold-bright);line-height:1}
.os-marker .label{font-size:13px;letter-spacing:.2em;text-transform:uppercase;color:var(--ink-faint);font-weight:600}
.os-root h2{font-family:var(--serif);font-weight:500;font-size:clamp(30px,4vw,44px);line-height:1.08;letter-spacing:-.3px;margin-bottom:20px}
.os-body{font-size:17px;color:var(--ink-soft);margin-bottom:18px;max-width:760px}
.os-body strong{color:var(--ink);font-weight:600}
.os-body em{font-family:var(--serif);font-style:italic;font-size:19px;color:var(--gold)}

.os-pullquote{font-family:var(--serif);font-style:italic;font-weight:500;font-size:clamp(23px,3.2vw,32px);line-height:1.32;color:var(--ink);padding:8px 0 8px 28px;margin:30px 0;border-left:2px solid var(--gold);max-width:720px}

.os-name-grid{display:flex;gap:44px;align-items:center;flex-wrap:wrap}
.os-mascot{flex:0 0 auto;display:flex;align-items:center;justify-content:center}
.os-mascot img{height:210px;width:auto;max-width:100%;filter:drop-shadow(0 12px 22px rgba(33,29,23,.16))}
.os-name-body{flex:1;min-width:300px}

/* ECOSYSTEM — AI teacher (center) + specialized agent cards, on-theme */
.os-eco{margin:26px 0 12px;border-radius:20px;padding:34px clamp(18px,3.5vw,40px) 30px;
  border:1px solid var(--line);position:relative;overflow:hidden;color:#f4efe4;
  background:radial-gradient(130% 100% at 50% -10%, #33254e 0%, #271d3d 46%, #1e1631 100%)}
.os-eco::before{content:"";position:absolute;inset:0;pointer-events:none;
  background:radial-gradient(60% 45% at 50% 42%, rgba(201,163,94,.10), transparent 70%)}
.os-eco-head{text-align:center;position:relative;margin-bottom:26px}
.os-eco-title{font-family:var(--serif);font-weight:500;font-size:clamp(30px,4.2vw,44px);
  letter-spacing:-.5px;color:#fbf6ea;line-height:1}
.os-eco-sub{display:inline-flex;align-items:center;gap:12px;margin-top:12px;
  font-size:12px;letter-spacing:.26em;text-transform:uppercase;color:var(--gold-bright);font-weight:600}
.os-eco-sub::before,.os-eco-sub::after{content:"";width:26px;height:1px;background:var(--gold-bright);opacity:.7}

.os-eco-stage{position:relative;display:grid;grid-template-columns:1fr minmax(240px,340px) 1fr;
  gap:clamp(14px,2vw,26px);align-items:center}
.os-eco-side{display:flex;flex-direction:column;gap:14px}

.os-eco-center{position:relative;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:280px}
.os-eco-glow{position:absolute;top:46%;left:50%;width:118%;height:118%;transform:translate(-50%,-50%);
  border-radius:50%;pointer-events:none;
  background:radial-gradient(closest-side, rgba(201,163,94,.30), rgba(201,163,94,.08) 55%, transparent 72%)}
.os-eco-teacher{position:relative;width:100%;max-width:330px;height:auto;display:block;
  filter:drop-shadow(0 16px 30px rgba(10,6,20,.45))}
.os-eco-center-cap{position:relative;margin-top:6px;font-size:12px;letter-spacing:.22em;
  text-transform:uppercase;color:var(--gold-bright);font-weight:600}

.os-eco-grid{position:relative;display:grid;grid-template-columns:repeat(4,1fr);
  gap:14px;margin-top:22px}

.os-eco-card{display:flex;align-items:center;gap:12px;padding:13px 15px;border-radius:12px;
  background:rgba(255,255,255,.045);border:1px solid rgba(201,163,94,.26);
  transition:transform .2s ease,border-color .2s ease,background .2s ease}
.os-eco-card:hover{transform:translateY(-2px);border-color:var(--gold-bright);background:rgba(201,163,94,.10)}
.os-eco-ic{flex:0 0 auto;width:38px;height:38px;border-radius:9px;display:flex;align-items:center;justify-content:center;
  color:var(--gold-bright);background:rgba(201,163,94,.12);border:1px solid rgba(201,163,94,.28)}
.os-eco-ic svg{width:21px;height:21px;display:block}
.os-eco-lb{font-size:13.5px;font-weight:500;line-height:1.3;color:#f0e9db}

.os-eco-hint{position:relative;text-align:center;margin-top:22px;font-style:italic;
  font-family:var(--serif);font-size:16px;color:rgba(244,239,228,.72)}

.os-principles{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line-faint);border:1px solid var(--line-faint);border-radius:14px;overflow:hidden;margin-top:26px}
.os-principle{background:var(--card);padding:24px}
.os-principle .lead{font-family:var(--serif);font-style:italic;font-size:20px;color:var(--gold);line-height:1.3;margin-bottom:8px}
.os-principle .desc{font-size:15px;color:var(--ink-soft)}

.os-closing{text-align:center;padding:78px 0 96px}
.os-closing .tagline{font-family:var(--serif);font-style:italic;font-size:clamp(28px,4vw,40px);color:var(--gold);margin-bottom:14px}
.os-closing p{font-size:18px;color:var(--ink-soft);max-width:540px;margin:0 auto 28px}
.os-cta{display:inline-flex;align-items:center;gap:10px;background:var(--plum);color:#fff;font-weight:600;font-size:15px;padding:14px 28px;border-radius:8px;text-decoration:none;transition:transform .2s,background .2s}
.os-cta:hover{background:var(--plum-deep);transform:translateY(-1px)}
.os-cta svg{width:18px;height:18px}

.os-reveal{opacity:0;transform:translateY(20px);transition:opacity .7s cubic-bezier(.2,.7,.2,1),transform .7s cubic-bezier(.2,.7,.2,1)}
.os-reveal.in{opacity:1;transform:none}
@media (prefers-reduced-motion:reduce){.os-reveal{opacity:1;transform:none;transition:none}}

@media(max-width:900px){
  /* Stack the flanking columns below the teacher; merge into one card grid. */
  .os-eco-stage{grid-template-columns:1fr;gap:22px}
  .os-eco-center{order:-1;min-height:0}
  .os-eco-side{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
  .os-eco-teacher{max-width:240px}
}
@media(max-width:760px){
  .os-principles{grid-template-columns:1fr}
  .os-hero{padding:96px 22px 70px}
  .os-section{padding:44px 0}
  .os-marker .num{font-size:30px}
  .os-eco-grid{grid-template-columns:repeat(2,1fr)}
}
@media(max-width:600px){
  .os-eco{padding:26px 16px 24px}
  .os-eco-side,.os-eco-grid{grid-template-columns:1fr}
}
`;

// Ecosystem diagram — the AI teacher (center) surrounded by the specialized
// agent/feature cards. Rendered as on-theme HTML/SVG (not a raster) so it
// matches the page's gold/plum/cream palette and stays crisp + responsive.
// Labels come from i18n (story.eco.* — English base, other locales fall back).
const ECO_ICONS: Record<string, React.ReactNode> = {
  homeworkGrader: (
    <>
      <rect x="5" y="3" width="14" height="18" rx="2" />
      <path d="M9 3.5h6V5H9z" />
      <path d="M8.5 13l2.2 2.2L15.5 10" />
    </>
  ),
  tutorAgent: (
    <>
      <path d="M2 8.5 12 4l10 4.5L12 13z" />
      <path d="M6 10.6V15c0 1.6 2.7 3 6 3s6-1.4 6-3v-4.4" />
      <path d="M22 8.5V14" />
    </>
  ),
  mobileApp: (
    <>
      <rect x="7" y="2.5" width="10" height="19" rx="2.5" />
      <line x1="10.5" y1="18.5" x2="13.5" y2="18.5" />
    </>
  ),
  driveMode: (
    <>
      <path d="M4 13.5v-1a8 8 0 0 1 16 0v1" />
      <rect x="3" y="13" width="4" height="6.5" rx="1.6" />
      <rect x="17" y="13" width="4" height="6.5" rx="1.6" />
    </>
  ),
  hitlCourses: (
    <>
      <circle cx="9" cy="7.5" r="3.4" />
      <path d="M2.8 20v-1.4a6.2 6.2 0 0 1 12.4 0V20" />
      <path d="M16.5 11.5l2 2 3.5-3.5" />
    </>
  ),
  liveGroup: (
    <>
      <circle cx="9" cy="8" r="3.1" />
      <path d="M3.4 19.5v-1a5.6 5.6 0 0 1 11.2 0v1" />
      <circle cx="17.2" cy="8.6" r="2.5" />
      <path d="M16.6 13.4a5 5 0 0 1 4 4.9v1.2" />
    </>
  ),
  onDemand: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M10 8.2l6 3.8-6 3.8z" />
    </>
  ),
  integrations: (
    <>
      <path d="M10.5 4a1.9 1.9 0 0 1 3.8 0V6H18a1 1 0 0 1 1 1v3.7h.1a1.9 1.9 0 0 1 0 3.8H19V18a1 1 0 0 1-1 1h-3.7v.1a1.9 1.9 0 0 1-3.8 0V19H6a1 1 0 0 1-1-1v-3.7a1.9 1.9 0 0 1 0-3.8V7a1 1 0 0 1 1-1h4.5z" />
    </>
  ),
  arcade: (
    <>
      <rect x="2.5" y="7.5" width="19" height="9.5" rx="4.75" />
      <line x1="7" y1="10.5" x2="7" y2="14" />
      <line x1="5.3" y1="12.2" x2="8.7" y2="12.2" />
      <circle cx="15.8" cy="11.4" r="1" />
      <circle cx="18.2" cy="13.6" r="1" />
    </>
  ),
  rewards: (
    <>
      <path d="M8 4h8v3.5a4 4 0 0 1-8 0z" />
      <path d="M8 5H5v1a3 3 0 0 0 3 3" />
      <path d="M16 5h3v1a3 3 0 0 1-3 3" />
      <line x1="12" y1="11.5" x2="12" y2="16" />
      <path d="M8.5 20h7l-1-3h-5z" />
    </>
  ),
  scraper: (
    <>
      <path d="M12 3v10" />
      <path d="M8 10.5l4 4 4-4" />
      <path d="M4.5 19.5h15" />
    </>
  ),
  rag: (
    <>
      <path d="M3 5.4c3-1.2 6-1.2 9 .5 3-1.7 6-1.7 9-.5v13.1c-3-1.2-6-1.2-9 .5-3-1.7-6-1.7-9-.5z" />
      <line x1="12" y1="5.9" x2="12" y2="19" />
    </>
  ),
  adaptive: (
    <>
      <path d="M4 20h16" />
      <rect x="5.5" y="11" width="3.2" height="7" rx="0.6" />
      <rect x="10.4" y="6.5" width="3.2" height="11.5" rx="0.6" />
      <rect x="15.3" y="13.5" width="3.2" height="4.5" rx="0.6" />
    </>
  ),
  vision: (
    <>
      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  robot: (
    <>
      <rect x="5" y="8" width="14" height="11" rx="3" />
      <line x1="12" y1="4.5" x2="12" y2="8" />
      <circle cx="12" cy="4" r="1.1" />
      <circle cx="9.5" cy="13" r="1.25" />
      <circle cx="14.5" cy="13" r="1.25" />
      <line x1="9" y1="19" x2="9" y2="21" />
      <line x1="15" y1="19" x2="15" y2="21" />
    </>
  ),
  languages: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18" />
      <path d="M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18" />
    </>
  ),
};

type EcoCard = { id: string; key: string };
// Left / right flank the teacher; the rest sit in the grid below — same set of
// features as the original poster, just reformatted on-theme.
const ECO_LEFT: EcoCard[] = [
  { id: "homeworkGrader", key: "story.eco.homeworkGrader" },
  { id: "tutorAgent", key: "story.eco.tutorAgent" },
  { id: "mobileApp", key: "story.eco.mobileApp" },
  { id: "driveMode", key: "story.eco.driveMode" },
];
const ECO_RIGHT: EcoCard[] = [
  { id: "hitlCourses", key: "story.eco.hitlCourses" },
  { id: "liveGroup", key: "story.eco.liveGroup" },
  { id: "onDemand", key: "story.eco.onDemand" },
  { id: "integrations", key: "story.eco.integrations" },
];
const ECO_BOTTOM: EcoCard[] = [
  { id: "arcade", key: "story.eco.arcade" },
  { id: "rewards", key: "story.eco.rewards" },
  { id: "scraper", key: "story.eco.scraper" },
  { id: "rag", key: "story.eco.rag" },
  { id: "adaptive", key: "story.eco.adaptive" },
  { id: "vision", key: "story.eco.vision" },
  { id: "robot", key: "story.eco.robot" },
  { id: "languages", key: "story.eco.languages" },
];

// Render a single line's inline emphasis: **bold** -> <strong>, *italic* -> <em>.
// Non-nested; our copy never combines the two. Everything else is plain text.
function renderInline(line: string, keyPrefix: string): React.ReactNode[] {
  const parts = line.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
  return parts
    .filter((p) => p !== "")
    .map((part, i) => {
      const key = `${keyPrefix}-${i}`;
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={key}>{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith("*") && part.endsWith("*")) {
        return <em key={key}>{part.slice(1, -1)}</em>;
      }
      return <span key={key}>{part}</span>;
    });
}

// One ecosystem feature card: gold line-icon + translated label.
function ecoCard(
  c: EcoCard,
  t: (key: string, vars?: Record<string, string | number>) => string,
): React.ReactNode {
  return (
    <div className="os-eco-card" key={c.id}>
      <span className="os-eco-ic" aria-hidden="true">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          {ECO_ICONS[c.id]}
        </svg>
      </span>
      <span className="os-eco-lb">{t(c.key)}</span>
    </div>
  );
}

// Turn a translated string into React nodes, honoring \n as a line break and
// **bold**/*italic* inline markers.
function renderRich(text: string): React.ReactNode[] {
  const lines = text.split("\n");
  const out: React.ReactNode[] = [];
  lines.forEach((line, i) => {
    if (i > 0) out.push(<br key={`br-${i}`} />);
    out.push(...renderInline(line, `l${i}`));
  });
  return out;
}

export default function OurStoryContent() {
  const { t } = useT();

  useEffect(() => {
    const io = new IntersectionObserver(
      (es) =>
        es.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("in");
            io.unobserve(e.target);
          }
        }),
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" },
    );
    document.querySelectorAll(".os-reveal").forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);

  return (
    <div className="os-root">
      {/* Fraunces (serif) + Inter (sans); graceful fallback to Georgia/system if offline. */}
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      {/* eslint-disable-next-line @next/next/no-page-custom-font -- scoped to this route; falls back to Georgia/system offline */}
      <link
        href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;0,9..144,600;1,9..144,400;1,9..144,500&family=Inter:wght@400;500;600&display=swap"
        rel="stylesheet"
      />
      {/* Inject as raw CSS: rendering the string as a text child makes the
          server HTML-escape the quotes in the CSS (' -> &#x27;, " -> &quot;)
          while the hydrated DOM has the raw characters, causing a React
          hydration mismatch. dangerouslySetInnerHTML writes the CSS verbatim. */}
      <style dangerouslySetInnerHTML={{ __html: styles }} />

      {/* hero background points at the SAME photo as the homepage hero */}
      <div
        className="os-hero"
        style={{ "--hero-img": "url('/wallpapers/wisdom_bodhi.webp')" } as React.CSSProperties}
      >
        <div className="os-hero-inner">
          <div className="os-eyebrow os-reveal">{t("story.title")}</div>
          <h1 className="os-reveal">{renderRich(t("story.hero"))}</h1>
        </div>
      </div>

      <div className="os-wrap">
        <div className="os-opener os-reveal">
          <div className="os-believe-label">{t("story.believeTitle")}</div>
          <p className="os-believe">{renderRich(t("story.believeBody"))}</p>
        </div>

        <main>
          {/* 01 — Where the idea was forged */}
          <section className="os-section">
            <div className="os-marker os-reveal">
              <span className="num">01</span>
              <span className="label">{t("story.s1Label")}</span>
            </div>
            <h2 className="os-reveal">{renderRich(t("story.s1Title"))}</h2>
            <p className="os-body os-reveal">{renderRich(t("story.s1Body1"))}</p>
            <p className="os-body os-reveal">{renderRich(t("story.s1Body2"))}</p>
            <div className="os-pullquote os-reveal">{renderRich(t("story.s1Quote"))}</div>
            <p className="os-body os-reveal">{renderRich(t("story.s1Body3"))}</p>
          </section>

          {/* 02 — What the name means */}
          <section className="os-section">
            <div className="os-marker os-reveal">
              <span className="num">02</span>
              <span className="label">{t("story.s2Label")}</span>
            </div>
            <h2 className="os-reveal">{t("story.s2Title")}</h2>
            <div className="os-name-grid">
              <div className="os-mascot os-reveal">
                <MascotImage width={210} alt={t("story.mascotAlt")} />
              </div>
              <div className="os-name-body os-reveal">
                <p className="os-body">{renderRich(t("story.s2Body1"))}</p>
                <p className="os-body">{renderRich(t("story.s2Body2"))}</p>
              </div>
            </div>
          </section>

          {/* 03 — Learning, reimagined */}
          <section className="os-section">
            <div className="os-marker os-reveal">
              <span className="num">03</span>
              <span className="label">{t("story.s3Label")}</span>
            </div>
            <h2 className="os-reveal">{renderRich(t("story.s3Title"))}</h2>
            <p className="os-body os-reveal">{renderRich(t("story.s3Body1"))}</p>
            <p className="os-body os-reveal">{renderRich(t("story.s3Body2"))}</p>
            <div className="os-eco os-reveal">
              <div className="os-eco-head">
                <div className="os-eco-title">{t("story.eco.title")}</div>
                <div className="os-eco-sub">{t("story.eco.subtitle")}</div>
              </div>

              <div className="os-eco-stage">
                <div className="os-eco-side">
                  {ECO_LEFT.map((c) => ecoCard(c, t))}
                </div>

                <div className="os-eco-center">
                  <div className="os-eco-glow" aria-hidden="true" />
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    className="os-eco-teacher"
                    src="/salareen-teacher.webp"
                    alt={t("story.diagramAlt")}
                  />
                  <div className="os-eco-center-cap">{t("story.eco.center")}</div>
                </div>

                <div className="os-eco-side">
                  {ECO_RIGHT.map((c) => ecoCard(c, t))}
                </div>
              </div>

              <div className="os-eco-grid">
                {ECO_BOTTOM.map((c) => ecoCard(c, t))}
              </div>

              <div className="os-eco-hint">{t("story.eco.hint")}</div>
            </div>
          </section>

          {/* 04 — How we build */}
          <section className="os-section">
            <div className="os-marker os-reveal">
              <span className="num">04</span>
              <span className="label">{t("story.s4Label")}</span>
            </div>
            <h2 className="os-reveal">{renderRich(t("story.s4Title"))}</h2>
            <div className="os-principles os-reveal">
              <div className="os-principle">
                <div className="lead">{t("story.build.privacyTitle")}</div>
                <div className="desc">{t("story.build.privacyBody")}</div>
              </div>
              <div className="os-principle">
                <div className="lead">{t("story.build.aiTitle")}</div>
                <div className="desc">{t("story.build.aiBody")}</div>
              </div>
              <div className="os-principle">
                <div className="lead">{t("story.build.affordTitle")}</div>
                <div className="desc">{t("story.build.affordBody")}</div>
              </div>
              <div className="os-principle">
                <div className="lead">{t("story.build.respectTitle")}</div>
                <div className="desc">{t("story.build.respectBody")}</div>
              </div>
            </div>
          </section>

          <div className="os-closing os-reveal">
            <div className="tagline">{t("story.closingTagline")}</div>
            <p>{t("story.closingBody")}</p>
            <a href="/browse" className="os-cta">
              {t("story.closingCta")}
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path
                  d="M5 12h14M13 6l6 6-6 6"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </a>
          </div>
        </main>
      </div>
    </div>
  );
}
