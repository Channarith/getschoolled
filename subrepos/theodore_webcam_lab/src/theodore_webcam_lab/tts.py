"""Server-side neural speech for the webcam lab (shared lab_tts)."""

from __future__ import annotations

from aoep_shared.lab_tts import (  # noqa: F401
    ProviderUnavailable,
    engine_chain,
    synthesize,
    tts_status,
)
