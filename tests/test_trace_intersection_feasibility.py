from __future__ import annotations

import json
import hashlib
import math
from pathlib import Path

from scripts.trace_intersection_feasibility import (
    EARTH_SURFACE_AREA_KM2,
    MIXED_CRAFT,
    Connector,
    EqualAreaGrid,
    analyze_connectors,
    proper_interior_crossing,
)


def connector(
    index: int,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    event_ids: tuple[int, int] | None = None,
    craft: str = "triangle",
    endpoint_crafts: tuple[str, str] | None = None,
    distance_km: float = 100.0,
) -> Connector:
    left_event_id, right_event_id = event_ids or (index * 2 + 1, index * 2 + 2)
    return Connector(
        index=index,
        left_event_id=left_event_id,
        right_event_id=right_event_id,
        from_lat=start[0],
        from_lon=start[1],
        to_lat=end[0],
        to_lon=end[1],
        distance_km=distance_km,
        day_lag=1,
        start_ordinal=730120 + index,
        end_ordinal=730121 + index,
        mid_ordinal=730120 + index,
        mid_year=2000,
        cross_source=True,
        endpoint_crafts=endpoint_crafts or (craft, craft),
        craft_class=craft,
        sources=("majestic", "ufocat"),
        time_bands=(2000,),
        decades=(2000,),
    )


def test_proper_crossing_excludes_endpoints_and_shared_events() -> None:
    horizontal = connector(0, (0.0, -1.0), (0.0, 1.0))
    vertical = connector(1, (-1.0, 0.0), (1.0, 0.0), craft="disc_saucer")
    crossing = proper_interior_crossing(
        horizontal,
        vertical,
        endpoint_buffer_km=1.0,
        minimum_angle_degrees=15.0,
    )
    assert crossing is not None
    assert crossing.lat == 0.0
    assert crossing.lon == 0.0
    assert crossing.angle_degrees == 90.0

    endpoint_touch = connector(2, (-1.0, 1.0), (0.0, 1.0), craft="disc_saucer")
    assert proper_interior_crossing(
        horizontal,
        endpoint_touch,
        endpoint_buffer_km=0.0,
        minimum_angle_degrees=0.0,
    ) is None

    shared_event = connector(
        3,
        (-1.0, 0.0),
        (1.0, 0.0),
        event_ids=(horizontal.left_event_id, 999),
    )
    assert proper_interior_crossing(
        horizontal,
        shared_event,
        endpoint_buffer_km=0.0,
        minimum_angle_degrees=0.0,
    ) is None


def test_endpoint_buffer_and_crossing_angle_gate() -> None:
    horizontal = connector(0, (0.0, -1.0), (0.0, 1.0), distance_km=200.0)
    near_endpoint = connector(1, (-1.0, -0.95), (1.0, -0.95), distance_km=200.0)
    assert proper_interior_crossing(
        horizontal,
        near_endpoint,
        endpoint_buffer_km=10.0,
        minimum_angle_degrees=15.0,
    ) is None

    shallow = connector(2, (-0.1, -1.0), (0.1, 1.0), distance_km=200.0)
    assert proper_interior_crossing(
        horizontal,
        shallow,
        endpoint_buffer_km=0.0,
        minimum_angle_degrees=15.0,
    ) is None


def test_equal_area_grid_has_constant_surface_area() -> None:
    grid = EqualAreaGrid.for_cell_area(2_500.0)
    assert grid.nx > grid.ny
    assert math.isclose(
        grid.actual_cell_area_km2 * grid.nx * grid.ny,
        EARTH_SURFACE_AREA_KM2,
        rel_tol=1e-12,
    )
    equator = grid.bounds_for(grid.cell_for(0.0, 0.0))
    high_latitude = grid.bounds_for(grid.cell_for(70.0, 0.0))
    assert high_latitude["east"] - high_latitude["west"] == equator["east"] - equator["west"]
    assert high_latitude["north"] - high_latitude["south"] > equator["north"] - equator["south"]


