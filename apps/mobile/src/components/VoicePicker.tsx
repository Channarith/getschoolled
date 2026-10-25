import { useEffect, useMemo, useState } from "react";
import { StyleSheet, View } from "react-native";

import type { VoiceGroup } from "../api";
import { DEFAULT_VOICE_ID, cloneVoiceLanguages, getSelectedVoice, loadCloneVoices, setSelectedVoice } from "../cloneVoice";
import { useT } from "../i18n";
import { applyVoicePrefsToTts, loadVoiceCatalog, voicePrefsFromSettings } from "../narrationTts";
import { getSettings, setSettings } from "../storage";
import { CUSTOM_PREFIX, buildVoiceOptions, clipLangForLocale, customVoiceLabel } from "../voicePicker";
import { loadVoiceAgentChoice, saveVoiceAgentChoice, subscribeVoiceAgent, type VoiceAgentChoice } from "../voiceAgentPref";
import DropdownListSelector from "./DropdownListSelector";
import VoiceAgentToggle from "./VoiceAgentToggle";

/**
 * The one voice control of the app (home footer and Settings), matching the site's profile menu: Salane or xAI live voice, then a single
 * dropdown of Default (auto), the consented custom voices that have clips in the current language, and every catalog voice with its (F)/(M).
 */
export default function VoicePicker() {
  const { t, locale } = useT();
  const [groups, setGroups] = useState<VoiceGroup[]>([]);
  const [voiceId, setVoiceId] = useState("");
  const [custom, setCustom] = useState<{ id: string; label: string }[]>([]);
  const [customChoice, setCustomChoice] = useState(DEFAULT_VOICE_ID);
  const [agent, setAgent] = useState<VoiceAgentChoice>("sala");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let alive = true;
    void (async () => {
      const s = await getSettings();
      if (!alive) return;
      setVoiceId(s.voiceId || "");
      applyVoicePrefsToTts(voicePrefsFromSettings(s));
      const catalog = await loadVoiceCatalog();
      if (alive) setGroups(catalog);
    })();
    void loadVoiceAgentChoice().then((next) => { if (alive) setAgent(next); });
    const unsubscribe = subscribeVoiceAgent((next) => { if (alive) setAgent(next); });
    return () => { alive = false; unsubscribe(); };
  }, []);

  // Consented company voices: listed only when the voice is switched on AND has clips in the language the app is in.
  useEffect(() => {
    let alive = true;
    const lang = clipLangForLocale(locale);
    void (async () => {
      const rows: { id: string; label: string }[] = [];
      for (const v of await loadCloneVoices()) {
        if ((await cloneVoiceLanguages(v.id)).includes(lang)) rows.push({ id: v.id, label: customVoiceLabel(v.label, lang, locale) });
      }
      const saved = await getSelectedVoice();
      if (!alive) return;
      setCustom(rows);
      setCustomChoice(rows.some((r) => r.id === saved) ? saved : DEFAULT_VOICE_ID);
    })();
    return () => { alive = false; };
  }, [locale]);

  const options = useMemo(() => buildVoiceOptions({
    defaultLabel: t("voice.defaultAuto"), customHeader: t("voice.customGroup"), custom, groups, savedVoiceId: voiceId,
  }), [t, custom, groups, voiceId]);
  const selectedKey = custom.some((c) => c.id === customChoice) ? `${CUSTOM_PREFIX}${customChoice}` : voiceId;
  const selected = options.find((o) => !o.header && o.key === selectedKey) ?? options[0];

  async function choose(key: string) {
    setOpen(false);
    if (key.startsWith(CUSTOM_PREFIX)) {
      const id = key.slice(CUSTOM_PREFIX.length);
      setCustomChoice(id);
      await setSelectedVoice(id);   // same stored choice as the demo narrator
      return;
    }
    setCustomChoice(DEFAULT_VOICE_ID);
    await setSelectedVoice(DEFAULT_VOICE_ID);
    setVoiceId(key);
    // The (F)/(M) in each option is the gender now, so keep the stored gender in step with the voice picked.
    const picked = groups.flatMap((g) => g.voices).find((v) => v.id === key);
    const gender = picked?.gender === "male" || picked?.gender === "female" ? picked.gender : undefined;
    const next = await setSettings(gender ? { voiceId: key, voiceGender: gender } : { voiceId: key });
    applyVoicePrefsToTts(voicePrefsFromSettings(next));
  }

  return (
    <View style={styles.wrap}>
      <VoiceAgentToggle value={agent} onChange={(next) => { setAgent(next); void saveVoiceAgentChoice(next); }} />
      <DropdownListSelector
        title={t("settings.sectionVoice")}
        selectedLabel={selected.label}
        selectedKey={selected.key}
        options={options}
        open={open}
        onToggle={() => setOpen((v) => !v)}
        onSelect={(key) => { void choose(key); }}
        maxHeight={320}
      />
    </View>
  );
}

const styles = StyleSheet.create({ wrap: { gap: 10 } });
