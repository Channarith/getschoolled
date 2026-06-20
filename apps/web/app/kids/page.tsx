"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Rail } from "../components/CourseRail";
import { getHomeFeed, type HomeRail } from "../lib/api";
import { ACTIVE_MASCOT, MASCOTS } from "../lib/mascots";

export default function KidsPage() {
  const [rails, setRails] = useState<HomeRail[] | null>(null);
  const [error, setError] = useState("");
  const mascot = MASCOTS[ACTIVE_MASCOT];

  useEffect(() => {
    // kids=true returns only child-appropriate (all/kids) content.
    getHomeFeed(true).then(setRails).catch((e) => setError(String(e)));
  }, []);

  return (
    <div className="kids">
      <div className="feed">
        <div className="kids-hero">
          {/* Hero row: brand lockup on the left, friendly Angkorian
              mascot greeter on the right. The mascot is a one-line
              swap via ACTIVE_MASCOT in lib/mascots.ts (apsara | bayon
              | naga | garuda). */}
          <div style={{ display: "flex", justifyContent: "center",
                        alignItems: "flex-end", gap: 28,
                        flexWrap: "wrap", marginBottom: 8 }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/logo-cartoon-lockup-512.webp"
                 alt="Salarean Kids - សាលារៀន"
                 width={180} height={225}
                 style={{ borderRadius: 24,
                          boxShadow: "0 6px 20px rgba(15,23,42,.12)" }} />
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={mascot.image} alt={mascot.altLong}
                 width={220} height={220}
                 style={{ filter: "drop-shadow(0 8px 18px rgba(15,23,42,.18))" }} />
          </div>
          <p style={{ textAlign: "center", color: "#0f172a", fontWeight: 700,
                      fontSize: 18, margin: "0 0 6px" }}>
            <span aria-hidden>👋 </span>
            Hi! I&apos;m {mascot.name} — {mascot.greeting}
          </p>
          <h1>🚀 Kids Academy</h1>
          <p style={{ color: "#9a3412", fontWeight: 600, fontSize: 18 }}>
            Safe, fun, age-appropriate classes — pick something and start the adventure!
          </p>
          <div className="hero-cta" style={{ justifyContent: "center" }}>
            <Link href="/class"><button className="theme-btn" style={{ background: "#f59e0b" }}>▶ Start a class</button></Link>
            <Link href="/"><button className="theme-btn" style={{ background: "#fff", color: "#9a3412", border: "2px solid #fdba74" }}>Back to main site</button></Link>
          </div>
          <p style={{ color: "#a16207", fontSize: 13, marginTop: 10 }}>
            Kids mode hides mature content (parental controls). Grown-ups can manage
            profiles &amp; limits in <Link href="/account">Account</Link>.
          </p>
        </div>

        {error && <p style={{ color: "#b00" }}>Could not load kids classes: {error}</p>}
        {rails === null && !error && <p className="muted">Loading fun classes…</p>}
        {rails && rails.length === 0 && <p className="muted">No kids classes yet.</p>}
        {rails?.map((r) => <Rail key={r.key} rail={r} kids />)}
      </div>
    </div>
  );
}
