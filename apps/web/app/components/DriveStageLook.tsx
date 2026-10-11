"use client";

import { useEffect, useId, useRef } from "react";

export const DRIVE_LOOKS = [
  { value: "bars", label: "Bars", group: "Motion" },
  { value: "line", label: "Frequency line", group: "Motion" },
  { value: "mouth", label: "Talking mouth", group: "Motion" },
  { value: "ripple", label: "Soft ripples", group: "Motion" },
  { value: "lantern", label: "Lantern", group: "Motion" },
  { value: "face-amina", label: "Amina", group: "Faces" },
  { value: "face-mei", label: "Mei", group: "Faces" },
  { value: "face-luis", label: "Luis", group: "Faces" },
  { value: "face-amara", label: "Amara", group: "Faces" },
  { value: "face-noah", label: "Noah", group: "Faces" },
  { value: "face-priya", label: "Priya", group: "Faces" },
] as const;

export type DriveLook = (typeof DRIVE_LOOKS)[number]["value"];

export function isDriveLook(value: string): value is DriveLook {
  return DRIVE_LOOKS.some((row) => row.value === value);
}

const LOOK_CSS = `
.drive-look { display:flex; align-items:center; justify-content:center; width:100%; min-height:140px; --level:.16; }
.drive-look.is-speaking { --level:.42; }
.drive-look .bars { display:none; align-items:center; justify-content:center; gap:7px; height:32vh; max-height:220px; }
.drive-look[data-look="bars"] .bars { display:flex; }
.drive-look .bars i { display:block; width:9px; border-radius:99px; transform-origin:center;
  background:linear-gradient(180deg,#e8fdff,#3ec6e0);
  height:calc(16px + var(--level) * 18vh); animation:driveBar .8s ease-in-out infinite; animation-play-state:paused; }
.drive-look.is-speaking .bars i { animation-play-state:running; }
.drive-look .bars i:nth-child(odd) { animation-delay:.14s; }
.drive-look .bars i:nth-child(3n) { animation-delay:.28s; }
@keyframes driveBar { 50% { transform:scaleY(1.7); } }
.drive-look .line, .drive-look .mouth, .drive-look .ripple, .drive-look .lantern, .drive-look .face { display:none; }
.drive-look[data-look="line"] .line { display:block; width:min(920px, 86vw); height:min(28vh, 220px); }
.drive-look[data-look="mouth"] .mouth { display:block; }
.drive-look[data-look="ripple"] .ripple { display:block; }
.drive-look[data-look="lantern"] .lantern { display:block; }
.drive-look[data-look^="face-"] .face { display:block; width:min(280px, 68vw); height:auto; }
.drive-look .mouth { position:relative; width:min(280px, 64vw); height:150px; }
.drive-look .lip-upper, .drive-look .lip-lower { position:absolute; left:6%; right:6%; height:46px; z-index:2; }
.drive-look .lip-upper { top:22px; border-radius:80px 80px 16px 16px; background:linear-gradient(#e7a8ad, #c96b74); }
.drive-look .lip-lower { bottom:22px; border-radius:16px 16px 80px 80px; background:linear-gradient(#c96b74, #a85460); }
.drive-look .lip-opening { position:absolute; z-index:1; left:22%; right:22%; top:50%; transform:translateY(-50%);
  border-radius:50%; background:#3a1824; height:calc(8px + var(--level) * 52px); }
.drive-look.is-speaking .lip-opening { animation:driveLip .42s ease-in-out infinite; }
@keyframes driveLip { 50% { height:calc(18px + var(--level) * 58px); } }
.drive-look .ripple { position:relative; width:220px; height:220px; }
.drive-look .ripple b, .drive-look .ripple i { position:absolute; border-radius:50%; }
.drive-look .ripple b { inset:38%; background:#8feaff; box-shadow:0 0 24px rgba(143,234,255,.35);
  transform:scale(calc(.85 + var(--level) * .5)); }
.drive-look .ripple i { inset:18%; border:2px solid rgba(143,234,255,.5); animation:driveRipple 2.8s ease-out infinite; }
.drive-look .ripple i:nth-child(3) { animation-delay:.9s; }
.drive-look .ripple i:nth-child(4) { animation-delay:1.8s; }
.drive-look.is-speaking .ripple i { animation-duration:1.7s; }
@keyframes driveRipple {
  0% { transform:scale(calc(.55 + var(--level) * .3)); opacity:.65; }
  100% { transform:scale(calc(1.35 + var(--level) * .45)); opacity:0; }
}
.drive-look .lantern i { display:block; width:148px; height:148px; border-radius:50%;
  background:radial-gradient(circle at 40% 34%, #fff8e4, #f0b429 46%, #c2410c 80%);
  box-shadow:0 0 calc(18px + var(--level) * 70px) rgba(240,180,41,.4);
  transform:scale(calc(.94 + var(--level) * .22)); }
.drive-look.is-speaking .lantern i { animation:driveLantern 1.8s ease-in-out infinite; }
@keyframes driveLantern { 50% { filter:brightness(1.08); transform:scale(calc(1.02 + var(--level) * .16)); } }
.drive-look[data-look="face-amina"] { --skin:#8d5524; --lip:#c4848a; --hair:#1b120c; }
.drive-look[data-look="face-mei"] { --skin:#f0c9a0; --lip:#d7a0a6; --hair:#24180f; }
.drive-look[data-look="face-luis"] { --skin:#c68642; --lip:#c98980; --hair:#3a2414; }
.drive-look[data-look="face-amara"] { --skin:#5c3317; --lip:#a86a72; --hair:#140e0a; }
.drive-look[data-look="face-noah"] { --skin:#f3d2b5; --lip:#e0a8ad; --hair:#c4a574; }
.drive-look[data-look="face-priya"] { --skin:#a56b3c; --lip:#c47d78; --hair:#1a120c; }
.drive-look .skin, .drive-look .ear { fill:var(--skin, #e6b48a); }
.drive-look .hfill { fill:var(--hair, #1a120c); }
.drive-look .lip { fill:var(--lip, #d08990); }
.drive-look .brow { fill:none; stroke:var(--hair, #1a120c); stroke-width:2.6; stroke-linecap:round; }
.drive-look .nose { fill:none; stroke:rgba(40,24,16,.35); stroke-width:2.2; stroke-linecap:round; }
.drive-look .hair, .drive-look .glasses { visibility:hidden; }
.drive-look[data-look="face-amina"] .hair-coils,
.drive-look[data-look="face-mei"] .hair-bangs,
.drive-look[data-look="face-luis"] .hair-crop,
.drive-look[data-look="face-amara"] .hair-natural,
.drive-look[data-look="face-noah"] .hair-crop,
.drive-look[data-look="face-priya"] .hair-long,
.drive-look[data-look="face-noah"] .glasses { visibility:visible; }
.drive-look .mouth-wrap { transform-box:fill-box; transform-origin:center; transform:scaleY(calc(.42 + var(--level) * 1.7)); }
.drive-look.is-speaking .mouth-wrap { animation:driveMouth .46s ease-in-out infinite; }
@keyframes driveMouth {
  0%, 100% { transform:scaleY(calc(.4 + var(--level) * .7)); }
  50% { transform:scaleY(calc(.9 + var(--level) * 1.35)); }
}
.drive-look .eye { transform-box:fill-box; transform-origin:center; animation:driveBlink 7.5s infinite; }
@keyframes driveBlink { 0%, 92%, 100% { transform:scaleY(1); } 96% { transform:scaleY(.12); } }
@media (prefers-reduced-motion: reduce) {
  .drive-look .bars i, .drive-look .lip-opening, .drive-look .ripple i,
  .drive-look .lantern i, .drive-look .mouth-wrap, .drive-look .eye { animation:none !important; }
}
`;

