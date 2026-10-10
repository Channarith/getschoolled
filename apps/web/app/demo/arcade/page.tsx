import { VisionArcadeLinks } from "../../components/DemoOnly";
import { VisionArcadeFrame } from "../../components/VisionArcadeFrame";
import { visionArcadeFrameSrc } from "../../lib/visionArcade";

export default function VisionArcadeDemoPage() {
  return (
    <main className="container" style={{ maxWidth: 1180, margin: "0 auto", padding: "16px 16px 40px" }}>
      <p style={{ margin: "0 0 12px", display: "flex", flexWrap: "wrap", gap: "6px 14px" }}>
        <VisionArcadeLinks />
      </p>
      <VisionArcadeFrame title="Children machine vision games" src={visionArcadeFrameSrc()} />
    </main>
  );
}
