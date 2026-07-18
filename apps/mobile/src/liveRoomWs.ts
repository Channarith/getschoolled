import { useEffect, useRef, useState } from "react";

import { ORCHESTRATOR_URL } from "./config";
import type { LiveRoomState } from "./api";

export type LiveRoomWsMessage = {
  type: string;
  payload?: Record<string, unknown>;
};

function wsUrl(roomId: string): string {
  const base = ORCHESTRATOR_URL.replace(/\/$/, "");
  const proto = base.startsWith("https") ? "wss" : "ws";
  const host = base.replace(/^https?:\/\//, "");
  return `${proto}://${host}/api/live-rooms/${encodeURIComponent(roomId)}/ws`;
}

export type HostAnswer = {
  text: string;
  asker: string;
  done: boolean;
  id: number;
};

export function useLiveRoomSocket(
  roomId: string,
  enabled: boolean,
  onRoom: (room: LiveRoomState) => void,
) {
  const [connected, setConnected] = useState(false);
  const [presenceToast, setPresenceToast] = useState<{ kind: string; name: string } | null>(null);
  const [floatingReactions, setFloatingReactions] = useState<{ id: string; emoji: string; left: number }[]>([]);
  const [giftBanner, setGiftBanner] = useState<string>("");
  const [viewerCount, setViewerCount] = useState(0);
  const [followerCount, setFollowerCount] = useState(0);
  const [hostAnswer, setHostAnswer] = useState<HostAnswer | null>(null);
  const hostBufRef = useRef("");
  const hostSeqRef = useRef(0);
  const hostClearTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onRoomRef = useRef(onRoom);
  onRoomRef.current = onRoom;

  const pushReaction = (emoji: string) => {
    const id = `${Date.now()}-${Math.random()}`;
    const left = 10 + Math.random() * 70;
    setFloatingReactions((prev) => [...prev.slice(-10), { id, emoji, left }]);
    setTimeout(() => {
      setFloatingReactions((prev) => prev.filter((r) => r.id !== id));
    }, 2200);
  };

  useEffect(() => {
    if (!enabled || !roomId) return;
    let alive = true;
    let socket: WebSocket | null = null;
    let retryMs = 2000;

    const connect = () => {
      if (!alive) return;
      try {
        socket = new WebSocket(wsUrl(roomId));
      } catch {
        setConnected(false);
        setTimeout(connect, retryMs);
        retryMs = Math.min(retryMs * 1.5, 9000);
        return;
      }
      socket.onopen = () => {
        setConnected(true);
        retryMs = 2000;
      };
      socket.onclose = () => {
        setConnected(false);
        if (alive) setTimeout(connect, retryMs);
        retryMs = Math.min(retryMs * 1.5, 9000);
      };
      socket.onmessage = (ev) => {
        try {
          const msg = JSON.parse(String(ev.data)) as LiveRoomWsMessage;
          const payload = msg.payload ?? {};
          if (msg.type === "room" && payload.room) {
            onRoomRef.current(payload.room as LiveRoomState);
          } else if (msg.type === "reaction") {
            const reaction = payload.reaction as { emoji?: string } | undefined;
            if (reaction?.emoji) pushReaction(reaction.emoji);
          } else if (msg.type === "gift") {
            const gift = payload.gift as { emoji?: string; sender_name?: string; gift_name?: string } | undefined;
            if (gift?.emoji) {
              setGiftBanner(
                `${gift.emoji} ${gift.sender_name ?? "Someone"} sent ${gift.gift_name ?? "a gift"}`,
              );
              setTimeout(() => setGiftBanner(""), 3000);
            }
          } else if (msg.type === "presence") {
            const toast = payload.toast as { kind?: string; name?: string } | undefined;
            if (toast?.name) {
              setPresenceToast({ kind: toast.kind ?? "join", name: toast.name });
              setTimeout(() => setPresenceToast(null), 2500);
            }
            if (typeof payload.viewer_count === "number") {
              setViewerCount(payload.viewer_count as number);
            }
          } else if (msg.type === "follow" && typeof payload.follower_count === "number") {
            setFollowerCount(payload.follower_count as number);
          } else if (msg.type === "host_delta") {
            const asker = (payload.asker as string) || "";
            const chunk = (payload.text as string) || "";
            const done = Boolean(payload.done);
            if (hostClearTimer.current) {
              clearTimeout(hostClearTimer.current);
              hostClearTimer.current = null;
            }
            if (done) {
              const finalMsg = payload.message as { text?: string } | null | undefined;
              const finalText = (finalMsg?.text || hostBufRef.current || "")
                .replace(/^@\S+\s*/, "")
                .trim();
              hostBufRef.current = "";
              setHostAnswer({ text: finalText, asker, done: true, id: ++hostSeqRef.current });
              hostClearTimer.current = setTimeout(() => setHostAnswer(null), 8000);
            } else if (!chunk) {
              hostBufRef.current = "";
              setHostAnswer({ text: "", asker, done: false, id: hostSeqRef.current + 1 });
            } else {
              hostBufRef.current += chunk;
              setHostAnswer({ text: hostBufRef.current, asker, done: false, id: hostSeqRef.current + 1 });
            }
          }
        } catch {
          /* ignore */
        }
      };
    };

    connect();
    return () => {
      alive = false;
      socket?.close();
    };
  }, [enabled, roomId]);

  return {
    connected,
    presenceToast,
    floatingReactions,
    giftBanner,
    viewerCount,
    setViewerCount,
    followerCount,
    setFollowerCount,
    hostAnswer,
    pushReaction,
  };
}
