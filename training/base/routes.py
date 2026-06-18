#!/usr/bin/env python3
"""Track B helper: turn the domain->adapter map + a class-category->domain map
into the LLM_ROUTES string consumed by RoutedLLMProvider.

Pure (operates on already-parsed dicts) so it is offline-testable; the CLI loads
training/base/domains.yaml.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict


def routes_from_domains(domains: dict, category_to_domain: Dict[str, str]) -> str:
    adapter_by_domain = {d["name"]: d["adapter"] for d in domains.get("domains", [])}
    safety_gated = {d["name"] for d in domains.get("domains", []) if d.get("safety_gated")}
    pairs = []
    for category, domain in category_to_domain.items():
        if domain in adapter_by_domain and domain not in safety_gated:
            pairs.append(f"{category}={adapter_by_domain[domain]}")
    return ",".join(pairs)


# Default class-subject -> Track B domain mapping.
DEFAULT_CATEGORY_TO_DOMAIN: Dict[str, str] = {
    "math": "stem", "science": "stem", "biology": "stem", "technology": "stem",
    "history": "humanities", "culture": "humanities", "art": "humanities",
    "language": "languages", "languages": "languages",
    "culinary": "vocational",
    "medical": "medical",  # safety_gated -> excluded from routes until reviewed
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domains", default="training/base/domains.yaml")
    args = ap.parse_args(argv)
    import yaml  # local import so the pure helper needs no yaml

    domains = yaml.safe_load(Path(args.domains).read_text(encoding="utf-8"))
    print(routes_from_domains(domains, DEFAULT_CATEGORY_TO_DOMAIN))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
