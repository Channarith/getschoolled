"""Provider abstraction layer.

Every heavy capability sits behind a narrow interface with a ``local`` and a
``cloud`` implementation. The concrete class is chosen at startup by the
config-driven factory (see :mod:`aoep_shared.factory`).

The implementations shipped here are deliberately runtime-light: they encode the
contract and the wiring (endpoints, request shapes, consent gating) and clearly
mark where a GPU/model/network call belongs. This lets the whole platform import
and be tested without network or GPU access, while the cloud/local split is real
and exercised by tests.
"""

from .base import (
    LLMProvider,
    MediaProvider,
    ObjectStoreProvider,
    PaymentProvider,
    Provider,
    SpeechProvider,
    VisionProvider,
)

__all__ = [
    "Provider",
    "LLMProvider",
    "SpeechProvider",
    "VisionProvider",
    "MediaProvider",
    "ObjectStoreProvider",
    "PaymentProvider",
]
