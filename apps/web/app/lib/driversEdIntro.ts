/** Order of the Driver's Ed demo opening: tutorial first, then the video, then the course page. */

export const INTRO_SEEN_KEY = "salareen.driversEdIntro.seen.v1";

export type TutorialState = "pending" | "open" | "closed";
export type IntroPhase = "hold" | "play" | "done";

/** hold = video waits behind the tutorial (paused); play = video on top; done = course page. */
export function introPhase(tutorial: TutorialState, finished: boolean): IntroPhase {
  if (finished) return "done";
  return tutorial === "closed" ? "play" : "hold";
}

export type TutorialMessage = { type: "sala-tutorial"; state: TutorialState };

export function tutorialStateFrom(data: unknown): TutorialState | null {
  if (!data || typeof data !== "object") return null;
  const msg = data as Partial<TutorialMessage>;
  if (msg.type !== "sala-tutorial") return null;
  return msg.state === "pending" || msg.state === "open" || msg.state === "closed" ? msg.state : null;
}