export default function DriveStageLook({ look, playing }: { look: string; playing: boolean }) {
  const chosen = isDriveLook(look) ? look : "bars";
  const pathId = useId().replace(/:/g, "");
  const pathRef = useRef<SVGPathElement | null>(null);
  const playingRef = useRef(playing);
  playingRef.current = playing;

  useEffect(() => {
    if (chosen !== "line") return;
    let frame = 0;
    let phase = 0;
    let alive = true;
    const tick = () => {
      if (!alive) return;
      const path = pathRef.current;
      if (path) {
        const speaking = playingRef.current;
        const amp = speaking ? 36 : 6;
        phase += speaking ? 0.22 : 0.04;
        let d = "";
        for (let x = 0; x <= 600; x += 10) {
          const y = 90 + Math.sin(x / 26 + phase) * amp * (0.65 + 0.35 * Math.sin(x / 80 + phase * 0.5));
          d += (x ? "L" : "M") + x + " " + y.toFixed(1);
        }
        path.setAttribute("d", d);
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => {
      alive = false;
      cancelAnimationFrame(frame);
    };
  }, [chosen]);

  return (
    <div className={playing ? "drive-look is-speaking" : "drive-look"} data-look={chosen} aria-hidden="true">
      <style>{LOOK_CSS}</style>
      <div className="bars">
        {Array.from({ length: 17 }, (_, index) => <i key={index} />)}
      </div>
      <svg className="line" viewBox="0 0 600 180" preserveAspectRatio="none">
        <path id={pathId} ref={pathRef} fill="none" stroke="#8feaff" strokeWidth="3.5" strokeLinecap="round" />
      </svg>
      <div className="mouth"><i className="lip-upper" /><i className="lip-opening" /><i className="lip-lower" /></div>
      <div className="ripple"><b /><i /><i /><i /></div>
      <div className="lantern"><i /></div>
      <svg className="face" viewBox="0 0 200 250">
        <g className="hair hair-coils hfill"><circle cx="48" cy="78" r="18" /><circle cx="72" cy="50" r="18" /><circle cx="100" cy="42" r="20" /><circle cx="128" cy="50" r="18" /><circle cx="152" cy="78" r="18" /><circle cx="38" cy="108" r="16" /><circle cx="162" cy="108" r="16" /></g>
        <g className="hair hair-natural hfill"><ellipse cx="100" cy="96" rx="90" ry="74" /></g>
        <g className="hair hair-long hfill"><path d="M52 108 Q48 42 100 34 Q152 42 148 108 Q170 48 176 214 Q148 198 138 128 Q100 78 62 128 Q52 198 24 214 Q30 48 52 108" /></g>
        <path d="M28 248 Q28 198 72 186 Q100 178 128 186 Q172 198 172 248" fill="#163044" />
        <ellipse className="ear" cx="38" cy="132" rx="12" ry="16" />
        <ellipse className="ear" cx="162" cy="132" rx="12" ry="16" />
        <ellipse className="skin" cx="100" cy="132" rx="64" ry="76" />
        <path className="brow" d="M64 114 Q76 106 88 114" />
        <path className="brow" d="M112 114 Q124 106 136 114" />
        <path className="nose" d="M100 134 Q108 150 100 158" />
        <g className="hair hair-bangs hfill"><path d="M42 118 Q54 46 100 40 Q146 46 158 118 Q136 86 100 92 Q64 86 42 118" /></g>
        <g className="hair hair-crop hfill"><path d="M46 124 Q54 52 100 46 Q146 52 154 124 Q136 102 100 106 Q64 102 46 124" /></g>
        <ellipse className="eye" cx="76" cy="128" rx="7" ry="8" fill="#1c140f" />
        <ellipse className="eye" cx="124" cy="128" rx="7" ry="8" fill="#1c140f" />
        <circle cx="78" cy="126" r="2" fill="#fff" opacity=".85" />
        <circle cx="126" cy="126" r="2" fill="#fff" opacity=".85" />
        <g className="glasses" fill="none" stroke="#d7e7ea" strokeWidth="2.4"><circle cx="76" cy="128" r="14" /><circle cx="124" cy="128" r="14" /><path d="M90 128 H110" /></g>
        <g className="mouth-wrap">
          <ellipse cx="100" cy="166" rx="14" ry="8" fill="#4a2030" />
          <path className="lip" d="M84 162 Q100 156 116 162 Q100 176 84 162" />
        </g>
      </svg>
    </div>
  );
}
