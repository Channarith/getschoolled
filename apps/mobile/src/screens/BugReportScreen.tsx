import { useEffect, useState } from "react";
import {
  Alert, Image, Platform, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";
import * as ImagePicker from "expo-image-picker";

import { getMe, submitBugReport, type BugScreenshotUpload } from "../api";
import { bugReportBase, imageAssetToUpload } from "../bugReport";
import { installClientLog } from "../clientLog";
import { useAndroidBackTo } from "../hooks/useAndroidBack";
import { useT } from "../i18n";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { theme } from "../theme";

const CATEGORIES = [
  { id: "bug", labelKey: "bugReport.catBug" },
  { id: "crash", labelKey: "bugReport.catCrash" },
  { id: "ux", labelKey: "bugReport.catUx" },
  { id: "other", labelKey: "bugReport.catOther" },
] as const;

type Props = {
  screen?: string;
  onBack: () => void;
  initialScreenshot?: BugScreenshotUpload | null;
};

export default function BugReportScreen({
  screen = "settings",
  onBack,
  initialScreenshot = null,
}: Props) {
  const { t } = useT();
  useAndroidBackTo(onBack);
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("bug");
  const [shots, setShots] = useState<BugScreenshotUpload[]>(
    initialScreenshot ? [initialScreenshot] : [],
  );
  const [previewUris, setPreviewUris] = useState<string[]>(
    initialScreenshot
      ? [`data:${initialScreenshot.content_type};base64,${initialScreenshot.data_base64}`]
      : [],
  );
  const [busy, setBusy] = useState(false);
  const [doneId, setDoneId] = useState("");

  useEffect(() => {
    installClientLog();
  }, []);

  async function pickScreenshot() {
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      Alert.alert(t("bugReport.permTitle"), t("bugReport.permBody"));
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.75,
      base64: true,
      allowsMultipleSelection: false,
    });
    if (result.canceled || !result.assets?.[0]) return;
    const asset = result.assets[0];
    const upload = imageAssetToUpload(asset);
    if (!upload) {
      Alert.alert(t("bugReport.attachFail"));
      return;
    }
    setShots((prev) => [...prev, upload].slice(0, 3));
    if (asset.uri) setPreviewUris((prev) => [...prev, asset.uri!].slice(0, 3));
  }

  async function onSubmit() {
    if (!description.trim()) {
      Alert.alert(t("bugReport.needDesc"));
      return;
    }
    setBusy(true);
    try {
      let email = "";
      let userId = "";
      try {
        const me = await getMe();
        email = me.email || "";
        userId = me.id || "";
      } catch {
        /* optional */
      }
      const base = bugReportBase(screen, { tab: screen });
      const res = await submitBugReport({
        ...base,
        description: description.trim(),
        category,
        email,
        user_id: userId,
        screenshots: shots,
      });
      setDoneId(res.id);
    } catch (e) {
      Alert.alert(t("bugReport.failTitle"), (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (doneId) {
    return (
      <ScrollView style={styles.bg} contentContainerStyle={styles.pad}>
        <GlassPanel>
          <Text style={styles.title}>{t("bugReport.thanksTitle")}</Text>
          <Text style={styles.sub}>{t("bugReport.thanksBody", { id: doneId })}</Text>
          <PrimaryButton label={t("bugReport.back")} onPress={onBack} variant="netflix" />
        </GlassPanel>
      </ScrollView>
    );
  }

  return (
    <ScrollView style={styles.bg} contentContainerStyle={styles.pad}>
      <Text style={styles.title}>{t("bugReport.title")}</Text>
      <Text style={styles.sub}>{t("bugReport.sub")}</Text>
      {initialScreenshot ? (
        <Text style={styles.autoCapture}>{t("bugReport.autoCaptured")}</Text>
      ) : null}

      <GlassPanel style={{ marginTop: 12 }}>
        <Text style={styles.label}>{t("bugReport.what")}</Text>
        <TextInput
          value={description}
          onChangeText={setDescription}
          multiline
          placeholder={t("bugReport.placeholder")}
          placeholderTextColor={theme.colors.muted}
          style={styles.input}
        />

        <Text style={[styles.label, { marginTop: 12 }]}>{t("bugReport.category")}</Text>
        <View style={styles.chips}>
          {CATEGORIES.map((c) => (
            <PrimaryButton
              key={c.id}
              label={t(c.labelKey)}
              onPress={() => setCategory(c.id)}
              variant={category === c.id ? "netflix" : "ghost"}
            />
          ))}
        </View>

        <View style={{ marginTop: 14, gap: 8 }}>
          <PrimaryButton
            label={t("bugReport.attach")}
            onPress={() => void pickScreenshot()}
            variant="brand"
          />
          <Text style={styles.hint}>
            {t("bugReport.attachHint", { count: String(shots.length) })}
          </Text>
        </View>

        {previewUris.length > 0 ? (
          <ScrollView horizontal style={{ marginTop: 10 }} showsHorizontalScrollIndicator={false}>
            {previewUris.map((uri) => (
              <Image key={uri} source={{ uri }} style={styles.thumb} />
            ))}
          </ScrollView>
        ) : null}

        <View style={{ marginTop: 16, gap: 10 }}>
          <PrimaryButton
            label={busy ? t("bugReport.sending") : t("bugReport.send")}
            loading={busy}
            onPress={() => void onSubmit()}
            variant="netflix"
          />
          <PrimaryButton label={t("bugReport.cancel")} onPress={onBack} variant="ghost" />
        </View>
      </GlassPanel>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  bg: { flex: 1, backgroundColor: theme.colors.bg },
  pad: { paddingTop: Platform.OS === "ios" ? 56 : 24, paddingHorizontal: 16, paddingBottom: 32 },
  title: { color: theme.colors.text, fontSize: 22, fontWeight: "800" },
  sub: { color: theme.colors.muted, fontSize: 14, marginTop: 6, lineHeight: 20 },
  label: { color: theme.colors.text, fontWeight: "700", fontSize: 14 },
  input: {
    marginTop: 8, minHeight: 110, borderRadius: 10, borderWidth: 1,
    borderColor: theme.colors.border, padding: 12, color: theme.colors.text,
    textAlignVertical: "top",
  },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 8 },
  hint: { color: theme.colors.muted, fontSize: 12 },
  autoCapture: { color: theme.colors.success, fontSize: 12, marginTop: 7, fontWeight: "600" },
  thumb: { width: 88, height: 88, borderRadius: 8, marginRight: 8 },
});
