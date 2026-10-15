"""Request authentication helpers for the webhook receiver."""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import threading
import time
from collections import OrderedDict
from collections.abc import Sequence

SIGNATURE_HEADER = "X-SFX-Signature"

IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


def compute_signature(secret: bytes, body: bytes) -> str:
    """base64(HMAC-SHA256(secret, body)) as sent by Splunk in X-SFX-Signature."""
    return base64.b64encode(hmac.new(secret, body, hashlib.sha256).digest()).decode("ascii")


def verify_signature(secret: bytes, body: bytes, provided: str | None) -> bool:
    if not provided:
        return False
    return hmac.compare_digest(compute_signature(secret, body), provided.strip())


class IpAllowlist:
    """Empty allowlist allows everything."""

    def __init__(self, networks: Sequence[IPNetwork]) -> None:
        self._networks = tuple(networks)

    def allows(self, address: str | None) -> bool:
        if not self._networks:
            return True
        if not address:
            return False
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return False
        return any(ip in network for network in self._networks)


class ReplayGuard:
    """Bounded in-process TTL cache that drops Splunk retries / replays of the same event."""

    def __init__(self, ttl_seconds: int, max_entries: int = 10_000) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._seen: OrderedDict[str, float] = OrderedDict()
        self._lock = threading.Lock()

    def is_duplicate(self, key: str | None) -> bool:
        if not key or self._ttl <= 0:
            return False
        now = time.monotonic()
        with self._lock:
            while self._seen and next(iter(self._seen.values())) <= now:
                self._seen.popitem(last=False)
            if key in self._seen:
                return True
            self._seen[key] = now + self._ttl
            if len(self._seen) > self._max:
                self._seen.popitem(last=False)
            return False
