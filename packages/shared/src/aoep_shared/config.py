"""Dual-mode configuration for AOEP.

The exact same code runs either fully local (single machine / docker compose) or
against a cloud backend (Kubernetes + GPU pool). The mode is selected purely by
environment / config -- there are no code forks.

DEPLOY_MODE sets the default for every heavy capability. Each capability can be
overridden independently (e.g. run the LLM in the cloud while keeping biometrics
local for compliance) via a per-component ``*_MODE`` variable.
"""

from __future__ import annotations

import os
from enum import Enum
from typing import Mapping, MutableMapping, Optional

from pydantic import BaseModel, Field


class DeployMode(str, Enum):
    """Top-level deployment target."""

    LOCAL = "local"
    CLOUD = "cloud"
    # Edge: fully on-device / offline (no cloud calls). Selects local providers
    # everywhere; used for the embodiment/humanoid path (Phases 13-15).
    EDGE = "edge"


# Accepted aliases for DEPLOY_MODE env var — mapped to canonical values before
# parsing so operators can use intuitive names without changing internal logic.
_DEPLOY_MODE_ALIASES: dict[str, str] = {
    "production": "cloud",
    "prod": "cloud",
    "dev": "local",
    "development": "local",
    "offline": "edge",
}


# A per-component mode is the same value space as the deploy mode; keeping a
# distinct alias documents intent at call sites and leaves room to diverge.
ComponentMode = DeployMode


# Components whose implementation is chosen by mode. The biometrics-bearing
# components (vision/media) can be pinned locally regardless of DEPLOY_MODE to
# keep face data inside a configured boundary (a key compliance lever).
COMPONENTS = (
    "llm",
    "speech",
    "vision",
    "media",
    "object_store",
    "payment",
    "database",
    "bus",
    "ocr",
)


def _coerce_mode(value: Optional[str], default: DeployMode) -> DeployMode:
    if value is None or value.strip() == "":
        return default
    normalized = value.strip().lower()
    normalized = _DEPLOY_MODE_ALIASES.get(normalized, normalized)
    try:
        return DeployMode(normalized)
    except ValueError as exc:  # pragma: no cover - defensive
        valid = ", ".join(
            list(m.value for m in DeployMode) + list(_DEPLOY_MODE_ALIASES)
        )
        raise ValueError(
            f"Invalid mode {value!r}; expected one of: {valid}"
        ) from exc


