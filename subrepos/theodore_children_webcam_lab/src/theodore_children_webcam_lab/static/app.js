import {
  centroid, colorLine, dotHit, dotRadius, dotsFor, markerRadius, outlineCoverage, outlinePassed,
  sceneForWord, scratchCoverage, scratchPassed, segmentAt, swatchHit, swatchLayout,
} from "./picture_play.js";
import {
  FIST_MAX_PALMS, HEART_TIPS_PALMS, HEART_THUMBS_PALMS, HEART_WRISTS_PALMS,
  HEART_CLEFT_PALMS, HEART_POINT_PALMS,
  KISS_NEAR_FACES, KISS_AWAY_FACES, HAND_BONES,
  PAUSE_LINE, RESUME_LINE,
<<<<<<< HEAD
  activeFingertips, advanceMirrorBeat, advanceThrowGesture, catchRadiusPx, claimTouch, coverFrame, createPresenceWatch,
  debiasedGazeDown, defaultMirrorPace, fingersPointed, freshMirrorRun, handShape, headPoseFromMesh,
  heartRatios, isHeartShape, localMathRound, mapMirroredLandmark, mirrorBeatMatched, mirrorPace,
  mirrorPose, mirrorSummary, MIRROR_ROUTINE, newThrowTracker, profileTouchAge,
  advanceNinjaWeave, freshNinjaRun, ninjaSealFits, ninjaTechnique, recognizeNinjaSeal,
  NINJA_DEFAULT_TECHNIQUE, NINJA_ELEMENTS, NINJA_SEALS, NINJA_TECHNIQUES, ninjaEffectParticles, ninjaEffectSpec,
  ninjaTechniqueList, projectThrowTarget, syntheticHand,
=======
  activeFingertips, advanceThrowGesture, catchRadiusPx, claimTouch, coverFrame, createPresenceWatch,
  debiasedGazeDown, fingersPointed, handShape, headPoseFromMesh,
  heartRatios, isHeartShape, mapMirroredLandmark, newThrowTracker, profileTouchAge,
  projectThrowTarget, syntheticHand,
>>>>>>> 2aaa58c3 (Pop Quiz Toss: quiz rounds, themed targets, curve throws, voice + throw scoring, tutorial, adult ages)
  tipHitsTarget, traceProgress,
} from "./vision_math.js";
import {createPopQuizGame} from "./pop_quiz_game.js";

const $ = (id) => document.getElementById(id);

