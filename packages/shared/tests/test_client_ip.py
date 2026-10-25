import pytest

from aoep_shared import client_ip as ci
from aoep_shared.ratelimit import InMemoryTokenBucket, RateLimit


def test_takes_the_entry_the_trusted_proxy_added_not_the_one_the_client_sent(monkeypatch):
    monkeypatch.setenv("AOEP_TRUSTED_PROXY_HOPS", "1")
    assert ci.client_ip({"x-forwarded-for": "6.6.6.6, 203.0.113.9"}, "10.0.0.5") == "203.0.113.9"


def test_a_client_cannot_mint_new_identities_by_rotating_the_header(monkeypatch):
    monkeypatch.setenv("AOEP_TRUSTED_PROXY_HOPS", "1")
    ids = {ci.client_ip({"x-forwarded-for": f"10.{i}.1.1, 203.0.113.9"}, "10.0.0.5") for i in range(50)}
    assert ids == {"203.0.113.9"}


def test_two_hops_for_a_cdn_in_front(monkeypatch):
    monkeypatch.setenv("AOEP_TRUSTED_PROXY_HOPS", "2")
    assert ci.client_ip({"x-forwarded-for": "1.1.1.1, 198.51.100.7, 203.0.113.9"}, "10.0.0.5") == "198.51.100.7"


@pytest.mark.parametrize("header", ["", "not-an-ip", "evil.example", "<script>"])
def test_missing_or_garbage_header_falls_back_to_the_peer(monkeypatch, header):
    monkeypatch.setenv("AOEP_TRUSTED_PROXY_HOPS", "1")
    assert ci.client_ip({"x-forwarded-for": header}, "10.0.0.5") == "10.0.0.5"


def test_zero_hops_ignores_the_header_entirely(monkeypatch):
    monkeypatch.setenv("AOEP_TRUSTED_PROXY_HOPS", "0")
    assert ci.client_ip({"x-forwarded-for": "203.0.113.9"}, "10.0.0.5") == "10.0.0.5"


def test_ipv6_and_port_are_normalised(monkeypatch):
    monkeypatch.setenv("AOEP_TRUSTED_PROXY_HOPS", "1")
    assert ci.client_ip({"x-forwarded-for": "2001:db8::1"}, "x") == "2001:db8::1"
    assert ci.client_ip({"x-forwarded-for": "203.0.113.9:51234"}, "x") == "203.0.113.9"


def test_in_memory_buckets_are_bounded(monkeypatch):
    from aoep_shared import ratelimit as rl

    monkeypatch.setattr(rl, "_MAX_BUCKETS", 50)
    lim = InMemoryTokenBucket(RateLimit(5, 60))
    for i in range(500):
        lim.allow(f"k{i}")
    assert len(lim._buckets) <= 50
