"""Base geocoder classes."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any

from ..config import GeocoderConfig
from ..geocode_cache import GeocodeCache


class GeocoderError(RuntimeError):
    """Raised when a geocoder call fails unexpectedly."""


class GeocoderLimitReached(GeocoderError):
    """Raised when the configured per-run geocoder budget has been exhausted."""


@dataclass(slots=True)
class BaseGeocoder:
    config: GeocoderConfig
    cache: GeocodeCache
    provider_id: str
    query_count: int = 0
    cache_hit_count: int = 0
    _last_request_monotonic: float = field(default=0.0, init=False)

    def geocode(self, query: str) -> dict[str, Any] | None:  # pragma: no cover - implemented by subclasses
        raise NotImplementedError

    def _sleep_for_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_monotonic
        minimum = max(self.config.rate_limit_seconds, 0.0)
        if self.query_count > 0 and elapsed < minimum:
            time.sleep(minimum - elapsed)
        self._last_request_monotonic = time.monotonic()
