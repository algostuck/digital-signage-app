"""Fixed-window rate limiting (SRS §16: login, player bootstrap, uploads,
event ingestion).

In-memory per-process windows — correct for the single-process dev/test
setup and a safe backstop in production. Multi-instance deployments should
front this with a shared limiter (Redis INCR/EXPIRE drop-in) or an edge/API
gateway; the dependency interface stays the same.
"""

import time
from collections.abc import Callable

from fastapi import Depends, Request

from app.core.config import get_settings
from app.core.errors import RateLimitedError


class FixedWindowLimiter:
    def __init__(self):
        self._windows: dict[str, tuple[int, int]] = {}

    def hit(self, key: str, limit: int, per_seconds: int) -> bool:
        """Returns True when the request is allowed."""
        now = int(time.time())
        window = now - (now % per_seconds)
        start, count = self._windows.get(key, (window, 0))
        if start != window:
            start, count = window, 0
        count += 1
        self._windows[key] = (start, count)
        # Opportunistic cleanup so the map does not grow unbounded.
        if len(self._windows) > 10_000:
            self._windows = {
                k: v for k, v in self._windows.items() if v[0] == window
            }
        return count <= limit

    def reset(self) -> None:
        self._windows.clear()


limiter = FixedWindowLimiter()


def rate_limit(
    scope: str,
    limit_getter: Callable[[], int],
    *,
    per_seconds: int = 60,
    key_param: str | None = None,
):
    """Dependency factory. Keys by client IP, or by a path parameter (e.g.
    device_id) when key_param is given, so device endpoints are limited
    per device rather than per NAT."""

    async def dependency(request: Request) -> None:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return
        if key_param is not None and key_param in request.path_params:
            identity = str(request.path_params[key_param])
        else:
            identity = request.client.host if request.client else "unknown"
        if not limiter.hit(f"{scope}:{identity}", limit_getter(), per_seconds):
            raise RateLimitedError(
                f"Too many {scope} requests; retry in up to {per_seconds} seconds"
            )

    return Depends(dependency)
