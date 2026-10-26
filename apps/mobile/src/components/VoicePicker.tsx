import { useEffect, useMemo, useState } from "react";
import { StyleSheet, TextInput, View } from "react-native";

import type { VoiceGroup } from "../api";
import {
  DEFAULT_VOICE_ID, defaultCloneVoice, explicitEdgeVoice, getSelectedVoice, loadCloneVoices, salaneVoiceLabel, setExplicitEdgeVoice,
  setSelectedVoice, type CloneVoice,
} from "../cloneVoice";
import { LANGUAGES, useT, type LocaleCode } from "../i18n";
import { applyVoicePrefsToTts, loadVoiceCatalog, voicePrefsFromSettings } from "../narrationTts";
import { getSettings, setSettings } from "../storage";
import { theme } from "../theme";
import { AUTO_PREFIX, CUSTOM_PREFIX, buildVoiceGroups, filterVoiceGroups, flattenVoiceGroups, selectedVoiceKey } from "../voicePicker";
import { languageForGroup, languageForVoice, type VoiceChoice } from "../voiceLanguage";
import { loadVoiceAgentChoice, saveVoiceAgentChoice, subscribeVoiceAgent, type VoiceAgentChoice } from "../voiceAgentPref";
import DropdownListSelector from "./DropdownListSelector";
import VoiceAgentToggle from "./VoiceAgentToggle";

const LOCALES: readonly string[] = LANGUAGES.map((l) => l.code);

/** Each language's own name from the app's language list ("English" for the whole English group, not "English (US)"). */
const NATIVE_NAMES: Record<string, string> = {
  ...Object.fromEntries(LANGUAGES.filter((l) => !l.code.includes("-")).map((l) => [l.code, l.native])),
  en: "English",
};

/**
 * The ONE voice-and-language control of the app (home footer and Settings), matching the site's profile menu: the Salane or xAI live voice,
 * then a searchable list of voices grouped by language. Picking a voice sets the app language to the voice's language, so there is no
 * separate language setting. Sage opens the English group. Every other row is a named voice labeled with its language.
 */
