"use client";

import { useEffect } from "react";

type LiveAudio = {
  noteActivity?: (detail: { id?: string; prompt?: string }) => void;
  setHidden?: (hidden: boolean) => void;
  start?: () => Promise<boolean>;
};

function liveAudio(): LiveAudio | undefined {
  return (window as Window & { TheodoreLiveAudio?: LiveAudio }).TheodoreLiveAudio;
}

function fold(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, " ").replace(/\s+/g, " ").trim();
}

/** Same idea as the lesson studio: a short spoken choice or its number. */
export function matchSpokenChoice(spoken: string, choices: string[]): number {
  const said = fold(spoken);
  if (!said || !choices.length) return -1;
  const ordinals: Record<string, number> = {
    one: 0, first: 0, two: 1, second: 1, three: 2, third: 2,
    four: 3, fourth: 3, five: 4, fifth: 4, six: 5, sixth: 5,
  };
  const letters: Record<string, number> = { a: 0, b: 1, c: 2, d: 3, e: 4, f: 5 };
  const tokens = said.split(" ").filter((word) => !["the", "number", "option", "choice", "answer", "please"].includes(word));
  const only = tokens.length === 1 ? tokens[0] : said;
  if (Object.prototype.hasOwnProperty.call(ordinals, only) && ordinals[only] < choices.length) return ordinals[only];
  if (Object.prototype.hasOwnProperty.call(letters, only) && letters[only] < choices.length) return letters[only];
  const num = parseInt(said, 10);
  if (String(num) === said && num >= 1 && num <= choices.length) return num - 1;
  let best = -1;
  let bestScore = 0;
  choices.forEach((choice, index) => {
    const words = fold(choice).split(" ").filter((word) => word.length > 2);
    const score = words.filter((word) => said.includes(word)).length;
    if (score > bestScore) {
      bestScore = score;
      best = index;
    }
  });
  return bestScore > 0 ? best : -1;
}

function isSubmit(text: string): boolean {
  const said = fold(text);
  return said === "submit" || said === "done" || said === "check" || said === "finished" ||
    said === "check my answers" || said === "thats all" || said === "that is all";
}

/**
 * Loads the shared live-voice widget and clicks the open arcade activity
 * when the learner says a choice. Machine-vision games keep their own widget
 * inside the lab frame.
 */
export function LiveActivityVoice({ active, prompt }: { active: boolean; prompt?: string }) {
  useEffect(() => {
    if (!active) {
      liveAudio()?.setHidden?.(true);
      return;
    }
    const onUtterance = (event: Event) => {
      const detail = (event as CustomEvent<{ role?: string; text?: string; command?: boolean }>).detail || {};
      if (detail.role !== "user" || detail.command || !detail.text) return;
      if (isSubmit(detail.text)) {
        document.querySelector<HTMLButtonElement>("[data-voice-submit]")?.click();
        return;
      }
      const buttons = [...document.querySelectorAll<HTMLButtonElement>("[data-voice-choice]:not([disabled])")];
      const index = matchSpokenChoice(detail.text, buttons.map((button) => button.textContent || ""));
      if (index >= 0) buttons[index].click();
    };
    window.addEventListener("theodore-live-audio-utterance", onUtterance);
    const onLive = (event: Event) => {
      const detail = (event as CustomEvent<{ active?: boolean }>).detail || {};
      if (!detail.active || !prompt) return;
      window.setTimeout(() => {
        liveAudio()?.noteActivity?.({
          id: prompt.slice(0, 160),
          prompt: "An arcade game is on the screen. Ask for the answer in one short sentence and wait. Do not reveal the correct answer. " + prompt,
        });
      }, 700);
    };
    window.addEventListener("theodore-live-audio", onLive);
    let script = document.querySelector<HTMLScriptElement>("script[data-aoep-live-audio]");
    const show = () => {
      liveAudio()?.setHidden?.(false);
      if (prompt) {
        liveAudio()?.noteActivity?.({
          id: prompt.slice(0, 160),
          prompt: "An arcade game is on the screen. Ask for the answer in one short sentence and wait. Do not reveal the correct answer. " + prompt,
        });
      }
    };
    if (!script) {
      script = document.createElement("script");
      script.src = "/api/live-audio/client.js";
      script.dataset.aoepLiveAudio = "1";
      script.async = true;
      script.onload = show;
      document.body.appendChild(script);
    } else if (liveAudio()) {
      show();
    } else {
      script.addEventListener("load", show, { once: true });
    }
    return () => {
      window.removeEventListener("theodore-live-audio-utterance", onUtterance);
      window.removeEventListener("theodore-live-audio", onLive);
    };
  }, [active, prompt]);
  return null;
}
