import React from "react";

import FriendlyErrorView from "./FriendlyErrorView";
import { writeCrashRecord } from "../crashLog";

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
    // Persist for the Bug Reporter so the next session can surface the trace
    // even if the user force-quits the app from the error screen.
    writeCrashRecord({ error, isFatal: false, source: "errorBoundary" });
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
      <FriendlyErrorView
        kind="oops"
        details={`${String(error.message || error)}${stack ? `\n${stack.trim()}` : ""}`}
        onRetry={() => { this.setState({ error: null, stack: "" }); return true; }}
        onBack={this.handleReset}
      />
    );
  }
}

