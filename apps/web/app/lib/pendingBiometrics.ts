/**
 * Learner Check payloads captured in the browser and still waiting for a connection.
 * Face values are the on-device embeddings. The voice clip is the recording.
 * Contours are not stored.
 */
import { enrollBiometricFace, enrollVoiceprint, setBiometricConsent } from "./api";
import {
  PENDING_MAX_AGE_MS,
  isForeignLearner,
  isRejectedCapture,
  pendingRetryDelayMs,
} from "./pendingUpload";

const DB_NAME = "salareen-learner-check";
const STORE = "pending";

export type PendingFace = { embeddings: number[][]; poseSequence: string[] };
export type PendingVoice = { mime: string; base64: string };
export type PendingConsent = { granted: boolean; guardianGranted: boolean };
export type PendingRecord = {
  studentId: string;
  consent?: PendingConsent;
  face?: PendingFace;
  voice?: PendingVoice;
  queuedAt?: number;
  attempts?: number;
  retryAt?: number;
};

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("This browser couldn't keep the check for later."));
      return;
    }
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: "studentId" });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("This browser couldn't keep the check for later."));
  });
}

function requestToPromise<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("This browser couldn't keep the check for later."));
  });
}

async function read(studentId: string): Promise<PendingRecord | null> {
  const db = await openDb();
  try {
    const row = await requestToPromise(db.transaction(STORE, "readonly").objectStore(STORE).get(studentId));
    return (row as PendingRecord | undefined) ?? null;
  } finally {
    db.close();
  }
}

async function write(record: PendingRecord): Promise<void> {
  const db = await openDb();
  try {
    await requestToPromise(db.transaction(STORE, "readwrite").objectStore(STORE).put(record));
  } finally {
    db.close();
  }
}

async function remove(studentId: string): Promise<void> {
  const db = await openDb();
  try {
    await requestToPromise(db.transaction(STORE, "readwrite").objectStore(STORE).delete(studentId));
  } finally {
    db.close();
  }
}

async function all(): Promise<PendingRecord[]> {
  const db = await openDb();
  try {
    const rows = await requestToPromise(db.transaction(STORE, "readonly").objectStore(STORE).getAll());
    return (rows as PendingRecord[]) ?? [];
  } finally {
    db.close();
  }
}

async function merge(studentId: string, patch: Partial<Omit<PendingRecord, "studentId">>): Promise<void> {
  if (!studentId) throw new Error("This browser couldn't keep the check for later.");
  const existing = await read(studentId).catch(() => null);
  const next: PendingRecord = {
    studentId,
    queuedAt: existing?.queuedAt ?? Date.now(),
    attempts: "attempts" in patch ? patch.attempts : existing?.attempts,
    retryAt: "retryAt" in patch ? patch.retryAt : existing?.retryAt,
  };
  const consent = "consent" in patch ? patch.consent : existing?.consent;
  if (consent) next.consent = consent;
  const face = "face" in patch ? patch.face : existing?.face;
  if (face) next.face = face;
  const voice = "voice" in patch ? patch.voice : existing?.voice;
  if (voice) next.voice = voice;
  if (!next.face && !next.voice && !next.consent) {
    await remove(studentId);
    return;
  }
  await write(next);
}

export async function queuePendingFace(
  studentId: string,
  embeddings: number[][],
  poseSequence: string[],
  consent?: PendingConsent,
): Promise<void> {
  await merge(studentId, {
    face: { embeddings, poseSequence },
    attempts: 0,
    retryAt: Date.now() + pendingRetryDelayMs(0),
    ...(consent ? { consent } : {}),
  });
}

export async function queuePendingVoice(
  studentId: string,
  voice: PendingVoice,
  consent?: PendingConsent,
): Promise<void> {
  await merge(studentId, {
    voice,
    attempts: 0,
    retryAt: Date.now() + pendingRetryDelayMs(0),
    ...(consent ? { consent } : {}),
  });
}

export async function dropPendingFace(studentId: string): Promise<void> {
  await merge(studentId, { face: undefined });
}

export async function blobToBase64(blob: Blob): Promise<string> {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  }
  return btoa(binary);
}

function blobFromBase64(base64: string, mime: string): Blob {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return new Blob([bytes], { type: mime || "application/octet-stream" });
}

async function later(record: PendingRecord): Promise<void> {
  const attempts = (record.attempts ?? 0) + 1;
  await merge(record.studentId, { attempts, retryAt: Date.now() + pendingRetryDelayMs(attempts) });
}

async function flushRecord(record: PendingRecord): Promise<void> {
  if (record.consent) {
    try {
      await setBiometricConsent(record.studentId, {
        granted: record.consent.granted,
        guardian_granted: record.consent.guardianGranted,
        retention_days: 365,
      });
      await merge(record.studentId, { consent: undefined });
    } catch (reason) {
      if (isRejectedCapture(reason) && !isForeignLearner(reason)) {
        await remove(record.studentId);
        return;
      }
      await later(record);
      return;
    }
  }
  if (record.face) {
    try {
      await enrollBiometricFace(record.studentId, record.face.embeddings, record.face.poseSequence);
      await merge(record.studentId, { face: undefined });
    } catch (reason) {
      if (!isRejectedCapture(reason) || isForeignLearner(reason)) {
        await later(record);
        return;
      }
      await merge(record.studentId, { face: undefined });
    }
  }
  const current = (await read(record.studentId)) ?? record;
  if (!current.voice) return;
  try {
    await enrollVoiceprint(current.studentId, blobFromBase64(current.voice.base64, current.voice.mime));
    await merge(current.studentId, { voice: undefined });
  } catch (reason) {
    if (isRejectedCapture(reason) && !isForeignLearner(reason)) {
      await merge(current.studentId, { voice: undefined });
    } else {
      await later(current);
    }
  }
}

let flushing: Promise<void> | null = null;

/**
 * Send every Learner Check that is still sitting in this browser.
 * Failed sends wait 15s, 30s, 1m ... up to 15 minutes. `force` ignores the
 * wait, for example when the browser reports it is back online.
 */
export function flushPendingLearnerCheck(force = false): Promise<void> {
  if (flushing) return flushing;
  flushing = (async () => {
    let rows: PendingRecord[] = [];
    try {
      rows = await all();
    } catch {
      return;
    }
    const now = Date.now();
    for (const row of rows) {
      if (now - (row.queuedAt ?? now) > PENDING_MAX_AGE_MS) {
        await remove(row.studentId).catch(() => undefined);
        continue;
      }
      if (!force && row.retryAt && row.retryAt > now) continue;
      await flushRecord(row).catch(() => undefined);
    }
  })().finally(() => {
    flushing = null;
  });
  return flushing;
}
