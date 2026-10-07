import Link from "next/link";

import { VisionArcadeFrame } from "../../components/VisionArcadeFrame";
import { visionArcadeFrameSrc } from "../../lib/visionArcade";

export default function VisionArcadeDemoPage() {
  return (
    <main className="container" style={{ maxWidth: 1180, margin: "0 auto", padding: "28px 22px 70px" }}>
      <p className="theme-badge">DEMO</p>
      <h1>Vision arcade</h1>
      <p className="muted" style={{ maxWidth: 720 }}>
        Children play the machine-vision games from the webcam lab: trace letters, make faces,
        catch objects with their hands, and move. Anyone can play. The camera stays in this browser.
        Nothing is recorded, and the lab does not identify who is playing.
      </p>
      <p style={{ margin: "12px 0 18px" }}>
        <Link href="/">← Back to Salareen</Link>
        {" · "}
        <Link href="/arcade">More arcade games</Link>
      </p>
      <VisionArcadeFrame title="Children machine vision games" src={visionArcadeFrameSrc()} />
    </main>
  );
}