class AppConfig(BaseModel):
    """Resolved configuration for a running process.

    ``deploy_mode`` is the default; ``component_modes`` holds the effective mode
    for every component after applying per-component overrides.
    """

    deploy_mode: DeployMode = DeployMode.LOCAL
    component_modes: dict[str, DeployMode] = Field(default_factory=dict)

    # Endpoints / connection strings consumed by provider implementations. These
    # are intentionally generic strings so the same config object serves both
    # local container URLs and cloud service URLs.
    llm_base_url: str = "http://llm:8000/v1"
    llm_model: str = "aoep-base-edu"
    llm_api_key: str = ""          # Bearer token for the OpenAI-compatible endpoint
    llm_provider: str = ""         # "" (auto) | "nemotron" to force the Nemotron agent
    # Track B routing: "category=model,category=model" -> per-domain adapters.
    llm_routes: str = ""
    # NVIDIA Nemotron conversational agent (OpenAI-compatible via NIM or self-hosted
    # vLLM). Set NEMOTRON_API_KEY to route the tutor/voice agent through Nemotron
    # with streaming (real-time, low-latency answers).
    nemotron_api_key: str = ""
    nemotron_base_url: str = "https://integrate.api.nvidia.com/v1"
    nemotron_model: str = "nvidia/llama-3.1-nemotron-70b-instruct"
    # xAI Grok Voice Agent (Speech-to-Speech realtime WebSocket). Used by the
    # private webcam-recognition lab and Theodore natural dialogue. Server-side
    # key only — browsers must use ephemeral tokens.
    xai_api_key: str = ""
    xai_voice_model: str = "grok-voice-latest"
    xai_voice_name: str = "eve"
    xai_voice_ws_url: str = "wss://api.x.ai/v1/realtime"
    # Bake-off champion pointer (JSON); serving layer uses it to pick the model.
    champion_path: str = ""
    # 24/7 harvester (runs on a separate worker agent).
    harvest_user_agent: str = "AOEP-Harvester/1.0 (+contact@example.org)"
    harvest_max_rps: float = 1.0
    harvest_seeds: str = ""
    speech_base_url: str = "http://speech:8100"
    vision_base_url: str = "http://perception:8200"
    # Memory service base URL. Empty => the orchestrator runs the live teaching
    # loop without per-student memory (neutral signals); set it to wire mastery/
    # behavior signals into adaptive pacing + quiz difficulty.
    memory_base_url: str = ""
    # Face-model cache dir (empty -> ~/.cache/aoep/models) and cosine match
    # threshold for SFace embeddings (0.363 is OpenCV's calibrated default).
    vision_model_dir: str = ""
    vision_match_threshold: float = 0.363
    # Persisted face gallery (cross-session student memory). Empty => in-memory.
    vision_gallery_path: str = ""
    livekit_url: str = "ws://livekit:7880"
    livekit_api_key: str = "devkey"
    livekit_api_secret: str = "devsecret"
    object_store_endpoint: str = "http://minio:9000"
    object_store_bucket: str = "aoep"
    object_store_access_key: str = "aoep"
    object_store_secret_key: str = "aoep-secret"
    database_url: str = "postgresql://aoep:aoep@postgres:5432/aoep"
    redis_url: str = "redis://redis:6379/0"
    # Payment-processor API keys. Only the ones configured for a given
    # deployment are activated; unconfigured providers raise NotImplementedError
    # so the platform fails-closed instead of silently dropping payments.
    # See packages/shared/src/aoep_shared/providers/payment.py.
    payment_api_key: str = ""              # Stripe (covers a wide global set)
    paypal_api_key: str = ""               # PayPal/Braintree (PayPal + Venmo)
    square_api_key: str = ""               # Square (US + a few EU)
    razorpay_api_key: str = ""             # India (UPI/PhonePe/RuPay)
    paytm_api_key: str = ""                # India alternate
    mercado_pago_api_key: str = ""         # LATAM (PIX/Boleto/OXXO)
    vnpay_api_key: str = ""                # Vietnam (VNPay)
    momo_api_key: str = ""                 # Vietnam wallet (MoMo + ZaloPay)
    aba_api_key: str = ""                  # Cambodia (ABA Pay/KHQR/Wing)
    yoomoney_api_key: str = ""             # Russia (Mir/YooMoney)
    toss_api_key: str = ""                 # Korea (KakaoPay/NaverPay/Toss)
    local_psp_api_key: str = ""            # Regional fallback (Mada/Knet/Fawry/etc.)
    # Course-validation search engines (each enabled only when its key is set).
    bing_search_key: str = ""
    google_cse_key: str = ""
    google_cse_cx: str = ""
    brave_search_key: str = ""
    kagi_api_key: str = ""
    baidu_api_key: str = ""
    # OCR (homework scanning; handwriting needs a cloud OCR backend).
    ocr_api_key: str = ""
    ocr_endpoint: str = ""
    # Neural TTS: ElevenLabs gives top-tier, natural, cultural voices for
    # narration (Drive Mode, live class). When the key is set the speech gateway
    # renders audio with it; otherwise it falls back to edge-tts neural voices,
    # then to the browser's on-device voice.
    elevenlabs_api_key: str = ""
    elevenlabs_model: str = "eleven_multilingual_v2"
    # CosyVoice 2 (self-hosted, FunAudioLLM): a streaming multilingual neural TTS
    # you run yourself. When COSYVOICE_URL points at your inference server the
    # speech gateway prefers it over ElevenLabs/edge-tts for narration.
    cosyvoice_url: str = ""
    cosyvoice_api_key: str = ""
    # Embodiment: screen avatar (default) or a humanoid robot (Phases 14-15).
    embodiment: str = "screen"   # screen | robot
    robot_endpoint: str = ""
    # Deployment region for the compliance policy engine (us | eu | us_il | other).
    region: str = "us"

    def mode_for(self, component: str) -> DeployMode:
        """Return the effective mode for ``component``."""
        if component not in COMPONENTS:
            raise KeyError(f"Unknown component {component!r}")
        return self.component_modes.get(component, self.deploy_mode)

    def is_local(self, component: str) -> bool:
        # Edge resolves to local (on-device) implementations.
        return self.mode_for(component) in (DeployMode.LOCAL, DeployMode.EDGE)

    def is_cloud(self, component: str) -> bool:
        return self.mode_for(component) is DeployMode.CLOUD

    @property
    def is_edge(self) -> bool:
        return self.deploy_mode is DeployMode.EDGE


