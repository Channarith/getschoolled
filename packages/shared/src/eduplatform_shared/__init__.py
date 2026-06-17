"""Shared library for the Agentic Online Education Platform.

Exposes the provider abstraction (narrow interfaces with local + cloud
implementations), a config-driven factory, runtime settings, and shared
pydantic schemas. The SAME code runs local or cloud, selected purely by env.
"""

from eduplatform_shared.config import DeployMode, Settings, get_settings
from eduplatform_shared.factory import ProviderFactory, get_provider_factory

__all__ = [
    "DeployMode",
    "Settings",
    "get_settings",
    "ProviderFactory",
    "get_provider_factory",
]

__version__ = "0.1.0"
