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
//   platform diagram -> /salareen-ecosystem.webp
//   team photos      -> fill the TEAM array below (circular crops; optional)

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

/* TEAM — centered label + 4x2 circular photo slots */
.os-team{margin:42px 0 10px;text-align:center}
.os-team-label{font-family:var(--serif);font-style:italic;font-size:26px;color:var(--gold);margin-bottom:26px}
.os-team-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:30px 34px;max-width:820px;margin:0 auto}
.os-member{display:flex;flex-direction:column;align-items:center}
.os-member .avatar{width:120px;height:120px;border-radius:50%;background:var(--bg-soft);border:2px dashed var(--line);display:flex;align-items:center;justify-content:center;overflow:hidden}
.os-member .avatar img{width:100%;height:100%;object-fit:cover}
.os-member .avatar.empty::after{content:"photo";font-size:11px;color:var(--ink-faint);letter-spacing:.05em}
.os-member .m-name{margin-top:14px;font-size:15px;font-weight:600;color:var(--ink)}
.os-member .m-role{font-size:13px;color:var(--ink-faint);margin-top:2px}

.os-name-grid{display:flex;gap:44px;align-items:center;flex-wrap:wrap}
.os-mascot{flex:0 0 auto;display:flex;align-items:center;justify-content:center}
.os-mascot img{height:210px;width:auto;max-width:100%;filter:drop-shadow(0 12px 22px rgba(33,29,23,.16))}
.os-name-body{flex:1;min-width:300px}

.os-diagram{margin:24px 0 12px;border-radius:16px;overflow:hidden;border:1px solid var(--line-faint);background:var(--plum-deep)}
.os-diagram img{width:100%;height:auto;display:block}

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

@media(max-width:760px){
  .os-principles{grid-template-columns:1fr}
  .os-hero{padding:96px 22px 70px}
  .os-section{padding:44px 0}
  .os-marker .num{font-size:30px}
  .os-team-grid{grid-template-columns:repeat(2,1fr);gap:28px}
}
@media(max-width:600px){
  .os-team-grid{grid-template-columns:repeat(2,1fr);gap:24px}
  .os-member .avatar{width:96px;height:96px}
}
`;

type Member = { name: string; role: string; img: string | null };

const TEAM: Member[] = [
  { name: "Name", role: "Role", img: null },
  { name: "Name", role: "Role", img: null },
  { name: "Name", role: "Role", img: null },
  { name: "Name", role: "Role", img: null },
  { name: "Name", role: "Role", img: null },
  { name: "Name", role: "Role", img: null },
  { name: "Name", role: "Role", img: null },
  { name: "Name", role: "Role", img: null },
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

            <div className="os-team os-reveal">
              <div className="os-team-label">{t("story.teamLabel")}</div>
              <div className="os-team-grid">
                {TEAM.map((m, i) => (
                  <div className="os-member" key={i}>
                    <div className={"avatar" + (m.img ? "" : " empty")}>
                      {m.img ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={m.img} alt={m.name} />
                      ) : null}
                    </div>
                    <div className="m-name">{m.name}</div>
                    <div className="m-role">{m.role}</div>
                  </div>
                ))}
              </div>
            </div>

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
            <div className="os-diagram os-reveal">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/salareen-ecosystem.webp" alt={t("story.diagramAlt")} />
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
