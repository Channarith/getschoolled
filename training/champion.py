#!/usr/bin/env python3
"""Champion model pointer (the bake-off winner the serving layer points at).

A tiny JSON-persisted registry: the bake-off `promote`s a winner, the served
LLMProvider reads `current()` to know which model/adapter to serve, and `revert`
rolls the pointer back to the previous (or a named) prior champion. This is the
serving-side complement of the runtime OptimizationLedger.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class ChampionRegistry:
    path: Path

    def _load(self) -> Dict:
        p = Path(self.path)
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
        return {"champion": None, "metrics": {}, "history": []}

    def _save(self, data: Dict) -> None:
        p = Path(self.path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def current(self) -> Optional[str]:
        return self._load().get("champion")

    def current_metrics(self) -> Dict:
        return self._load().get("metrics", {})

    def history(self) -> List[Dict]:
        return self._load().get("history", [])

    def promote(self, name: str, metrics: Optional[Dict] = None) -> Dict:
        data = self._load()
        data["history"].append({"name": name, "metrics": metrics or {}, "ts": time.time()})
        data["champion"] = name
        data["metrics"] = metrics or {}
        self._save(data)
        return data

    def revert(self, name: Optional[str] = None) -> Dict:
        """Roll the champion back to a named prior entry, or the previous one."""
        data = self._load()
        hist = data["history"]
        if name is not None:
            match = [h for h in hist if h["name"] == name]
            if not match:
                raise KeyError(f"no prior champion named {name!r}")
            target = match[-1]
        else:
            if len(hist) < 2:
                raise KeyError("no previous champion to revert to")
            target = hist[-2]
        data["champion"] = target["name"]
        data["metrics"] = target.get("metrics", {})
        data["history"].append({**target, "ts": time.time(), "reverted": True})
        self._save(data)
        return data


def served_model(champion_path: Optional[str], default: str) -> str:
    """The model the serving layer should use: the champion if set, else default."""
    if champion_path and Path(champion_path).is_file():
        name = ChampionRegistry(Path(champion_path)).current()
        if name:
            return name
    return default
