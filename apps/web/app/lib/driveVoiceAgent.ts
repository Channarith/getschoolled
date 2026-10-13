/**
 * Hands-free xAI voice tutor for Drive Mode.
 *
 * The speech service writes the prompt and allows only web search. This client
 * streams the microphone and plays the tutor. It does not send instructions.
 */

import { cancelSpeech, speakNaturally } from "./tts";
import { getXaiVoiceStatus, isSalaneEngine, mintXaiVoiceToken, connectXaiVoiceSession, appendInputAudio, closeXaiVoiceSession, sendTextTurn } from "./xaiVoice";

const BLUETOOTH_INPUT = /bluetooth|airpod|headset|hands-free|handset|beats|bose/i;

export type DriveVoiceTopic = {
  category: string;
  title: string;
  excerpt: string;
  courseId?: string;
  language?: string;
};

export type DriveVoiceCallbacks = {
  onStatus?: (text: string) => void;
  onUser?: (text: string) => void;
  onTutor?: (text: string) => void;
  onSpeaking?: (speaking: boolean) => void;
  /** The learner interrupted, and the agent's answer has finished. */
  onAnswerDone?: () => void;
};

export type DriveVoiceSession = {
  stop: () => void;
  /** While the lesson is audible, quiet audio is not sent, so the tutor does not answer the narration. */
  setLessonAudible: (audible: boolean) => void;
  /** Read one lesson segment. onDone runs only if the learner did not interrupt. */
  speakLesson: (text: string, onDone?: () => void) => boolean;
  /** Ask the voice agent. The lesson does not advance when the answer ends. */
  ask: (text: string) => void;
  /** Stop the current spoken turn without advancing the lesson. */
  hold: () => void;
};

function pcm16Base64(samples: Float32Array): string {
  const pcm = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i++) {
    const value = Math.max(-1, Math.min(1, samples[i]));
    pcm[i] = value < 0 ? value * 32768 : value * 32767;
  }
  const bytes = new Uint8Array(pcm.buffer);
  let out = "";
  const step = 0x8000;
  for (let i = 0; i < bytes.length; i += step) {
    out += String.fromCharCode(...bytes.subarray(i, i + step));
  }
  return btoa(out);
}

function resample(input: Float32Array, sourceRate: number, targetRate: number): Float32Array {
  if (sourceRate === targetRate) return input;
  const ratio = sourceRate / targetRate;
  const out = new Float32Array(Math.max(1, Math.floor(input.length / ratio)));
  for (let i = 0; i < out.length; i++) {
    const start = Math.floor(i * ratio);
    const end = Math.min(input.length, Math.floor((i + 1) * ratio));
    let sum = 0;
    for (let j = start; j < end; j++) sum += input[j];
    out[i] = sum / Math.max(1, end - start);
  }
  return out;
}

async function openComputerMic(): Promise<MediaStream> {
  const audio = {
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: false,
    channelCount: 1,
  };
  let stream = await navigator.mediaDevices.getUserMedia({ audio, video: false });
  const devices = await navigator.mediaDevices.enumerateDevices().catch(() => [] as MediaDeviceInfo[]);
  const inputs = devices.filter((device) => device.kind === "audioinput");
  const track = stream.getAudioTracks()[0];
  const activeId = track?.getSettings?.().deviceId || "";
  const label = inputs.find((device) => device.deviceId === activeId)?.label || track?.label || "";
  if (!BLUETOOTH_INPUT.test(label)) return stream;
  const builtin = inputs.find((device) => {
    if (!device.deviceId || device.deviceId === "default" || device.deviceId === "communications") return false;
    return !BLUETOOTH_INPUT.test(device.label || "");
  });
  if (!builtin) return stream;
  stream.getTracks().forEach((item) => item.stop());
  try {
    return await navigator.mediaDevices.getUserMedia({
      audio: { ...audio, deviceId: { exact: builtin.deviceId } },
      video: false,
    });
  } catch {
    return navigator.mediaDevices.getUserMedia({ audio, video: false });
  }
}

