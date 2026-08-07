"""Parse human Good/Bad/Moderate/Better labels and category folders."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .types import CategoryId, QualityLabel

# Filenames use underscores around labels: `_Good_`, `_ Bad_`, `_Moderate_`.
_QUALITY_RE = re.compile(
    r"(?i)(?:^|[^A-Za-z0-9])(good|better|moderate|bad)(?:[^A-Za-z0-9]|$)"
)

_CATEGORY_ALIASES: dict[str, CategoryId] = {
    "3. communication": CategoryId.COMMUNICATION,
    "communication": CategoryId.COMMUNICATION,
    "comm": CategoryId.COMMUNICATION,
    "leadership": CategoryId.LEADERSHIP,
    "sexual harassment": CategoryId.SEXUAL_HARASSMENT,
    "s.harassment": CategoryId.SEXUAL_HARASSMENT,
    "sexual_harassment": CategoryId.SEXUAL_HARASSMENT,
}


def normalize_category(folder_name: str) -> CategoryId:
    key = (folder_name or "").strip().lower()
    if key in _CATEGORY_ALIASES:
        return _CATEGORY_ALIASES[key]
    for alias, cat in _CATEGORY_ALIASES.items():
        if alias in key or key in alias:
            return cat
    return CategoryId.OTHER


def parse_quality_label(filename: str) -> QualityLabel:
    match = _QUALITY_RE.search(filename or "")
    if not match:
        return QualityLabel.UNLABELED
    token = match.group(1).lower()
    return QualityLabel(token)


def should_incorporate(label: QualityLabel) -> bool:
    """Default policy: incorporate Good + Better; queue Moderate; reject Bad."""
    return label in {QualityLabel.GOOD, QualityLabel.BETTER}


def should_review_queue(label: QualityLabel) -> bool:
    return label in {QualityLabel.MODERATE, QualityLabel.UNLABELED}


def source_id_for(path: Path, category: CategoryId) -> str:
    digest = hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:10]
    stem = re.sub(r"[^a-zA-Z0-9]+", "-", path.stem)[:48].strip("-").lower() or "doc"
    return f"{category.value}__{stem}__{digest}"


def title_guess_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    # Drop trailing _PDF / _PPTX markers and leading catalog codes.
    stem = re.sub(r"(?i)_(pdf|pptx)$", "", stem)
    stem = re.sub(r"(?i)^(comm|leadership|s\.?harassment)[#\d_\s,-]*", "", stem)
    stem = re.sub(
        r"(?i)(?:^|_)(good|better|moderate|bad)(?=_|$|\s)",
        " ",
        stem,
    )
    stem = re.sub(r"[_\s]+", " ", stem).strip(" -_")
    return stem or filename
