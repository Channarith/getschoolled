"""In-memory realtime translation hub with per-viewer language delivery."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from fastapi import WebSocket

from .languages import normalize_language
from .models import (
    AudienceRole,
    SessionConfig,
    SessionSnapshot,
    SessionUpdate,
    TranscriptInput,
    TranslationEvent,
)
from .providers import TranslationEngine


@dataclass(eq=False)
class Connection:
    websocket: WebSocket
    role: AudienceRole
    target_language: str
    participant_id: str


@dataclass
class LiveSession:
    config: SessionConfig
    history: list[TranslationEvent] = field(default_factory=list)
    sequence: int = 0
    created_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    connections: list[Connection] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def snapshot(self) -> SessionSnapshot:
        connected: dict[str, int] = {}
        for conn in self.connections:
            key = conn.role.value
            connected[key] = connected.get(key, 0) + 1
        return SessionSnapshot(
            config=self.config,
            connected=connected,
            history=list(self.history),
            sequence=self.sequence,
            created_at_ms=self.created_at_ms,
        )


class TranslationHub:
    def __init__(self, translator: TranslationEngine | None = None) -> None:
        self.translator = translator or TranslationEngine()
        self._sessions: dict[str, LiveSession] = {}
        self._sessions_lock = asyncio.Lock()

    async def create(self, config: SessionConfig) -> SessionSnapshot:
        normalized = config.normalized()
        async with self._sessions_lock:
            if normalized.session_id in self._sessions:
                raise ValueError(f"session already exists: {normalized.session_id}")
            live = LiveSession(config=normalized)
            self._sessions[normalized.session_id] = live
            return live.snapshot()

    async def get_or_create(
        self,
        session_id: str,
        *,
        source_language: str = "en",
        target_language: str = "en",
    ) -> LiveSession:
        async with self._sessions_lock:
            live = self._sessions.get(session_id)
            if live is None:
                config = SessionConfig(
                    session_id=session_id,
                    source_language=source_language,
                    target_languages=[target_language],
                ).normalized()
                live = LiveSession(config=config)
                self._sessions[session_id] = live
            return live

    async def snapshot(self, session_id: str) -> SessionSnapshot | None:
        live = self._sessions.get(session_id)
        return live.snapshot() if live else None

    async def configure(
        self, session_id: str, update: SessionUpdate
    ) -> SessionSnapshot:
        """Change source/targets while a stream stays connected."""
        live = self._sessions.get(session_id)
        if live is None:
            raise KeyError(session_id)
        changes = update.model_dump(exclude_none=True)
        proposed = live.config.model_copy(update=changes).normalized()
        async with live.lock:
            live.config = proposed
        snapshot = live.snapshot()
        await self._broadcast_config(live)
        return snapshot

    async def register(
        self,
        session_id: str,
        websocket: WebSocket,
        *,
        role: AudienceRole,
        target_language: str,
        participant_id: str,
        source_language: str = "en",
    ) -> Connection:
        target = normalize_language(target_language)
        if not target:
            raise ValueError(f"unsupported target language: {target_language}")
        live = await self.get_or_create(
            session_id,
            source_language=source_language,
            target_language=target,
        )
        conn = Connection(websocket, role, target, participant_id)
        async with live.lock:
            live.connections.append(conn)
            history = [
                e.model_dump(mode="json")
                for e in live.history
                if e.target_language == target or role is AudienceRole.SPEAKER
            ]
        await websocket.send_json(
            {
                "type": "connected",
                "session": live.snapshot().model_dump(mode="json"),
                "history": history,
                "your_role": role.value,
                "your_language": target,
            }
        )
        await self._broadcast_presence(live)
        return conn

    async def unregister(self, session_id: str, conn: Connection) -> None:
        live = self._sessions.get(session_id)
        if not live:
            return
        async with live.lock:
            if conn in live.connections:
                live.connections.remove(conn)
        await self._broadcast_presence(live)

    async def process_transcript(
        self,
        session_id: str,
        item: TranscriptInput,
    ) -> list[TranslationEvent]:
        live = await self.get_or_create(
            session_id,
            source_language=item.source_language or "en",
            target_language="en",
        )
        source = normalize_language(item.source_language, live.config.source_language)
        if not source:
            raise ValueError("unsupported transcript source language")

        async with live.lock:
            targets = list(live.config.target_languages)
            for conn in live.connections:
                if conn.target_language not in targets:
                    targets.append(conn.target_language)
            live.sequence += 1
            sequence = live.sequence

        # Interim text is sent immediately in source language; translating every
        # partial token would be expensive and flickery. Sessions can opt in.
        if not item.is_final and not live.config.translate_interim:
            event = TranslationEvent(
                session_id=session_id,
                sequence=sequence,
                speaker_id=item.speaker_id,
                source_text=item.text,
                source_language=source,
                target_language=source,
                translated_text=item.text,
                is_final=False,
                confidence=item.confidence,
                asr_provider=item.asr_provider,
                translation_provider="interim-source",
            )
            await self._broadcast_events(live, [event])
            return [event]

        started = time.time()
        results = await asyncio.gather(
            *[
                asyncio.to_thread(self.translator.translate, item.text, source, target)
                for target in targets
            ]
        )
        total_ms = int((time.time() - started) * 1000)
        events = [
            TranslationEvent(
                session_id=session_id,
                sequence=sequence,
                speaker_id=item.speaker_id,
                source_text=item.text,
                source_language=source,
                target_language=result.target_language,
                translated_text=result.text,
                is_final=item.is_final,
                confidence=item.confidence,
                asr_provider=item.asr_provider,
                translation_provider=result.provider,
                warning=result.warning,
                latency_ms=total_ms,
            )
            for result in results
        ]
        async with live.lock:
            live.history.extend(events)
            if len(live.history) > live.config.max_history:
                live.history = live.history[-live.config.max_history :]
        await self._broadcast_events(live, events)
        return events

    async def _broadcast_events(
        self, live: LiveSession, events: list[TranslationEvent]
    ) -> None:
        dead: list[Connection] = []
        for conn in list(live.connections):
            visible = [
                event
                for event in events
                if (
                    event.target_language == conn.target_language
                    or conn.role is AudienceRole.SPEAKER
                    or not event.is_final
                )
            ]
            if not visible:
                continue
            try:
                await conn.websocket.send_json(
                    {
                        "type": "translation",
                        "events": [e.model_dump(mode="json") for e in visible],
                    }
                )
            except Exception:  # noqa: BLE001 — disconnect cleanup
                dead.append(conn)
        if dead:
            async with live.lock:
                for conn in dead:
                    if conn in live.connections:
                        live.connections.remove(conn)

    async def _broadcast_config(self, live: LiveSession) -> None:
        payload = {
            "type": "config",
            "config": live.config.model_dump(mode="json"),
        }
        dead: list[Connection] = []
        for conn in list(live.connections):
            try:
                await conn.websocket.send_json(payload)
            except Exception:  # noqa: BLE001
                dead.append(conn)
        if dead:
            async with live.lock:
                for conn in dead:
                    if conn in live.connections:
                        live.connections.remove(conn)

    async def _broadcast_presence(self, live: LiveSession) -> None:
        payload = {
            "type": "presence",
            "connected": live.snapshot().connected,
        }
        dead: list[Connection] = []
        for conn in list(live.connections):
            try:
                await conn.websocket.send_json(payload)
            except Exception:  # noqa: BLE001
                dead.append(conn)
        if dead:
            async with live.lock:
                for conn in dead:
                    if conn in live.connections:
                        live.connections.remove(conn)