export async function startDriveVoice(
  topic: DriveVoiceTopic,
  callbacks: DriveVoiceCallbacks = {},
): Promise<DriveVoiceSession | null> {
  const status = await getXaiVoiceStatus().catch(() => null);
  if (!status?.available) return null;
  if (isSalaneEngine(status.engine)) {
    const locale = topic.language || "en";
    let stopped = false;
    callbacks.onStatus?.("Sala is speaking with Salane Voice.");
    return {
      setLessonAudible() {},
      speakLesson(text: string, onDone?: () => void) {
        const line = text.trim();
        if (stopped || !line) return false;
        callbacks.onSpeaking?.(true);
        speakNaturally(line, {
          locale,
          onend: () => {
            callbacks.onSpeaking?.(false);
            onDone?.();
          },
        });
        return true;
      },
      ask(text: string) {
        const line = (text || topic.excerpt || topic.title || "").trim();
        if (stopped || !line) return;
        callbacks.onTutor?.(topic.excerpt || topic.title);
        callbacks.onSpeaking?.(true);
        speakNaturally(topic.excerpt || topic.title || line, {
          locale,
          onend: () => {
            callbacks.onSpeaking?.(false);
            callbacks.onAnswerDone?.();
          },
        });
      },
      hold() {
        cancelSpeech();
        callbacks.onSpeaking?.(false);
      },
      stop() {
        stopped = true;
        cancelSpeech();
        callbacks.onSpeaking?.(false);
      },
    };
  }
  const token = await mintXaiVoiceToken({
    mode: "drive",
    category: topic.category,
    topic: topic.title,
    lesson_context: topic.excerpt,
    course_id: topic.courseId || "",
    language: topic.language || "",
    expires_seconds: 600,
  });
  if (token.use_xai === false || !token.token || !token.session_update) return null;
  const ctx = new AudioContext({ latencyHint: "playback" });
  await ctx.resume();
  const output = ctx.createGain();
  output.gain.value = 1;
  output.connect(ctx.destination);
  const stream = await openComputerMic();
  const source = ctx.createMediaStreamSource(stream);
  const sink = ctx.createMediaStreamDestination();
  let processor: AudioWorkletNode | ScriptProcessorNode;
  const workletUrl = URL.createObjectURL(new Blob([`
    class DriveMic extends AudioWorkletProcessor {
      process(inputs) {
        const channel = inputs[0] && inputs[0][0];
        if (channel && channel.length) this.port.postMessage(channel.slice());
        return true;
      }
    }
    registerProcessor("drive-mic", DriveMic);
  `], { type: "application/javascript" }));
  try {
    await ctx.audioWorklet.addModule(workletUrl);
    processor = new AudioWorkletNode(ctx, "drive-mic");
  } catch {
    processor = ctx.createScriptProcessor(2048, 1, 1);
  } finally {
    URL.revokeObjectURL(workletUrl);
  }
  source.connect(processor);
  processor.connect(sink);

  let ws: WebSocket | null = null;
  let nextAt = 0;
  let micRms = 0;
  let speaking = false;
  let lessonAudible = false;
  let endTimer = 0;
  let lessonDone: (() => void) | null = null;
  let awaitingAnswer = false;
  const playing = new Set<AudioBufferSourceNode>();

  const noteSpeaking = (on: boolean) => {
    if (speaking === on) return;
    speaking = on;
    callbacks.onSpeaking?.(on);
  };

  const clearPlayback = () => {
    window.clearTimeout(endTimer);
    for (const node of playing) {
      try { node.stop(); } catch { /* already stopped */ }
    }
    playing.clear();
    nextAt = ctx.currentTime;
    noteSpeaking(false);
  };

  const finishTurn = () => {
    if (playing.size) return;
    noteSpeaking(false);
    if (awaitingAnswer) {
      awaitingAnswer = false;
      lessonDone = null;
      callbacks.onAnswerDone?.();
      return;
    }
    const done = lessonDone;
    lessonDone = null;
    done?.();
  };

  const cancelResponse = () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    try { ws.send(JSON.stringify({ type: "response.cancel" })); } catch { /* already closed */ }
  };

  const playPcm = (base64: string) => {
    const raw = atob(base64);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    const pcm = new Int16Array(bytes.buffer, bytes.byteOffset, Math.floor(bytes.byteLength / 2));
    if (!pcm.length) return;
    const floats = new Float32Array(pcm.length);
    for (let i = 0; i < pcm.length; i++) floats[i] = pcm[i] / 32768;
    const buffer = ctx.createBuffer(1, floats.length, 24000);
    buffer.copyToChannel(floats, 0);
    const node = ctx.createBufferSource();
    node.buffer = buffer;
    node.connect(output);
    const at = Math.max(ctx.currentTime + 0.03, nextAt);
    node.start(at);
    nextAt = at + buffer.duration;
    playing.add(node);
    node.onended = () => playing.delete(node);
    noteSpeaking(true);
    window.clearTimeout(endTimer);
    endTimer = window.setTimeout(finishTurn, 700);
  };

  const sendMic = (samples: Float32Array) => {
    let sum = 0;
    let n = 0;
    for (let i = 0; i < samples.length; i += 8) {
      sum += samples[i] * samples[i];
      n += 1;
    }
    micRms = micRms * 0.65 + Math.sqrt(sum / Math.max(1, n)) * 0.35;
    if (!ws) return;
    if (lessonAudible && micRms < 0.035) return;
    appendInputAudio(ws, pcm16Base64(resample(samples, ctx.sampleRate, 24000)));
  };

  if (processor instanceof AudioWorkletNode) {
    processor.port.onmessage = (event) => sendMic(new Float32Array(event.data));
  } else {
    processor.onaudioprocess = (event) => {
      sendMic(new Float32Array(event.inputBuffer.getChannelData(0)));
    };
  }

  let tutorText = "";
  ws = connectXaiVoiceSession(token, {
    onOpen: () => callbacks.onStatus?.("Hands-free tutor is listening. Ask about this subject."),
    onAudioDelta: (delta) => playPcm(delta),
    onTranscriptDelta: (text) => {
      tutorText += text;
      callbacks.onTutor?.(tutorText);
    },
    onTranscriptDone: (text) => {
      tutorText = "";
      if (text) callbacks.onTutor?.(text);
    },
    onEvent: (event) => {
      const type = String(event.type || "");
      if (type === "input_audio_buffer.speech_started" && playing.size && micRms >= 0.035) {
        awaitingAnswer = true;
        lessonDone = null;
        clearPlayback();
      }
      if (type.endsWith("transcription.completed") || type.endsWith("input_audio_transcription.completed")) {
        const said = String(event.transcript || event.text || "");
        if (said) callbacks.onUser?.(said);
      }
    },
    onError: () => callbacks.onStatus?.("The voice tutor disconnected. The lesson audio continues."),
    onClose: () => {
      callbacks.onStatus?.("");
      const done = lessonDone;
      lessonDone = null;
      awaitingAnswer = false;
      done?.();
    },
  });

  return {
    setLessonAudible(audible: boolean) {
      lessonAudible = audible;
    },
    speakLesson(text: string, onDone?: () => void) {
      const line = text.trim();
      if (!line || !ws || ws.readyState !== WebSocket.OPEN) return false;
      awaitingAnswer = false;
      lessonDone = onDone || null;
      clearPlayback();
      cancelResponse();
      sendTextTurn(ws, `Read this lesson segment aloud, then stop. Do not ask a question.\n\n${line}`);
      return true;
    },
    ask(text: string) {
      const line = text.trim();
      if (!line || !ws || ws.readyState !== WebSocket.OPEN) return;
      awaitingAnswer = true;
      lessonDone = null;
      clearPlayback();
      cancelResponse();
      sendTextTurn(ws, line);
    },
    hold() {
      awaitingAnswer = false;
      lessonDone = null;
      clearPlayback();
      cancelResponse();
    },
    stop() {
      window.clearTimeout(endTimer);
      clearPlayback();
      closeXaiVoiceSession(ws);
      ws = null;
      try { processor.disconnect(); } catch { /* */ }
      try { source.disconnect(); } catch { /* */ }
      stream.getTracks().forEach((track) => track.stop());
      void ctx.close();
      noteSpeaking(false);
    },
  };
}
