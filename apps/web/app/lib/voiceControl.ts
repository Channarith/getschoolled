/**
 * Voice control for every voice engine: Salane, Sage, company voices and the edge-tts voices.
 *
 * The xAI voice agent could answer questions and slow down or re-explain when the learner asked. The Salane engines only spoke.
 * This module is the engine-agnostic half of the fix: it turns what the learner SAID into one intent, with no dependence on how
 * the lesson is spoken. Pages then act on the intent (pause, pace, skip, ask the lesson a question) and speak the reply in the
 * voice the learner picked. The same table is mirrored in the studio player (voice_static/course_voice.js); a parity test keeps
 * the two from drifting.
 *
 * Only SHORT command-shaped utterances are commands. Anything that reads as a question goes to Q&A, so "why does the brake pause
 * the car?" is a question, while "pause" pauses.
 *
 * Non-English phrase lists (fr, de, it, pt, zh, yue, ja, ko, vi, th, km) are MACHINE-DRAFTED: a native speaker should review them.
 */
import {
  clampPlaybackRate, isQuestion, parsePlaybackCommand, MIN_PLAYBACK_RATE, MAX_PLAYBACK_RATE,
  type PlaybackCommand,
} from "./voiceCommands";

export { MIN_PLAYBACK_RATE, MAX_PLAYBACK_RATE };

export type FlexKind = "simpler" | "deeper" | "example" | "summarize" | "quiz_me" | "lost";
export type VolumeKind = "louder" | "quieter" | "mute" | "unmute";

export type VoiceControlIntent =
  | { type: "playback"; command: PlaybackCommand }
  | { type: "volume"; kind: VolumeKind }
  | { type: "captions"; on: boolean | null }
  | { type: "fullscreen"; on: boolean }
  | { type: "stop_listening" }
  /** Re-explain / elaborate / quiz: answered by the lesson Q&A with a ready-made prompt. */
  | { type: "flex"; kind: FlexKind }
  /** "skip this section", "next section". */
  | { type: "skip_section" }
  /** "I know this": move ahead by `count` parts. */
  | { type: "know_this"; count: number }
  | { type: "go_back_to"; topic: string }
  | { type: "question"; text: string }
  | { type: "none" };

// ---- pace --------------------------------------------------------------------------------------------------------------

export const PACE_KEY = "aoep_voice_pace";
export const PACE_STEP = 0.15;

export function loadPace(): number {
  try {
    const raw = Number(localStorage.getItem(PACE_KEY) || "");
    return Number.isFinite(raw) && raw > 0 ? clampPlaybackRate(raw) : 1;
  } catch {
    return 1;
  }
}

export function savePace(rate: number): number {
  const next = clampPlaybackRate(rate);
  try { localStorage.setItem(PACE_KEY, String(next)); } catch { /* private mode */ }
  return next;
}

/** The new pace after a spoken playback command (faster, slower, "speed 1.5", "normal speed"); the current pace otherwise. */
export function paceAfter(current: number, command: PlaybackCommand): number {
  if (command.kind === "faster") return clampPlaybackRate(current + PACE_STEP);
  if (command.kind === "slower") return clampPlaybackRate(current - PACE_STEP);
  if (command.kind === "speed") return clampPlaybackRate(command.rate);
  return clampPlaybackRate(current);
}

// ---- normalising -------------------------------------------------------------------------------------------------------

