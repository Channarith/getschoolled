"""Shared library for the Agentic Online Education Platform (AOEP).

Exposes the dual-mode configuration model, the provider interfaces with their
local and cloud implementations, the config-driven provider factory, the
cross-service pydantic schemas, and a dependency-free RAG skeleton.
"""

from .config import AppConfig, ComponentMode, DeployMode, load_config
from .factory import ProviderFactory, build_factory
from .version import get_version

__all__ = [
    "AppConfig",
    "ComponentMode",
    "DeployMode",
    "load_config",
    "ProviderFactory",
    "build_factory",
    "get_version",
]

__version__ = get_version()
