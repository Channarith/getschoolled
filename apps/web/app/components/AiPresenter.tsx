"use client";

// Live "presenter" video tile for the AI instructor — a Bigo/live-stream style
// feed where the agent visibly presents. We don't stream a real talking-head
// avatar; instead the branded mascot animates (bobbing + a pulsing glow + an
// audio visualizer) whenever narration is speaking, with a LIVE badge, an
// elapsed timer, live captions of what's being said, and floating chat bubbles.

import { useEffect, useRef, useState } from "react";

export type PresenterMessage = { role: string; text: string };

export type AiPresenterProps = {
  speaking: boolean;
  name?: string;
  persona?: string;
  caption?: string;
  avatarSrc?: string;
  live?: boolean;
  muted?: boolean;
  onToggleMute?: () => void;
  messages?: PresenterMessage[];
};

function useElapsed(): string {
  const start = useRef(Date.now());
  const [, tick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, []);
  const s = Math.floor((Date.now() - start.current) / 1000);
  const mm = String(Math.floor(s / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

export default function AiPresenter({
  speaking, name = "AI Instructor", persona, caption,
  avatarSrc = "/salareen-mascot.webp", live = true, muted, onToggleMute, messages = [],
}: AiPresenterProps) {
  const elapsed = useElapsed();
  const recent = messages.slice(-2);

  return (
    <div className="ai-presenter" data-speaking={speaking ? "1" : "0"}>
      <style>{PRESENTER_CSS}</style>

      {/* Animated stage */}
      <div className="ai-presenter__stage">
        <div className="ai-presenter__glow" />
        {/* eslint-disable-next-line @next/next/no-img-element -- small static mascot; next/image adds no value in this animated tile */}
        <img className="ai-presenter__avatar" src={avatarSrc} alt={name} draggable={false} />

        {/* Top bar: LIVE + timer */}
        <div className="ai-presenter__top">
          {live && (
            <span className="ai-presenter__live">
              <span className="ai-presenter__dot" /> LIVE
            </span>
          )}
          <span className="ai-presenter__timer">{elapsed}</span>
        </div>

        {/* Audio visualizer (animates only while speaking) */}
        <div className="ai-presenter__bars" aria-hidden>
          {Array.from({ length: 7 }).map((_, i) => (
            <span key={i} style={{ animationDelay: `${i * 0.09}s` }} />
          ))}
        </div>

        {/* Floating chat bubbles (Bigo-style) */}
        {recent.length > 0 && (
          <div className="ai-presenter__chat">
            {recent.map((m, i) => (
              <div key={i} className={`ai-presenter__bubble ${m.role === "student" ? "me" : "ai"}`}>
                <strong>{m.role === "student" ? "You" : name}:</strong> {m.text.slice(0, 90)}
                {m.text.length > 90 ? "…" : ""}
              </div>
            ))}
          </div>
        )}

        {/* Presenter identity + speaking state */}
        <div className="ai-presenter__id">
          <span className="ai-presenter__name">{name}</span>
          {persona && <span className="ai-presenter__persona">{persona}</span>}
          <span className="ai-presenter__state">{speaking ? "🎙 presenting…" : "listening"}</span>
        </div>

        {onToggleMute && (
          <button type="button" className="ai-presenter__mute" onClick={onToggleMute}
            title={muted ? "Unmute presenter" : "Mute presenter"}>
            {muted ? "🔇" : "🔊"}
          </button>
        )}
      </div>

      {/* Live captions of the current narration */}
      {caption && (
        <div className="ai-presenter__caption">
          <span>{caption.length > 180 ? `${caption.slice(0, 180)}…` : caption}</span>
        </div>
      )}
    </div>
  );
}

const PRESENTER_CSS = `
.ai-presenter { border-radius: 16px; overflow: hidden; border: 1px solid #23304f;
  background: #060a17; box-shadow: 0 10px 30px rgba(0,0,0,0.35); }
.ai-presenter__stage { position: relative; aspect-ratio: 16 / 9; display: flex;
  align-items: center; justify-content: center; overflow: hidden;
  background: radial-gradient(120% 120% at 50% 20%, #1b2a5a 0%, #0a1330 55%, #060a17 100%); }
.ai-presenter__glow { position: absolute; width: 60%; aspect-ratio: 1; border-radius: 50%;
  background: radial-gradient(circle, rgba(56,189,248,0.45), transparent 60%);
  filter: blur(18px); opacity: 0.5; transition: opacity .3s; }
.ai-presenter[data-speaking="1"] .ai-presenter__glow { animation: aiGlow 1.4s ease-in-out infinite; opacity: 0.9; }
.ai-presenter__avatar { position: relative; z-index: 2; height: 82%; max-width: 82%;
  object-fit: contain; filter: drop-shadow(0 8px 20px rgba(0,0,0,0.5));
  animation: aiBob 4s ease-in-out infinite; }
.ai-presenter[data-speaking="1"] .ai-presenter__avatar { animation: aiTalk 0.5s ease-in-out infinite; }
.ai-presenter__top { position: absolute; top: 10px; left: 10px; right: 10px; z-index: 3;
  display: flex; align-items: center; justify-content: space-between; }
.ai-presenter__live { display: inline-flex; align-items: center; gap: 6px; background: #e11d48;
  color: #fff; font-weight: 800; font-size: 12px; letter-spacing: .5px; padding: 3px 10px; border-radius: 999px; }
.ai-presenter__dot { width: 8px; height: 8px; border-radius: 50%; background: #fff; animation: aiBlink 1s steps(2) infinite; }
.ai-presenter__timer { background: rgba(0,0,0,0.45); color: #e8ecf6; font-size: 12px;
  padding: 3px 8px; border-radius: 999px; font-variant-numeric: tabular-nums; }
.ai-presenter__bars { position: absolute; bottom: 12px; left: 50%; transform: translateX(-50%);
  z-index: 3; display: flex; align-items: flex-end; gap: 4px; height: 26px; }
.ai-presenter__bars span { width: 5px; height: 6px; border-radius: 3px;
  background: linear-gradient(#67e8f9, #38bdf8); }
.ai-presenter[data-speaking="1"] .ai-presenter__bars span { animation: aiBars .8s ease-in-out infinite; }
.ai-presenter__id { position: absolute; bottom: 10px; left: 12px; z-index: 3;
  display: flex; align-items: center; gap: 8px; }
.ai-presenter__name { color: #fff; font-weight: 700; font-size: 14px; text-shadow: 0 1px 4px rgba(0,0,0,.6); }
.ai-presenter__persona { background: rgba(56,189,248,0.2); color: #bae6fd; border: 1px solid #38bdf8;
  font-size: 11px; padding: 1px 8px; border-radius: 999px; text-transform: capitalize; }
.ai-presenter__state { color: #9fb4d8; font-size: 12px; }
.ai-presenter__chat { position: absolute; right: 10px; bottom: 44px; z-index: 3;
  display: flex; flex-direction: column; gap: 6px; max-width: 62%; align-items: flex-end; }
.ai-presenter__bubble { font-size: 12px; padding: 5px 10px; border-radius: 12px; color: #e8ecf6;
  background: rgba(10,19,48,0.82); border: 1px solid #23304f; animation: aiRise .3s ease-out; }
.ai-presenter__bubble.me { background: rgba(37,99,235,0.75); border-color: #3b82f6; }
.ai-presenter__mute { position: absolute; top: 44px; right: 10px; z-index: 3; border: 0;
  background: rgba(0,0,0,0.45); color: #fff; border-radius: 999px; width: 34px; height: 34px; cursor: pointer; font-size: 16px; }
.ai-presenter__caption { background: #0a1330; color: #e8ecf6; padding: 8px 14px; min-height: 20px;
  font-size: 14px; line-height: 1.4; border-top: 1px solid #23304f; }
@keyframes aiBob { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
@keyframes aiTalk { 0%,100% { transform: translateY(0) scale(1); } 50% { transform: translateY(-4px) scale(1.02); } }
@keyframes aiGlow { 0%,100% { transform: scale(1); opacity: .55; } 50% { transform: scale(1.12); opacity: .95; } }
@keyframes aiBlink { 0% { opacity: 1; } 50% { opacity: .2; } 100% { opacity: 1; } }
@keyframes aiBars { 0%,100% { height: 6px; } 50% { height: 24px; } }
@keyframes aiRise { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
@media (prefers-reduced-motion: reduce) {
  .ai-presenter__avatar, .ai-presenter__glow, .ai-presenter__bars span, .ai-presenter__dot { animation: none !important; }
}
`;
