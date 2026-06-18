"""24/7 large-scale course-material harvester (license-gated, deduped)."""

from .queue import HarvestQueue, url_key
from .sources import LICENSE_ALLOWLIST, SourceSpec, is_allowed, normalize_license
from .worker import HarvestStats, HarvestWorker

__all__ = [
    "HarvestQueue",
    "url_key",
    "LICENSE_ALLOWLIST",
    "SourceSpec",
    "is_allowed",
    "normalize_license",
    "HarvestStats",
    "HarvestWorker",
]
