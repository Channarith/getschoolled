"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { LiveRoomState } from "../lib/api";
import { ORCHESTRATOR_URL } from "../lib/api";

export type LiveRoomWsMessage = {
  type: string;
  room_id?: string;
  payload?: Record<string, unknown>;
};

export type PresenceToast = {
  kind: string;
  name: string;
  participant_id?: string;
};

export type FloatingReaction = {
  id: string;
  emoji: string;
  x: number;
};

export type GiftOverlay = {
  id: string;
  giftId: string;
  emoji: string;
  label: string;
};

function wsUrl(roomId: string): string {
  const base = ORCHESTRATOR_URL.replace(/\/$/, "");
  const path = `/api/live-rooms/${encodeURIComponent(roomId)}/ws`;
  // Absolute base (http(s)://host) -> swap scheme to ws(s).
  if (/^https?:\/\//.test(base)) {
    return `${base.startsWith("https") ? "wss" : "ws"}://${base.replace(/^https?:\/\//, "")}${path}`;
  }
  // Relative same-origin prefix (e.g. "/orchestrator"): a WebSocket needs an
  // absolute URL, so resolve against the page origin. Without this, host became
  // "/orchestrator" and the browser dialed ws://orchestrator/... (fails -> polling).
  const proto = typeof window !== "undefined" && window.location.protocol === "https:" ? "wss" : "ws";
  const host = typeof window !== "undefined" ? window.location.host : "";
  const prefix = base ? (base.startsWith("/") ? base : `/${base}`) : "";
  return `${proto}://${host}${prefix}${path}`;
}

export type HostAnswer = {
  text: string;
  asker: string;
  done: boolean;
  id: number;
  awaitingConfirmation?: boolean;
};

export function useLiveRoomSocket(
  roomId: string,
  enabled: boolean,
  onRoom: (room: LiveRoomState) => void,
) {
  const [connected, setConnected] = useState(false);
  const [presenceToast, setPresenceToast] = useState<PresenceToast | null>(null);
  const [floatingReactions, setFloatingReactions] = useState<FloatingReaction[]>([]);
  const [giftOverlay, setGiftOverlay] = useState<GiftOverlay | null>(null);
  const [followerCount, setFollowerCount] = useState(0);
  const [viewerCount, setViewerCount] = useState(0);
  const [hostAnswer, setHostAnswer] = useState<HostAnswer | null>(null);
  const hostBufRef = useRef("");
  const hostSeqRef = useRef(0);
  const hostClearTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onRoomRef = useRef(onRoom);
  onRoomRef.current = onRoom;

  const pushReaction = useCallback((emoji: string) => {
    const id = `${Date.now()}-${Math.random()}`;
    const x = 10 + Math.random() * 80;
    setFloatingReactions((prev) => [...prev.slice(-12), { id, emoji, x }]);
    window.setTimeout(() => {
      setFloatingReactions((prev) => prev.filter((r) => r.id !== id));
    }, 2200);
  }, []);

  useEffect(() => {
    if (!enabled || !roomId) return;
    let alive = true;
    let socket: WebSocket | null = null;
    let retryMs = 1500;

    const connect = () => {
      if (!alive) return;
      try {
        socket = new WebSocket(wsUrl(roomId));
      } catch {
        setConnected(false);
        window.setTimeout(connect, retryMs);
        retryMs = Math.min(retryMs * 1.5, 8000);
        return;
      }
      socket.onopen = () => {
        setConnected(true);
        retryMs = 1500;
      };
      socket.onclose = () => {
        setConnected(false);
        if (alive) window.setTimeout(connect, retryMs);
        retryMs = Math.min(retryMs * 1.5, 8000);
      };
      socket.onmessage = (ev) => {
        try {
          const msg = JSON.parse(String(ev.data)) as LiveRoomWsMessage;
          const payload = msg.payload ?? {};
          switch (msg.type) {
            case "room":
              if (payload.room) onRoomRef.current(payload.room as LiveRoomState);
              break;
            case "chat":
              break;
            case "reaction": {
              const reaction = payload.reaction as { emoji?: string } | undefined;
              if (reaction?.emoji) pushReaction(reaction.emoji);
              break;
            }
            case "gift": {
              const gift = payload.gift as {
                gift_id?: string;
                emoji?: string;
                gift_name?: string;
                sender_name?: string;
                recipient_name?: string;
              } | undefined;
              if (gift?.emoji) {
                setGiftOverlay({
                  id: `${Date.now()}`,
                  giftId: gift.gift_id ?? "",
                  emoji: gift.emoji,
                  label: `${gift.sender_name ?? "Someone"} sent ${gift.gift_name ?? "a gift"} to ${gift.recipient_name ?? "Theodore"}`,
                });
                window.setTimeout(() => setGiftOverlay(null), 4200);
              }
              break;
            }
            case "game":
              if (payload.room) onRoomRef.current(payload.room as LiveRoomState);
              break;
            case "presence": {
              const toast = payload.toast as PresenceToast | undefined;
              if (toast?.name) {
                setPresenceToast(toast);
                window.setTimeout(() => setPresenceToast(null), 2800);
              }
              if (typeof payload.viewer_count === "number") {
                setViewerCount(payload.viewer_count as number);
              }
              break;
            }
            case "follow":
              if (typeof payload.follower_count === "number") {
                setFollowerCount(payload.follower_count as number);
              }
              break;
            case "viewer_count":
              if (typeof payload.viewer_count === "number") {
                setViewerCount(payload.viewer_count as number);
              }
              break;
            case "host_delta": {
              const asker = (payload.asker as string) || "";
              const chunk = (payload.text as string) || "";
              const done = Boolean(payload.done);
              if (hostClearTimer.current) {
                clearTimeout(hostClearTimer.current);
                hostClearTimer.current = null;
              }
              if (done) {
                const msg = payload.message as { text?: string } | null | undefined;
                // Prefer the finalized chat message (strip the "@Name " prefix).
                const finalText = (msg?.text || hostBufRef.current || "")
                  .replace(/^@\S+\s*/, "")
                  .trim();
                hostBufRef.current = "";
                setHostAnswer({
                  text: finalText,
                  asker,
                  done: true,
                  id: ++hostSeqRef.current,
                  awaitingConfirmation: Boolean(payload.awaiting_confirmation),
                });
                // Fade the live bubble a few seconds after the answer completes.
                hostClearTimer.current = setTimeout(() => setHostAnswer(null), 8000);
              } else if (!chunk) {
                // Start-of-answer marker: reset the buffer + show "answering…".
                hostBufRef.current = "";
                setHostAnswer({ text: "", asker, done: false, id: hostSeqRef.current + 1 });
              } else {
                hostBufRef.current += chunk;
                setHostAnswer({ text: hostBufRef.current, asker, done: false, id: hostSeqRef.current + 1 });
              }
              break;
            }
            case "queue":
            case "slide":
              break;
            default:
              break;
          }
        } catch {
          /* ignore malformed frames */
        }
      };
    };

    connect();
    return () => {
      alive = false;
      socket?.close();
    };
  }, [enabled, roomId, pushReaction]);

  return {
    connected,
    presenceToast,
    floatingReactions,
    giftOverlay,
    followerCount,
    setFollowerCount,
    viewerCount,
    setViewerCount,
    hostAnswer,
    pushReaction,
  };
}
