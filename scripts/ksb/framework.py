"""KSB (Knowledge, Skills, Behaviours) structures for corporate courses.

Models each corporate course the same way a UK apprenticeship occupational
standard does (e.g. ST1398 Machine Learning Engineer): a set of occupation
*duties*, each mapped to the *knowledge* (K), *skills* (S) and *behaviours* (B)
required to perform it.

The canonical in-memory representation is a small set of NumPy structured
arrays (a "numpy object structure"):

  - knowledge / skills / behaviours -> structured array, dtype KSB_DTYPE
        fields: code (e.g. "K1"), kind ("K"/"S"/"B"), statement (object/str)
  - duties                          -> structured array, dtype DUTY_DTYPE
        fields: code (e.g. "Duty 1"), statement (object/str),
                ksbs (object: numpy array of referenced KSB codes)

NumPy is used so a course standard is a typed, vectorised table that can be
queried, masked, concatenated and persisted (.npz) like any other array data.

This module has no third-party dependency other than NumPy (already pinned in
the repo's requirements) and is pure-stdlib otherwise.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence

import numpy as np

# A single KSB row: its code, which family it belongs to, and the statement.
KSB_DTYPE = np.dtype([("code", "U8"), ("kind", "U1"), ("statement", object)])

# A duty row: its code, the duty statement, and the KSB codes it maps to. The
# variable-length list of references is stored as an object-dtype cell holding a
# NumPy array of code strings.
DUTY_DTYPE = np.dtype([("code", "U12"), ("statement", object), ("ksbs", object)])

_KIND_BY_PREFIX = {"K": "K", "S": "S", "B": "B"}


def _ksb_array(items: Mapping[str, str], kind: str) -> np.ndarray:
    """Build a KSB structured array from an ordered {code: statement} mapping."""
    rows = [(code, kind, str(stmt)) for code, stmt in items.items()]
    arr = np.empty(len(rows), dtype=KSB_DTYPE)
    for i, row in enumerate(rows):
        arr[i] = row
    return arr


def _duty_array(duties: Mapping[str, Mapping]) -> np.ndarray:
    """Build a duty structured array from {code: {statement, ksbs[]}}."""
    arr = np.empty(len(duties), dtype=DUTY_DTYPE)
    for i, (code, body) in enumerate(duties.items()):
        refs = np.array(list(body.get("ksbs", [])), dtype="U8")
        arr[i] = (code, str(body.get("statement", "")), refs)
    return arr


@dataclass
class KSBStandard:
    """A course's occupational standard as NumPy structured arrays."""

    course_id: str
    title: str
    level: str
    role: str
    knowledge: np.ndarray  # KSB_DTYPE
    skills: np.ndarray  # KSB_DTYPE
    behaviours: np.ndarray  # KSB_DTYPE
    duties: np.ndarray  # DUTY_DTYPE

    # ---- construction -----------------------------------------------------
    @classmethod
    def from_dict(cls, data: Mapping) -> "KSBStandard":
        return cls(
            course_id=data["course_id"],
            title=data.get("title", data["course_id"]),
            level=data.get("level", ""),
            role=data.get("role", ""),
            knowledge=_ksb_array(data.get("knowledge", {}), "K"),
            skills=_ksb_array(data.get("skills", {}), "S"),
            behaviours=_ksb_array(data.get("behaviours", {}), "B"),
            duties=_duty_array(data.get("duties", {})),
        )

    @classmethod
    def from_json(cls, path: str | Path) -> "KSBStandard":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    # ---- views ------------------------------------------------------------
    @property
    def ksbs(self) -> np.ndarray:
        """All K, S and B rows concatenated into one structured array."""
        return np.concatenate([self.knowledge, self.skills, self.behaviours])

    def codes(self) -> set:
        return set(self.ksbs["code"].tolist())

    def statement(self, code: str) -> str:
        """Look up a KSB statement by code using a NumPy mask."""
        all_ksbs = self.ksbs
        mask = all_ksbs["code"] == code
        if not mask.any():
            raise KeyError(code)
        return str(all_ksbs["statement"][mask][0])

    def duty_matrix(self) -> np.ndarray:
        """Boolean (duties x ksbs) coverage matrix as a NumPy array.

        Row i, column j is True when duty i references KSB j (ordered as in
        ``self.ksbs``). Useful for coverage analysis and heatmaps.
        """
        codes = self.ksbs["code"]
        index = {c: j for j, c in enumerate(codes.tolist())}
        matrix = np.zeros((len(self.duties), len(codes)), dtype=bool)
        for i, duty in enumerate(self.duties):
            for ref in duty["ksbs"].tolist():
                j = index.get(ref)
                if j is not None:
                    matrix[i, j] = True
        return matrix

    # ---- validation -------------------------------------------------------
    def validate(self) -> List[str]:
        """Return a list of problems; empty list means the standard is clean."""
        problems: List[str] = []
        all_codes = self.codes()

        # Code prefixes match their family and are unique within each family.
        for arr, kind in (
            (self.knowledge, "K"),
            (self.skills, "S"),
            (self.behaviours, "B"),
        ):
            codes = arr["code"].tolist()
            for c in codes:
                if not c.startswith(kind):
                    problems.append(f"{self.course_id}: {c} should start with '{kind}'")
            dupes = {c for c in codes if codes.count(c) > 1}
            for c in sorted(dupes):
                problems.append(f"{self.course_id}: duplicate code {c}")

        # Every duty must reference at least one KSB, and only existing ones.
        referenced: set = set()
        for duty in self.duties:
            refs = duty["ksbs"].tolist()
            if not refs:
                problems.append(f"{self.course_id}: {duty['code']} maps to no KSBs")
            for ref in refs:
                referenced.add(ref)
                if ref not in all_codes:
                    problems.append(
                        f"{self.course_id}: {duty['code']} references unknown KSB {ref}"
                    )

        # Every KSB should be exercised by at least one duty (apprenticeship rule).
        for code in sorted(all_codes - referenced):
            problems.append(f"{self.course_id}: {code} is not mapped to any duty")

        return problems

    # ---- reporting --------------------------------------------------------
    def summary(self) -> str:
        return (
            f"{self.course_id} | {self.title}\n"
            f"  {self.level} - {self.role}\n"
            f"  duties={len(self.duties)} "
            f"K={len(self.knowledge)} S={len(self.skills)} B={len(self.behaviours)}"
        )

    def describe(self) -> str:
        lines = [self.summary(), ""]
        lines.append("Occupation duties")
        for duty in self.duties:
            refs = " ".join(duty["ksbs"].tolist())
            lines.append(f"  {duty['code']}: {duty['statement']}")
            lines.append(f"    KSBs: {refs}")
        for label, arr in (
            ("Knowledge", self.knowledge),
            ("Skills", self.skills),
            ("Behaviours", self.behaviours),
        ):
            lines.append("")
            lines.append(label)
            for row in arr:
                lines.append(f"  {row['code']}: {row['statement']}")
        return "\n".join(lines)

    # ---- persistence ------------------------------------------------------
    def to_npz(self, path: str | Path) -> None:
        """Persist the structured arrays to a NumPy .npz archive."""
        np.savez(
            path,
            meta=np.array(
                [self.course_id, self.title, self.level, self.role], dtype=object
            ),
            knowledge=self.knowledge,
            skills=self.skills,
            behaviours=self.behaviours,
            duties=self.duties,
        )

    @classmethod
    def from_npz(cls, path: str | Path) -> "KSBStandard":
        with np.load(path, allow_pickle=True) as z:
            meta = z["meta"].tolist()
            return cls(
                course_id=meta[0],
                title=meta[1],
                level=meta[2],
                role=meta[3],
                knowledge=z["knowledge"],
                skills=z["skills"],
                behaviours=z["behaviours"],
                duties=z["duties"],
            )


# KSB data lives next to each course's lesson, at
# sample-curriculum/<course-id>/ksb.json, so it ships with the orchestrator image
# (which copies sample-curriculum) and stays the single source of truth.
CURRICULUM_DIR = (
    Path(__file__).resolve().parents[2] / "sample-curriculum"
)


def load_all(curriculum_dir: str | Path = CURRICULUM_DIR) -> Dict[str, KSBStandard]:
    """Load every <course>/ksb.json under ``curriculum_dir`` into a KSBStandard."""
    out: Dict[str, KSBStandard] = {}
    for path in sorted(Path(curriculum_dir).glob("*/ksb.json")):
        std = KSBStandard.from_json(path)
        out[std.course_id] = std
    return out
