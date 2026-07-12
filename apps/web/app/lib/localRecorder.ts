// Local (client-side) session recording for the group video room.
//
// Records what the learner sees + hears (screen/tab video + tab audio, mixed
// with their mic) via MediaRecorder, and keeps everything ON THE USER'S DEVICE:
//   * playback library -> IndexedDB (local browser storage),
//   * "Save to disk" -> File System Access API (falls back to a download).
// Nothing is uploaded to the cloud, so cloud disk isn't consumed by recordings.

export type RecordingMeta = {
  id: string;
  roomId: string;
  title: string;
  createdAt: number;
  durationMs: number;
  size: number;
  mime: string;
};

export type StoredRecording = RecordingMeta & { blob: Blob };

export function isRecordingSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof (window as unknown as { MediaRecorder?: unknown }).MediaRecorder !== "undefined" &&
    Boolean(navigator.mediaDevices?.getDisplayMedia)
  );
}

function pickMime(): string {
  const candidates = [
    "video/webm;codecs=vp9,opus",
    "video/webm;codecs=vp8,opus",
    "video/webm",
    "video/mp4",
  ];
  const MR = (window as unknown as { MediaRecorder: typeof MediaRecorder }).MediaRecorder;
  for (const m of candidates) {
    try {
      if (MR.isTypeSupported && MR.isTypeSupported(m)) return m;
    } catch { /* ignore */ }
  }
  return "video/webm";
}

// --------------------------------------------------------------------------- //
// Recorder
// --------------------------------------------------------------------------- //
export class LocalSessionRecorder {
  private recorder: MediaRecorder | null = null;
  private chunks: BlobPart[] = [];
  private displayStream: MediaStream | null = null;
  private micStream: MediaStream | null = null;
  private audioCtx: AudioContext | null = null;
  private startedAt = 0;
  private mime = "video/webm";

  get isRecording(): boolean {
    return this.recorder?.state === "recording";
  }

  /** Prompt to share the tab/screen, mix in the mic, and start recording. */
  async start(): Promise<void> {
    if (!isRecordingSupported()) throw new Error("Recording is not supported in this browser.");
    this.displayStream = await navigator.mediaDevices.getDisplayMedia({
      video: { frameRate: 30 },
      audio: true,   // capture tab audio (narration + other participants)
    });

    // Best-effort: also capture the mic so the learner's voice is recorded.
    let audioTracks: MediaStreamTrack[] = this.displayStream.getAudioTracks();
    try {
      this.micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const AC = (window as unknown as { AudioContext?: typeof AudioContext; webkitAudioContext?: typeof AudioContext });
      const Ctor = AC.AudioContext || AC.webkitAudioContext;
      if (Ctor && (this.displayStream.getAudioTracks().length || this.micStream.getAudioTracks().length)) {
        this.audioCtx = new Ctor();
        const dest = this.audioCtx.createMediaStreamDestination();
        for (const s of [this.displayStream, this.micStream]) {
          if (s.getAudioTracks().length) {
            this.audioCtx.createMediaStreamSource(s).connect(dest);
          }
        }
        audioTracks = dest.stream.getAudioTracks();
      }
    } catch { /* mic optional */ }

    const mixed = new MediaStream([
      ...this.displayStream.getVideoTracks(),
      ...audioTracks,
    ]);
    this.mime = pickMime();
    this.chunks = [];
    this.recorder = new MediaRecorder(mixed, { mimeType: this.mime });
    this.recorder.ondataavailable = (e) => { if (e.data && e.data.size) this.chunks.push(e.data); };
    // If the user stops sharing via the browser UI, finalize gracefully.
    this.displayStream.getVideoTracks()[0]?.addEventListener("ended", () => {
      if (this.isRecording) this.recorder?.stop();
    });
    this.startedAt = Date.now();
    this.recorder.start(1000);   // 1s timeslice so long sessions don't buffer unbounded
  }

