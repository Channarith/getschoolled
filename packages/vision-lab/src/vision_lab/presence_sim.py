"""Replay lab presence reports against a local orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Iterable
import urllib.error
import urllib.request

from .group_loop import GroupPresenceReport


class PresenceReplayError(RuntimeError):
    """Raised when a presence replay request fails."""


@dataclass(frozen=True)
class ReplayResponse:
    path: str
    status: int
    body: dict


class OrchestratorPresenceReplayer:
    """Small stdlib client for terminal-driven presence experiments."""

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url.rstrip("/")

    def post(self, report: GroupPresenceReport) -> ReplayResponse:
        path = report.endpoint_path()
        body = json.dumps(report.payload()).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            resp = urllib.request.urlopen(req, timeout=15)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise PresenceReplayError(f"presence replay HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise PresenceReplayError(f"presence replay unreachable: {exc.reason}") from exc
        return ReplayResponse(
            path=path,
            status=getattr(resp, "status", 200),
            body=json.loads(resp.read().decode("utf-8") or "{}"),
        )

    def replay(self, reports: Iterable[GroupPresenceReport]) -> list[ReplayResponse]:
        return [self.post(report) for report in reports]
