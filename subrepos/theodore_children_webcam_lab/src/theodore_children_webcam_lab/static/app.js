const $ = (id) => document.getElementById(id);
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
const state = {
  stream:null, face:null, hands:null, running:false, demo:false, lastVideoTime:-1,
  lastMpTs:0, faceData:null, handData:[], trail:[], game:null, startedAt:0,
  attempts:1, combo:0, fun:0, muted:false, age:"7-10", theme:"mix", seated:false,
  share:false, timerMs:8000, deadline:0, pausedAt:0, targetRegion:"center",
  targetExpression:"happy", object:null, phase:0, lastFaceY:null, lastHandY:null,
  beatAt:0, recognition:null, activityEvents:[], spokenPrompt:"Let's play!",
  localKey:"theodoreChildrenFunV1", roundId:0, roundDone:false, roundTimer:0,
  failTimer:0, audio:null, padHeld:false, hitCount:0, lastTip:null
};

const canvas = $("overlay");
const ctx = canvas.getContext("2d");
const video = $("camera");
const stage = $("stage");
const spriteLayer = $("sprite-layer");
const target = $("target");

for (const letter of Object.keys(LETTER_WORDS)) {
  const option = document.createElement("option");
  option.value = letter; option.textContent = `${letter} — ${LETTER_WORDS[letter]}`;
  $("letter").append(option);
}

function resizeCanvas() {
  const box = stage.getBoundingClientRect();
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  canvas.width = Math.round(box.width * dpr);
  canvas.height = Math.round(box.height * dpr);
  canvas.style.width = `${box.width}px`; canvas.style.height = `${box.height}px`;
  ctx.setTransform(dpr,0,0,dpr,0,0);
  return {w:box.width,h:box.height};
}
new ResizeObserver(resizeCanvas).observe(stage);

function setPrompt(title, copy, speakText="") {
  $("prompt-title").textContent = title;
  $("prompt-copy").textContent = copy;
  state.spokenPrompt = speakText || `${title}. ${copy}`;
}
function setStatus(text) { $("vision-status").textContent = text; }
function clamp01(value) { return Math.max(0, Math.min(1, Number(value) || 0)); }
function randomOf(items) {
  if (!items || !items.length) return undefined;
  return items[Math.floor(Math.random() * items.length)];
}
function distance(a,b) { return Math.hypot(a.x-b.x,a.y-b.y); }
function mirrored(point) {
  if (!point) return {x:0,y:0,z:0};
  const {w,h} = stage.getBoundingClientRect();
  return {x:(1-point.x)*w,y:point.y*h,z:point.z || 0};
}
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[ch]));
}

async function start(camera=true) {
  state.age = $("age").value; state.theme = $("theme").value;
  state.seated = $("seated").checked; state.share = $("share").checked;
  state.demo = !camera;
  $("setup").classList.add("hidden"); $("play").classList.remove("hidden");
  resizeCanvas(); loadLocalAnalytics();
  if (camera) {
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("insecure-context");
      state.stream = await navigator.mediaDevices.getUserMedia({
        video:{facingMode:"user",width:{ideal:1280},height:{ideal:720}}, audio:false
      });
      video.srcObject = state.stream;
      await video.play();
      setStatus("Camera live · loading face & hands…");
      await initVision();
    } catch (error) {
      state.demo = true;
      setStatus(`Pointer demo · camera unavailable (${error.name || error.message || "blocked"})`);
    }
  } else setStatus("Pointer demo · move over the screen");
  state.running = true;
  requestAnimationFrame(loop);
  chooseGame();
}

