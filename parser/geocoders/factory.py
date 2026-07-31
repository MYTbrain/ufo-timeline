"""Geocoder factory."""

from __future__ import annotations

from ..config import GeocoderConfig
from ..geocode_cache import GeocodeCache
from .base import BaseGeocoder
from .nominatim import NominatimGeocoder


def create_geocoder(config: GeocoderConfig, cache: GeocodeCache) -> BaseGeocoder:
    provider = config.provider.lower()
    if provider == "nominatim":
        return NominatimGeocoder(config, cache)
    raise ValueError(f"Unsupported geocoder provider '{config.provider}'")
