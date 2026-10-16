"use client";

import { VisionArcadeFrame } from "../components/VisionArcadeFrame";
import { useT } from "../lib/i18n";
import { visionArcadeFrameSrc } from "../lib/visionArcade";

// Vision Play shows Machine Vision only. Other games and Salareen Worlds
// keep their routes; they are not listed on this page.
export default function ArcadePage() {
  const { t } = useT();

  return (
    <main className="container" style={{ maxWidth: 1000 }}>
      <h1>{t("arcade.title")}</h1>
      <p className="muted" style={{ marginTop: 0 }}>
        {t("arcade.intro")}
      </p>
      <div id="vision" className="card" style={{ background: "linear-gradient(135deg, rgba(14,165,233,0.18), rgba(124,58,237,0.14))" }}>
        <h2 style={{ marginTop: 0 }}>Machine vision</h2>
        <VisionArcadeFrame title="Machine vision" src={visionArcadeFrameSrc()} />
      </div>
    </main>
  );
}
