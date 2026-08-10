"""Per-session quality telemetry for the audio translation lab.

`SessionQualityStore` records lightweight counters and gauges for every live
session: transcript volume, ASR/MT latency, Theodore reply health, phrasebook
vs source-fallback coverage, noise-gate behaviour, and viewer peaks. `snapshot`
folds those into a flat dict (>20 keys) plus a computed `quality_score_0_1` so
dashboards can show responsiveness and honesty at a glance.
"""

from __future__ import annotations

import threading
from typing import Any, Callable

from .audio_policy import AudioPolicy, get_policy


def _blank() -> dict[str, Any]:
    return {
        "transcripts_final": 0,
        "transcripts_interim": 0,
        "asr_latency_ms_sum": 0,
        "asr_latency_ms_count": 0,
        "mt_latency_ms_sum": 0,
        "mt_latency_ms_count": 0,
        "theodore_replies": 0,
        "theodore_fallback_count": 0,
        "phrasebook_hits": 0,
        "source_fallback_count": 0,
        "gate_skips": 0,
        "gate_passes": 0,
        "uploads_accepted": 0,
        "ws_viewers_peak": 0,
        "capture_window_ms_effective": 0,
        "speech_ratio_last": 0.0,
        "noise_floor_db_last": 0.0,
        "peak_db_last": 0.0,
        "end_of_turn_count": 0,
        "provider_errors": 0,
        "languages_seen": set(),
        "roles_seen": set(),
    }


