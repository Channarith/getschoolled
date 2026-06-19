"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Rail } from "./components/CourseRail";
import { getHomeFeed, getToken, type HomeRail } from "./lib/api";

export default function HomePage() {
  const [rails, setRails] = useState<HomeRail[] | null>(null);
  const [error, setError] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    setLoggedIn(Boolean(getToken()));
    getHomeFeed().then(setRails).catch((e) => setError(String(e)));
  }, []);

  return (
    <main>
      <section className="theme-hero" style={{
        background: "linear-gradient(120deg, #0b1020 0%, #4338ca 60%, #7c3aed 100%)",
        color: "#fff", padding: "40px 24px 44px",
      }}>
        <div className="theme-hero-inner">
          <span className="theme-badge">AI-instructed learning</span>
          <h1 className="theme-title" style={{ marginTop: 14 }}>
            Thousands of classes. One AI campus.
          </h1>
          <p className="theme-subtitle">
            {loggedIn
              ? "Pick up where you left off, or explore popular courses by category and age."
              : "Browse popular courses by category and age — sign in to track progress, earn rewards, and get personalized picks."}
          </p>
          <div className="hero-cta">
            <Link href="/class"><button className="theme-btn">▶ Try a sample class</button></Link>
            <Link href="/browse"><button className="theme-btn" style={{ background: "#e50914", color: "#fff" }}>Browse all</button></Link>
            <Link href="/arcade"><button className="theme-btn" style={{ background: "#7c3aed", color: "#fff" }}>🎮 Arcade</button></Link>
            <Link href="/languages"><button className="theme-btn" style={{ background: "#0ea5e9", color: "#fff" }}>🌍 Languages</button></Link>
            <Link href="/jobs"><button className="theme-btn" style={{ background: "#16a34a", color: "#fff" }}>💼 Careers</button></Link>
            <Link href="/kids"><button className="theme-btn" style={{ background: "#f59e0b" }}>Kids</button></Link>
            <Link href="/corporate"><button className="theme-btn" style={{ background: "#0ea5e9", color: "#fff" }}>Corporate training</button></Link>
            {loggedIn
              ? <Link href="/recommended"><button className="theme-btn" style={{ background: "#16a34a", color: "#fff" }}>For You</button></Link>
              : <Link href="/login"><button className="theme-btn" style={{ background: "#111827", color: "#fff" }}>Sign in</button></Link>}
          </div>
        </div>
      </section>

      <div className="feed">
        {error && <p style={{ color: "#b00" }}>Could not load the catalog: {error}</p>}
        {rails === null && !error && <p className="muted">Loading your catalog…</p>}
        {rails && rails.length === 0 && (
          <p className="muted">No courses yet. <Link href="/browse">Browse</Link> to get started.</p>
        )}
        {rails?.map((r) => <Rail key={r.key} rail={r} />)}
      </div>
    </main>
  );
}
