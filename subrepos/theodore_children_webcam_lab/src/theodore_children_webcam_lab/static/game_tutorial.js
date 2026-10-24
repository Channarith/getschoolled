// Short first-visit tutorials for every Play Lab game (Pop Quiz Toss has its own).
// Data plus a tiny overlay; the page decides when a game is chosen.

export const TUTORIAL_KEY_PREFIX = "salareen.lab.tutorial.v1.";

import {HOWTO, UI, howtoFor, howtoLang} from "./game_howto.js";

export const TUTORIALS = Object.fromEntries(Object.keys(HOWTO).map((id) => {
  const t = howtoFor(id, "en");
  return [id, [t.icon, t.title, t.lines]];
}));

export const DEFAULT_TUTORIAL = ["✨", "How to play", ["Allow your camera and mic if asked.", "Follow the prompt at the top of the screen.", "Tap the ? button any time to see this again."]];

export function tutorialFor(gameId, lang = "en") {
  const found = howtoFor(gameId, lang);
  if (found) return found;
  const [icon, title, lines] = DEFAULT_TUTORIAL;
  return {icon, title, lines: [...lines], labels: null};
}

export function hasSeenTutorial(gameId, storage = globalThis.localStorage) {
  try { return storage?.getItem(TUTORIAL_KEY_PREFIX + gameId) === "1"; } catch { return false; }
}

export function markTutorialSeen(gameId, storage = globalThis.localStorage) {
  try { storage?.setItem(TUTORIAL_KEY_PREFIX + gameId, "1"); } catch { /* private mode */ }
}

const OWN_TUTORIAL = new Set(["pop-quiz-toss"]);

/** Builds the ? button and the overlay inside the stage. */
export function createGameTutorial(stage, doc = document) {
  let game = "";
  const help = doc.createElement("button");
  help.type = "button";
  help.className = "gt-help";
  help.setAttribute("aria-label", "How to play");
  help.textContent = "?";
  const overlay = doc.createElement("div");
  overlay.className = "gt-overlay";
  overlay.hidden = true;
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  stage.append(help, overlay);

  function close() {
    overlay.hidden = true;
    if (game) markTutorialSeen(game);
    if (!help.hidden) help.focus?.({preventScroll: true});
  }
  function open() {
    if (!game || OWN_TUTORIAL.has(game)) return;
    const lang = howtoLang();
    const words = UI[lang] || UI.en;
    const tut = tutorialFor(game, lang);
    help.setAttribute("aria-label", words.help);
    overlay.setAttribute("aria-label", tut.title);
    overlay.replaceChildren();
    const card = doc.createElement("div");
    card.className = "gt-card";
    const h = doc.createElement("h2");
    h.textContent = `${tut.icon} ${tut.title}`;
    const list = doc.createElement("ol");
    tut.lines.forEach((line, i) => {
      const li = doc.createElement("li");
      if (tut.labels?.[i]) {
        const label = doc.createElement("strong");
        label.textContent = `${tut.labels[i]}: `;
        li.append(label);
      }
      li.append(doc.createTextNode(line));
      list.append(li);
    });
    const go = doc.createElement("button");
    go.type = "button";
    go.className = "gt-go";
    go.textContent = words.letsPlay;
    go.addEventListener("click", close);
    const skip = doc.createElement("button");
    skip.type = "button";
    skip.className = "gt-skip";
    skip.textContent = words.skip;
    skip.addEventListener("click", close);
    card.append(h, list, go, skip);
    overlay.append(card);
    overlay.hidden = false;
    go.focus?.({preventScroll: true});
  }
  help.addEventListener("click", open);
  overlay.addEventListener("keydown", (event) => { if (event.key === "Escape") { event.stopPropagation(); close(); } });
  overlay.addEventListener("click", (event) => { if (event.target === overlay) close(); });

  return {
    /** Call whenever a game is chosen: shows the tutorial the first time only. */
    onGameChosen(gameId) {
      game = gameId;
      overlay.hidden = true;
      const own = OWN_TUTORIAL.has(gameId);
      help.hidden = own;
      if (!own && !hasSeenTutorial(gameId)) open();
    },
    open,
    close,
  };
}
