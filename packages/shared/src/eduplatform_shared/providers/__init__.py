"""Provider abstraction: narrow interfaces + local/cloud implementations.

Every heavy capability (LLM, speech, vision, media, object store, payments)
sits behind an abstract interface here. A config-driven factory
(``eduplatform_shared.factory``) instantiates the local or cloud
implementation at startup. No code forks between deployment modes.
"""

from eduplatform_shared.providers.base import (
    LLMProvider,
    MediaProvider,
    ObjectStoreProvider,
    PaymentProvider,
    SpeechProvider,
    VisionProvider,
)

__all__ = [
    "LLMProvider",
    "SpeechProvider",
    "VisionProvider",
    "MediaProvider",
    "ObjectStoreProvider",
    "PaymentProvider",
]
