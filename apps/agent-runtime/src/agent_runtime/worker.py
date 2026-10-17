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
    import os

    config = load_config()
    livekit_url = (os.environ.get("LIVEKIT_URL") or "").strip()
    if not livekit_url:
        raise SystemExit(
            "Salareen hosts the class. Zoom, Teams, and Meet stay pasted join "
            "links. Set LIVEKIT_URL when this worker should join a Salareen room."
        )
    try:
        from livekit.agents import WorkerOptions, cli  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "livekit-agents is not installed. Install the 'livekit' extra to run "
            "the media worker: pip install 'aoep-agent-runtime[livekit]'. The "
            f"teaching brain itself runs without it. ({exc})"
        )
    if not callable(getattr(cli, "run_app", None)):
        raise SystemExit("livekit-agents is installed without cli.run_app")

    async def entrypoint(ctx):  # noqa: ANN001
        _ = (ctx, config, build_brain)

    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))


if __name__ == "__main__":  # pragma: no cover
    main()