/** Lower-case, no punctuation, single spaces; keeps letters of every script. */
export function normalizeSpoken(text: string): string {
  return (text || "").toLowerCase().normalize("NFC").replace(/[^\p{L}\p{N}\s']/gu, " ").replace(/\s+/g, " ").trim();
}

function stripMarks(text: string): string {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "");
}

const LEADING_POLITE = /^(please |hey sala |ok |okay |can you |could you |would you |kindly )+/;
const TRAILING_POLITE = / (please|now|for me|thanks|thank you)$/;

function stripPolite(text: string): string {
  return text.replace(LEADING_POLITE, "").replace(TRAILING_POLITE, "").trim();
}

// ---- English flexibility intents ----------------------------------------------------------------------------------------

type EnRule = { re: RegExp; intent: VoiceControlIntent };

const EN_RULES: EnRule[] = [
  { re: /^(simpler|more simply|simplify( it| that| this)?|make it simpler|dumb it down|eli5|explain (it |that |this )?(again )?(more )?(simply|simpler|in simpler (words|terms)|in plain (english|words|terms)|like i'?m (5|five))|say (it|that) (more )?simply)$/,
    intent: { type: "flex", kind: "simpler" } },
  { re: /^(go deeper|dig deeper|more (detail|details|depth)|tell me more|go into more detail|explain (it |that |this )?(more|further|in more detail|in depth)|elaborate|expand on (it|that|this))$/,
    intent: { type: "flex", kind: "deeper" } },
  { re: /^((give me |show me |i need |i want )?(an|one|another) examples?|for example|example|any examples?)$/,
    intent: { type: "flex", kind: "example" } },
  { re: /^(summar(y|ize|ise)( (this|that|it|the lesson|so far))?|sum (it|this|that) up|(give me )?(a |the )?(quick )?(summary|recap)|recap|tl;?dr)$/,
    intent: { type: "flex", kind: "summarize" } },
  { re: /^(quiz me|test me|ask me (a |one )?(question|quiz question)|give me a quiz|check my understanding|let'?s (do (a )?)?quiz|pop quiz)$/,
    intent: { type: "flex", kind: "quiz_me" } },
  { re: /^((i'?m|i am) (lost|confused)|i (don'?t|do not) (understand|get it|follow)( this| that| it)?|(this is |that is |that'?s )?confusing|i'?m not following|wait what|huh|i didn'?t (get|understand) (it|that|this))$/,
    intent: { type: "flex", kind: "lost" } },
  { re: /^((skip|jump over|move past|go past) (this|the|that) (section|chapter|part|topic)|next (section|chapter|topic)|skip (the )?(section|chapter))$/,
    intent: { type: "skip_section" } },
  { re: /^((i )?(already )?know (this|that|it)( already| well)?|i know( this| that| it)? (already|well)|(this is |that is |that'?s )?(too )?easy|skip,? i know (this|that|it)|i got (it|this|that))$/,
    intent: { type: "know_this", count: 2 } },
  { re: /^((you'?re|you are|that'?s|that is|it'?s|it is) )?((going|talking|speaking|moving) )?too (fast|quick|quickly)$|^slow it down$|^not so fast$|^hold your horses$/,
    intent: { type: "playback", command: { kind: "slower" } } },
  { re: /^((you'?re|you are|that'?s|that is|it'?s|it is) )?((going|talking|speaking|moving) )?too slow(ly)?$|^hurry up$|^get on with it$|^speed it up$/,
    intent: { type: "playback", command: { kind: "faster" } } },
  { re: /^(louder|turn it up|volume up|(turn )?(the )?volume up|increase (the )?volume|speak up|raise (the )?volume)$/,
    intent: { type: "volume", kind: "louder" } },
  { re: /^(quieter|softer|turn it down|volume down|(turn )?(the )?volume down|lower (the )?volume|decrease (the )?volume|not so loud)$/,
    intent: { type: "volume", kind: "quieter" } },
  { re: /^(mute( (the )?(audio|sound|volume|narration))?|turn (the )?(sound|audio) off|silence( the)? (audio|sound))$/,
    intent: { type: "volume", kind: "mute" } },
  { re: /^(unmute( (the )?(audio|sound|volume|narration))?|turn (the )?(sound|audio) on|sound on)$/,
    intent: { type: "volume", kind: "unmute" } },
  { re: /^((turn )?(on|enable|show) (the )?(closed )?(captions?|subtitles?|cc)|(closed )?(captions?|subtitles?|cc) on)$/,
    intent: { type: "captions", on: true } },
  { re: /^((turn )?(off|disable|hide) (the )?(closed )?(captions?|subtitles?|cc)|(closed )?(captions?|subtitles?|cc) off)$/,
    intent: { type: "captions", on: false } },
  { re: /^(go )?full ?screen|^make it (bigger|full)$|^bigger screen$/,
    intent: { type: "fullscreen", on: true } },
  { re: /^(exit|leave|close|quit) full ?screen$|^normal size$|^minimi[sz]e$/,
    intent: { type: "fullscreen", on: false } },
  { re: /^(stop listening|mute (the )?(mic|microphone)|turn (the )?(mic|microphone) off|stop hearing me)$/,
    intent: { type: "stop_listening" } },
];

const GO_BACK_RE = /^(go back to|take me back to|return to|jump back to|back to|go to) (the )?(.{2,60})$/;

// ---- Localised core commands (machine-drafted; English always works) --------------------------------------------------

export type CoreCommand = "pause" | "resume" | "next" | "previous" | "repeat" | "faster" | "slower" | "louder" | "quieter" | "mute";

type Phrases = Record<CoreCommand, string[]>;

export const LOCALIZED: Record<string, Phrases> = {
  es: {
    pause: ["pausa", "pausar", "para", "detente", "alto", "espera"], resume: ["continua", "continuar", "sigue", "reanuda", "reanudar"],
    next: ["siguiente", "proximo", "salta", "avanza"], previous: ["atras", "anterior", "vuelve", "retrocede"], repeat: ["repite", "repetir", "otra vez", "de nuevo"],
    faster: ["mas rapido", "mas rapida", "acelera"], slower: ["mas lento", "mas lenta", "mas despacio", "despacio"],
    louder: ["mas fuerte", "sube el volumen", "mas alto"], quieter: ["mas bajo", "baja el volumen", "menos fuerte"], mute: ["silenciar", "mudo", "sin sonido"],
  },
  fr: {
    pause: ["pause", "arrete", "stop", "attends"], resume: ["reprends", "reprendre", "continue", "continuer", "lecture"],
    next: ["suivant", "suite", "passe", "saute", "passer"], previous: ["precedent", "retour", "reviens", "en arriere"], repeat: ["repete", "repeter", "encore", "une autre fois"],
    faster: ["plus vite", "accelere", "plus rapide"], slower: ["plus lentement", "plus lent", "ralentis", "moins vite", "doucement"],
    louder: ["plus fort", "monte le son", "augmente le volume"], quieter: ["moins fort", "baisse le son", "plus bas"], mute: ["muet", "coupe le son"],
  },
  de: {
    pause: ["pause", "stopp", "halt", "warte", "anhalten"], resume: ["weiter", "fortsetzen", "weitermachen"],
    next: ["nachste", "nachster", "uberspringen", "weiter zum nachsten"], previous: ["zuruck", "vorherige", "vorheriger"], repeat: ["wiederholen", "wiederhole", "nochmal", "noch einmal"],
    faster: ["schneller"], slower: ["langsamer"], louder: ["lauter"], quieter: ["leiser"], mute: ["stumm", "ton aus"],
  },
  it: {
    pause: ["pausa", "fermati", "ferma", "aspetta"], resume: ["riprendi", "continua", "riprendere"],
    next: ["avanti", "prossimo", "salta", "successivo"], previous: ["indietro", "precedente", "torna indietro"], repeat: ["ripeti", "di nuovo", "ancora una volta"],
    faster: ["piu veloce", "accelera"], slower: ["piu lento", "rallenta", "piu piano"], louder: ["piu forte", "alza il volume"], quieter: ["meno forte", "abbassa il volume"], mute: ["muto"],
  },
  pt: {
    pause: ["pausa", "pausar", "para", "pare", "espera"], resume: ["continuar", "continua", "retomar", "seguir"],
    next: ["proximo", "pular", "avancar"], previous: ["anterior", "voltar", "volta"], repeat: ["repetir", "repete", "de novo", "outra vez"],
    faster: ["mais rapido", "acelera"], slower: ["mais devagar", "mais lento", "devagar"], louder: ["mais alto", "aumenta o volume"], quieter: ["mais baixo", "diminui o volume"], mute: ["mudo", "silenciar"],
  },
  zh: {
    pause: ["暂停", "停", "停止", "等一下"], resume: ["继续", "播放", "接着"], next: ["下一个", "下一节", "下一页", "跳过"], previous: ["上一个", "上一节", "上一页", "返回", "后退"],
    repeat: ["重复", "再说一遍", "再来一次", "重播"], faster: ["快一点", "快点", "加快", "更快"], slower: ["慢一点", "慢点", "减慢", "更慢"],
    louder: ["大声一点", "大点声", "音量大一点", "声音大一点"], quieter: ["小声一点", "小点声", "音量小一点"], mute: ["静音"],
  },
  yue: {
    pause: ["暫停", "停", "等一等"], resume: ["繼續", "播放"], next: ["下一個", "下一節", "跳過"], previous: ["上一個", "返回", "返去"],
    repeat: ["再講一次", "重複", "再嚟一次"], faster: ["快啲", "快少少", "加快"], slower: ["慢啲", "慢少少", "減慢"],
    louder: ["大聲啲", "大聲少少"], quieter: ["細聲啲", "細聲少少"], mute: ["靜音"],
  },
  ja: {
    pause: ["一時停止", "止めて", "ストップ", "待って"], resume: ["再開", "続けて", "再生"], next: ["次", "次へ", "スキップ"], previous: ["前", "前へ", "戻って", "戻る"],
    repeat: ["もう一度", "繰り返して", "リピート"], faster: ["速く", "もっと速く", "早く"], slower: ["ゆっくり", "もっとゆっくり", "遅く"],
    louder: ["大きく", "音量を上げて", "もっと大きく"], quieter: ["小さく", "音量を下げて"], mute: ["ミュート", "消音"],
  },
  ko: {
    pause: ["일시정지", "멈춰", "정지", "잠깐"], resume: ["계속", "재생", "다시 시작"], next: ["다음", "건너뛰기", "넘겨"], previous: ["이전", "뒤로", "돌아가"],
    repeat: ["다시", "반복", "한 번 더"], faster: ["더 빠르게", "빠르게"], slower: ["더 느리게", "느리게", "천천히"],
    louder: ["더 크게", "크게", "볼륨 올려"], quieter: ["더 작게", "작게", "볼륨 낮춰"], mute: ["음소거"],
  },
  vi: {
    pause: ["tam dung", "dung lai", "dung", "cho chut"], resume: ["tiep tuc", "phat tiep"], next: ["tiep theo", "bo qua", "ke tiep"], previous: ["truoc do", "quay lai", "lui lai"],
    repeat: ["lap lai", "noi lai", "nhac lai"], faster: ["nhanh hon", "nhanh len"], slower: ["cham hon", "cham lai"],
    louder: ["to hon", "tang am luong"], quieter: ["nho hon", "giam am luong"], mute: ["tat tieng", "im lang"],
  },
  th: {
    pause: ["หยุดชั่วคราว", "หยุด", "รอแป๊บ"], resume: ["เล่นต่อ", "ต่อ", "เริ่มต่อ"], next: ["ถัดไป", "ข้าม", "ต่อไป"], previous: ["ก่อนหน้า", "ย้อนกลับ", "กลับ"],
    repeat: ["พูดอีกครั้ง", "ซ้ำ", "อีกครั้ง"], faster: ["เร็วขึ้น", "เร็วกว่านี้"], slower: ["ช้าลง", "ช้ากว่านี้"],
    louder: ["ดังขึ้น", "เสียงดังขึ้น"], quieter: ["เบาลง", "เสียงเบาลง"], mute: ["ปิดเสียง"],
  },
  km: {
    pause: ["ផ្អាក", "ឈប់"], resume: ["បន្ត"], next: ["បន្ទាប់", "រំលង"], previous: ["មុន", "ត្រឡប់ក្រោយ"], repeat: ["និយាយម្តងទៀត", "ម្តងទៀត"],
    faster: ["លឿនជាងនេះ", "លឿនឡើង"], slower: ["យឺតជាងនេះ", "យឺតឡើង", "យឺតៗ"], louder: ["ខ្លាំងជាងនេះ", "ខ្លាំងឡើង"], quieter: ["តូចជាងនេះ", "តិចជាងនេះ"], mute: ["បិទសំឡេង"],
  },
};

/** Scripts written without spaces: a phrase may sit inside a slightly longer utterance. */
const UNSPACED = new Set(["zh", "yue", "ja", "ko", "th", "km"]);

const CORE_ORDER: CoreCommand[] = ["mute", "pause", "resume", "previous", "next", "repeat", "faster", "slower", "louder", "quieter"];

function coreToIntent(cmd: CoreCommand): VoiceControlIntent {
  switch (cmd) {
    case "louder": case "quieter": case "mute": return { type: "volume", kind: cmd };
    default: return { type: "playback", command: { kind: cmd } as PlaybackCommand };
  }
}

function languageBase(locale?: string): string {
  const l = (locale || "en").toLowerCase();
  if (l === "yue" || l.startsWith("zh-hk") || l.startsWith("zh-mo")) return "yue";
  return l.split(/[-_]/)[0];
}

/** Match a short utterance against one language's core command phrases. */
export function matchLocalizedCommand(text: string, locale?: string): VoiceControlIntent | null {
  const base = languageBase(locale);
  const table = LOCALIZED[base];
  if (!table) return null;
  const norm = normalizeSpoken(text);
  if (!norm) return null;
  const plain = stripMarks(norm);
  const spaced = !UNSPACED.has(base);
  for (const cmd of CORE_ORDER) {
    for (const phrase of table[cmd]) {
      const p = spaced ? stripMarks(normalizeSpoken(phrase)) : normalizeSpoken(phrase);
      if (!p) continue;
      if (spaced) {
        if (plain === p) return coreToIntent(cmd);
        const words = plain.split(" ").length - p.split(" ").length;
        if (words >= 0 && words <= 2 && (plain.startsWith(`${p} `) || plain.endsWith(` ${p}`))) return coreToIntent(cmd);
      } else if (norm.includes(p) && norm.length <= p.length + 6) {
        return coreToIntent(cmd);
      }
    }
  }
  return null;
}

// ---- The router --------------------------------------------------------------------------------------------------------

const MAX_COMMAND_WORDS = 9;

export type RouteOptions = { locale?: string };

/** Turn a final transcript into one intent. Commands are short; questions go to the lesson Q&A; noise is "none". */
export function routeUtterance(text: string, opts: RouteOptions = {}): VoiceControlIntent {
  const raw = (text || "").trim();
  if (!raw) return { type: "none" };
  const spacedLocale = !UNSPACED.has(languageBase(opts.locale));

  // 1. The existing playback parser (pause, resume, next, previous, repeat, restart, faster, slower, "speed 1.5"), English + Spanish.
  const playback = parsePlaybackCommand(raw);
  if (playback) return { type: "playback", command: playback };

  // 2. Short English flexibility / volume / captions / fullscreen intents.
  const words = normalizeSpoken(raw).split(" ").length;
  if (words <= MAX_COMMAND_WORDS) {
    const body = stripPolite(normalizeSpoken(raw));
    for (const rule of EN_RULES) if (rule.re.test(body)) return rule.intent;
    const back = body.match(GO_BACK_RE);
    if (back && back[3] && !/^(the )?(beginning|start|top)$/.test(back[3])) return { type: "go_back_to", topic: back[3].trim() };
  }

  // 3. Localised core commands in the page's language (and in the learner's browser language when different).
  const local = matchLocalizedCommand(raw, opts.locale);
  if (local) return local;

  // 4. Questions (and longer requests) go to the lesson. A single word or two is noise, not a question.
  if (isQuestion(raw)) return { type: "question", text: raw };
  if (!spacedLocale && raw.length >= 6 && /[?？吗嗎呢什么麼嘅咩點点]/.test(raw)) return { type: "question", text: raw };
  return { type: "none" };
}

// ---- Ready-made prompts for the lesson Q&A -------------------------------------------------------------------------------

const FLEX_PROMPTS: Record<FlexKind, string> = {
  simpler: "Explain this again in simpler words, in two or three short sentences, with one everyday example.",
  deeper: "Go deeper on this part: add the key detail a learner usually misses, in three or four short sentences.",
  example: "Give one clear, concrete example of this part, in two or three short sentences.",
  summarize: "Summarize this lesson so far in three short sentences.",
  quiz_me: "Ask me one short quiz question about this part, then wait for my answer. If I answer next, tell me in one sentence whether I am right.",
  lost: "I am lost. Slow down and explain this part again very simply in two or three short sentences, then ask if it makes sense.",
};

/** The question the Q&A receives for a flexibility intent: the instruction, then the part of the lesson it is about. */
export function flexPrompt(kind: FlexKind, lessonText: string): string {
  const part = (lessonText || "").trim().slice(0, 1200);
  return part ? `${FLEX_PROMPTS[kind]}\n\nThis part of the lesson:\n${part}` : FLEX_PROMPTS[kind];
}

/** A flexibility intent the page should answer with a slower pace as well. */
export function flexSlowsDown(kind: FlexKind): boolean {
  return kind === "lost";
}

/** Find a part of the course whose title contains the spoken topic ("go back to the brakes"). Returns the index or -1. */
export function findTopicIndex(topic: string, titles: string[], before = titles.length): number {
  const want = stripMarks(normalizeSpoken(topic)).replace(/^(the|a|an) /, "");
  if (!want) return -1;
  const words = want.split(" ").filter((w) => w.length > 2);
  let best = -1;
  let bestScore = 0;
  for (let i = Math.min(before, titles.length) - 1; i >= 0; i--) {
    const title = stripMarks(normalizeSpoken(titles[i] || ""));
    if (!title) continue;
    const score = title.includes(want) ? 10 + want.length : words.filter((w) => title.includes(w)).length;
    if (score > bestScore) { bestScore = score; best = i; }
  }
  return bestScore > 0 ? best : -1;
}
