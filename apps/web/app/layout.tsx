import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Agentic Online Education Platform",
  description: "A multi-agent AI instructor that teaches live online classes.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <nav className="nav">
          <span className="brand">AI Classroom</span>
          <Link href="/">Home</Link>
          <Link href="/class">Live Class</Link>
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/consent">Consent</Link>
        </nav>
        {children}
      </body>
    </html>
  );
}
