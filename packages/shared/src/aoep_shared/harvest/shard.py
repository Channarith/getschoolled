"""Deterministic shard assignment so several machines never harvest the same source.

A source is owned by exactly one machine, chosen by hashing its HOST into a fixed
number of virtual shards and giving each machine a contiguous block of virtual
shards in proportion to its weight. Hashing the host (not the URL) keeps every page
of one site on one machine, so the per-host politeness limit (HARVEST_MAX_RPS) is
not multiplied by the number of machines.

Config (JSON), default config/harvest_shards.json:
  {"virtual_shards": 256,
   "machines": {"spark": {"weight": 1}, "kalel": {"weight": 3}, "mac": {"weight": 1}}}

Pure and offline-testable: no network, no clock, no randomness.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlsplit

DEFAULT_VIRTUAL_SHARDS = 256
DEFAULT_CONFIG_PATH = "config/harvest_shards.json"


def host_key(url: str) -> str:
    """Normalized host used for sharding ('www.' dropped, lower-case, no port)."""
    raw = (url or "").strip()
    parts = urlsplit(raw if "://" in raw else f"//{raw}")
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    # Sources without a host (local files, ids) shard by their whole string.
    return host or raw.lower()


def virtual_shard(url: str, virtual_shards: int = DEFAULT_VIRTUAL_SHARDS) -> int:
    digest = hashlib.sha256(host_key(url).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % virtual_shards


@dataclass(frozen=True)
class ShardMap:
    """Maps virtual shards to machine names by weight (contiguous blocks)."""

    virtual_shards: int
    owners: tuple  # owners[i] = machine name owning virtual shard i

    @classmethod
    def build(
        cls, machines: Dict[str, float], virtual_shards: int = DEFAULT_VIRTUAL_SHARDS
    ) -> "ShardMap":
        if not machines:
            raise ValueError("at least one machine is required")
        if virtual_shards < len(machines):
            raise ValueError("virtual_shards must be >= number of machines")
        names = sorted(machines)  # sorted: the map must not depend on dict order
        weights = [float(machines[n]) for n in names]
        if any(w <= 0 for w in weights):
            raise ValueError("every machine weight must be > 0")
        total = sum(weights)
        # Largest-remainder allocation: exact total, every machine gets >= 1 shard.
        raw = [w / total * virtual_shards for w in weights]
        counts = [max(1, int(r)) for r in raw]
        while sum(counts) > virtual_shards:
            counts[counts.index(max(counts))] -= 1
        remainders = sorted(
            range(len(names)), key=lambda i: (raw[i] - int(raw[i]), -i), reverse=True
        )
        i = 0
        while sum(counts) < virtual_shards:
            counts[remainders[i % len(names)]] += 1
            i += 1
        owners: List[str] = []
        for name, n in zip(names, counts):
            owners.extend([name] * n)
        return cls(virtual_shards=virtual_shards, owners=tuple(owners))

    @classmethod
    def from_config(cls, data: dict) -> "ShardMap":
        machines = {
            name: float((cfg or {}).get("weight", 1))
            for name, cfg in (data.get("machines") or {}).items()
        }
        return cls.build(machines, int(data.get("virtual_shards", DEFAULT_VIRTUAL_SHARDS)))

    @classmethod
    def load(cls, path: Optional[str] = None) -> "ShardMap":
        p = Path(path or os.environ.get("HARVEST_SHARD_CONFIG") or DEFAULT_CONFIG_PATH)
        return cls.from_config(json.loads(p.read_text(encoding="utf-8")))

    def owner(self, url: str) -> str:
        return self.owners[virtual_shard(url, self.virtual_shards)]

    def machines(self) -> List[str]:
        return sorted(set(self.owners))

    def share(self) -> Dict[str, float]:
        return {m: self.owners.count(m) / self.virtual_shards for m in self.machines()}


@dataclass(frozen=True)
class ShardFilter:
    """'Is this URL mine?' for one machine. A filter with no map owns everything."""

    shard_map: Optional[ShardMap] = None
    machine: str = ""

    def owns(self, url: str) -> bool:
        if self.shard_map is None:
            return True
        return self.shard_map.owner(url) == self.machine

    @classmethod
    def from_env(cls) -> "ShardFilter":
        """HARVEST_MACHINE=spark|kalel|mac selects this machine; unset = unsharded."""
        machine = (os.environ.get("HARVEST_MACHINE") or "").strip().lower()
        if not machine:
            return cls()
        shard_map = ShardMap.load()
        if machine not in shard_map.machines():
            raise ValueError(
                f"HARVEST_MACHINE={machine!r} is not in the shard map {shard_map.machines()}"
            )
        return cls(shard_map, machine)
