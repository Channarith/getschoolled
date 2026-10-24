"use client";

import { usePathname } from "next/navigation";

import DemoTutorial from "./DemoTutorial";

/** One how-to per arcade game (and one for the arcade home), remembered per game. */
export default function ArcadeTutorial() {
  const path = usePathname() || "/arcade";
  const slug = path.replace(/^\/arcade\/?/, "").split("/")[0] || "home";
  const home = slug === "home";
  return (
    <DemoTutorial
      key={slug}
      storageKey={`arcade.${slug}`}
      title={home ? "Pick a game" : "How to play"}
      steps={
        home
          ? [
              "Choose any game to start. Every game explains its goal at the top.",
              "Play with a mouse, finger or keyboard. Camera games ask first and keep video on your device.",
              "Earn points and stars, and come back for the leaderboard.",
              "Tap the ? button any time to see this again.",
            ]
          : [
              "Read the goal at the top of the game, then press Start or tap the board.",
              "Use your mouse, finger or keyboard to play. Take your time: there is no rush.",
              "Your score is saved when the round ends. Try again to beat it.",
              "Tap the ? button any time to see this again.",
            ]
      }
    />
  );
}
