"""Media provider implementations (LiveKit WebRTC backbone).

local  -> self-hosted LiveKit container.
cloud  -> LiveKit cluster.

Both mint join tokens the same way; only the URL/keys differ (carried by
AppConfig). Token minting is a pure HMAC operation, so it is implemented and
unit-testable without any running media server.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from ..config import AppConfig
from .base import MediaProvider, ProviderInfo, RoomToken


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


class _BaseMediaProvider(MediaProvider):
    impl = "livekit"

    def __init__(self, config: AppConfig, *, mode: str) -> None:
        self._config = config
        self._mode = mode
        self._url = config.livekit_url
        self._api_key = config.livekit_api_key
        self._api_secret = config.livekit_api_secret

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            capability=self.capability,
            mode=self._mode,
            impl=self.impl,
            endpoint=self._url,
        )

    def issue_token(
        self, *, room: str, identity: str, can_publish: bool = True
    ) -> RoomToken:
        """Mint a LiveKit-style JWT (HS256) granting access to ``room``.

        This mirrors LiveKit's access-token claims so the same token works
        against a local container or a cloud cluster.
        """
        now = int(time.time())
        header = {"alg": "HS256", "typ": "JWT"}
        claims = {
            "iss": self._api_key,
            "sub": identity,
            "nbf": now,
            "exp": now + 3600,
            "video": {
                "room": room,
                "roomJoin": True,
                "canPublish": can_publish,
                "canSubscribe": True,
            },
        }
        signing_input = (
            _b64url(json.dumps(header, separators=(",", ":")).encode())
            + "."
            + _b64url(json.dumps(claims, separators=(",", ":")).encode())
        )
        signature = hmac.new(
            self._api_secret.encode(),
            signing_input.encode(),
            hashlib.sha256,
        ).digest()
        token = signing_input + "." + _b64url(signature)
        return RoomToken(room=room, identity=identity, token=token, url=self._url)


class LocalMediaProvider(_BaseMediaProvider):
    impl = "livekit-self-hosted"

    def __init__(self, config: AppConfig) -> None:
        super().__init__(config, mode="local")


class CloudMediaProvider(_BaseMediaProvider):
    impl = "livekit-cluster"

    def __init__(self, config: AppConfig) -> None:
        super().__init__(config, mode="cloud")
