"""Outbound webhooks + signing (Integrations, Phase 16).

HMAC-signed event delivery to external subscribers, with retries/backoff. The
sender is pluggable so the logic is offline-testable (a MockSender records calls
and can simulate transient failures); production injects an httpx sender.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Dict, List

from pydantic import BaseModel, Field


def sign_payload(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify_signature(body: bytes, signature: str, secret: str) -> bool:
    return hmac.compare_digest(sign_payload(body, secret), signature or "")


class WebhookEvent(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    event_type: str
    data: dict = Field(default_factory=dict)
    created_at: float = Field(default_factory=lambda: time.time())

    def body_bytes(self) -> bytes:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True,
                          separators=(",", ":")).encode("utf-8")


class WebhookSubscription(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    url: str
    event_types: List[str] = Field(default_factory=list)  # empty = all events
    secret: str = ""
    active: bool = True

    def matches(self, event_type: str) -> bool:
        return self.active and (not self.event_types or event_type in self.event_types)


class SubscriptionStore:
    def __init__(self) -> None:
        self._subs: Dict[str, WebhookSubscription] = {}

    def add(self, sub: WebhookSubscription) -> WebhookSubscription:
        self._subs[sub.id] = sub
        return sub

    def list(self) -> List[WebhookSubscription]:
        return list(self._subs.values())

    def matching(self, event_type: str) -> List[WebhookSubscription]:
        return [s for s in self._subs.values() if s.matches(event_type)]


@dataclass
class DeliveryResult:
    subscription_id: str
    delivered: bool
    attempts: int
    status: int


# A sender takes (url, body, headers) and returns an HTTP status code.
Sender = Callable[[str, bytes, Dict[str, str]], int]


class MockSender:
    """Records deliveries; optionally fails the first ``fail_times`` calls."""

    def __init__(self, fail_times: int = 0, fail_status: int = 503) -> None:
        self.fail_times = fail_times
        self.fail_status = fail_status
        self.calls: List[dict] = []

    def __call__(self, url: str, body: bytes, headers: Dict[str, str]) -> int:
        self.calls.append({"url": url, "body": body, "headers": headers})
        if len(self.calls) <= self.fail_times:
            return self.fail_status
        return 200


def deliver(
    sub: WebhookSubscription,
    event: WebhookEvent,
    *,
    sender: Sender,
    max_attempts: int = 3,
) -> DeliveryResult:
    body = event.body_bytes()
    headers = {
        "Content-Type": "application/json",
        "X-AOEP-Event": event.event_type,
        "X-AOEP-Signature": sign_payload(body, sub.secret),
    }
    status = 0
    for attempt in range(1, max_attempts + 1):
        status = sender(sub.url, body, headers)
        if 200 <= status < 300:
            return DeliveryResult(sub.id, True, attempt, status)
    return DeliveryResult(sub.id, False, max_attempts, status)


def dispatch(
    store: SubscriptionStore,
    event: WebhookEvent,
    *,
    sender: Sender,
    max_attempts: int = 3,
) -> List[DeliveryResult]:
    return [deliver(s, event, sender=sender, max_attempts=max_attempts)
            for s in store.matching(event.event_type)]
