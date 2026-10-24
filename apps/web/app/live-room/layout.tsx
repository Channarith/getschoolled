import type { ReactNode } from "react";

import DemoTutorial from "../components/DemoTutorial";

export default function LiveRoomLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <DemoTutorial
        storageKey="live-room"
        title="Your live room"
        steps={[
          "Allow your microphone when asked. Your camera is optional.",
          "Use the chat to ask questions or send a reaction.",
          "Leave any time with the Leave button.",
          "Tap the ? button any time to see this again.",
        ]}
      />
      {children}
    </>
  );
}
