"""In-process WebSocket hub for Salareen live rooms."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class LiveRoomConnectionHub:
    """Broadcast live-room events to connected WebSocket clients."""

    def __init__(self) -> None:
        self._rooms: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, room_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._rooms.setdefault(room_id, set()).add(websocket)

    async def disconnect(self, room_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            bucket = self._rooms.get(room_id)
            if bucket is None:
                return
            bucket.discard(websocket)
            if not bucket:
                self._rooms.pop(room_id, None)

    async def broadcast(self, room_id: str, event: Dict[str, Any]) -> None:
        payload = json.dumps(event, separators=(",", ":"))
        async with self._lock:
            sockets: List[WebSocket] = list(self._rooms.get(room_id, set()))
        dead: List[WebSocket] = []
        for ws in sockets:
            try:
                await ws.send_text(payload)
            except Exception as exc:  # noqa: BLE001
                logger.debug("live room ws send failed (%s)", exc)
                dead.append(ws)
        if dead:
            async with self._lock:
                bucket = self._rooms.get(room_id)
                if bucket:
                    for ws in dead:
                        bucket.discard(ws)

    def connection_count(self, room_id: str) -> int:
        return len(self._rooms.get(room_id, set()))
