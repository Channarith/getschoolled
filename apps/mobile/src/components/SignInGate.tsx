import { StyleSheet, Text, View } from "react-native";

import PrimaryButton from "./PrimaryButton";
import GlassPanel from "./GlassPanel";
import { theme } from "../theme";

type Props = {
  title?: string;
  body?: string;
  signInLabel?: string;
  onSignIn: () => void;
};

/** Blocks a feature until the user signs in (web SignInToUse parity). */
export default function SignInGate({
  title = "Sign in to continue",
  body = "Create a free account to unlock this feature.",
  signInLabel = "Sign in",
  onSignIn,
}: Props) {
  return (
    <GlassPanel style={styles.wrap}>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.body}>{body}</Text>
      <PrimaryButton label={signInLabel} onPress={onSignIn} variant="netflix" />
    </GlassPanel>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 12, marginVertical: 12 },
  title: { color: theme.colors.text, fontSize: 17, fontWeight: "800" },
  body: { color: theme.colors.muted, fontSize: 14, lineHeight: 20 },
});
