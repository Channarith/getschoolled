import type { Metadata } from "next";
import "./globals.css";
import { DEPLOY_MODE } from "@/lib/api";

export const metadata: Metadata = {
  title: "AOEP - Agentic Online Education Platform",
  description: "A multi-agent AI instructor that teaches live classes.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="container">
          <header style={{ marginBottom: "1.5rem" }}>
            <h1 style={{ margin: 0 }}>AOEP</h1>
            <span className="badge">deploy mode: {DEPLOY_MODE}</span>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
