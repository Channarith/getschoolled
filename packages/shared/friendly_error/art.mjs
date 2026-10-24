// Original Sala mascot artwork: the gold-S seal with its Bodhi leaf, given a face.
// Pure SVG + CSS (no external hosts), so it works under a strict CSP and offline.
// Moods: tears (network/maintenance), surprised (404), thinking (501), calm (500).

const NAVY = "#0b1020";
const GOLD = "#d4af37";
const GOLD_LIGHT = "#f6e08a";
const TEAL = "#5eead4";

const FACES = {
  tears: {
    brows: `<path fill="none" stroke="#f6e08a" stroke-width="5" stroke-linecap="round" d="M72 92 Q86 80 104 90" /><path fill="none" stroke="#f6e08a" stroke-width="5" stroke-linecap="round" d="M168 92 Q154 80 136 90" />`,
    eyes: `<ellipse cx="88" cy="112" rx="15" ry="17" fill="#fff"/><ellipse cx="152" cy="112" rx="15" ry="17" fill="#fff"/>
      <circle cx="88" cy="115" r="9" fill="#1b2540"/><circle cx="152" cy="115" r="9" fill="#1b2540"/>
      <circle cx="85" cy="111" r="3.4" fill="#fff"/><circle cx="149" cy="111" r="3.4" fill="#fff"/>
      <path d="M74 126 Q88 134 102 126" fill="none" stroke="#8fd3ff" stroke-width="3" opacity=".7"/>
      <path d="M138 126 Q152 134 166 126" fill="none" stroke="#8fd3ff" stroke-width="3" opacity=".7"/>`,
    mouth: `<path d="M104 152 Q120 140 136 152" fill="none" stroke="${GOLD_LIGHT}" stroke-width="5" stroke-linecap="round"/>`,
    extra: `<g class="sfe-tear sfe-t1"><path d="M84 130 Q76 148 84 156 Q92 148 84 130Z" fill="#7dd3fc"/></g>
      <g class="sfe-tear sfe-t2"><path d="M156 130 Q148 148 156 156 Q164 148 156 130Z" fill="#7dd3fc"/></g>
      <g class="sfe-tear sfe-t3"><path d="M84 130 Q78 142 84 148 Q90 142 84 130Z" fill="#bae6fd"/></g>`,
  },
  surprised: {
    brows: `<path fill="none" stroke="#f6e08a" stroke-width="5" stroke-linecap="round" d="M72 80 Q88 68 104 78" /><path fill="none" stroke="#f6e08a" stroke-width="5" stroke-linecap="round" d="M168 80 Q152 68 136 78" />`,
    eyes: `<circle cx="88" cy="108" r="18" fill="#fff"/><circle cx="152" cy="108" r="18" fill="#fff"/>
      <circle cx="90" cy="109" r="8" fill="#1b2540"/><circle cx="150" cy="109" r="8" fill="#1b2540"/>
      <circle cx="87" cy="105" r="3" fill="#fff"/><circle cx="147" cy="105" r="3" fill="#fff"/>`,
    mouth: `<ellipse cx="120" cy="150" rx="9" ry="11" fill="#1b2540" stroke="${GOLD_LIGHT}" stroke-width="3"/>`,
    extra: `<g class="sfe-bob"><text x="186" y="64" font-size="40" font-weight="800" fill="${TEAL}" font-family="Georgia,serif">?</text></g>
      <g class="sfe-bob sfe-d2"><text x="10" y="62" font-size="30" font-weight="800" fill="${GOLD_LIGHT}" font-family="Georgia,serif">!</text></g>`,
  },
  thinking: {
    brows: `<path fill="none" stroke="#f6e08a" stroke-width="5" stroke-linecap="round" d="M72 90 Q88 84 104 90" /><path fill="none" stroke="#f6e08a" stroke-width="5" stroke-linecap="round" d="M136 80 Q152 70 168 82" />`,
    eyes: `<ellipse cx="88" cy="110" rx="14" ry="15" fill="#fff"/><ellipse cx="152" cy="110" rx="14" ry="15" fill="#fff"/>
      <circle cx="94" cy="104" r="8" fill="#1b2540"/><circle cx="158" cy="104" r="8" fill="#1b2540"/>
      <circle cx="91" cy="101" r="3" fill="#fff"/><circle cx="155" cy="101" r="3" fill="#fff"/>`,
    mouth: `<path d="M106 152 Q122 148 134 142" fill="none" stroke="${GOLD_LIGHT}" stroke-width="5" stroke-linecap="round"/>`,
    extra: `<g class="sfe-bob"><circle cx="192" cy="72" r="5" fill="${TEAL}"/><circle cx="206" cy="54" r="7" fill="${TEAL}"/>
      <circle cx="222" cy="28" r="15" fill="${GOLD_LIGHT}"/><path d="M216 26 h12 M217 31 h10" stroke="${NAVY}" stroke-width="2.5" stroke-linecap="round"/></g>`,
  },
  calm: {
    brows: `<path fill="none" stroke="#f6e08a" stroke-width="5" stroke-linecap="round" d="M72 92 Q88 86 104 92" /><path fill="none" stroke="#f6e08a" stroke-width="5" stroke-linecap="round" d="M168 92 Q152 86 136 92" />`,
    eyes: `<ellipse cx="88" cy="112" rx="14" ry="15" fill="#fff"/><ellipse cx="152" cy="112" rx="14" ry="15" fill="#fff"/>
      <circle cx="88" cy="114" r="8" fill="#1b2540"/><circle cx="152" cy="114" r="8" fill="#1b2540"/>
      <circle cx="85" cy="110" r="3" fill="#fff"/><circle cx="149" cy="110" r="3" fill="#fff"/>`,
    mouth: `<path d="M102 146 Q120 160 138 146" fill="none" stroke="${GOLD_LIGHT}" stroke-width="5" stroke-linecap="round"/>`,
    extra: `<g class="sfe-tear sfe-t1"><path d="M186 84 Q178 100 186 106 Q194 100 186 84Z" fill="#7dd3fc"/></g>`,
  },
};

