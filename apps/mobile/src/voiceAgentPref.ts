/**
 * Temporary Sala / xAI Voice Agent choice.
 *
 * The choice lives in the existing settings record. Until the learner picks
 * one, Sala is used unless the speech service reports an xAI engine that is
 * actually available. The xAI API key never enters this module.
 */

import { readSettingsPatch, setSettings } from "./storage";
import { getXaiVoiceStatus } from "./xaiVoice";

export type VoiceAgentChoice = "sala" | "xai";

type Listener = (choice: VoiceAgentChoice) => void;

const listeners = new Set<Listener>();

export function normalizeVoiceAgent(value: unknown): VoiceAgentChoice {
  const raw = String(value ?? "").trim().toLowerCase().replace(/[\s_]+/g, "-");
  if (raw === "xai" || raw === "xai-voice" || raw === "xai-voice-agent" || raw === "grok" || raw === "grok-voice") {
    return "xai";
  }
  return "sala";
}

export function isConfiguredXaiEngine(engine: string | undefined, available: boolean | undefined): boolean {
  if (!available) return false;
  const raw = (engine || "").trim().toLowerCase();
  if (!raw || raw === "none" || raw === "sala" || raw.startsWith("salane")) return false;
  return raw === "xai" || raw.startsWith("xai") || raw.includes("grok");
}

/** Explicit storage wins. Otherwise Sala, unless status itself is a live xAI engine. */
export function resolveVoiceAgent(
  stored: VoiceAgentChoice | null,
  status?: { engine?: string; available?: boolean } | null,
): VoiceAgentChoice {
  if (stored) return stored;
  if (isConfiguredXaiEngine(status?.engine, status?.available)) return "xai";
  return "sala";
}

export async function getStoredVoiceAgent(): Promise<VoiceAgentChoice | null> {
  const raw = await readSettingsPatch();
  if (!Object.prototype.hasOwnProperty.call(raw, "voiceAgent")) return null;
  const value = raw.voiceAgent;
  if (value == null || String(value).trim() === "") return null;
  return normalizeVoiceAgent(value);
}

export function subscribeVoiceAgent(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function publish(choice: VoiceAgentChoice): void {
  for (const listener of listeners) listener(choice);
}

export async function loadVoiceAgentChoice(): Promise<VoiceAgentChoice> {
  const stored = await getStoredVoiceAgent();
  if (stored) {
    publish(stored);
    return stored;
  }
  const status = await getXaiVoiceStatus();
  const choice = resolveVoiceAgent(null, status);
  publish(choice);
  return choice;
}

export async function saveVoiceAgentChoice(choice: VoiceAgentChoice): Promise<VoiceAgentChoice> {
  const next = normalizeVoiceAgent(choice);
  await setSettings({ voiceAgent: next });
  publish(next);
  return next;
}

/** User-facing text from a failed mint. Drops anything that looks like a secret. */
export function publicVoiceError(message: string, fallback: string): string {
  let text = (message || "").replace(/\s+/g, " ").trim();
  const detail = text.match(/"detail"\s*:\s*"((?:\\.|[^"\\])*)"/);
  if (detail?.[1]) {
    text = detail[1].replace(/\\"/g, "\"").replace(/\\n/g, " ").trim();
  }
  if (!text) return fallback;
  if (/bearer\s+\S+/i.test(text)) return fallback;
  if (/\bxai-[a-z0-9_-]{16,}\b/i.test(text)) return fallback;
  if (/api[_-]?key\s*[:=]\s*\S+/i.test(text)) return fallback;
  return text.slice(0, 240);
}
