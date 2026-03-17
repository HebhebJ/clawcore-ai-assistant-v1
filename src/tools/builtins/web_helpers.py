"""Helpers for web tool URL validation and normalization."""

from __future__ import annotations

import ipaddress
from urllib.parse import parse_qs, unquote, urlparse

_BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "metadata.google.internal",
    "169.254.169.254",
}


def is_valid_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def is_blocked_host(value: str) -> bool:
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if not host:
        return True
    if host in _BLOCKED_HOSTS or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
    )


def unwrap_search_result_url(value: str) -> str:
    if not value:
        return value
    parsed = urlparse(value)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        query = parse_qs(parsed.query)
        encoded = query.get("uddg", [""])[0]
        if encoded:
            return unquote(encoded)
    return value
