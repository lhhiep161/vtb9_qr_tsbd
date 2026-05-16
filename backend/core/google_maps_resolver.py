from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

import httpx


ALLOWED_GOOGLE_HOSTS = {
    "maps.app.goo.gl",
    "goo.gl",
    "google.com",
    "www.google.com",
    "maps.google.com",
}


def _is_allowed_google_host(host: str) -> bool:
    host = (host or "").lower().strip(".")
    if host in ALLOWED_GOOGLE_HOSTS:
        return True
    return host.endswith(".google.com")


def _is_private_or_loopback_ip(ip_text: str) -> bool:
    ip = ipaddress.ip_address(ip_text)
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast


def validate_google_maps_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Chỉ hỗ trợ link http/https.")
    host = (parsed.hostname or "").lower()
    if not _is_allowed_google_host(host):
        raise ValueError("Chỉ chấp nhận link Google Maps.")
    if host in {"localhost", "127.0.0.1"}:
        raise ValueError("Không chấp nhận địa chỉ nội bộ.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if _is_private_or_loopback_ip(host):
            raise ValueError("Không chấp nhận địa chỉ mạng nội bộ.")
    return parsed.geturl()


def resolve_google_maps_short_link(url: str, timeout_seconds: float = 8.0) -> str:
    safe_url = validate_google_maps_url(url)
    with httpx.Client(follow_redirects=True, timeout=timeout_seconds) as client:
        response = client.get(safe_url)
        final_url = str(response.url)
    return validate_google_maps_url(final_url)
