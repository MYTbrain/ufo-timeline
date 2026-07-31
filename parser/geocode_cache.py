"""Simple provider-aware geocode cache stored as JSONL."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .utils import collapse_whitespace, ensure_parent_dir


@dataclass(slots=True)
class GeocodeCache:
    path: Path
    _records: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    key = (record["provider_id"], record["normalized_query"])
                    self._records[key] = record

    @staticmethod
    def normalize_query(query: str) -> str:
        return collapse_whitespace(query).lower()

    def get(self, provider_id: str, query: str) -> dict[str, Any] | None:
        return self._records.get((provider_id, self.normalize_query(query)))

    def put(self, provider_id: str, query: str, result: dict[str, Any] | None) -> None:
        normalized_query = self.normalize_query(query)
        record = {
            "provider_id": provider_id,
            "query": query,
            "normalized_query": normalized_query,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "result": result,
        }
        self._records[(provider_id, normalized_query)] = record
        ensure_parent_dir(self.path)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")
