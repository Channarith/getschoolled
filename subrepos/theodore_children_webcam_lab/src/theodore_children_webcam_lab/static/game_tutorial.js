// Short first-visit tutorials for every Play Lab game (Pop Quiz Toss has its own).
// Data plus a tiny overlay; the page decides when a game is chosen.

export const TUTORIAL_KEY_PREFIX = "salareen.lab.tutorial.v1.";

export const TUTORIALS = {
  "trace-letter": [
    "✏️",
    "Trace a letter",
    [
      "Point at the screen or use your finger to draw over the letter.",
      "Stay on the dotted path from start to finish.",
      "Tap Undo to try a stroke again."
    ]
  ],
  "trace-picture": [
    "🖍️",
    "Trace a picture",
    [
      "Draw along the outline of the picture.",
      "Go slowly, close is good enough.",
      "Tap Undo if you slip."
    ]
  ],
  "color-picture": [
    "🎨",
    "Color the picture",
    [
      "Pick a color, then color inside the shapes.",
      "Fill every shape to finish.",
      "Tap Undo to take a stroke back."
    ]
  ],
  "connect-dots": [
    "🔵",
    "Connect the dots",
    [
      "Touch the dots in number order.",
      "Draw a line from one dot to the next.",
      "Finish the last dot to reveal the picture."
    ]
  ],
  "trace-outline": [
    "🧩",
    "Trace the outline",
    [
      "Follow the outline with your finger or hand.",
      "Stay close to the line.",
      "Tap Undo to fix a stroke."
    ]
  ],
  "say-letter": [
    "🔤",
    "Say the letter",
    [
      "A letter appears on screen.",
      "Tap the mic and say its name out loud.",
      "Not sure? Tap Hear it to listen first."
    ]
  ],
  "repeat-after-me": [
    "🗣️",
    "Repeat after me",
    [
      "Tap Hear it and listen to the phrase.",
      "Tap the mic and say it back.",
      "Speak clearly, then tap Check."
    ]
  ],
  "pronounce-word": [
    "🔊",
    "Pronounce the word",
    [
      "Read the word, or tap Hear it.",
      "Say it out loud into the mic.",
      "Try again for a closer match."
    ]
  ],
  "rhyme-time": [
    "🎶",
    "Say a rhyme",
    [
      "Listen to the word.",
      "Say a word that rhymes with it.",
      "Any real rhyme counts."
    ]
  ],
  "listen-answer": [
    "👂",
    "Answer what you hear",
    [
      "Listen to the question.",
      "Answer by voice or type it.",
      "Tap Hear it to listen again."
    ]
  ],
  "missing-word": [
    "❓",
    "Say the missing word",
    [
      "Listen to the sentence with a gap.",
      "Say the word that fits.",
      "Tap Hear it to replay."
    ]
  ],
  "opposites": [
    "↔️",
    "Say the opposite",
    [
      "You hear a word.",
      "Say its opposite, like hot and cold.",
      "Tap Check if you typed it."
    ]
  ],
  "explain-it": [
    "💬",
    "Explain it",
    [
      "Listen to the idea.",
      "Explain it in your own words.",
      "A short answer is fine."
    ]
  ],
  "sum-it-up": [
    "📝",
    "Sum it up",
    [
      "Listen to the short story.",
      "Say what it was about in a sentence.",
      "Keep it short."
    ]
  ],
  "prove-it": [
    "🧠",
    "Prove you understand",
    [
      "Listen, then answer the question.",
      "Give an example or a reason.",
      "Your own words are best."
    ]
  ],
  "story-order": [
    "📖",
    "What happened first",
    [
      "Listen to the story.",
      "Say or type what happened first.",
      "Tap Hear it to listen again."
    ]
  ],
  "how-many": [
    "🔢",
    "How many did you hear",
    [
      "Listen carefully.",
      "Say or type how many you heard.",
      "Tap Hear it to count again."
    ]
  ],
  "same-or-different": [
    "⚖️",
    "Same or different",
    [
      "Listen to two sounds or words.",
      "Say same or different.",
      "Replay with Hear it."
    ]
  ],
  "finish-the-line": [
    "🎤",
    "Finish the line",
    [
      "Listen to the start of the line.",
      "Say how it ends.",
      "Tap Hear it to replay."
    ]
  ],
  "spell-aloud": [
    "🔠",
    "Spell what you hear",
    [
      "Listen to the word.",
      "Spell it out loud, letter by letter.",
      "Or type it and tap Check."
    ]
  ],
  "karaoke": [
    "🎤",
    "Karaoke sing-along",
    [
      "The words light up as the song plays.",
      "Sing along with the highlighted words.",
      "Tap Play to start over."
    ]
  ],
  "oh-behave": [
    "😮",
    "Oh behave",
    [
      "Look at the camera so your face is in the picture.",
      "Make the face it asks for.",
      "Hold it for a moment."
    ]
  ],
  "heart": [
    "💖",
    "Make hearts",
    [
      "Show both hands to the camera.",
      "Make a heart shape with your two hands.",
      "Hold it until it lights up."
    ]
  ],
  "idea": [
    "💡",
    "I have an idea",
    [
      "Show one hand to the camera.",
      "Point one finger up, like a bright idea.",
      "Hold it for a moment."
    ]
  ],
  "fist-bump": [
    "👊",
    "Fist bump",
    [
      "Close your fist and show it to the camera.",
      "Bump it toward the other fist on screen.",
      "Keep your hand in the picture."
    ]
  ],
  "wow": [
    "🤩",
    "Wow face",
    [
      "Look at the camera.",
      "Open your eyes and mouth wide.",
      "Hold your wow face."
    ]
  ],
  "blow-kiss": [
    "😘",
    "Blow a kiss",
    [
      "Look at the camera.",
      "Pucker up and blow a kiss.",
      "Hold it a moment."
    ]
  ],
  "wink": [
    "😉",
    "Wink challenge",
    [
      "Look at the camera.",
      "Wink with one eye.",
      "Hold the wink."
    ]
  ],
  "make-pose": [
    "🦸",
    "Make a hero pose",
    [
      "Step back so your upper body is in the picture.",
      "Copy the hero pose shown.",
      "Hold it still."
    ]
  ],
  "balloon": [
    "🎈",
    "Pop balloons",
    [
      "Show your hand or tap the screen.",
      "Touch the balloons to pop them.",
      "Pop as many as you can."
    ]
  ],
  "fish": [
    "🐟",
    "Catch flying fish",
    [
      "Show your hand or tap the screen.",
      "Touch the fish before they swim away.",
      "Catch them all."
    ]
  ],
  "popcorn": [
    "🍿",
    "Catch popcorn",
    [
      "Open your mouth wide, or touch the popcorn.",
      "Catch the popcorn as it pops up.",
      "Keep your face in the picture."
    ]
  ],
  "mirror-hall": [
    "🪞",
    "Mirror Hall",
    [
      "Stand back so your whole body is in the picture.",
      "Copy the moves in the mirror.",
      "Match the pose to score."
    ]
  ],
  "ninja-weave": [
    "🥷",
    "Ninja Weave",
    [
      "Show both hands to the camera.",
      "Make the hand signs shown, in order.",
      "Finish the sign to unleash the finisher."
    ]
  ],
  "fruit-cut": [
    "🍉",
    "Fruit cut",
    [
      "Show your hand to the camera, or swipe the screen.",
      "Slice through the fruit as it flies.",
      "Avoid the bombs."
    ]
  ],
  "air-drums": [
    "🥁",
    "Air drums",
    [
      "Show both hands to the camera.",
      "Tap the air over each drum.",
      "Follow the beat."
    ]
  ],
  "bird-flap": [
    "🐦",
    "Flap like a bird",
    [
      "Step back so your arms are in the picture.",
      "Flap your arms up and down.",
      "Keep flapping to fly higher."
    ]
  ],
  "head-bop": [
    "🎧",
    "Head bop",
    [
      "Look at the camera.",
      "Nod your head to the beat.",
      "Keep nodding in time."
    ]
  ],
  "face-chase": [
    "🙂",
    "Face chase",
    [
      "Look at the camera.",
      "Move your face to chase the target.",
      "Keep your face in the picture."
    ]
  ],
  "stand-sit": [
    "🪑",
    "Stand up, sit down",
    [
      "Step back so your whole body shows.",
      "Stand up when told, then sit down.",
      "Keep in the picture."
    ]
  ],
  "dance-freeze": [
    "💃",
    "Dance freeze",
    [
      "Step back so your whole body shows.",
      "Dance while the music plays.",
      "Freeze when it stops!"
    ]
  ],
  "rainbow-reach": [
    "🌈",
    "Rainbow reach",
    [
      "Show your hand to the camera.",
      "Reach to touch each color of the rainbow.",
      "Stretch up and across."
    ]
  ]
};

export const DEFAULT_TUTORIAL = ["✨", "How to play", ["Allow your camera and mic if asked.", "Follow the prompt at the top of the screen.", "Tap the ? button any time to see this again."]];

export function tutorialFor(gameId) {
  const [icon, title, lines] = TUTORIALS[gameId] || DEFAULT_TUTORIAL;
  return {icon, title, lines: [...lines]};
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
    const tut = tutorialFor(game);
    overlay.replaceChildren();
    const card = doc.createElement("div");
    card.className = "gt-card";
    const h = doc.createElement("h2");
    h.textContent = `${tut.icon} ${tut.title}`;
    const list = doc.createElement("ol");
    for (const line of tut.lines) {
      const li = doc.createElement("li");
      li.textContent = line;
      list.append(li);
    }
    const go = doc.createElement("button");
    go.type = "button";
    go.className = "gt-go";
    go.textContent = "Let's play";
    go.addEventListener("click", close);
    const skip = doc.createElement("button");
    skip.type = "button";
    skip.className = "gt-skip";
    skip.textContent = "Skip";
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
