import {
  FIST_MAX_PALMS, HEART_TIPS_PALMS, HEART_THUMBS_PALMS, HEART_WRISTS_PALMS,
  KISS_NEAR_FACES, KISS_AWAY_FACES,
  handShape, heartRatios, isHeartShape, syntheticHand,
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
// Keep in lockstep with game_engine.GAME_MENU / /api/child/content. A game in
// the menu without a matching chooseGame + update* branch is a missing game.
const GAMES = [
  "trace-letter","trace-picture","say-letter","oh-behave","heart","idea",
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
  handMotion:0, serverTts:null, speechToken:0
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
function mirrored(point) {
  if (!point) return {x:0,y:0,z:0};
  const {w,h} = stageBox();
  return {x:(1-point.x)*w,y:point.y*h,z:point.z || 0};
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
      const runtime=await fetch("/health").then(response=>response.ok?response.json():null);
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
        state.handConnections = (vision.HandLandmarker.HAND_CONNECTIONS || []).map(c=>[c.start,c.end]);
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
    if (state.hands) {
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
  drawGuide(w,h);
  ctx.save();ctx.lineWidth=3;ctx.strokeStyle="#a78bfa";ctx.fillStyle="#fde68a";
  if (switchedOn("show-hands")) {
    for (const hand of state.handData) {
      if (!hand.points?.length) continue;
      for (const [a,b] of state.handConnections||[]) {
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

function drawGuide(w,h) {
  if (!switchedOn("show-guide") || !["trace-letter","trace-picture"].includes(state.game)) return;
  const letter=$("letter")?.value;
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

function traceProgress(points, ageBand) {
  const cells = new Set();
  let inside = 0;
  for (const p of points) {
    if (p.x >= 0.22 && p.x <= 0.78 && p.y >= 0.18 && p.y <= 0.82) {
      inside += 1;
      cells.add(`${Math.round(p.x*8)}:${Math.round(p.y*8)}`);
    }
  }
  // A real letter trace is a narrow path, not an area-filling scribble. The old
  // 16/22-cell requirement made clean A/B/C outlines effectively impossible
  // even after the child visibly followed the guide.
  const need = ageBand === "4-6" ? 10 : 14;
  const sampleScore=Math.min(1,points.length/40);
  const insideScore=points.length?Math.min(1,inside/(points.length*.55)):0;
  const coverageScore=Math.min(1,cells.size/need);
  return {percent:Math.round(100*Math.min(sampleScore,insideScore,coverageScore)),passed:sampleScore>=1&&insideScore>=1&&coverageScore>=1,cells:cells.size};
}
function tracePass(points, ageBand) {
  return traceProgress(points,ageBand).passed;
}

function updateTrace() {
  if (!["trace-letter","trace-picture"].includes(state.game)) return;
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
      return `tips ${near(m.tips)}/<${HEART_TIPS_PALMS} · thumbs ${near(m.thumbs)}/<${HEART_THUMBS_PALMS} · wrists ${near(m.wrists)}/>${HEART_WRISTS_PALMS}`;
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
  const letter=$("letter")?.value, picture=state.game==="trace-picture";
  glyph.textContent=picture?(PICTURE_EMOJI[LETTER_WORDS[letter]]||"✨"):letter;
  glyph.classList.toggle("picture",picture);
}

function setTarget(region,content,kind="") {
  const [x,y]=REGIONS[region]||REGIONS.center;
  target.className=`target ${kind}`.trim();target.textContent=content;
  target.style.left=`calc(${x*100}% - 72px)`;target.style.top=`calc(${y*100}% - 72px)`;
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
  detectFrame();drawVision();updateTrace();updateObjectGame();updateGestureGame(now);
  requestAnimationFrame(loop);
}

function chooseGame() {
  clearTimeout(state.roundTimer);clearTimeout(state.failTimer);cancelSpeech();
  state.roundId += 1; const round = state.roundId; state.roundDone=false;
  clearRound();
  const select=$("game");
  if (!select) return;
  state.game=select.value;state.startedAt=performance.now();state.attempts=1;state.hitCount=0;state.phase=0;state.padHeld=false;state.pausedAt=0;
  updateGuideLayer();
  const letter=$("letter")?.value,word=LETTER_WORDS[letter];
  if(state.game==="trace-letter")setPrompt(`Trace ${letter}`,"Point one finger up and follow the glowing letter.",`Trace the letter ${letter}.`);
  else if(state.game==="trace-picture")setPrompt(`Trace the ${word}`,"Use one finger to draw around the picture.",`Now trace the ${word}.`);
  else if(state.game==="say-letter")setPrompt(`Say ${letter}`,"Tap the microphone or type what you said.",`Listen, then say the letter ${letter}.`);
  else if(state.game==="oh-behave"){
    state.targetRegion=randomRegion();state.targetExpression=randomOf(EXPRESSIONS);state.deadline=performance.now()+state.timerMs;
    $("countdown")?.classList.remove("hidden");setTarget(state.targetRegion,expressionEmoji(state.targetExpression));
    setPrompt("Oh behave!",`Make a ${state.targetExpression} face inside the glowing circle.`);
  } else if(state.game==="heart"){setTarget(randomRegion(),"💖");setPrompt("Make a heart","Cup both hands together like a heart.");}
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
  speak(state.spokenPrompt);
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

function succeed(message) {
  if(state.roundDone)return;state.roundDone=true;state.combo+=1;
  const round=state.roundId;
  if(state.game==="oh-behave")state.timerMs=nextTimer(true);
  const result=calculateFun(true);state.fun=result.score;renderScore();fireworks();setPrompt("You did it!",message);
  recordEvent("success",result);speak(`You did it! ${message}`);
  clearTimeout(state.roundTimer);
  state.roundTimer=setTimeout(()=>{if(state.roundId!==round)return;state.roundDone=false;chooseGame();},1900);
}
function fail(message) {
  if(state.roundDone)return;state.roundDone=true;state.combo=0;state.attempts+=1;
  const round=state.roundId;
  fadeMissedObject();
  const result=calculateFun(false);state.fun=result.score;renderScore();missGag();setPrompt("Almost!",message);
  recordEvent("retry",result);speak(`Almost! ${message}`);
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
  if(event.detail?.active)cancelSpeech();
});

function startListening() {
  if (state.game!=="say-letter") {
    setPrompt("Say the letter first","Switch to Say the letter, then use the microphone.");
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
async function checkSpeech(heard) {
  if (state.game!=="say-letter") {
    setPrompt("Say the letter first","Switch to Say the letter, then check what was said.");
    return;
  }
  const letter=$("letter")?.value;
  try{
    const response=await fetch("/api/child/pronounce",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({target:letter,heard,kind:"letter"})});
    if (!response.ok) throw new Error(String(response.status));
    const result=await response.json();result.passed?succeed(result.feedback):fail(result.feedback);
  }catch(error){setPrompt("Try again","I could not check that answer.");}
}

function recordEvent(outcome,result) {
  const event={activity_id:state.game,age_band:state.age,outcome,attempts:state.attempts,duration_ms:result.duration,fun_score:result.score,
    components:result.components,celebration_kind:outcome==="success"?"fireworks":"",miss_gag_id:outcome==="retry"?state.lastGag||"":"",theme_pack:state.theme,seated_only:state.seated};
  state.activityEvents.push(event);state.activityEvents=state.activityEvents.slice(-100);
  localStorage.setItem(state.localKey,JSON.stringify(state.activityEvents));renderDashboard();
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

canvas?.addEventListener("pointermove",event=>{
  if(!state.demo)return; applyDemoPointer(event);
});
stage?.addEventListener("pointermove",applyDemoPointer);
stage?.addEventListener("pointerdown",applyDemoPointer);
stage?.addEventListener("contextmenu",(event)=>{if(state.demo)event.preventDefault();});
stage?.addEventListener("pointerleave",()=>{if(state.demo){state.handData=[];state.faceData=null;}});
$("start")?.addEventListener("click",()=>start(true));
$("demo")?.addEventListener("click",()=>start(false));
$("play-game")?.addEventListener("click",()=>chooseGame());
$("game")?.addEventListener("change",()=>chooseGame());
$("letter")?.addEventListener("change",()=>chooseGame());
$("hear")?.addEventListener("click",()=>speak(state.spokenPrompt));
$("mic")?.addEventListener("click",startListening);
$("check")?.addEventListener("click",()=>checkSpeech($("typed")?.value || ""));
$("undo")?.addEventListener("click",()=>{state.trail=[];});
$("show-guide")?.addEventListener("change",updateGuideLayer);
for (const id of ["show-face","show-hands","show-trail","show-measures","show-readout"]) {
  $(id)?.addEventListener("change",renderVisionReadout);
}
$("mute")?.addEventListener("click",()=>{state.muted=!state.muted;setText("mute",state.muted?"🔇":"🔊");$("mute")?.setAttribute("aria-pressed",String(state.muted));if(state.muted)cancelSpeech();});
$("fullscreen")?.addEventListener("click",()=>document.fullscreenElement?document.exitFullscreen():$("play")?.requestFullscreen?.());
$("home")?.addEventListener("click",()=>{if(state.stream)state.stream.getTracks().forEach((t)=>t.stop());location.reload();});
$("clear-data")?.addEventListener("click",()=>{localStorage.removeItem(state.localKey);state.activityEvents=[];state.fun=0;state.combo=0;renderScore();renderDashboard();});

// Deterministic visual smoke-test entry point: no camera permission prompt and
// no recording. It is also useful when an adult wants to inspect every overlay
// before allowing camera access.
if (new URLSearchParams(location.search).get("demo")==="1") {
  requestAnimationFrame(()=>start(false));
}
