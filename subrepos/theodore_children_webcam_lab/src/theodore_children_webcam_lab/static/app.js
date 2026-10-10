import {
  centroid, colorLine, dotHit, dotRadius, dotsFor, markerRadius, outlineCoverage, outlinePassed,
  sceneForWord, scratchCoverage, scratchPassed, segmentAt, swatchHit, swatchLayout,
} from "./picture_play.js";
import {
  FIST_MAX_PALMS, HEART_TIPS_PALMS, HEART_THUMBS_PALMS, HEART_WRISTS_PALMS,
  HEART_CLEFT_PALMS, HEART_POINT_PALMS,
  KISS_NEAR_FACES, KISS_AWAY_FACES, HAND_BONES,
  coverFrame, fingersPointed, handShape, heartRatios, isHeartShape, mapMirroredLandmark, syntheticHand,
  traceProgress,
} from "./vision_math.js";

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
  "trace-letter","trace-picture","color-picture","connect-dots","trace-outline","say-letter",
  "repeat-after-me","pronounce-word","rhyme-time","listen-answer","missing-word",
  "opposites","explain-it","sum-it-up","prove-it","story-order","how-many",
  "same-or-different","finish-the-line","spell-aloud",
  "oh-behave","heart","idea",
  "fist-bump","wow","blow-kiss","wink","make-pose","balloon","fish","popcorn",
  "fruit-cut","air-drums","bird-flap","head-bop","face-chase","stand-sit",
  "dance-freeze","rainbow-reach",
];
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
  handMotion:0, serverTts:null, speechToken:0, audioIndex:0, audioRound:null,
  touchMode:"air", crayon:null, ink:[], inkDown:false, screenDown:false, screenPointerId:null,
};

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

