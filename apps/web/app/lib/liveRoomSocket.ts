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
  emoji: string;
  label: string;
};

function wsUrl(roomId: string): string {
  const base = ORCHESTRATOR_URL.replace(/\/$/, "");
  const proto = base.startsWith("https") ? "wss" : "ws";
  const host = base.replace(/^https?:\/\//, "");
  return `${proto}://${host}/api/live-rooms/${encodeURIComponent(roomId)}/ws`;
}

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
              const gift = payload.gift as { emoji?: string; gift_name?: string; sender_name?: string } | undefined;
              if (gift?.emoji) {
                setGiftOverlay({
                  id: `${Date.now()}`,
                  emoji: gift.emoji,
                  label: `${gift.sender_name ?? "Someone"} sent ${gift.gift_name ?? "a gift"}`,
                });
                window.setTimeout(() => setGiftOverlay(null), 3200);
              }
              break;
            }
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
    pushReaction,
  };
}
