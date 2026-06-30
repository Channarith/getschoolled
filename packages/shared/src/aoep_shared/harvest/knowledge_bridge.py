"""Bridge harvested/vetted content into knowledge content packs.

Lets the harvester grow the knowledge base at scale: after the critique pass
vets material, emit citable facts as a knowledge pack (JSON) into a content-pack
directory. On next load (or ``KnowledgeStore.rebuild()``) those facts become part
of the live, searchable, persisted knowledge base.

Pure/stdlib-only; the schema matches what ``content_packs``/``knowledge_base``
consume so no separate transform is needed.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence


@dataclass
class VettedFact:
    fact: str
    source: str
    reference: str
    category: str = "guideline"
    url: str = ""
    domains: Sequence[str] = field(default_factory=tuple)
    keywords: Sequence[str] = field(default_factory=tuple)

    def to_record(self) -> dict:
        return {
            "fact": self.fact,
            "source": self.source,
            "reference": self.reference,
            "category": self.category,
            "url": self.url,
            "domains": list(self.domains),
            "keywords": list(self.keywords),
        }


def _is_valid(rec: dict) -> bool:
    return bool(rec.get("fact") and rec.get("source") and rec.get("reference"))


def write_knowledge_pack(
    facts: Iterable[VettedFact | dict],
    out_path: str | Path,
    *,
    pack_name: str = "harvested",
    description: str = "Harvested vetted facts",
) -> int:
    """Write vetted facts to a knowledge pack JSON. Returns records written."""
    records: List[dict] = []
    for f in facts:
        rec = f.to_record() if isinstance(f, VettedFact) else dict(f)
        if _is_valid(rec):
            records.append(rec)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"pack": pack_name, "description": description, "records": records}, indent=2),
        encoding="utf-8",
    )
    return len(records)


def default_packs_dir() -> Path:
    """Where harvested packs are written (an AOEP_CONTENT_PACKS root)."""
    env = os.environ.get("AOEP_CONTENT_PACKS", "")
    first = next((p for p in env.split(os.pathsep) if p.strip()), "")
    base = Path(first) if first else (Path(os.path.expanduser("~")) / ".cache" / "aoep" / "content-packs")
    return base / "knowledge"


def facts_from_course(course, *, default_domains: Sequence[str] = ()) -> List[VettedFact]:
    """Extract candidate facts from a harvested/generated course's FACT lines.

    Looks for slide ``facts`` (or ``key_facts``) attributes/keys and turns each
    into a VettedFact attributed to the course source. Conservative: only emits
    facts that already carry an explicit source/reference, to keep the knowledge
    base trustworthy.
    """
    out: List[VettedFact] = []
    slides = getattr(course, "slides", None)
    if slides is None and isinstance(course, dict):
        slides = course.get("slides", [])
    for slide in slides or []:
        raw_facts = getattr(slide, "facts", None)
        if raw_facts is None and isinstance(slide, dict):
            raw_facts = slide.get("facts") or slide.get("key_facts")
        for item in raw_facts or []:
            if isinstance(item, dict) and item.get("source") and item.get("reference"):
                out.append(VettedFact(
                    fact=str(item.get("fact", "")).strip(),
                    source=str(item["source"]).strip(),
                    reference=str(item["reference"]).strip(),
                    category=str(item.get("category", "guideline")),
                    url=str(item.get("url", "")),
                    domains=tuple(item.get("domains", default_domains)),
                    keywords=tuple(item.get("keywords", ())),
                ))
    return [f for f in out if f.fact]
