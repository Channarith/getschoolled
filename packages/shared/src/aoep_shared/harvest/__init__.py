"""24/7 large-scale course-material harvester (license-gated, deduped)."""

from .pipeline import BatchMetrics, CatalogUpsertStore, HarvestPipeline, catalog_key
from .queue import HarvestQueue, url_key
from .runner import Checkpoint, harvest_loop
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
    "HarvestPipeline",
    "CatalogUpsertStore",
    "BatchMetrics",
    "catalog_key",
    "Checkpoint",
    "harvest_loop",
]
