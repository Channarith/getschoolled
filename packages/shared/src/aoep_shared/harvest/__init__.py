"""24/7 large-scale course-material harvester (license-gated, deduped).

Beyond the crawl/queue/upsert loop this package now turns harvested material
into quantifiable, tagged, scored course compositions and continuously
critiques them:
  - extractors : read text/html/pdf/pptx/docx/database into a normalized doc
  - composition: numpy node/sub-node matrix + composition_score + quality
  - tagging    : JSON/meta tags (free/expensive, LinkedIn job, career, core)
  - generate   : extract -> slides -> composition -> score -> tags (reviewable)
  - critique   : grade + suggest + track quality in the optimization ledger
"""

from .auto_tags import InferredMetadata, infer_harvest_metadata, merge_tags
from .composition import (
    CATEGORY_INDEX,
    COMPOSITION_VERSION,
    DEFAULT_SCORE_MODULUS,
    NODE_CATEGORIES,
    NUM_CATEGORIES,
    PCS_VERSION,
    QUANT_RESOLUTION,
    STRUCT_CATEGORY_COEFF,
    STRUCT_NODE_COEFF,
    CompositionOutcomeLedger,
    CourseComposition,
    classify_section,
)
from .critique import (
    CritiqueReport,
    HarvestCritic,
    optimize_with_ledger,
    summarize_reports,
)
from .extractors import (
    SUPPORTED_SOURCE_TYPES,
    ExtractedDoc,
    extract,
    extract_database,
    extract_docx,
    extract_file,
    extract_html,
    extract_pdf,
    extract_pptx,
    extract_text,
)
from .export import (
    CoursePackage,
    ensure_pptx_available,
    export_course_json,
    export_course_package,
    export_pptx,
    resolve_course_pptx,
)
from .generate import (
    GENERATION_INSTRUCTIONS,
    GeneratedCourse,
    GeneratedSlide,
    generate_course,
)
from .pipeline import BatchMetrics, CatalogUpsertStore, HarvestPipeline, catalog_key
from .queue import HarvestQueue, url_key
from .corpus_store import CorpusHit, HarvestCorpusStore, chunk_text, default_corpus_path
from .crawl import CrawlMetrics, CrawlSession, open_crawl_session
from .discovery import discover_topic, load_env_seeds, portal_specs
from .fetcher import extract_links, fetch_text, fetch_url
from .queue_store import PersistentHarvestQueue
from .runner import Checkpoint, harvest_loop
from .themes import SlideTheme, resolve_slide_theme
from .section_normalize import normalize_document
from .sources import LICENSE_ALLOWLIST, SourceSpec, is_allowed, normalize_license
from .tagging import ACCESS_TIERS, CourseTags
from .worker import HarvestStats, HarvestWorker

__all__ = [
    # crawl/queue/upsert
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
    # extraction
    "SUPPORTED_SOURCE_TYPES",
    "ExtractedDoc",
    "extract",
    "extract_file",
    "extract_text",
    "extract_html",
    "extract_pdf",
    "extract_pptx",
    "extract_docx",
    "extract_database",
    # composition / scoring
    "NODE_CATEGORIES",
    "CATEGORY_INDEX",
    "NUM_CATEGORIES",
    "COMPOSITION_VERSION",
    "PCS_VERSION",
    "QUANT_RESOLUTION",
    "STRUCT_NODE_COEFF",
    "STRUCT_CATEGORY_COEFF",
    "DEFAULT_SCORE_MODULUS",
    "CourseComposition",
    "CompositionOutcomeLedger",
    "classify_section",
    # tagging
    "CourseTags",
    "ACCESS_TIERS",
    "InferredMetadata",
    "infer_harvest_metadata",
    "merge_tags",
    # generation
    "GeneratedCourse",
    "GeneratedSlide",
    "generate_course",
    "GENERATION_INSTRUCTIONS",
    "normalize_document",
    # online crawl + corpus
    "HarvestCorpusStore",
    "CorpusHit",
    "chunk_text",
    "default_corpus_path",
    "PersistentHarvestQueue",
    "open_crawl_session",
    "CrawlSession",
    "CrawlMetrics",
    "discover_topic",
    "portal_specs",
    "load_env_seeds",
    "fetch_url",
    "fetch_text",
    "resolve_slide_theme",
    "SlideTheme",
    # export / hand-off (Part 1 -> Part 2)
    "ensure_pptx_available",
    "resolve_course_pptx",
    "export_pptx",
    "export_course_json",
    "export_course_package",
    "CoursePackage",
    # critique / optimization
    "HarvestCritic",
    "CritiqueReport",
    "summarize_reports",
    "optimize_with_ledger",
]