function setPrompt(title, copy, speakText="") {
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
function mirrored(point) {
  return mapMirroredLandmark(point, videoFrame());
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

async function start(camera=true) {
  state.age = $("age")?.value || "7-10";
  state.theme = $("theme")?.value || "mix";
  state.seated = Boolean($("seated")?.checked);
  state.share = Boolean($("share")?.checked);
  state.demo = !camera;
  $("setup")?.classList.add("hidden");
  $("play")?.classList.remove("hidden");
  stage?.classList.toggle("demo", state.demo);
  resizeCanvas(); loadLocalAnalytics();
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
  return {points,bs,cx,cy,width:maxX-minX,height:maxY-minY,expression,confidence,region,smile};
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
  if (video.currentTime===state.lastVideoTime) return;
  state.lastVideoTime=video.currentTime;
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
    if (state.hands && !screenTouch()) {
      const result=state.hands.detectForVideo(video,now);
      const labels=(result.handedness||[]).map(row=>row?.[0]?.categoryName||"");
      const previous=state.handData.map(hand=>hand.tip);
      state.handData=(result.landmarks||[]).map((points,i)=>handMetrics(points,labels[i])).filter(Boolean);
      state.handMotion=state.handData.reduce((max,hand,i)=>Math.max(max,previous[i]?distance(hand.tip,previous[i]):0),0);
    }
  } catch (error) { console.warn("[children-lab] hand frame skipped",error); }
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
  if (switchedOn("show-trail") && state.trail.length) {
    ctx.lineWidth=12;ctx.lineCap="round";ctx.lineJoin="round";
    const grad=ctx.createLinearGradient(0,0,w,h);grad.addColorStop(0,"#f472b6");grad.addColorStop(.5,"#fde047");grad.addColorStop(1,"#34d399");
    ctx.strokeStyle=grad;ctx.beginPath();state.trail.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.stroke();
  }
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
  if (!["trace-letter","trace-picture"].includes(state.game)) return;
  if (state.roundDone || performance.now() < (state.traceHoldUntil || 0)) return;
  const hand=state.handData.find(h=>h.indexUp)||state.handData[0];
  if (!hand?.tip) return;
  const {w,h}=stageBox();
  if (!w || !h) return;
  const p=hand.tip, last=state.trail.at(-1);
  if (!last || distance(p,last)>4) {
    state.trail.push({x:p.x,y:p.y,nx:p.x/w,ny:p.y/h,t:performance.now()});
  }
  const normalized = state.trail.map((pt) => ({x:pt.nx, y:pt.ny}));
  const progress=traceProgress(normalized,state.age);
  if (progress.passed) succeed("Beautiful tracing!");
}

function fingerPoint() {
  const hand = state.handData.find((item) => item.indexUp) || state.handData[0];
  if (!hand?.tip) return null;
  const {w, h} = stageBox();
  if (!w || !h) return null;
  return {x: hand.tip.x / w, y: hand.tip.y / h, px: hand.tip.x, py: hand.tip.y};
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
  return state.handData.find((hand) => fingersPointed(hand)) || null;
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
  if (!state.crayon || !fingersPointed(hand)) {
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
    state.dotCursor += 1;
    if (state.dotCursor >= dots.length) succeed("You connected every number!");
    return;
  }
  const last = state.trail.at(-1);
  if (!last || distance({x: tip.px, y: tip.py}, last) > 4) {
    state.trail.push({x: tip.px, y: tip.py, nx: tip.x, ny: tip.y, t: performance.now()});
  }
  const coverage = outlineCoverage(
    state.trail.map((point) => ({x: point.nx, y: point.ny})),
    scene.outline,
    state.age === "4-6" ? 0.07 : 0.05,
  );
  if (state.trail.length >= 8 && outlinePassed(coverage, state.age)) succeed("You traced the picture!");
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
  return Math.max(64, Math.min(w,h)*0.09);
}

function updateObjectGame() {
  if (!OBJECT_GAMES.has(state.game) || !state.object?.el?.isConnected) return;
  const center=objectCenter();if(!center)return;
  const radius=catchRadius();
  let hit=false;
  if (state.game==="popcorn") {
    if (state.faceData?.expression==="mouth-o") {
      const box=stageBox(),face={x:state.faceData.cx*box.w,y:state.faceData.cy*box.h};
      // Catch radius follows the face, so a child sitting back is not penalised.
      hit=distance(face,center)<Math.max(radius,state.faceData.width*box.w*.75);
    }
  } else {
    const hand=state.handData.find(h=>h.indexUp)||state.handData[0];
    if(hand?.tip) {
      const last=state.lastTip||hand.tip,velocity=distance(hand.tip,last);
      state.lastTip=hand.tip;
      hit=distance(hand.tip,center)<radius && (state.game!=="fruit-cut"||velocity>10);
    }
  }
  if(hit && !state.object.hit){
    state.object.hit=true;
    const say=reactToHit(state.game)||"Great catch!";
    const round=state.roundId;
    setTimeout(()=>{if(state.roundId===round)succeed(say);},280);
  }
}

function updateGestureGame(now) {
  if (state.game==="heart" && isHeart(state.handData)) succeed("A heart made with two hands!");
  else if (state.game==="idea" && state.handData.some(h=>h.indexUp)) succeed("What a bright idea!");
  else if (state.game==="fist-bump") {
    const fist=state.handData.find(h=>h.fist);
    if (fist && distance(fist.tip, targetPoint())<catchRadius()) succeed("Fist bump!");
  }
  else if (state.game==="wow" && state.faceData?.expression==="surprised") succeed("That is a wonderful wow face!");
  else if (state.game==="wink" && state.faceData?.expression?.startsWith("wink-")) succeed("Wink-tastic!");
  else if (state.game==="blow-kiss") {
    // The old version succeeded as soon as the hand was no longer "near" the
    // face — which also happened when the face left the frame, so the round
    // passed itself. Both steps now require a tracked face, and the hand has to
    // actually travel outward rather than merely stop being close.
    if (!state.faceData) {
      setPrompt("I need to see you","Come back into the camera so I can see your kiss.");
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
  } else if (state.game==="make-pose" && state.handData.length>=2) {
    const high=state.handData.filter(h=>h.wrist.y<stageBox().h*.48).length;
    if(high>=2)succeed("Hero pose complete!");
  }
  else if (state.game==="oh-behave") {
    if (!state.faceData) {
      if (!state.pausedAt) {
        state.pausedAt = now;
        setPrompt("I need to see you","Come back into the camera. The timer is paused.");
      }
      return;
    }
    if (state.pausedAt) {
      state.deadline += now - state.pausedAt;
      state.pausedAt = 0;
    }
    const remaining=Math.max(0,state.deadline-now);setText("countdown",(remaining/1000).toFixed(1));
    if(state.faceData.expression===state.targetExpression&&state.faceData.region===state.targetRegion&&state.faceData.confidence>=.55) succeed("Perfect face match!");
    else if(remaining<=0) fail("Almost — match the face and the spot!");
  } else if (state.game==="face-chase" && state.faceData?.region===state.targetRegion) succeed("You found the face spot!");
  else if (state.game==="air-drums") {
    if(now-state.beatAt>650){state.beatAt=now;state.phase=(state.phase+1)%2;setTarget(state.phase?"left":"right","🥁");state.padHeld=false;}
    const hand=state.handData.find(h=>h.tip&&distance(h.tip,targetPoint())<catchRadius());
    if(hand && !state.padHeld){state.padHeld=true;state.hitCount+=1;if(state.hitCount>=6)succeed("Amazing air drums!");}
    if(!hand) state.padHeld=false;
  } else if (state.game==="bird-flap" && state.handData.length>=2) {
    const y=(state.handData[0].wrist.y+state.handData[1].wrist.y)/2;
    if(state.lastHandY!=null&&Math.abs(y-state.lastHandY)>28){state.hitCount+=1;state.lastHandY=y;}
    else if(state.lastHandY==null)state.lastHandY=y;
    if(state.hitCount>=8)succeed("You flew like a bird!");
  } else if (state.game==="head-bop" && state.faceData) {
    const y=state.faceData.cy*stageBox().h;
    if(state.lastFaceY!=null&&Math.abs(y-state.lastFaceY)>18){state.hitCount+=1;state.lastFaceY=y;}
    else if(state.lastFaceY==null)state.lastFaceY=y;
    if(state.hitCount>=7)succeed("Head-bop beat master!");
  } else if (state.game==="stand-sit") {
    if (!state.faceData) {
      setPrompt("I need to see you","Step back so Theodore can see your face.");
      return;
    }
    const y=state.faceData.cy;
    if(state.phase===0&&y<.38){state.phase=1;setPrompt("Now sit down","Move gently back to your seat.");}
    if(state.phase===1&&y>.57)succeed("Stand and sit complete!");
  } else if (state.game==="rainbow-reach" && state.handData.length>=2) {
    const tips=state.handData.map(h=>h.tip),box=stageBox();if(tips.every(p=>p.y<box.h*.35)&&Math.abs(tips[0].x-tips[1].x)>box.w*.45)succeed("Rainbow reach!");
    } else if (state.game==="dance-freeze") {
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
  const hand=state.handData[0]?.tip;
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
  return motion>7;
}
function targetPoint(){
  if (!target || target.classList.contains("hidden")) return {x:-9999,y:-9999};
  const r=target.getBoundingClientRect(),s=stage.getBoundingClientRect();
  if (!r.width || !r.height) return {x:-9999,y:-9999};
  return{x:r.left-s.left+r.width/2,y:r.top-s.top+r.height/2};
}

function loop(now) {
  if(!state.running)return;
  detectFrame();drawVision();updateTrace();updatePicturePlay();updateObjectGame();updateGestureGame(now);
  requestAnimationFrame(loop);
}

function chooseGame() {
  clearTimeout(state.roundTimer);clearTimeout(state.failTimer);cancelSpeech();
  state.roundId += 1; const round = state.roundId; state.roundDone=false;
  clearRound();
  const select=$("game");
  if (!select) return;
  const previousGame=state.game;
  state.game=select.value;
  if (state.game!==previousGame) state.audioIndex=0;
  state.startedAt=performance.now();state.attempts=1;state.hitCount=0;state.phase=0;state.padHeld=false;state.pausedAt=0;
  updateGuideLayer();
  const letter=$("letter")?.value,word=LETTER_WORDS[letter];
  if(state.game==="trace-letter"){
    state.traceHoldUntil=performance.now()+500;
    setPrompt(`Trace ${letter}`,"Point one finger up and follow the glowing letter.",`Trace the letter ${letter}.`);
  }
  else if(state.game==="trace-picture")setPrompt(`Trace the ${word}`,"Use one finger to draw around the picture.",`Now trace the ${word}.`);
  else if(state.game==="color-picture"||state.game==="connect-dots"||state.game==="trace-outline"){
    armPictureRound(word);
    state.traceHoldUntil=performance.now()+500;
    if(state.game==="color-picture")refreshColorPrompt(false);
    else if(state.game==="connect-dots")setPrompt(`Connect the ${word}`,"Touch the numbers in order, starting at 1.",`Connect the numbered dots on the ${word}.`);
    else setPrompt(`Trace the ${word}`,"Follow the outline with one finger. It does not need to be perfect.",`Trace the outline of the ${word}.`);
  }
  else if(state.game==="say-letter")setPrompt(`Say ${letter}`,"Tap the microphone or type what you said.",`Listen, then say the letter ${letter}.`);
  else if(AUDIO_GAMES.has(state.game)){
    setPrompt("Listen","Theodore is getting the next listening round.");
    void armAudioRound(round);
  }
  else if(state.game==="oh-behave"){
    state.targetRegion=randomRegion();state.targetExpression=randomOf(EXPRESSIONS);state.deadline=performance.now()+state.timerMs;
    $("countdown")?.classList.remove("hidden");setTarget(state.targetRegion,expressionEmoji(state.targetExpression));
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
    state.failTimer=setTimeout(()=>{
      if(state.roundId!==round) return;
      if(state.object&&!state.object.hit)fail("So close! Try the next one.");
    },state.game==="popcorn"?4200:5800);
  } else if(state.game==="face-chase"){state.targetRegion=randomRegion();setTarget(state.targetRegion,"😊");setPrompt("Face chase","Move your face into the glowing circle.");}
  else if(state.game==="air-drums"){setTarget("left","🥁");setPrompt("Air drums","Hit the drum pads with your hands on the beat.");state.beatAt=performance.now();}
  else if(state.game==="bird-flap"){setPrompt("Flap like a bird","Lift both hands up and down. Fly!");spawnObject("","🐦");}
  else if(state.game==="head-bop"){setPrompt("Bop to the beat","Move your head gently up and down.");}
  else if(state.game==="stand-sit"){
    if(state.seated){setPrompt("Seated reach","Seated-only is on. Reach both hands high instead.");state.game="rainbow-reach";}
    else setPrompt("Stand up","Step back so Theodore sees you, then stand gently.");
  } else if(state.game==="dance-freeze"){setPrompt("Dance!","Move any way you like… freeze when Theodore says freeze.");spawnObject("","🎵");}
  else if(state.game==="rainbow-reach"){setPrompt("Rainbow reach","Stretch both hands toward opposite top corners.");}
  else if(!GAMES.includes(state.game)){setPrompt("Pick a game","That activity is not wired yet. Choose another from the list.");}
  if (!AUDIO_GAMES.has(state.game)) {
    tellActivity(state.spokenPrompt);
    speak(state.spokenPrompt);
  }
}
function tellActivity(prompt) {
  if (!window.__THEODORE_LIVE_AUDIO_ACTIVE__ || !prompt) return;
  window.TheodoreLiveAudio?.noteActivity?.({
    id: String(state.game || "play") + ":" + prompt,
    prompt: "The webcam game on screen is the activity. Coach it in one short sentence and wait. Do not reveal the answer. " + prompt,
  });
}

function randomRegion(){const keys=Object.keys(REGIONS).filter(k=>!state.seated||!k.startsWith("bottom"));return randomOf(keys)||"center";}
function expressionEmoji(kind){return({happy:"😄",surprised:"😮","wink-left":"😉","wink-right":"😉","mouth-o":"😗",sleepy:"😴"})[kind]||"🙂";}

function clearRound() {
  hideTarget();
  for (const node of [...spriteLayer.querySelectorAll(".sprite,.miss-gag,.miss-caption")]) node.remove();
  $("countdown")?.classList.add("hidden");
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
  if(state.roundDone)return;state.roundDone=true;state.combo+=1;
  const round=state.roundId;
  const advanceLetter=state.game==="trace-letter"||PICTURE_PLAY.has(state.game);
  if(state.game==="oh-behave")state.timerMs=nextTimer(true);
  if (AUDIO_GAMES.has(state.game)) state.audioIndex=(state.audioIndex||0)+1;
  const result=calculateFun(true);state.fun=result.score;renderScore();fireworks();setPrompt("You did it!",message);
  recordEvent("success",result);tellActivity(`The child succeeded. Celebrate in one short sentence: ${message}`);speak(`You did it! ${message}`);
  clearTimeout(state.roundTimer);
  state.roundTimer=setTimeout(()=>{
    if(state.roundId!==round)return;
    state.roundDone=false;
    if(advanceLetter) pickNextLetter();
    chooseGame();
  }, advanceLetter?600:1900);
}
function fail(message) {
  if(state.roundDone)return;state.roundDone=true;state.combo=0;state.attempts+=1;
  const round=state.roundId;
  fadeMissedObject();
  const result=calculateFun(false);state.fun=result.score;renderScore();missGag();setPrompt("Almost!",message);
  recordEvent("retry",result);tellActivity(`The child missed. Encourage them in one short sentence: ${message}`);speak(`Almost! ${message}`);
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

async function speak(text) {
  if(state.muted||!text||window.__THEODORE_LIVE_AUDIO_ACTIVE__)return;
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
  if(event.detail?.active){
    cancelSpeech();
    setTimeout(()=>tellActivity(state.spokenPrompt),700);
  }
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
    tellActivity(data.speak);
    speak(data.speak);
  } catch (error) {
    if (state.roundId !== round) return;
    setPrompt("Listen again", "I could not load that listening round.");
  }
}
async function checkSpeech(heard) {
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
    components:result.components,celebration_kind:outcome==="success"?"fireworks":"",miss_gag_id:outcome==="retry"?state.lastGag||"":"",theme_pack:state.theme,seated_only:state.seated};
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
  const pose = event.altKey ? "fist" : "index";
  const primary = handMetrics(syntheticHand({x:nx,y:ny}, {pose}), "Pointer");
  state.handData = primary ? [primary] : [];
  if (event.shiftKey) {
    const other = handMetrics(syntheticHand({x:clamp01(1-nx), y:ny}, {pose:"open"}), "Pointer-2");
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
function placeScreenHand(event) {
  const box = stage.getBoundingClientRect();
  const w = Math.max(1, box.width);
  const h = Math.max(1, box.height);
  stageRect = {w, h, left: box.left, top: box.top};
  const nx = clamp01((event.clientX - box.left) / w);
  const ny = clamp01((event.clientY - box.top) / h);
  state.handData = [{
    indexUp: true,
    fist: false,
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
  liftScreenHand();
  const btn = $("touch-mode");
  if (btn) {
    const screen = state.touchMode === "screen";
    btn.textContent = screen ? "Screen touch" : "Air touch";
    btn.setAttribute("aria-pressed", screen ? "true" : "false");
    btn.setAttribute(
      "aria-label",
      screen ? "Using screen touch. Switch to air touch." : "Using air touch. Switch to screen touch.",
    );
  }
  if (state.game === "color-picture" && state.picture) refreshColorPrompt(false);
}
function syncTouchToggle() {
  const btn = $("touch-mode");
  if (!btn) return;
  btn.hidden = !phonePlay();
  setTouchMode(state.touchMode || "air");
}
stage?.addEventListener("pointermove",(event)=>{
  if (screenTouch()) {
    if (!state.screenDown || event.pointerId !== state.screenPointerId) return;
    placeScreenHand(event);
    return;
  }
  applyDemoPointer(event);
});
stage?.addEventListener("pointerdown",(event)=>{
  if (screenTouch()) {
    if (state.screenPointerId != null) return;
    event.preventDefault();
    state.screenDown = true;
    state.screenPointerId = event.pointerId;
    stage.setPointerCapture?.(event.pointerId);
    placeScreenHand(event);
    return;
  }
  if (!state.demo) return;
  event.preventDefault();
  stage.setPointerCapture?.(event.pointerId);
  applyDemoPointer(event);
});
stage?.addEventListener("pointerup",(event)=>{
  if (!screenTouch()) return;
  if (event.pointerId !== state.screenPointerId) return;
  liftScreenHand();
});
stage?.addEventListener("pointercancel",(event)=>{
  if (!screenTouch()) return;
  if (event.pointerId !== state.screenPointerId) return;
  liftScreenHand();
});
stage?.addEventListener("pointerleave",()=>{
  if (screenTouch()) return;
  if (state.demo) state.handData = [];
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
$("touch-mode")?.addEventListener("click",()=>{
  setTouchMode(state.touchMode==="screen"?"air":"screen");
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
const embedMobile=new URLSearchParams(location.search).get("embed")==="mobile"
  || window.matchMedia("(max-width: 760px)").matches;
if (embedMobile) {
  document.body.classList.add("phone-play");
  const share=$("share");
  if (share) share.checked=true;
  $("vision-tools")?.removeAttribute("open");
  setChromeHidden(false);
  syncTouchToggle();
}
if (new URLSearchParams(location.search).get("demo")==="1") {
  requestAnimationFrame(()=>start(false));
}
const requestedGame=new URLSearchParams(location.search).get("game");
const gameSelect=$("game");
if (requestedGame && gameSelect && [...gameSelect.options].some((opt)=>opt.value===requestedGame)) {
  gameSelect.value=requestedGame;
}
