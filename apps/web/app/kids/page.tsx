"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Rail } from "../components/CourseRail";
import { getHomeFeed, type HomeRail } from "../lib/api";

export default function KidsPage() {
  const [rails, setRails] = useState<HomeRail[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    // kids=true returns only child-appropriate (all/kids) content.
    getHomeFeed(true).then(setRails).catch((e) => setError(String(e)));
  }, []);

  return (
    <div className="kids">
      <div className="feed">
        <div className="kids-hero">
          {/* Cartoon lockup: kid-friendly mark + Khmer wordmark
              (សាលារៀន). Same composition as the realistic lockup
              on the home page so the brand reads consistently. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo-cartoon-lockup-512.webp"
               alt="Salarean Kids - សាលារៀន"
               width={180} height={225}
               style={{ display: "block", margin: "0 auto 8px",
                        borderRadius: 24,
                        boxShadow: "0 6px 20px rgba(15,23,42,.12)" }} />
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