// Static files reload from disk but the HTML shell is rendered by the running
// Python process, so a dev server started before an update serves NEW script
// against an OLD page — and a browser can hold a cached page too. Reading
// `.checked` straight off a missing node threw and killed the whole lab, so
// overlay switches default to on when their control is not there and text
// targets are skipped rather than fatal.
const switchedOn = (id) => $(id)?.checked ?? true;
const setText = (id, text) => { const node = $(id); if (node) node.textContent = text; };
const VISION_VERSION = "0.10.14";
const VISION_CDN = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${VISION_VERSION}`;
const MODEL_ROOT = "https://storage.googleapis.com/mediapipe-models";
const LETTER_WORDS = {
  A:"apple",B:"ball",C:"cat",D:"dragon",E:"elephant",F:"fish",G:"grape",H:"heart",
  I:"ice cream",J:"jellyfish",K:"kite",L:"lion",M:"moon",N:"nest",O:"octopus",
  P:"popcorn",Q:"queen",R:"rocket",S:"star",T:"teddy",U:"umbrella",V:"violin",
  W:"whale",X:"xylophone",Y:"yo-yo",Z:"zebra"
};
const REGIONS = {
  "top-left":[.18,.23],"top":[.5,.2],"top-right":[.82,.23],"left":[.18,.5],
  "center":[.5,.5],"right":[.82,.5],"bottom-left":[.18,.77],"bottom":[.5,.8],
  "bottom-right":[.82,.77]
};
const EXPRESSIONS = ["happy","surprised","wink-left","wink-right","mouth-o","sleepy"];
const MISS_GAGS = {
  cuddly:[["🐷💨","Piggy made a silly puff!"],["🧸💨","Teddy ran away!"],["🎂😄","Cake in the face!"],["🐌🚩","The snail got here late!"],["🐧↩️","Penguin slid the wrong way!"],["🌧️💖","A cloud rained hearts!"]],
  hero:[["🐉🤧","Dragon sneeze!"],["🏎️💫","Tiny spin-out!"],["🤖💤","Robot needs a reboot!"],["🥷💨","Ninja vanished!"],["⚔️🛏️","The sword bonked a pillow!"],["🚀🙃","Rocket took a funny turn!"]]
};
const OBJECT_GAMES = new Set(["fruit-cut","balloon","fish","popcorn"]);
const PICTURE_PLAY = new Set(["color-picture","connect-dots","trace-outline"]);
const AUDIO_GAMES = new Set([
  "repeat-after-me","pronounce-word","rhyme-time","listen-answer","missing-word",
  "opposites","explain-it","sum-it-up","prove-it","story-order","how-many",
  "same-or-different","finish-the-line","spell-aloud",
]);
function isAudioGame(game = state.game) {
  return game === "say-letter" || AUDIO_GAMES.has(game);
}
// Keep in lockstep with game_engine.GAME_MENU / /api/child/content. A game in
// the menu without a matching chooseGame + update* branch is a missing game.
const GAMES = [
  "trace-letter","trace-picture","color-picture","connect-dots","trace-outline","say-letter","pop-quiz-toss",
  "repeat-after-me","pronounce-word","rhyme-time","listen-answer","missing-word",
  "opposites","explain-it","sum-it-up","prove-it","story-order","how-many",
  "same-or-different","finish-the-line","spell-aloud",
  "karaoke",
  "oh-behave","heart","idea",
  "fist-bump","wow","blow-kiss","wink","make-pose","balloon","fish","popcorn",
  "mirror-hall","ninja-weave","fruit-cut","air-drums","bird-flap","head-bop","face-chase","stand-sit",
  "dance-freeze","rainbow-reach",
];
// Missing ids get Play only. A new game cannot inherit the letter, mic, and undo row.
const NO_CONTROLS = {letter:false, undo:false, mic:false, typed:false, check:false, hear:false, words:false, play:true};
const GAME_CONTROLS = {
  "trace-letter": {letter:true, undo:true, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "trace-picture": {letter:true, undo:true, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "color-picture": {letter:true, undo:true, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "connect-dots": {letter:true, undo:true, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "trace-outline": {letter:true, undo:true, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "say-letter": {letter:true, undo:false, mic:true, typed:true, check:true, hear:true, words:false, play:true},
  "pop-quiz-toss": {letter:false, undo:false, mic:true, typed:true, check:true, hear:true, words:false, play:true},
  "repeat-after-me": {letter:false, undo:false, mic:true, typed:true, check:true, hear:true, words:true, play:true},
  "pronounce-word": {letter:false, undo:false, mic:true, typed:true, check:true, hear:true, words:true, play:true},
  "rhyme-time": {letter:false, undo:false, mic:true, typed:true, check:true, hear:true, words:true, play:true},
  "listen-answer": {letter:false, undo:false, mic:true, typed:true, check:true, hear:true, words:true, play:true},
  "missing-word": {letter:false, undo:false, mic:true, typed:true, check:true, hear:true, words:true, play:true},
  "opposites": {letter:false, undo:false, mic:true, typed:true, check:true, hear:true, words:true, play:true},
  "explain-it": {letter:false, undo:false, mic:true, typed:true, check:true, hear:true, words:true, play:true},
  "sum-it-up": {letter:false, undo:false, mic:true, typed:true, check:true, hear:true, words:true, play:true},
  "prove-it": {letter:false, undo:false, mic:true, typed:true, check:true, hear:true, words:true, play:true},
  "story-order": {letter:false, undo:false, mic:true, typed:true, check:true, hear:true, words:true, play:true},
  "how-many": {letter:false, undo:false, mic:true, typed:true, check:true, hear:true, words:true, play:true},
  "same-or-different": {letter:false, undo:false, mic:true, typed:true, check:true, hear:true, words:true, play:true},
  "finish-the-line": {letter:false, undo:false, mic:true, typed:true, check:true, hear:true, words:true, play:true},
  "spell-aloud": {letter:false, undo:false, mic:true, typed:true, check:true, hear:true, words:true, play:true},
  "karaoke": {letter:false, undo:false, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "oh-behave": {letter:false, undo:false, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "heart": {letter:false, undo:false, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "idea": {letter:false, undo:false, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "fist-bump": {letter:false, undo:false, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "wow": {letter:false, undo:false, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "blow-kiss": {letter:false, undo:false, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "wink": {letter:false, undo:false, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "make-pose": {letter:false, undo:false, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "balloon": {letter:false, undo:false, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "fish": {letter:false, undo:false, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "popcorn": {letter:false, undo:false, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "mirror-hall": {letter:false, undo:false, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "ninja-weave": {letter:false, undo:false, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "fruit-cut": {letter:false, undo:false, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "air-drums": {letter:false, undo:false, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "bird-flap": {letter:false, undo:false, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "head-bop": {letter:false, undo:false, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "face-chase": {letter:false, undo:false, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "stand-sit": {letter:false, undo:false, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "dance-freeze": {letter:false, undo:false, mic:false, typed:false, check:false, hear:true, words:false, play:true},
  "rainbow-reach": {letter:false, undo:false, mic:false, typed:false, check:false, hear:true, words:false, play:true},
};
function controlsFor(gameId) {
  return GAME_CONTROLS[gameId] || NO_CONTROLS;
}
const PICTURE_EMOJI = {
  apple:"🍎",ball:"⚽",cat:"🐱",dragon:"🐉",elephant:"🐘",fish:"🐟",grape:"🍇",
  heart:"💖","ice cream":"🍦",jellyfish:"🪼",kite:"🪁",lion:"🦁",moon:"🌙",
  nest:"🪺",octopus:"🐙",popcorn:"🍿",queen:"👑",rocket:"🚀",star:"⭐",teddy:"🧸",
  umbrella:"☂️",violin:"🎻",whale:"🐋",xylophone:"🎹","yo-yo":"🪀",zebra:"🦓",
};
const state = {
  stream:null, face:null, hands:null, running:false, demo:false, lastVideoTime:-1,
  lastMpTs:0, faceData:null, handData:[], trail:[], game:null, startedAt:0,
  attempts:1, combo:0, fun:0, muted:false, age:"7-10", theme:"mix", seated:false,
  share:false, timerMs:8000, deadline:0, pausedAt:0, targetRegion:"center",
  targetExpression:"happy", object:null, phase:0, lastFaceY:null, lastHandY:null,
  beatAt:0, recognition:null, activityEvents:[], spokenPrompt:"Let's play!",
  localKey:"theodoreChildrenFunV1", roundId:0, roundDone:false, roundTimer:0,
  failTimer:0, audio:null, padHeld:false, hitCount:0, lastTip:null,
  handMotion:0, serverTts:null, speechToken:0, audioIndex:0, audioRound:null, showWords:false,
  touchMode:"air", touchLatch:{key:"",until:0}, lastTouchTips:[],
  crayon:null, ink:[], inkDown:false, screenDown:false, screenPointerId:null,
  voiceAway:false, heldPrompt:"", missingFaceAt:0, chaseLeft:false, bopDir:0, flapDir:0,
  presenceNoteUntil:0, presenceCueUntil:0, pace:"patient", lastDetectAt:0,
  glanceNote:false, poseOpen:false, standBase:null, sitLow:null,
  
  playStartedAt:0, playEndsAt:0, playTick:0, playEnded:false,
};
const PLAY_SESSION_MS = 10 * 60 * 1000;
const presenceWatch = createPresenceWatch();

const canvas = $("overlay");
const ctx = canvas ? canvas.getContext("2d") : null;
const video = $("camera");
const stage = $("stage");
const spriteLayer = $("sprite-layer");
const target = $("target");

  const letter = $("letter");
  if (letter) {
    for (const key of Object.keys(LETTER_WORDS)) {
      const option = document.createElement("option");
      option.value = key; option.textContent = `${key} — ${LETTER_WORDS[key]}`;
      letter.append(option);
    }
    if (letter.options.length) {
      letter.selectedIndex = Math.floor(Math.random() * letter.options.length);
    }
  }

// mirrored() runs for every landmark of every hand every frame; reading the
// live rect there forced dozens of synchronous layouts per frame. The observer
// already tells us when it changed, so measure once and reuse.
let stageRect = {w:0,h:0};
function stageBox() { return stageRect; }

function resizeCanvas() {
  if (!stage || !canvas || !ctx) return stageRect;
  const box = stage.getBoundingClientRect();
  stageRect = {w:box.width,h:box.height,left:box.left,top:box.top};
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  canvas.width = Math.round(box.width * dpr);
  canvas.height = Math.round(box.height * dpr);
  canvas.style.width = `${box.width}px`; canvas.style.height = `${box.height}px`;
  ctx.setTransform(dpr,0,0,dpr,0,0);
  return stageRect;
}
if (stage) new ResizeObserver(resizeCanvas).observe(stage);
video?.addEventListener("loadedmetadata", () => resizeCanvas());

function setPrompt(title, copy, speakText="") {
  const celebrating = state.roundDone && $("prompt")?.classList.contains("is-success");
  if (celebrating && title !== "You did it!") return;
  setText("prompt-title", title);
  setText("prompt-copy", copy);
  state.spokenPrompt = speakText || `${title}. ${copy}`;
}
function setStatus(text) { setText("vision-status", text); }
function clamp01(value) { return Math.max(0, Math.min(1, Number(value) || 0)); }
function randomOf(items) {
  if (!items || !items.length) return undefined;
  return items[Math.floor(Math.random() * items.length)];
}
function distance(a,b) { return Math.hypot(a.x-b.x,a.y-b.y); }
function videoFrame() {
  const {w,h} = stageBox();
  return coverFrame(w, h, video?.videoWidth || 0, video?.videoHeight || 0);
}
function videoIsMirrored() {
  if (!video) return true;
  const transform = getComputedStyle(video).transform || "";
  if (!transform || transform === "none") return false;
  const match = /matrix\(\s*(-?\d*\.?\d+)/.exec(transform);
  if (!match) return true;
  return Number(match[1]) < 0;
}
function mirrored(point) {
  // Pointer demo landmarks are already stage fractions. Flipping them parks
  // the trail on the opposite side of the cursor.
  if (state.demo) {
    const {w, h} = stageBox();
    return {
      x: (Number(point?.x) || 0) * (w || 1),
      y: (Number(point?.y) || 0) * (h || 1),
      z: Number(point?.z) || 0,
    };
  }
  const frame = videoFrame();
  if (!videoIsMirrored()) {
    const x = Number(point?.x) || 0;
    const y = Number(point?.y) || 0;
    return { x: frame.x + x * frame.w, y: frame.y + y * frame.h, z: Number(point?.z) || 0 };
  }
  return mapMirroredLandmark(point, frame);
}
// Trail samples keep the fingertip in the space it was captured, then this
// maps them again every frame. A stored pixel drifts when the camera crop
// changes; the live fingertip and the ink stay on the same point.
function trailMark(hand) {
  if (!hand?.tip) return null;
  const {w, h} = stageBox();
  if (!w || !h) return null;
  if (hand.screen || !hand.points?.[8]) {
    return {screen: true, x: hand.tip.x / w, y: hand.tip.y / h};
  }
  return {screen: false, video: true, x: hand.points[8].x, y: hand.points[8].y};
}
function trailPixel(mark) {
  if (!mark) return null;
  if (mark.screen) {
    const {w, h} = stageBox();
    return {x: mark.x * w, y: mark.y * h};
  }
  if (mark.video) return mirrored({x: mark.x, y: mark.y});
  return {x: mark.x, y: mark.y};
}
function pushTrail(hand) {
  const mark = trailMark(hand);
  const pixel = trailPixel(mark);
  const {w, h} = stageBox();
  if (!mark || !pixel || !w || !h) return;
  const prev = state.trail.length ? trailPixel(state.trail.at(-1)) : null;
  if (prev && distance(pixel, prev) <= 4) return;
  state.trail.push({...mark, nx: pixel.x / w, ny: pixel.y / h, t: performance.now()});
}
function bonePairs() {
  const raw = state.handConnections;
  if (Array.isArray(raw) && raw.length) return raw;
  return HAND_BONES;
}
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[ch]));
}

function formatPlayClock(ms) {
  const total = Math.max(0, Math.ceil(ms / 1000));
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return `${mins}:${String(secs).padStart(2, "0")}`;
}
function stopPlayClock() {
  clearInterval(state.playTick);
  state.playTick = 0;
  state.playStartedAt = 0;
  state.playEndsAt = 0;
  const clock = $("play-clock");
  if (clock) clock.hidden = true;
}
function endPlaySession() {
  if (state.playEnded) return;
  state.playEnded = true;
  clearInterval(state.playTick);
  state.playTick = 0;
  const clock = $("play-clock");
  const timeEl = $("play-clock-time");
  if (timeEl) timeEl.textContent = "0:00";
  if (clock) {
    clock.hidden = false;
    clock.classList.add("is-ended");
  }
  setPrompt("Play time is up", "Thanks for playing! Tap home to start a fresh 10-minute session.");
  tellActivity(
    "Play time ended. Thank the child in one short sentence. Do not start a new game prompt.",
    {force: true},
  );
  speak("Play time is up. Thanks for playing!");
  state.roundDone = true;
  clearTimeout(state.roundTimer);
  hideCountdown();
}
function tickPlayClock() {
  if (!state.playEndsAt) return;
  const left = state.playEndsAt - Date.now();
  const timeEl = $("play-clock-time");
  if (timeEl) timeEl.textContent = formatPlayClock(left);
  if (left <= 0) endPlaySession();
}
function armPlayClock() {
  clearInterval(state.playTick);
  state.playEnded = false;
  state.playStartedAt = Date.now();
  state.playEndsAt = state.playStartedAt + PLAY_SESSION_MS;
  const clock = $("play-clock");
  const timeEl = $("play-clock-time");
  if (timeEl) timeEl.textContent = formatPlayClock(PLAY_SESSION_MS);
  if (clock) {
    clock.hidden = false;
    clock.classList.remove("is-ended");
  }
  tickPlayClock();
  state.playTick = setInterval(tickPlayClock, 1000);
}

async function start(camera=true) {
  seedPlayAge();
  state.theme = $("theme")?.value || "mix";
  state.seated = Boolean($("seated")?.checked);
  state.share = Boolean($("share")?.checked);
  state.demo = !camera;
  // Create the effects context from the user's Start/Demo gesture. Browsers
  // may reject a later completion sound if no context was opened here.
  fxAudioContext();
  $("setup")?.classList.add("hidden");
  $("play")?.classList.remove("hidden");
  if ($("game")?.value) state.game = $("game").value;
  applyGameControls();
  stage?.classList.toggle("demo", state.demo);
  resizeCanvas(); loadLocalAnalytics();
  armPlayClock();
  if (camera) {
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("insecure-context");
      state.stream = await navigator.mediaDevices.getUserMedia({
        video:{facingMode:"user",width:{ideal:1280},height:{ideal:720}}, audio:false
      });
      if (video) {
        video.srcObject = state.stream;
        await video.play();
      }
      setStatus("Camera live · loading face & hands…");
      await initVision();
    } catch (error) {
      state.demo = true;
      setStatus(`Pointer demo · camera unavailable (${error.name || error.message || "blocked"})`);
    }
  } else {
    setStatus("Pointer demo · move over the screen");
  }
  if (state.demo) stage?.classList.add("demo");
  state.running = true;
  requestAnimationFrame(loop);
  probeSpeech();
  chooseGame();
}

async function initVision() {
  try {
    let moduleUrl=`${VISION_CDN}/+esm`,wasmUrl=`${VISION_CDN}/wasm`;
    let faceModel=`${MODEL_ROOT}/face_landmarker/face_landmarker/float16/1/face_landmarker.task`;
    let handModel=`${MODEL_ROOT}/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task`;
    try {
      // Asking for a path that is intentionally absent generated a scary 404
      // on every load. The health contract already says whether local assets
      // were mounted, so use that instead.
      // On salareen.com, /health is the orchestrator. The lab health is proxied
      // beside the page so vision_assets is the lab's answer, not the API's.
      const healthUrl=location.pathname.indexOf("/children-lab")===0?"/children-live-audio/health":"/health";
      const runtime=await fetch(healthUrl).then(response=>response.ok?response.json():null);
      if(runtime?.vision_assets==="self-hosted"){moduleUrl="/vendor/vision/tasks-vision.mjs";wasmUrl="/vendor/vision/wasm";faceModel="/vendor/vision/face_landmarker.task";handModel="/vendor/vision/hand_landmarker.task";}
    } catch (_) {}
    const vision = await import(moduleUrl);
    const files = await vision.FilesetResolver.forVisionTasks(wasmUrl);
    const delegates = ["GPU","CPU"];
    for (const delegate of delegates) {
      try {
        state.face = await vision.FaceLandmarker.createFromOptions(files, {
          baseOptions:{modelAssetPath:faceModel,delegate},
          runningMode:"VIDEO",numFaces:1,outputFaceBlendshapes:true
        });
        break;
      } catch (_) {}
    }
    for (const delegate of delegates) {
      try {
        state.hands = await vision.HandLandmarker.createFromOptions(files, {
          baseOptions:{modelAssetPath:handModel,delegate},
          runningMode:"VIDEO",numHands:2
        });
        state.handConnections = (vision.HandLandmarker.HAND_CONNECTIONS || []).map((c) => (
          Array.isArray(c) ? [c[0], c[1]] : [c.start, c.end]
        )).filter((pair) => Number.isFinite(pair[0]) && Number.isFinite(pair[1]));
        break;
      } catch (_) {}
    }
    setStatus(state.face && state.hands ? "Face + two hands ready" : "Camera ready · some gesture models unavailable");
  } catch (error) {
    setStatus("Camera live · pointer fallback (vision model unavailable)");
    console.warn("[children-lab] vision init failed", error);
  }
}

function blendshapeMap(result) {
  const out = {};
  const cats = result?.faceBlendshapes?.[0]?.categories || [];
  cats.forEach(c => { out[c.categoryName] = c.score; });
  return out;
}

function faceMetrics(points, bs) {
  if (!points?.length) return null;
  let minX=1,maxX=0,minY=1,maxY=0;
  points.forEach(p=>{minX=Math.min(minX,p.x);maxX=Math.max(maxX,p.x);minY=Math.min(minY,p.y);maxY=Math.max(maxY,p.y);});
  const leftBlink=bs.eyeBlinkLeft||0, rightBlink=bs.eyeBlinkRight||0;
  const smile=((bs.mouthSmileLeft||0)+(bs.mouthSmileRight||0))/2;
  const jaw=bs.jawOpen||0, brow=bs.browInnerUp||0, funnel=bs.mouthFunnel||0;
  let expression="neutral", confidence=0;
  if (leftBlink>.62 && rightBlink<.38) {expression="wink-left";confidence=leftBlink;}
  else if (rightBlink>.62 && leftBlink<.38) {expression="wink-right";confidence=rightBlink;}
  else if (leftBlink>.68 && rightBlink>.68) {expression="sleepy";confidence=(leftBlink+rightBlink)/2;}
  else if (jaw>.38 && brow>.2) {expression="surprised";confidence=Math.max(jaw,brow);}
  else if (funnel>.38 || (jaw>.32 && smile<.18)) {expression="mouth-o";confidence=Math.max(funnel,jaw);}
  else if (smile>.35) {expression="happy";confidence=smile;}
  const cx=1-(minX+maxX)/2, cy=(minY+maxY)/2;
  const region=Object.entries(REGIONS).sort((a,b)=>Math.hypot(cx-a[1][0],cy-a[1][1])-Math.hypot(cx-b[1][0],cy-b[1][1]))[0][0];
  const pose = headPoseFromMesh(points, (video?.videoWidth && video?.videoHeight) ? video.videoWidth / video.videoHeight : 1);
  return {
    points,bs,cx,cy,width:maxX-minX,height:maxY-minY,expression,confidence,region,smile,
    pitchDeg: pose?.pitch ?? null,
    yawDeg: pose?.yaw ?? null,
    gazeFrontal: pose?.frontal ?? null,
    gazeDown: debiasedGazeDown(bs),
  };
}

function handMetrics(points, label="") {
  const shape=handShape(points);
  if (!shape) return null;
  return {...shape, points, label, tip:mirrored(points[8]), wrist:mirrored(points[0])};
}
function heartMetrics(hands) {
  if (hands.length<2) return null;
  return heartRatios(hands[0].points, hands[1].points, (hands[0].scale+hands[1].scale)/2);
}
function isHeart(hands) {
  return isHeartShape(heartMetrics(hands));
}
function handToFaceFaces(hand, face) {
  // Distance from fingertip to the mouth, measured in face widths so it does
  // not depend on the child's distance from the camera either.
  if (!hand?.tip || !face) return Infinity;
  const {w,h}=stageBox();
  if (!w || !h) return Infinity;
  const mouth={x:face.cx*w, y:(face.cy+face.height*.28)*h};
  return distance(hand.tip,mouth)/Math.max(1e-4,face.width*w);
}

function detectFrame() {
  if ((!state.face && !state.hands) || !video || video.readyState<2) return;
  // A phone WebView often freezes video.currentTime at 0 for a camera stream.
  // Keep sampling on a clock so the finger, the trail, and a fist still move.
  const nowMs = performance.now();
  const sameStamp = video.currentTime===state.lastVideoTime;
  if (sameStamp && nowMs - (state.lastDetectAt || 0) < 40) return;
  state.lastVideoTime=video.currentTime;
  state.lastDetectAt=nowMs;
  const now=Math.max((state.lastMpTs||0)+1, performance.now());
  state.lastMpTs=now;
  try {
    if (state.face) {
      const result=state.face.detectForVideo(video,now);
      const points=result.faceLandmarks?.[0];
      state.faceData=faceMetrics(points,blendshapeMap(result));
    }
  } catch (error) { console.warn("[children-lab] face frame skipped",error); }
  try {
    if (state.hands && (!screenTouch() || state.game === "ninja-weave")) {
      const result=state.hands.detectForVideo(video,now);
      const labels=(result.handedness||[]).map(row=>row?.[0]?.categoryName||"");
      const previous=state.handData.map(hand=>hand.tip);
      state.handData=(result.landmarks||[]).map((points,i)=>handMetrics(points,labels[i])).filter(Boolean);
      state.handMotion=state.handData.reduce((max,hand,i)=>Math.max(max,previous[i]?distance(hand.tip,previous[i]):0),0);
    }
  } catch (error) { console.warn("[children-lab] hand frame skipped",error); }
}

function drawFistMark(hand) {
  if (!hand?.fist) return;
  let palm = hand.wrist;
  if (!hand.screen && hand.points?.[0] && hand.points?.[9]) {
    const wrist = mirrored(hand.points[0]);
    const knuckle = mirrored(hand.points[9]);
    palm = {x: (wrist.x + knuckle.x) / 2, y: (wrist.y + knuckle.y) / 2};
  }
  if (!palm) return;
  ctx.save();
  ctx.fillStyle = "rgba(251,113,133,.92)";
  ctx.strokeStyle = "#fff";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.arc(palm.x, palm.y, 22, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#fff";
  ctx.font = "700 12px ui-rounded, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText("fist", palm.x, palm.y);
  ctx.restore();
}
function drawVision() {
  if (!ctx) return;
  const {w,h}=stageBox();
  ctx.clearRect(0,0,w,h);
  drawPicture(w,h);
  drawGuide(w,h);
  ctx.save();ctx.lineWidth=4;ctx.lineCap="round";ctx.strokeStyle="#c4b5fd";ctx.fillStyle="#fde68a";
  if (switchedOn("show-hands")) {
    for (const hand of state.handData) {
      if (!hand.points?.length) continue;
      for (const [a,b] of bonePairs()) {
        if (!hand.points[a] || !hand.points[b]) continue;
        const p=mirrored(hand.points[a]),q=mirrored(hand.points[b]);
        ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(q.x,q.y);ctx.stroke();
      }
      for (let i=0;i<hand.points.length;i++) {
        const p=mirrored(hand.points[i]);
        ctx.fillStyle=[4,8,12,16,20].includes(i)?"#fde047":"#c4b5fd";
        ctx.beginPath();ctx.arc(p.x,p.y,[4,8,12,16,20].includes(i)?6:3,0,Math.PI*2);ctx.fill();
      }
      if (switchedOn("show-measures") && hand.tip && hand.wrist) {
        ctx.strokeStyle="#fde047";ctx.setLineDash([8,6]);ctx.beginPath();ctx.moveTo(hand.wrist.x,hand.wrist.y);ctx.lineTo(hand.tip.x,hand.tip.y);ctx.stroke();ctx.setLineDash([]);
      }
    }
  }
  if (switchedOn("show-face") && state.faceData?.points) {
    ctx.strokeStyle="#5eead4";ctx.lineWidth=2;ctx.beginPath();
    let started=false;
    for (const i of [10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109]) {
      const p=state.faceData.points[i];if(!p)continue;const q=mirrored(p);
      if(!started){ctx.moveTo(q.x,q.y);started=true;} else ctx.lineTo(q.x,q.y);
    }
    ctx.closePath();ctx.stroke();
    for (const i of [1,10,33,61,152,199,263,291,454]) {
      const p=state.faceData.points[i];if(!p)continue;const q=mirrored(p);
      ctx.fillStyle="#5eead4";ctx.beginPath();ctx.arc(q.x,q.y,3.5,0,Math.PI*2);ctx.fill();
    }
    if (switchedOn("show-measures")) {
      const left=(1-(state.faceData.cx+state.faceData.width/2))*w;
      const top=(state.faceData.cy-state.faceData.height/2)*h;
      ctx.strokeStyle="#34d399";ctx.setLineDash([10,7]);
      ctx.strokeRect(left,top,state.faceData.width*w,state.faceData.height*h);ctx.setLineDash([]);
    }
  }
  // show-trail stays checked when the phone hides the vision-tools panel.
  // A one-point stroke draws nothing, so the live fingertip is always a dot.
  if (switchedOn("show-trail")) {
    const live = pointingHand()?.tip || null;
    const pts = state.trail.map((mark) => trailPixel(mark)).filter(Boolean);
    if (live) pts.push(live);
    if (pts.length > 1) {
      ctx.lineWidth=12;ctx.lineCap="round";ctx.lineJoin="round";
      const grad=ctx.createLinearGradient(0,0,w,h);grad.addColorStop(0,"#f472b6");grad.addColorStop(.5,"#fde047");grad.addColorStop(1,"#34d399");
      ctx.strokeStyle=grad;ctx.beginPath();
      pts.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));
      ctx.stroke();
    }
    if (live) {
      ctx.fillStyle="#fde047";ctx.beginPath();ctx.arc(live.x,live.y,11,0,Math.PI*2);ctx.fill();
      ctx.strokeStyle="#fff";ctx.lineWidth=2;ctx.stroke();
    }
  }
  for (const hand of state.handData) drawFistMark(hand);
<<<<<<< HEAD
  drawMathThrowGuide();
  drawMirrorGhost(w, h);
=======
  if(state.game==="pop-quiz-toss")popQuiz.drawGuide(ctx);
>>>>>>> 2aaa58c3 (Pop Quiz Toss: quiz rounds, themed targets, curve throws, voice + throw scoring, tutorial, adult ages)
  ctx.restore();
  renderVisionReadout();
}

function drawPicture(w, h) {
  const scene = state.picture;
  if (!scene || !PICTURE_PLAY.has(state.game)) return;
  const pathOf = (points) => {
    ctx.beginPath();
    points.forEach(([x, y], index) => {
      const px = x * w;
      const py = y * h;
      if (index) ctx.lineTo(px, py);
      else ctx.moveTo(px, py);
    });
    ctx.closePath();
  };
  if (state.game === "color-picture") {
    const reach = markerRadius(state.age) * Math.min(w, h);
    scene.segments.forEach((region, index) => {
      pathOf(region.points);
      ctx.fillStyle = "rgba(255,255,255,.16)";
      ctx.fill();
      ctx.save();
      ctx.clip();
      ctx.lineWidth = reach * 2;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.strokeStyle = region.color;
      ctx.fillStyle = region.color;
      for (const stroke of state.ink || []) {
        if (stroke.colorName !== region.colorName) continue;
        const pts = stroke.points || [];
        if (!pts.length) continue;
        if (pts.length === 1) {
          ctx.beginPath();
          ctx.arc(pts[0].x * w, pts[0].y * h, reach, 0, Math.PI * 2);
          ctx.fill();
          continue;
        }
        ctx.beginPath();
        pts.forEach((point, pointIndex) => {
          const px = point.x * w;
          const py = point.y * h;
          if (pointIndex) ctx.lineTo(px, py);
          else ctx.moveTo(px, py);
        });
        ctx.stroke();
      }
      ctx.restore();
      pathOf(region.points);
      ctx.save();
      ctx.strokeStyle = region.color;
      ctx.lineWidth = 4;
      ctx.setLineDash(state.painted?.[index] ? [] : [8, 6]);
      ctx.stroke();
      ctx.restore();
      if (state.painted?.[index]) return;
      const [cx, cy] = centroid(region.points);
      const label = region.colorName;
      ctx.font = "800 16px ui-rounded, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      const box = ctx.measureText(label).width;
      ctx.fillStyle = "rgba(15,23,42,.78)";
      ctx.fillRect(cx * w - box / 2 - 8, cy * h - 13, box + 16, 26);
      ctx.fillStyle = region.color;
      ctx.fillText(label, cx * w, cy * h);
    });
    scene.segments.forEach((region, index) => {
      const spot = swatchLayout(scene.segments.length, index, w, h);
      const picked = state.crayon === region.colorName;
      ctx.beginPath();
      ctx.arc(spot.x, spot.y, picked ? 20 : 16, 0, Math.PI * 2);
      ctx.fillStyle = picked ? region.color : "#ffffff";
      ctx.fill();
      ctx.lineWidth = picked ? 6 : 4;
      ctx.strokeStyle = picked ? "#fde047" : region.color;
      ctx.stroke();
      ctx.fillStyle = "#f8fafc";
      ctx.font = "700 15px ui-rounded, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "bottom";
      ctx.fillText(region.colorName, spot.x, spot.y - 24);
    });
    return;
  }
  scene.segments.forEach((region) => {
    pathOf(region.points);
    ctx.fillStyle = `${region.color}55`;
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = "rgba(255,255,255,.4)";
    ctx.stroke();
  });
  if (state.game === "connect-dots") {
    const dots = state.pictureDots || [];
    const done = Math.min(state.dotCursor || 0, dots.length);
    if (done > 1) {
      ctx.beginPath();
      dots.slice(0, done).forEach((dot, index) => {
        const px = dot.x * w;
        const py = dot.y * h;
        if (index) ctx.lineTo(px, py);
        else ctx.moveTo(px, py);
      });
      if (done === dots.length) ctx.lineTo(dots[0].x * w, dots[0].y * h);
      ctx.strokeStyle = "#fde047";
      ctx.lineWidth = 6;
      ctx.stroke();
    }
    dots.forEach((dot, index) => {
      const px = dot.x * w;
      const py = dot.y * h;
      const next = index === state.dotCursor;
      const finished = index < state.dotCursor;
      ctx.beginPath();
      ctx.arc(px, py, next ? 22 : 16, 0, Math.PI * 2);
      ctx.fillStyle = finished ? "#22c55e" : (next ? "#fde047" : "#ffffff");
      ctx.fill();
      ctx.lineWidth = 3;
      ctx.strokeStyle = "#1e1b4b";
      ctx.stroke();
      ctx.fillStyle = "#1e1b4b";
      ctx.font = "900 16px ui-rounded, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(String(dot.n), px, py);
    });
    return;
  }
  pathOf(scene.outline);
  ctx.strokeStyle = "#f8fafc";
  ctx.lineWidth = 8;
  ctx.setLineDash([14, 10]);
  ctx.stroke();
  ctx.setLineDash([]);
}

function drawGuide(w,h) {
  if (!switchedOn("show-guide") || !["trace-letter","trace-picture"].includes(state.game)) return;
  const letter=$("letter").value;
  ctx.save();ctx.textAlign="center";ctx.textBaseline="middle";ctx.lineJoin="round";
  if (state.game==="trace-letter") {
    ctx.font=`900 ${Math.min(w,h)*.62}px ui-rounded, sans-serif`;
    ctx.lineWidth=state.age==="4-6"?38:26;ctx.strokeStyle="#ffffff88";ctx.setLineDash([16,12]);
    ctx.strokeText(letter,w/2,h/2+20);
  } else {
    ctx.font=`${Math.min(w,h)*.5}px serif`;ctx.globalAlpha=.68;
    const emoji=PICTURE_EMOJI[LETTER_WORDS[letter]]||"✨";
    ctx.fillText(emoji,w/2,h/2+10);
  }
  ctx.setLineDash([]);ctx.fillStyle="#fde047";ctx.beginPath();ctx.arc(w*.31,h*.2,10,0,Math.PI*2);ctx.fill();ctx.restore();
}

function updateTrace() {
  if (state.game === "trace-picture") {
    if (!state.picture || state.roundDone || performance.now() < (state.traceHoldUntil || 0)) return;
    strokeOutline(state.picture, "You traced the picture!");
    return;
  }
  if (state.game !== "trace-letter") return;
  if (state.roundDone || performance.now() < (state.traceHoldUntil || 0)) return;
  const hand = pointingHand();
  if (!hand?.tip) return;
  const {w,h}=stageBox();
  if (!w || !h) return;
  pushTrail(hand);
  const normalized = state.trail.map((pt) => ({x:pt.nx, y:pt.ny}));
  const progress=traceProgress(normalized,state.age);
  if (progress.passed) succeed("Beautiful tracing!");
}

function bestAirHand() {
  let chosen = null;
  let reach = -1;
  for (const hand of state.handData) {
    if (!hand || hand.screen || !hand.points) continue;
    const ids = activeFingertips(hand.points, state.age);
    if (!ids.length) continue;
    const wrist = hand.wrist;
    for (const id of ids) {
      const point = mirrored(hand.points[id]);
      if (!point) continue;
      const span = wrist ? distance(point, wrist) : 1;
      if (span > reach) {
        reach = span;
        chosen = {...hand, tip: point};
      }
    }
  }
  return chosen;
}
function pointingHand() {
  // Screen touch is a finger on the glass. Air touch follows any fingertip
  // that is out, including a point held while the other fingers make a fist.
  if (screenTouch()) {
    return state.screenDown ? (state.handData.find((hand) => hand.screen) || null) : null;
  }
  return bestAirHand();
}
function fingerPoint() {
  return fingerPointFrom(pointingHand());
}

function inkFor(colorName) {
  const points = [];
  for (const stroke of state.ink || []) {
    if (stroke.colorName === colorName) points.push(...stroke.points);
  }
  return points;
}

function colorLiftCopy() {
  return screenTouch()
    ? "Lift your finger to stop."
    : "A fist stops the marker.";
}

function refreshColorPrompt(speakIt) {
  const word = state.picture?.word || "picture";
  const colors = colorLine(state.picture);
  const copy = state.crayon
    ? `Scratch ${state.crayon} like a marker. ${colorLiftCopy()}`
    : `Pick a color first. ${colors}. Scratch inside the shape. ${colorLiftCopy()}`;
  setPrompt(`Color the ${word}`, copy, `Color the ${word}. ${copy}`);
  if (speakIt) {
    tellActivity(state.spokenPrompt);
    speak(state.spokenPrompt);
  }
}

function coloringHand() {
  if (screenTouch()) {
    return state.screenDown ? (state.handData.find((hand) => hand.screen) || null) : null;
  }
  return bestAirHand();
}

function updateColoring() {
  const scene = state.picture;
  const hand = coloringHand();
  const tip = hand?.tip ? fingerPointFrom(hand) : null;
  if (!scene || !tip) {
    state.inkDown = false;
    return;
  }
  const {w, h} = stageBox();
  for (let index = 0; index < scene.segments.length; index += 1) {
    if (!swatchHit(scene.segments.length, index, tip.px, tip.py, w, h)) continue;
    const next = scene.segments[index].colorName;
    state.inkDown = false;
    if (state.crayon !== next) {
      state.crayon = next;
      refreshColorPrompt(true);
    }
    return;
  }
  if (!state.crayon || !hand?.tip) {
    state.inkDown = false;
    return;
  }
  const index = segmentAt(scene, tip.x, tip.y);
  const region = index >= 0 ? scene.segments[index] : null;
  if (!region || region.colorName !== state.crayon) {
    state.inkDown = false;
    return;
  }
  if (!state.inkDown || state.ink.at(-1)?.colorName !== state.crayon) {
    state.ink.push({colorName: state.crayon, points: []});
    state.inkDown = true;
  }
  const stroke = state.ink.at(-1);
  const last = stroke.points.at(-1);
  if (!last || Math.hypot(last.x - tip.x, last.y - tip.y) > 0.008) {
    stroke.points.push({x: tip.x, y: tip.y});
  }
  const radius = markerRadius(state.age);
  state.painted = scene.segments.map((part) => scratchPassed(
    scratchCoverage(inkFor(part.colorName), part.points, radius),
    state.age,
  ));
  if (state.painted.every(Boolean)) succeed("Beautiful coloring!");
}

function fingerPointFrom(hand) {
  if (!hand?.tip) return null;
  const {w, h} = stageBox();
  if (!w || !h) return null;
  return {x: hand.tip.x / w, y: hand.tip.y / h, px: hand.tip.x, py: hand.tip.y};
}

function updatePicturePlay() {
  if (!PICTURE_PLAY.has(state.game)) return;
  if (state.roundDone || performance.now() < (state.traceHoldUntil || 0)) return;
  const scene = state.picture;
  if (!scene) return;
  if (state.game === "color-picture") {
    updateColoring();
    return;
  }
  const tip = fingerPoint();
  if (!tip) return;
  if (state.game === "connect-dots") {
    const dots = state.pictureDots || [];
    const next = dots[state.dotCursor];
    if (!dotHit(next, tip.x, tip.y, dotRadius(state.age))) return;
    const claim = claimTouch(state.touchLatch, `dot:${next.n}`, performance.now(), 280);
    state.touchLatch = claim.latch;
    if (!claim.claimed) return;
    state.dotCursor += 1;
    if (state.dotCursor >= dots.length) succeed("You connected every number!");
    return;
  }
  strokeOutline(scene, "You traced the picture!");
}

function strokeOutline(scene, doneMessage) {
  const hand = pointingHand();
  const tip = fingerPointFrom(hand);
  if (!tip || !scene) return;
  pushTrail(hand);
  const coverage = outlineCoverage(
    state.trail.map((point) => ({x: point.nx, y: point.ny})),
    scene.outline,
    state.age === "4-6" ? 0.07 : 0.05,
  );
  if (state.trail.length >= 8 && outlinePassed(coverage, state.age)) succeed(doneMessage);
}

function faceDistanceLabel(face) {
  if (!face) return "waiting";
  if (face.width<.18) return "far";
  if (face.width>.48) return "very close";
  return "good";
}

function renderVisionReadout() {
  const face=state.faceData, hands=state.handData;
  $("vision-readout")?.classList.toggle("hidden",!switchedOn("show-readout"));
  setText("face-readout",face?`Face: ${face.expression} · ${Math.round(face.confidence*100)}%`:"Face: not detected");
  setText("hand-readout",hands.length?`Hands: ${hands.length} · fingers ${hands.map(hand=>hand.count).join("/")}`:"Hands: not detected");
  setText("distance-readout",`Distance: ${faceDistanceLabel(face)}${face?` · face ${Math.round(face.width*100)}%`:""}`);
  setText("motion-readout",`Motion: ${state.handMotion.toFixed(1)} px/frame`);
  const normalized=state.trail.map(point=>({x:point.nx,y:point.ny}));
  const progress=traceProgress(normalized,state.age);
  setText("trace-readout",`Trace: ${progress.percent}% · ${state.trail.length} points`);
  setText("game-readout",`Gesture: ${gestureReadout()}`);
}

// Live measurement vs the threshold for the current game, so an adult testing
// the lab can see whether a gesture is close or nowhere near, instead of
// guessing why a round will not pass.
function gestureReadout() {
  const hands=state.handData, face=state.faceData;
  const near=(value)=>Number.isFinite(value)?value.toFixed(2):"–";
  switch (state.game) {
    case "heart": {
      const m=heartMetrics(hands);
      if (!m) return `need 2 hands (have ${hands.length})`;
      return `tips ${near(m.tips)}/<${HEART_TIPS_PALMS} · thumbs ${near(m.thumbs)}/<${HEART_THUMBS_PALMS} · cleft ${near(m.cleft)}/>${HEART_CLEFT_PALMS} · point ${near(m.point)}/>${HEART_POINT_PALMS} · wrists ${near(m.wrists)}/>${HEART_WRISTS_PALMS}`;
    }
    case "fist-bump":
      if (!hands.length) return "no hand";
      return `fist ${hands.some(h=>h.fist)?"yes":"no"} · fingers ${hands.map(h=>h.count).join("/")} · tip ${near(hands[0].tipPalms)}/<${FIST_MAX_PALMS} palms · bump ${hands[0].tip?Math.round(distance(hands[0].tip,targetPoint())):"–"}px`;
    case "idea":
      return hands.length?`index-only ${hands.some(h=>h.indexUp)?"yes":"no"} · fingers ${hands.map(h=>h.count).join("/")}`:"no hand";
    case "blow-kiss": {
      if (!face) return "face not tracked";
      const nearest=Math.min(...hands.map(hand=>handToFaceFaces(hand,face)));
      return state.phase===0
        ? `step 1 · hand ${near(nearest)}/<${KISS_NEAR_FACES} faces · mouth-o ${face.expression==="mouth-o"?"yes":"no"}`
        : `step 2 · hand ${near(nearest)}/>${KISS_AWAY_FACES} faces`;
    }
    case "wow": case "wink": case "oh-behave":
      return face?`${face.expression} ${Math.round(face.confidence*100)}% (need 55%)${state.game==="oh-behave"?` · ${face.region}/${state.targetRegion}`:""}`:"face not tracked";
    case "make-pose":
      return `hands ${hands.length}/2 high ${hands.filter(h=>h.wrist&&h.wrist.y<stageBox().h*.48).length}`;
    case "face-chase":
      return face?`region ${face.region} (need ${state.targetRegion})`:"face not tracked";
    case "air-drums":
      return `hits ${state.hitCount}/6 · pad ${state.padHeld?"held":"open"}`;
    case "bird-flap":
      return `hands ${hands.length}/2 · flaps ${state.hitCount}/8`;
    case "head-bop":
      return face?`bops ${state.hitCount}/7`:"face not tracked";
    case "stand-sit":
      return face?`phase ${state.phase} · face y ${face.cy.toFixed(2)}`:"face not tracked";
    case "rainbow-reach":
      return `hands ${hands.length}/2`;
    case "dance-freeze":
      return `${state.phase===0?"dance":"freeze"} · motion ${state.handMotion.toFixed(1)}`;
    case "mirror-hall": {
      const pose = state.mirror ? mirrorPose(state.mirror.index, {seated: state.seated}) : null;
      const pace = mirrorPace(state.mirror?.pace);
      return pose ? `${pose.prompt} · beat ${(state.mirror.index || 0) + 1}/${MIRROR_ROUTINE.length} · ${pace.id}` : "waiting";
    }
    case "ninja-weave": {
      const technique = ninjaTechnique(state.ninja?.technique);
      const expected = technique.sequence[state.ninja?.index || 0];
      const hands = airHands();
      const {w: width, h: height} = stageBox();
      const seen = recognizeNinjaSeal(hands, width, height);
      const close = expected && seen !== expected
        && ninjaSealFits(hands, expected, width, height, {mirrorOk: state.ninja?.pace === "easy"});
      return `seal ${close ? `${expected} close` : (seen || "none")} · need ${expected || "finish"} · ${(state.ninja?.index || 0)}/${technique.sequence.length}`;
    }
    case "fruit-cut": case "balloon": case "fish": case "popcorn":
      return `${state.object?.hit?"hit":"seeking"} · ${state.game==="popcorn"?"mouth-o":"index"}`;
    case "say-letter":
      return `say ${$("letter")?.value||"?"}`;
    case "trace-letter": case "trace-picture":
      return `${progressLabel()} · index-up ${hands.some(h=>h.indexUp)?"yes":"no"}`;
    case "color-picture":
      return `crayon ${state.crayon||"pick one"} · scratched ${(state.painted||[]).filter(Boolean).length}/${state.picture?.segments.length||0}`;
    case "connect-dots":
      return `dot ${Math.min((state.dotCursor||0)+1, state.pictureDots?.length||0)}/${state.pictureDots?.length||0}`;
    case "trace-outline":
      return `${progressLabel()} outline`;
    default:
      return state.game?`${state.game} · hands ${hands.length} · face ${face?"yes":"no"}`:"choose a game";
  }
}
function progressLabel() {
  const progress=traceProgress(state.trail.map(p=>({x:p.nx,y:p.ny})),state.age);
  return `${progress.percent}%`;
}

function updateGuideLayer() {
  const enabled=switchedOn("show-guide")&&["trace-letter","trace-picture"].includes(state.game);
  $("guide-layer")?.classList.toggle("hidden",!enabled);
  const glyph=$("guide-glyph");
  if (!enabled || !glyph) return;
  const letter=$("letter").value, picture=state.game==="trace-picture";
  glyph.textContent=picture?(PICTURE_EMOJI[LETTER_WORDS[letter]]||"✨"):letter;
  glyph.classList.toggle("picture",picture);
}

function setTarget(region,content,kind="") {
  const [x,y]=REGIONS[region]||REGIONS.center;
  target.className=`target ${kind}`.trim();target.textContent=content;
  const {w,h}=stageBox();
  const size=target.offsetWidth||145;
  const half=size/2;
  // Keep the circle on the stage. A fixed 72px inset pushes it off a phone.
  if (!w || !h) {
    target.style.left=`calc(${x*100}% - ${half}px)`;
    target.style.top=`calc(${y*100}% - ${half}px)`;
    return;
  }
  const left=Math.min(Math.max(x*w, half), Math.max(half, w-half));
  const top=Math.min(Math.max(y*h, half), Math.max(half, h-half));
  target.style.left=`${left-half}px`;
  target.style.top=`${top-half}px`;
}
function hideTarget(){if(!target)return;target.classList.add("hidden");target.textContent="";}

function spawnObject(kind,content) {
  if (!spriteLayer) return null;
  for (const node of [...spriteLayer.querySelectorAll(".sprite")]) node.remove();
  const el=document.createElement("div");el.className=`sprite ${kind}`;el.textContent=content;
  el.style.top=`${15+Math.random()*55}%`;if(kind==="balloon")el.style.left=`${10+Math.random()*75}%`;
  spriteLayer.append(el);state.object={el,kind,hit:false,roundId:state.roundId};return el;
}

function freezeSprite(el) {
  if (!el || !stage) return {x:0,y:0};
  const root=stage.getBoundingClientRect(),rect=el.getBoundingClientRect();
  const x=rect.left-root.left+rect.width/2,y=rect.top-root.top+rect.height/2;
  // Hold animation:none until travel classes are stripped, or fly/rise/swim
  // would restart the instant the inline style is cleared.
  el.style.animation="none";
  el.style.left=`${x}px`;el.style.top=`${y}px`;
  el.style.transform="translate(-50%, -50%)";
  return {x,y};
}

function playSpriteReaction(el, extraClass) {
  el.classList.remove("fruit","balloon","fish","kernel");
  el.classList.add(extraClass);
  void el.offsetWidth;
  el.style.animation="";
}

function burstAt(x,y,glyph) {
  if (!spriteLayer || !glyph) return;
  const spark=document.createElement("div");
  spark.className="hit-burst";spark.textContent=glyph;
  spark.style.left=`${x}px`;spark.style.top=`${y}px`;
  spriteLayer.append(spark);
  setTimeout(()=>{if(spark.isConnected)spark.remove();},700);
}

function reactToHit(game) {
  const el=state.object?.el;if(!el)return;
  const pos=freezeSprite(el);
  const reactions={
    "fruit-cut":{cls:"sliced",burst:"💥",say:"Sliced!"},
    balloon:{cls:"popped",burst:"💥",emoji:"💥",say:"Popped!"},
    fish:{cls:"caught-fish",burst:"✨",say:"Caught!"},
    popcorn:{cls:"eaten",burst:"😋",say:"Yum!"},
  };
  const react=reactions[game]||{cls:"sliced",burst:"✨",say:"Great catch!"};
  const toward=game==="popcorn"&&state.faceData
    ?{x:state.faceData.cx*stageBox().w,y:state.faceData.cy*stageBox().h}
    :(state.handData.find(h=>h.tip)?.tip||pos);
  el.style.setProperty("--react-x",`${toward.x}px`);
  el.style.setProperty("--react-y",`${toward.y}px`);
  if(react.emoji)el.textContent=react.emoji;
  el.classList.add("hit","caught");
  playSpriteReaction(el, react.cls);
  burstAt(pos.x,pos.y,react.burst);
  setTimeout(()=>{if(el.isConnected)el.remove();},650);
  return react.say;
}

function fadeMissedObject() {
  const el=state.object?.el;if(!el||el.classList.contains("caught"))return;
  freezeSprite(el);
  playSpriteReaction(el, "missed");
  setTimeout(()=>{if(el.isConnected)el.remove();},600);
}

function objectCenter() {
  const rect=state.object?.el?.getBoundingClientRect(),root=stage.getBoundingClientRect();
  return rect?{x:rect.left-root.left+rect.width/2,y:rect.top-root.top+rect.height/2}:null;
}

function catchRadius() {
  const {w,h}=stageBox();
  return catchRadiusPx(Math.min(w || 0, h || 0), state.age);
}
function touchPoints() {
  if (screenTouch()) {
    if (!state.screenDown) return [];
    const hand = state.handData.find((row) => row.screen);
    return hand?.tip ? [hand.tip] : [];
  }
  const tips = [];
  for (const hand of state.handData) {
    if (!hand || hand.screen || !hand.points) continue;
    for (const id of activeFingertips(hand.points, state.age)) {
      const point = mirrored(hand.points[id]);
      if (point) tips.push(point);
    }
  }
  return tips;
}

function updateObjectGame() {
  if (state.roundDone) return;
  if (!OBJECT_GAMES.has(state.game) || !state.object?.el?.isConnected) return;
  const center=objectCenter();if(!center)return;
  const radius=catchRadius();
  let hit=false;
  if (state.game==="popcorn" && !screenTouch()) {
    if (state.faceData?.expression==="mouth-o") {
      const box=stageBox(),face={x:state.faceData.cx*box.w,y:state.faceData.cy*box.h};
      // Catch radius follows the face, so a child sitting back is not penalised.
      hit=distance(face,center)<Math.max(radius,state.faceData.width*box.w*.75);
    }
  } else {
    const tips = touchPoints();
    const previous = state.lastTouchTips || [];
    state.lastTouchTips = tips.map((tip) => ({x: tip.x, y: tip.y}));
    hit = tips.some((tip) => {
      if (!tipHitsTarget([tip], center, radius)) return false;
      // A tap on the glass is the catch. Air fruit still has to slice.
      if (state.game !== "fruit-cut" || screenTouch()) return true;
      if (!previous.length) return false;
      let nearest = Infinity;
      for (const prev of previous) nearest = Math.min(nearest, distance(tip, prev));
      return nearest > 10;
    });
  }
  if(hit && !state.object.hit){
    const claim = claimTouch(state.touchLatch, `object:${state.game}`, performance.now(), 420);
    state.touchLatch = claim.latch;
    if (!claim.claimed) return;
    state.object.hit=true;
    hideCountdown();
    const say=reactToHit(state.game)||"Great catch!";
    const round=state.roundId;
    setTimeout(()=>{if(state.roundId===round)succeed(say);},280);
  }
}

// Pop Quiz Toss lives in pop_quiz_game.js; these thin wrappers keep the lab's
// existing hooks (update loop, touch fallback, cancel) pointing at it.
const popQuiz = createPopQuizGame({
  state, $, stage, spriteLayer, stageBox, catchRadius,
  setPrompt, tellActivity, speak, calculateFun, renderScore, recordEvent,
  chooseGame: () => chooseGame(),
});
window.__popQuiz = popQuiz; // read-only status for tests
function cancelQuizThrow() { popQuiz.cancelThrow(); }
function updatePopQuizToss(now = performance.now(), handOverride = null) { popQuiz.update(now, handOverride); }
function armPopQuiz(roundId) { return popQuiz.arm(roundId); }

function hitAirDrums(now) {
  const hitting = tipHitsTarget(touchPoints(), targetPoint(), catchRadius());
  if (hitting && !state.padHeld) {
    const claim = claimTouch(state.touchLatch, "air-drums", now, 280);
    state.touchLatch = claim.latch;
    if (claim.claimed) {
      state.padHeld = true;
      state.hitCount += 1;
      if (state.hitCount >= 6) succeed("Amazing air drums!");
    }
  }
  if (!hitting) state.padHeld = false;
}
function airHands() {
  return state.handData.filter((hand) => !hand.screen);
}
function noteMissingFace(now) {
  if (state.faceData) {
    state.missingFaceAt = 0;
    return false;
  }
  if (!state.missingFaceAt) state.missingFaceAt = now;
  return true;
}
function poseCommit(active) {
  if (!active) {
    state.poseOpen = true;
    return false;
  }
  return Boolean(state.poseOpen);
}
function regionOtherThan(current) {
  const keys = Object.keys(REGIONS).filter((key) => key !== current && (!state.seated || !key.startsWith("bottom")));
  return randomOf(keys) || "top";
}
function ensureMirrorPace() {
  const select = $("mirror-pace");
  if (select && select.dataset.touched !== "1") {
    const next = defaultMirrorPace(state.age);
    if ([...select.options].some((opt) => opt.value === next)) select.value = next;
  }
  state.mirrorPace = mirrorPace(select?.value || defaultMirrorPace(state.age)).id;
}
function mirrorClick() {
  if (state.muted) return;
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) return;
  try {
    if (!state.mirrorAudio) state.mirrorAudio = new AudioCtx();
    const audio = state.mirrorAudio;
    if (audio.state === "suspended") audio.resume().catch(() => {});
    const osc = audio.createOscillator();
    const gain = audio.createGain();
    osc.frequency.value = 880;
    const t = audio.currentTime;
    gain.gain.setValueAtTime(0.0001, t);
    gain.gain.exponentialRampToValueAtTime(0.07, t + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.12);
    osc.connect(gain);
    gain.connect(audio.destination);
    osc.start(t);
    osc.stop(t + 0.13);
  } catch (_) {}
}
function mirrorLiveNormalized() {
  const {w, h} = stageBox();
  if (!w || !h) return {head: null, left: null, right: null};
  let head = null;
  if (state.demo && state.faceData && Number.isFinite(state.faceData.cx)) {
    head = {x: state.faceData.cx, y: state.faceData.cy};
  } else if (state.faceData?.points?.length) {
    const nose = state.faceData.points[1] || state.faceData.points[0];
    const pixel = mirrored(nose);
    if (pixel) head = {x: pixel.x / w, y: pixel.y / h};
  } else if (state.faceData && Number.isFinite(state.faceData.cx)) {
    head = {x: state.faceData.cx, y: state.faceData.cy};
  }
  const hands = airHands().filter((hand) => hand?.tip && Number.isFinite(hand.tip.x));
  const sorted = [...hands].sort((a, b) => a.tip.x - b.tip.x);
  const norm = (hand) => ({x: hand.tip.x / w, y: hand.tip.y / h});
  return {
    head,
    left: sorted.length ? norm(sorted[0]) : null,
    right: sorted.length >= 2 ? norm(sorted[sorted.length - 1]) : null,
  };
}
function drawMirrorGhost(w, h) {
  if (!ctx || state.game !== "mirror-hall" || !state.mirror || !w || !h) return;
  const pose = mirrorPose(state.mirror.index, {seated: state.seated});
  const pace = mirrorPace(state.mirror.pace);
  const radius = pace.radius * Math.min(w, h);
  const spot = (point) => ({x: point.x * w, y: point.y * h});
  const head = spot(pose.head);
  const left = spot(pose.left);
  const right = spot(pose.right);
  ctx.save();
  ctx.lineCap = "round";
  ctx.strokeStyle = "rgba(253, 224, 71, .9)";
  ctx.lineWidth = 6;
  ctx.beginPath();
  ctx.moveTo(left.x, left.y);
  ctx.lineTo(head.x, head.y);
  ctx.lineTo(right.x, right.y);
  ctx.stroke();
  for (const light of [head, left, right]) {
    ctx.beginPath();
    ctx.arc(light.x, light.y, radius, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(253, 224, 71, .22)";
    ctx.fill();
    ctx.lineWidth = 4;
    ctx.strokeStyle = "#fde68a";
    ctx.stroke();
  }
  ctx.restore();
}
function armMirrorBeat(now) {
  const run = state.mirror;
  if (!run || run.finished) return;
  const pose = mirrorPose(run.index, {seated: state.seated});
  run.windowStart = now;
  run.matchedSince = null;
  mirrorClick();
  const seatedNote = state.seated ? " Seated targets stay up high." : "";
  setPrompt(
    pose.prompt,
    `Match the lights.${seatedNote} Beat ${run.index + 1} of ${MIRROR_ROUTINE.length}.`,
    `Match the lights. ${pose.prompt}.`,
  );
}
function noteMirrorPause(now) {
  const run = state.mirror;
  if (state.game !== "mirror-hall" || !run || run.finished || run.pausedAt) return;
  run.pausedAt = now;
}
function finishMirrorHall() {
  const summary = mirrorSummary(state.mirror);
  succeed(`${summary.stars} stars. ${summary.line}`);
  state.combo = summary.bestCombo;
  setText("combo", `Combo ${summary.bestCombo}`);
  setText("stars", `${"★".repeat(summary.stars)}${"☆".repeat(3 - summary.stars)}`);
}
function updateMirrorHall(now) {
  const run = state.mirror;
  if (!run || run.finished || state.roundDone) return;
  if (run.pausedAt) {
    const delta = now - run.pausedAt;
    if (Number.isFinite(run.windowStart)) run.windowStart += delta;
    if (Number.isFinite(run.matchedSince)) run.matchedSince += delta;
    run.pausedAt = 0;
  }
  const pose = mirrorPose(run.index, {seated: state.seated});
  const pace = mirrorPace(run.pace);
  const matched = mirrorBeatMatched(mirrorLiveNormalized(), pose, pace.radius);
  const step = advanceMirrorBeat(run, {matched, now});
  state.mirror = step;
  if (step.event === "done") {
    finishMirrorHall();
    return;
  }
  if (step.event === "hit" || step.event === "miss") {
    state.combo = step.combo;
    setText("combo", `Combo ${step.combo}`);
    armMirrorBeat(now);
    return;
  }
  if (step.event === "retry") {
    mirrorClick();
    setPrompt(pose.prompt, "Try once more. Match the lights.", `Match the lights. ${pose.prompt}.`);
  }
}
function ensureNinjaPace() {
  const select = $("mirror-pace");
  if (select && select.dataset.touched !== "1") {
    const next = defaultMirrorPace(state.age);
    if ([...select.options].some((opt) => opt.value === next)) select.value = next;
  }
  return mirrorPace(select?.value || defaultMirrorPace(state.age)).id;
}
function ninjaPrompt(copy = "A few matching glimpses count. Pause or correct a mistake whenever you need.") {
  const run = state.ninja;
  if (!run) return;
  const technique = ninjaTechnique(run.technique);
  const sealId = technique.sequence[run.index];
  const seal = NINJA_SEALS[sealId];
  setPrompt(
    `${technique.glyph} ${technique.label} ${run.index + 1}/${technique.sequence.length} · ${seal.glyph} ${seal.label}`,
    `${seal.how} ${copy}`,
    `${seal.label}. ${seal.how} ${copy}`,
  );
}
const NINJA_PROGRESS_KEY = "theodoreNinjaWeaveV1";
function ninjaProgress() {
  try {
    const saved = JSON.parse(localStorage.getItem(NINJA_PROGRESS_KEY) || "[]");
    return new Set(Array.isArray(saved) ? saved.filter((id) => NINJA_TECHNIQUES[id]) : []);
  } catch (_) {
    return new Set();
  }
}
function saveNinjaProgress(id) {
  const done = ninjaProgress();
  done.add(id);
  try { localStorage.setItem(NINJA_PROGRESS_KEY, JSON.stringify([...done])); } catch (_) {}
  return done;
}
function fillNinjaTechniques(selected = "") {
  const elementSelect = $("ninja-element");
  const techniqueSelect = $("ninja-technique");
  if (!elementSelect || !techniqueSelect) return;
  if (!elementSelect.options.length) {
    elementSelect.replaceChildren(...Object.values(NINJA_ELEMENTS).map((element) => {
      const option = document.createElement("option");
      option.value = element.id;
      option.textContent = `${element.glyph} ${element.label}`;
      return option;
    }));
  }
  const wanted = NINJA_TECHNIQUES[selected] || NINJA_TECHNIQUES[techniqueSelect.value];
  if (wanted) elementSelect.value = wanted.element;
  const done = ninjaProgress();
  const list = ninjaTechniqueList(elementSelect.value || "fire");
  techniqueSelect.replaceChildren(...list.map((technique) => {
    const option = document.createElement("option");
    option.value = technique.id;
    option.textContent = `${done.has(technique.id) ? "★ " : ""}${technique.label} · ${technique.sequence.length} signs`;
    return option;
  }));
  techniqueSelect.value = wanted && wanted.element === elementSelect.value ? wanted.id : (list[0]?.id || NINJA_DEFAULT_TECHNIQUE);
  setText("ninja-progress", `★ ${done.size}/${Object.keys(NINJA_TECHNIQUES).length}`);
}
function nextNinjaTechnique(id) {
  const ids = Object.values(NINJA_ELEMENTS).flatMap((element) => ninjaTechniqueList(element.id).map((t) => t.id));
  const at = ids.indexOf(id);
  return ids[(at + 1) % ids.length] || NINJA_DEFAULT_TECHNIQUE;
}
function renderNinjaSequence() {
  let row = spriteLayer.querySelector(".ninja-sequence");
  if (!state.ninja || state.game !== "ninja-weave") {
    row?.remove();
    return;
  }
  if (!row) {
    row = document.createElement("div");
    row.className = "ninja-sequence";
    spriteLayer.append(row);
  }
  const technique = ninjaTechnique(state.ninja.technique);
  row.replaceChildren(...technique.sequence.map((sealId, index) => {
    const chip = document.createElement("span");
    const seal = NINJA_SEALS[sealId];
    const first = document.createElement("i");
    const second = document.createElement("i");
    first.textContent = seal.glyphA;
    second.textContent = seal.glyphB;
    chip.append(first, second);
    chip.title = `${seal.label}: ${seal.how}`;
    chip.setAttribute("aria-label", seal.label);
    const status = index < state.ninja.index ? "done" : index === state.ninja.index ? "active" : "";
    chip.className = `place-${seal.placement} ${status}`.trim();
    return chip;
  }));
}
function startNinjaWeave() {
  if (screenTouch()) setTouchMode("air");
  if (!$("ninja-technique")?.options.length) fillNinjaTechniques();
  const technique = ninjaTechnique($("ninja-technique")?.value || NINJA_DEFAULT_TECHNIQUE);
  const pace = ensureNinjaPace();
  state.ninja = freshNinjaRun(technique.id, pace);
  state.ninja.stepStartedAt = performance.now();
  state.combo = 0;
  renderScore();
  renderNinjaSequence();
  ninjaPrompt();
  ninjaSound("start", technique.id);
}
function finishNinjaWeave() {
  const run = state.ninja;
  const technique = ninjaTechnique(run?.technique);
  state.combo = run?.bestCombo || 0;
  renderScore();
  launchNinjaEffect(technique.id);
  ninjaSound("finish", technique.id);
  saveNinjaProgress(technique.id);
  fillNinjaTechniques(nextNinjaTechnique(technique.id));
  succeed(`${technique.label}! ${technique.sequence.length} signs complete with a ${run?.bestCombo || 0}-sign combo.`);
}
function updateNinjaWeave(now) {
  const run = state.ninja;
  if (!run || run.finished || state.roundDone) return;
  if (run.pausedAt) {
    const delta = now - run.pausedAt;
    if (Number.isFinite(run.stepStartedAt)) run.stepStartedAt += delta;
    if (Number.isFinite(run.holdSince)) run.holdSince += delta;
    if (Number.isFinite(run.holdBrokenAt)) run.holdBrokenAt += delta;
    if (Number.isFinite(run.lastMatchedAt)) run.lastMatchedAt += delta;
    if (Number.isFinite(run.releaseSince)) run.releaseSince += delta;
    run.pausedAt = 0;
  }
  const hands = airHands();
  const {w: width, h: height} = stageBox();
  const technique = ninjaTechnique(run.technique);
  const expected = technique.sequence[run.index];
  const seal = ninjaSealFits(hands, expected, width, height, {mirrorOk: run.pace === "easy"})
    ? expected
    : recognizeNinjaSeal(hands, width, height);
  const previousEvent = run.event;
  const step = advanceNinjaWeave(run, {seal, now});
  state.ninja = step;
  if (step.event === "done") {
    renderNinjaSequence();
    finishNinjaWeave();
    return;
  }
  if (step.event === "step") {
    state.combo = step.combo;
    renderScore();
    renderNinjaSequence();
    ninjaSound("step", step.technique);
    ninjaPrompt("Good. Relax your hands. Start the next sign whenever you are ready.");
  } else if (step.event === "wrong" && previousEvent !== "wrong") {
    ninjaPrompt("That is okay. Adjust toward the highlighted sign; your earlier matches still count.");
  }
}
function updateGestureGame(now) {
  if (state.roundDone || state.voiceAway) return;
  if (state.game==="heart" && poseCommit(isHeart(airHands()))) succeed("A heart made with two hands!");
  else if (state.game==="idea" && poseCommit(airHands().some(h=>h.indexUp))) succeed("What a bright idea!");
  else if (state.game==="fist-bump") {
    const fist=airHands().find(h=>h.fist);
    const near = Boolean(fist && distance(fist.tip, targetPoint())<catchRadius());
    if (poseCommit(near)) succeed("Fist bump!");
  }
  else if (state.game==="wow") {
    if (noteMissingFace(now)) return;
    if (poseCommit(state.faceData?.expression==="surprised")) succeed("That is a wonderful wow face!");
  }
  else if (state.game==="wink") {
    if (noteMissingFace(now)) return;
    if (poseCommit(Boolean(state.faceData?.expression?.startsWith("wink-")))) succeed("Wink-tastic!");
  }
  else if (state.game==="blow-kiss") {
    // The old version succeeded as soon as the hand was no longer "near" the
    // face — which also happened when the face left the frame, so the round
    // passed itself. Both steps now require a tracked face, and the hand has to
    // actually travel outward rather than merely stop being close.
    if (!state.faceData) {
      noteMissingFace(now);
      return;
    }
    const nearest=Math.min(...state.handData.map(hand=>handToFaceFaces(hand,state.faceData)));
    if (state.phase===0) {
      if (Number.isFinite(nearest) && nearest<KISS_NEAR_FACES && state.faceData.expression==="mouth-o") {
        state.phase=1;
        setPrompt("Now send it!","Sweep your hand away to send the kiss flying.");
      }
    } else if (state.phase===1 && state.handData.length && nearest>KISS_AWAY_FACES) {
      succeed("A lovely flying kiss!");
    }
  } else if (state.game==="make-pose") {
    const hands = airHands();
    const high = hands.length>=2 && hands.filter(h=>h.wrist && h.wrist.y<stageBox().h*.48).length>=2;
    if (poseCommit(high)) succeed("Hero pose complete!");
  }
  else if (state.game==="oh-behave") {
    if (state.glanceNote) state.deadline = Math.max(state.deadline || 0, now + 2000);
    if (!state.faceData) {
      if (!state.pausedAt) {
        state.pausedAt = now;
        setPrompt("I'll wait","Come back into the camera. The timer is paused.");
      }
      return;
    }
    if (state.pausedAt) {
      state.deadline += now - state.pausedAt;
      state.pausedAt = 0;
    }
    const remaining=countdownRemaining(now);
    if(state.faceData.expression===state.targetExpression&&state.faceData.region===state.targetRegion&&state.faceData.confidence>=.55) succeed("Perfect face match!");
    else if(remaining<=0 && !state.glanceNote) fail("Almost — match the face and the spot!");
  } else if (state.game==="face-chase") {
    if (noteMissingFace(now)) return;
    if (state.faceData.region !== state.targetRegion) state.chaseLeft = true;
    if (state.chaseLeft && state.faceData.region === state.targetRegion) succeed("You found the face spot!");
  }
  else if (state.game==="air-drums") {
    if(now-state.beatAt>650){state.beatAt=now;state.phase=(state.phase+1)%2;setTarget(state.phase?"left":"right","🥁");state.padHeld=false;}
    hitAirDrums(now);
  } else if (state.game==="bird-flap" && airHands().length>=2) {
    const hands = airHands();
    const y=(hands[0].wrist.y+hands[1].wrist.y)/2;
    if (state.lastHandY == null) state.lastHandY = y;
    else if (Math.abs(y - state.lastHandY) > 28) {
      const dir = y > state.lastHandY ? 1 : -1;
      if (state.flapDir && dir !== state.flapDir) state.hitCount += 1;
      state.flapDir = dir;
      state.lastHandY = y;
    }
    if(state.hitCount>=4)succeed("You flew like a bird!");
  } else if (state.game==="head-bop") {
    if (noteMissingFace(now)) return;
    const y=state.faceData.cy*stageBox().h;
    if (state.lastFaceY == null) state.lastFaceY = y;
    else if (Math.abs(y - state.lastFaceY) > 22) {
      const dir = y > state.lastFaceY ? 1 : -1;
      if (state.bopDir && dir !== state.bopDir) state.hitCount += 1;
      state.bopDir = dir;
      state.lastFaceY = y;
    }
    if(state.hitCount>=4)succeed("Head-bop beat master!");
  } else if (state.game==="stand-sit") {
    if (noteMissingFace(now)) return;
    const y=state.faceData.cy;
    if (state.standBase == null) state.standBase = y;
    if(state.phase===0 && y < state.standBase - 0.07){
      state.phase=1;
      state.sitLow=y;
      setPrompt("Now sit down","Move gently back to your seat.");
    }
    if(state.phase===1 && y > (state.sitLow ?? y) + 0.08) succeed("Stand and sit complete!");
  } else if (state.game==="rainbow-reach" && airHands().length>=2) {
    const tips=airHands().map(h=>h.tip),box=stageBox();if(tips.every(p=>p&&p.y<box.h*.35)&&Math.abs(tips[0].x-tips[1].x)>box.w*.45)succeed("Rainbow reach!");
    } else if (state.game==="mirror-hall") updateMirrorHall(now);
    else if (state.game==="ninja-weave") updateNinjaWeave(now);
    else if (state.game==="dance-freeze") {
    const moving = isDancing();
    if (state.phase===0) {
      if (moving) state.hitCount += 1;
      if (state.hitCount>=4 && now-state.startedAt>2500) {
        state.phase=1;state.beatAt=now;
        setPrompt("Freeze!","Hold still like a statue!");
        tellActivity("Say freeze, then tell them to hold still like a statue.");
        speak("Freeze!");
      }
    } else if (state.phase===1) {
      if (moving) state.beatAt=now;
      else if (now-state.beatAt>750) succeed("Freeze! Brilliant dancing!");
    }
  }
}

function isDancing() {
  const hand=airHands()[0]?.tip;
  const face=state.faceData;
  let motion=0;
  if (hand) {
    if (state.lastTip) motion=Math.max(motion, distance(hand,state.lastTip));
    state.lastTip=hand;
  }
  if (face) {
    const y=face.cy*stageBox().h;
    if (state.lastFaceY!=null) motion=Math.max(motion, Math.abs(y-state.lastFaceY));
    state.lastFaceY=y;
  }
  // Landmark jitter is a few pixels. A real dance or head move is larger,
  // so a still face does not freeze-succeed on its own.
  return motion>18;
}
function targetPoint(){
  if (!target || target.classList.contains("hidden")) return {x:-9999,y:-9999};
  const r=target.getBoundingClientRect(),s=stage.getBoundingClientRect();
  if (!r.width || !r.height) return {x:-9999,y:-9999};
  return{x:r.left-s.left+r.width/2,y:r.top-s.top+r.height/2};
}

function loop(now) {
  if(!state.running)return;
  detectFrame();noteSensors();drawVision();
  watchPresence(now);
  if (state.voiceAway) {
    if (state.deadline && !state.pausedAt) state.pausedAt = now;
    noteMirrorPause(now);
    if (state.game === "ninja-weave" && state.ninja && !state.ninja.pausedAt) state.ninja.pausedAt = now;
  } else {
    updateTrace();updatePicturePlay();updateObjectGame();updatePopQuizToss(now);updateGestureGame(now);
    tickCountdown(now);
  }
  requestAnimationFrame(loop);
}

function setPresenceNote(text, holdMs) {
  const note = $("presence-note");
  if (!note) return;
  if (!text) {
    note.hidden = true;
    note.textContent = "";
    state.presenceNoteUntil = 0;
    return;
  }
  note.hidden = false;
  note.textContent = text;
  state.presenceNoteUntil = holdMs ? performance.now() + holdMs : 0;
}

function rememberPresence(kind, evidence) {
  try {
    const key = "theodoreChildrenPresenceV1";
    const rows = JSON.parse(localStorage.getItem(key) || "[]");
    const next = Array.isArray(rows) ? rows : [];
    next.push({kind, at: Date.now(), game: state.game || "", ...(evidence || {})});
    localStorage.setItem(key, JSON.stringify(next.slice(-40)));
  } catch (_) {}
}
function postFocus(kind, evidence) {
  let token = "";
  let studentId = "";
  try {
    token = localStorage.getItem("aoep_token") || "";
    studentId = localStorage.getItem("aoep_student_id") || "";
  } catch (_) {}
  if (!token || !studentId) return;
  const host = location.hostname;
  const base = host === "localhost" || host === "127.0.0.1" ? "http://127.0.0.1:8008" : "/identity";
  fetch(`${base}/students/${encodeURIComponent(studentId)}/focus-events`, {
    method: "POST",
    headers: {"content-type": "application/json", Authorization: `Bearer ${token}`},
    body: JSON.stringify({
      kind,
      surface: "children_lab",
      context: "children",
      evidence: evidence || {},
    }),
    keepalive: true,
  }).catch(() => {});
}

function watchPresence(now) {
  const face = state.faceData;
  const events = presenceWatch.update({
    atMs: now,
    facePresent: Boolean(face),
    pitchDeg: face?.pitchDeg ?? null,
    yawDeg: face?.yawDeg ?? null,
    gazeDown: face ? face.gazeDown : null,
    gazeFrontal: face?.gazeFrontal ?? null,
    // Face mesh is running whenever the landmarker exists. Pointer-demo faces
    // have no mesh pitch, so pose-only phone guesses stay off.
    allowPoseOnly: Boolean(state.face && face && face.pitchDeg != null),
    source: state.demo ? "pointer" : "face_mesh",
  });
  if (!events.length && state.presenceNoteUntil && now > state.presenceNoteUntil && !state.voiceAway) {
    setPresenceNote("");
    state.glanceNote = false;
  }
  for (const event of events) {
    if (event.type === "pause") {
      if (!state.voiceAway) {
        state.heldPrompt = state.spokenPrompt;
        state.voiceAway = true;
        state.glanceNote = false;
        cancelSpeech();
        window.TheodoreLiveAudio?.pauseRecognition?.();
        setPresenceNote(event.notice || event.line);
        speak(event.line, true);
        rememberPresence("left_frame", {signal: event.signal || "no_face"});
        postFocus("left_frame", {signal: event.signal || "no_face"});
      }
    } else if (event.type === "resume") {
      if (state.pausedAt && state.deadline) state.deadline += now - state.pausedAt;
      state.pausedAt = 0;
      state.voiceAway = false;
      const held = state.heldPrompt;
      state.heldPrompt = "";
      state.presenceCueUntil = now + 4000;
      window.TheodoreLiveAudio?.resumeRecognition?.();
      setPresenceNote(event.line, 4000);
      speak(event.line, true);
      setTimeout(() => {
        if (state.voiceAway) return;
        tellActivity(held || state.spokenPrompt);
      }, 1600);
      rememberPresence("returned", {away_ms: event.awayMs || 0, signal: event.signal || "face_mesh"});
      postFocus("returned", {away_ms: event.awayMs || 0, signal: event.signal || "face_mesh"});
    } else if (event.type === "notice") {
      state.glanceNote = true;
      setPresenceNote(event.line, 7000);
      rememberPresence(event.kind, {signal: event.signal || ""});
      postFocus(event.kind, {signal: event.signal || ""});
    }
  }
}

function successHoldMs() {
  if (state.game === "ninja-weave") return 3000;
  let fromQuery = "";
  try { fromQuery = new URLSearchParams(location.search).get("pace") || ""; } catch (_) {}
  const pace = (fromQuery || $("pace")?.value || state.pace || "patient").toLowerCase();
  if (pace === "quick") return 1000;
  if (pace === "steady") return 2000;
  return 3000;
}
function setControl(id, on) {
  const node = $(id);
  if (!node) return;
  node.classList.toggle("hidden", !on);
  if ("disabled" in node) node.disabled = !on;
}
function applyGameControls() {
  const flags = controlsFor(state.game);
  const letterWrap = $("letter-control");
  if (letterWrap) letterWrap.classList.toggle("hidden", !flags.letter);
  const letter = $("letter");
  if (letter) letter.disabled = !flags.letter;
  setControl("play-game", flags.play);
  setControl("hear", flags.hear);
  setControl("mic", flags.mic);
  setControl("typed", flags.typed);
  setControl("check", flags.check);
  setControl("undo", flags.undo);
  const wordsToggle = $("words-toggle");
  if (wordsToggle) wordsToggle.classList.toggle("hidden", !flags.words);
  const mirrorPaceControl = $("mirror-pace-control");
  if (mirrorPaceControl) mirrorPaceControl.classList.toggle(
    "hidden",
    state.game !== "mirror-hall" && state.game !== "ninja-weave",
  );
  const ninjaTechniqueControl = $("ninja-technique-control");
  if (ninjaTechniqueControl) ninjaTechniqueControl.classList.toggle("hidden", state.game !== "ninja-weave");
  const words = $("show-words");
  if (words) {
    words.disabled = !flags.words;
    words.checked = Boolean(flags.words && state.showWords);
  }
  renderSpokenWords();
}
function renderSpokenWords() {
  const node = $("spoken-words");
  if (!node) return;
  const flags = controlsFor(state.game);
  const round = state.audioRound;
  const line = flags.words && state.showWords && round && round.game === state.game
    ? String(round.speak || "").trim()
    : "";
  node.textContent = line;
  node.classList.toggle("hidden", !line);
}
function countdownRemaining(now) {
  if (!state.deadline) return 0;
  const held = state.pausedAt ? now - state.pausedAt : 0;
  return Math.max(0, state.deadline + held - now);
}
function traceDeadlineMs() {
  return state.age === "4-6" ? 60000 : 45000;
}
function armTraceClock() {
  armDeadline(traceDeadlineMs());
}
function armDeadline(ms) {
  const duration = Math.max(0, Number(ms) || 0);
  state.deadline = performance.now() + duration;
  state.pausedAt = 0;
  const node = $("countdown");
  if (!node) return;
  node.textContent = (duration / 1000).toFixed(1);
  node.classList.remove("hidden");
}
function hideCountdown() {
  state.deadline = 0;
  state.pausedAt = 0;
  const node = $("countdown");
  if (!node) return;
  node.textContent = "";
  node.classList.add("hidden");
}
function tickCountdown(now) {
  if (!state.deadline) return;
  if (state.roundDone) {
    hideCountdown();
    return;
  }
  const remaining = countdownRemaining(now);
  const node = $("countdown");
  if (node && !node.classList.contains("hidden")) {
    node.textContent = (remaining / 1000).toFixed(1);
  }
  const tracing = state.game === "trace-letter" || PICTURE_PLAY.has(state.game);
  if (remaining <= 0 && tracing) {
    fail("Time is up. Trace it once more.");
    return;
  }
  if (remaining <= 0 && OBJECT_GAMES.has(state.game) && state.object && !state.object.hit) {
    if (state.glanceNote || state.voiceAway) {
      state.deadline = now + 2500;
      return;
    }
    fail("So close! Try the next one.");
  }
}
function karaokeFrameSrc() {
  if (location.port === "8018") return "http://127.0.0.1:8097/lab?embed=arcade";
  return "/music/lab?embed=arcade";
}
function showKaraoke() {
  const frame = $("karaoke-frame");
  if (!frame) return;
  const src = karaokeFrameSrc();
  if (frame.getAttribute("src") !== src) frame.src = src;
  frame.classList.remove("hidden");
  $("stage")?.classList.add("karaoke-on");
}
function hideKaraoke() {
  const frame = $("karaoke-frame");
  $("stage")?.classList.remove("karaoke-on");
  if (!frame || frame.classList.contains("hidden")) return;
  frame.classList.add("hidden");
  try {
    frame.contentWindow?.document?.getElementById("player")?.pause();
  } catch (_) {
    frame.removeAttribute("src");
  }
}
function updateKaraoke() {
  if (state.game === "karaoke") showKaraoke();
}
function chooseGame() {
  if (state.playEnded) {
    setPrompt("Play time is up", "Thanks for playing! Tap home to start a fresh 10-minute session.");
    return;
  }
  $("prompt")?.classList.remove("is-success");
  clearTimeout(state.roundTimer);clearTimeout(state.failTimer);cancelSpeech();
  state.roundId += 1; const round = state.roundId; state.roundDone=false;
  clearRound();
  const select=$("game");
  if (!select) return;
  const previousGame=state.game;
  state.game=select.value;
<<<<<<< HEAD
  document.body.classList.toggle("ninja-play", state.game === "ninja-weave");
=======
  if (previousGame==="pop-quiz-toss" && state.game!=="pop-quiz-toss") popQuiz.teardown();
>>>>>>> 2aaa58c3 (Pop Quiz Toss: quiz rounds, themed targets, curve throws, voice + throw scoring, tutorial, adult ages)
  if (state.game!=="karaoke") hideKaraoke();
  if (state.game!==previousGame) state.audioIndex=0;
  state.startedAt=performance.now();state.attempts=1;state.hitCount=0;state.phase=0;state.padHeld=false;state.pausedAt=0;
  state.missingFaceAt=0;state.bopDir=0;state.flapDir=0;
  state.poseOpen=false;state.standBase=null;state.sitLow=null;
  updateGuideLayer();
  const letter=$("letter")?.value,word=LETTER_WORDS[letter];
  if(state.game==="trace-letter"){
    state.traceHoldUntil=performance.now()+500;
    armTraceClock();
    setPrompt(`Trace ${letter}`,"Point one finger up and follow the glowing letter.",`Trace the letter ${letter}.`);
  }
  else if(state.game==="trace-picture"){
    armPictureRound(word);
    state.traceHoldUntil=performance.now()+500;
    armTraceClock();
    setPrompt(`Trace the ${word}`,"Use one finger to draw around the picture.",`Now trace the ${word}.`);
  }
  else if(state.game==="color-picture"||state.game==="connect-dots"||state.game==="trace-outline"){
    armPictureRound(word);
    state.traceHoldUntil=performance.now()+500;
    armTraceClock();
    if(state.game==="color-picture")refreshColorPrompt(false);
    else if(state.game==="connect-dots")setPrompt(`Connect the ${word}`,"Touch the numbers in order, starting at 1.",`Connect the numbered dots on the ${word}.`);
    else setPrompt(`Trace the ${word}`,"Follow the outline with one finger. It does not need to be perfect.",`Trace the outline of the ${word}.`);
  }
  else if(state.game==="say-letter")setPrompt(`Say ${letter}`,"Tap the microphone or type what you said.",`Listen, then say the letter ${letter}.`);
  else if(state.game==="pop-quiz-toss"){
    setPrompt("Pop Quiz Toss","Getting your next question…");
    void armPopQuiz(round);
  }
  else if(AUDIO_GAMES.has(state.game)){
    state.audioRound = null;
    setPrompt("Listen","Theodore is getting the next listening round.");
    void armAudioRound(round);
  }
  else if(state.game==="oh-behave"){
    state.targetRegion=randomRegion();state.targetExpression=randomOf(EXPRESSIONS);
    armDeadline(state.timerMs);
    setTarget(state.targetRegion,expressionEmoji(state.targetExpression));
    setPrompt("Oh behave!",`Make a ${state.targetExpression} face inside the glowing circle.`);
  } else if(state.game==="heart"){setTarget(randomRegion(),"💖");setPrompt("Make a heart","Use both hands. Fingertips dip together at the top and thumbs meet at the bottom. A circle does not count.");}
  else if(state.game==="idea"){setTarget("top","☝️");setPrompt("I have an idea!","Hold one index finger up in the air.");}
  else if(state.game==="fist-bump"){setTarget("center","👊");setPrompt("Fist bump!","Make a fist and bump Theodore.");}
  else if(state.game==="wow"){setTarget(randomRegion(),"😮");setPrompt("Wow face!","Open your mouth and raise your eyebrows like a surprise.");}
  else if(state.game==="wink"){setTarget(randomRegion(),"😉");setPrompt("Wink challenge","Wink one eye at Theodore.");}
  else if(state.game==="blow-kiss"){setTarget("center","💋");setPrompt("Blow a kiss","Make a little O, bring a hand near your mouth, then send it away.");}
  else if(state.game==="make-pose"){setTarget("center",state.theme==="hero"?"🦸":"🌟");setPrompt("Make a pose","Raise both hands and hold your biggest hero pose.");}
  else if(OBJECT_GAMES.has(state.game)){
    const config={ "fruit-cut":["fruit",randomOf(["🍎","🍉","🍓","🍊"])],"balloon":["balloon","🎈"],fish:["fish","🐠"],popcorn:["kernel","🍿"]}[state.game];
    spawnObject(...config);setPrompt({"fruit-cut":"Fruit cut!","balloon":"Pop the balloon!","fish":"Catch the flying fish!","popcorn":"Catch the popcorn!"}[state.game],
      state.game==="popcorn"?"Make a big O with your mouth and catch it.":"Use one finger to catch it!");
    armDeadline(state.game==="popcorn"?4200:5800);
  } else if(state.game==="face-chase"){
    state.chaseLeft=false;
    state.targetRegion=regionOtherThan(state.faceData?.region);
    setTarget(state.targetRegion,"😊");
    setPrompt("Face chase","Move your face into the glowing circle.");
  }
  else if(state.game==="air-drums"){setTarget("left","🥁");setPrompt("Air drums","Hit the drum pads with your hands on the beat.");state.beatAt=performance.now();}
  else if(state.game==="bird-flap"){setPrompt("Flap like a bird","Lift both hands up and down. Fly!");spawnObject("","🐦");}
  else if(state.game==="head-bop"){setPrompt("Bop to the beat","Move your head gently up and down.");}
  else if(state.game==="stand-sit"){
    if(state.seated){setPrompt("Seated reach","Seated-only is on. Reach both hands high instead.");state.game="rainbow-reach";}
    else setPrompt("Stand up","Step back so Theodore sees you, then stand gently.");
  } else if(state.game==="dance-freeze"){setPrompt("Dance!","Move any way you like… freeze when Theodore says freeze.");spawnObject("","🎵");}
  else if(state.game==="rainbow-reach"){setPrompt("Rainbow reach","Stretch both hands toward opposite top corners.");}
  else if(state.game==="mirror-hall"){
    ensureMirrorPace();
    state.combo = 0;
    state.mirror = freshMirrorRun(state.mirrorPace);
    armMirrorBeat(performance.now());
  }
  else if(state.game==="ninja-weave") startNinjaWeave();
  else if(state.game==="karaoke"){
    showKaraoke();
    setPrompt("Karaoke sing-along","Pick a song. The words stay large, and your language sings louder than the English track.");
  }
  else if(!GAMES.includes(state.game)){setPrompt("Pick a game","That activity is not wired yet. Choose another from the list.");}
  if (!AUDIO_GAMES.has(state.game) && state.game!=="karaoke") {
    tellActivity(state.spokenPrompt);
    speak(state.spokenPrompt);
  }
  applyGameControls();
}
function tellActivity(prompt, opts = {}) {
  if (state.voiceAway || window.__THEODORE_LIVE_AUDIO_HOLD__) return;
  if (!window.__THEODORE_LIVE_AUDIO_ACTIVE__ || !prompt) return;
  const roundKey = state.audioRound?.round_id || String(state.roundId || 0);
  const target = state.audioRound?.round_id || state.spokenPrompt || prompt;
  window.TheodoreLiveAudio?.noteActivity?.({
    id: String(state.game || "play") + ":" + roundKey + ":" + String(target).slice(0, 80),
    force: Boolean(opts.force),
    prompt: (
      "The webcam game on screen is the only activity. Coach that current prompt "
      + "in one short sentence and wait. Do not mention or ask for any earlier "
      + "target word. Do not reveal the answer. Current prompt: " + prompt
    ),
  });
}

function randomRegion(){const keys=Object.keys(REGIONS).filter(k=>!state.seated||!k.startsWith("bottom"));return randomOf(keys)||"center";}
function expressionEmoji(kind){return({happy:"😄",surprised:"😮","wink-left":"😉","wink-right":"😉","mouth-o":"😗",sleepy:"😴"})[kind]||"🙂";}

function clearRound() {
  state.sawFace = false;
  state.sawHand = false;
  state.sawFinger = false;
  state.sawScreen = false;
  hideTarget();
<<<<<<< HEAD
  for (const node of [...spriteLayer.querySelectorAll(".sprite,.miss-gag,.miss-caption,.math-target,.math-ball,.ninja-sequence,.ninja-fx")]) node.remove();
=======
  for (const node of [...spriteLayer.querySelectorAll(".sprite,.miss-gag,.miss-caption")]) node.remove();
  popQuiz.clearRoundVisuals();
>>>>>>> 2aaa58c3 (Pop Quiz Toss: quiz rounds, themed targets, curve throws, voice + throw scoring, tutorial, adult ages)
  hideCountdown();
  state.trail=[];state.object=null;state.lastTip=null;state.lastFaceY=null;state.lastHandY=null;
}

function calculateFun(success,extra={}) {
  const duration=Math.round(performance.now()-state.startedAt);
  const play=success?40:8,pace=Math.max(0,1-duration/8000);
  const spark=(success&&state.attempts===1?18:success?8:0)+Math.min(8,state.combo*2)+pace*4;
  const giggle=clamp01(state.faceData?.smile)*12;
  const keepGoing=(state.attempts>1?8:2)+Math.min(8,new Set((state.faceData?[state.faceData.region]:[])).size*2);
  const score=Math.round(Math.max(0,Math.min(100,play+spark+giggle+keepGoing)));
  return {score,duration,components:{play:Math.round(play),spark:Math.round(spark),giggle:Math.round(giggle),keep_going:Math.round(keepGoing)},...extra};
}

function armPictureRound(word) {
  const scene = sceneForWord(word);
  state.picture = scene;
  state.crayon = null;
  state.ink = [];
  state.inkDown = false;
  state.painted = scene.segments.map(() => false);
  state.pictureDots = dotsFor(scene.outline, state.age === "4-6" ? 6 : 10);
  state.dotCursor = 0;
}
function pickNextLetter() {
  const select=$("letter");
  if (!select || !select.options.length) return;
  const choices=[];
  for (const option of select.options) {
    if (option.value && option.value!==select.value) choices.push(option.value);
  }
  const next=randomOf(choices.length?choices:[select.value]);
  if (next) select.value=next;
}
function succeed(message) {
  if(state.playEnded || state.roundDone || state.voiceAway)return;state.roundDone=true;state.combo+=1;
  const round=state.roundId;
  const advanceLetter=state.game==="trace-letter"||PICTURE_PLAY.has(state.game);
  if(state.game==="oh-behave")state.timerMs=nextTimer(true);
  if (AUDIO_GAMES.has(state.game)) state.audioIndex=(state.audioIndex||0)+1;
  const result=calculateFun(true);state.fun=result.score;renderScore();fireworks();setPrompt("You did it!",message);
  $("prompt")?.classList.add("is-success");
  recordEvent("success",result);
  // Celebrate only — never invite another answer for the word that just ended.
  // The next chooseGame()/armAudioRound call pushes the new target with force.
  tellActivity(
    `The child succeeded. Celebrate in one short sentence: ${message}. `
    + "Do not ask for another answer. Wait for the next on-screen prompt.",
    {force: true},
  );
  speak(`You did it! ${message}`);
  clearTimeout(state.roundTimer);
  state.roundTimer=setTimeout(()=>{
    if(state.roundId!==round)return;
    state.roundDone=false;
    if(advanceLetter) pickNextLetter();
    chooseGame();
  }, successHoldMs());
}
function fail(message) {
  if(state.playEnded || state.roundDone)return;state.roundDone=true;state.combo=0;state.attempts+=1;
  const round=state.roundId;
  fadeMissedObject();
  const result=calculateFun(false);state.fun=result.score;renderScore();missGag();setPrompt("Almost!",message);
  recordEvent("retry",result);
  tellActivity(
    `The child missed. Encourage them in one short sentence: ${message}. `
    + "Stay on the current on-screen prompt. Do not invent a new target word.",
    {force: true},
  );
  speak(`Almost! ${message}`);
  if(state.game==="oh-behave")state.timerMs=nextTimer(false);
  clearTimeout(state.roundTimer);
  state.roundTimer=setTimeout(()=>{if(state.roundId!==round)return;state.roundDone=false;chooseGame();},1500);
}
function nextTimer(hit){const full=[8000,6000,4000,2000,1500],ladder=state.age==="4-6"?full.slice(0,3):full;let i=Math.max(0,ladder.indexOf(state.timerMs));i=hit?Math.min(ladder.length-1,i+1):Math.max(0,i-1);return ladder[i];}
function renderScore(){
  setText("fun-score", `Fun ${state.fun}`);
  setText("combo", `Combo ${state.combo}`);
  setText("stars", state.fun>=85?"★★★":state.fun>=60?"★★☆":state.fun>0?"★☆☆":"☆☆☆");
}

function fxAudioContext() {
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) return null;
  try {
    if (!state.fxAudio) state.fxAudio = new AudioCtx();
    if (state.fxAudio.state === "suspended") state.fxAudio.resume().catch(() => {});
    return state.fxAudio;
  } catch (_) {
    return null;
  }
}
function fxTone(audio, {at=0, from=440, to=440, duration=.16, volume=.06, type="sine"}={}) {
  const start = audio.currentTime + at;
  const osc = audio.createOscillator();
  const gain = audio.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(from, start);
  osc.frequency.exponentialRampToValueAtTime(Math.max(20, to), start + duration);
  gain.gain.setValueAtTime(.0001, start);
  gain.gain.exponentialRampToValueAtTime(volume, start + Math.min(.025, duration / 3));
  gain.gain.exponentialRampToValueAtTime(.0001, start + duration);
  osc.connect(gain);gain.connect(audio.destination);
  osc.start(start);osc.stop(start + duration + .02);
}
function fxNoise(audio, {at=0, duration=.7, volume=.05, lowpass=1200, filter="lowpass"}={}) {
  const frames = Math.max(1, Math.floor(audio.sampleRate * duration));
  const buffer = audio.createBuffer(1, frames, audio.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i=0;i<frames;i++) data[i]=(Math.random()*2-1)*(1-i/frames);
  const source=audio.createBufferSource(),biquad=audio.createBiquadFilter(),gain=audio.createGain();
  source.buffer=buffer;biquad.type=filter;biquad.frequency.value=lowpass;gain.gain.value=volume;
  source.connect(biquad);biquad.connect(gain);gain.connect(audio.destination);source.start(audio.currentTime+at);
}
const NINJA_SOUNDS = {
  roar(audio, p) {
    fxNoise(audio,{duration:1.15,volume:.075,lowpass:1450*p});
    fxTone(audio,{from:110*p,to:620*p,duration:.8,volume:.09,type:"sawtooth"});
    fxTone(audio,{at:.32,from:420*p,to:980*p,duration:.6,volume:.045,type:"triangle"});
  },
  splash(audio, p) {
    fxNoise(audio,{duration:1.3,volume:.04,lowpass:850*p});
    for(let i=0;i<5;i++)fxTone(audio,{at:i*.12,from:(260+i*35)*p,to:(520+i*50)*p,duration:.42,volume:.04});
  },
  rumble(audio, p) {
    fxTone(audio,{from:95*p,to:38,duration:1.2,volume:.12});
    fxTone(audio,{at:.08,from:64*p,to:42,duration:.9,volume:.08,type:"square"});
    fxNoise(audio,{duration:.65,volume:.05,lowpass:260*p});
  },
  whoosh(audio, p) {
    fxNoise(audio,{duration:1.1,volume:.07,lowpass:900*p,filter:"bandpass"});
    fxNoise(audio,{at:.35,duration:.8,volume:.05,lowpass:1800*p,filter:"bandpass"});
    fxTone(audio,{from:300*p,to:900*p,duration:.7,volume:.025,type:"triangle"});
  },
  zap(audio, p) {
    for(let i=0;i<4;i++)fxTone(audio,{at:i*.09,from:(1400-i*200)*p,to:120,duration:.12,volume:.05,type:"square"});
    fxNoise(audio,{at:.05,duration:.5,volume:.06,lowpass:3200*p,filter:"highpass"});
  },
  chime(audio, p) {
    [1,1.25,1.5,2].forEach((step,i)=>fxTone(audio,{at:i*.11,from:880*step*p,to:880*step*p,duration:.7,volume:.035}));
  },
  shine(audio, p) {
    [1,1.26,1.5,1.88,2.52].forEach((step,i)=>fxTone(audio,{at:i*.08,from:520*step*p,to:540*step*p,duration:.5,volume:.035,type:"triangle"}));
  },
  hum(audio, p) {
    fxTone(audio,{from:146*p,to:110*p,duration:1.4,volume:.07});
    fxTone(audio,{from:220*p,to:165*p,duration:1.4,volume:.04});
    fxTone(audio,{at:.4,from:330*p,to:660*p,duration:.6,volume:.025,type:"triangle"});
  },
  rustle(audio, p) {
    for(let i=0;i<6;i++)fxNoise(audio,{at:i*.11,duration:.16,volume:.05,lowpass:2400*p,filter:"bandpass"});
    fxTone(audio,{at:.3,from:392*p,to:523*p,duration:.5,volume:.03});
  },
  clang(audio, p) {
    [1,2.76,5.4].forEach((ratio)=>fxTone(audio,{from:300*ratio*p,to:290*ratio*p,duration:1.1,volume:.04/ratio+.01,type:"triangle"}));
    fxNoise(audio,{duration:.12,volume:.06,lowpass:5000,filter:"highpass"});
  },
};
function ninjaSound(kind, techniqueId=NINJA_DEFAULT_TECHNIQUE) {
  if (state.muted) return;
  const audio=fxAudioContext();
  if (!audio) return;
  try {
    if (kind==="step"||kind==="start") {
      fxTone(audio,{from:kind==="start"?330:520,to:kind==="start"?660:780,duration:.12,volume:.045,type:"triangle"});
      return;
    }
    if (kind==="miss") {
      fxTone(audio,{from:180,to:90,duration:.22,volume:.035,type:"square"});
      return;
    }
    const spec=ninjaEffectSpec(techniqueId);
    (NINJA_SOUNDS[spec.sound]||NINJA_SOUNDS.roar)(audio, spec.pitch);
  } catch (_) {}
}
function launchNinjaEffect(techniqueId) {
  const spec=ninjaEffectSpec(techniqueId);
  const reduced=window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const phone=document.body.classList.contains("phone-play");
  const fx=document.createElement("div");
  fx.className=`ninja-fx ninja-${spec.element} ninja-form-${spec.form}${spec.shake&&!reduced?" ninja-shake":""}`;
  fx.setAttribute("aria-hidden","true");
  spec.colors.forEach((color,i)=>fx.style.setProperty(`--c${i+1}`,color));
  const core=document.createElement("i");
  core.className="ninja-fx-core";
  core.style.left=`${spec.focus.x*100}%`;
  core.style.top=`${spec.focus.y*100}%`;
  const title=document.createElement("strong");
  title.className="ninja-fx-title";
  title.textContent=`${NINJA_ELEMENTS[spec.element].glyph} ${spec.label}!`;
  fx.append(core,title);
  const canAnimate=typeof core.animate==="function";
  if (canAnimate&&!reduced) {
    core.animate([
      {transform:"translate(-50%,-50%) scale(.1)",opacity:0},
      {transform:"translate(-50%,-50%) scale(1.3)",opacity:1,offset:.3},
      {transform:"translate(-50%,-50%) scale(3.2)",opacity:0},
    ],{duration:1800,easing:"ease-out",fill:"forwards"});
    title.animate([
      {transform:"translate(-50%,0) scale(.6)",opacity:0},
      {transform:"translate(-50%,0) scale(1.08)",opacity:1,offset:.2},
      {transform:"translate(-50%,0) scale(1)",opacity:1,offset:.8},
      {transform:"translate(-50%,-12px) scale(1)",opacity:0},
    ],{duration:2400,easing:"ease-out",fill:"forwards"});
  }
  if (!reduced) {
    for (const particle of ninjaEffectParticles(spec.id, phone?18:28)) {
      const dot=document.createElement("b");
      dot.className=`ninja-p ninja-p-${spec.particle}`;
      const start=particle.points[0];
      dot.style.left=`${start.x*100}%`;
      dot.style.top=`${start.y*100}%`;
      dot.style.setProperty("--s",String(particle.size));
      fx.append(dot);
      if (!canAnimate) continue;
      const last=particle.points.length-1;
      dot.animate(particle.points.map((point,i)=>({
        left:`${point.x*100}%`,
        top:`${point.y*100}%`,
        opacity:i===0?0:i===last?0:1,
        transform:`translate(-50%,-50%) rotate(${Math.round(particle.spin*i/Math.max(1,last))}deg) scale(${particle.size*(i===0?.4:1)})`,
      })),{duration:1500,delay:particle.delay,easing:"cubic-bezier(.2,.7,.3,1)",fill:"both"});
    }
  }
  spriteLayer.append(fx);
  setTimeout(()=>fx.remove(),reduced?1600:3000);
}

function fireworks() {
  const colors=["#fde047","#fb7185","#34d399","#60a5fa","#c084fc","#f97316"];
  const count = state.theme==="hero" ? 8 : 6;
  for(let i=0;i<count;i++){const el=document.createElement("i");el.className="firework";el.style.setProperty("--c",randomOf(colors));el.style.left=`${10+Math.random()*80}%`;el.style.top=`${15+Math.random()*60}%`;spriteLayer.append(el);setTimeout(()=>el.remove(),1000);}
}
function missGag() {
  const pack=state.theme==="mix"?randomOf(["cuddly","hero"]):state.theme;
  const [art,caption]=randomOf(MISS_GAGS[pack]||MISS_GAGS.cuddly);
  const el=document.createElement("div");el.className="miss-gag";el.textContent=art;
  const label=document.createElement("div");label.className="miss-caption";label.textContent=caption;
  spriteLayer.append(el,label);setTimeout(()=>{el.remove();label.remove();},1300);
  state.lastGag=caption;
}

function cancelSpeech() {
  state.speechToken+=1;
  if (state.audio) {
    try { state.audio.pause(); state.audio.src = ""; } catch (_) {}
    state.audio = null;
  }
  if ("speechSynthesis" in window) speechSynthesis.cancel();
}

async function probeSpeech() {
  // A failed render is more recent than a successful probe. Do not revive the
  // server path from a racy /api/tts/status that still says available.
  if (state.serverTts === false) return;
  try {
    const response=await fetch("/api/tts/status");
    const status=response.ok?await response.json():null;
    if (state.serverTts === false) return;
    state.serverTts=Boolean(status?.available);
  } catch (_) {
    if (state.serverTts !== false) state.serverTts=false;
  }
}

async function speak(text, cue=false) {
  if(state.voiceAway && !cue) return;
  if(state.muted||!text)return;
  if(window.__THEODORE_LIVE_AUDIO_ACTIVE__ && !cue)return;
  cancelSpeech();
  const token=state.speechToken;
  try {
    if(state.serverTts===null) await probeSpeech();
    if(!state.serverTts)throw new Error("device-fallback");
    const response=await fetch(`/api/tts?text=${encodeURIComponent(text)}&language=en&style=cheerful`);
    if(!response.ok){state.serverTts=false;throw new Error(String(response.status));}
    const url=URL.createObjectURL(await response.blob()),audio=new Audio(url);
    if(token!==state.speechToken){URL.revokeObjectURL(url);return;}
    state.audio=audio;
    audio.onended=()=>{URL.revokeObjectURL(url);if(state.audio===audio)state.audio=null;};
    await audio.play();
  } catch (_) {
    if(token!==state.speechToken)return;
    if("speechSynthesis" in window){const utterance=new SpeechSynthesisUtterance(text);utterance.rate=.94;utterance.pitch=1.08;speechSynthesis.speak(utterance);}
  }
}
window.addEventListener("theodore-live-audio",(event)=>{
  if (!event.detail?.active || event.detail.paused || window.__THEODORE_LIVE_AUDIO_HOLD__ || state.voiceAway) return;
  if (performance.now() < (state.presenceCueUntil || 0)) return;
  cancelSpeech();
  setTimeout(()=> {
    if (state.voiceAway || window.__THEODORE_LIVE_AUDIO_HOLD__) return;
    tellActivity(state.spokenPrompt);
  }, 700);
});

function pulsePlayStage() {
  const box = $("stage");
  if (!box) return;
  box.classList.remove("voice-shift");
  void box.offsetWidth;
  box.classList.add("voice-shift");
}
function cycleSelect(select) {
  if (!select || select.options.length < 2) return false;
  select.selectedIndex = (select.selectedIndex + 1) % select.options.length;
  return true;
}
function gameMatchesSpoken(option, target) {
  const want = String(target || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  if (want.length < 3) return false;
  const label = option.textContent.toLowerCase();
  const id = option.value.toLowerCase().replace(/-/g, " ");
  return label.includes(want) || id.includes(want) || want.includes(id);
}
function selectSpokenGame(target) {
  const select = $("game");
  if (!select) return false;
  const hit = [...select.options].find((option) => gameMatchesSpoken(option, target));
  if (!hit) return false;
  select.value = hit.value;
  chooseGame();
  return true;
}
function applySpokenActivity(text, role) {
  const said = String(text || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").replace(/\s+/g, " ").trim();
  const short = said.split(" ").filter(Boolean).length <= 6;
  if (state.game === "dance-freeze" && short) {
    if (/\bfreeze\b/.test(said)) {
      if (state.phase !== 1) {
        state.phase = 1;
        state.beatAt = performance.now();
        state.hitCount = Math.max(state.hitCount, 4);
        setPrompt("Freeze!", "Hold still like a statue!");
      }
      pulsePlayStage();
      return true;
    }
    if (state.phase === 1 && /\b(dance|move)\b/.test(said)) {
      state.phase = 0;
      state.hitCount = 0;
      state.startedAt = performance.now();
      setPrompt("Dance!", "Move any way you like… freeze when Theodore says freeze.");
      pulsePlayStage();
      return true;
    }
  }
  if (role !== "user" || !isAudioGame()) return false;
  const typed = $("typed");
  if (typed) typed.value = text;
  checkSpeech(text);
  pulsePlayStage();
  return true;
}
function applyVoiceScreen(detail) {
  const action = detail && detail.action;
  if (!action) return;
  const game = $("game");
  const letter = $("letter");
  if (action === "game") {
    if (!selectSpokenGame(detail.target) && game) {
      cycleSelect(game);
      chooseGame();
    }
  } else if (action === "letter" && letter && detail.target) {
    const opt = [...letter.options].find((option) => option.value.toLowerCase() === detail.target);
    if (!opt) return;
    letter.value = opt.value;
    if (game && !["trace-letter", "say-letter", "trace-picture", "color-picture", "connect-dots", "trace-outline"].includes(game.value)) {
      game.value = "trace-letter";
    }
    chooseGame();
  } else if (action === "next_letter" && letter) {
    cycleSelect(letter);
    chooseGame();
  } else if (action === "example" && game) {
    if (game.value === "trace-picture" && letter) cycleSelect(letter);
    game.value = "trace-picture";
    chooseGame();
  } else if (action === "animation") {
    chooseGame();
  } else if ((action === "next" || action === "next_game" || action === "next_section") && game) {
    cycleSelect(game);
    chooseGame();
  } else {
    return;
  }
  pulsePlayStage();
}
window.addEventListener("theodore-live-audio-action", (event) => {
  applyVoiceScreen(event.detail || {});
});
window.addEventListener("theodore-live-audio-utterance", (event) => {
  const detail = event.detail || {};
  if (!detail.text || detail.command) return;
  applySpokenActivity(detail.text, detail.role);
});

function startListening() {
  if(state.game==="pop-quiz-toss"){popQuiz.startVoice();return;}
  if (!isAudioGame()) {
    setPrompt("Pick a listening game","Choose Say the letter or a game under Listen, then use the microphone.");
    return;
  }
  const Ctor=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!Ctor){setPrompt("Type instead","Speech recognition is unavailable here.");$("typed")?.focus();return;}
  if(state.recognition)try{state.recognition.stop();}catch(_){}
  const rec=new Ctor();state.recognition=rec;rec.lang="en-US";rec.interimResults=false;rec.maxAlternatives=1;
  setText("mic","Listening…");rec.onresult=e=>{const heard=e.results[0][0].transcript;const typed=$("typed");if(typed)typed.value=heard;checkSpeech(heard);};
  rec.onerror=e=>setPrompt("Mic paused",`Try typing instead (${e.error}).`);
  rec.onend=()=>setText("mic","🎤 Say it");rec.start();
}
async function armAudioRound(round) {
  const game = state.game;
  const index = state.audioIndex || 0;
  try {
    const response = await fetch(`/api/child/audio-round?game=${encodeURIComponent(game)}&index=${index}`);
    if (!response.ok) throw new Error(String(response.status));
    const data = await response.json();
    if (state.roundId !== round || state.game !== game) return;
    state.audioRound = data;
    setPrompt(data.title, data.prompt, data.speak);
    renderSpokenWords();
    // Force replaces any celebrate/retry turn still aimed at the previous word.
    tellActivity(data.speak, {force: true});
    speak(data.speak);
  } catch (error) {
    if (state.roundId !== round) return;
    setPrompt("Listen again", "I could not load that listening round.");
  }
}
async function checkSpeech(heard) {
  if(state.game==="pop-quiz-toss"){popQuiz.typedAnswer(heard);return;}
  if (!isAudioGame()) {
    setPrompt("Pick a listening game","Choose Say the letter or a game under Listen, then check what was said.");
    return;
  }
  try {
    const response = state.game === "say-letter"
      ? await fetch("/api/child/pronounce", {method:"POST", headers:{"content-type":"application/json"}, body:JSON.stringify({target:$("letter")?.value, heard, kind:"letter"})})
      : await fetch("/api/child/audio-check", {method:"POST", headers:{"content-type":"application/json"}, body:JSON.stringify({game:state.game, round_id:state.audioRound?.round_id || "", heard})});
    if (!response.ok) throw new Error(String(response.status));
    const result = await response.json();
    result.passed ? succeed(result.feedback) : fail(result.feedback);
  } catch (error) {
    setPrompt("Try again", "I could not check that answer.");
  }
}

function recordEvent(outcome,result) {
  const event={activity_id:state.game,age_band:state.age,outcome,attempts:state.attempts,duration_ms:result.duration,fun_score:result.score,
    components:result.components,celebration_kind:outcome==="success"?"fireworks":"",miss_gag_id:outcome==="retry"?state.lastGag||"":"",theme_pack:state.theme,seated_only:state.seated,
    vision:visionTelemetry()};
  state.activityEvents.push(event);state.activityEvents=state.activityEvents.slice(-100);
  localStorage.setItem(state.localKey,JSON.stringify(state.activityEvents));renderDashboard();
  try {
    if (window.ReactNativeWebView) {
      window.ReactNativeWebView.postMessage(JSON.stringify({type:"salareen-telemetry", event}));
    }
  } catch (_) {}
  if(state.share)fetch("/api/child/analytics",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(event),keepalive:true}).catch(()=>{});
}
function loadLocalAnalytics(){try{state.activityEvents=JSON.parse(localStorage.getItem(state.localKey)||"[]");if(!Array.isArray(state.activityEvents))state.activityEvents=[];}catch(_){state.activityEvents=[];}renderDashboard();}
function renderDashboard(){
  const by={};for(const event of state.activityEvents){const id=String(event.activity_id||"game");const row=by[id]||(by[id]={scores:[],wins:0,plays:0});row.scores.push(Number(event.fun_score)||0);row.plays++;if(event.outcome==="success")row.wins++;}
  $("dashboard") && ($("dashboard").innerHTML=`<div class="dashboard-grid">${Object.entries(by).map(([id,row])=>`<div class="metric"><strong>${esc(id.replaceAll("-"," "))}</strong>Fun ${Math.round(row.scores.reduce((a,b)=>a+b,0)/row.scores.length)} · ${row.wins}/${row.plays} wins</div>`).join("")||"<p>No games recorded yet.</p>"}</div>`);
}

function demoExpression(event) {
  if (event.altKey) return "sleepy";
  if (event.ctrlKey || event.metaKey) return "surprised";
  if (event.buttons===2) return "wink-left";
  if (event.buttons===1) return "mouth-o";
  return "happy";
}

function applyDemoPointer(event) {
  if (!state.demo) return;
  const box = stage.getBoundingClientRect();
  const tip = {x:event.clientX-box.left, y:event.clientY-box.top};
  const w = Math.max(1, box.width), h = Math.max(1, box.height);
  const nx = clamp01(tip.x/w), ny = clamp01(tip.y/h);
  const pose = event.altKey ? "fist" : ((event.ctrlKey || event.metaKey) ? "open" : "index");
  const primary = handMetrics(syntheticHand({x:nx,y:ny}, {pose}), "Pointer");
  state.handData = primary ? [primary] : [];
  if (event.shiftKey) {
    const other = handMetrics(syntheticHand({x:clamp01(1-nx), y:ny}, {pose}), "Pointer-2");
    if (other) state.handData.push(other);
  }
  const smile = demoExpression(event)==="happy" ? 0.7 : 0.05;
  const expression = demoExpression(event);
  const width=0.24, height=0.28;
  const region=Object.entries(REGIONS).sort((a,b)=>Math.hypot(nx-a[1][0],ny-a[1][1])-Math.hypot(nx-b[1][0],ny-b[1][1]))[0][0];
  state.faceData={
    points:[{x:1-nx,y:ny}], bs:{}, cx:nx, cy:ny, width, height,
    expression, confidence:0.9, region, smile,
  };
}

function screenTouch() {
  return phonePlay() && state.touchMode === "screen";
}
function noteSensors() {
  if (state.faceData) state.sawFace = true;
  if (state.handData.some((hand) => !hand.screen)) state.sawHand = true;
  if (state.handData.some((hand) => !hand.screen && (fingersPointed(hand) || activeFingertips(hand.points, state.age).length))) state.sawFinger = true;
  if (state.screenDown) state.sawScreen = true;
}
function visionTelemetry() {
  const face = state.faceData;
  const hands = state.handData.filter((hand) => !hand.screen);
  const normalized = state.trail.map((point) => ({x: point.nx, y: point.ny}));
  const progress = traceProgress(normalized, state.age);
  const fingers = hands.reduce((max, hand) => Math.max(max, Number(hand.count) || 0), 0);
  return {
    face: face ? String(face.expression || "unknown") : "none",
    face_confidence: face ? Math.round((Number(face.confidence) || 0) * 100) : 0,
    distance: faceDistanceLabel(face),
    face_width: face ? Math.round(face.width * 100) : 0,
    hands: hands.length,
    fingers,
    motion_px: Math.round(state.handMotion || 0),
    trail_points: state.trail.length,
    trace_percent: Number(progress.percent) || 0,
    touch_mode: state.touchMode === "screen" ? "screen" : "air",
    hand: Boolean(state.sawHand),
    finger: Boolean(state.sawFinger),
    face_seen: Boolean(state.sawFace),
    screen_touch: Boolean(state.sawScreen),
  };
}
function placeScreenHand(event) {
  const box = stage.getBoundingClientRect();
  const w = Math.max(1, box.width);
  const h = Math.max(1, box.height);
  stageRect = {w, h, left: box.left, top: box.top};
  const nx = clamp01((event.clientX - box.left) / w);
  const ny = clamp01((event.clientY - box.top) / h);
  state.handData = [{
    indexUp: state.game!=="pop-quiz-toss",
    fist: state.game==="pop-quiz-toss"&&state.screenDown,
    count: 1,
    tipPalms: 2.4,
    scale: 0.1,
    thumbOut: false,
    points: [],
    label: "Screen",
    screen: true,
    tip: {x: nx * w, y: ny * h},
    wrist: {x: nx * w, y: Math.min(h - 1, ny * h + 48)},
  }];
}
function liftScreenHand() {
  state.screenDown = false;
  state.screenPointerId = null;
  state.inkDown = false;
  state.handData = state.handData.filter((hand) => !hand.screen);
}
function setTouchMode(mode) {
  state.touchMode = mode === "screen" ? "screen" : "air";
  if (state.game === "pop-quiz-toss") cancelQuizThrow();
  liftScreenHand();
  const screen = state.touchMode === "screen";
  const group = $("touch-mode");
  const air = $("touch-air");
  const glass = $("touch-screen");
  if (air && glass) {
    air.setAttribute("aria-checked", screen ? "false" : "true");
    glass.setAttribute("aria-checked", screen ? "true" : "false");
  } else if (group && group.tagName === "BUTTON") {
    group.textContent = screen ? "Screen touch" : "Air touch";
    group.setAttribute("aria-pressed", screen ? "true" : "false");
  }
  group?.setAttribute(
    "aria-label",
    screen
      ? "Screen touch selected. Air touch is also available."
      : "Air touch selected. Screen touch is also available.",
  );
  const showCatcher = screen && phonePlay();
  document.body.classList.toggle("screen-touch", showCatcher);
  const catcher = $("screen-catcher");
  if (catcher) catcher.hidden = !showCatcher;
  if (state.game === "color-picture" && state.picture) refreshColorPrompt(false);
}
function syncTouchToggle() {
  const group = $("touch-mode");
  if (!group) return;
  group.hidden = !phonePlay();
  setTouchMode(state.touchMode || "air");
}
function pokeScreenTargets() {
  if (!screenTouch() || state.roundDone) return;
  updateObjectGame();
  updateTrace();
  updatePicturePlay();
  updatePopQuizToss(performance.now());
  if (state.game === "air-drums") hitAirDrums(performance.now());
}
function releaseScreenThrow(point) {
  if(state.game!=="pop-quiz-toss"||!point)return;
  placeScreenHand(point);
  const hand=state.handData.find(row=>row.screen);
  if(!hand)return;
  hand.fist=false;hand.indexUp=true;
  updatePopQuizToss(performance.now(),hand);
}
function screenEventPoint(event) {
  if (Number.isFinite(event?.clientX) && Number.isFinite(event?.clientY)) return event;
  const touch = event?.changedTouches?.[0] || event?.touches?.[0];
  return touch ? screenPoint(touch) : null;
}
function beginScreenTouch(event) {
  if (!screenTouch()) return false;
  if (state.screenPointerId != null) return true;
  const point = screenEventPoint(event);
  if (!point) return false;
  event.preventDefault();
  state.screenDown = true;
  state.screenPointerId = event.pointerId ?? event.changedTouches?.[0]?.identifier ?? 1;
  if (event.pointerId != null) stage.setPointerCapture?.(event.pointerId);
  placeScreenHand(point);
  pokeScreenTargets();
  return true;
}
stage?.addEventListener("pointermove",(event)=>{
  if (screenTouch()) {
    if (!state.screenDown || (event.pointerId != null && event.pointerId !== state.screenPointerId)) return;
    placeScreenHand(event);
    updateObjectGame();
    updateTrace();
    updatePicturePlay();
    updatePopQuizToss(performance.now());
    if (state.game === "air-drums") hitAirDrums(performance.now());
    return;
  }
  applyDemoPointer(event);
});
// Pop Quiz Toss draws its own buttons (tutorial, help, win) inside the stage; a press
// on them must not start a throw or capture the pointer, or the button never clicks.
function isPopQuizUi(event) {
  return Boolean(event?.target?.closest?.(".pq-tutorial,.pq-win,.pq-help"));
}
stage?.addEventListener("pointerdown",(event)=>{
  if (isPopQuizUi(event)) return;
  if (beginScreenTouch(event)) return;
  if (!state.demo) return;
  event.preventDefault();
  stage.setPointerCapture?.(event.pointerId);
  applyDemoPointer(event);
});
stage?.addEventListener("pointerup",(event)=>{
  if (isPopQuizUi(event)) return;
  if (!screenTouch()) return;
  if (state.screenPointerId == null) {
    beginScreenTouch(event);
  }
  if (event.pointerId !== state.screenPointerId && state.screenPointerId != null) return;
  releaseScreenThrow(event);
  liftScreenHand();
});
stage?.addEventListener("pointercancel",(event)=>{
  if (!screenTouch()) return;
  if (event.pointerId !== state.screenPointerId) return;
  if (state.game === "pop-quiz-toss") cancelQuizThrow();
  liftScreenHand();
});
stage?.addEventListener("pointerleave",()=>{
  if (screenTouch()) return;
  if (state.demo) state.handData = [];
});
function screenPoint(touch) {
  return {clientX: touch.clientX, clientY: touch.clientY};
}
stage?.addEventListener("touchstart",(event)=>{
  if (isPopQuizUi(event)) return;
  if (!screenTouch() || state.screenDown || !event.changedTouches?.length) return;
  beginScreenTouch(event);
},{passive:false});
stage?.addEventListener("touchmove",(event)=>{
  if (!screenTouch() || !state.screenDown) return;
  const touch = [...event.touches].find((row) => row.identifier === state.screenPointerId) || event.touches[0];
  if (!touch) return;
  event.preventDefault();
  placeScreenHand(screenPoint(touch));
  updateObjectGame();
  updateTrace();
  updatePicturePlay();
  updatePopQuizToss(performance.now());
},{passive:false});
stage?.addEventListener("touchend",(event)=>{
  if (!screenTouch()) return;
  const touch = [...(event.changedTouches || [])][0];
  if (touch && state.screenPointerId == null) beginScreenTouch(event);
  const ended = [...(event.changedTouches || [])].some((row) => row.identifier === state.screenPointerId);
  if (!ended && event.touches?.length) return;
  releaseScreenThrow(touch?screenPoint(touch):null);
  liftScreenHand();
},{passive:false});
stage?.addEventListener("touchcancel",()=>{
  if (!screenTouch()) return;
  if (state.game === "pop-quiz-toss") cancelQuizThrow();
  liftScreenHand();
});
$("start").addEventListener("click",()=>start(true));$("demo").addEventListener("click",()=>start(false));
$("play-game").addEventListener("click",()=>chooseGame());
$("game").addEventListener("change",()=>chooseGame());
$("letter").addEventListener("change",()=>chooseGame());
$("hear").addEventListener("click",()=>speak(state.spokenPrompt));
$("mic").addEventListener("click",startListening);
$("check").addEventListener("click",()=>checkSpeech($("typed").value));
$("undo").addEventListener("click",()=>{
  state.trail=[];
  if (state.game==="color-picture") {
    state.ink=[];
    state.inkDown=false;
    state.painted=(state.picture?.segments||[]).map(()=>false);
  }
});
$("touch-mode")?.addEventListener("click",(event)=>{
  const choice = event.target?.closest?.("[data-touch]")?.getAttribute("data-touch");
  setTouchMode(choice || (state.touchMode==="screen"?"air":"screen"));
});
$("age")?.addEventListener("change",()=>{
  const select = $("age");
  if (select) select.dataset.touched = "1";
  state.age = select?.value || state.age;
});
$("pace")?.addEventListener("change", () => {
  state.pace = $("pace")?.value || "patient";
});
$("mirror-pace")?.addEventListener("change", () => {
  const select = $("mirror-pace");
  if (select) select.dataset.touched = "1";
  state.mirrorPace = mirrorPace(select?.value).id;
  if (state.mirror) state.mirror.pace = state.mirrorPace;
  if (state.ninja) state.ninja.pace = state.mirrorPace;
});
fillNinjaTechniques();
$("ninja-element")?.addEventListener("change", () => {
  fillNinjaTechniques(ninjaTechniqueList($("ninja-element").value)[0]?.id);
  if (state.game === "ninja-weave") chooseGame();
});
$("ninja-technique")?.addEventListener("change", () => {
  if (state.game === "ninja-weave") chooseGame();
});
$("show-words")?.addEventListener("change", () => {
  state.showWords = Boolean($("show-words")?.checked);
  renderSpokenWords();
});
$("show-guide")?.addEventListener("change",updateGuideLayer);
for (const id of ["show-face","show-hands","show-trail","show-measures","show-readout"]) {
  $(id)?.addEventListener("change",renderVisionReadout);
}
$("mute")?.addEventListener("click",()=>{state.muted=!state.muted;setText("mute",state.muted?"🔇":"🔊");$("mute")?.setAttribute("aria-pressed",String(state.muted));if(state.muted)cancelSpeech();});
function phonePlay(){
  return document.body.classList.contains("phone-play");
}
$("fullscreen")?.addEventListener("click",()=>{
  if (document.fullscreenElement) {
    document.exitFullscreen?.();
    document.body.classList.remove("stage-fill");
    return;
  }
  const play=$("play");
  const request=play?.requestFullscreen?.();
  if (request && request.catch) request.catch(()=>document.body.classList.add("stage-fill"));
  else document.body.classList.add("stage-fill");
});
function setChromeHidden(hidden){
  document.body.classList.toggle("chrome-hidden",!!hidden);
  const btn=$("chrome-toggle");
  if(!btn) return;
  const innerFull=document.fullscreenElement===$("play");
  btn.hidden=!phonePlay() && !innerFull && !hidden;
  btn.textContent=hidden?"Show options":"Hide options";
  btn.setAttribute("aria-pressed",String(!!hidden));
}
$("chrome-toggle")?.addEventListener("click",()=>setChromeHidden(!document.body.classList.contains("chrome-hidden")));
document.addEventListener("fullscreenchange",()=>{
  if(document.fullscreenElement!==$("play")) {
    document.body.classList.remove("stage-fill");
    setChromeHidden(false);
  } else setChromeHidden(document.body.classList.contains("chrome-hidden"));
});
window.addEventListener("message",(event)=>{
  const data=event.data;
  if(!data||data.type!=="salareen-chrome") return;
  setChromeHidden(!!data.hidden);
});
$("home")?.addEventListener("click",()=>{if(state.stream)state.stream.getTracks().forEach((t)=>t.stop());location.reload();});
$("clear-data")?.addEventListener("click",()=>{localStorage.removeItem(state.localKey);state.activityEvents=[];state.fun=0;state.combo=0;renderScore();renderDashboard();});

// Deterministic visual smoke-test entry point: no camera permission prompt and
// no recording. It is also useful when an adult wants to inspect every overlay
// before allowing camera access.
function readStoredTouchAge() {
  try {
    return profileTouchAge({
      ageYears: localStorage.getItem("onboarding_age") || "",
      ageBand: localStorage.getItem("onboarding_age_band") || "",
    });
  } catch (_) {
    return "";
  }
}
function seedPlayAge() {
  let query = "";
  try {
    const params = new URLSearchParams(location.search);
    query = params.get("age") || params.get("age_band") || "";
  } catch (_) {}
  const next = profileTouchAge({query}) || readStoredTouchAge();
  const select = $("age");
  if (select && next && select.dataset.touched !== "1" && [...select.options].some((opt) => opt.value === next)) {
    select.value = next;
  }
  state.age = select?.value || next || state.age || "7-10";
}
seedPlayAge();
const coarseTablet = window.matchMedia("(pointer: coarse) and (max-width: 1400px)").matches;
const embedMobile=new URLSearchParams(location.search).get("embed")==="mobile"
  || window.matchMedia("(max-width: 1180px)").matches
  || coarseTablet;
if (embedMobile) {
  document.body.classList.add("phone-play");
  const share=$("share");
  if (share) share.checked=true;
  $("vision-tools")?.removeAttribute("open");
  setChromeHidden(false);
  syncTouchToggle();
}
function pickLaunchGame() {
  const select = $("game");
  if (!select) return;
  const rawRequested = new URLSearchParams(location.search).get("game");
  // Math Toss was renamed; old links and app builds still ask for it.
  const requested = rawRequested === "math-toss" ? "pop-quiz-toss" : rawRequested;
  const options = [...select.options].map((opt) => opt.value).filter((id) => GAMES.includes(id));
  if (requested) {
    if (options.includes(requested)) select.value = requested;
    return;
  }
  if (!options.length) return;
  select.value = options[Math.floor(Math.random() * options.length)];
}
pickLaunchGame();
if (new URLSearchParams(location.search).get("demo")==="1"
    || new URLSearchParams(location.search).get("game")==="karaoke") {
  requestAnimationFrame(()=>start(false));
}