const STYLE = `.sfe-tear{animation:sfeTear 2.2s ease-in infinite;transform-box:fill-box}
.sfe-t2{animation-delay:.7s}.sfe-t3{animation-delay:1.3s}
.sfe-bob{animation:sfeBob 2.6s ease-in-out infinite;transform-box:fill-box}
.sfe-d2{animation-delay:.9s}
.sfe-seal{animation:sfeFloat 4s ease-in-out infinite;transform-box:fill-box;transform-origin:50% 50%}
@keyframes sfeTear{0%{transform:translateY(-4px) scale(.6);opacity:0}15%{opacity:1;transform:translateY(0) scale(1)}100%{transform:translateY(46px) scale(.9);opacity:0}}
@keyframes sfeBob{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
@keyframes sfeFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}
@media (prefers-reduced-motion:reduce){.sfe-tear,.sfe-bob,.sfe-seal{animation:none!important}.sfe-tear{opacity:.9}}`;

export const MOODS = Object.keys(FACES);

/** Self-contained SVG string for a mood. `animated:false` omits the CSS (React Native). */
export function moodSvg(mood = "calm", { title = "Sala, the Salareen mascot", animated = true, size = 240 } = {}) {
  const face = FACES[mood] || FACES.calm;
  const safeTitle = String(title).replace(/[<>&"]/g, "");
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 260" width="${size}" height="${Math.round(size * 260 / 240)}" role="img" aria-label="${safeTitle}" class="sfe-art sfe-${mood}">
<title>${safeTitle}</title>${animated ? `<style>${STYLE}</style>` : ""}
<defs><radialGradient id="sfeG" cx="50%" cy="38%" r="70%"><stop offset="0" stop-color="#1b2a55"/><stop offset="1" stop-color="${NAVY}"/></radialGradient>
<linearGradient id="sfeGold" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${GOLD_LIGHT}"/><stop offset="1" stop-color="#b8861b"/></linearGradient></defs>
<g class="sfe-seal">
<circle cx="120" cy="142" r="100" fill="url(#sfeG)" stroke="url(#sfeGold)" stroke-width="7"/>
<circle cx="120" cy="142" r="88" fill="none" stroke="${GOLD}" stroke-width="2" opacity=".75"/>
<path d="M120 4 C152 22 158 56 120 76 C82 56 88 22 120 4Z" fill="#2f8f46" stroke="#1f6a33" stroke-width="2"/>
<path d="M120 10 V72 M120 30 L104 24 M120 44 L138 36 M120 56 L106 50" stroke="#a7f3b5" stroke-width="2" fill="none" stroke-linecap="round" opacity=".8"/>
${face.eyes}${face.brows}${face.mouth}
<path d="M144 178 C136 162 98 162 98 184 C98 202 144 196 144 216 C144 236 104 236 96 220" fill="none" stroke="url(#sfeGold)" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>
</g>${face.extra}</svg>`;
}