class SessionQualityStore:
    def __init__(
        self, policy_provider: Callable[[], AudioPolicy] | None = None
    ) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}
        self._policy_provider = policy_provider or get_policy
        self._lock = threading.Lock()

    def _bucket(self, session_id: str) -> dict[str, Any]:
        bucket = self._sessions.get(session_id)
        if bucket is None:
            bucket = _blank()
            self._sessions[session_id] = bucket
        return bucket

    def reset(self, session_id: str | None = None) -> None:
        with self._lock:
            if session_id is None:
                self._sessions.clear()
            else:
                self._sessions.pop(session_id, None)

    def record_transcript(
        self,
        session_id: str,
        *,
        is_final: bool = True,
        end_of_turn: bool = False,
        language: str = "",
        role: str = "",
    ) -> None:
        with self._lock:
            b = self._bucket(session_id)
            if is_final:
                b["transcripts_final"] += 1
            else:
                b["transcripts_interim"] += 1
            if end_of_turn:
                b["end_of_turn_count"] += 1
            if language:
                b["languages_seen"].add(language)
            if role:
                b["roles_seen"].add(role)

    def record_asr(
        self, session_id: str, *, latency_ms: int, language: str = ""
    ) -> None:
        with self._lock:
            b = self._bucket(session_id)
            b["asr_latency_ms_sum"] += max(0, int(latency_ms))
            b["asr_latency_ms_count"] += 1
            if language:
                b["languages_seen"].add(language)

    def record_mt(
        self,
        session_id: str,
        *,
        latency_ms: int,
        provider: str = "",
        target_language: str = "",
    ) -> None:
        with self._lock:
            b = self._bucket(session_id)
            b["mt_latency_ms_sum"] += max(0, int(latency_ms))
            b["mt_latency_ms_count"] += 1
            prov = (provider or "").lower()
            if "phrasebook" in prov:
                b["phrasebook_hits"] += 1
            if "source-fallback" in prov:
                b["source_fallback_count"] += 1
            if target_language:
                b["languages_seen"].add(target_language)

    def record_theodore(
        self, session_id: str, *, latency_ms: int = 0, fallback: bool = False
    ) -> None:
        with self._lock:
            b = self._bucket(session_id)
            b["theodore_replies"] += 1
            if fallback:
                b["theodore_fallback_count"] += 1

    def record_gate(
        self,
        session_id: str,
        *,
        uploaded: bool,
        noise_floor_db: float = 0.0,
        peak_db: float = 0.0,
        speech_ratio: float = 0.0,
        window_ms: int = 0,
    ) -> None:
        with self._lock:
            b = self._bucket(session_id)
            if uploaded:
                b["gate_passes"] += 1
            else:
                b["gate_skips"] += 1
            b["noise_floor_db_last"] = float(noise_floor_db)
            b["peak_db_last"] = float(peak_db)
            b["speech_ratio_last"] = float(speech_ratio)
            if window_ms:
                b["capture_window_ms_effective"] = int(window_ms)

    def record_upload(
        self, session_id: str, *, accepted: bool, bytes_size: int = 0
    ) -> None:
        with self._lock:
            b = self._bucket(session_id)
            if accepted:
                b["uploads_accepted"] += 1
            else:
                b["provider_errors"] += 1

    def record_error(self, session_id: str, *, provider: str = "") -> None:
        with self._lock:
            self._bucket(session_id)["provider_errors"] += 1

    def record_viewers(self, session_id: str, count: int) -> None:
        with self._lock:
            b = self._bucket(session_id)
            b["ws_viewers_peak"] = max(b["ws_viewers_peak"], int(count))

    def _quality_score(self, b: dict[str, Any]) -> float:
        policy = self._policy_provider()
        p50 = max(1, policy.latency_target_p50_ms)
        p95 = max(p50 + 1, policy.latency_target_p95_ms)

        def latency_score(avg: float) -> float:
            if avg <= 0:
                return 1.0
            if avg <= p50:
                return 1.0
            if avg >= p95:
                return policy.fallback_honesty_score
            span = p95 - p50
            drop = 1.0 - policy.fallback_honesty_score
            return 1.0 - drop * (avg - p50) / span

        mt_count = b["mt_latency_ms_count"]
        mt_avg = b["mt_latency_ms_sum"] / mt_count if mt_count else 0.0
        responsiveness = latency_score(mt_avg)

        finals = b["transcripts_final"] or 1
        coverage = 1.0 - min(1.0, b["source_fallback_count"] / finals)

        components = [(responsiveness, 0.5), (coverage, 0.3)]
        if b["gate_passes"] or b["gate_skips"]:
            gate_quality = min(1.0, max(0.0, b["speech_ratio_last"] / 0.5))
            components.append((gate_quality, 0.2))
        total_w = sum(w for _, w in components)
        score = sum(v * w for v, w in components) / total_w if total_w else 1.0
        return round(max(0.0, min(1.0, score)), 3)

    def snapshot(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            b = self._bucket(session_id)
            asr_count = b["asr_latency_ms_count"]
            mt_count = b["mt_latency_ms_count"]
            snap: dict[str, Any] = {
                "session_id": session_id,
                "transcripts_final": b["transcripts_final"],
                "transcripts_interim": b["transcripts_interim"],
                "asr_latency_ms_sum": b["asr_latency_ms_sum"],
                "asr_latency_ms_count": asr_count,
                "asr_latency_ms_avg": round(b["asr_latency_ms_sum"] / asr_count, 1)
                if asr_count
                else 0.0,
                "mt_latency_ms_sum": b["mt_latency_ms_sum"],
                "mt_latency_ms_count": mt_count,
                "mt_latency_ms_avg": round(b["mt_latency_ms_sum"] / mt_count, 1)
                if mt_count
                else 0.0,
                "theodore_replies": b["theodore_replies"],
                "theodore_fallback_count": b["theodore_fallback_count"],
                "phrasebook_hits": b["phrasebook_hits"],
                "source_fallback_count": b["source_fallback_count"],
                "gate_skips": b["gate_skips"],
                "gate_passes": b["gate_passes"],
                "uploads_accepted": b["uploads_accepted"],
                "ws_viewers_peak": b["ws_viewers_peak"],
                "capture_window_ms_effective": b["capture_window_ms_effective"],
                "speech_ratio_last": round(b["speech_ratio_last"], 3),
                "noise_floor_db_last": round(b["noise_floor_db_last"], 2),
                "peak_db_last": round(b["peak_db_last"], 2),
                "end_of_turn_count": b["end_of_turn_count"],
                "provider_errors": b["provider_errors"],
                "languages_seen": sorted(b["languages_seen"]),
                "roles_seen": sorted(b["roles_seen"]),
            }
            snap["quality_score_0_1"] = self._quality_score(b)
            return snap

    def overview(self) -> dict[str, Any]:
        with self._lock:
            session_ids = list(self._sessions.keys())
        sessions = [self.snapshot(sid) for sid in session_ids]
        totals: dict[str, Any] = {
            "sessions": len(sessions),
            "transcripts_final": sum(s["transcripts_final"] for s in sessions),
            "transcripts_interim": sum(s["transcripts_interim"] for s in sessions),
            "theodore_replies": sum(s["theodore_replies"] for s in sessions),
            "phrasebook_hits": sum(s["phrasebook_hits"] for s in sessions),
            "source_fallback_count": sum(s["source_fallback_count"] for s in sessions),
            "provider_errors": sum(s["provider_errors"] for s in sessions),
            "avg_quality_score_0_1": round(
                sum(s["quality_score_0_1"] for s in sessions) / len(sessions), 3
            )
            if sessions
            else 1.0,
        }
        return {"totals": totals, "sessions": sessions}


# Shared store used by the FastAPI app.
_STORE = SessionQualityStore()


def get_store() -> SessionQualityStore:
    return _STORE