def load_config(
    env: Optional[Mapping[str, str]] = None,
) -> AppConfig:
    """Build an :class:`AppConfig` from an environment mapping.

    Resolution order for each component's mode:
      1. ``<COMPONENT>_MODE`` (e.g. ``LLM_MODE``) if set.
      2. ``DEPLOY_MODE`` otherwise.
      3. ``local`` if nothing is set.
    """

    source: Mapping[str, str] = os.environ if env is None else env

    deploy_mode = _coerce_mode(source.get("DEPLOY_MODE"), DeployMode.LOCAL)

    component_modes: MutableMapping[str, DeployMode] = {}
    for component in COMPONENTS:
        override = source.get(f"{component.upper()}_MODE")
        component_modes[component] = _coerce_mode(override, deploy_mode)

    def get(key: str, default: str) -> str:
        value = source.get(key)
        return default if value is None or value == "" else value

    def get_stripped(key: str, default: str) -> str:
        """Like ``get`` but trims surrounding whitespace.

        Secrets/URLs are frequently injected with a trailing newline (heredocs,
        ``echo``, ``kubectl patch``/``create secret --from-literal``). For an
        HMAC-signed LiveKit token a single stray ``\\n`` in the secret makes the
        signature silently wrong, and LiveKit Cloud rejects the socket with the
        opaque "WebSocket is closed before the connection is established". Trim it
        so a copy-paste newline can't break signalling; fall back to the default
        when only whitespace was provided.
        """
        value = source.get(key)
        if value is None:
            return default
        cleaned = value.strip()
        return cleaned if cleaned else default

    return AppConfig(
        deploy_mode=deploy_mode,
        component_modes=dict(component_modes),
        llm_base_url=get("LLM_BASE_URL", "http://llm:8000/v1"),
        llm_model=get("LLM_MODEL", "aoep-base-edu"),
        llm_api_key=get("LLM_API_KEY", ""),
        llm_provider=get("LLM_PROVIDER", ""),
        llm_routes=get("LLM_ROUTES", ""),
        nemotron_api_key=get("NEMOTRON_API_KEY", ""),
        nemotron_base_url=get("NEMOTRON_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        nemotron_model=get("NEMOTRON_MODEL", "nvidia/llama-3.1-nemotron-70b-instruct"),
        xai_api_key=get("XAI_API_KEY", ""),
        xai_voice_model=get("XAI_VOICE_MODEL", "grok-voice-latest"),
        xai_voice_name=get("XAI_VOICE_NAME", "eve"),
        xai_voice_ws_url=get("XAI_VOICE_WS_URL", "wss://api.x.ai/v1/realtime"),
        champion_path=get("CHAMPION_PATH", ""),
        harvest_user_agent=get("HARVEST_USER_AGENT", "AOEP-Harvester/1.0 (+contact@example.org)"),
        harvest_max_rps=float(get("HARVEST_MAX_RPS", "1.0") or "1.0"),
        harvest_seeds=get("HARVEST_SEEDS", ""),
        speech_base_url=get("SPEECH_BASE_URL", "http://speech:8100"),
        vision_base_url=get("VISION_BASE_URL", "http://perception:8200"),
        memory_base_url=get("MEMORY_URL", ""),
        vision_model_dir=get("VISION_MODEL_DIR", ""),
        ocr_api_key=get("OCR_API_KEY", ""),
        elevenlabs_api_key=get("ELEVENLABS_API_KEY", ""),
        elevenlabs_model=get("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
        cosyvoice_url=get("COSYVOICE_URL", ""),
        cosyvoice_api_key=get("COSYVOICE_API_KEY", ""),
        ocr_endpoint=get("OCR_ENDPOINT", ""),
        embodiment=get("EMBODIMENT", "screen"),
        robot_endpoint=get("ROBOT_ENDPOINT", ""),
        region=get("REGION", "us"),
        vision_match_threshold=float(get("VISION_MATCH_THRESHOLD", "0.363")),
        vision_gallery_path=get("VISION_GALLERY_PATH", ""),
        livekit_url=get_stripped("LIVEKIT_URL", "ws://livekit:7880"),
        livekit_api_key=get_stripped("LIVEKIT_API_KEY", "devkey"),
        livekit_api_secret=get_stripped("LIVEKIT_API_SECRET", "devsecret"),
        object_store_endpoint=get("OBJECT_STORE_ENDPOINT", "http://minio:9000"),
        object_store_bucket=get("OBJECT_STORE_BUCKET", "aoep"),
        object_store_access_key=get("OBJECT_STORE_ACCESS_KEY", "aoep"),
        object_store_secret_key=get("OBJECT_STORE_SECRET_KEY", "aoep-secret"),
        database_url=get(
            "DATABASE_URL", "postgresql://aoep:aoep@postgres:5432/aoep"
        ),
        redis_url=get("REDIS_URL", "redis://redis:6379/0"),
        payment_api_key=get("PAYMENT_API_KEY", ""),
        paypal_api_key=get("PAYPAL_API_KEY", ""),
        square_api_key=get("SQUARE_API_KEY", ""),
        razorpay_api_key=get("RAZORPAY_API_KEY", ""),
        paytm_api_key=get("PAYTM_API_KEY", ""),
        mercado_pago_api_key=get("MERCADO_PAGO_API_KEY", ""),
        vnpay_api_key=get("VNPAY_API_KEY", ""),
        momo_api_key=get("MOMO_API_KEY", ""),
        aba_api_key=get("ABA_API_KEY", ""),
        yoomoney_api_key=get("YOOMONEY_API_KEY", ""),
        toss_api_key=get("TOSS_API_KEY", ""),
        local_psp_api_key=get("LOCAL_PSP_API_KEY", ""),
        bing_search_key=get("BING_SEARCH_KEY", ""),
        google_cse_key=get("GOOGLE_CSE_KEY", ""),
        google_cse_cx=get("GOOGLE_CSE_CX", ""),
        brave_search_key=get("BRAVE_SEARCH_KEY", ""),
        kagi_api_key=get("KAGI_API_KEY", ""),
        baidu_api_key=get("BAIDU_API_KEY", ""),
    )
