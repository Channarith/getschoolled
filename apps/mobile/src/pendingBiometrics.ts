/**
 * Learner Check payloads that were captured on the phone and still need a connection.
 * Face stills and the voice recording stay under the app document directory until
 * identity accepts them. Contours are not stored.
 */
import * as FileSystem from "expo-file-system";

import {
  enrollMobileFaceImages,
  enrollMobileVoiceprint,
  setMobileBiometricConsent,
} from "./api";
import {
  PENDING_MAX_AGE_MS,
  isForeignLearner,
  isRejectedCapture,
  pendingRetryDelayMs,
} from "./pendingUpload";

const ROOT = "learner-check-pending";

type Consent = { granted: boolean; guardianGranted: boolean };
type FacePayload = { files: string[]; poses: string[] };
type VoicePayload = { file: string };
type Manifest = {
  studentId: string;
  consent?: Consent;
  face?: FacePayload;
  voice?: VoicePayload;
  queuedAt?: number;
  attempts?: number;
  retryAt?: number;
};

function directory(): string | null {
  const root = FileSystem.documentDirectory;
  if (!root) return null;
  return `${root}${ROOT}/`;
}

function safeId(studentId: string): string {
  const safe = studentId.replace(/[^a-zA-Z0-9_-]/g, "");
  return safe || "learner";
}

async function readManifest(folder: string): Promise<Manifest | null> {
  try {
    const raw = await FileSystem.readAsStringAsync(`${folder}manifest.json`);
    const parsed = JSON.parse(raw) as Manifest;
    return parsed?.studentId ? parsed : null;
  } catch {
    return null;
  }
}

async function writeManifest(folder: string, manifest: Manifest): Promise<void> {
  await FileSystem.writeAsStringAsync(`${folder}manifest.json`, JSON.stringify(manifest));
}

async function folderFor(studentId: string): Promise<{ folder: string; id: string } | null> {
  const root = directory();
  if (!root) return null;
  const id = safeId(studentId);
  const folder = `${root}${id}/`;
  await FileSystem.makeDirectoryAsync(folder, { intermediates: true });
  return { folder, id };
}

async function load(studentId: string): Promise<{ folder: string; manifest: Manifest } | null> {
  const located = await folderFor(studentId);
  if (!located) return null;
  const existing = await readManifest(located.folder);
  return {
    folder: located.folder,
    manifest: existing ?? { studentId, queuedAt: Date.now() },
  };
}

function freshAttempt(manifest: Manifest, consent?: Consent): void {
  manifest.attempts = 0;
  manifest.retryAt = Date.now() + pendingRetryDelayMs(0);
  manifest.queuedAt = manifest.queuedAt ?? Date.now();
  if (consent) manifest.consent = consent;
}

export async function rememberPendingConsent(studentId: string, guardianGranted: boolean): Promise<void> {
  const loaded = await load(studentId);
  if (!loaded) return;
  loaded.manifest.studentId = studentId;
  loaded.manifest.consent = { granted: true, guardianGranted };
  await writeManifest(loaded.folder, loaded.manifest);
}

export async function queuePendingFace(
  studentId: string,
  imagesBase64: string[],
  poses: string[],
  consent?: Consent,
): Promise<void> {
  const loaded = await load(studentId);
  if (!loaded) throw new Error("This phone couldn't keep the face check for later.");
  const files: string[] = [];
  for (let index = 0; index < imagesBase64.length; index += 1) {
    const name = `face-${index}.b64`;
    await FileSystem.writeAsStringAsync(`${loaded.folder}${name}`, imagesBase64[index]);
    files.push(name);
  }
  loaded.manifest.studentId = studentId;
  loaded.manifest.face = { files, poses };
  freshAttempt(loaded.manifest, consent);
  await writeManifest(loaded.folder, loaded.manifest);
}

export async function queuePendingVoice(
  studentId: string,
  sourceUri: string,
  consent?: Consent,
): Promise<void> {
  const loaded = await load(studentId);
  if (!loaded) throw new Error("This phone couldn't keep the voice check for later.");
  const name = "voice.m4a";
  await FileSystem.deleteAsync(`${loaded.folder}${name}`, { idempotent: true }).catch(() => undefined);
  await FileSystem.copyAsync({ from: sourceUri, to: `${loaded.folder}${name}` });
  loaded.manifest.studentId = studentId;
  loaded.manifest.voice = { file: name };
  freshAttempt(loaded.manifest, consent);
  await writeManifest(loaded.folder, loaded.manifest);
}

