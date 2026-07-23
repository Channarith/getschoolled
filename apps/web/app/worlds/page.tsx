import dynamic from "next/dynamic";
import WorldsErrorBoundary from "./WorldsErrorBoundary";

// Load the Three.js game client-side only — it uses browser APIs.
const WorldGame = dynamic(() => import("./WorldGame"), {
  ssr: false,
  loading: () => (
    <div style={{
      minHeight: "100vh", display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
      background: "#07080f", color: "#fff", gap: 16,
    }}>
      <div style={{ fontSize: 56 }}>🌍</div>
      <p style={{ color: "#6366f1", fontSize: 18, fontWeight: 700 }}>Loading Salareen Worlds…</p>
    </div>
  ),
});

export const metadata = { title: "Salareen Worlds · Learn & Explore" };

export default function WorldsPage() {
  return (
    <WorldsErrorBoundary>
      <WorldGame />
    </WorldsErrorBoundary>
  );
}
