"""Guarded outbound HTTP fetch for data sources (P3 3A-2).

SSRF protections: http(s) only, hostname resolved and every address must be
globally routable (no loopback/private/link-local/reserved/multicast), no
redirect following (a redirect is an error, not a bypass), 10 s timeout and
a hard 1 MiB response cap enforced while streaming.
"""

import ipaddress
import socket
from urllib.parse import urlparse

import httpx

MAX_BYTES = 1 * 1024 * 1024
TIMEOUT_SECONDS = 10.0


class FetchError(Exception):
    """Guard or transport failure — message is safe to store/show."""


BLOCKED_HOST_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home", ".arpa")


def check_url_shape(url: str) -> None:
    """Save-time guard that needs no network: http(s) only, no obviously
    internal hostnames, and any literal IP must be globally routable. The
    resolving check (`assert_public_url`) runs again at send time, so a
    hostname that later resolves to a private address is still refused."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise FetchError("Only http(s) endpoints are allowed")
    host = (parsed.hostname or "").lower()
    if not host:
        raise FetchError("Endpoint has no hostname")
    if host == "localhost" or host.endswith(BLOCKED_HOST_SUFFIXES):
        raise FetchError(f"Endpoint host '{host}' is not a public address")
    try:
        address = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return
    if not address.is_global:
        raise FetchError(f"Endpoint address {address} is not publicly routable")


def assert_public_url(url: str) -> None:
    """Send-time guard: shape check plus DNS resolution; every resolved
    address must be globally routable."""
    check_url_shape(url)
    _assert_public_host(url)


def _assert_public_host(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise FetchError("Only http(s) endpoints are allowed")
    host = parsed.hostname
    if not host:
        raise FetchError("Endpoint has no hostname")
    try:
        infos = socket.getaddrinfo(host, parsed.port or 0, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise FetchError(f"Cannot resolve host '{host}'") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise FetchError(f"Endpoint resolves to a non-public address ({address}) — refused")


async def guarded_fetch(url: str, *, headers: dict | None = None) -> bytes:
    """Fetches at most MAX_BYTES from a public http(s) endpoint.
    Raises FetchError on any guard violation, transport error or non-2xx."""
    _assert_public_host(url)
    try:
        async with (
            httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=False) as client,
            client.stream("GET", url, headers=headers or {}) as response,
        ):
            if response.status_code < 200 or response.status_code >= 300:
                raise FetchError(f"HTTP {response.status_code}")
            body = b""
            async for chunk in response.aiter_bytes():
                body += chunk
                if len(body) > MAX_BYTES:
                    raise FetchError(f"Response exceeds {MAX_BYTES} bytes")
            return body
    except FetchError:
        raise
    except httpx.HTTPError as exc:
        raise FetchError(str(exc)[:300]) from exc