  /** Stop and return the assembled recording (video/webm blob + metadata). */
  stop(meta: { roomId: string; title: string }): Promise<StoredRecording> {
    return new Promise((resolve, reject) => {
      const rec = this.recorder;
      if (!rec) { reject(new Error("Not recording")); return; }
      rec.onstop = () => {
        const blob = new Blob(this.chunks, { type: this.mime });
        const durationMs = Date.now() - this.startedAt;
        this.cleanup();
        resolve({
          id: `rec-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          roomId: meta.roomId,
          title: meta.title || "Live session",
          createdAt: Date.now(),
          durationMs,
          size: blob.size,
          mime: this.mime,
          blob,
        });
      };
      rec.onerror = () => { this.cleanup(); reject(new Error("Recording error")); };
      try { rec.stop(); } catch (e) { this.cleanup(); reject(e as Error); }
    });
  }

  private cleanup(): void {
    this.displayStream?.getTracks().forEach((t) => t.stop());
    this.micStream?.getTracks().forEach((t) => t.stop());
    try { void this.audioCtx?.close(); } catch { /* */ }
    this.displayStream = null;
    this.micStream = null;
    this.audioCtx = null;
    this.recorder = null;
    this.chunks = [];
  }
}

// --------------------------------------------------------------------------- //
// IndexedDB playback library (local device only)
// --------------------------------------------------------------------------- //
const DB_NAME = "aoep-recordings";
const STORE = "recordings";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "id" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function saveRecording(rec: StoredRecording): Promise<void> {
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).put(rec);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  db.close();
}

export async function listRecordings(roomId?: string): Promise<RecordingMeta[]> {
  const db = await openDb();
  const all = await new Promise<StoredRecording[]>((resolve, reject) => {
    const tx = db.transaction(STORE, "readonly");
    const req = tx.objectStore(STORE).getAll();
    req.onsuccess = () => resolve(req.result as StoredRecording[]);
    req.onerror = () => reject(req.error);
  });
  db.close();
  return all
    .filter((r) => !roomId || r.roomId === roomId)
    .sort((a, b) => b.createdAt - a.createdAt)
    .map(({ blob: _blob, ...meta }) => meta);   // don't hand blobs to the list view
}

export async function getRecordingBlob(id: string): Promise<Blob | null> {
  const db = await openDb();
  const rec = await new Promise<StoredRecording | undefined>((resolve, reject) => {
    const tx = db.transaction(STORE, "readonly");
    const req = tx.objectStore(STORE).get(id);
    req.onsuccess = () => resolve(req.result as StoredRecording | undefined);
    req.onerror = () => reject(req.error);
  });
  db.close();
  return rec?.blob ?? null;
}

export async function deleteRecording(id: string): Promise<void> {
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).delete(id);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  db.close();
}

// --------------------------------------------------------------------------- //
// Save to the user's hard drive
// --------------------------------------------------------------------------- //
export function suggestedFilename(meta: { title: string; createdAt: number }): string {
  const date = new Date(meta.createdAt).toISOString().slice(0, 19).replace(/[:T]/g, "-");
  const safe = (meta.title || "session").replace(/[^\w-]+/g, "_").slice(0, 40);
  return `salareen-${safe}-${date}.webm`;
}

/** Write the recording to a file the user picks; falls back to a download. */
export async function saveBlobToDisk(blob: Blob, filename: string): Promise<void> {
  const picker = (window as unknown as {
    showSaveFilePicker?: (opts: unknown) => Promise<{
      createWritable: () => Promise<{ write: (b: Blob) => Promise<void>; close: () => Promise<void> }>;
    }>;
  }).showSaveFilePicker;
  if (picker) {
    try {
      const handle = await picker({
        suggestedName: filename,
        types: [{ description: "WebM video", accept: { "video/webm": [".webm"] } }],
      });
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      return;
    } catch (e) {
      if ((e as DOMException)?.name === "AbortError") return;   // user cancelled
      // otherwise fall through to download
    }
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

export function formatDuration(ms: number): string {
  const s = Math.round(ms / 1000);
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
}

export function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}
