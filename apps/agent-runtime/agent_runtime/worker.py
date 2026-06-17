"""LiveKit Agents worker entrypoint.

The worker joins a LiveKit room and runs the STT -> LLM -> TTS teaching loop,
driven by the orchestrator's Director. Connecting to LiveKit requires a running
media server (provided by infra/compose), so this module is structured so its
pure logic is importable and unit-testable without a server. Full LiveKit
wiring lands in phase1/phase2.
"""

from __future__ import annotations

from dataclasses import dataclass

from eduplatform_shared.config import get_settings
from eduplatform_shared.factory import get_provider_factory


@dataclass
class WorkerConfig:
    livekit_url: str
    room: str
    deploy_mode: str


def build_config(room: str = "demo-class") -> WorkerConfig:
    settings = get_settings()
    return WorkerConfig(
        livekit_url=settings.livekit_url,
        room=room,
        deploy_mode=settings.deploy_mode.value,
    )


def narrate(text: str) -> bytes:
    """Render narration audio via the configured SpeechProvider (TTS)."""
    return get_provider_factory().speech().synthesize(text)


def answer(question: str, context: str = "") -> str:
    """Tutor reply via the configured LLMProvider (used by the room loop)."""
    prompt = f"QUESTION: {question}\nCONTEXT: {context}" if context else question
    return get_provider_factory().llm().complete(prompt)


def main() -> None:  # pragma: no cover - requires a live LiveKit server
    cfg = build_config()
    raise SystemExit(
        "agent-runtime requires a running LiveKit server "
        f"({cfg.livekit_url}); start infra/compose first."
    )


if __name__ == "__main__":  # pragma: no cover
    main()
