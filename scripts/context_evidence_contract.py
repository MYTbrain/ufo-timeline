"""Shared cross-ledger field-cardinality rules for context evidence."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any


# Cross-row validation remains scalar and fail-closed unless a field is named here.
REPEATABLE_CONTEXT_FIELDS = frozenset({"associated_claim"})


def distinct_reviewed_values(
    field_name: str,
    values: Iterable[Any],
    canonicalize: Callable[[Any], bytes],
) -> list[Any]:
    """Return deterministic distinct values, flattening repeatable claim arrays once."""
    candidates: list[Any] = []
    for value in values:
        if field_name in REPEATABLE_CONTEXT_FIELDS and isinstance(value, list):
            candidates.extend(value)
        else:
            candidates.append(value)
    by_canonical = {canonicalize(value): value for value in candidates}
    return [by_canonical[key] for key in sorted(by_canonical)]
