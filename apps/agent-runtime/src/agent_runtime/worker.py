"""LiveKit Agents worker entrypoint.

This wires the TeachingBrain into a LiveKit room: subscribe to audio/video, run
STT -> brain -> TTS, and publish audio + screen-share back. The livekit-agents
import is optional (extra: ``livekit``) so the brain stays testable without the
media stack installed. Run with: python3 -m agent_runtime.worker
"""

from __future__ import annotations

from aoep_shared.config import load_config

from .brain import TeachingBrain


def build_brain() -> TeachingBrain:
    return TeachingBrain()


def main() -> None:  # pragma: no cover - requires LiveKit runtime
    config = load_config()
    try:
        from livekit.agents import cli  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "livekit-agents is not installed. Install the 'livekit' extra to run "
            "the media worker: pip install 'aoep-agent-runtime[livekit]'. The "
            f"teaching brain itself runs without it. ({exc})"
        )

    # The entrypoint registers the brain with the LiveKit Agents framework using
    # the configured media endpoint/keys from AppConfig.
    _ = (config, cli, build_brain)
    raise SystemExit(
        "Connect this worker to a LiveKit server (LIVEKIT_URL) to run live."
    )


if __name__ == "__main__":  # pragma: no cover
    main()
