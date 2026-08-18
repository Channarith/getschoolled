"""Hours-a-day RAG bakeoff loop with OptimizationLedger promote/revert."""

from __future__ import annotations

import argparse
import json
import random
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from .eval_harness import (
    evaluate_index,
    load_curriculum_index,
    load_golden,
    sweep_presets,
)
from .quality_telemetry import RagTelemetryStore
from .rag_tuning import PRESETS, RagTuning

try:
    from aoep_shared.optimization import OptimizationLedger
except Exception:  # noqa: BLE001
    OptimizationLedger = None  # type: ignore


@dataclass
class TrainStatus:
    running: bool = False
    started_at: float = 0.0
    target_hours: float = 0.0
    rounds_done: int = 0
    last_error: str = ""
    champion: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RagBakeoffRunner:
    """Continuous knob sweep that promotes non-regressing champions."""

    def __init__(self) -> None:
        self.tuning = RagTuning.from_env()
        self.telemetry = RagTelemetryStore()
        self.index = load_curriculum_index()
        self.examples = load_golden()
        self.ledger = (
            OptimizationLedger(primary_metric="rag_quality", higher_is_better=True)
            if OptimizationLedger is not None
            else None
        )
        self._status = TrainStatus()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        # Seed champion from balanced eval.
        self._seed_champion()

    def _seed_champion(self) -> None:
        report = evaluate_index(self.index, self.examples, self.tuning)
        payload = {
            "tuning": self.tuning.to_dict(),
            "report": report.to_dict(),
            "source": "seed",
        }
        self.telemetry.record_eval(report.to_dict())
        self.telemetry.set_champion(payload)
        self._status.champion = payload
        if self.ledger is not None:
            step = self.ledger.commit("rag", self.tuning.to_dict(), report.to_dict())
            self.ledger.promote_if_better(step)

    def status(self) -> dict[str, Any]:
        with self._lock:
            out = self._status.to_dict()
        out["telemetry"] = self.telemetry.snapshot()
        return out

    def evaluate_once(self, *, include_details: bool = False) -> dict[str, Any]:
        report = evaluate_index(
            self.index, self.examples, self.tuning, include_details=include_details
        )
        self.telemetry.record_eval(report.to_dict())
        return report.to_dict()

    def sweep(self) -> list[dict[str, Any]]:
        return sweep_presets(self.index, self.examples)

    def _candidate_tuning(self, rng: random.Random) -> RagTuning:
        """Mutate knobs lightly or pick a named preset."""
        if rng.random() < 0.35:
            name = rng.choice(list(PRESETS.keys()))
            return RagTuning.preset(name)
        base = self.tuning.to_dict()
        base["top_k"] = max(1, min(8, int(base["top_k"]) + rng.choice([-1, 0, 1])))
        base["min_score"] = round(
            max(0.0, min(0.2, float(base["min_score"]) + rng.choice([-0.01, 0.0, 0.01]))),
            4,
        )
        base["groundedness_pass"] = round(
            max(0.3, min(0.95, float(base["groundedness_pass"]) + rng.choice([-0.05, 0.0, 0.05]))),
            4,
        )
        base["groundedness_support"] = round(
            max(0.2, min(0.8, float(base["groundedness_support"]) + rng.choice([-0.05, 0.0, 0.05]))),
            4,
        )
        base["max_context_chars"] = max(
            400, min(4000, int(base["max_context_chars"]) + rng.choice([-200, 0, 200]))
        )
        return RagTuning(**base)

    def run_round(self, *, seed: Optional[int] = None) -> dict[str, Any]:
        rng = random.Random(seed if seed is not None else time.time_ns())
        candidate = self._candidate_tuning(rng)
        report = evaluate_index(self.index, self.examples, candidate)
        self.telemetry.record_eval(report.to_dict())
        promoted = False
        if self.ledger is not None:
            step = self.ledger.commit("rag", candidate.to_dict(), report.to_dict())
            promoted = self.ledger.promote_if_better(step)
            if promoted:
                self.tuning = candidate
                champ = self.ledger.champion("rag")
                payload = {
                    "tuning": candidate.to_dict(),
                    "report": report.to_dict(),
                    "step_id": champ.step_id if champ else "",
                    "source": "bakeoff",
                }
                self.telemetry.set_champion(payload)
                with self._lock:
                    self._status.champion = payload
        else:
            # Offline fallback without ledger: keep if quality improves.
            current = float(self._status.champion.get("report", {}).get("rag_quality") or 0.0)
            if report.rag_quality >= current:
                promoted = True
                self.tuning = candidate
                payload = {
                    "tuning": candidate.to_dict(),
                    "report": report.to_dict(),
                    "source": "bakeoff_no_ledger",
                }
                self.telemetry.set_champion(payload)
                with self._lock:
                    self._status.champion = payload
        self.telemetry.record_bakeoff_round(promoted=promoted)
        with self._lock:
            self._status.rounds_done += 1
        return {
            "promoted": promoted,
            "tuning": candidate.to_dict(),
            "report": report.to_dict(),
        }

    def _loop(self, target_hours: float) -> None:
        started = time.time()
        rounds_per_hour = max(1, int(self.tuning.bakeoff_rounds_per_hour))
        target_rounds = max(1, int(float(target_hours) * rounds_per_hour))
        # Keep CI/dev responsive: never exceed 200 background rounds per start.
        target_rounds = min(target_rounds, 200)
        sleep_s = 0.01
        try:
            while not self._stop.is_set() and self._status.rounds_done < target_rounds:
                self.run_round()
                sim_h = self._status.rounds_done / float(rounds_per_hour)
                self.telemetry.record_hours(sim_h)
                # Wall-clock safety valve (avoid runaway if rounds_per_hour is huge).
                if (time.time() - started) > max(30.0, float(target_hours) * 120.0):
                    break
                if sleep_s:
                    self._stop.wait(sleep_s)
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self._status.last_error = str(exc)
        finally:
            with self._lock:
                self._status.running = False

    def start(self, *, hours: float = 1.0) -> dict[str, Any]:
        with self._lock:
            if self._status.running:
                return self.status()
            self._stop.clear()
            self._status = TrainStatus(
                running=True,
                started_at=time.time(),
                target_hours=float(hours),
                rounds_done=0,
                champion=dict(self._status.champion),
            )
        self._thread = threading.Thread(
            target=self._loop, args=(float(hours),), name="rag-bakeoff", daemon=True
        )
        self._thread.start()
        return self.status()

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=5.0)
        with self._lock:
            self._status.running = False
        return self.status()

    def run_blocking(self, *, hours: float = 0.01) -> dict[str, Any]:
        """Synchronous short bakeoff for CLI/CI (no background thread)."""
        # Refuse to share the singleton's status block with a live background
        # run — resetting running/rounds_done/target_hours mid-run clobbered
        # it (status reported "not running" while the thread kept looping).
        thread = self._thread
        if thread and thread.is_alive():
            raise RuntimeError("a background training run is active — stop it first")
        target_rounds = max(1, int(float(hours) * max(1, self.tuning.bakeoff_rounds_per_hour)))
        # Cap for safety in tests.
        target_rounds = min(target_rounds, 50)
        with self._lock:
            self._status.running = True
            self._status.target_hours = float(hours)
            self._status.rounds_done = 0
            self._status.started_at = time.time()
        try:
            for i in range(target_rounds):
                self.run_round(seed=i + 1)
            self.telemetry.record_hours(float(hours))
        finally:
            with self._lock:
                self._status.running = False
        return self.status()


_RUNNER: Optional[RagBakeoffRunner] = None


def get_runner() -> RagBakeoffRunner:
    global _RUNNER
    if _RUNNER is None:
        _RUNNER = RagBakeoffRunner()
    return _RUNNER


def cli_main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="RAG hours-a-day auto-tune bakeoff")
    parser.add_argument("--hours", type=float, default=0.01, help="Simulated training hours")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    runner = RagBakeoffRunner()
    result = runner.run_blocking(hours=args.hours)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        champ = result.get("champion") or {}
        report = (champ.get("report") or {})
        print(
            f"rag-bakeoff hours={args.hours} rounds={result.get('rounds_done')} "
            f"quality={report.get('rag_quality')} recall={report.get('recall_at_k')}"
        )
        tel = result.get("telemetry") or {}
        print(
            f"  promotions={tel.get('promotions')} rejections={tel.get('rejections')} "
            f"avg_quality={tel.get('avg_rag_quality')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(cli_main())
