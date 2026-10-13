"""RAG lab facade for the shared CosyVoice voice-training queue."""

from __future__ import annotations

import threading
from typing import Optional

from aoep_shared.cosyvoice_ingest.queue import (
    VoiceQueueBusy,
    assert_queue_free,
    catalog_summary,
    clear_stop,
    execute_queue,
    read_status,
    request_stop,
    resolve_paths,
)

_SERVICE: Optional["VoiceQueueService"] = None
_GUARD = threading.Lock()


class VoiceQueueService:
    """Background runner. The shell CLI uses the same status file and stop flag."""

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def snapshot(self) -> dict:
        paths = resolve_paths()
        summary = catalog_summary(
            paths["catalog"], paths["urls_root"], paths["output_root"]
        )
        summary["queue"] = read_status(paths["output_root"])
        summary["cli"] = (
            "python3 scripts/cosyvoice_batch_ingest.py --pool <ids> --workers 2 --max-urls 2"
        )
        return summary

    def start(
        self,
        *,
        pools: list[str],
        workers: int,
        max_urls: Optional[int],
        max_channels: Optional[int],
        include_news: bool,
        min_videos: int,
    ) -> dict:
        with _GUARD:
            if self._thread is not None and self._thread.is_alive():
                raise VoiceQueueBusy("voice queue is already running in this lab")
            paths = resolve_paths()
            assert_queue_free(paths["output_root"])
            clear_stop(paths["output_root"])
            self._stop = threading.Event()
            chosen = {item.strip() for item in pools if item and item.strip()} or None
            self._thread = threading.Thread(
                target=self._run,
                kwargs={
                    "paths": paths,
                    "pools": chosen,
                    "workers": workers,
                    "max_urls": max_urls,
                    "max_channels": max_channels,
                    "include_news": include_news,
                    "min_videos": min_videos,
                    "stop_event": self._stop,
                },
                daemon=True,
                name="rag-voice-queue",
            )
            self._thread.start()
        return self.snapshot()

    def _run(self, *, paths: dict, stop_event: threading.Event, pools, **kwargs) -> None:
        import aoep_shared.cosyvoice_ingest.queue as queue_mod

        execute_queue(
            catalog_path=paths["catalog"],
            urls_root=paths["urls_root"],
            output_root=paths["output_root"],
            cosyvoice_repo=paths["cosyvoice_repo"],
            ingest_script=paths["ingest_script"],
            pools=pools,
            stop_event=stop_event,
            run_channel=queue_mod.ingest_channel,
            **kwargs,
        )

    def stop(self) -> dict:
        self._stop.set()
        paths = resolve_paths()
        request_stop(paths["output_root"])
        return self.snapshot()


def get_voice_queue() -> VoiceQueueService:
    global _SERVICE
    with _GUARD:
        if _SERVICE is None:
            _SERVICE = VoiceQueueService()
        return _SERVICE


def reset_voice_queue() -> None:
    """Test helper. Does not kill a queue that is still ingesting."""
    global _SERVICE
    with _GUARD:
        _SERVICE = None
