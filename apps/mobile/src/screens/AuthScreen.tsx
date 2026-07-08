import { Ionicons } from "@expo/vector-icons";
import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView,
  StyleSheet, Text, TextInput, View,
} from "react-native";

import { CURRICULUM_URL, IDENTITY_URL, checkServiceReachable } from "../api";
import { useAuth } from "../auth/AuthContext";
import AnimatedPressable from "../components/AnimatedPressable";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { DEPLOY_MODE, QA_TEST_ACCOUNTS } from "../config";
import { LANGUAGES, languageInfo, useT } from "../i18n";
import { theme } from "../theme";
import { APP_VERSION } from "../version";

export default function AuthScreen() {
  const { t, locale, setLocale } = useT();
  const { signIn, signUp } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [identityUp, setIdentityUp] = useState<boolean | null>(null);

  const probeIdentity = useCallback(async () => {
    const up = await checkServiceReachable(IDENTITY_URL);
    setIdentityUp(up);
    return up;
  }, []);

  const backendDownMessage = useCallback((url: string) => {
    const host = url.replace("http://", "");
    return DEPLOY_MODE === "local"
      ? t("auth.backendDownLocal", { url: host })
      : t("auth.backendDownCloud", { url: host });
  }, [t]);

  useEffect(() => { void probeIdentity(); }, [probeIdentity]);

  async function onSubmit() {
    setBusy(true);
    setError("");
    try {
      const up = await probeIdentity();
      if (!up) {
        setError(backendDownMessage(IDENTITY_URL));
        return;
      }
      if (mode === "login") {
        await signIn(email.trim(), password);
      } else {
        await signUp(
          email.trim(),
          password,
          displayName.trim() || email.split("@")[0],
        );
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  function fillQa(qaEmail: string, qaPassword: string) {
    setEmail(qaEmail);
    setPassword(qaPassword);
    setMode("login");
  }

  const current = languageInfo(locale);

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView
        contentContainerStyle={styles.scroll}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.header}>
          <Text style={styles.brand}>Salareen</Text>
          <Text style={styles.title}>{t("auth.welcomeTitle")}</Text>
          <Text style={styles.sub}>{t("auth.welcomeSubtitle")}</Text>
        </View>

        <GlassPanel style={styles.card}>
          {mode === "signup" ? (
            <TextInput
              style={styles.input}
              placeholder={t("auth.displayName")}
              placeholderTextColor={theme.colors.muted}
              value={displayName}
              onChangeText={setDisplayName}
            />
          ) : null}
          <TextInput
            style={styles.input}
            placeholder={t("auth.email")}
            placeholderTextColor={theme.colors.muted}
            autoCapitalize="none"
            keyboardType="email-address"
            autoComplete="email"
            value={email}
            onChangeText={setEmail}
          />
          <View style={styles.passwordRow}>
            <TextInput
              style={styles.passwordInput}
              placeholder={t("auth.password")}
              placeholderTextColor={theme.colors.muted}
              secureTextEntry={!showPassword}
              autoCapitalize="none"
              autoComplete={mode === "login" ? "password" : "new-password"}
              value={password}
              onChangeText={setPassword}
              onSubmitEditing={() => void onSubmit()}
            />
            <Pressable
              onPress={() => setShowPassword((v) => !v)}
              style={styles.eyeButton}
              hitSlop={10}
              accessibilityRole="button"
              accessibilityLabel={t(showPassword ? "auth.hidePassword" : "auth.showPassword")}
            >
              <Ionicons
                name={showPassword ? "eye-off-outline" : "eye-outline"}
                size={22}
                color={theme.colors.muted}
              />
            </Pressable>
          </View>
          {error ? <Text style={styles.error}>{error}</Text> : null}
          <PrimaryButton
            label={mode === "login" ? t("auth.signIn") : t("auth.signUp")}
            onPress={() => void onSubmit()}
            loading={busy}
            disabled={busy}
            variant="netflix"
          />
          <AnimatedPressable onPress={() => setMode(mode === "login" ? "signup" : "login")}>
            <Text style={styles.link}>
              {mode === "login" ? t("auth.createAccount") : t("auth.haveAccount")}
            </Text>
          </AnimatedPressable>
          {__DEV__ ? (
            <View style={{ marginTop: 16 }}>
              <Text style={styles.hint}>{t("auth.qaHint")}</Text>
              <View style={styles.qaRow}>
                {QA_TEST_ACCOUNTS.map((qa) => (
                  <AnimatedPressable
                    key={qa.email}
                    onPress={() => fillQa(qa.email, qa.password)}
                    style={styles.qaChip}
                  >
                    <Text style={styles.qaText}>{t("auth.useQa", { label: qa.label })}</Text>
                  </AnimatedPressable>
                ))}
              </View>
            </View>
          ) : null}
        </GlassPanel>

        <View style={styles.langBlock}>
          <Text style={styles.langLabel}>{t("settings.language")}</Text>
          <Text style={styles.langCurrent}>{current.flag}  {current.native}</Text>
          <View style={styles.langRow}>
            {LANGUAGES.map((lang) => {
              const selected = lang.code === locale;
              return (
                <AnimatedPressable
                  key={lang.code}
                  onPress={() => setLocale(lang.code)}
                  style={[styles.langChip, selected && styles.langChipOn]}
                >
                  <Text style={[styles.langChipText, selected && styles.langChipTextOn]}>
                    {lang.flag} {lang.native}
                  </Text>
                </AnimatedPressable>
              );
            })}
          </View>
        </View>

        <Text style={[
          styles.backend,
          identityUp === false && styles.backendDown,
          identityUp === true && styles.backendUp,
        ]}>
          {identityUp === false
            ? backendDownMessage(IDENTITY_URL)
            : identityUp === true
              ? `${t("auth.backendUp")} · ${t("settings.backendUrls", {
                curriculum: CURRICULUM_URL.replace("http://", ""),
                identity: IDENTITY_URL.replace("http://", ""),
              })}`
              : t("auth.checkingBackend")}
        </Text>
        <Text style={styles.version}>v{APP_VERSION}</Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

export function AuthLoadingScreen() {
  const { t } = useT();
  return (
    <View style={styles.loading}>
      <ActivityIndicator color={theme.colors.netflix} size="large" />
      <Text style={styles.loadingText}>{t("auth.checkingSession")}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  scroll: {
    flexGrow: 1,
    paddingHorizontal: theme.spacing.screenX,
    paddingTop: 72,
    paddingBottom: 40,
    justifyContent: "center",
  },
  header: { marginBottom: 24, alignItems: "center" },
  brand: {
    color: theme.colors.netflix,
    fontSize: 28,
    fontWeight: "900",
    letterSpacing: 1,
    marginBottom: 8,
  },
  title: { color: theme.colors.text, fontSize: 22, fontWeight: "800", textAlign: "center" },
  sub: {
    color: theme.colors.muted,
    fontSize: 14,
    textAlign: "center",
    marginTop: 8,
    lineHeight: 20,
    paddingHorizontal: 12,
  },
  card: { gap: 12 },
  input: {
    backgroundColor: "rgba(255,255,255,0.06)",
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    color: theme.colors.text,
    padding: 14,
    fontSize: 16,
  },
  passwordRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(255,255,255,0.06)",
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    borderWidth: 1,
  },
  passwordInput: {
    flex: 1,
    color: theme.colors.text,
    padding: 14,
    fontSize: 16,
  },
  eyeButton: {
    paddingHorizontal: 14,
    paddingVertical: 12,
    alignItems: "center",
    justifyContent: "center",
  },
  error: { color: theme.colors.netflix, fontSize: 13 },
  link: { color: theme.colors.accent, textAlign: "center", marginTop: 4, fontWeight: "600" },
  hint: { color: theme.colors.muted, fontSize: 12 },
  qaRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 8 },
  qaChip: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: theme.radius.pill,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  qaText: { color: theme.colors.muted, fontSize: 12, fontWeight: "700" },
  langBlock: { marginTop: 28 },
  langLabel: { color: theme.colors.muted, fontSize: 12, fontWeight: "800", letterSpacing: 1 },
  langCurrent: { color: theme.colors.text, marginTop: 6, marginBottom: 10 },
  langRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  langChip: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: theme.radius.pill,
    borderWidth: 1,
    borderColor: theme.colors.border,
    backgroundColor: "rgba(255,255,255,0.06)",
  },
  langChipOn: { backgroundColor: theme.colors.netflix, borderColor: theme.colors.netflix },
  langChipText: { color: theme.colors.muted, fontSize: 12, fontWeight: "700" },
  langChipTextOn: { color: "#fff" },
  backend: { color: theme.colors.muted, fontSize: 11, marginTop: 20, textAlign: "center", lineHeight: 16 },
  backendDown: { color: theme.colors.netflix },
  backendUp: { color: theme.colors.success },
  version: { color: theme.colors.muted, fontSize: 11, textAlign: "center", marginTop: 8 },
  loading: { flex: 1, alignItems: "center", justifyContent: "center", gap: 16 },
  loadingText: { color: theme.colors.muted, fontSize: 14 },
});
