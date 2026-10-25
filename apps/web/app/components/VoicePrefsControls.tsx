"use client";

import { useEffect, useMemo, useState } from "react";

import { getTtsVoices, type VoiceGroup } from "../lib/api";
import {
  DEFAULT_VOICE_ID, VOICE_CHOICE_EVENT, defaultCloneVoice, explicitEdgeVoice, getSelectedVoice, loadCloneVoices, salaneVoiceLabel, setExplicitEdgeVoice, setSelectedVoice, type CloneVoice,
} from "../lib/cloneVoice";
import { AUTO_PREFIX, CUSTOM_PREFIX, buildVoiceOptions, filterVoiceOptions, selectedVoiceValue } from "../lib/voicePicker";
import { languageForGroup, languageForVoice, type VoiceChoice } from "../lib/voiceLanguage";
import { LANGUAGE_LIST, LOCALES } from "../lib/i18n-strings";
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

/** Each language's own name from the app's language list ("English" for the whole English group, not "English (US)"). */
const NATIVE_NAMES: Record<string, string> = {
  ...Object.fromEntries(LANGUAGE_LIST.filter((l) => !l.code.includes("-")).map((l) => [l.code, l.native])),
  en: "English",
};

/**
 * The ONE voice-and-language control of the profile menu. Voices are listed by language (each language's own name as the header, with a
 * search box); picking a voice sets the app language to the voice's language, so there is no separate language setting. "Salane Voice
 * (Sage)" opens the English group while the designed default is published.
 */
export default function VoicePrefsControls() {
  const { t, locale, setLocale } = useT();
  const [voiceGroups, setVoiceGroups] = useState<VoiceGroup[]>([]);
  const [voiceId, setVoiceId] = useState("");
  const [clones, setClones] = useState<CloneVoice[]>([]);
  const [customChoice, setCustomChoice] = useState(DEFAULT_VOICE_ID);
  const [liveEngine, setLiveEngine] = useState<LiveVoiceEngine>("salane");
  const [tone, setToneState] = useState(NEUTRAL_TONE);
  const [query, setQuery] = useState("");
  const [explicit, setExplicit] = useState(false);   // an edge voice picked on purpose (not one the app wrote to follow the language)

  useEffect(() => {
    const sync = () => setToneState(getTone() || NEUTRAL_TONE);
    sync();
    window.addEventListener(TONE_EVENT, sync);
    return () => window.removeEventListener(TONE_EVENT, sync);
  }, []);

  useEffect(() => {
    const prefs = getVoicePrefs();
    setVoiceId(prefs.voiceId);
    setExplicit(Boolean(explicitEdgeVoice()));
    setLiveEngine(getLiveVoiceEngine());
    applyVoicePrefsToTts(prefs);
    getTtsVoices()
      .then((r) => setVoiceGroups(r.groups))
      .catch(() => setVoiceGroups([]));
  }, []);

  // Company and designed voices are listed under the language they speak (their primary_lang), whatever the site language is.
  useEffect(() => {
    let alive = true;
    loadCloneVoices().then((voices) => { if (alive) setClones(voices); });
    const sync = () => setCustomChoice(getSelectedVoice());
    sync();
    window.addEventListener(VOICE_CHOICE_EVENT, sync);
    return () => { alive = false; window.removeEventListener(VOICE_CHOICE_EVENT, sync); };
  }, []);

  const defaultVoice = defaultCloneVoice(clones);
  const groups = useMemo(
    () => buildVoiceOptions({
      groups: voiceGroups, clones, savedVoiceId: voiceId, salaneLabel: salaneVoiceLabel(clones), hasDefault: Boolean(defaultVoice),
      nativeNames: NATIVE_NAMES,
    }),
    [voiceGroups, clones, voiceId, defaultVoice],
  );
  const cloneListed = clones.some((v) => v.active && v.id === customChoice && v.id !== defaultVoice?.id);
  const value = selectedVoiceValue({ cloneId: customChoice === DEFAULT_VOICE_ID ? "" : customChoice, cloneListed, savedVoiceId: explicit ? voiceId : "", locale, groups });
  const shown = useMemo(() => filterVoiceOptions(groups, query, value), [groups, query, value]);

  /** The voice decides the language: switch the app to it (menus, lesson text, direction) unless it is already that language. */
  function followLanguage(choice: VoiceChoice) {
    const next = languageForVoice(choice, { current: locale, supported: LOCALES, clones });
    if (next && next !== locale) setLocale(next as typeof locale);
  }

  function chooseVoice(picked: string) {
    if (picked.startsWith(CUSTOM_PREFIX)) {
      const id = picked.slice(CUSTOM_PREFIX.length);
      setSelectedVoice(id);   // same stored choice as the demo narrator selector
      followLanguage({ type: "clone", id });
      return;
    }
    if (picked.startsWith(AUTO_PREFIX)) {
      const key = picked.slice(AUTO_PREFIX.length);
      setSelectedVoice(DEFAULT_VOICE_ID);   // the Salane Voice on purpose: the published default (Sage) narrates English lines
      setExplicitEdgeVoice(false);
      setExplicit(false);
      setVoiceId("");
      setServerVoice("");
      applyVoicePrefsToTts(setVoicePrefs({ voiceId: "" }));
      const next = languageForGroup(key, locale, LOCALES);
      if (next && next !== locale) setLocale(next as typeof locale);
      return;
    }
    setSelectedVoice(DEFAULT_VOICE_ID);
    setExplicitEdgeVoice(true);
    setExplicit(true);
    setVoiceId(picked);
    setServerVoice(picked);
    // The (F)/(M) in each option is the gender now, so keep the stored gender in step with the voice picked.
    const pickedVoice = voiceGroups.flatMap((g) => g.voices).find((v) => v.id === picked);
    const gender: VoiceGenderPref | undefined = pickedVoice?.gender === "male" || pickedVoice?.gender === "female" ? pickedVoice.gender : undefined;
    const next = setVoicePrefs(gender ? { voiceId: picked, voiceGender: gender } : { voiceId: picked });
    applyVoicePrefsToTts(next);
    followLanguage({ type: "edge", id: pickedVoice?.edge_voice || pickedVoice?.locale || picked });
  }

  const customSelected = cloneListed;
  const toneBlocked = customSelected && toneBlockedForVoice({ stylized: clones.find((v) => v.id === customChoice)?.stylized === true });

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
      </div>
      <div style={{ display: "grid", gap: 4 }}>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("voice.search")}
          aria-label={t("voice.search")}
          style={{
            width: "100%", background: "var(--panel-2)", color: "var(--text)", border: "1px solid var(--border)",
            borderRadius: 6, padding: "6px 8px", fontSize: 13, boxSizing: "border-box",
          }}
        />
        <select
          value={value}
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
          {shown.map((g) => (
            <optgroup key={g.key} label={g.label}>
              {g.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </optgroup>
          ))}
        </select>
      </div>
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
