"""Source-specific CSV adapters for the canonical UFO import pipeline."""

from __future__ import annotations

from pathlib import Path

from .base import CsvSourceAdapter
from .majestic import MajesticAdapter
from .mufon import MufonPyAdapter
from .nuforc import NuforcPyAdapter
from .phenomenainon import PhenomenainonAdapter
from .ufocat import UfocatAdapter


ADAPTERS: dict[str, type[CsvSourceAdapter]] = {
    MajesticAdapter.source_file: MajesticAdapter,
    MufonPyAdapter.source_file: MufonPyAdapter,
    NuforcPyAdapter.source_file: NuforcPyAdapter,
    PhenomenainonAdapter.source_file: PhenomenainonAdapter,
    UfocatAdapter.source_file: UfocatAdapter,
}


def adapter_for_path(path: Path) -> CsvSourceAdapter | None:
    adapter_class = ADAPTERS.get(path.name)
    if adapter_class is None:
        return None
    return adapter_class()


__all__ = [
    "ADAPTERS",
    "CsvSourceAdapter",
    "adapter_for_path",
]
