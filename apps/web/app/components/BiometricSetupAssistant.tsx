"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Image from "next/image";
import {
  deleteBiometrics,
  enrollBiometricFace,
  enrollVoiceprint,
  getSetupAssistant,
  setBiometricConsent,
  submitGovernmentId,
  updateSetupAssistant,
} from "../lib/api";
import { createVisionEngine, type VisionEngine } from "../lib/vision";
import styles from "./BiometricSetupAssistant.module.css";

const VOICE_PROMPT =
  "Today I’m ready to learn with Salareen. Can you hear my voice clearly? Yes—I’m speaking naturally and confidently.";

type Step = "welcome" | "privacy" | "portrait" | "pose" | "voice" | "identity" | "complete";
const FLOW: Step[] = ["welcome", "privacy", "portrait", "pose", "voice", "identity", "complete"];
const MEDIA: Record<Step, string> = {
  welcome: "welcome", privacy: "privacy", portrait: "portrait", pose: "pose",
  voice: "voice", identity: "identity", complete: "welcome",
};

const COPY: Record<Step, { eyebrow: string; title: string; body: string }> = {
  welcome: {
    eyebrow: "Optional identity setup",
    title: "A simpler way to prove it’s you.",
    body: "Four short checks can protect your learning record and unlock accredited courses. You can skip this now unless your course requires verified identity.",
  },
  privacy: {
    eyebrow: "Your choice. Your data.",
    title: "Private by design.",
    body: "Camera, voice, and document media is processed only for setup. Salareen stores protected identity templates and verification decisions—not raw recordings or ID photos.",
  },
  portrait: {
    eyebrow: "Check 1 of 4 · Portrait",
    title: "Look naturally at the camera.",
    body: "Center your face in the frame. When you’re ready, a three-second timer will take the portrait automatically.",
  },
  pose: {
    eyebrow: "Check 2 of 4 · Movement",
    title: "Turn gently with the guide.",
    body: "We’ll capture left, right, up, and down. Move only your head, keep your shoulders relaxed, and pause briefly in each direction.",
  },
  voice: {
    eyebrow: "Check 3 of 4 · Voice",
    title: "Speak in your everyday voice.",
    body: "Read the sentence naturally. This 10-second sample creates a voiceprint; the recording itself is discarded after processing.",
  },
  identity: {
    eyebrow: "Check 4 of 4 · Government ID",
    title: "Verify an accredited learner.",
    body: "Required only for courses that lead to a certificate, license, or regulated exam. Your ID image is processed ephemerally and is not retained.",
  },
  complete: {
    eyebrow: "Setup complete",
    title: "You’re ready to learn.",
    body: "Your identity setup can be reviewed or removed at any time in Profile → Settings → Camera & Identity.",
  },
};

type Props = {
  studentId: string;
  ageBand?: string;
  requireGovernmentId?: boolean;
  allowSkip?: boolean;
  onComplete?: () => void;
  onSkip?: () => void;
};

