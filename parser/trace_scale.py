"""Trace scaling helpers for render-mode and legend planning."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Iterable


TRACE_RENDER_MODE_INDIVIDUAL = "individual"
TRACE_RENDER_MODE_BUDGETED = "budgeted"
TRACE_RENDER_MODE_AGGREGATE = "aggregate"
TRACE_RENDER_MODE_SUMMARY = "summary"

TRACE_INDIVIDUAL_SEGMENT_THRESHOLD = 1_800
TRACE_BUDGETED_SEGMENT_THRESHOLD = 6_000
TRACE_AGGREGATE_SEGMENT_THRESHOLD = 28_000
TRACE_SUMMARY_SEGMENT_THRESHOLD = TRACE_AGGREGATE_SEGMENT_THRESHOLD + 1

TRACE_RENDER_MODE_THRESHOLDS = {
    TRACE_RENDER_MODE_INDIVIDUAL: TRACE_INDIVIDUAL_SEGMENT_THRESHOLD,
    TRACE_RENDER_MODE_BUDGETED: TRACE_BUDGETED_SEGMENT_THRESHOLD,
    TRACE_RENDER_MODE_AGGREGATE: TRACE_AGGREGATE_SEGMENT_THRESHOLD,
    TRACE_RENDER_MODE_SUMMARY: TRACE_SUMMARY_SEGMENT_THRESHOLD,
}

TRACE_GAP_BUCKETS = (
    {"key": "gap_le_1", "label": "\u22641 day", "max_days": 1},
    {"key": "gap_le_2", "label": "\u22642 days", "max_days": 2},
    {"key": "gap_le_7", "label": "\u22647 days", "max_days": 7},
    {"key": "gap_le_30", "label": "\u226430 days", "max_days": 30},
    {"key": "gap_gt_30", "label": ">30 days", "max_days": None},
)

TRACE_SOURCE_COLOR_PALETTE = (
    "#2f6bff",
    "#f59e0b",
    "#10b981",
    "#ef4444",
    "#14b8a6",
    "#8b5cf6",
    "#f97316",
    "#64748b",
)

DEFAULT_SOURCE_LEGEND_LABELS = (
    "Majestic",
    "MUFON",
    "NUFORC",
    "PhenomenAInon",
    "UFOCAT",
)


@dataclass(frozen=True, slots=True)
class TraceLegendStop:
    value: float
    label: str
    color: str


@dataclass(frozen=True, slots=True)
class TraceLegendSwatch:
    value: str
    label: str
    color: str


@dataclass(frozen=True, slots=True)
class TraceLegendDescriptor:
    mode: str
    title: str
    kind: str
    description: str
    stops: tuple[TraceLegendStop, ...] = ()
    swatches: tuple[TraceLegendSwatch, ...] = ()

    def to_json_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "mode": self.mode,
            "title": self.title,
            "kind": self.kind,
            "description": self.description,
        }
        if self.stops:
            payload["stops"] = [asdict(stop) for stop in self.stops]
        if self.swatches:
            payload["swatches"] = [asdict(swatch) for swatch in self.swatches]
        return payload


def resolve_trace_render_mode(segment_count: int) -> str:
    """Return the planned trace representation for a visible segment count."""
    if isinstance(segment_count, bool) or not isinstance(segment_count, int):
        raise TypeError("segment_count must be an integer")
    if segment_count < 0:
        raise ValueError("segment_count must be non-negative")
    if segment_count <= TRACE_INDIVIDUAL_SEGMENT_THRESHOLD:
        return TRACE_RENDER_MODE_INDIVIDUAL
    if segment_count <= TRACE_BUDGETED_SEGMENT_THRESHOLD:
        return TRACE_RENDER_MODE_BUDGETED
    if segment_count <= TRACE_AGGREGATE_SEGMENT_THRESHOLD:
        return TRACE_RENDER_MODE_AGGREGATE
    return TRACE_RENDER_MODE_SUMMARY


def trace_gap_bucket_for_days(gap_days: int | float) -> str:
    """Return the trace bucket key used by playback/static trace controls."""
    if isinstance(gap_days, bool) or not isinstance(gap_days, (int, float)):
        raise TypeError("gap_days must be numeric")
    if gap_days < 0:
        raise ValueError("gap_days must be non-negative")
    for bucket in TRACE_GAP_BUCKETS:
        max_days = bucket["max_days"]
        if max_days is None or gap_days <= max_days:
            return str(bucket["key"])
    return str(TRACE_GAP_BUCKETS[-1]["key"])


def chronology_legend_descriptor() -> TraceLegendDescriptor:
    return TraceLegendDescriptor(
        mode="chronology",
        title="Chronology",
        kind="gradient",
        description="Older trace segments use cooler colors; newer segments warm up.",
        stops=(
            TraceLegendStop(value=0.0, label="Older", color="#2b6cb0"),
            TraceLegendStop(value=0.16, label="", color="#00a6d6"),
            TraceLegendStop(value=0.34, label="", color="#14b8a6"),
            TraceLegendStop(value=0.52, label="Middle", color="#84cc16"),
            TraceLegendStop(value=0.7, label="", color="#facc15"),
            TraceLegendStop(value=0.86, label="", color="#f97316"),
            TraceLegendStop(value=1.0, label="Newer", color="#e11d48"),
        ),
    )


def playback_recency_legend_descriptor() -> TraceLegendDescriptor:
    return TraceLegendDescriptor(
        mode="playback_recency",
        title="Playback Recency",
        kind="gradient",
        description="Past segments fade back while the current playback window stays bright.",
        stops=(
            TraceLegendStop(value=0.0, label="Past", color="#64748b"),
            TraceLegendStop(value=0.7, label="Recent", color="#38bdf8"),
            TraceLegendStop(value=1.0, label="Current", color="#fde047"),
        ),
    )


def density_legend_descriptor() -> TraceLegendDescriptor:
    return TraceLegendDescriptor(
        mode="density",
        title="Trace Density",
        kind="gradient",
        description="Aggregate trace density moves from muted blue to amber-white.",
        stops=(
            TraceLegendStop(value=0.0, label="Low", color="#1e3a5f"),
            TraceLegendStop(value=0.5, label="Medium", color="#f59e0b"),
            TraceLegendStop(value=1.0, label="High", color="#fff7cc"),
        ),
    )


def source_legend_descriptor(source_labels: Iterable[str] | None = None) -> TraceLegendDescriptor:
    labels = _distinct_labels(DEFAULT_SOURCE_LEGEND_LABELS if source_labels is None else source_labels)
    return TraceLegendDescriptor(
        mode="source",
        title="Trace Source",
        kind="swatches",
        description="Categorical trace colors compare sources with a stable palette.",
        swatches=tuple(
            TraceLegendSwatch(
                value=_source_value(label),
                label=label,
                color=TRACE_SOURCE_COLOR_PALETTE[index % len(TRACE_SOURCE_COLOR_PALETTE)],
            )
            for index, label in enumerate(labels)
        ),
    )


def gap_legend_descriptor() -> TraceLegendDescriptor:
    return TraceLegendDescriptor(
        mode="gap",
        title="Trace Gap Diagnostics",
        kind="swatches",
        description="Diagnostic colors identify the current bucket and trace gaps.",
        swatches=(
            TraceLegendSwatch(value="current_bucket", label="Current bucket", color="#fde047"),
            TraceLegendSwatch(value="short_gap", label="Short gap", color="#38bdf8"),
            TraceLegendSwatch(value="long_gap", label="Long gap", color="#f97316"),
            TraceLegendSwatch(value="unknown_gap", label="Unknown gap", color="#94a3b8"),
        ),
    )


def _distinct_labels(labels: Iterable[str]) -> list[str]:
    distinct: list[str] = []
    seen: set[str] = set()
    for raw_label in labels:
        label = str(raw_label).strip()
        if not label or label in seen:
            continue
        seen.add(label)
        distinct.append(label)
    return distinct


def _source_value(label: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return value or "source"


__all__ = [
    "DEFAULT_SOURCE_LEGEND_LABELS",
    "TRACE_AGGREGATE_SEGMENT_THRESHOLD",
    "TRACE_BUDGETED_SEGMENT_THRESHOLD",
    "TRACE_INDIVIDUAL_SEGMENT_THRESHOLD",
    "TRACE_RENDER_MODE_AGGREGATE",
    "TRACE_RENDER_MODE_BUDGETED",
    "TRACE_RENDER_MODE_INDIVIDUAL",
    "TRACE_RENDER_MODE_SUMMARY",
    "TRACE_RENDER_MODE_THRESHOLDS",
    "TRACE_GAP_BUCKETS",
    "TRACE_SOURCE_COLOR_PALETTE",
    "TRACE_SUMMARY_SEGMENT_THRESHOLD",
    "TraceLegendDescriptor",
    "TraceLegendStop",
    "TraceLegendSwatch",
    "chronology_legend_descriptor",
    "density_legend_descriptor",
    "gap_legend_descriptor",
    "playback_recency_legend_descriptor",
    "resolve_trace_render_mode",
    "source_legend_descriptor",
    "trace_gap_bucket_for_days",
]
