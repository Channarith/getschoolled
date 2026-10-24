import type { Metadata } from "next";
import Link from "next/link";

import DemoTutorial from "../../components/DemoTutorial";
import DemoVoiceSelect from "../../components/DemoVoiceSelect";
import OnTheGo from "../../components/OnTheGo";

// Not listed anywhere public: reached by four quick clicks on the Salareen logo. Keep it out of search results.
export const metadata: Metadata = { robots: { index: false, follow: false } };

/** Hidden demo of the same On the Go player, limited to a 10-minute sample. */
export default function OnTheGoDemoPage() {
  return (
    <main className="course-stage">
      <p className="course-stage-links">
        <Link href="/">← Back to Salareen</Link>
        <Link href="/demo/drivers-ed">Driver&apos;s ed on screen</Link>
      </p>
      <DemoTutorial
        storageKey="on-the-go"
        title="Listen on the go"
        steps={[
          "Tap the course to start the audio. Put on headphones or turn up the sound.",
          "Use Pause, Next and Back on the player to control the lesson.",
          "This demo is a free 10-minute sample. The timer shows how much is left.",
          "Tap the ? button any time to see this again.",
        ]}
      />
      <p><DemoVoiceSelect /></p>
      <OnTheGo mode="demo" />
    </main>
  );
}
