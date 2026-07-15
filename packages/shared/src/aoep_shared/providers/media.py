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

    def _sign(self, claims: dict) -> str:
        """Sign ``claims`` as a LiveKit-style HS256 JWT with the API secret."""
        header = {"alg": "HS256", "typ": "JWT"}
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
        return signing_input + "." + _b64url(signature)

    def issue_token(
        self, *, room: str, identity: str, can_publish: bool = True
    ) -> RoomToken:
        """Mint a LiveKit-style JWT (HS256) granting access to ``room``.

        This mirrors LiveKit's access-token claims so the same token works
        against a local container or a cloud cluster.
        """
        now = int(time.time())
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
        token = self._sign(claims)
        return RoomToken(room=room, identity=identity, token=token, url=self._url)

    @staticmethod
    def _http_base(url: str) -> str:
        """Map a LiveKit ws(s):// signalling URL to its https(s):// REST base."""
        base = (url or "").strip()
        if base.startswith("wss://"):
            base = "https://" + base[len("wss://"):]
        elif base.startswith("ws://"):
            base = "http://" + base[len("ws://"):]
        return base.rstrip("/")

    def verify_credentials(self, *, timeout: float = 3.0) -> dict:
        """Best-effort server-side check that (url, api_key, api_secret) are a
        valid, MATCHING LiveKit trio.

        The browser only ever reports "WebSocket is closed before the connection
        is established" when Cloud rejects a token — which is indistinguishable
        from a network problem client-side. This mints a short-lived roomList
        token and calls LiveKit's Twirp ``ListRooms`` so operators get a clear
        verdict: ``verified`` (creds match), ``rejected`` (secret/key mismatch),
        or ``unreachable`` (network/URL problem).
        """
        import urllib.error
        import urllib.request

        now = int(time.time())
        token = self._sign(
            {
                "iss": self._api_key,
                "sub": "diagnostics",
                "nbf": now - 5,
                "exp": now + 60,
                "video": {"roomList": True, "roomAdmin": True},
            }
        )
        base = self._http_base(self._url)
        if not base:
            return {"status": "unreachable", "detail": "no LiveKit URL configured"}
        endpoint = base + "/twirp/livekit.RoomService/ListRooms"
        req = urllib.request.Request(
            endpoint,
            data=b"{}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                if 200 <= resp.status < 300:
                    return {"status": "verified", "endpoint": endpoint}
                return {"status": "rejected", "http_status": resp.status, "endpoint": endpoint}
        except urllib.error.HTTPError as exc:
            # 401/403 => the api_key/api_secret pair is wrong for this project.
            return {
                "status": "rejected",
                "http_status": exc.code,
                "detail": exc.reason,
                "endpoint": endpoint,
                "hint": (
                    "LiveKit rejected the credentials. Re-copy LIVEKIT_API_SECRET "
                    "for this exact key from the project's LiveKit Cloud dashboard."
                    if exc.code in (401, 403)
                    else ""
                ),
            }
        except Exception as exc:  # noqa: BLE001
            return {"status": "unreachable", "detail": str(exc), "endpoint": endpoint}


class LocalMediaProvider(_BaseMediaProvider):
    impl = "livekit-self-hosted"

    def __init__(self, config: AppConfig) -> None:
        super().__init__(config, mode="local")


class CloudMediaProvider(_BaseMediaProvider):
    impl = "livekit-cluster"

    def __init__(self, config: AppConfig) -> None:
        super().__init__(config, mode="cloud")