def test_analysis_retains_different_craft_crossings() -> None:
    segments = [
        connector(0, (0.0, -1.0), (0.0, 1.0), craft="triangle"),
        connector(1, (-1.0, 0.0), (1.0, 0.0), craft="disc_saucer"),
        connector(
            2,
            (-1.0, 0.5),
            (1.0, 0.5),
            craft=MIXED_CRAFT,
            endpoint_crafts=("disc_saucer", "sphere_orb"),
        ),
    ]
    result = analyze_connectors(
        segments,
        cell_areas_km2=(25_000.0,),
        endpoint_buffer_km=0.0,
        minimum_angle_degrees=15.0,
        broad_phase_cell_degrees=2.0,
    )
    grid = next(iter(result["grids"].values()))
    assert grid["totalCrossings"] == 2
    cell = max(grid["cells"], key=lambda item: item["crossings"])
    assert cell["differentCraftCrossings"] == 1
    assert cell["mixedEndpointCraftCrossings"] == 1
    assert cell["sameCraftCrossings"] == 0
    assert cell["craftPairCounts"]["disc_saucer x triangle"] == 1
    assert cell["craftPairCounts"]["disc_saucer+sphere_orb x triangle"] == 1
    assert cell["craftInvolvementCounts"]["triangle"] == 2
    assert cell["craftInvolvementCounts"]["disc_saucer"] == 2
    assert cell["craftInvolvementCounts"]["sphere_orb"] == 1
    assert cell["homotypicCraftPairCounts"]["disc_saucer x triangle"] == 1
    assert cell["craftAxisConnectorCounts"]["triangle"]["east_west"] == 1
    assert cell["craftAxisConnectorCounts"]["disc_saucer"]["north_south"] == 2
    assert cell["craftAxisConnectorCounts"]["sphere_orb"]["north_south"] == 1


def test_published_feasibility_profiles_are_internally_consistent() -> None:
    artifact_dir = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "trace_intersection_feasibility_v1"
    )
    expected = {
        "strict_25km_7d_buffer1.json": (1.0, 2375),
        "strict_25km_7d_buffer5.json": (5.0, 363),
    }
    for filename, (endpoint_buffer_km, crossing_count) in expected.items():
        payload = json.loads((artifact_dir / filename).read_text(encoding="utf-8"))
        assert payload["schemaVersion"] == 1
        assert payload["claimBoundary"]["observedTravelPaths"] is False
        assert payload["claimBoundary"]["originsOrDestinations"] is False
        assert payload["axisSemantics"]["directed"] is False
        assert payload["temporalSemantics"]["fiveYearBandsAreAnalysisLimit"] is False
        assert payload["temporalSemantics"]["crossingDateSeparationLimited"] is False
        assert payload["profile"]["maximumDistanceKm"] == 25.0
        assert payload["profile"]["maximumDayLag"] == 7
        assert payload["parameters"]["endpointBufferKm"] == endpoint_buffer_km
        assert payload["connectors"]["count"] == 5992
        assert len(payload["connectorRecords"]) == 5992
        assert payload["connectorRecordSchema"] == [
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
        ]
        metrics = payload["intersectionMetrics"]
        assert metrics["proper_interior_crossings"] == crossing_count
        assert len(payload["crossingRecords"]) == crossing_count
        assert (
            metrics["same_craft_crossings"]
            + metrics["different_craft_crossings"]
            + metrics["mixed_endpoint_craft_crossings"]
            == crossing_count
        )
        assert set(payload["grids"]) == {
            "equal_area_24792_km2",
            "equal_area_2497_km2",
            "equal_area_259_km2",
            "equal_area_26_km2",
        }
        assert math.isclose(payload["grids"]["equal_area_26_km2"]["actualCellAreaKm2"], 25.893026)
        for grid in payload["grids"].values():
            assert grid["totalCrossings"] == crossing_count
            assert sum(cell["crossings"] for cell in grid["cells"]) == crossing_count
            assert grid["exposureCellSchema"] == ["cellId", "connectorIndexes"]
            assert len(grid["exposureCells"]) == grid["occupiedExposureCells"]
            assert all(
                0 <= connector_index < payload["connectors"]["count"]
                for _cell_id, connector_indexes in grid["exposureCells"]
                for connector_index in connector_indexes
            )
            for cell in grid["cells"]:
                assert (
                    cell["sameCraftCrossings"]
                    + cell["differentCraftCrossings"]
                    + cell["mixedEndpointCraftCrossings"]
                    == cell["crossings"]
                )


def test_feasibility_manifest_pins_generated_artifacts() -> None:
    root = Path(__file__).resolve().parents[1]
    artifact_dir = root / "data" / "trace_intersection_feasibility_v1"
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))

    def sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    assert manifest["artifactStatus"] == "integrated_local_not_deployed"
    assert manifest["claimBoundary"]["observedTravelPaths"] is False
    builder = root / manifest["builder"]["file"]
    assert sha256(builder) == manifest["builder"]["sha256"]
    for artifact in manifest["artifacts"].values():
        path = artifact_dir / artifact["file"]
        assert path.stat().st_size == artifact["bytes"]
        assert sha256(path) == artifact["sha256"]
