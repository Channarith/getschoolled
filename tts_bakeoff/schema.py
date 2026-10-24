"""Load and validate candidates.yaml, and decide what is shippable.

A candidate is shippable only when BOTH the code and the weights are explicitly "yes" for
commercial use and the training data is not "no". "unverified" never counts as yes.
"""
from __future__ import annotations

from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
CANDIDATES_PATH = HERE / "candidates.yaml"

COMMERCIAL = {"yes", "no", "unverified"}
ROLES = {"product", "candidate", "incumbent", "reference", "excluded", "ceiling"}
KINDS = {"open", "cloud"}


def load(path: Path | str = CANDIDATES_PATH) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def candidates(path: Path | str = CANDIDATES_PATH) -> dict[str, dict]:
    return {c["id"]: c for c in load(path)["candidates"]}


def shippable(c: dict) -> bool:
    lic = c.get("license", {})
    return (
        lic.get("code", {}).get("commercial_ok") == "yes"
        and lic.get("weights", {}).get("commercial_ok") == "yes"
        and lic.get("training_data", {}).get("commercial_ok") != "no"
    )


def label(c: dict) -> str:
    """Short text for reports: SHIPPABLE, CHECK LICENSE (open questions), or NOT SHIPPABLE."""
    if shippable(c):
        return "SHIPPABLE"
    lic = c.get("license", {})
    if "no" in (lic.get("weights", {}).get("commercial_ok"), lic.get("code", {}).get("commercial_ok"), lic.get("training_data", {}).get("commercial_ok")):
        return "NOT SHIPPABLE"
    return "CHECK LICENSE"


def covers(c: dict, lang: str) -> bool:
    return lang in [str(x) for x in c.get("languages", [])]


def validate(data: dict) -> list[str]:
    """Return a list of problems; empty means the matrix is valid."""
    problems: list[str] = []
    if data.get("version") != 1:
        problems.append("version must be 1")
    seen: set[str] = set()
    for c in data.get("candidates", []):
        cid = c.get("id", "?")
        if cid in seen:
            problems.append(f"{cid}: duplicate id")
        seen.add(cid)
        for key in ("name", "role", "kind", "license", "languages", "evidence"):
            if key not in c:
                problems.append(f"{cid}: missing {key}")
        if c.get("role") not in ROLES:
            problems.append(f"{cid}: bad role {c.get('role')!r}")
        if c.get("kind") not in KINDS:
            problems.append(f"{cid}: bad kind {c.get('kind')!r}")
        lic = c.get("license", {})
        for part in ("code", "weights", "training_data"):
            value = lic.get(part, {}).get("commercial_ok")
            if value not in COMMERCIAL:
                problems.append(f"{cid}: license.{part}.commercial_ok must be one of {sorted(COMMERCIAL)}, got {value!r} (quote yes/no)")
        evidence = c.get("evidence") or []
        if not evidence:
            problems.append(f"{cid}: no evidence")
        for ev in evidence:
            for key in ("claim", "url", "quote", "retrieved"):
                if not ev.get(key):
                    problems.append(f"{cid}: evidence entry missing {key}")
            if ev.get("url") and not str(ev["url"]).startswith("https://"):
                problems.append(f"{cid}: evidence url must be https")
        if c.get("role") == "product" and not shippable(c):
            problems.append(f"{cid}: role product requires code and weights commercial_ok yes")
        if not isinstance(c.get("languages"), list):
            problems.append(f"{cid}: languages must be a list")
    return problems
