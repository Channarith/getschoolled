import { useEffect, useState } from "react";
import { ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import {
  confirm2fa, disable2fa, getSecuritySummary, setup2fa,
} from "../api";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { useAndroidBackTo } from "../hooks/useAndroidBack";
import { useT } from "../i18n";
import { theme } from "../theme";

export default function SecurityScreen({ onBack }: { onBack: () => void }) {
  const { t } = useT();
  useAndroidBackTo(onBack);
  const [enabled, setEnabled] = useState(false);
  const [secret, setSecret] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void getSecuritySummary()
      .then((s) => setEnabled(s.totp_enabled))
      .catch(() => {});
  }, []);

  async function startSetup() {
    setBusy(true);
    setError("");
    try {
      const r = await setup2fa();
      setSecret(r.secret);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    setBusy(true);
    setError("");
    try {
      const r = await confirm2fa(code.trim());
      setEnabled(r.enabled);
      setSecret("");
      setCode("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function disable() {
    setBusy(true);
    setError("");
    try {
      const r = await disable2fa(code.trim());
      setEnabled(r.enabled);
      setCode("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScrollView style={styles.bg} contentContainerStyle={styles.scroll}>
      <PrimaryButton label={t("security.back")} onPress={onBack} variant="ghost" />
      <Text style={styles.title}>{t("security.title")}</Text>
      {error ? <Text style={styles.err}>{error}</Text> : null}
      <GlassPanel style={styles.card}>
        <Text style={styles.meta}>
          {enabled ? t("security.enabled") : t("security.disabled")}
        </Text>
        {!enabled && !secret ? (
          <PrimaryButton label={t("security.setup")} onPress={() => void startSetup()} loading={busy} variant="netflix" />
        ) : null}
        {secret ? (
          <>
            <Text style={styles.secret}>{t("security.secret", { secret })}</Text>
            <TextInput style={styles.input} placeholder={t("security.code")}
              placeholderTextColor={theme.colors.muted} value={code} onChangeText={setCode}
              keyboardType="number-pad" />
            <PrimaryButton label={t("security.confirm")} onPress={() => void confirm()} loading={busy} variant="brand" />
          </>
        ) : null}
        {enabled ? (
          <>
            <TextInput style={styles.input} placeholder={t("security.code")}
              placeholderTextColor={theme.colors.muted} value={code} onChangeText={setCode}
              keyboardType="number-pad" />
            <PrimaryButton label={t("security.disable")} onPress={() => void disable()} loading={busy} variant="ghost" />
          </>
        ) : null}
      </GlassPanel>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  bg: { flex: 1 },
  scroll: { paddingHorizontal: theme.spacing.screenX, paddingTop: 56, paddingBottom: 32, gap: 10 },
  title: { color: theme.colors.text, fontSize: 26, fontWeight: "800" },
  card: { gap: 10 },
  meta: { color: theme.colors.text, fontSize: 15, fontWeight: "700" },
  secret: { color: theme.colors.muted, fontSize: 12, fontFamily: "monospace" },
  input: {
    borderWidth: 1, borderColor: theme.colors.border, borderRadius: 10,
    padding: 12, color: theme.colors.text, backgroundColor: "rgba(0,0,0,0.2)",
  },
  err: { color: theme.colors.netflix, fontSize: 13 },
});
