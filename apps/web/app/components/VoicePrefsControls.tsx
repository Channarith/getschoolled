"use client";

import { useEffect, useState } from "react";

import { getTtsVoices, type VoiceGroup } from "../lib/api";
import { useT } from "../lib/i18n";
import { applyVoicePrefsToTts } from "../lib/narrationTts";
import { getVoicePrefs, setVoicePrefs, type VoiceGenderPref } from "../lib/voicePrefs";
import { setServerVoice } from "../lib/tts";

/** Voice gender + accent picker for the profile menu (single source of truth). */
export default function VoicePrefsControls() {
  const { t } = useT();
  const [voiceGroups, setVoiceGroups] = useState<VoiceGroup[]>([]);
  const [voiceId, setVoiceId] = useState("");
  const [gender, setGender] = useState<VoiceGenderPref>("any");

  useEffect(() => {
    const prefs = getVoicePrefs();
    setVoiceId(prefs.voiceId);
    setGender(prefs.voiceGender);
    applyVoicePrefsToTts(prefs);
    getTtsVoices()
      .then((r) => setVoiceGroups(r.groups))
      .catch(() => setVoiceGroups([]));
  }, []);

  function chooseGender(pref: VoiceGenderPref) {
    setGender(pref);
    let nextVoice = voiceId;
    if (pref !== "any") {
      const all = voiceGroups.flatMap((g) => g.voices);
      const current = all.find((x) => x.id === voiceId);
      if (!current || current.gender !== pref) {
        const match = all.find((v) => v.gender === pref);
        if (match) {
          nextVoice = match.id;
          setVoiceId(match.id);
          setServerVoice(match.id);
        }
      }
    }
    const next = setVoicePrefs({ voiceGender: pref, voiceId: nextVoice });
    applyVoicePrefsToTts(next);
  }

  function chooseVoice(id: string) {
    setVoiceId(id);
    setServerVoice(id);
    const next = setVoicePrefs({ voiceId: id });
    applyVoicePrefsToTts(next);
  }

  return (
    <div style={{ display: "grid", gap: 8 }}>
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap", alignItems: "center" }}>
        {(["any", "female", "male"] as const).map((g) => {
          const on = gender === g;
          return (
            <button
              key={g}
              type="button"
              onClick={() => chooseGender(g)}
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
              {g === "any"
                ? t("drive.voiceGenderAny")
                : g === "female"
                  ? t("drive.voiceGenderFemale")
                  : t("drive.voiceGenderMale")}
            </button>
          );
        })}
      </div>
      {voiceGroups.length > 0 && (
        <select
          value={voiceId}
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
          {voiceGroups.map((g) => (
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
    </div>
  );
}
