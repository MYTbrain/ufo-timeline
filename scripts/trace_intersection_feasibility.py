"""Build a compact, deterministic trace-intersection feasibility artifact.

This pilot intentionally analyzes the existing Analysis v2 qualified UFO
point-neighbor connectors.  Those connectors are bounded report associations,
not observed travel paths.  The output is therefore descriptive and must not
be interpreted as craft traffic, origins, destinations, or routes.

The builder keeps the analysis small and reproducible:

* no canonical dataset is copied;
* endpoint touches and shared-event connector pairs are excluded;
* proper interior crossings are aggregated into equal-area cells;
* every crossing retains same-craft, cross-craft, or mixed-endpoint semantics;
* raw counts are paired with local crossing opportunities so dense areas do
  not automatically look important; and
* only bounded deterministic examples are emitted for cell drill-down.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


EARTH_RADIUS_KM = 6371.0088
EARTH_SURFACE_AREA_KM2 = 4.0 * math.pi * EARTH_RADIUS_KM * EARTH_RADIUS_KM
DEFAULT_CELL_AREAS_KM2 = (25_000.0, 2_500.0, 258.998811, 25.8998811)
DEFAULT_EXAMPLE_LIMIT = 8
MIXED_CRAFT = "mixed_endpoint_types"
AXIS_BUCKETS = (
    "north_south",
    "northeast_southwest",
    "east_west",
    "northwest_southeast",
)


@dataclass(frozen=True, slots=True)
class QualifiedPoint:
    event_id: int
    lat: float
    lon: float
    ordinal: int
    year: int
    source: str
    craft: str
    five_year_band: int
    decade: int


@dataclass(frozen=True, slots=True)
class Connector:
    index: int
    left_event_id: int
    right_event_id: int
    from_lat: float
    from_lon: float
    to_lat: float
    to_lon: float
    distance_km: float
    day_lag: int
    start_ordinal: int
    end_ordinal: int
    mid_ordinal: int
    mid_year: int
    cross_source: bool
    endpoint_crafts: tuple[str, str]
    craft_class: str
    sources: tuple[str, ...]
    time_bands: tuple[int, ...]
    decades: tuple[int, ...]

    @property
    def event_ids(self) -> tuple[int, int]:
        return self.left_event_id, self.right_event_id


@dataclass(frozen=True, slots=True)
class Crossing:
    lon: float
    lat: float
    left_fraction: float
    right_fraction: float
    angle_degrees: float


@dataclass(frozen=True, slots=True)
class EqualAreaGrid:
    requested_cell_area_km2: float
    nx: int
    ny: int

    @classmethod
    def for_cell_area(cls, cell_area_km2: float) -> "EqualAreaGrid":
        area = float(cell_area_km2)
        if not math.isfinite(area) or area <= 0:
            raise ValueError("cell_area_km2 must be positive and finite")
        target_cells = max(1.0, EARTH_SURFACE_AREA_KM2 / area)
        ny = max(1, round(math.sqrt(target_cells / math.pi)))
        nx = max(1, round(math.pi * ny))
        return cls(requested_cell_area_km2=area, nx=nx, ny=ny)

    @property
    def actual_cell_area_km2(self) -> float:
        return EARTH_SURFACE_AREA_KM2 / (self.nx * self.ny)

    @property
    def key(self) -> str:
        rounded = round(self.actual_cell_area_km2)
        return f"equal_area_{rounded:d}_km2"

    def cell_for(self, lat: float, lon: float) -> tuple[int, int]:
        safe_lat = max(-90.0, min(90.0, float(lat)))
        safe_lon = normalize_longitude(float(lon))
        x = min(self.nx - 1, max(0, int(((safe_lon + 180.0) / 360.0) * self.nx)))
        sin_lat = math.sin(math.radians(safe_lat))
        y = min(self.ny - 1, max(0, int(((sin_lat + 1.0) / 2.0) * self.ny)))
        return x, y

    def bounds_for(self, cell: tuple[int, int]) -> dict[str, float]:
        x, y = cell
        west = -180.0 + (360.0 * x / self.nx)
        east = -180.0 + (360.0 * (x + 1) / self.nx)
        south_sin = -1.0 + (2.0 * y / self.ny)
        north_sin = -1.0 + (2.0 * (y + 1) / self.ny)
        south = math.degrees(math.asin(max(-1.0, min(1.0, south_sin))))
        north = math.degrees(math.asin(max(-1.0, min(1.0, north_sin))))
        return {
            "west": round(west, 8),
            "south": round(south, 8),
            "east": round(east, 8),
            "north": round(north, 8),
        }


@dataclass(slots=True)
class CellAccumulator:
    crossing_count: int = 0
    same_period_crossing_count: int = 0
    same_craft_crossing_count: int = 0
    different_craft_crossing_count: int = 0
    mixed_craft_crossing_count: int = 0
    angle_counts: Counter[str] = field(default_factory=Counter)
    craft_pair_counts: Counter[str] = field(default_factory=Counter)
    craft_involvement_counts: Counter[str] = field(default_factory=Counter)
    homotypic_craft_pair_counts: Counter[str] = field(default_factory=Counter)
    craft_axis_connector_ids: dict[tuple[str, str], set[int]] = field(
        default_factory=lambda: defaultdict(set)
    )
    segment_crossing_counts: Counter[int] = field(default_factory=Counter)
    source_labels: set[str] = field(default_factory=set)
    time_bands: set[int] = field(default_factory=set)
    decades: set[int] = field(default_factory=set)
    examples: list[dict[str, Any]] = field(default_factory=list)


def normalize_longitude(value: float) -> float:
    wrapped = ((value + 180.0) % 360.0) - 180.0
    return 180.0 if wrapped == -180.0 and value > 0 else wrapped


def shortest_wrapped_longitude(from_lon: float, to_lon: float) -> tuple[float, float]:
    start = normalize_longitude(from_lon)
    end = normalize_longitude(to_lon)
    delta = end - start
    if delta > 180.0:
        delta -= 360.0
    elif delta < -180.0:
        delta += 360.0
    return start, start + delta


def haversine_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    lat1 = math.radians(lat_a)
    lat2 = math.radians(lat_b)
    dlat = lat2 - lat1
    dlon = math.radians(normalize_longitude(lon_b - lon_a))
    value = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(max(0.0, value))))


def _cross_2d(ax: float, ay: float, bx: float, by: float) -> float:
    return ax * by - ay * bx


def _aligned_segment_longitudes(first: Connector, second: Connector) -> tuple[float, float, float, float]:
    first_from, first_to = shortest_wrapped_longitude(first.from_lon, first.to_lon)
    second_from, second_to = shortest_wrapped_longitude(second.from_lon, second.to_lon)
    first_mid = (first_from + first_to) / 2.0
    second_mid = (second_from + second_to) / 2.0
    shift = round((first_mid - second_mid) / 360.0) * 360.0
    return first_from, first_to, second_from + shift, second_to + shift


def proper_interior_crossing(
    first: Connector,
    second: Connector,
    *,
    endpoint_buffer_km: float,
    minimum_angle_degrees: float,
    epsilon: float = 1e-10,
) -> Crossing | None:
    """Return a render-equivalent proper crossing, excluding endpoint effects."""
    if set(first.event_ids).intersection(second.event_ids):
        return None

    first_from_lon, first_to_lon, second_from_lon, second_to_lon = _aligned_segment_longitudes(first, second)
    px, py = first_from_lon, first.from_lat
    qx, qy = second_from_lon, second.from_lat
    rx, ry = first_to_lon - first_from_lon, first.to_lat - first.from_lat
    sx, sy = second_to_lon - second_from_lon, second.to_lat - second.from_lat
    denominator = _cross_2d(rx, ry, sx, sy)
    if abs(denominator) <= epsilon:
        return None

    qpx, qpy = qx - px, qy - py
    first_fraction = _cross_2d(qpx, qpy, sx, sy) / denominator
    second_fraction = _cross_2d(qpx, qpy, rx, ry) / denominator
    if not (epsilon < first_fraction < 1.0 - epsilon and epsilon < second_fraction < 1.0 - epsilon):
        return None

    first_length = max(first.distance_km, epsilon)
    second_length = max(second.distance_km, epsilon)
    if endpoint_buffer_km > 0:
        if min(first_fraction, 1.0 - first_fraction) * first_length < endpoint_buffer_km:
            return None
        if min(second_fraction, 1.0 - second_fraction) * second_length < endpoint_buffer_km:
            return None

    lon = px + first_fraction * rx
    lat = py + first_fraction * ry
    cos_lat = max(0.05, abs(math.cos(math.radians(lat))))
    first_x, first_y = rx * cos_lat, ry
    second_x, second_y = sx * cos_lat, sy
    first_norm = math.hypot(first_x, first_y)
    second_norm = math.hypot(second_x, second_y)
    if first_norm <= epsilon or second_norm <= epsilon:
        return None
    cosine = max(-1.0, min(1.0, (first_x * second_x + first_y * second_y) / (first_norm * second_norm)))
    angle = math.degrees(math.acos(cosine))
    angle = min(angle, 180.0 - angle)
    if angle + epsilon < minimum_angle_degrees:
        return None

    return Crossing(
        lon=normalize_longitude(lon),
        lat=lat,
        left_fraction=first_fraction,
        right_fraction=second_fraction,
        angle_degrees=angle,
    )


def _angle_bucket(angle_degrees: float) -> str:
    if angle_degrees < 30.0:
        return "15_to_30"
    if angle_degrees < 60.0:
        return "30_to_60"
    return "60_to_90"


def _craft_pair(first: Connector, second: Connector) -> tuple[str, str]:
    if first.craft_class == MIXED_CRAFT or second.craft_class == MIXED_CRAFT:
        return "mixed_or_untyped", "mixed_or_untyped"
    return tuple(sorted((first.craft_class, second.craft_class)))


def _connector_craft_signature(connector: Connector) -> str:
    if connector.craft_class != MIXED_CRAFT:
        return connector.craft_class
    return "+".join(connector.endpoint_crafts)


def _craft_pair_key(first: Connector, second: Connector) -> str:
    left, right = sorted((_connector_craft_signature(first), _connector_craft_signature(second)))
    return f"{left} x {right}"


def _homotypic_craft_pair_key(first: Connector, second: Connector) -> str | None:
    if first.craft_class == MIXED_CRAFT or second.craft_class == MIXED_CRAFT:
        return None
    left, right = sorted((first.craft_class, second.craft_class))
    return f"{left} x {right}"


def _same_period(first: Connector, second: Connector) -> bool:
    return bool(set(first.time_bands).intersection(second.time_bands))


def _connector_axis_bucket(connector: Connector) -> str:
    """Return an undirected local axis; this intentionally encodes no heading."""
    start_lon, end_lon = shortest_wrapped_longitude(connector.from_lon, connector.to_lon)
    mean_lat = (connector.from_lat + connector.to_lat) / 2.0
    east = (end_lon - start_lon) * math.cos(math.radians(mean_lat))
    north = connector.to_lat - connector.from_lat
    axis_degrees = math.degrees(math.atan2(east, north)) % 180.0
    if axis_degrees < 22.5 or axis_degrees >= 157.5:
        return "north_south"
    if axis_degrees < 67.5:
        return "northeast_southwest"
    if axis_degrees < 112.5:
        return "east_west"
    return "northwest_southeast"


def _craft_axis_counts(accumulator: CellAccumulator) -> dict[str, dict[str, int]]:
    output: dict[str, dict[str, int]] = {}
    crafts = sorted({craft for craft, _axis in accumulator.craft_axis_connector_ids})
    for craft in crafts:
        counts = {
            axis: len(accumulator.craft_axis_connector_ids.get((craft, axis), set()))
            for axis in AXIS_BUCKETS
        }
        output[craft] = {axis: count for axis, count in counts.items() if count}
    return output


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inverse_codebook(values: Sequence[str]) -> dict[int, str]:
    return {index: str(value) for index, value in enumerate(values)}


def load_qualified_points(points_path: Path, manifest: Mapping[str, Any]) -> dict[int, QualifiedPoint]:
    artifact = manifest["artifacts"]["ufoSpatialPoints"]
    schema = list(artifact["rowSchema"])
    rows = json.loads(points_path.read_text(encoding="utf-8"))
    if len(rows) != int(artifact["rowCount"]):
        raise ValueError("ufo spatial point row count does not match the manifest")
    if _sha256(points_path) != artifact["sha256"]:
        raise ValueError("ufo spatial point hash does not match the manifest")

    fields = {name: index for index, name in enumerate(schema)}
    codes = manifest["codes"]["ufoSpatialPoints"]
    source_codes = _inverse_codebook(codes["source"])
    craft_codes = _inverse_codebook(codes["craft"])
    output: dict[int, QualifiedPoint] = {}
    for row in rows:
        event_id = int(row[fields["eventId"]])
        output[event_id] = QualifiedPoint(
            event_id=event_id,
            lat=float(row[fields["lat"]]),
            lon=float(row[fields["lon"]]),
            ordinal=int(row[fields["ordinal"]]),
            year=int(row[fields["year"]]),
            source=source_codes[int(row[fields["sourceCode"]])],
            craft=craft_codes[int(row[fields["craftCode"]])],
            five_year_band=int(row[fields["fiveYearBand"]]),
            decade=int(row[fields["decade"]]),
        )
    return output


def load_neighbor_connectors(
    neighbors_path: Path,
    manifest: Mapping[str, Any],
    points: Mapping[int, QualifiedPoint],
    *,
    maximum_distance_km: float,
    maximum_day_lag: int,
) -> tuple[list[Connector], dict[str, int]]:
    artifact = manifest["artifacts"]["ufoPointNeighbors"]
    schema = list(artifact["rowSchema"])
    rows = json.loads(neighbors_path.read_text(encoding="utf-8"))
    if len(rows) != int(artifact["rowCount"]):
        raise ValueError("ufo point-neighbor row count does not match the manifest")
    if _sha256(neighbors_path) != artifact["sha256"]:
        raise ValueError("ufo point-neighbor hash does not match the manifest")

    fields = {name: index for index, name in enumerate(schema)}
    counters: Counter[str] = Counter()
    connectors: list[Connector] = []
    for row in rows:
        counters["input_rows"] += 1
        distance_km = int(row[fields["distanceDecameters"]]) / 100.0
        day_lag = int(row[fields["dayLag"]])
        if distance_km > maximum_distance_km:
            counters["excluded_distance"] += 1
            continue
        if day_lag > maximum_day_lag:
            counters["excluded_day_lag"] += 1
            continue
        left_id = int(row[fields["leftEventId"]])
        right_id = int(row[fields["rightEventId"]])
        left = points.get(left_id)
        right = points.get(right_id)
        if left is None or right is None:
            counters["excluded_missing_endpoint"] += 1
            continue
        if left_id == right_id or distance_km <= 0:
            counters["excluded_degenerate"] += 1
            continue
        from_lon, to_lon = shortest_wrapped_longitude(left.lon, right.lon)
        endpoint_crafts = tuple(sorted((left.craft, right.craft)))
        craft_class = left.craft if left.craft == right.craft else MIXED_CRAFT
        connectors.append(
            Connector(
                index=len(connectors),
                left_event_id=left_id,
                right_event_id=right_id,
                from_lat=left.lat,
                from_lon=from_lon,
                to_lat=right.lat,
                to_lon=to_lon,
                distance_km=distance_km,
                day_lag=day_lag,
                start_ordinal=min(left.ordinal, right.ordinal),
                end_ordinal=max(left.ordinal, right.ordinal),
                mid_ordinal=round((left.ordinal + right.ordinal) / 2.0),
                mid_year=round((left.year + right.year) / 2.0),
                cross_source=bool(row[fields["crossSource"]]),
                endpoint_crafts=endpoint_crafts,
                craft_class=craft_class,
                sources=tuple(sorted({left.source, right.source})),
                time_bands=tuple(sorted({left.five_year_band, right.five_year_band})),
                decades=tuple(sorted({left.decade, right.decade})),
            )
        )
        counters["included"] += 1
        counters[f"craft_class:{craft_class}"] += 1
    return connectors, dict(sorted(counters.items()))


def _broad_phase_cells(connector: Connector, cell_size_degrees: float) -> Iterable[tuple[int, int]]:
    min_lat = min(connector.from_lat, connector.to_lat)
    max_lat = max(connector.from_lat, connector.to_lat)
    min_lon = min(connector.from_lon, connector.to_lon)
    max_lon = max(connector.from_lon, connector.to_lon)
    min_lat_cell = math.floor((min_lat + 90.0) / cell_size_degrees)
    max_lat_cell = math.floor((max_lat + 90.0) / cell_size_degrees)
    for world_shift in (-360.0, 0.0, 360.0):
        min_lon_cell = math.floor((min_lon + world_shift) / cell_size_degrees)
        max_lon_cell = math.floor((max_lon + world_shift) / cell_size_degrees)
        for lat_cell in range(min_lat_cell, max_lat_cell + 1):
            for lon_cell in range(min_lon_cell, max_lon_cell + 1):
                yield lat_cell, lon_cell


def _candidate_pairs(connectors: Sequence[Connector], cell_size_degrees: float) -> tuple[list[tuple[int, int]], dict[str, int]]:
    buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    for connector in connectors:
        for cell in _broad_phase_cells(connector, cell_size_degrees):
            buckets[cell].append(connector.index)

    seen: set[int] = set()
    pairs: list[tuple[int, int]] = []
    raw_bucket_pairs = 0
    for indexes in buckets.values():
        unique = sorted(set(indexes))
        for offset, left in enumerate(unique):
            for right in unique[offset + 1 :]:
                raw_bucket_pairs += 1
                key = (left << 32) | right
                if key in seen:
                    continue
                seen.add(key)
                pairs.append((left, right))
    return pairs, {
        "broad_phase_cells": len(buckets),
        "raw_bucket_pairs": raw_bucket_pairs,
        "unique_candidate_pairs": len(pairs),
    }


def _trimmed_fraction(connector: Connector, endpoint_buffer_km: float) -> tuple[float, float] | None:
    if connector.distance_km <= 0:
        return None
    fraction = max(0.0, endpoint_buffer_km / connector.distance_km)
    if fraction >= 0.5:
        return None
    return fraction, 1.0 - fraction


def _connector_cells(connector: Connector, grid: EqualAreaGrid, endpoint_buffer_km: float) -> set[tuple[int, int]]:
    fractions = _trimmed_fraction(connector, endpoint_buffer_km)
    if fractions is None:
        return set()
    start_fraction, end_fraction = fractions
    start_lon, end_lon = shortest_wrapped_longitude(connector.from_lon, connector.to_lon)
    start_sin = math.sin(math.radians(connector.from_lat))
    end_sin = math.sin(math.radians(connector.to_lat))
    delta_x_cells = abs((end_lon - start_lon) / 360.0 * grid.nx)
    delta_y_cells = abs((end_sin - start_sin) / 2.0 * grid.ny)
    steps = max(2, math.ceil(max(delta_x_cells, delta_y_cells) * 3.0))
    output: set[tuple[int, int]] = set()
    for index in range(steps + 1):
        ratio = index / steps
        fraction = start_fraction + (end_fraction - start_fraction) * ratio
        lat = connector.from_lat + (connector.to_lat - connector.from_lat) * fraction
        lon = start_lon + (end_lon - start_lon) * fraction
        output.add(grid.cell_for(lat, lon))
    return output


def _valid_opportunities(segment_indexes: set[int], connectors: Sequence[Connector]) -> int:
    count = len(segment_indexes)
    if count < 2:
        return 0
    total = count * (count - 1) // 2
    endpoint_counts: Counter[int] = Counter()
    for index in segment_indexes:
        endpoint_counts.update(connectors[index].event_ids)
    shared_endpoint_pairs = sum(value * (value - 1) // 2 for value in endpoint_counts.values() if value > 1)
    return max(0, total - shared_endpoint_pairs)


def _screening_tier(
    *,
    crossing_count: int,
    unique_segments: int,
    time_band_count: int,
    dominant_trace_share: float,
) -> str:
    if crossing_count >= 20 and unique_segments >= 10 and time_band_count >= 3 and dominant_trace_share <= 0.35:
        return "repeated_candidate"
    if crossing_count >= 5 and unique_segments >= 4 and dominant_trace_share <= 0.60:
        return "limited_candidate"
    return "descriptive_only"


def analyze_connectors(
    connectors: Sequence[Connector],
    *,
    cell_areas_km2: Sequence[float] = DEFAULT_CELL_AREAS_KM2,
    endpoint_buffer_km: float = 1.0,
    minimum_angle_degrees: float = 15.0,
    broad_phase_cell_degrees: float = 2.0,
    example_limit: int = DEFAULT_EXAMPLE_LIMIT,
) -> dict[str, Any]:
    if endpoint_buffer_km < 0:
        raise ValueError("endpoint_buffer_km must be non-negative")
    if not 0 <= minimum_angle_degrees < 90:
        raise ValueError("minimum_angle_degrees must be in [0, 90)")
    grids = [EqualAreaGrid.for_cell_area(area) for area in cell_areas_km2]
    accumulators: dict[str, dict[tuple[int, int], CellAccumulator]] = {
        grid.key: defaultdict(CellAccumulator) for grid in grids
    }
    exposures: dict[str, dict[tuple[int, int], set[int]]] = {
        grid.key: defaultdict(set) for grid in grids
    }
    crossing_records: list[list[Any]] = []

    for connector in connectors:
        for grid in grids:
            for cell in _connector_cells(connector, grid, endpoint_buffer_km):
                exposures[grid.key][cell].add(connector.index)

    candidate_pairs, broad_phase_metrics = _candidate_pairs(connectors, broad_phase_cell_degrees)
    metrics: Counter[str] = Counter()
    metrics.update(broad_phase_metrics)
    for left_index, right_index in candidate_pairs:
        first = connectors[left_index]
        second = connectors[right_index]
        if set(first.event_ids).intersection(second.event_ids):
            metrics["shared_endpoint_pairs_excluded"] += 1
            continue
        crossing = proper_interior_crossing(
            first,
            second,
            endpoint_buffer_km=endpoint_buffer_km,
            minimum_angle_degrees=minimum_angle_degrees,
        )
        if crossing is None:
            metrics["non_crossing_candidate_pairs"] += 1
            continue
        metrics["proper_interior_crossings"] += 1
        craft_pair = _craft_pair_key(first, second)
        homotypic_craft_pair = _homotypic_craft_pair_key(first, second)
        involved_crafts = set(first.endpoint_crafts).union(second.endpoint_crafts)
        same_period = _same_period(first, second)
        crossing_records.append(
            [
                round(crossing.lat, 6),
                round(crossing.lon, 6),
                first.index,
                second.index,
                round(crossing.angle_degrees, 2),
                int(same_period),
            ]
        )
        if first.craft_class == MIXED_CRAFT or second.craft_class == MIXED_CRAFT:
            metrics["mixed_endpoint_craft_crossings"] += 1
        elif first.craft_class == second.craft_class:
            metrics["same_craft_crossings"] += 1
        else:
            metrics["different_craft_crossings"] += 1
        for grid in grids:
            cell = grid.cell_for(crossing.lat, crossing.lon)
            accumulator = accumulators[grid.key][cell]
            accumulator.crossing_count += 1
            accumulator.same_period_crossing_count += int(same_period)
            accumulator.angle_counts[_angle_bucket(crossing.angle_degrees)] += 1
            accumulator.craft_pair_counts[craft_pair] += 1
            accumulator.craft_involvement_counts.update(involved_crafts)
            for connector in (first, second):
                axis = _connector_axis_bucket(connector)
                for craft in set(connector.endpoint_crafts):
                    accumulator.craft_axis_connector_ids[(craft, axis)].add(connector.index)
            if homotypic_craft_pair:
                accumulator.homotypic_craft_pair_counts[homotypic_craft_pair] += 1
            accumulator.segment_crossing_counts[first.index] += 1
            accumulator.segment_crossing_counts[second.index] += 1
            accumulator.source_labels.update(first.sources)
            accumulator.source_labels.update(second.sources)
            accumulator.time_bands.update(first.time_bands)
            accumulator.time_bands.update(second.time_bands)
            accumulator.decades.update(first.decades)
            accumulator.decades.update(second.decades)
            if first.craft_class == MIXED_CRAFT or second.craft_class == MIXED_CRAFT:
                accumulator.mixed_craft_crossing_count += 1
            elif first.craft_class == second.craft_class:
                accumulator.same_craft_crossing_count += 1
            else:
                accumulator.different_craft_crossing_count += 1
            if len(accumulator.examples) < example_limit:
                accumulator.examples.append(
                    {
                        "lat": round(crossing.lat, 6),
                        "lon": round(crossing.lon, 6),
                        "angleDegrees": round(crossing.angle_degrees, 2),
                        "firstConnector": first.index,
                        "secondConnector": second.index,
                        "craftPair": craft_pair,
                        "sameFiveYearBand": same_period,
                    }
                )

    grid_payloads: dict[str, Any] = {}
    for grid in grids:
        grid_accumulators = accumulators[grid.key]
        grid_exposures = exposures[grid.key]
        total_crossings = sum(cell.crossing_count for cell in grid_accumulators.values())
        total_opportunities = sum(
            _valid_opportunities(segment_indexes, connectors)
            for segment_indexes in grid_exposures.values()
        )
        global_rate = total_crossings / total_opportunities if total_opportunities else 0.0
        cells: list[dict[str, Any]] = []
        for cell_key, accumulator in grid_accumulators.items():
            segment_indexes = grid_exposures.get(cell_key, set())
            opportunities = _valid_opportunities(segment_indexes, connectors)
            expected = opportunities * global_rate
            rate_per_million = accumulator.crossing_count / opportunities * 1_000_000 if opportunities else 0.0
            lift = (accumulator.crossing_count + 0.5) / (expected + 0.5) if expected or accumulator.crossing_count else 0.0
            max_trace_crossings = max(accumulator.segment_crossing_counts.values(), default=0)
            dominant_trace_share = max_trace_crossings / accumulator.crossing_count if accumulator.crossing_count else 0.0
            unique_segments = len(accumulator.segment_crossing_counts)
            bounds = grid.bounds_for(cell_key)
            cells.append(
                {
                    "cellId": f"{cell_key[0]}:{cell_key[1]}",
                    "bounds": bounds,
                    "center": {
                        "lat": round((bounds["south"] + bounds["north"]) / 2.0, 8),
                        "lon": round((bounds["west"] + bounds["east"]) / 2.0, 8),
                    },
                    "crossings": accumulator.crossing_count,
                    "expectedFromLocalOpportunity": round(expected, 6),
                    "opportunityNormalizedLift": round(lift, 6),
                    "crossingsPerMillionOpportunities": round(rate_per_million, 6),
                    "localConnectorOpportunities": opportunities,
                    "exposedConnectors": len(segment_indexes),
                    "uniqueCrossingConnectors": unique_segments,
                    "dominantConnectorShare": round(dominant_trace_share, 6),
                    "sameFiveYearBandCrossings": accumulator.same_period_crossing_count,
                    "fiveYearBandCount": len(accumulator.time_bands),
                    "decadeCount": len(accumulator.decades),
                    "sourceCount": len(accumulator.source_labels),
                    "sameCraftCrossings": accumulator.same_craft_crossing_count,
                    "differentCraftCrossings": accumulator.different_craft_crossing_count,
                    "mixedEndpointCraftCrossings": accumulator.mixed_craft_crossing_count,
                    "craftPairCounts": dict(accumulator.craft_pair_counts.most_common()),
                    "craftInvolvementCounts": dict(accumulator.craft_involvement_counts.most_common()),
                    "homotypicCraftPairCounts": dict(accumulator.homotypic_craft_pair_counts.most_common()),
                    "craftAxisConnectorCounts": _craft_axis_counts(accumulator),
                    "angleCounts": dict(sorted(accumulator.angle_counts.items())),
                    "screeningTier": _screening_tier(
                        crossing_count=accumulator.crossing_count,
                        unique_segments=unique_segments,
                        time_band_count=len(accumulator.time_bands),
                        dominant_trace_share=dominant_trace_share,
                    ),
                    "examples": accumulator.examples,
                }
            )
        cells.sort(key=lambda item: (-item["opportunityNormalizedLift"], -item["crossings"], item["cellId"]))
        grid_payloads[grid.key] = {
            "requestedCellAreaKm2": grid.requested_cell_area_km2,
            "actualCellAreaKm2": round(grid.actual_cell_area_km2, 6),
            "dimensions": {"longitudeCells": grid.nx, "equalAreaLatitudeBands": grid.ny},
            "occupiedExposureCells": len(grid_exposures),
            "crossingCells": len(cells),
            "totalCrossings": total_crossings,
            "totalLocalConnectorOpportunities": total_opportunities,
            "globalCrossingsPerMillionOpportunities": round(global_rate * 1_000_000, 6),
            "exposureCellSchema": ["cellId", "connectorIndexes"],
            "exposureCells": [
                [f"{cell_key[0]}:{cell_key[1]}", sorted(segment_indexes)]
                for cell_key, segment_indexes in sorted(grid_exposures.items())
            ],
            "cells": cells,
        }

    connector_crafts = Counter(connector.craft_class for connector in connectors)
    connector_signatures = Counter(_connector_craft_signature(connector) for connector in connectors)
    connector_endpoint_pairs = Counter(" x ".join(connector.endpoint_crafts) for connector in connectors)
    return {
        "schemaVersion": 1,
        "analysisRole": "qualified_report_neighbor_connector_intersection_feasibility",
        "claimBoundary": {
            "observedTravelPaths": False,
            "originsOrDestinations": False,
            "causalInference": False,
            "chronologyTraceParity": False,
            "description": (
                "Interior crossings of bounded qualified report-neighbor connectors. "
                "Connectors are exploratory associations, not observed craft movement."
            ),
        },
        "axisSemantics": {
            "directed": False,
            "description": (
                "Unique crossing connectors are grouped by local undirected axis. "
                "Axis bins do not imply heading, origin, or destination."
            ),
            "buckets": list(AXIS_BUCKETS),
        },
        "temporalSemantics": {
            "fiveYearBandsAreAnalysisLimit": False,
            "crossingDateSeparationLimited": False,
            "description": (
                "Five-year bands summarize recurrence. The default crossing analysis spans all "
                "qualified catalog years; runtime filters may constrain connector dates or their separation."
            ),
        },
        "parameters": {
            "endpointBufferKm": endpoint_buffer_km,
            "minimumCrossingAngleDegrees": minimum_angle_degrees,
            "broadPhaseCellDegrees": broad_phase_cell_degrees,
            "exampleLimitPerCell": example_limit,
        },
        "connectors": {
            "count": len(connectors),
            "craftClassCounts": dict(connector_crafts.most_common()),
            "craftSignatureCounts": dict(connector_signatures.most_common()),
            "endpointCraftPairCounts": dict(connector_endpoint_pairs.most_common()),
        },
        "connectorRecordSchema": [
            "index",
            "leftEventId",
            "rightEventId",
            "startOrdinal",
            "endOrdinal",
            "midOrdinal",
            "midYear",
            "craftClass",
            "endpointCrafts",
            "axis",
            "sources",
            "timeBands",
        ],
        "connectorRecords": [
            [
                connector.index,
                connector.left_event_id,
                connector.right_event_id,
                connector.start_ordinal,
                connector.end_ordinal,
                connector.mid_ordinal,
                connector.mid_year,
                connector.craft_class,
                list(connector.endpoint_crafts),
                _connector_axis_bucket(connector),
                list(connector.sources),
                list(connector.time_bands),
            ]
            for connector in connectors
        ],
        "crossingRecordSchema": [
            "lat",
            "lon",
            "firstConnectorIndex",
            "secondConnectorIndex",
            "angleDegrees",
            "sameFiveYearBand",
        ],
        "crossingRecords": crossing_records,
        "intersectionMetrics": dict(sorted(metrics.items())),
        "grids": grid_payloads,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("webapp/static_public/data/analysis_v2/manifest.json"),
    )
    parser.add_argument(
        "--points",
        type=Path,
        default=Path("webapp/static_public/data/analysis_v2/ufo_spatial_points_v2.json"),
    )
    parser.add_argument(
        "--neighbors",
        type=Path,
        default=Path("webapp/static_public/data/analysis_v2/ufo_point_neighbors_v1.json"),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--maximum-distance-km", type=float, default=25.0)
    parser.add_argument("--maximum-day-lag", type=int, default=7)
    parser.add_argument("--endpoint-buffer-km", type=float, default=1.0)
    parser.add_argument("--minimum-angle-degrees", type=float, default=15.0)
    parser.add_argument("--broad-phase-cell-degrees", type=float, default=2.0)
    parser.add_argument(
        "--cell-area-km2",
        type=float,
        action="append",
        dest="cell_areas_km2",
        help="Repeat for each equal-area grid resolution.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    points = load_qualified_points(args.points, manifest)
    connectors, selection = load_neighbor_connectors(
        args.neighbors,
        manifest,
        points,
        maximum_distance_km=args.maximum_distance_km,
        maximum_day_lag=args.maximum_day_lag,
    )
    result = analyze_connectors(
        connectors,
        cell_areas_km2=args.cell_areas_km2 or DEFAULT_CELL_AREAS_KM2,
        endpoint_buffer_km=args.endpoint_buffer_km,
        minimum_angle_degrees=args.minimum_angle_degrees,
        broad_phase_cell_degrees=args.broad_phase_cell_degrees,
    )
    result["profile"] = {
        "maximumDistanceKm": args.maximum_distance_km,
        "maximumDayLag": args.maximum_day_lag,
        "selection": selection,
    }
    result["provenance"] = {
        "analysisManifest": {"path": str(args.manifest), "sha256": _sha256(args.manifest)},
        "qualifiedPoints": {"path": str(args.points), "sha256": _sha256(args.points)},
        "qualifiedNeighbors": {"path": str(args.neighbors), "sha256": _sha256(args.neighbors)},
    }

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
            encoding="utf-8",
        )
    summary = {
        "profile": result["profile"],
        "connectors": result["connectors"],
        "intersectionMetrics": result["intersectionMetrics"],
        "grids": {
            key: {
                name: value
                for name, value in grid.items()
                if name not in {"cells", "exposureCells"}
            }
            for key, grid in result["grids"].items()
        },
        "output": str(args.output) if args.output else None,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
