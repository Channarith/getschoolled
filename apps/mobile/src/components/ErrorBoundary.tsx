import React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";

import PrimaryButton from "./PrimaryButton";
import { theme } from "../theme";

type Props = {
  children: React.ReactNode;
  // Called by the "Go back" button so the app can return to a safe screen.
  onReset?: () => void;
  // A value that identifies the currently shown screen. When it changes (the
  // user navigates elsewhere, e.g. via the bottom tabs) the boundary clears its
  // error automatically so the app recovers without a restart.
  resetKey?: string | number | null;
};

type State = { error: Error | null; stack: string };

// Catches render/runtime errors in the screen tree so a single bad screen
// (e.g. the live room) shows a readable, dismissible message and logs the stack
// instead of white-screen crashing the whole app. The console.error surfaces in
// Metro AND in `adb logcat` (tag ReactNativeJS), which is exactly what you need
// to diagnose an otherwise-silent release crash.
export default class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null, stack: "" };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: { componentStack?: string }): void {
    const stack = info?.componentStack || "";
    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary] screen crashed:", error?.stack || String(error), stack);
    this.setState({ stack });
  }

  componentDidUpdate(prev: Props): void {
    if (prev.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null, stack: "" });
    }
  }

  private handleReset = (): void => {
    this.setState({ error: null, stack: "" });
    this.props.onReset?.();
  };

  render(): React.ReactNode {
    const { error, stack } = this.state;
    if (!error) return this.props.children;
    return (
      <ScrollView contentContainerStyle={styles.wrap}>
        <Text style={styles.title}>Something went wrong on this screen</Text>
        <Text style={styles.msg}>{String(error.message || error)}</Text>
        {stack ? (
          <View style={styles.stackBox}>
            <Text style={styles.stack}>{stack.trim()}</Text>
          </View>
        ) : null}
        <PrimaryButton label="Go back" onPress={this.handleReset} />
      </ScrollView>
    );
  }
}

const styles = StyleSheet.create({
  wrap: {
    flexGrow: 1,
    justifyContent: "center",
    padding: theme.spacing.screenX,
    gap: 12,
  },
  title: { color: theme.colors.text, fontSize: 20, fontWeight: "700" },
  msg: { color: theme.colors.text, fontSize: 14, opacity: 0.9 },
  stackBox: {
    backgroundColor: "rgba(0,0,0,0.35)",
    borderRadius: 10,
    padding: 12,
    maxHeight: 260,
  },
  stack: { color: "rgba(255,255,255,0.75)", fontSize: 11, fontFamily: "monospace" },
});
