"""Nominatim-compatible geocoder implementation."""

from __future__ import annotations

from typing import Any

import requests

from .base import BaseGeocoder, GeocoderError, GeocoderLimitReached


class NominatimGeocoder(BaseGeocoder):
    def __init__(self, config, cache) -> None:
        provider_id = f"nominatim:{config.endpoint}"
        super().__init__(config=config, cache=cache, provider_id=provider_id)
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": self.config.user_agent})

    def geocode(self, query: str) -> dict[str, Any] | None:
        cached = self.cache.get(self.provider_id, query)
        if cached is not None:
            self.cache_hit_count += 1
            return cached.get("result")

        if (
            self.config.query_limit_per_run is not None
            and self.query_count >= self.config.query_limit_per_run
        ):
            raise GeocoderLimitReached(
                f"Configured query_limit_per_run={self.config.query_limit_per_run} reached."
            )

        self._sleep_for_rate_limit()
        params: dict[str, Any] = {
            "q": query,
            "format": "jsonv2",
            "limit": 5,
            "addressdetails": 1,
            "accept-language": self.config.language,
        }
        if self.config.email:
            params["email"] = self.config.email
        if self.config.country_codes:
            params["countrycodes"] = ",".join(self.config.country_codes)

        try:
            response = self._session.get(
                self.config.endpoint,
                params=params,
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:  # pragma: no cover - depends on network
            raise GeocoderError(str(exc)) from exc

        self.query_count += 1
        if not payload:
            self.cache.put(self.provider_id, query, None)
            return None

        chosen = payload[0]
        result = {
            "lat": float(chosen["lat"]),
            "lon": float(chosen["lon"]),
            "display_name": chosen.get("display_name"),
            "confidence": chosen.get("importance"),
            "raw": chosen,
            "query_used": query,
        }
        self.cache.put(self.provider_id, query, result)
        return result