async function dropFace(folder: string, manifest: Manifest): Promise<void> {
  for (const file of manifest.face?.files ?? []) {
    await FileSystem.deleteAsync(`${folder}${file}`, { idempotent: true }).catch(() => undefined);
  }
  delete manifest.face;
  await writeManifest(folder, manifest);
}

async function dropVoice(folder: string, manifest: Manifest): Promise<void> {
  if (manifest.voice) {
    await FileSystem.deleteAsync(`${folder}${manifest.voice.file}`, { idempotent: true }).catch(() => undefined);
  }
  delete manifest.voice;
  await writeManifest(folder, manifest);
}

async function later(folder: string, manifest: Manifest): Promise<void> {
  const attempts = (manifest.attempts ?? 0) + 1;
  manifest.attempts = attempts;
  manifest.retryAt = Date.now() + pendingRetryDelayMs(attempts);
  await writeManifest(folder, manifest);
}

async function flushFolder(folderName: string, force: boolean): Promise<void> {
  const root = directory();
  if (!root) return;
  const folder = `${root}${folderName}/`;
  const manifest = await readManifest(folder);
  if (!manifest) return;
  const now = Date.now();
  if (now - (manifest.queuedAt ?? now) > PENDING_MAX_AGE_MS) {
    await FileSystem.deleteAsync(folder, { idempotent: true }).catch(() => undefined);
    return;
  }
  if (!force && manifest.retryAt && manifest.retryAt > now) return;
  if (manifest.consent) {
    try {
      await setMobileBiometricConsent(
        manifest.studentId,
        manifest.consent.granted,
        manifest.consent.guardianGranted,
      );
      delete manifest.consent;
      await writeManifest(folder, manifest);
    } catch (reason) {
      if (isRejectedCapture(reason) && !isForeignLearner(reason)) {
        await FileSystem.deleteAsync(folder, { idempotent: true }).catch(() => undefined);
        return;
      }
      await later(folder, manifest);
      return;
    }
  }
  if (manifest.face) {
    try {
      const images: string[] = [];
      for (const file of manifest.face.files) {
        images.push(await FileSystem.readAsStringAsync(`${folder}${file}`));
      }
      await enrollMobileFaceImages(manifest.studentId, images, manifest.face.poses);
      await dropFace(folder, manifest);
    } catch (reason) {
      if (isRejectedCapture(reason) && !isForeignLearner(reason)) {
        await dropFace(folder, manifest);
      } else {
        await later(folder, manifest);
        return;
      }
    }
  }
  const current = (await readManifest(folder)) ?? manifest;
  if (current.voice) {
    try {
      const audio = await FileSystem.readAsStringAsync(`${folder}${current.voice.file}`, {
        encoding: FileSystem.EncodingType.Base64,
      });
      await enrollMobileVoiceprint(current.studentId, audio);
      await dropVoice(folder, current);
    } catch (reason) {
      if (isRejectedCapture(reason) && !isForeignLearner(reason)) {
        await dropVoice(folder, current);
      } else {
        await later(folder, current);
        return;
      }
    }
  }
  const left = await readManifest(folder);
  if (left && !left.face && !left.voice && !left.consent) {
    await FileSystem.deleteAsync(folder, { idempotent: true }).catch(() => undefined);
  }
}

let flushing: Promise<void> | null = null;

/**
 * Send every Learner Check that is still sitting on this phone.
 * Failed sends wait 15s, 30s, 1m ... up to 15 minutes; `force` skips the wait.
 */
export function flushPendingLearnerCheck(force = false): Promise<void> {
  if (flushing) return flushing;
  flushing = (async () => {
    const root = directory();
    if (!root) return;
    let names: string[] = [];
    try {
      names = await FileSystem.readDirectoryAsync(root);
    } catch {
      return;
    }
    for (const name of names) {
      await flushFolder(name, force).catch(() => undefined);
    }
  })().finally(() => {
    flushing = null;
  });
  return flushing;
}
