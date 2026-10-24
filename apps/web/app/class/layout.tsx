import type { ReactNode } from "react";

import DemoTutorial from "../components/DemoTutorial";

export default function ClassLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <DemoTutorial
        storageKey="live-class"
        title="Your live class"
        steps={[
          "Join the room and allow your microphone when asked. Your camera is optional.",
          "Your teacher leads the lesson. Ask a question in the chat or by voice at any time.",
          "Slides and the whiteboard update live. Tap a slide to focus it.",
          "Tap the ? button any time to see this again.",
        ]}
      />
      {children}
    </>
  );
}
