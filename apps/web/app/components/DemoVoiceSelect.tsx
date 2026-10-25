"use client";

import { useEffect, useState } from "react";

import {
  DEFAULT_VOICE_ID, VOICE_CHOICE_EVENT, defaultCloneVoice, getSelectedVoice, loadCloneVoices, salaneVoiceLabel, setSelectedVoice, type CloneVoice,
} from "../lib/cloneVoice";

/** Picks the narration voice for the demos: the Salane Voice (Sage, the published default) or a consented company voice. Hidden until a voice is published. */
export default function DemoVoiceSelect({ className }: { className?: string }) {
  const [voices, setVoices] = useState<CloneVoice[]>([]);
  const [choice, setChoice] = useState(DEFAULT_VOICE_ID);

  useEffect(() => {
    let alive = true;
    loadCloneVoices().then((v) => {
      if (!alive) return;
      setVoices(v);
      const saved = getSelectedVoice();
      setChoice(v.some((x) => x.id === saved && !x.default) ? saved : DEFAULT_VOICE_ID);
    });
    const sync = () => setChoice(getSelectedVoice());
    window.addEventListener(VOICE_CHOICE_EVENT, sync);
    return () => { alive = false; window.removeEventListener(VOICE_CHOICE_EVENT, sync); };
  }, []);

  if (!voices.length) return null;
  const defaultId = defaultCloneVoice(voices)?.id;
  const others = voices.filter((v) => v.id !== defaultId);   // the default is the first option, not a second copy
  const current = choice === DEFAULT_VOICE_ID ? defaultCloneVoice(voices) : voices.find((v) => v.id === choice);
  return (
    <label className={className ?? "demo-voice-select"} style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 14 }}>
      <span>Narrator voice</span>
      <select
        aria-label="Narrator voice"
        value={choice}
        onChange={(e) => { setChoice(e.target.value); setSelectedVoice(e.target.value); }}
      >
        <option value={DEFAULT_VOICE_ID}>{salaneVoiceLabel(voices)}</option>
        {others.map((v) => <option key={v.id} value={v.id}>{v.label}</option>)}
      </select>
      {current && <small style={{ opacity: 0.75 }}>{current.ai_label}</small>}
    </label>
  );
}
