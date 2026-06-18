"""Per-subject trusted sources for homework correctness checks (Phase 9).

Open homework answers are corroborated against authoritative sources for the
subject (e.g. a medical assignment checks medical authorities like webmd.com /
nih.gov), not the open web at large. `restrict_to_domains` filters search
results to the allowlist so corroboration only counts trusted evidence.
"""

from __future__ import annotations

import os
from typing import Dict, List, Sequence
from urllib.parse import urlparse

# Subject -> trusted domains. Extend via HOMEWORK_TRUSTED_DOMAINS env
# ("subject=domain|domain,subject=...").
SUBJECT_TRUSTED_DOMAINS: Dict[str, List[str]] = {
    "medical": ["webmd.com", "nih.gov", "medlineplus.gov", "mayoclinic.org", "who.int"],
    "biology": ["nih.gov", "ncbi.nlm.nih.gov", "khanacademy.org", "britannica.com"],
    "science": ["nasa.gov", "nih.gov", "britannica.com", "khanacademy.org"],
    "history": ["britannica.com", "loc.gov", "si.edu"],
    "math": ["khanacademy.org", "mathworld.wolfram.com"],
}


def _domain(url: str) -> str:
    try:
        net = urlparse(url).netloc.lower()
    except Exception:  # noqa: BLE001
        return ""
    return net[4:] if net.startswith("www.") else net


def _env_overrides() -> Dict[str, List[str]]:
    raw = os.environ.get("HOMEWORK_TRUSTED_DOMAINS", "")
    out: Dict[str, List[str]] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if "=" in pair:
            subj, doms = pair.split("=", 1)
            out[subj.strip().lower()] = [d.strip().lower() for d in doms.split("|") if d.strip()]
    return out


def trusted_domains_for(subject: str) -> List[str]:
    subject = (subject or "").lower()
    overrides = _env_overrides()
    if subject in overrides:
        return overrides[subject]
    return SUBJECT_TRUSTED_DOMAINS.get(subject, [])


def restrict_to_domains(results: Sequence, domains: Sequence[str]):
    """Keep only results whose URL host is in ``domains`` (no filter if empty)."""
    if not domains:
        return list(results)
    allow = {d.lower() for d in domains}
    return [r for r in results if any(_domain(getattr(r, "url", "")).endswith(d) for d in allow)]
