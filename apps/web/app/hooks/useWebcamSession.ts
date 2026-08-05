"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  createWebcamSession,
  endWebcamSession,
  submitWebcamFrame,
  askVoiceAgent,
  openWebcamWebSocket,
  type FrameAnalysis,
  type VoiceAgentResponse,
} from "../lib/api";

export type WebcamSessionMode = "solo" | "group";

export type PresenceState = "unknown" | "present" | "away" | "absent";

export type WebcamSessionHookOptions = {
  classType?: WebcamSessionMode;
  studentIds?: string[];
  lessonContext?: string;
  participantId?: string;
  agentType?: "teacher" | "self_teach";
  /** Frames per second to capture and submit. Default 2. */
  fps?: number;
  /** If true, submit frames over WebSocket (lower latency). Default false = REST. */
  useWebSocket?: boolean;
  onPresenceChange?: (state: PresenceState, event: string | null) => void;
  onVoiceResponse?: (resp: VoiceAgentResponse) => void;
  onAbsent?: (awaySeconds: number) => void;
  onReturned?: () => void;
};

export type WebcamSessionState = {
  sessionId: string | null;
  isActive: boolean;
  isLoading: boolean;
  error: string | null;
  presenceState: PresenceState;
  attention: number | null;
  awayDurationS: number;
  frameCount: number;
  lastAnalysis: FrameAnalysis | null;
  lastVoiceResponse: VoiceAgentResponse | null;
  /** True when the camera stream is live */
  cameraReady: boolean;
};

export function useWebcamSession(opts: WebcamSessionHookOptions = {}) {
  const {
    classType = "solo",
    studentIds = [],
    lessonContext = "",
    participantId = "student",
    agentType = "teacher",
    fps = 2,
    useWebSocket = false,
    onPresenceChange,
    onVoiceResponse,
    onAbsent,
    onReturned,
  } = opts;

  const [state, setState] = useState<WebcamSessionState>({
    sessionId: null,
    isActive: false,
    isLoading: false,
    error: null,
    presenceState: "unknown",
    attention: null,
    awayDurationS: 0,
    frameCount: 0,
    lastAnalysis: null,
    lastVoiceResponse: null,
    cameraReady: false,
  });

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const prevPresenceRef = useRef<PresenceState>("unknown");

  // Track absence for callbacks.
  const absenceCallbackRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleAnalysis = useCallback(
    (analysis: FrameAnalysis) => {
      const newPresence = analysis.presence_state as PresenceState;
      setState((prev) => ({
        ...prev,
        presenceState: newPresence,
        attention: analysis.attention,
        awayDurationS: analysis.away_duration_s,
        frameCount: analysis.frame_count,
        lastAnalysis: analysis,
      }));

      if (analysis.presence_event && newPresence !== prevPresenceRef.current) {
        onPresenceChange?.(newPresence, analysis.presence_event);
        if (
          (analysis.presence_event === "away" || analysis.presence_event === "absent") &&
          onAbsent
        ) {
          onAbsent(analysis.away_duration_s);
        }
        if (analysis.presence_event === "returned" && onReturned) {
          onReturned();
        }
      }
      prevPresenceRef.current = newPresence;
    },
    [onPresenceChange, onAbsent, onReturned]
  );

  const captureFrame = useCallback((): Blob | null => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState < 2) return null;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    canvas.width = video.videoWidth || 320;
    canvas.height = video.videoHeight || 240;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    // toBlob is async; use a sync path via toDataURL → Blob conversion.
    const dataUrl = canvas.toDataURL("image/jpeg", 0.7);
    const binary = atob(dataUrl.split(",")[1]);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return new Blob([bytes], { type: "image/jpeg" });
  }, []);

  const sendFrameRest = useCallback(
    async (sessionId: string) => {
      const blob = captureFrame();
      if (!blob) return;
      try {
        const analysis = await submitWebcamFrame(sessionId, blob, {
          participantId,
        });
        handleAnalysis(analysis);
      } catch {
        // Non-fatal: skip this frame
      }
    },
    [captureFrame, handleAnalysis, participantId]
  );

  const sendFrameWs = useCallback(
    (ws: WebSocket) => {
      const blob = captureFrame();
      if (!blob || ws.readyState !== WebSocket.OPEN) return;
      ws.send(
        JSON.stringify({
          type: "frame",
          participant_id: participantId,
          face_present: false,
          attention: null,
        })
      );
      const reader = new FileReader();
      reader.onloadend = () => {
        if (ws.readyState === WebSocket.OPEN && reader.result instanceof ArrayBuffer) {
          ws.send(reader.result);
        }
      };
      reader.readAsArrayBuffer(blob);
    },
    [captureFrame, participantId]
  );

  const start = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    try {
      // Request camera access.
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 320, height: 240 },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => undefined);
      }

      // Create backend session.
      const session = await createWebcamSession({
        class_type: classType,
        student_ids: studentIds,
        lesson_context: lessonContext,
      });
      sessionIdRef.current = session.session_id;
      setState((prev) => ({
        ...prev,
        sessionId: session.session_id,
        isActive: true,
        isLoading: false,
        cameraReady: true,
      }));

      if (useWebSocket) {
        const ws = openWebcamWebSocket(session.session_id);
        wsRef.current = ws;
        ws.onmessage = (evt) => {
          try {
            const msg = JSON.parse(evt.data as string);
            if (msg.type === "analysis") handleAnalysis(msg as FrameAnalysis);
          } catch {
            // ignore parse errors
          }
        };
        intervalRef.current = setInterval(() => sendFrameWs(ws), 1000 / fps);
      } else {
        intervalRef.current = setInterval(
          () => void sendFrameRest(session.session_id),
          1000 / fps
        );
      }
    } catch (err) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: err instanceof Error ? err.message : "Failed to start webcam session",
      }));
    }
  }, [
    classType,
    studentIds,
    lessonContext,
    fps,
    useWebSocket,
    sendFrameRest,
    sendFrameWs,
    handleAnalysis,
  ]);

  const stop = useCallback(async () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (sessionIdRef.current) {
      await endWebcamSession(sessionIdRef.current).catch(() => undefined);
      sessionIdRef.current = null;
    }
    setState({
      sessionId: null,
      isActive: false,
      isLoading: false,
      error: null,
      presenceState: "unknown",
      attention: null,
      awayDurationS: 0,
      frameCount: 0,
      lastAnalysis: null,
      lastVoiceResponse: null,
      cameraReady: false,
    });
  }, []);

  const askAgent = useCallback(
    async (text: string, withAudio = false): Promise<VoiceAgentResponse | null> => {
      const sid = sessionIdRef.current;
      if (!sid) return null;
      try {
        const resp = await askVoiceAgent(sid, {
          text,
          participantId,
          audio: withAudio,
          agentType,
        });
        setState((prev) => ({ ...prev, lastVoiceResponse: resp }));
        onVoiceResponse?.(resp);
        return resp;
      } catch {
        return null;
      }
    },
    [agentType, participantId, onVoiceResponse]
  );

  // Cleanup on unmount.
  useEffect(() => {
    return () => {
      void stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    state,
    videoRef,
    canvasRef,
    start,
    stop,
    askAgent,
  };
}

// Re-export for consumers that want direct access without importing from api.ts.
export { submitWebcamFrame, openWebcamWebSocket, getWebcamPresence } from "../lib/api";
