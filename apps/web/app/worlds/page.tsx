import dynamic from "next/dynamic";

// Load the Three.js game client-side only — it uses browser APIs.
const WorldGame = dynamic(() => import("./WorldGame"), { ssr: false });

export const metadata = { title: "Salareen Worlds · Learn & Explore" };

export default function WorldsPage() {
  return <WorldGame />;
}
