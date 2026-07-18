import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";

import {
  changePassword, createStudent, getPortfolio, listStudents,
  type Portfolio, type StudentProfile,
} from "../api";
import { useAuth } from "../auth/AuthContext";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { useAndroidBackTo } from "../hooks/useAndroidBack";
import { useT } from "../i18n";
import { getSettings, setSettings } from "../storage";
import { theme } from "../theme";

export default function AccountScreen({
  onBack, onOpenSecurity, onOpenBilling,
}: {
  onBack: () => void;
  onOpenSecurity: () => void;
  onOpenBilling: () => void;
}) {
  const { t } = useT();
  useAndroidBackTo(onBack);
  const { account, refreshAccount } = useAuth();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [students, setStudents] = useState<StudentProfile[]>([]);
  const [activeStudentId, setActiveStudentId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [curPw, setCurPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [newLearner, setNewLearner] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      const [p, s, settings] = await Promise.all([
        getPortfolio(), listStudents(), getSettings(),
      ]);
      setPortfolio(p);
      setStudents(s.students);
      setActiveStudentId(settings.studentId);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function switchStudent(id: string) {
    await setSettings({ studentId: id });
    setActiveStudentId(id);
  }

  async function addLearner() {
    const name = newLearner.trim();
    if (!name) return;
    setBusy(true);
    try {
      const s = await createStudent(name);
      setStudents((prev) => [...prev, s]);
      setNewLearner("");
      await switchStudent(s.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function updatePassword() {
    setBusy(true);
    setError("");
    try {
      await changePassword(curPw, newPw);
      setCurPw("");
      setNewPw("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScrollView style={styles.bg} contentContainerStyle={styles.scroll}>
      <PrimaryButton label={t("account.back")} onPress={onBack} variant="ghost" />
      <Text style={styles.title}>{t("account.title")}</Text>
      {loading ? <ActivityIndicator color={theme.colors.netflix} /> : null}
      {error ? <Text style={styles.err}>{error}</Text> : null}
      <GlassPanel style={styles.card}>
        <Text style={styles.label}>{account?.display_name}</Text>
        <Text style={styles.meta}>{account?.email} · {account?.tier}</Text>
        {portfolio ? (
          <Text style={styles.meta}>{t("account.points", { n: portfolio.points_balance })}</Text>
        ) : null}
        <PrimaryButton label={t("account.security")} onPress={onOpenSecurity} variant="brand" />
        <PrimaryButton label={t("account.billing")} onPress={onOpenBilling} variant="ghost" />
      </GlassPanel>
      <Text style={styles.section}>{t("account.learners")}</Text>
      {students.map((s) => (
        <PrimaryButton
          key={s.id}
          label={`${s.display_name}${s.id === activeStudentId ? " ✓" : ""}`}
          onPress={() => void switchStudent(s.id)}
          variant={s.id === activeStudentId ? "netflix" : "ghost"}
        />
      ))}
      <View style={styles.row}>
        <TextInput
          style={styles.input}
          placeholder={t("account.newLearner")}
          placeholderTextColor={theme.colors.muted}
          value={newLearner}
          onChangeText={setNewLearner}
        />
        <PrimaryButton label={t("account.add")} onPress={() => void addLearner()} loading={busy} variant="brand" />
      </View>
      <Text style={styles.section}>{t("account.password")}</Text>
      <GlassPanel style={styles.card}>
        <TextInput style={styles.input} secureTextEntry placeholder={t("account.currentPw")}
          placeholderTextColor={theme.colors.muted} value={curPw} onChangeText={setCurPw} />
        <TextInput style={styles.input} secureTextEntry placeholder={t("account.newPw")}
          placeholderTextColor={theme.colors.muted} value={newPw} onChangeText={setNewPw} />
        <PrimaryButton label={t("account.changePw")} onPress={() => void updatePassword()}
          loading={busy} variant="netflix" />
      </GlassPanel>
      <PrimaryButton label={t("account.refresh")} onPress={() => { void refreshAccount(); void load(); }} variant="ghost" />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  bg: { flex: 1 },
  scroll: { paddingHorizontal: theme.spacing.screenX, paddingTop: 56, paddingBottom: 32, gap: 10 },
  title: { color: theme.colors.text, fontSize: 26, fontWeight: "800" },
  section: { color: theme.colors.muted, fontSize: 12, fontWeight: "800", letterSpacing: 0.8, marginTop: 8 },
  card: { gap: 10 },
  label: { color: theme.colors.text, fontSize: 18, fontWeight: "800" },
  meta: { color: theme.colors.muted, fontSize: 13 },
  row: { gap: 8 },
  input: {
    borderWidth: 1, borderColor: theme.colors.border, borderRadius: 10,
    padding: 12, color: theme.colors.text, backgroundColor: "rgba(0,0,0,0.2)",
  },
  err: { color: theme.colors.netflix, fontSize: 13 },
});