async function initVision() {
  try {
    let moduleUrl=`${VISION_CDN}/+esm`,wasmUrl=`${VISION_CDN}/wasm`;
    let faceModel=`${MODEL_ROOT}/face_landmarker/face_landmarker/float16/1/face_landmarker.task`;
    let handModel=`${MODEL_ROOT}/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task`;
    try {
      const local=await fetch("/vendor/vision/tasks-vision.mjs",{method:"HEAD"});
      if(local.ok){moduleUrl="/vendor/vision/tasks-vision.mjs";wasmUrl="/vendor/vision/wasm";faceModel="/vendor/vision/face_landmarker.task";handModel="/vendor/vision/hand_landmarker.task";}
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

function fingerExtended(points, tip, pip) {
  return points?.[tip] && points?.[pip] && points[tip].y < points[pip].y - .025;
}
function handMetrics(points, label="") {
  if (!points?.length) return null;
  const fingers=[fingerExtended(points,8,6),fingerExtended(points,12,10),fingerExtended(points,16,14),fingerExtended(points,20,18)];
  const count=fingers.filter(Boolean).length + (Math.abs((points[4]?.x||0)-(points[3]?.x||0))>.035 ? 1 : 0);
  const tip=points[8], wrist=points[0];
  const tipToWrist = (tip && wrist) ? distance(tip, wrist) : 1;
  return {
    points,label,count,
    indexUp:fingers[0]&&!fingers[1]&&!fingers[2]&&!fingers[3],
    fist:count===0 && tipToWrist<0.22,
    tip:mirrored(points[8]),
    wrist:mirrored(points[0])
  };
}
function isHeart(hands) {
  if (hands.length<2) return false;
  const a=hands[0].points,b=hands[1].points;
  if (!a?.[8] || !b?.[8] || !a[4] || !b[4] || !a[0] || !b[0]) return false;
  return distance(a[8],b[8])<.14 && distance(a[4],b[4])<.16 && distance(a[0],b[0])>.13;
}

function detectFrame() {
  if ((!state.face && !state.hands) || video.readyState<2) return;
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
      state.handData=(result.landmarks||[]).map((points,i)=>handMetrics(points,labels[i])).filter(Boolean);
    }
  } catch (error) { console.warn("[children-lab] hand frame skipped",error); }
}

function drawVision() {
  const {w,h}=stage.getBoundingClientRect();
  ctx.clearRect(0,0,w,h);
  drawGuide(w,h);
  ctx.save();ctx.lineWidth=3;ctx.strokeStyle="#a78bfa";ctx.fillStyle="#fde68a";
  for (const hand of state.handData) {
    if (!hand.points?.length) continue;
    for (const [a,b] of state.handConnections||[]) {
      if (!hand.points[a] || !hand.points[b]) continue;
      const p=mirrored(hand.points[a]),q=mirrored(hand.points[b]);
      ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(q.x,q.y);ctx.stroke();
    }
    for (const i of [4,8,12,16,20]) {if(!hand.points[i])continue;const p=mirrored(hand.points[i]);ctx.beginPath();ctx.arc(p.x,p.y,5,0,Math.PI*2);ctx.fill();}
  }
  if (state.faceData?.points) {
    ctx.strokeStyle="#5eead4";ctx.lineWidth=2;ctx.beginPath();
    let started=false;
    for (const i of [10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109]) {
      const p=state.faceData.points[i];if(!p)continue;const q=mirrored(p);
      if(!started){ctx.moveTo(q.x,q.y);started=true;} else ctx.lineTo(q.x,q.y);
    }
    ctx.closePath();ctx.stroke();
  }
  if (state.trail.length) {
    ctx.lineWidth=12;ctx.lineCap="round";ctx.lineJoin="round";
    const grad=ctx.createLinearGradient(0,0,w,h);grad.addColorStop(0,"#f472b6");grad.addColorStop(.5,"#fde047");grad.addColorStop(1,"#34d399");
    ctx.strokeStyle=grad;ctx.beginPath();state.trail.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.stroke();
  }
  ctx.restore();
}

function drawGuide(w,h) {
  if (!["trace-letter","trace-picture"].includes(state.game)) return;
  const letter=$("letter").value;
  ctx.save();ctx.textAlign="center";ctx.textBaseline="middle";ctx.lineJoin="round";
  if (state.game==="trace-letter") {
    ctx.font=`900 ${Math.min(w,h)*.62}px ui-rounded, sans-serif`;
    ctx.lineWidth=state.age==="4-6"?38:26;ctx.strokeStyle="#ffffff88";ctx.setLineDash([16,12]);
    ctx.strokeText(letter,w/2,h/2+20);
  } else {
    ctx.font=`${Math.min(w,h)*.5}px serif`;ctx.globalAlpha=.68;
    const emoji={apple:"🍎",ball:"⚽",cat:"🐱",dragon:"🐉",elephant:"🐘",fish:"🐟",heart:"💖",popcorn:"🍿",rocket:"🚀",star:"⭐",teddy:"🧸"}[LETTER_WORDS[letter]]||"✨";
    ctx.fillText(emoji,w/2,h/2+10);
  }
  ctx.setLineDash([]);ctx.fillStyle="#fde047";ctx.beginPath();ctx.arc(w*.31,h*.2,10,0,Math.PI*2);ctx.fill();ctx.restore();
}

function tracePass(points, ageBand) {
  if (points.length < 40) return false;
  const cells = new Set();
  let inside = 0;
  for (const p of points) {
    if (p.x >= 0.22 && p.x <= 0.78 && p.y >= 0.18 && p.y <= 0.82) {
      inside += 1;
      cells.add(`${Math.round(p.x*8)}:${Math.round(p.y*8)}`);
    }
  }
  const need = ageBand === "4-6" ? 16 : 22;
  return inside >= points.length * 0.55 && cells.size >= need;
}

function updateTrace() {
  if (!["trace-letter","trace-picture"].includes(state.game)) return;
  const hand=state.handData.find(h=>h.indexUp)||state.handData[0];
  if (!hand?.tip) return;
  const {w,h}=stage.getBoundingClientRect();
  if (!w || !h) return;
  const p=hand.tip, last=state.trail.at(-1);
  if (!last || distance(p,last)>4) {
    state.trail.push({x:p.x,y:p.y,nx:p.x/w,ny:p.y/h,t:performance.now()});
  }
  const normalized = state.trail.map((pt) => ({x:pt.nx, y:pt.ny}));
  if (tracePass(normalized, state.age)) succeed("Beautiful tracing!");
}

function setTarget(region,content,kind="") {
  const [x,y]=REGIONS[region]||REGIONS.center;
  target.className=`target ${kind}`.trim();target.textContent=content;
  target.style.left=`calc(${x*100}% - 72px)`;target.style.top=`calc(${y*100}% - 72px)`;
}
function hideTarget(){target.classList.add("hidden");target.textContent="";}

function spawnObject(kind,content) {
  for (const node of [...spriteLayer.querySelectorAll(".sprite")]) node.remove();
  const el=document.createElement("div");el.className=`sprite ${kind}`;el.textContent=content;
  el.style.top=`${15+Math.random()*55}%`;if(kind==="balloon")el.style.left=`${10+Math.random()*75}%`;
  spriteLayer.append(el);state.object={el,kind,hit:false,roundId:state.roundId};return el;
}

function objectCenter() {
  const rect=state.object?.el?.getBoundingClientRect(),root=stage.getBoundingClientRect();
  return rect?{x:rect.left-root.left+rect.width/2,y:rect.top-root.top+rect.height/2}:null;
}

function updateObjectGame() {
  if (!OBJECT_GAMES.has(state.game) || !state.object?.el?.isConnected) return;
  const center=objectCenter();if(!center)return;
  let hit=false;
  if (state.game==="popcorn") {
    if (state.faceData?.expression==="mouth-o") {
      const box=stage.getBoundingClientRect(),face={x:state.faceData.cx*box.width,y:state.faceData.cy*box.height};
      hit=distance(face,center)<95;
    }
  } else {
    const hand=state.handData.find(h=>h.indexUp)||state.handData[0];
    if(hand?.tip) {
      const last=state.lastTip||hand.tip,velocity=distance(hand.tip,last);
      state.lastTip=hand.tip;
      hit=distance(hand.tip,center)<90 && (state.game!=="fruit-cut"||velocity>10);
    }
  }
  if(hit && !state.object.hit){
    state.object.hit=true;state.object.el.classList.add("hit");
    const round=state.roundId;
    setTimeout(()=>{if(state.roundId===round)succeed("Great catch!");},250);
  }
}

function updateGestureGame(now) {
  if (state.game==="heart" && isHeart(state.handData)) succeed("A heart made with two hands!");
  else if (state.game==="idea" && state.handData.some(h=>h.indexUp)) succeed("What a bright idea!");
  else if (state.game==="fist-bump" && state.handData.some(h=>h.fist)) succeed("Fist bump!");
  else if (state.game==="wow" && state.faceData?.expression==="surprised") succeed("That is a wonderful wow face!");
  else if (state.game==="wink" && state.faceData?.expression?.startsWith("wink-")) succeed("Wink-tastic!");
  else if (state.game==="blow-kiss") {
    const handNearFace=state.handData.some(h=>state.faceData&&h.tip&&Math.hypot(h.tip.x/stage.clientWidth-state.faceData.cx,h.tip.y/stage.clientHeight-state.faceData.cy)<.2);
    if(state.phase===0&&handNearFace&&state.faceData?.expression==="mouth-o")state.phase=1;
    if(state.phase===1&&state.handData.length&&!handNearFace)succeed("A lovely flying kiss!");
  } else if (state.game==="make-pose" && state.handData.length>=2) {
    const high=state.handData.filter(h=>h.wrist.y<stage.clientHeight*.48).length;
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
    const remaining=Math.max(0,state.deadline-now);$("countdown").textContent=(remaining/1000).toFixed(1);
    if(state.faceData.expression===state.targetExpression&&state.faceData.region===state.targetRegion&&state.faceData.confidence>=.55) succeed("Perfect face match!");
    else if(remaining<=0) fail("Almost — match the face and the spot!");
  } else if (state.game==="face-chase" && state.faceData?.region===state.targetRegion) succeed("You found the face spot!");
  else if (state.game==="air-drums") {
    if(now-state.beatAt>650){state.beatAt=now;state.phase=(state.phase+1)%2;setTarget(state.phase?"left":"right","🥁");state.padHeld=false;}
    const hand=state.handData.find(h=>h.tip&&distance(h.tip,targetPoint())<95);
    if(hand && !state.padHeld){state.padHeld=true;state.hitCount+=1;if(state.hitCount>=6)succeed("Amazing air drums!");}
    if(!hand) state.padHeld=false;
  } else if (state.game==="bird-flap" && state.handData.length>=2) {
    const y=(state.handData[0].wrist.y+state.handData[1].wrist.y)/2;
    if(state.lastHandY!=null&&Math.abs(y-state.lastHandY)>28){state.hitCount+=1;state.lastHandY=y;}
    else if(state.lastHandY==null)state.lastHandY=y;
    if(state.hitCount>=8)succeed("You flew like a bird!");
  } else if (state.game==="head-bop" && state.faceData) {
    const y=state.faceData.cy*stage.clientHeight;
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
    const tips=state.handData.map(h=>h.tip);if(tips.every(p=>p.y<stage.clientHeight*.35)&&Math.abs(tips[0].x-tips[1].x)>stage.clientWidth*.45)succeed("Rainbow reach!");
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
    const y=face.cy*stage.clientHeight;
    if (state.lastFaceY!=null) motion=Math.max(motion, Math.abs(y-state.lastFaceY));
    state.lastFaceY=y;
  }
  return motion>7;
}
function targetPoint(){const r=target.getBoundingClientRect(),s=stage.getBoundingClientRect();return{x:r.left-s.left+r.width/2,y:r.top-s.top+r.height/2};}

function loop(now) {
  if(!state.running)return;
  detectFrame();drawVision();updateTrace();updateObjectGame();updateGestureGame(now);
  requestAnimationFrame(loop);
}

function chooseGame() {
  clearTimeout(state.roundTimer);clearTimeout(state.failTimer);cancelSpeech();
  state.roundId += 1; const round = state.roundId; state.roundDone=false;
  clearRound();
  state.game=$("game").value;state.startedAt=performance.now();state.attempts=1;state.hitCount=0;state.phase=0;state.padHeld=false;state.pausedAt=0;
  const letter=$("letter").value,word=LETTER_WORDS[letter];
  if(state.game==="trace-letter")setPrompt(`Trace ${letter}`,"Point one finger up and follow the glowing letter.",`Trace the letter ${letter}.`);
  else if(state.game==="trace-picture")setPrompt(`Trace the ${word}`,"Use one finger to draw around the picture.",`Now trace the ${word}.`);
  else if(state.game==="say-letter")setPrompt(`Say ${letter}`,"Tap the microphone or type what you said.",`Listen, then say the letter ${letter}.`);
  else if(state.game==="oh-behave"){
    state.targetRegion=randomRegion();state.targetExpression=randomOf(EXPRESSIONS);state.deadline=performance.now()+state.timerMs;
    $("countdown").classList.remove("hidden");setTarget(state.targetRegion,expressionEmoji(state.targetExpression));
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
  speak(state.spokenPrompt);
}

function randomRegion(){const keys=Object.keys(REGIONS).filter(k=>!state.seated||!k.startsWith("bottom"));return randomOf(keys)||"center";}
function expressionEmoji(kind){return({happy:"😄",surprised:"😮","wink-left":"😉","wink-right":"😉","mouth-o":"😗",sleepy:"😴"})[kind]||"🙂";}

function clearRound() {
  hideTarget();
  for (const node of [...spriteLayer.querySelectorAll(".sprite,.miss-gag,.miss-caption")]) node.remove();
  $("countdown").classList.add("hidden");
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
  const result=calculateFun(false);state.fun=result.score;renderScore();missGag();setPrompt("Almost!",message);
  recordEvent("retry",result);speak(`Almost! ${message}`);
  if(state.game==="oh-behave")state.timerMs=nextTimer(false);
  clearTimeout(state.roundTimer);
  state.roundTimer=setTimeout(()=>{if(state.roundId!==round)return;state.roundDone=false;chooseGame();},1500);
}
function nextTimer(hit){const full=[8000,6000,4000,2000,1500],ladder=state.age==="4-6"?full.slice(0,3):full;let i=Math.max(0,ladder.indexOf(state.timerMs));i=hit?Math.min(ladder.length-1,i+1):Math.max(0,i-1);return ladder[i];}
function renderScore(){$("fun-score").textContent=`Fun ${state.fun}`;$("combo").textContent=`Combo ${state.combo}`;$("stars").textContent=state.fun>=85?"★★★":state.fun>=60?"★★☆":state.fun>0?"★☆☆":"☆☆☆";}

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
  if (state.audio) {
    try { state.audio.pause(); state.audio.src = ""; } catch (_) {}
    state.audio = null;
  }
  if ("speechSynthesis" in window) speechSynthesis.cancel();
}

async function speak(text) {
  if(state.muted||!text)return;
  cancelSpeech();
  try {
    const response=await fetch(`/api/tts?text=${encodeURIComponent(text)}&language=en&style=cheerful`);
    if(!response.ok)throw new Error(String(response.status));
    const url=URL.createObjectURL(await response.blob()),audio=new Audio(url);
    state.audio=audio;
    audio.onended=()=>{URL.revokeObjectURL(url);if(state.audio===audio)state.audio=null;};
    await audio.play();
  } catch (_) {
    if("speechSynthesis" in window){const utterance=new SpeechSynthesisUtterance(text);utterance.rate=.94;utterance.pitch=1.08;speechSynthesis.speak(utterance);}
  }
}

function startListening() {
  if (state.game!=="say-letter") {
    setPrompt("Say the letter first","Switch to Say the letter, then use the microphone.");
    return;
  }
  const Ctor=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!Ctor){setPrompt("Type instead","Speech recognition is unavailable here.");$("typed").focus();return;}
  if(state.recognition)try{state.recognition.stop();}catch(_){}
  const rec=new Ctor();state.recognition=rec;rec.lang="en-US";rec.interimResults=false;rec.maxAlternatives=1;
  $("mic").textContent="Listening…";rec.onresult=e=>{const heard=e.results[0][0].transcript;$("typed").value=heard;checkSpeech(heard);};
  rec.onerror=e=>setPrompt("Mic paused",`Try typing instead (${e.error}).`);
  rec.onend=()=>{$("mic").textContent="🎤 Say it";};rec.start();
}
async function checkSpeech(heard) {
  if (state.game!=="say-letter") {
    setPrompt("Say the letter first","Switch to Say the letter, then check what was said.");
    return;
  }
  const letter=$("letter").value;
  try{
    const response=await fetch("/api/child/pronounce",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({target:letter,heard,kind:"letter"})});
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
  $("dashboard").innerHTML=`<div class="dashboard-grid">${Object.entries(by).map(([id,row])=>`<div class="metric"><strong>${esc(id.replaceAll("-"," "))}</strong>Fun ${Math.round(row.scores.reduce((a,b)=>a+b,0)/row.scores.length)} · ${row.wins}/${row.plays} wins</div>`).join("")||"<p>No games recorded yet.</p>"}</div>`;
}

