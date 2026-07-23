"use client";
import { Component, type ReactNode } from "react";
import Link from "next/link";

interface Props { children: ReactNode }
interface State { error: Error | null }

export default class WorldsErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{
          minHeight: "100vh", display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center",
          background: "#07080f", color: "#fff", padding: 32, gap: 16, textAlign: "center",
        }}>
          <div style={{ fontSize: 56 }}>🌍</div>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 900 }}>Salareen Worlds failed to load</h2>
          <p style={{ color: "#94a3b8", maxWidth: 340, margin: 0 }}>
            Your device may not support WebGL, or there was a script error. Try refreshing.
          </p>
          <p style={{ color: "#475569", fontSize: 12, fontFamily: "monospace", maxWidth: 400 }}>
            {this.state.error.message}
          </p>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", justifyContent: "center" }}>
            <button
              onClick={() => { this.setState({ error: null }); window.location.reload(); }}
              style={{ padding: "12px 24px", borderRadius: 10, background: "#6366f1", color: "#fff", border: "none", fontWeight: 700, cursor: "pointer" }}
            >
              Reload
            </button>
            <Link href="/arcade" style={{ padding: "12px 24px", borderRadius: 10, background: "rgba(255,255,255,0.1)", color: "#fff", fontWeight: 700, textDecoration: "none" }}>
              Back to Arcade
            </Link>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
