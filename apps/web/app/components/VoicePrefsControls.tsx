"use client";

import { useEffect, useState } from "react";

import { getTtsVoices, type VoiceGroup } from "../lib/api";
import {
  DEFAULT_VOICE_ID, VOICE_CHOICE_EVENT, cloneVoiceLanguages, getSelectedVoice, loadCloneVoices, setSelectedVoice,
} from "../lib/cloneVoice";
import { CUSTOM_PREFIX, clipLangForLocale, customVoiceLabel, distinctVoiceGroups } from "../lib/voicePicker";
import { useT } from "../lib/i18n";
import { applyVoicePrefsToTts } from "../lib/narrationTts";
import {
  getLiveVoiceEngine,
  setLiveVoiceEngine,
  type LiveVoiceEngine,
} from "../lib/liveVoiceEngine";
import { getVoicePrefs, setVoicePrefs, type VoiceGenderPref } from "../lib/voicePrefs";
import { setServerTone, setServerVoice } from "../lib/tts";
import { MIX_TONES, NEUTRAL_TONE, TONES, TONE_BLOCKED_TIP, TONE_EVENT, getTone, setTone, toneBlockedForVoice } from "../lib/voiceTone";

/** Voice gender + accent picker for the profile menu (single source of truth). */
export default function VoicePrefsControls() {
  const { t, locale } = useT();
  const [voiceGroups, setVoiceGroups] = useState<VoiceGroup[]>([]);
  const [voiceId, setVoiceId] = useState("");
  const [customVoices, setCustomVoices] = useState<{ id: string; label: string }[]>([]);
  const [customChoice, setCustomChoice] = useState(DEFAULT_VOICE_ID);
  const [liveEngine, setLiveEngine] = useState<LiveVoiceEngine>("salane");
  const [tone, setToneState] = useState(NEUTRAL_TONE);
  const [stylizedVoices, setStylizedVoices] = useState<string[]>([]);

  useEffect(() => {
    const sync = () => setToneState(getTone() || NEUTRAL_TONE);
    sync();
    window.addEventListener(TONE_EVENT, sync);
    return () => window.removeEventListener(TONE_EVENT, sync);
  }, []);

  useEffect(() => {
    const prefs = getVoicePrefs();
    setVoiceId(prefs.voiceId);
    setLiveEngine(getLiveVoiceEngine());
    applyVoicePrefsToTts(prefs);
    getTtsVoices()
      .then((r) => setVoiceGroups(r.groups))
      .catch(() => setVoiceGroups([]));
  }, []);

  // Consented company voices: listed only when the voice is switched on AND has clips in the language the site is in.
  useEffect(() => {
    let alive = true;
    const lang = clipLangForLocale(locale);
    loadCloneVoices().then(async (voices) => {
      if (alive) setStylizedVoices(voices.filter((v) => v.stylized === true).map((v) => v.id));
      const rows: { id: string; label: string }[] = [];
      for (const v of voices) {
        if ((await cloneVoiceLanguages(v.id)).includes(lang)) rows.push({ id: v.id, label: customVoiceLabel(v.label, lang, locale) });
      }
      if (alive) setCustomVoices(rows);
    });
    const sync = () => setCustomChoice(getSelectedVoice());
    sync();
    window.addEventListener(VOICE_CHOICE_EVENT, sync);
    return () => { alive = false; window.removeEventListener(VOICE_CHOICE_EVENT, sync); };
  }, [locale]);

  function chooseVoice(id: string) {
    if (id.startsWith(CUSTOM_PREFIX)) {
      setSelectedVoice(id.slice(CUSTOM_PREFIX.length));   // same stored choice as the demo narrator selector
      return;
    }
    setSelectedVoice(DEFAULT_VOICE_ID);
    setVoiceId(id);
    setServerVoice(id);
    // The (F)/(M) in each option is the gender now, so keep the stored gender in step with the voice picked.
    const picked = voiceGroups.flatMap((g) => g.voices).find((v) => v.id === id);
    const gender: VoiceGenderPref | undefined = picked?.gender === "male" || picked?.gender === "female" ? picked.gender : undefined;
    const next = setVoicePrefs(gender ? { voiceId: id, voiceGender: gender } : { voiceId: id });
    applyVoicePrefsToTts(next);
  }

  const customSelected = customVoices.some((v) => v.id === customChoice);
  const toneBlocked = customSelected && toneBlockedForVoice({ stylized: stylizedVoices.includes(customChoice) });

  function chooseTone(id: string) {
    setToneState(id);
    setTone(id);
    setServerTone(id === NEUTRAL_TONE ? "" : id);
  }

  function chooseLiveEngine(engine: LiveVoiceEngine) {
    setLiveEngine(engine);
    setLiveVoiceEngine(engine);
  }

  return (
    <div style={{ display: "grid", gap: 8 }}>
      <div style={{ display: "grid", gap: 4 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: "var(--muted)" }}>Live voice (Sala)</span>
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          {(["salane", "xai"] as const).map((engine) => {
            const on = liveEngine === engine;
            return (
              <button
                key={engine}
                type="button"
                onClick={() => chooseLiveEngine(engine)}
                aria-pressed={on}
                style={{
                  padding: "5px 10px",
                  borderRadius: 999,
                  fontSize: 12,
                  fontWeight: 700,
                  border: on ? "1px solid var(--accent)" : "1px solid var(--border)",
                  background: on ? "var(--accent)" : "transparent",
                  color: on ? "#fff" : "var(--text)",
                  cursor: "pointer",
                }}
              >
                {engine === "salane" ? "Salane Voice (default)" : "xAI Voice Agent (opt-in)"}
              </button>
            );
          })}
        </div>
        <p className="muted" style={{ margin: 0, fontSize: 11, lineHeight: 1.35 }}>
          xAI is optional and only used when selected. Switch back to Salane Voice if Grok is unavailable.
        </p>
      </div>
      {(voiceGroups.length > 0 || customVoices.length > 0) && (
        <select
          value={customVoices.some((v) => v.id === customChoice) ? `${CUSTOM_PREFIX}${customChoice}` : voiceId}
          onChange={(e) => chooseVoice(e.target.value)}
          aria-label={t("drive.voice")}
          style={{
            width: "100%",
            background: "var(--panel-2)",
            color: "var(--text)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            padding: "6px 8px",
            fontSize: 13,
          }}
        >
          <option value="">{t("drive.voiceDefault")}</option>
          {customVoices.length > 0 && (
            <optgroup label={t("drive.voiceCustomGroup")}>
              {customVoices.map((v) => (
                <option key={v.id} value={`${CUSTOM_PREFIX}${v.id}`}>{v.label}</option>
              ))}
            </optgroup>
          )}
          {distinctVoiceGroups(voiceGroups, voiceId).map((g) => (
            <optgroup key={g.language} label={g.language.toUpperCase()}>
              {g.voices.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.accent} · {v.label}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      )}
      <label style={{ display: "grid", gap: 4 }} title={toneBlocked ? TONE_BLOCKED_TIP : undefined}>
        <span style={{ fontSize: 12, fontWeight: 700, color: "var(--muted)" }}>Tone</span>
        <select
          value={toneBlocked ? NEUTRAL_TONE : tone}
          onChange={(e) => chooseTone(e.target.value)}
          disabled={toneBlocked}
          aria-label="Voice tone"
          aria-disabled={toneBlocked}
          title={toneBlocked ? TONE_BLOCKED_TIP : undefined}
          style={{
            width: "100%",
            background: "var(--panel-2)",
            color: "var(--text)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            padding: "6px 8px",
            fontSize: 13,
            opacity: toneBlocked ? 0.55 : 1,
            cursor: toneBlocked ? "not-allowed" : "pointer",
          }}
        >
          {TONES.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
          <optgroup label="Mix">
            {MIX_TONES.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
          </optgroup>
        </select>
      </label>
    </div>
  );
}