canvas.addEventListener("pointermove",event=>{
  if(!state.demo)return;const rect=canvas.getBoundingClientRect(),tip={x:event.clientX-rect.left,y:event.clientY-rect.top};
  state.handData=[{points:[],label:"Pointer",count:1,indexUp:true,fist:false,tip,wrist:tip}];
});
canvas.addEventListener("pointerleave",()=>{if(state.demo)state.handData=[];});
$("start").addEventListener("click",()=>start(true));$("demo").addEventListener("click",()=>start(false));
$("play-game").addEventListener("click",()=>chooseGame());
$("game").addEventListener("change",()=>chooseGame());
$("letter").addEventListener("change",()=>chooseGame());
$("hear").addEventListener("click",()=>speak(state.spokenPrompt));
$("mic").addEventListener("click",startListening);
$("check").addEventListener("click",()=>checkSpeech($("typed").value));
$("undo").addEventListener("click",()=>{state.trail=[];});
$("mute").addEventListener("click",()=>{state.muted=!state.muted;$("mute").textContent=state.muted?"🔇":"🔊";$("mute").setAttribute("aria-pressed",String(state.muted));if(state.muted)cancelSpeech();});
$("fullscreen").addEventListener("click",()=>document.fullscreenElement?document.exitFullscreen():$("play").requestFullscreen());
$("home").addEventListener("click",()=>{if(state.stream)state.stream.getTracks().forEach((t)=>t.stop());location.reload();});
$("clear-data").addEventListener("click",()=>{localStorage.removeItem(state.localKey);state.activityEvents=[];state.fun=0;state.combo=0;renderScore();renderDashboard();});