export default function BiometricSetupAssistant({
  studentId,
  ageBand = "adult",
  requireGovernmentId = false,
  allowSkip = true,
  onComplete,
  onSkip,
}: Props) {
  const [step, setStep] = useState<Step>("welcome");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [countdown, setCountdown] = useState(0);
  const [poseIndex, setPoseIndex] = useState(0);
  const [embeddings, setEmbeddings] = useState<number[][]>([]);
  const [guardianConsent, setGuardianConsent] = useState(ageBand === "adult");
  const [idFile, setIdFile] = useState<File | null>(null);
  const [hasEnrollment, setHasEnrollment] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const engineRef = useRef<VisionEngine | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const stopMedia = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  }, []);

  useEffect(() => () => stopMedia(), [stopMedia]);

  useEffect(() => {
    getSetupAssistant(studentId).then((state) => {
      setHasEnrollment(
        state.portrait.status === "verified"
        || state.voice.status === "verified"
        || state.government_id.status === "verified",
      );
      if (state.voice.status === "verified") setStep(requireGovernmentId ? "identity" : "complete");
      else if (state.portrait.status === "verified") setStep("voice");
    }).catch(() => undefined);
  }, [requireGovernmentId, studentId]);

  const startCamera = useCallback(async () => {
    if (streamRef.current) return;
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 1280 } },
      audio: false,
    });
    streamRef.current = stream;
    if (videoRef.current) {
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
    }
    engineRef.current ??= await createVisionEngine();
  }, []);

  useEffect(() => {
    if (step === "portrait" || step === "pose") {
      startCamera().catch((reason) => setError(`Camera unavailable: ${String(reason)}`));
    } else {
      stopMedia();
    }
  }, [startCamera, step, stopMedia]);

  const captureEmbedding = useCallback(async () => {
    const video = videoRef.current;
    const engine = engineRef.current;
    if (!video || !engine) throw new Error("Camera is still starting");
    const faces = engine.detectAndEmbed(video);
    if (faces.length !== 1) throw new Error("Keep one face centered in the frame");
    return faces[0].embedding;
  }, []);

  async function timedCapture() {
    setError("");
    setBusy(true);
    try {
      for (let value = 3; value > 0; value -= 1) {
        setCountdown(value);
        await new Promise((resolve) => window.setTimeout(resolve, 850));
      }
      setCountdown(0);
      const vector = await captureEmbedding();
      setEmbeddings([vector]);
      setStep("pose");
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  }

  const poses = ["left", "right", "up", "down"];
  async function capturePose() {
    setError("");
    setBusy(true);
    try {
      const vector = await captureEmbedding();
      const next = [...embeddings, vector];
      setEmbeddings(next);
      if (poseIndex < poses.length - 1) {
        setPoseIndex((value) => value + 1);
      } else {
        await enrollBiometricFace(studentId, next, poses);
        setStep("voice");
      }
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function recordVoice() {
    setError("");
    setBusy(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const recorder = new MediaRecorder(stream);
      recorderRef.current = recorder;
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunksRef.current.push(event.data);
      };
      const finished = new Promise<Blob>((resolve, reject) => {
        recorder.onerror = () => reject(new Error("Voice recording failed"));
        recorder.onstop = () => resolve(
          new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" }),
        );
      });
      recorder.start();
      await new Promise((resolve) => window.setTimeout(resolve, 10_000));
      recorder.stop();
      const blob = await finished;
      stopMedia();
      await enrollVoiceprint(studentId, blob);
      setStep(requireGovernmentId ? "identity" : "complete");
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function acceptPrivacy() {
    setBusy(true);
    setError("");
    try {
      await setBiometricConsent(studentId, {
        granted: true,
        guardian_granted: ageBand === "adult" ? false : guardianConsent,
        retention_days: 365,
      });
      await updateSetupAssistant(studentId, { current_step: "biometrics" });
      setStep("portrait");
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function submitId() {
    if (!idFile) return;
    setBusy(true);
    setError("");
    try {
      const result = await submitGovernmentId(studentId, "government_id", idFile);
      if (result.status !== "verified") {
        throw new Error("The portrait on this ID did not match. Use a clear, well-lit image and try again.");
      }
      setStep("complete");
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function finish() {
    await updateSetupAssistant(studentId, { current_step: "complete", complete: true });
    onComplete?.();
  }

  async function skip() {
    await updateSetupAssistant(studentId, {
      current_step: "complete",
      skipped_biometrics: true,
      complete: true,
    });
    onSkip?.();
  }

  async function removeIdentity() {
    setBusy(true);
    setError("");
    try {
      await deleteBiometrics(studentId);
      setHasEnrollment(false);
      setStep("welcome");
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  }

  const index = FLOW.indexOf(step);
  const media = MEDIA[step];
  const copy = COPY[step];
  const showsCamera = step === "portrait" || step === "pose";

  return (
    <main className={styles.shell}>
      <section className={styles.visual} aria-hidden="true">
        <video className={styles.motion} key={media} autoPlay muted loop playsInline src={`/setup-assistant/${media}.mp4`} />
        <Image
          className={styles.poster}
          src={`/setup-assistant/${media}.webp`}
          alt=""
          fill
          sizes="(max-width: 860px) 100vw, 55vw"
        />
        {showsCamera && (
          <div className={styles.cameraWrap}>
            <video ref={videoRef} className={styles.camera} muted playsInline />
          </div>
        )}
        {countdown > 0 && <div className={styles.countdown}>{countdown}</div>}
        <div className={styles.shade} />
      </section>
      <section className={styles.panel}>
        <div className={styles.progress}>
          {FLOW.slice(0, -1).map((item, itemIndex) => (
            <span key={item} className={itemIndex <= index ? styles.active : ""} />
          ))}
        </div>
        <span className={styles.eyebrow}>{copy.eyebrow}</span>
        <h1>{step === "pose" ? `Turn ${poses[poseIndex]}.` : copy.title}</h1>
        <p>{copy.body}</p>

        {step === "voice" && <div className={styles.prompt}>{VOICE_PROMPT}</div>}
        {step === "privacy" && ageBand !== "adult" && (
          <label className={styles.notice}>
            <input
              type="checkbox"
              checked={guardianConsent}
              onChange={(event) => setGuardianConsent(event.target.checked)}
            />{" "}
            I am the account owner or guardian and consent to this minor’s identity setup.
          </label>
        )}
        {step === "identity" && (
          <label className={styles.file}>
            Choose a clear JPEG or PNG of the front of the ID
            <input
              type="file"
              accept="image/jpeg,image/png"
              onChange={(event) => setIdFile(event.target.files?.[0] ?? null)}
            />
          </label>
        )}
        {error && <p className={styles.error} role="alert">{error}</p>}

        <div className={styles.actions}>
          {step === "welcome" && (
            <>
              <button className={styles.primary} onClick={() => setStep("privacy")}>Continue</button>
              {allowSkip && !requireGovernmentId && (
                <button className={styles.secondary} onClick={() => void skip()}>Set up later</button>
              )}
              {hasEnrollment && !requireGovernmentId && (
                <button className={styles.secondary} disabled={busy} onClick={() => void removeIdentity()}>
                  Remove identity data
                </button>
              )}
            </>
          )}
          {step === "privacy" && (
            <button
              className={styles.primary}
              disabled={busy || (ageBand !== "adult" && !guardianConsent)}
              onClick={() => void acceptPrivacy()}
            >Agree and continue</button>
          )}
          {step === "portrait" && (
            <button className={styles.primary} disabled={busy} onClick={() => void timedCapture()}>
              {busy ? "Hold still…" : "Take portrait"}
            </button>
          )}
          {step === "pose" && (
            <button className={styles.primary} disabled={busy} onClick={() => void capturePose()}>
              {busy ? "Checking…" : `Capture ${poses[poseIndex]}`}
            </button>
          )}
          {step === "voice" && (
            <button className={styles.primary} disabled={busy} onClick={() => void recordVoice()}>
              {busy ? "Recording… keep speaking" : "Record 10-second sample"}
            </button>
          )}
          {step === "identity" && (
            <>
              <button className={styles.primary} disabled={busy || !idFile} onClick={() => void submitId()}>
                {busy ? "Submitting securely…" : "Submit for verification"}
              </button>
              {!requireGovernmentId && (
                <button className={styles.secondary} onClick={() => setStep("complete")}>Not now</button>
              )}
            </>
          )}
          {step === "complete" && (
            <button className={styles.primary} onClick={() => void finish()}>Finish</button>
          )}
        </div>
        <div className={styles.notice}>
          General learning and games never require biometric identity. Accredited and certification courses require all checks before the first full lesson.
        </div>
      </section>
    </main>
  );
}