export default function VoicePicker() {
  const { t, locale, setLocale } = useT();
  const [catalog, setCatalog] = useState<VoiceGroup[]>([]);
  const [voiceId, setVoiceId] = useState("");
  const [explicit, setExplicit] = useState(false);   // an edge voice picked on purpose, not one the app wrote to follow the language
  const [clones, setClones] = useState<CloneVoice[]>([]);
  const [customChoice, setCustomChoice] = useState(DEFAULT_VOICE_ID);
  const [agent, setAgent] = useState<VoiceAgentChoice>("sala");
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let alive = true;
    void (async () => {
      const s = await getSettings();
      if (!alive) return;
      setVoiceId(s.voiceId || "");
      setExplicit(Boolean(await explicitEdgeVoice()));
      applyVoicePrefsToTts(voicePrefsFromSettings(s));
      const groups = await loadVoiceCatalog();
      if (alive) setCatalog(groups);
    })();
    void loadVoiceAgentChoice().then((next) => { if (alive) setAgent(next); });
    const unsubscribe = subscribeVoiceAgent((next) => { if (alive) setAgent(next); });
    return () => { alive = false; unsubscribe(); };
  }, []);

  // Company and designed voices are listed under the language they speak (their primary_lang), whatever language the app is in.
  useEffect(() => {
    let alive = true;
    void (async () => {
      const voices = await loadCloneVoices();
      const saved = await getSelectedVoice();
      if (!alive) return;
      setClones(voices);
      setCustomChoice(saved);
    })();
    return () => { alive = false; };
  }, []);

  const defaultVoice = defaultCloneVoice(clones);
  const groups = useMemo(() => buildVoiceGroups({
    groups: catalog, clones, savedVoiceId: voiceId, salaneLabel: salaneVoiceLabel(clones), hasDefault: Boolean(defaultVoice), nativeNames: NATIVE_NAMES,
  }), [catalog, clones, voiceId, defaultVoice]);
  const cloneListed = clones.some((v) => v.active && v.id === customChoice && v.id !== defaultVoice?.id);
  const selectedKey = selectedVoiceKey({
    cloneId: customChoice === DEFAULT_VOICE_ID ? "" : customChoice, cloneListed, savedVoiceId: explicit ? voiceId : "", locale, groups,
  });
  const options = useMemo(() => flattenVoiceGroups(filterVoiceGroups(groups, query, selectedKey)), [groups, query, selectedKey]);
  const selected = groups.flatMap((g) => g.options).find((o) => o.key === selectedKey) ?? groups[0].options[0];

  /** The voice decides the language: switch the app to it unless it already is that language. */
  function followLanguage(choice: VoiceChoice) {
    const next = languageForVoice(choice, { current: locale, supported: LOCALES, clones });
    if (next && next !== locale) setLocale(next as LocaleCode);
  }

  async function choose(key: string) {
    setOpen(false);
    setQuery("");
    if (key.startsWith(CUSTOM_PREFIX)) {
      const id = key.slice(CUSTOM_PREFIX.length);
      setCustomChoice(id);
      await setSelectedVoice(id);   // same stored choice as the demo narrator
      followLanguage({ type: "clone", id });
      return;
    }
    if (key.startsWith(AUTO_PREFIX)) {
      const group = key.slice(AUTO_PREFIX.length);
      setCustomChoice(DEFAULT_VOICE_ID);
      await setSelectedVoice(DEFAULT_VOICE_ID);   // the Salane Voice on purpose: the published default (Sage) narrates English lines
      await setExplicitEdgeVoice(false);
      setExplicit(false);
      setVoiceId("");
      applyVoicePrefsToTts(voicePrefsFromSettings(await setSettings({ voiceId: "" })));
      const next = languageForGroup(group, locale, LOCALES);
      if (next && next !== locale) setLocale(next as LocaleCode);
      return;
    }
    setCustomChoice(DEFAULT_VOICE_ID);
    await setSelectedVoice(DEFAULT_VOICE_ID);
    await setExplicitEdgeVoice(true);
    setExplicit(true);
    setVoiceId(key);
    // The (F)/(M) in each option is the gender now, so keep the stored gender in step with the voice picked.
    const picked = catalog.flatMap((g) => g.voices).find((v) => v.id === key);
    const gender = picked?.gender === "male" || picked?.gender === "female" ? picked.gender : undefined;
    const next = await setSettings(gender ? { voiceId: key, voiceGender: gender } : { voiceId: key });
    applyVoicePrefsToTts(voicePrefsFromSettings(next));
    followLanguage({ type: "edge", id: picked?.edge_voice || picked?.locale || key });
  }

  return (
    <View style={styles.wrap}>
      <VoiceAgentToggle value={agent} onChange={(next) => { setAgent(next); void saveVoiceAgentChoice(next); }} />
      {open ? (
        <TextInput
          testID="voice-search"
          value={query}
          onChangeText={setQuery}
          placeholder={t("voice.search")}
          placeholderTextColor={theme.colors.muted}
          accessibilityLabel={t("voice.search")}
          autoCorrect={false}
          autoCapitalize="none"
          style={styles.search}
        />
      ) : null}
      <DropdownListSelector
        title={t("settings.sectionVoice")}
        selectedLabel={selected.label}
        selectedKey={selected.key}
        options={options}
        open={open}
        onToggle={() => { setOpen((v) => !v); setQuery(""); }}
        onSelect={(key) => { void choose(key); }}
        maxHeight={320}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 10 },
  search: {
    color: theme.colors.text, borderColor: theme.colors.border, borderWidth: 1, borderRadius: 10,
    paddingHorizontal: 12, paddingVertical: 8, fontSize: 14,
  },
});
