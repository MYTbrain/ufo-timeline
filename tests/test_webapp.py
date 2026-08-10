import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from webapp.app import create_app


def _extract_js_function_body(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[brace + 1:index]
    raise AssertionError(f"Could not extract JS function body: {name}")


def _normalize_js_body(body: str) -> str:
    return re.sub(r"\s+", "", body)


def test_webapp_serves_index_and_runtime_config(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    reports_dir = data_dir / "reports"
    reports_dir.mkdir(parents=True)
    (data_dir / "map_events.json").write_text("[]", encoding="utf-8")
    (data_dir / "normalized_events.json").write_text("[]", encoding="utf-8")
    (reports_dir / "unresolved_locations.json").write_text("[]", encoding="utf-8")

    config_path = tmp_path / "config.yaml"
    normalized_path = str(data_dir / "normalized_events.json").replace("\\", "/")
    map_path = str(data_dir / "map_events.json").replace("\\", "/")
    unresolved_json = str(reports_dir / "unresolved_locations.json").replace("\\", "/")
    unresolved_csv = str(reports_dir / "unresolved_locations.csv").replace("\\", "/")
    parse_failures = str(reports_dir / "parse_failures.jsonl").replace("\\", "/")
    geocode_failures = str(reports_dir / "geocode_failures.jsonl").replace("\\", "/")
    overrides_path = str(data_dir / "manual_location_overrides.json").replace("\\", "/")
    cache_path = str(tmp_path / "cache.jsonl").replace("\\", "/")
    config_path.write_text(
        f"""
inputs:
  files: []
outputs:
  normalized_events: {normalized_path}
  map_events: {map_path}
  unresolved_locations_json: {unresolved_json}
  unresolved_locations_csv: {unresolved_csv}
  parse_failures: {parse_failures}
  geocode_failures: {geocode_failures}
  manual_overrides: {overrides_path}
cache:
  geocode_cache: {cache_path}
geocoder:
  enabled: false
  provider: nominatim
  endpoint: https://example.com/search
  user_agent: tests
  rate_limit_seconds: 0.0
  timeout_seconds: 1
  description_fallback_enabled: true
web:
  host: 127.0.0.1
  port: 8000
  tile_url: https://tiles.example.com/{{z}}/{{x}}/{{y}}.png
  tile_attribution: example attribution
  initial_center: [30, 10]
  initial_zoom: 3
""",
        encoding="utf-8",
    )

    monkeypatch.setenv("UFO_TIMELINE_CONFIG", str(config_path))

    client = TestClient(create_app())
    response = client.get("/")
    config_response = client.get("/api/app-config")
    data_response = client.get("/data/map_events.json")

    assert response.status_code == 200
    assert "UFO Timeline World Map" in response.text
    assert 'id="toggle-area-selection"' in response.text
    assert 'id="area-selection-panel"' in response.text
    assert 'id="results-area-filter-indicator"' in response.text

    assert config_response.status_code == 200
    payload = config_response.json()
    assert payload["tileUrl"] == "https://tiles.example.com/{z}/{x}/{y}.png"
    assert payload["initialZoom"] == 3

    assert data_response.status_code == 200
    assert json.loads(data_response.text) == []


def test_static_app_validates_packed_points_against_canonical_primary_catalog():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")

    assert "Legacy packed-point parity validation is skipped" not in app_js
    assert "checkedAgainstCanonicalPrimaryCatalog" in app_js
    assert "validatePackedPointsCatalogParity({ sampleLimit: 256 })" in app_js


def test_canonical_primary_catalog_ingests_summary_shards_not_legacy_catalog_shards():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")

    assert 'runtime.catalogSource === "canonical_web"' in app_js
    assert "ensureCanonicalSummaryShardLoaded(shard && shard.id ? shard.id : index)" in app_js
    assert 'fetchJson("./data/catalog_shards/" + shard.file' in app_js


def test_canonical_summary_shards_prefer_existing_gzip_siblings_when_supported():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")

    assert "browserCanDecodeGzipJson" in app_js
    assert "new DecompressionStream(\"gzip\")" in app_js
    assert "fetchJsonPreferGzipWithRetry" in app_js
    assert "const gzipShardUrl = shardUrl ? shardUrl + \".gz\" : \"\";" in app_js
    assert "falling back to raw JSON" in app_js


def test_packed_points_binary_prefers_existing_gzip_sibling_when_supported():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")

    assert "browserCanDecodeGzipArrayBuffer" in app_js
    assert "fetchArrayBufferPreferGzipWithRetry" in app_js
    assert "const gzipBinaryUrl = binaryUrl ? binaryUrl + \".gz\" : \"\";" in app_js
    assert "falling back to raw binary" in app_js


def test_startup_profile_preview_loads_before_global_catalog_hydration():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")

    assert "function loadStartupProfileRuntime()" in app_js
    assert "function loadStartupProfileRuntimeViaWorker(config)" in app_js
    assert "function ensureCatalogFacetWorker()" in app_js
    assert "function computeFacetCountsViaWorker(keywordMatches, generation)" in app_js
    assert "function buildFilteredCatalogStateViaWorker(keywordMatches, generation)" in app_js
    assert "keyword: filters.keyword" in app_js
    assert "deferred startup facet counts computed off the main thread" in app_js
    assert "interactive catalog filter IDs computed off the main thread" in app_js
    assert 'new Worker(catalogFacetWorkerUrl())' in app_js
    assert 'new Worker(startupProfileWorkerUrl())' in app_js
    assert "function classifyTraceFacilitySegmentsViaWorker(segments, options)" in app_js
    assert 'new Worker(traceFacilityWorkerUrl())' in app_js
    assert "classifyVisibleStaticTraceFacilitiesInWorker" in app_js
    assert '"startupProfileWorker"' in app_js
    assert "function fetchStartupProfileJson(rawUrl, gzipUrl, label)" in app_js
    assert "files.events_gzip" in app_js
    assert "files.trace_preview_segments_gzip" in app_js
    assert "function renderStartupProfilePreviewMap(profile)" in app_js
    assert "startup profile heatmap rendered before global catalog hydration" in app_js
    assert "const profile = await loadStartupProfileRuntime();" in app_js
    assert "renderPackedStartupPreviewMap(): early parallel preview" in app_js
    assert "interactive startup profile already owns the provisional map" in app_js
    assert "while canonical artifacts continue loading" in app_js
    assert app_js.index("startup profile preview") < app_js.index("manifest load")
    assert app_js.index("runtime.canonicalWebArtifactsPromise = measureStartupStep") < app_js.index("await runtime.packedPointsPromise")
    assert app_js.index("renderPackedStartupPreviewMap(): early parallel preview") < app_js.index("await runtime.canonicalWebArtifactsPromise")


def test_catalog_filter_worker_contract_is_available_for_deployment():
    worker_js = Path("webapp/static_public/catalog_filter_worker.js").read_text(encoding="utf-8")

    assert 'type === "addCatalogFacetRows"' in worker_js
    assert 'type === "computeCatalogFacetCounts"' in worker_js
    assert 'type === "computeFilteredCatalogIds"' in worker_js
    assert "function computeFacetCounts(payload)" in worker_js
    assert "function computeFilteredCatalogIds(payload)" in worker_js
    assert "function normalizedFilters(payload)" in worker_js
    assert "catalogFacetCountsComputed" in worker_js
    assert "filteredCatalogIdsComputed" in worker_js
    assert "sourceFacetEligible" in worker_js
    assert "precisionFacetEligible" in worker_js
    assert "rows = rows.concat(nextRows);" not in worker_js
    assert 'mode: "typed_column_chunks"' in worker_js
    assert "new Float64Array(length)" in worker_js
    assert "new Uint16Array(length)" in worker_js
    assert "typedStorageBytes" in worker_js


def test_mobile_memory_efficiency_guards_use_compact_indexes_and_release_startup_payloads():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    packed_utils = Path("webapp/static/packed-points-utils.mjs").read_text(encoding="utf-8")

    for candidate in (app_js, packed_utils):
        assert 'storageMode: "typed_open_addressing"' in candidate
        assert "new Float64Array(capacity)" in candidate
        assert "new Uint32Array(capacity)" in candidate
        assert "packedPointEventIdHashSlot" in candidate

    assert "function compactCanonicalSummaryEventForRuntime(event)" in app_js
    assert "Deleting properties from the" in app_js
    assert "function internCanonicalSummaryString(value)" in app_js
    assert "releaseCanonicalSummaryStringPool();" in app_js
    assert "DEFAULT_CANONICAL_PLAYBACK_SORT_KEY" in app_js
    assert "fallbackPlaybackKeysReleased" in app_js
    assert "releaseCanonicalSummaryShardCacheEntry" in app_js
    assert 'mode: "bounded_ordered_fetch_ingest"' in app_js
    assert "prefetchWindow: concurrency" in app_js
    assert "if (!activeCatalogUsesCanonicalWebArtifacts())" in app_js
    assert "eventIdToChunkId.set(event.event_id, event.chunk_id);" in app_js


def test_low_precision_filter_copy_does_not_claim_to_filter_place_labels():
    expected_copy = (
        "Hide low-precision coordinates "
        "(country, state/province, approximate, and unknown)"
    )
    for root in (Path("webapp/static_public"), Path("static_bundle")):
        index_html = (root / "index.html").read_text(encoding="utf-8")
        app_js = (root / "app.js").read_text(encoding="utf-8")

        assert expected_copy in index_html
        assert "function popupResolvedPlaceRow(event)" in app_js
        assert "popupResolvedPlaceRow(event)" in app_js
        assert 'event.geocode_display_name || "Unresolved"' not in app_js
        popup_row_body = _extract_js_function_body(app_js, "popupResolvedPlaceRow")
        assert "event.geocode_display_name" in popup_row_body
        assert 'if (!resolvedPlace) return "";' in popup_row_body
        assert '...(resolvedPlace ? [["Resolved Place", resolvedPlace]] : [])' in app_js


def test_catalog_filter_worker_string_ids_resolve_against_catalog_map():
    for app_path in [
        Path("webapp/static_public/app.js"),
        Path("static_bundle/app.js"),
    ]:
        app_js = app_path.read_text(encoding="utf-8")

        assert "function getCatalogEventById(eventId)" in app_js
        assert "const stringId = String(eventId);" in app_js
        assert "const numericId = Number(stringId);" in app_js
        assert "const event = getCatalogEventById(eventId);" in app_js
        assert "const event = catalogById.get(eventId);" not in app_js


def test_versioning_and_gzip_cover_startup_profile_and_canonical_chunks():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")

    assert 'path.indexOf("/data/startup_profiles/") !== -1' in app_js
    assert "const gzipChunkUrl = chunkUrl ? chunkUrl + \".gz\" : \"\";" in app_js
    assert "Canonical web event chunk \" + chunkId" in app_js
    assert "fetchJsonPreferGzipWithRetry(\n        chunkUrl,\n        gzipChunkUrl," in app_js


def test_marker_and_result_description_clicks_do_not_load_full_event_chunks():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")

    assert "function summaryEventDescriptionShort(summary)" in app_js
    assert "if (config.allowFullDetailLoad !== true)" in app_js
    assert "ensureEventDescriptionShort(eventId, { allowFullDetailLoad: false })" in app_js

    description_body = _extract_js_function_body(app_js, "ensureEventDescriptionShort")
    normalized_body = _normalize_js_body(description_body)
    assert "if(config.allowFullDetailLoad!==true)" in normalized_body
    assert normalized_body.index("if(config.allowFullDetailLoad!==true)") < normalized_body.index("ensureFullEventLoaded(eventId)")

    map_description_body = _extract_js_function_body(app_js, "openMapDescriptionPanel")
    assert "summaryEventDescriptionShort(summary)" in map_description_body
    assert "ensureEventDescriptionShort(eventId, { allowFullDetailLoad: false })" in map_description_body


def test_visible_display_dedupe_collapses_exact_same_source_date_location_type():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")

    assert "visibleDisplayDedupeCache: new WeakMap()" in app_js
    assert "function visibleDisplayDuplicateKey(event)" in app_js
    assert "function visibleDisplayDuplicateFingerprint(event)" in app_js
    assert "function createVisibleDisplayDedupeAccumulator(catalog)" in app_js
    assert "occupied: new Uint8Array(capacity)" in app_js
    assert "fingerprints: new Uint32Array(capacity)" in app_js
    assert "function scheduleProgressiveVisibleDisplayDedupe(catalog)" in app_js
    assert "hash = Math.imul(hash, 16777619);" in app_js
    assert "visibleDisplayDuplicateKeyCache" not in app_js
    assert 'event.date_precision && event.date_precision !== "exact_day"' in app_js
    assert "event.sort_date_iso || event.date_raw" in app_js
    assert "event.time_raw || event.time || \"\"" in app_js
    assert "displayLocationForEvent(event)" in app_js
    assert "event.type || event.shape_normalized || event.visual_type_group" in app_js
    assert "function suppressVisibleDisplayDuplicates(catalog)" in app_js
    assert "function currentVisibleDisplayCatalog(catalog)" in app_js

    results_body = _extract_js_function_body(app_js, "currentVisibleResultsCatalog")
    mapped_body = _extract_js_function_body(app_js, "currentVisibleMappedCatalog")
    summary_body = _extract_js_function_body(app_js, "regionSelectionSummaryText")
    assert "return currentVisibleDisplayCatalog(visibleCatalog);" in results_body
    assert "return currentVisibleDisplayCatalog(visibleMappedCatalog);" in mapped_body
    assert "currentVisibleDisplayCatalog(result.visibleCatalog).length" in summary_body


def test_map_marker_clicks_do_not_rerender_results_list():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")

    assert "function syncVisibleResultCardSelection(eventId)" in app_js
    assert "function activateMapPointEvent(eventId, options)" in app_js

    set_selected_body = _extract_js_function_body(app_js, "setSelectedEventId")
    assert "if (config.renderResults === false)" in set_selected_body
    assert "syncVisibleResultCardSelection(state.selectedEventId);" in set_selected_body
    assert "renderResults();" in set_selected_body

    cluster_marker_body = _extract_js_function_body(app_js, "createClusterMarker")
    assert "activateMapPointEvent(event.event_id, { marker });" in cluster_marker_body

    point_marker_body = _extract_js_function_body(app_js, "createPointMarker")
    assert "activateMapPointEvent(event.event_id, { marker });" in point_marker_body

    activation_body = _extract_js_function_body(app_js, "activateMapPointEvent")
    assert "renderResults: false" in activation_body
    assert "syncResults: false" in activation_body
    assert "const marker = config.marker || markerByEventId.get(numericEventId);" in activation_body
    assert 'typeof marker.openPopup === "function"' in activation_body
    assert "marker.openPopup();" in activation_body

    assert 'openMapDescriptionPanel(Number(descriptionButton.getAttribute("data-popup-description")), { syncSelection: false })' in app_js
    assert "renderResults: false,\n        syncResults: false,\n        reason: \"results\"" in app_js


def test_point_markers_take_priority_over_overlapping_neighborhood_trace_clicks():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    neighborhood_js = Path("webapp/static_public/trace_neighborhood.js").read_text(encoding="utf-8")

    assert "function nearestPointHit(target, candidates, defaultTolerance)" in neighborhood_js
    assert "nearestPointHit," in neighborhood_js

    hit_test_body = _extract_js_function_body(app_js, "renderedPointMarkerHitAtLatLng")
    assert "!runtime.map.hasLayer(runtime.pointLayer)" in hit_test_body
    assert "runtime.pointLayer.eachLayer(function (layer)" in hit_test_body
    assert "marker: layer" in hit_test_body
    assert "TRACE_NEIGHBORHOOD.nearestPointHit(" in hit_test_body
    assert "MOBILE_MAP_POINT_INTERACTION_TOLERANCE" in hit_test_body
    assert "MAP_POINT_INTERACTION_TOLERANCE" in hit_test_body

    overlay_body = _extract_js_function_body(app_js, "renderChronologicalNeighborhoodOverlay")
    assert "const pointHit = renderedPointMarkerHitAtLatLng(leafletEvent && leafletEvent.latlng);" in overlay_body
    assert "activateMapPointEvent(pointHit.candidate.eventId, {" in overlay_body
    assert "marker: pointHit.candidate.marker" in overlay_body
    assert "runtime.neighborhoodInspectorTraceId = segment.traceId;" in overlay_body

    assert "L.circleMarker" not in overlay_body
    assert "chronological-neighborhood-endpoint" not in overlay_body
    assert "ufoEventId" not in overlay_body

    render_map_body = _extract_js_function_body(app_js, "renderMap")
    assert "TRACE_NEIGHBORHOOD.resolveAreaEventRepresentation({" in render_map_body
    assert "TRACE_NEIGHBORHOOD.planAreaEventLayerTransition(" in render_map_body
    assert 'nextAreaEventRepresentation === "hidden"' in render_map_body
    assert "clearMapDataLayers();" in render_map_body
    assert 'nextAreaEventRepresentation === MAP_RENDERERS.heatmap' in render_map_body
    assert 'nextAreaEventRepresentation === MAP_RENDERERS.clusters' in render_map_body

    clear_layers_body = _extract_js_function_body(app_js, "clearMapDataLayers")
    for layer in ("clusterLayer", "pointLayer", "heatmapLayer"):
        assert f"runtime.map.removeLayer(runtime.{layer});" in clear_layers_body


def test_area_selection_clear_releases_interaction_pane_and_popup_close_releases_description():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")

    clear_body = _extract_js_function_body(app_js, "clearAllRegionSelectionShapes")
    assert "clearChronologicalNeighborhoodInteractionLayer();" in clear_body

    overlay_body = _extract_js_function_body(app_js, "renderChronologicalNeighborhoodOverlay")
    assert "setChronologicalNeighborhoodPaneInteractive(false);" in overlay_body
    assert "setChronologicalNeighborhoodPaneInteractive(segments.length > 0);" in overlay_body

    pane_body = _extract_js_function_body(app_js, "setChronologicalNeighborhoodPaneInteractive")
    assert 'pane.style.pointerEvents = active ? "auto" : "none";' in pane_body

    cleanup_body = _extract_js_function_body(app_js, "clearChronologicalNeighborhoodInteractionLayer")
    assert "runtime.neighborhoodTraceLayer.clearLayers();" in cleanup_body
    assert "setChronologicalNeighborhoodPaneInteractive(false);" in cleanup_body

    initialize_body = _extract_js_function_body(app_js, "initializeMap")
    assert 'runtime.map.getPane("neighborhoodTracePane").style.pointerEvents = "none";' in initialize_body

    assert "interactionLayerCount:" in app_js
    assert "interactionPanePointerEvents:" in app_js
    assert "activateRenderedPointForTest:" in app_js
    assert "closeMapPopupForTest:" in app_js


def test_dataset_status_uses_canonical_or_config_total_counts():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")

    assert "const totalEvents = canonicalCounts && Number.isFinite(Number(canonicalCounts.events))" in app_js
    assert "runtime.appConfig.normalizedCount != null" in app_js
    assert "els.totalEventsCount.textContent = formatNumber(totalEvents)" in app_js


def test_wrapped_viewport_filter_checks_longitude_not_only_latitude():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")

    assert "const west = bounds.getWest() - TRACE_VIEWPORT_LON_PAD;" in app_js
    assert "const east = bounds.getEast() + TRACE_VIEWPORT_LON_PAD;" in app_js
    assert "return lon >= west && lon <= east;" in app_js


def test_map_wraps_across_dateline_without_finite_horizontal_bounds():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    initialize_map = _extract_js_function_body(app_js, "initializeMap")
    set_basemap = _extract_js_function_body(app_js, "setBasemap")
    moveend = _extract_js_function_body(app_js, "handleMapMoveEnd")

    assert "worldCopyJump: true" in initialize_map
    assert "maxBounds:" not in initialize_map
    assert "maxBoundsViscosity:" not in initialize_map
    assert "noWrap: false" in set_basemap
    assert "bounds: MAP_CANONICAL_BOUNDS" not in set_basemap
    assert "MAP_HORIZONTAL_PAN_LIMIT" not in app_js
    assert "MAP_CANONICAL_BOUNDS" not in app_js

    # Horizontal wrapping is unbounded, while the existing polar guard
    # continues to constrain only latitude after a move completes.
    assert "const clampedLat = clamp(center.lat, -MAP_VERTICAL_LIMIT, MAP_VERTICAL_LIMIT);" in moveend
    assert "runtime.mapVerticalClampInProgress" in moveend
    assert "runtime.map.setView(" in moveend
    assert "[clampedLat, center.lng]" in moveend
    assert "runtime.map.getZoom()" in moveend
    assert "{ animate: false, reset: true }" in moveend
    assert "finally" in moveend
    assert "runtime.map.panTo(" not in moveend
    assert "normalizeLongitude(center.lng)" not in moveend


def test_event_display_layers_do_not_duplicate_wrapped_world_copies():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")

    assert "function canonicalEventWorldIndices() {\n    return [0];\n  }" in app_js

    heatmap_start = app_js.index("function createHeatmapLayer()")
    heatmap_end = app_js.index("function createStaticTraceLayer", heatmap_start)
    heatmap_block = app_js[heatmap_start:heatmap_end]
    assert "const worldIndices = canonicalEventWorldIndices();" in heatmap_block
    assert "const worldIndices = wrappedWorldIndices();" not in heatmap_block

    point_start = app_js.index("function renderPointLayer")
    point_end = app_js.index("function renderClusterLayer", point_start)
    point_block = app_js[point_start:point_end]
    assert "const worldIndices = canonicalEventWorldIndices();" in point_block
    assert "const primaryWorldIndex = 0;" in point_block
    assert "wrappedWorldIndices()" not in point_block

    cluster_start = app_js.index("function renderClusterLayer")
    cluster_end = app_js.index("function renderHeatmapLayer", cluster_start)
    cluster_block = app_js[cluster_start:cluster_end]
    assert "const worldIndices = canonicalEventWorldIndices();" in cluster_block
    assert "const primaryWorldIndex = 0;" in cluster_block
    assert "wrappedWorldIndices()" not in cluster_block


def test_static_trace_render_metrics_debug_snapshot_is_exposed():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")

    assert "staticTraceRenderMetricsSnapshot" in app_js
    assert "getStaticTraceRenderMetrics" in app_js
    assert "static traces hidden or unavailable" in app_js
    assert "TRACE_AGGREGATE_SEGMENT_THRESHOLD" in app_js
    assert "sampleRatio" in app_js
    assert "viewportSourceSegments" in app_js
    assert "traceSegmentMayIntersectBounds" in app_js
    assert "const facilityFilterActive = traceFacilityFilterEnabled();" in app_js
    assert "const initialRenderMode = resolveTraceRenderMode(totalSegments)" in app_js
    assert "buildCanonicalPackedTraceRenderSegments" in app_js
    assert "packedTraceOrdinalScanRange" in app_js
    assert "function normalizedPackedTraceSortOrdinalForRender(artifact, rowIndex)" in app_js
    assert "normalizeBigIntForPackedPointRuntime(" not in app_js
    assert "normalizeBigIntForRuntime(view.getBigUint64(offset, littleEndian))" in app_js
    assert "normalizeBigIntForRuntime(view.getBigInt64(offset, littleEndian))" in app_js
    assert 'decodePackedTraceField(artifact.metadata, artifact.view, "sort_date_key", rowIndex)' in app_js
    assert "const sortDateIso = sortDateIsoFromPackedKey(sortDateKey)" in app_js
    assert "const normalizedOrdinal = isoToOrdinal(sortDateIso)" in app_js
    assert "const sortOrdinal = normalizedPackedTraceSortOrdinalForRender(artifact, rowIndex)" in app_js
    assert "return normalizedPackedTraceSortOrdinalForRender(artifact, rowIndex)" in app_js
    assert "packedTraceSortOrdinalLowerBound" in app_js
    assert "packedTraceSortOrdinalUpperBound" in app_js
    assert "for (let rowIndex = scanRange.startRow; rowIndex < scanRange.endRow; rowIndex += 1)" in app_js
    assert "const activeBucketKeys = new Set(activeBuckets.map(function (bucket) { return bucket.key; }))" in app_js
    assert "activeBucketKeys.has(bucket.key)" in app_js
    assert "const mappedSequence = state.filteredMappedPlaybackEvents.slice()" in app_js
    assert "return event.has_coordinates && event.sort_ordinal != null" not in app_js
    assert "rowScanBoundedByTimeRange" in app_js
    assert "filteredMappedEventIdSetCacheKey" not in app_js
    assert "filteredMappedEventIdSetCacheValue" not in app_js
    assert "function catalogEventIdIdentityKey(catalog)" in app_js
    assert "Math.floor(length * 0.5)" in app_js
    assert "catalogEventIdIdentityKey(state.filteredCatalog)" in app_js
    assert "catalogEventIdIdentityKey(state.filteredMappedCatalog)" in app_js
    assert "packedMapLayerCache: new Map()" in app_js
    assert "runtime.packedMapLayerCache.has(cacheKey)" in app_js
    assert "runtime.packedMapLayerCache.size > 4" in app_js
    assert "packedMapLayerEventIdSignature" not in app_js
    assert "function regionSelectionShapeBounds(shape)" in app_js
    assert "function pointMayIntersectRegionShapeBounds(lat, lon, bounds)" in app_js
    assert "function pointMayIntersectAnyRegionShape(lat, lon, shapeBounds)" in app_js
    assert "function pointInsideAnyRegionShapeWithBounds(lat, lon, shapes, shapeBounds)" in app_js
    assert "function segmentMayIntersectAnyRegionShape(segment, shapeBounds)" in app_js
    assert "const shapeBounds = shapes.map(regionSelectionShapeBounds)" in app_js
    assert "function currentChronologicalNeighborhoodSeeds(index, shapes, shapeBounds)" in app_js
    assert "const regionIds = regionIdsForPoint(event, shapes, shapeBounds)" in app_js
    assert "function traceSegmentRegionShapeIntersectionStatus(segment, shapes, shapeBounds)" in app_js
    assert "const regionIds = regionIdsForTrace(segment, shapes, shapeBounds)" in app_js
    assert "TRACE_NEIGHBORHOOD.querySpatialIndex(index.spatial, [bounds])" in app_js
    assert "const visibleMappedCatalog = []" in app_js
    assert "visibleMappedCatalog.push(event)" in app_js
    assert "state.filteredMappedCatalog.filter(function (event) {" not in app_js
    region_result_body = _extract_js_function_body(app_js, "computeRegionSelectionResult")
    assert "const index = pointOnly ? null : currentChronologicalNeighborhoodIndex();" in region_result_body
    assert "else if (areaDepth === 0)" in region_result_body
    assert "TRACE_NEIGHBORHOOD.computeAreaZeroHopSelection({" in region_result_body
    assert "neighborhood = TRACE_NEIGHBORHOOD.traverseNeighborhood({" in region_result_body
    assert "if (showsReachedTraces)" in region_result_body
    assert "if (showsReachedEvents)" in region_result_body
    assert "state.regionSelection.showTracesAssociatedWithSelectedEvents" in app_js
    assert "neighborhood.segmentIds.forEach(function (traceId)" in app_js
    assert "neighborhood.eventIds.forEach(function (eventId)" in app_js
    assert "regionSelectionMetrics" in app_js
    assert "getRegionSelectionMetrics" in app_js
    assert "eventPointsBroadPhaseRejected" in app_js
    assert "eventPointsExactTested" in app_js
    assert "traceSegmentsBroadPhaseRejected" in app_js
    assert "regionSelectionResultCacheHits" in app_js
    assert "runtime.regionSelectionResultCacheHits += 1" in app_js
    assert "runtime.regionSelectionResultCacheMisses += 1" in app_js
    assert "cacheHits: runtime.regionSelectionResultCacheHits" in app_js
    assert "cacheMisses: runtime.regionSelectionResultCacheMisses" in app_js
    assert "traceSegmentsExactTested" in app_js
    assert "associatedTraceIndexEntries" in app_js
    assert "visibleTraceIds.add(traceId)" in app_js
    assert "const traceIdsByEventId = new Map()" not in app_js
    assert "const regionResult = areaFilterActive ? currentRegionSelectionResult() : null" in app_js
    assert "const sourceTraceSegments = regionResult ? regionResult.traceSegments : buildCanonicalTraceSegments()" in app_js
    assert "const rawSegments = visibleTraceIds && !visibleTraceIds.size" in app_js


def test_trace_facility_worker_contract_is_available_for_deployment():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    worker_js = Path("webapp/static_public/trace_facility_worker.js").read_text(encoding="utf-8")

    assert "TRACE_FACILITY_WORKER_MIN_SEGMENTS" in app_js
    assert "TRACE_FACILITY_WORKER_TIMEOUT_MS" in app_js
    assert "function traceFacilityWorkerUrl()" in app_js
    assert "function traceFacilityWorkerInstance()" in app_js
    assert "function ensureTraceFacilityWorkerIndexConfigured(index, options)" in app_js
    assert "function traceFacilityWorkerFilterPayload()" in app_js
    assert "function serializeTraceFacilityWorkerFacilities(index)" in app_js
    assert "function serializeTraceFacilityWorkerSegments(segments)" in app_js
    assert "function ensureTraceFacilityWorkerTraceIndexConfigured(artifact, options)" in app_js
    assert "function buildAndClassifyPackedTraceFacilitySegmentsViaWorker(artifact, options)" in app_js
    assert "function schedulePackedTraceFacilityWorkerStaticRender(artifact, cacheKey, areaFilterActive, options)" in app_js
    assert "function applyPackedTraceFacilityWorkerRenderResult(workerResult, cacheKey, areaFilterActive, viewportBoundsKey)" in app_js
    assert "forceBufferFallback" in app_js
    assert "binaryGzip: gzipBinaryUrl" in app_js
    assert "traceIndexLoadMode: runtime.traceFacilityWorkerConfiguredTraceIndexLoadMode" in app_js
    assert "runtime.traceFacilityWorkerConfiguredTraceIndexLoadMode = String(result.loadMode || \"\")" in app_js
    assert "function buildPackedTraceFacilityWorkerCandidateSegments(artifact, options)" in app_js
    assert "function scheduleTraceFacilityWorkerStaticRender(candidateRender, cacheKey, areaFilterActive)" in app_js
    assert "function applyTraceFacilityWorkerRenderResult(candidateRender, workerResult, cacheKey, areaFilterActive)" in app_js
    assert "packed trace facility worker queued" in app_js
    assert "packed trace facility worker rendered aggregated proximity-filtered segments" in app_js
    assert "packed trace facility worker rendered exact proximity-filtered segments" in app_js
    assert "static trace facility worker queued" in app_js
    assert "static trace facility worker result applied" in app_js
    assert 'type: "configureTraceFacilityIndex"' in app_js
    assert 'type: "configureTraceEventIndex"' in app_js
    assert 'type: "buildAndClassifyPackedTraceFacilitySegments"' in app_js
    assert 'type: "traceFacilityIndexConfigured"' in worker_js
    assert 'type: "traceEventIndexConfigured"' in worker_js
    assert 'type: "packedTraceFacilitySegmentsBuilt"' in worker_js
    assert "async function fetchArrayBufferPreferGzipFromWorker(rawUrl, gzipUrl)" in worker_js
    assert "new DecompressionStream(\"gzip\")" in worker_js
    assert "const loadMode = message.buffer ? \"message_buffer\" : \"worker_fetch\"" in worker_js
    assert "await fetchArrayBufferPreferGzipFromWorker(message.binaryUrl || \"\", message.gzipBinaryUrl || \"\")" in worker_js
    assert "facilityIndexKey: indexResult.facilityIndexKey" in app_js
    assert "let facilityIndexCacheKey = \"\"" in worker_js
    assert "let traceEventIndexCacheKey = \"\"" in worker_js
    assert 'type: "classifyTraceFacilitySegments"' in app_js
    assert 'type: "traceFacilitySegmentsClassified"' in worker_js
    assert "function distanceMetersFromFacilityToTraceSegment(facility, segment)" in worker_js
    assert "function traceEndpointNearFacility(lat, lon, index, radiusMeters)" in worker_js
    assert "function segmentPassesNearFacility(segment, index, radiusMeters, stats)" in worker_js
    assert "visibleTraceSegments: visibleTraceSegments" in app_js
    assert "? regionResult.visibleTraceSegments" in app_js
    assert "visibleResultsEventIdSetCacheKey" in app_js
    assert "function visibleResultsEventIdSet()" in app_js
    assert "return visibleResultsEventIdSet().has(eventId)" in app_js
    assert "resultsDisplayIndexCache: new WeakMap()" in app_js
    assert "function resultIndexByEventIdForDisplay(events)" in app_js
    assert "display.indexByEventId.get(eventId)" in app_js
    assert "precisionLegendEntriesCacheKey" in app_js
    assert "function precisionLegendEntriesCacheKey(visibleCatalog)" in app_js
    assert "runtime.precisionLegendEntriesCacheValue = entries" in app_js
    assert "typeLegendCountsCacheKey" in app_js
    assert "function computeTypeLegendCounts()" in app_js
    assert "runtime.typeLegendCountsCacheValue = counts" in app_js
    assert "visibleMappedBoundsCacheKey" in app_js
    assert "function visibleMappedCatalogBounds()" in app_js
    assert "runtime.visibleMappedBoundsCacheValue = bounds" in app_js
    assert "filteredPlaybackEventCount" in app_js
    assert "let nextFilteredPlaybackEventCount = 0" in app_js
    assert "const canPlayback = state.filteredPlaybackEventCount > 0" in app_js
    assert "filteredPlaybackEvents: []" in app_js
    assert "const nextFilteredPlaybackEvents = []" in app_js
    assert "nextFilteredPlaybackEvents.push(event)" in app_js
    assert "state.filteredPlaybackEvents = nextFilteredPlaybackEvents" in app_js
    assert "const playbackSequence = state.filteredPlaybackEvents.filter(function (event)" in app_js
    assert "return visibleEventIds.has(event.event_id)" in app_js
    assert "filteredMappedPlaybackEvents: []" in app_js
    assert "const nextFilteredMappedPlaybackEvents = []" in app_js
    assert "nextFilteredMappedPlaybackEvents.push(event)" in app_js
    assert "state.filteredMappedPlaybackEvents = nextFilteredMappedPlaybackEvents" in app_js
    assert "const mappedSequence = state.filteredMappedPlaybackEvents.slice()" in app_js
    assert "filteredMappedEventIdSet: new Set()" in app_js
    assert "const nextFilteredMappedEventIdSet = new Set()" in app_js
    assert "nextFilteredMappedEventIdSet.add(String(event.event_id))" in app_js
    assert "state.filteredMappedEventIdSet = nextFilteredMappedEventIdSet" in app_js
    assert "return state.filteredMappedEventIdSet || new Set()" in app_js
    assert "playbackSequenceEventIdIndex: new Map()" in app_js
    assert "state.playbackSequenceEventIdIndex.get(currentEvent.event_id)" in app_js
    assert "playbackSequenceEventIdIndex.set(event.event_id, index)" in app_js
    assert "timelineCatalogEventIdSetCacheKey" in app_js

    assert "function timelineCatalogEventIdSet()" in app_js
    assert "timelineCatalogEventIdSet().has(currentEvent.event_id)" in app_js
    assert "catalogEventIdIdentityKey(state.filteredCatalog)" in app_js
    assert "catalogEventIdIdentityKey(state.filteredMappedCatalog)" in app_js
    assert "const playbackTimelineState = measureStep(\"timelinePlaybackEvents construction/sort\"" in app_js
    assert "state.timelinePlaybackEvents = playbackTimelineState.events" in app_js
    assert "state.filteredTimelineExtent = playbackTimelineState.extent || state.fullCatalogExtent" in app_js
    assert "const paddedSouth = bounds ? bounds.getSouth() - TRACE_VIEWPORT_LAT_PAD : null" in app_js
    assert "event.lat < paddedSouth || event.lat > paddedNorth" in app_js
    assert "const visibleCatalog = []" in app_js
    assert "if (!visibleEventIds.has(String(event.event_id))) continue;" in app_js
    assert "packed trace index aggregated during scan for wide trace windows" in app_js
    assert "? resolveTraceRenderMode(sourceSegments.length)" in app_js
    assert "initialRenderMode: initialRenderMode" in app_js
    assert '"packedStaticTraceRender"' in app_js
    assert "runtime.traceRenderCacheKey === packedRenderCacheKey" in app_js
    assert "runtime.traceRenderCacheValue = packedRender" in app_js
    assert "const cachedPackedRender = runtime.packedStaticTraceRenderCache.get(packedRenderCacheKey)" in app_js
    assert "runtime.staticTraceRenderMode = cachedPackedRender.renderMode" in app_js
    assert "runtime.staticTraceTotalSegments = cachedPackedRender.totalSegments" in app_js
    assert "runtime.staticTraceRenderedSegments = cachedPackedRender.segments.length" in app_js
    assert "runtime.staticTraceAggregationStatus = cachedPackedRender.aggregationStatus" in app_js
    assert "static trace segments restored from packed trace render LOD cache" in app_js
    assert "runtime.packedStaticTraceRenderCache.set(packedRenderCacheKey, packedRender)" in app_js
    assert "packedTraceRenderCacheKey: \"\"" in app_js
    assert "packedTraceRenderCacheValue: null" in app_js
    assert "runtime.packedTraceRenderCacheKey === cacheKey" in app_js
    assert "runtime.packedTraceRenderCacheValue = result" in app_js
    assert "TRACE_STATIC_RENDER_CACHE_LIMIT = 4" in app_js
    assert "packedStaticTraceRenderCache: new Map()" in app_js
    assert "runtime.packedStaticTraceRenderCache.has(packedRenderCacheKey)" in app_js
    assert "runtime.packedStaticTraceRenderCache.delete(packedRenderCacheKey)" in app_js
    assert "runtime.packedStaticTraceRenderCache.size > TRACE_STATIC_RENDER_CACHE_LIMIT" in app_js
    assert "runtime.packedStaticTraceRenderCache.clear()" in app_js
    assert "if (kind === PACKED_TRACE_ARTIFACT_KINDS.eventIndex)" in app_js
    assert "renderStaticTraceLayer();\n          renderTraceControls();" in app_js
    assert "state.filteredMappedCatalog.length,\n      activeBuckets.map(function (bucket) { return bucket.key; }).join(\",\")," not in app_js
    assert "catalogEventIdIdentityKey(state.filteredMappedCatalog),\n      activeBuckets.map(function (bucket) { return bucket.key; }).join(\",\")," in app_js
    assert "runtime.staticTraceAggregationStatus.viewportWindowed" in app_js
    assert "refreshStaticTraceLayerForViewportChange" in app_js
    assert "scheduleStaticTraceViewportRefresh" in app_js
    assert "runtime.pendingStaticTraceRenderTimerId = null;\n      refreshStaticTraceLayerForViewportChange();" in app_js
    assert "viewport=fallback-all" in app_js
    assert "packedRender.totalSegments > 0 && packedRender.segments.length === 0" in app_js
    assert "if (!packedTraceRenderResultIsUsable(packedRender))" in app_js
    assert "runtime.packedStaticTraceRenderCache.delete(packedRenderCacheKey)" in app_js
    assert "const facilityFilterActive = traceFacilityFilterEnabled();" in app_js
    assert "const useAggregation = Boolean(aggregates) ||" in app_js
    assert "const useFilteredAggregation = (facilityFilterActive || craftTraceColoringActive())" in app_js
    assert 'recordTraceFacilityFilterEvaluation(null, false, "sources_loading")' in app_js
    assert "if (traceFacilityFilterEnabled() && !traceFacilitySourcesLoaded()) return false;" in app_js
    assert "static trace facility filter waiting for sources" in app_js
    assert "ensureTraceFacilitySourcesLoaded();\n        updateStaticTraceRenderMetrics({" in app_js
    assert "return applyTraceFacilityAccentStyle(" in app_js
    assert "facilityAccentPlacement: placement" in app_js
    assert "facilityAccentWeight: placement ? Math.max(2.4, baseWeight + style.weightBoost + 0.6) : 0" in app_js
    assert 'typeof runtime.staticTraceLayer._reset === "function"' in app_js
    assert "function buildStaticTraceLodRender(rawSegments, options)" in app_js
    assert "runtime.traceFacilityWorkerPendingKey !== runtime.traceRenderCacheKey" in app_js
    assert "const initialRenderMode = facilityFilterActive\n      ? TRACE_RENDER_MODE_BUDGETED" not in app_js
    assert "viewportWindowed && rawSegments.length > 0 && sourceSegments.length === 0" in app_js
    assert "canonicalTraceRuntimeStatusSnapshot().eligible &&\n      (renderMode === TRACE_RENDER_MODE_AGGREGATE" not in app_js
    assert "const preserveExistingStaticTraceLayer = (" in app_js
    assert "static trace viewport refresh preserved existing visible layer" in app_js
    assert "keepEmptyStaticTraceLayerForRefresh" in app_js
    assert "static trace facility filter produced no visible segments; layer kept for source and viewport refresh" in app_js
    assert "runtime.staticTraceLayer._segments.length" in app_js
    assert "TRACE_VIEWPORT_REFRESH_DEBOUNCE_MS" in app_js
    assert "TRACE_AGGREGATE_ZOOM_DETAIL_STEPS" in app_js
    assert "traceAggregateZoomBucket" in app_js
    assert "aggregationZoomDetail" in app_js
    assert "runtime.traceRenderCacheKey = \"\";\n    runtime.traceRenderCacheValue = null;\n    renderStaticTraceLayer();" not in app_js
    assert "legacy_catalog_sequence" in app_js


def test_browser_compat_performance_profile_is_wired_into_rendering():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    styles_css = Path("webapp/static_public/styles.css").read_text(encoding="utf-8")
    index_html = Path("webapp/static_public/index.html").read_text(encoding="utf-8")
    bundle_app_js = Path("static_bundle/app.js").read_text(encoding="utf-8")
    bundle_styles_css = Path("static_bundle/styles.css").read_text(encoding="utf-8")
    bundle_index_html = Path("static_bundle/index.html").read_text(encoding="utf-8")

    expected_app_tokens = [
        "function detectBrowserPerformanceProfile()",
        "const BROWSER_PERFORMANCE_PROFILE = detectBrowserPerformanceProfile()",
        "function applyBrowserPerformanceProfile()",
        'root.classList.toggle("browser-perf-lean-visuals"',
        "function canvasContextOptions(alpha)",
        "function getCanvas2dContext(canvas, options)",
        "function renderCanvasDevicePixelRatio()",
        "BROWSER_PERFORMANCE_PROFILE.traceFrameBudgetMs",
        "BROWSER_PERFORMANCE_PROFILE.traceBatchSize",
        "BROWSER_PERFORMANCE_PROFILE.clusterChunkInterval",
        "BROWSER_PERFORMANCE_PROFILE.clusterChunkDelay",
        "runtime.browserPerformanceProfile",
    ]
    for token in expected_app_tokens:
        assert token in app_js
        assert token in bundle_app_js

    assert "const dpr = renderCanvasDevicePixelRatio();" in app_js
    assert "getCanvas2dContext(els.timelineCanvas, canvasContextOptions(true))" in app_js
    assert "getCanvas2dContext(this._canvas, canvasContextOptions(true))" in app_js
    assert "if (!options.alpha && BROWSER_PERFORMANCE_PROFILE.desynchronizedCanvas)" in app_js
    assert "if (!options.alpha && BROWSER_PERFORMANCE_PROFILE.desynchronizedCanvas)" in bundle_app_js
    assert "TRACE_PROGRESSIVE_COMPAT_BATCH_SIZE" in app_js
    assert "TRACE_PROGRESSIVE_COMPAT_FRAME_BUDGET_MS" in app_js
    assert "function recordStartupMilestoneIfUnset(name)" in app_js
    assert 'recordStartupMilestoneIfUnset("time to startup profile preview render")' in app_js
    assert "function recordStartupMilestoneIfUnset(name)" in bundle_app_js
    assert 'recordStartupMilestoneIfUnset("time to startup profile preview render")' in bundle_app_js
    assert "previewInteractive: false" in app_js
    assert "function setStartupPreviewInteractive(overview)" in app_js
    assert 'data-startup-preview-interactive' in app_js
    assert "Default view prepared. Loading the full catalog and final map layers." in app_js
    assert "startup profile preview interaction yield" in app_js
    assert "function applyStartupPreviewTimeRangeInputs()" in app_js
    assert "state.timeRangeStartOrdinal = initialTimeRange.startOrdinal;" in app_js
    assert "function startupProfilePreviewResultsCatalog()" in app_js
    assert "const visibleCatalog = regionSelectionAffectsRendering()" in app_js
    assert "return currentVisibleDisplayCatalog(visibleCatalog);" in app_js
    assert "const previewDecision = renderStartupProfilePreviewMap(profile);" in app_js
    assert "if (previewDecision.rendered) {\n          applyStartupPreviewTimeRangeInputs();\n          setStartupPreviewInteractive(\"Default view prepared. Loading the full catalog and final map layers.\");\n          renderStats();\n          renderResults({ preserveScroll: false });" in app_js


def test_current_ui_interaction_regression_contracts():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    index_html = Path("webapp/static_public/index.html").read_text(encoding="utf-8")
    styles_css = Path("webapp/static_public/styles.css").read_text(encoding="utf-8")
    bundle_app_js = Path("static_bundle/app.js").read_text(encoding="utf-8")
    bundle_index_html = Path("static_bundle/index.html").read_text(encoding="utf-8")
    bundle_styles_css = Path("static_bundle/styles.css").read_text(encoding="utf-8")

    assert Path("static_bundle/data/app_config.json").is_file()
    assert 'fetchJson("./data/app_config.json", "App config")' in app_js
    assert 'fetchJson("./data/app_config.json", "App config")' in bundle_app_js
    assert "function waitForBrowserPaint()" in app_js
    assert "window.setTimeout(finish, 160);" in app_js
    assert "function startupPageIsInactive()" in app_js
    assert 'typeof document.hasFocus === "function" && !document.hasFocus()' in app_js
    assert "function waitForNextFrame()" in app_js
    assert "if (startupPageIsInactive())" in app_js
    assert "yieldDeferredStartupWork().then(finish, finish);" in app_js
    assert "function waitForDeferredStartupSlot()" in app_js
    assert "window.setTimeout(finish, 350);" in app_js
    assert "window.setTimeout(finish, 160);" in bundle_app_js
    assert "window.setTimeout(finish, 350);" in bundle_app_js
    assert "function startupPageIsInactive()" in bundle_app_js
    assert "if (startupPageIsInactive())" in bundle_app_js
    assert "yieldDeferredStartupWork().then(finish, finish);" in bundle_app_js
    assert 'const ready = startup.phase === "Ready" && startup.initialViewReady && !startup.errorText;' in app_js
    assert 'const ready = startup.phase === "Ready" && startup.initialViewReady && !startup.errorText;' in bundle_app_js
    assert "const MAP_STARTUP_OVERLAY_MIN_VISIBLE_MS = 900;" in app_js
    assert "runtime.mapStartupOverlayHideTimerId = window.setTimeout" in app_js
    assert "function applyStartupPreviewTimeRangeInputs()" in app_js
    assert "function applyStartupPreviewTimeRangeInputs()" in bundle_app_js
    assert "function normalizeStartupProfileEvents(events)" in app_js
    assert "function normalizeStartupProfileEvents(events)" in bundle_app_js
    assert "state.timeRangeStartOrdinal = initialTimeRange.startOrdinal;" in app_js
    assert "state.timeRangeStartOrdinal = initialTimeRange.startOrdinal;" in bundle_app_js
    assert "function startupProfilePreviewResultsCatalog()" in app_js
    assert "function startupProfilePreviewResultsCatalog()" in bundle_app_js
    assert "const visibleCatalog = regionSelectionAffectsRendering()" in app_js
    assert "return currentVisibleDisplayCatalog(visibleCatalog);" in app_js
    assert "const visibleCatalog = regionSelectionAffectsRendering()" in bundle_app_js
    assert "return currentVisibleDisplayCatalog(visibleCatalog);" in bundle_app_js
    assert "const previewDecision = renderStartupProfilePreviewMap(profile);" in app_js
    assert "if (previewDecision.rendered) {\n          applyStartupPreviewTimeRangeInputs();\n          setStartupPreviewInteractive(\"Default view prepared. Loading the full catalog and final map layers.\");\n          renderStats();\n          renderResults({ preserveScroll: false });" in app_js
    assert "const previewDecision = renderStartupProfilePreviewMap(profile);" in bundle_app_js
    assert "if (previewDecision.rendered) {\n          applyStartupPreviewTimeRangeInputs();\n          setStartupPreviewInteractive(\"Default view prepared. Loading the full catalog and final map layers.\");\n          renderStats();\n          renderResults({ preserveScroll: false });" in bundle_app_js

    assert '<option value="points">Points</option>' in index_html
    assert '<option value="heatmap" selected>Heatmap</option>' in index_html
    assert '<option value="heatmap" selected>Heatmap</option>' in bundle_index_html
    assert 'reason: "startup policy: preserving configured heatmap default"' in app_js

    assert 'id: "flap_phoenix_lights"' in app_js
    assert 'startIso: "1997-03-12"' in app_js
    assert 'endIso: "1997-03-14"' in app_js

    for candidate in (app_js, bundle_app_js):
        assert "worldCopyJump: true" in candidate
        assert "maxBounds: MAP_CANONICAL_BOUNDS" not in candidate
        assert "maxBoundsViscosity:" not in candidate
        assert "bounds: MAP_CANONICAL_BOUNDS" not in candidate
        assert "MAP_HORIZONTAL_PAN_LIMIT" not in candidate
        assert "MAP_CANONICAL_BOUNDS" not in candidate
        assert "noWrap: false" in candidate

    assert "function scheduleDateInputCommit" not in app_js
    assert "function scheduleDateInputCommit" not in bundle_app_js
    assert 'input.dataset.pendingDateEdit = "true";' in app_js
    assert "function handleDateInputEdit(input, group)" in app_js
    assert "if (isDateInputElement(event.relatedTarget)) return;" in app_js
    assert '{ mode: "custom", autofitVisible: false }' in app_js
    assert 'input.addEventListener("keydown", function (event) {' in app_js

    assert 'if (!nextSelected.size) {\n      setOptionSelection(selectEl, false);\n      setMultiSelectMode(filterKey, "none");' in app_js
    assert 'if (explicitMode === "subset") {\n        return { mode: "none", selectedValues: [] };' in app_js
    assert "const manualSelectionCount = selectedValues(selectEl).length;" in app_js
    assert 'if (!manualSelectionCount) {\n      setMultiSelectMode(filterKey, "none");' in app_js
    assert 'const invertedSelectionCount = selectedValues(selectEl).length;' in app_js
    assert 'if (!invertedSelectionCount) {\n        setMultiSelectMode(filterKey, "none");' in app_js
    assert 'setOptionSelection(selectEl, false);\n        setMultiSelectMode(filterKey, "all");' in app_js
    assert 'selectedValues(selectEl).length ? "subset" : "all"' not in app_js
    assert "function ensureVisibleTimelineExtentContainsSelection()" in app_js
    assert 'const TIMELINE_DEFAULT_VISIBLE_START_ISO = "1890-01-01";' in app_js
    assert "function computeDefaultVisibleTimelineExtent()" in app_js
    assert "function renderTimelineFamousFlapMarkers(ctx, extent, plot, gridTop, gridBottom)" in app_js
    assert "autoFitVisibleTimelineExtent();\n        applyCurrentTimeRangeState();" not in app_js
    assert "const MAP_ZOOM_DELTA = 0.5;" in app_js
    assert "const MAP_WHEEL_PX_PER_ZOOM_LEVEL = 90;" in app_js
    assert "function mapMoveEndFollowsRecentZoom()" in app_js
    assert "STARTUP_CATALOG_INGEST_BATCH_SIZE" in app_js
    assert "function ingestCatalogShardProgressively(entries)" in app_js
    assert "function stableEventIdSortKey(value)" in app_js
    assert "function cachedStableEventIdSortKey(event)" in app_js
    assert "function compareStableEventIdSortKeys(leftKey, rightKey)" in app_js
    assert "event.playback_sort_key = [" in app_js
    assert "text.charCodeAt(4) === 45" in app_js
    assert 'Object.prototype.hasOwnProperty.call(event, "estimated_utc_timestamp_ms")' in app_js
    assert "defer full display sort for startup" in app_js
    assert "previewInteractive: false" in bundle_app_js
    assert "function setStartupPreviewInteractive(overview)" in bundle_app_js
    assert 'data-startup-preview-interactive' in bundle_app_js
    assert "Default view prepared. Loading the full catalog and final map layers." in bundle_app_js
    assert "startup profile preview interaction yield" in bundle_app_js
    assert "STARTUP_CATALOG_INGEST_BATCH_SIZE" in bundle_app_js
    assert "function ingestCatalogShardProgressively(entries)" in bundle_app_js
    assert "function stableEventIdSortKey(value)" in bundle_app_js
    assert "function cachedStableEventIdSortKey(event)" in bundle_app_js
    assert "function compareStableEventIdSortKeys(leftKey, rightKey)" in bundle_app_js
    assert "event.playback_sort_key = [" in bundle_app_js
    assert "text.charCodeAt(4) === 45" in bundle_app_js
    assert 'Object.prototype.hasOwnProperty.call(event, "estimated_utc_timestamp_ms")' in bundle_app_js
    assert "defer full display sort for startup" in bundle_app_js
    assert 'if (explicitMode === "subset") {\n        return { mode: "none", selectedValues: [] };' in bundle_app_js
    assert "const manualSelectionCount = selectedValues(selectEl).length;" in bundle_app_js
    assert 'if (!manualSelectionCount) {\n      setMultiSelectMode(filterKey, "none");' in bundle_app_js
    assert 'const invertedSelectionCount = selectedValues(selectEl).length;' in bundle_app_js
    assert 'if (!invertedSelectionCount) {\n        setMultiSelectMode(filterKey, "none");' in bundle_app_js
    assert 'setOptionSelection(selectEl, false);\n        setMultiSelectMode(filterKey, "all");' in bundle_app_js
    assert 'selectedValues(selectEl).length ? "subset" : "all"' not in bundle_app_js

    expected_style_tokens = [
        "html.browser-perf-lean-visuals",
        "backdrop-filter: none",
        ".heatmap-canvas-layer",
        "content-visibility: auto",
        "contain-intrinsic-size: var(--result-card-min-height) 320px",
    ]
    for token in expected_style_tokens:
        assert token in styles_css
        assert token in bundle_styles_css

    assert "2026-07-31-area-lifecycle-v154" in index_html
    assert "2026-07-31-area-lifecycle-v154" in bundle_index_html

    expected_loader_ready_guard = 'const ready = startup.phase === "Ready" && startup.initialViewReady && !startup.errorText;'
    assert expected_loader_ready_guard in app_js
    assert expected_loader_ready_guard in bundle_app_js


def test_only_one_and_two_day_trace_buckets_are_enabled_by_default():
    source_app = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    bundle_app = Path("static_bundle/app.js").read_text(encoding="utf-8")
    source_index = Path("webapp/static_public/index.html").read_text(encoding="utf-8")
    bundle_index = Path("static_bundle/index.html").read_text(encoding="utf-8")
    source_styles = Path("webapp/static_public/styles.css").read_text(encoding="utf-8")
    bundle_styles = Path("static_bundle/styles.css").read_text(encoding="utf-8")

    expected_visibility = {
        "gap_le_1": "true",
        "gap_le_2": "true",
        "gap_le_7": "false",
        "gap_le_30": "false",
        "gap_gt_30": "false",
    }
    expected_active_markup = {
        "gap_le_1": True,
        "gap_le_2": True,
        "gap_le_7": False,
        "gap_le_30": False,
        "gap_gt_30": False,
    }

    for app_js in (source_app, bundle_app):
        default_body = _extract_js_function_body(app_js, "defaultTraceBucketVisibilityState")
        for key, value in expected_visibility.items():
            assert f"{key}: {value}" in default_body
        assert "traceBucketVisibility: defaultTraceBucketVisibilityState()" in app_js
        assert "state.traceBucketVisibility = Object.assign({}, defaults.traceBucketVisibility)" in app_js
        assert "activeKeys: activeTraceBuckets().map(function (bucket) { return bucket.key; })" in app_js

    for index_html in (source_index, bundle_index):
        for key, active in expected_active_markup.items():
            expected_class = "trace-bucket-button is-active" if active else "trace-bucket-button"
            expected_pressed = "true" if active else "false"
            assert (
                f'class="{expected_class}" type="button" '
                f'data-trace-bucket="{key}" aria-pressed="{expected_pressed}"'
            ) in index_html

    for styles_css in (source_styles, bundle_styles):
        assert (
            ".map-control-cluster:not(.is-collapsed) ~ .map-legend {\n"
            "    z-index: 630;\n"
            "  }"
        ) in styles_css


def test_public_startup_benchmark_script_is_documented_for_deployment():
    benchmark_script = Path("scripts/benchmark_public_startup_cdp.ps1").read_text(encoding="utf-8")
    deploy_doc = Path("DEPLOY.md").read_text(encoding="utf-8")

    assert "param(" in benchmark_script
    assert "ProbeStaticTraces" in benchmark_script
    assert "getStartupTimingSummary" in benchmark_script
    assert "getCanonicalTraceRuntimeStatus" in benchmark_script
    assert "getStaticTraceLayerSnapshot" in benchmark_script
    assert "getTraceFacilityFilterMetrics" in benchmark_script
    assert "debug.forceStaticTraceRender" in benchmark_script
    assert "startupPreviewInteractive" in benchmark_script
    assert "startupPanelHidden" in benchmark_script
    assert "startup_benchmark_chrome_local.json" in deploy_doc
    assert "startup_benchmark_edge_local.json" in deploy_doc
    assert "traceFacility.worker.traceIndexLoadMode" in deploy_doc
    assert 'startupTiming.milestones["time to startup profile preview render"]' in deploy_doc
    assert 'startupTiming.milestones["time to Ready"]' in deploy_doc
    assert "startup diagnostics panel hides unless diagnostics are explicitly" in deploy_doc
    assert '"worker_fetch"' in deploy_doc
    assert '"message_buffer"' in deploy_doc


def test_famous_flap_presets_keep_month_ranges_and_descriptive_names():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    bundle_js = Path("static_bundle/app.js").read_text(encoding="utf-8")
    helper_js = Path("webapp/static_public/flap_preset_labels.js").read_text(encoding="utf-8")
    index_html = Path("webapp/static_public/index.html").read_text(encoding="utf-8")

    required_fragments = [
        'id: "flap_1896_1897_airship", name: "Mystery Airship Wave"',
        'id: "flap_1947", name: "Roswell era"',
        'id: "flap_1952", name: "Washington D.C."',
        'id: "flap_1954_france", name: "France wave"',
        'id: "flap_1965_1967", name: "Late-60s wave"',
        'id: "flap_1973", name: "1973 wave"',
        'id: "flap_1989_1990", name: "Belgium Wave"',
        'id: "flap_phoenix_lights", name: "Phoenix Lights"',
        'id: "flap_1997", name: "Phoenix era"',
        'id: "flap_2004", name: "Nimitz era"',
        'startIso: "1989-11-01", endIso: "1990-04-30"',
        'startIso: "1896-11-01", endIso: "1897-06-30"',
        'startIso: "1997-03-12", endIso: "1997-03-14"',
        'description: "1954 France Sept-Nov flap"',
        'flap_1989_1990: "Belgium Wave"',
        'flap_1896_1897_airship: "Mystery Airship Wave"',
        "FLAP_PRESET_LABELS.formatPresetLabel(preset)",
        "FLAP_PRESET_LABELS.formatPresetTitle(preset)",
    ]
    for fragment in required_fragments:
        assert fragment in app_js
        assert fragment in bundle_js
    assert "function formatMonthRange(startIso, endIso)" in helper_js
    assert "function formatPresetLabel(preset)" in helper_js
    assert "function formatPresetTitle(preset)" in helper_js
    assert (
        "flap_preset_labels.js?v=2026-07-31-area-lifecycle-v154"
        in index_html
    )
    assert index_html.index("flap_preset_labels.js") < index_html.index("app.js?v=")


def test_france_heatmap_facility_proximity_defaults_are_wired():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    index_html = Path("webapp/static_public/index.html").read_text(encoding="utf-8")
    bundle_js = Path("static_bundle/app.js").read_text(encoding="utf-8")
    bundle_index_html = Path("static_bundle/index.html").read_text(encoding="utf-8")

    required_app_fragments = [
        'const TRACE_FACILITY_FILTER_STORAGE_VERSION = 4',
        'const TRACE_FACILITY_FILTER_DEFAULT_RADIUS_KM = 5',
        'const TRACE_FACILITY_FILTER_MIN_RADIUS_KM = 1',
        'startIso: "1954-09-01"',
        'endIso: "1954-11-30"',
        'mapMode: MAP_RENDERERS.heatmap',
        'effectiveMapMode: MAP_RENDERERS.heatmap',
        'traceMode: "static"',
        'military: true',
        'researchSites: true',
        'sites: false',
        'claimedUfoBases: false',
        'onlyShowTraceLinkedFacilities: true',
        'if (parsed.version !== TRACE_FACILITY_FILTER_STORAGE_VERSION)',
        'version: TRACE_FACILITY_FILTER_STORAGE_VERSION',
    ]
    for fragment in required_app_fragments:
        assert fragment in app_js
        assert fragment in bundle_js

    for source in (app_js, bundle_js):
        default_filter = _normalize_js_body(
            _extract_js_function_body(source, "defaultTraceFacilityFilterState")
        )
        assert "enabled:false" in default_filter
        assert "radiusKm:TRACE_FACILITY_FILTER_DEFAULT_RADIUS_KM" in default_filter
        assert "evidenceMode:TRACE_FACILITY_DEFAULT_EVIDENCE_MODE" in default_filter
        assert "claimedUfoBases:false" in default_filter

    required_index_fragments = [
        'id="trace-facility-filter-enabled" type="checkbox"',
        'id="trace-facility-radius" type="number" min="1" max="1000" step="1" value="5" disabled',
        'id="trace-facility-evidence-mode" disabled aria-describedby="trace-facility-evidence-help"',
        'id="trace-facility-linked-only" type="checkbox" checked disabled',
        'data-trace-facility-radius-preset="1" disabled',
        'data-trace-facility-radius-preset="2"',
        'data-trace-facility-radius-preset="3"',
        'data-trace-facility-radius-preset="4"',
        'data-trace-facility-radius-preset="5"',
        'data-trace-facility-radius-preset="10"',
        'data-trace-facility-class="start" checked disabled',
        'data-trace-facility-class="passes" disabled',
        'data-trace-facility-source="military" checked disabled',
    ]
    for fragment in required_index_fragments:
        assert fragment in index_html
        assert fragment in bundle_index_html

    assert '<option value="source_coordinates" selected>Strict mode</option>' in index_html
    assert '<option value="include_generalized">Exploratory mode</option>' in index_html


def test_map_control_panel_has_seven_accessible_sections_and_moves_one_control_tree():
    index_html = Path("webapp/static_public/index.html").read_text(encoding="utf-8")
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")

    sections = (
        ("view", "View"),
        ("sightings", "Sightings"),
        ("overlays", "Overlays"),
        ("traces", "Traces"),
        ("facility", "Facility proximity"),
        ("area", "Area selection"),
        ("advanced", "Advanced"),
    )
    discovered = re.findall(
        r'<details id="map-control-section-([^"]+)" class="map-control-section" '
        r'data-map-control-section="([^"]+)"',
        index_html,
    )
    assert discovered == [(key, key) for key, _label in sections]

    for key, label in sections:
        assert index_html.count(f'id="map-control-section-{key}"') == 1
        assert index_html.count(f'id="map-control-{key}-slot"') == 1
        assert index_html.count(f'id="map-control-{key}-summary-state"') == 1
        assert re.search(
            rf'<span class="map-control-summary-label">{re.escape(label)}</span>\s*'
            rf'<span id="map-control-{key}-summary-state" class="map-control-summary-state">',
            index_html,
        )

    assert 'id="map-control-overlay-slot"' not in index_html
    assert 'id="map-control-trace-slot"' not in index_html

    original_control_ids = (
        "map-display-panel",
        "fit-results",
        "legend-panel",
        "map-overlays-panel",
        "trace-controls-panel",
        "trace-facility-filter",
        "area-selection-shell",
    )
    for control_id in original_control_ids:
        assert index_html.count(f'id="{control_id}"') == 1
    assert index_html.count('class="trace-facility-row trace-facility-advanced"') == 1

    mount_cluster = _extract_js_function_body(app_js, "mountMapControlCluster")
    expected_mounts = (
        "els.mapControlViewSlot.appendChild(els.mapSettingsDisplayPanel);",
        "els.mapControlViewSlot.appendChild(els.fitResultsButton);",
        "els.mapControlSightingsSlot.appendChild(els.legendPanel);",
        "els.mapControlOverlaysSlot.appendChild(els.mapSettingsOverlayPanel);",
        "els.mapControlTracesSlot.appendChild(els.traceControlsPanel);",
        "els.mapControlFacilitySlot.appendChild(els.traceFacilityFilter);",
        "els.mapControlAreaSlot.appendChild(els.areaSelectionShell);",
        "els.mapControlAdvancedSlot.appendChild(els.traceFacilityAdvanced);",
    )
    for fragment in expected_mounts:
        assert fragment in mount_cluster
    assert "cloneNode" not in mount_cluster

    assert 'const MAP_CONTROL_SECTION_SESSION_KEY = "ufoTimeline.mapControlSections.v1"' in app_js
    default_open_state = _extract_js_function_body(app_js, "defaultMapControlSectionOpenState")
    for key, _label in sections:
        assert re.search(rf"\b{key}:\s", default_open_state)
    persist_open_state = _extract_js_function_body(app_js, "persistMapControlSectionOpenState")
    assert "safeSessionStorageSet(MAP_CONTROL_SECTION_SESSION_KEY" in persist_open_state


def test_control_panel_compact_labels_and_overlay_counts_are_truthful_and_shared():
    index_html = Path("webapp/static_public/index.html").read_text(encoding="utf-8")
    styles_css = Path("webapp/static_public/styles.css").read_text(encoding="utf-8")
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")

    expected_gap_buttons = {
        "gap_le_1": ("true", "Up to 1 day", "&le;1"),
        "gap_le_2": ("true", "More than 1 and up to 2 days", "1&ndash;2"),
        "gap_le_7": ("false", "More than 2 and up to 7 days", "2&ndash;7"),
        "gap_le_30": ("false", "More than 7 and up to 30 days", "7&ndash;30"),
        "gap_gt_30": ("false", "More than 30 days", "&gt;30"),
    }
    assert 'role="group" aria-label="Trace time-gap buckets"' in index_html
    assert '<span class="trace-bucket-heading">Gap between sightings (days)</span>' in index_html
    for key, (pressed, accessible_label, visible_label) in expected_gap_buttons.items():
        assert (
            f'data-trace-bucket="{key}" aria-pressed="{pressed}" '
            f'aria-label="{accessible_label}">{visible_label}</button>'
        ) in index_html

    required_facility_fragments = (
        '<option value="source_coordinates" selected>Strict mode</option>',
        '<option value="include_generalized">Exploratory mode</option>',
        '>Endpoint near facility</span>',
        'data-trace-facility-class="start" checked disabled aria-label="Start endpoint near facility"',
        'data-trace-facility-class="end" checked disabled aria-label="End endpoint near facility"',
        'data-trace-facility-class="between" checked disabled aria-label="Both endpoints near facilities"',
        '<span>Start</span>',
        '<span>End</span>',
        '<span>Both ends</span>',
        'aria-label="Only show facilities linked to visible traces"',
        'Strict mode includes only source-provided endpoint coordinates with exact event dates',
        "facility's recorded operating period supports that date",
        "Year-only opening or closing years remain uncertain.",
    )
    for fragment in required_facility_fragments:
        assert fragment in index_html

    counted_overlay_rows = (
        ("overlay-research-sites", "overlay-research-sites-count", "Research sites"),
        ("overlay-crop-circles", "overlay-crop-circles-count", "Crop circles"),
        ("overlay-animal-mutilations", "overlay-animal-mutilations-count", "Mutilations"),
    )
    for button_id, count_id, visible_label in counted_overlay_rows:
        assert index_html.count(f'id="{button_id}"') == 1
        assert index_html.count(f'id="{count_id}"') == 1
        assert 'class="overlay-chip-label"' in index_html or 'class="overlay-chip-label" aria-hidden="true"' in index_html
        assert f'>{visible_label}</span>' in index_html
    animal_button = re.search(
        r'<button id="overlay-animal-mutilations"[^>]+>',
        index_html,
    )
    assert animal_button is not None
    assert 'aria-label="Animal Mutilation Reports"' in animal_button.group(0)
    assert ".overlay-chip-group-secondary" in styles_css
    assert ".overlay-chip-secondary-row" in styles_css
    assert ".overlay-chip-count" in styles_css

    compact_counts = _extract_js_function_body(app_js, "renderCompactOverlayCounts")
    map_legend_rows = _extract_js_function_body(app_js, "buildMapLegendOverlayRows")
    assert "const counts = currentOverlayCountModel();" in compact_counts
    assert "const overlayCounts = currentOverlayCountModel();" in map_legend_rows
    for key in ("researchSites", "cropCircles", "animalMutilations"):
        assert f"counts.{key}" in compact_counts
    assert "overlayCounts.researchByCategory.get(category)" in map_legend_rows
    assert "overlayCounts.cropCircles" in map_legend_rows
    assert "overlayCounts.animalMutilations" in map_legend_rows


def test_map_control_cluster_body_is_the_only_section_scroller():
    styles_css = Path("webapp/static_public/styles.css").read_text(encoding="utf-8")

    def rule(selector: str) -> str:
        match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", styles_css, re.DOTALL)
        assert match is not None, selector
        return match.group(1)

    cluster_body = rule(".map-control-cluster-body")
    slot = rule(".map-control-slot")
    open_section = rule(".map-control-section[open]")
    mounted_area_panel = rule(".map-control-slot .area-selection-panel")
    mounted_area_shell = rule(".map-control-slot .area-selection-shell")

    assert "overflow-y: auto;" in cluster_body
    assert "overflow-x: hidden;" in cluster_body
    assert "overflow: visible;" in slot
    assert "overflow-y:" not in slot
    assert "flex: 0 0 auto;" in open_section
    assert "max-height: none;" in mounted_area_panel
    assert "overflow: visible;" in mounted_area_panel
    assert "position: static;" in mounted_area_shell


def test_area_selection_zero_hops_is_the_independent_default():
    index_html = Path("webapp/static_public/index.html").read_text(encoding="utf-8")
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    helper_js = Path("webapp/static_public/trace_neighborhood.js").read_text(encoding="utf-8")

    depth_select = re.search(
        r'<select id="area-selection-depth"[^>]*>(.*?)</select>',
        index_html,
        re.DOTALL,
    )
    assert depth_select is not None
    depth_markup = depth_select.group(1)
    assert '<option value="0" selected>0 hops</option>' in depth_markup
    assert '<option value="1">1 hop</option>' in depth_markup
    assert '<option value="1" selected>' not in depth_markup

    assert "const CHRONOLOGICAL_NEIGHBORHOOD_DEFAULT_DEPTH = 0;" in app_js
    default_region = _normalize_js_body(_extract_js_function_body(app_js, "defaultRegionSelectionState"))
    assert "depth:CHRONOLOGICAL_NEIGHBORHOOD_DEFAULT_DEPTH" in default_region
    area_normalizer = _normalize_js_body(_extract_js_function_body(helper_js, "normalizeAreaDepth"))
    generic_normalizer = _normalize_js_body(_extract_js_function_body(helper_js, "normalizeDepth"))
    assert "Math.max(0,Math.min(4," in area_normalizer
    assert "Math.max(1,Math.min(4," in generic_normalizer

    region_ui = _extract_js_function_body(app_js, "renderRegionSelectionUi")
    assert "const directionInactive = TRACE_NEIGHBORHOOD.normalizeAreaDepth(state.regionSelection.depth) === 0;" in region_ui
    assert "els.areaSelectionDirectionSelect.disabled = directionInactive;" in region_ui
    assert 'els.areaSelectionDirectionSelect.setAttribute("aria-disabled", directionInactive ? "true" : "false");' in region_ui


def test_map_control_cluster_defaults_to_full_portrait_and_desktop_height_and_preserves_manual_resize():
    for app_path in (Path("webapp/static_public/app.js"), Path("static_bundle/app.js")):
        app_js = app_path.read_text(encoding="utf-8")
        apply_cluster_state = _normalize_js_body(
            _extract_js_function_body(app_js, "applyMapControlClusterState")
        )
        event_handlers = _extract_js_function_body(app_js, "attachEventHandlers")
        section_toggle_start = event_handlers.index('section.addEventListener("toggle"')
        section_toggle_end = event_handlers.index("window.addEventListener(\"pointermove\"", section_toggle_start)
        section_toggle = event_handlers[section_toggle_start:section_toggle_end]

        assert "constautoHeight=isMobileLandscapeLayout()?measureMapControlClusterAutoHeight():heightBounds.maxHeight;" in apply_cluster_state
        assert "constheightAwarePosition=clampMapControlClusterPosition(" in apply_cluster_state
        assert "els.mapControlCluster.style.top=heightAwarePosition.y+\"px\";" in apply_cluster_state
        assert "applyMapControlClusterState();" in section_toggle
        assert "clearMapControlClusterManualHeight" not in section_toggle
        assert "function clearMapControlClusterManualHeight()" not in app_js


def test_mobile_landscape_is_full_bleed_and_uses_the_compact_header():
    for root in (Path("webapp/static_public"), Path("static_bundle")):
        app_js = (root / "app.js").read_text(encoding="utf-8")
        index_html = (root / "index.html").read_text(encoding="utf-8")
        styles_css = (root / "styles.css").read_text(encoding="utf-8")

        viewport_content = re.search(
            r'<meta\s+name="viewport"\s+content="([^"]+)"',
            index_html,
        )
        assert viewport_content is not None
        viewport_tokens = {
            token.strip() for token in viewport_content.group(1).split(",")
        }
        assert viewport_tokens == {
            "width=device-width",
            "initial-scale=1",
            "viewport-fit=cover",
            "shrink-to-fit=no",
        }
        assert "maximum-scale" not in viewport_content.group(1)
        assert "user-scalable" not in viewport_content.group(1)

        required_fragments = [
            "--safe-area-top: env(safe-area-inset-top, 0px);",
            "--safe-area-right: env(safe-area-inset-right, 0px);",
            "--safe-area-bottom: env(safe-area-inset-bottom, 0px);",
            "--safe-area-left: env(safe-area-inset-left, 0px);",
            "background-color: var(--bg);",
            ":root.mobile-landscape-ui body",
            "max(6px, var(--safe-area-top))",
            "max(10px, var(--safe-area-bottom))",
            ":root.mobile-landscape-ui .page-shell",
            "max-width: none;",
            ":root.mobile-landscape-ui .hero",
            'grid-template-areas: "copy stats";',
            ":root.mobile-landscape-ui #appearance-panel",
            ":root.mobile-landscape-ui .mobile-appearance-controls",
            ":root.mobile-landscape-ui .hero-attribution",
            ":root.mobile-landscape-ui .map-panel",
            "left: max(12px, calc(var(--safe-area-left) + 6px)) !important;",
            "padding-right: max(18px, var(--safe-area-right));",
        ]
        for fragment in required_fragments:
            assert fragment in styles_css

        required_app_fragments = [
            "function isTouchCapableDevice()",
            'window.matchMedia("(any-pointer: coarse)").matches',
            "Number(navigator.maxTouchPoints) || 0",
            "isTouchCapableDevice() &&",
            'classList.toggle("mobile-landscape-ui", isMobileLandscapeLayout())',
        ]
        for fragment in required_app_fragments:
            assert fragment in app_js

        assert styles_css.index(":root.mobile-landscape-ui body") < styles_css.index(
            ":root.mobile-landscape-ui .layout"
        )


def test_facility_proximity_quick_cycle_is_visible_accessible_and_synchronized():
    for root in (Path("webapp/static_public"), Path("static_bundle")):
        app_js = (root / "app.js").read_text(encoding="utf-8")
        index_html = (root / "index.html").read_text(encoding="utf-8")
        styles_css = (root / "styles.css").read_text(encoding="utf-8")

        quick_group_start = index_html.index('<div class="map-control-quick-controls"')
        proximity_group_start = index_html.index('<div class="map-control-proximity-control"')
        assert quick_group_start < proximity_group_start
        assert index_html.index("</div>", quick_group_start) < proximity_group_start

        required_index_fragments = [
            'id="cluster-quick-facility-proximity"',
            'data-state="off"',
            'aria-pressed="false"',
            'Facility proximity quick cycle. Current: Off. Next: 3 kilometers.',
            'Facility proximity is off. Click to enable at 3 kilometers.',
            '>Off</span>',
            'aria-controls="trace-facility-filter-enabled trace-facility-radius"',
            'id="cluster-quick-facility-value"',
            '>Facility proximity</span>',
            'id="map-quick-control-status"',
            'role="status" aria-live="polite" aria-atomic="true"',
            'data-trace-facility-radius-preset="10"',
            'role="group" aria-label="Trace facility proximity filter"',
        ]
        for fragment in required_index_fragments:
            assert fragment in index_html

        required_app_fragments = [
            "const TRACE_FACILITY_QUICK_RADIUS_STEPS_KM = Object.freeze([3, 5, 10]);",
            "function currentQuickFacilityProximityState()",
            "function cycleQuickFacilityProximity()",
            'key: "custom"',
            'nextLabel: "Off"',
            "clusterQuickFacilityProximityButton",
            "clusterQuickFacilityValue",
            "mapQuickControlStatus",
            "renderMapControlQuickButtons();",
        ]
        for fragment in required_app_fragments:
            assert fragment in app_js

        cycle_body = _extract_js_function_body(app_js, "cycleQuickFacilityProximity")
        assert "persistTraceFacilityFilterState();" in cycle_body
        assert "refreshTracesForFacilityFilterChange();" in cycle_body
        assert "announceMapQuickControl(" in cycle_body

        required_style_fragments = [
            ".map-control-proximity-control",
            '.map-control-proximity-button[aria-pressed="true"]',
            '.map-control-proximity-button[data-state="custom"]',
            ".map-control-proximity-button:focus-visible",
            ".map-control-proximity-value",
            ".map-control-cluster.is-collapsed .map-control-proximity-label",
            ".map-control-cluster.is-collapsed .map-control-proximity-control",
            "display: none;",
        ]
        for fragment in required_style_fragments:
            assert fragment in styles_css


def test_context_layer_quick_toggles_are_adjacent_accessible_and_synchronized():
    for root in (Path("webapp/static_public"), Path("static_bundle")):
        app_js = (root / "app.js").read_text(encoding="utf-8")
        index_html = (root / "index.html").read_text(encoding="utf-8")
        styles_css = (root / "styles.css").read_text(encoding="utf-8")

        trace_button = index_html.index('id="cluster-quick-trace"')
        context_group = index_html.index('<div class="map-control-context-controls"')
        crop_button = index_html.index('id="cluster-quick-crop-circles"')
        animal_button = index_html.index('id="cluster-quick-animal-mutilations"')
        proximity_group = index_html.index('<div class="map-control-proximity-control"')
        assert trace_button < context_group < crop_button < animal_button < proximity_group

        required_index_fragments = [
            'class="map-control-quick-row"',
            'role="group" aria-label="Context layer quick toggles"',
            'aria-controls="map crop-circle-status"',
            'aria-controls="map animal-mutilation-status"',
            'class="map-legend-marker-sample map-legend-marker-sample-spiral"',
            'class="map-legend-marker-sample map-legend-marker-sample-cow"',
            'styles.css?v=2026-08-09-control-panel-area-v1',
            'app.js?v=2026-08-09-control-panel-area-v1',
        ]
        for fragment in required_index_fragments:
            assert fragment in index_html

        required_app_fragments = [
            'clusterQuickCropCirclesButton: document.querySelector("#cluster-quick-crop-circles")',
            'clusterQuickAnimalMutilationsButton: document.querySelector("#cluster-quick-animal-mutilations")',
            'els.overlayCropCirclesToggle.click();',
            'els.overlayAnimalMutilationsToggle.click();',
            'function setQuickContextButtonState(button, canonicalButton, active, label)',
            'canonicalButton.getAttribute("aria-busy") === "true"',
            'nextActive ? "Crop circles are turning on." : "Crop circles hidden."',
            '? "Animal Mutilation Reports are turning on."',
            ': "Animal Mutilation Reports hidden."',
            'function observeQuickContextCanonicalButton(canonicalButton)',
            'attributeFilter: ["aria-pressed", "aria-busy", "disabled"]',
        ]
        for fragment in required_app_fragments:
            assert fragment in app_js

        required_style_fragments = [
            '--crop-circle-art: url("data:image/svg+xml,',
            'background: var(--crop-circle-art) center / contain no-repeat;',
            '.map-control-quick-row',
            '.map-control-context-controls',
            '.map-control-context-button-crop[aria-pressed="true"]',
            '.map-control-context-button-animal[aria-pressed="true"]',
            '.map-control-context-button[aria-pressed="false"] .map-legend-marker-sample',
            '.map-control-cluster.is-collapsed .map-control-context-controls',
        ]
        for fragment in required_style_fragments:
            assert fragment in styles_css


def test_shell_assets_match_the_rebuilt_static_bundle():
    for filename in (
        "app.js",
        "index.html",
        "styles.css",
        "legend_controls.js",
        "flap_preset_labels.js",
        "playback_performance.js",
        "catalog_filter_worker.js",
        "analysis_stats.js",
        "analysis_view.js",
        "analysis_spatial.js",
        "analysis_spatial_worker.js",
        "_headers",
    ):
        assert (Path("webapp/static_public") / filename).read_bytes() == (
            Path("static_bundle") / filename
        ).read_bytes()

    for filename in (
        "manifest.json",
        "crop_circles.json",
        "crop_circles.json.gz",
        "animal_reports.json",
        "animal_reports.json.gz",
    ):
        assert (Path("webapp/static_public/data/analysis_v1") / filename).read_bytes() == (
            Path("static_bundle/data/analysis_v1") / filename
        ).read_bytes()

    for filename in (
        "manifest.json",
        "ufo_point_neighbors_v1.json",
        "ufo_point_neighbors_v1.json.gz",
        "ufo_spatial_points_v2.json",
        "ufo_spatial_points_v2.json.gz",
        "context_ufo_neighbors_v1.json",
        "context_ufo_neighbors_v1.json.gz",
        "ufo_geography_v1.json",
        "ufo_geography_v1.json.gz",
        "ufo_geography_v1.bin",
        "ufo_geography_v1.bin.gz",
        "ufo_configuration_points_v1.json",
        "ufo_configuration_points_v1.json.gz",
        "ufo_configuration_neighbors_v1.json",
        "ufo_configuration_neighbors_v1.json.gz",
        "facility_analysis_v1.json",
        "facility_analysis_v1.json.gz",
        "crop_context_readiness.json",
        "crop_context_readiness.json.gz",
        "animal_context_readiness.json",
        "animal_context_readiness.json.gz",
        "relationship_reconciliation.json",
        "relationship_reconciliation.json.gz",
        "relationship_source_snapshot.json",
        "relationship_source_snapshot.json.gz",
        "relationship_source_snapshot.meta.json",
    ):
        assert (Path("webapp/static_public/data/analysis_v2") / filename).read_bytes() == (
            Path("static_bundle/data/analysis_v2") / filename
        ).read_bytes()


def test_analysis_app_runtime_contract_is_wired_to_existing_filter_and_map_lifecycle():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    worker_js = Path("webapp/static_public/catalog_filter_worker.js").read_text(encoding="utf-8")
    stats_js = Path("webapp/static_public/analysis_stats.js").read_text(encoding="utf-8")

    for fragment in (
        'activeView: "map"',
        "function getAnalysisFilterSnapshot()",
        "function applyAnalysisFilterPatch(rawPatch)",
        "function handleAnalysisViewChange(nextView)",
        "function restoreMapAfterAnalysis()",
        'controller.setAnalysisEnabled(false, "Analysis becomes available when the core catalog is ready.")',
        "runtime.map.invalidateSize({ animate: false, pan: false })",
        'type: "computeAnalysis"',
        'message.type === "analysisComputed"',
        'quickMode: true',
        'selectedDomains: ["overview", "time", "sources_quality", "context"]',
        'runtime.analysisFullInferenceTimerId = window.setTimeout(function ()',
        'areaFilterShapes: snapshot.areaFilter && snapshot.areaFilter.active ? snapshot.areaFilter.shapes : []',
        'craft_type_confidence: internCanonicalSummaryString(event.craft_type_confidence)',
        'craft_type_source: internCanonicalSummaryString(event.craft_type_source)',
        'const ANALYSIS_CATALOG_DATASET_SHA256 = "242ff4abc42c70c2b241a3cd16c8b9059bca137d940bd6147c5a65de63b7750b"',
        'catalog_filter_worker.js?v=2026-08-05-analysis-color-v1-ui1',
        "Promise.all([manifestPromise, ensureWorldReferenceData()])",
        "getWorldReferenceData: function () { return runtime.worldReferenceData; }",
        "function ensureAnalysisContextEvidence()",
        'type: "setAnalysisContextSpatialArtifact"',
        'message.type === "analysisContextSpatialArtifactSet"',
        'ensureAnalysisRelationshipArtifact({ deferCompute: true })',
        'ensureAnalysisContextSpatialArtifact({ deferCompute: true })',
    ):
        assert fragment in app_js

    assert (
        "state.analysisBaselineMode = nextMode;\n"
        "        syncAnalysisDateRangeSummary();\n"
        "        // The cache signature already includes the reference baseline and every\n"
        "        // scientific input. Preserve other exact baseline results so a warm\n"
        "        // comparison can be restored without recomputation.\n"
        '        scheduleAnalysisCompute("baseline changed", { immediate: true });'
    ) in app_js
    assert (
        "state.analysisBaselineMode = nextMode;\n"
        "        syncAnalysisDateRangeSummary();\n"
        "        runtime.analysisCache.clear();"
    ) not in app_js

    compute_body = _extract_js_function_body(app_js, "computeAnalysisForCurrentView")
    assert "Full inference stays off the main thread." in compute_body
    assert "}, 0);" in compute_body
    assert "}, 900);" not in compute_body

    for fragment in (
        'message.type === "setAnalysisContextProjections"',
        'message.type === "setAnalysisContextSpatialArtifact"',
        'message.type === "computeAnalysis"',
        'type: "analysisComputed"',
        "pointInsideAnyAnalysisShape",
        "verifyAnalysisBytes",
        "validateSpatialManifestArtifact",
        "validateLoadedSpatialArtifact",
        'url.searchParams.set("sha256", sha256)',
        "analysisSpatialArtifactLoadEpoch",
        "analysisCacheKey",
        "quickMode: Boolean(message.quickMode)",
        'importScripts("./analysis_stats.js?v=" + ANALYSIS_RUNTIME_CACHE_KEY)',
        'importScripts("./analysis_spatial.js?v=" + ANALYSIS_RUNTIME_CACHE_KEY)',
        'analysis_spatial_worker.js?v=" + ANALYSIS_RUNTIME_CACHE_KEY',
    ):
        assert fragment in worker_js

    for prohibited in (
        "traceSegments",
        "trace_segments",
        "chronologySegments",
        "flight path",
    ):
        assert prohibited not in stats_js


def test_analysis_dashboards_collapse_secondary_evidence_without_removing_charts():
    index_html = Path("webapp/static_public/index.html").read_text(encoding="utf-8")
    styles_css = Path("webapp/static_public/styles.css").read_text(encoding="utf-8")
    supporting_cards = {
        "Reporting timing evidence": "analysis-reporting-delay-chart",
        "Recurring month-by-craft signal": "analysis-month-year-chart",
        "Craft by era": "analysis-craft-era-chart",
        "Classification confidence": "analysis-craft-confidence-chart",
        "Geography by era": "analysis-geography-time-chart",
        "Context-marker neighborhoods": "analysis-context-neighborhood-chart",
        "Facility context": "analysis-facility-context-chart",
        "Coordinate evidence quality": "analysis-coordinate-evidence-spatial-chart",
        "Cross-domain readiness": "analysis-cross-domain-readiness-chart",
        "Catalog composition": "analysis-crop-morphology-chart",
        "Location, coverage, and point evidence": "analysis-crop-coordinate-chart",
        "Report composition": "analysis-animal-species-chart",
        "Date, coverage, and public-marker evidence": "analysis-animal-date-precision-chart",
        "Coverage and event taxonomy": "analysis-quality-missingness-chart",
        "Craft classification and source dependence": "analysis-craft-residual-chart",
        "Coordinate provenance and quality": "analysis-coordinate-evidence-chart",
        "Explicit witness counts": "analysis-witness-count-chart",
    }

    disclosures = re.findall(
        r'<details\b[^>]*class="[^"]*analysis-dashboard-support[^"]*"[^>]*>',
        index_html,
    )
    assert len(disclosures) == len(supporting_cards)
    assert all(" open" not in disclosure for disclosure in disclosures)
    closed_disclosure_rule = styles_css.split(
        ".analysis-supporting-details:not([open]) {", 1
    )[1].split("}", 1)[0]
    assert "content-visibility: visible" in closed_disclosure_rule
    assert "contain-intrinsic-size: none" in closed_disclosure_rule
    assert ".analysis-supporting-details:not([open]) > :not(summary)" in styles_css
    assert "display: none" in styles_css.split(
        ".analysis-supporting-details:not([open]) > :not(summary)", 1
    )[1].split("}", 1)[0]

    for summary, chart_id in supporting_cards.items():
        pattern = (
            r'<details\b[^>]*class="[^"]*analysis-dashboard-support[^"]*"[^>]*>'
            rf'<summary>{re.escape(summary)}</summary>.*?id="{re.escape(chart_id)}"'
        )
        assert re.search(pattern, index_html, flags=re.DOTALL), summary

    nested_duration = (
        r'<details\b[^>]*class="[^"]*analysis-reporting-delay-card[^"]*"[^>]*>'
        r'.*?<details\b[^>]*class="[^"]*analysis-supporting-details[^"]*"[^>]*>'
        r'<summary>Reported observation duration</summary>.*?id="analysis-duration-chart"'
    )
    assert re.search(nested_duration, index_html, flags=re.DOTALL)
    nested_source_mix = (
        r'<article\b[^>]*class="[^"]*analysis-source-composite-card[^"]*"[^>]*>'
        r'.*?<details\b[^>]*class="[^"]*analysis-supporting-details[^"]*"[^>]*>'
        r'<summary>Source mix over time</summary>.*?id="analysis-source-time-chart"'
    )
    assert re.search(nested_source_mix, index_html, flags=re.DOTALL)

    for primary_chart_id in (
        "analysis-time-series-chart",
        "analysis-craft-distribution-chart",
        "analysis-geography-grid-chart",
        "analysis-cooccurrence-chart",
        "analysis-crop-time-chart",
        "analysis-source-composition-chart",
    ):
        assert f'id="{primary_chart_id}"' in index_html

    assert (
        '<details id="analysis-spatial-matrix-disclosure" class="analysis-supporting-details analysis-spatial-matrix-support">'
        '<summary>Craft co-occurrence matrix</summary>'
        '<div id="analysis-cooccurrence-chart"'
    ) in index_html
    assert (
        'analysis-spatial-matrix-support" open'
    ) not in index_html
    assert 'id="analysis-spatial-context-disclosure"' in index_html
    assert 'id="analysis-spatial-facility-disclosure"' in index_html
    assert 'caption: "High-precision co-occurrence pool", endpointsOnly: true' in Path(
        "webapp/static_public/analysis_view.js"
    ).read_text(encoding="utf-8")


def test_first_time_activation_defers_optional_sidecars_until_core_render():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    assert 'if (state.activeView === "analysis") {\n            requestAnalysisTimeEvidence();' in app_js
    assert "runtime.analysisTimeEvidenceLoadPending = true;" in app_js
    assert 'if (runtime.analysisTimeEvidenceLoadPending && state.activeView === "analysis") {' in app_js
    assert "runtime.analysisTimeEvidenceLoadPending = false;\n          requestAnalysisTimeEvidence();" in app_js


def test_analysis_area_filter_is_point_only_and_never_builds_a_chronology_index():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")

    apply_area_body = _extract_js_function_body(app_js, "applyAnalysisAreaFilter")
    assert "pointOnly: true" in apply_area_body
    assert "selectTraces: false" in apply_area_body
    assert "selectEvents: true" in apply_area_body
    assert 'String(candidate.type || "").toLowerCase() === "country"' in apply_area_body
    assert "state.analysisCountryAreaFilter = country;" in apply_area_body
    assert "skipAnalysis: true" in apply_area_body

    render_state_body = _extract_js_function_body(app_js, "refreshRegionSelectionRenderState")
    assert "if (!config.skipAnalysis)" in render_state_body
    assert 'scheduleAnalysisCompute("area filter changed")' in render_state_body

    patch_body = _extract_js_function_body(app_js, "applyAnalysisFilterPatch")
    assert "if (areaChanged)" in patch_body
    assert "return refreshFilters().then(function ()" in patch_body
    assert patch_body.count("refreshFilters().then(function ()") == 2

    seed_body = _extract_js_function_body(app_js, "currentPointOnlyRegionSelectionSeeds")
    assert "for (const event of state.filteredMappedCatalog)" in seed_body
    assert 'source: "mapped_report_points_only"' in seed_body
    for prohibited in (
        "currentChronologicalNeighborhoodIndex",
        "currentChronologicalNeighborhoodSeeds",
        "TRACE_NEIGHBORHOOD",
        "segment",
    ):
        assert prohibited not in seed_body

    result_body = _extract_js_function_body(app_js, "computeRegionSelectionResult")
    assert "const index = pointOnly ? null : currentChronologicalNeighborhoodIndex();" in result_body
    assert "? currentPointOnlyRegionSelectionSeeds(shapes, shapeBounds)" in result_body
    assert ": currentChronologicalNeighborhoodSeeds(index, shapes, shapeBounds);" in result_body
    assert "TRACE_NEIGHBORHOOD.computeAreaZeroHopSelection({" in result_body
    assert "TRACE_NEIGHBORHOOD.traverseNeighborhood({" in result_body
    assert "const areaDepth = TRACE_NEIGHBORHOOD.normalizeAreaDepth" in result_body
    assert "chronologyIndexUsed: !pointOnly" in result_body
    assert "traceSegments: pointOnly ? [] : index.segments" in result_body

    assert "pointOnly: Boolean(regionResult.pointOnly || state.regionSelection.pointOnly)" in app_js
    assert "chronologyIndexUsed: Boolean(regionResult.chronologyIndexUsed)" in app_js
    assert "visibleMappedEventIds: (regionResult.visibleMappedCatalog || [])" in app_js
    assert "resultEventIds: currentVisibleResultsCatalog().map(function (event)" in app_js


def test_analysis_v2_manifest_is_versioned_with_the_app_shell_release():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    versioned_asset_body = _normalize_js_body(
        _extract_js_function_body(app_js, "shouldVersionStaticAsset")
    )
    resolve_asset_body = _normalize_js_body(
        _extract_js_function_body(app_js, "resolveAssetPath")
    )

    assert 'path.indexOf("/data/analysis_v2/")!==-1' in versioned_asset_body
    assert 'url.searchParams.set("v",versionToken)' in resolve_asset_body
    for loader_name in (
        "ensureAnalysisGeographyArtifact",
        "ensureAnalysisRelationshipArtifact",
        "ensureAnalysisContextSpatialArtifact",
        "ensureAnalysisSpatialArtifacts",
    ):
        loader_body = _extract_js_function_body(app_js, loader_name)
        assert 'resolveAssetPath("./data/analysis_v2/manifest.json")' in loader_body


def test_country_area_filter_is_visible_human_labeled_clearable_and_atomic():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")

    active_body = _extract_js_function_body(app_js, "areaFilterHasActiveSelection")
    assert "regionSelectionHasActiveShapes() || analysisCountryAreaFilterActive()" in active_body

    affects_rendering_body = _extract_js_function_body(app_js, "regionSelectionAffectsRendering")
    assert "return areaFilterHasActiveSelection();" in affects_rendering_body

    ui_body = _extract_js_function_body(app_js, "renderRegionSelectionUi")
    for fragment in (
        "const countryLabel = analysisCountryAreaFilterLabel();",
        '"Area Filter \u00b7 " + countryLabel',
        '"Country Area Filter active: " + countryLabel',
        "els.undoAreaSelectionButton.disabled = !hasAreaFilter;",
        "els.clearAreaSelectionButton.disabled = !hasAreaFilter;",
        "els.resultsAreaFilterIndicator.hidden = !hasAreaFilter;",
        "els.resultsAreaFilterClearButton.disabled = !hasAreaFilter;",
    ):
        assert fragment in ui_body

    summary_body = _extract_js_function_body(app_js, "regionSelectionSummaryText")
    assert '"Country: " + countryLabel' in summary_body
    assert '" mapped report points \u00b7 point-only"' in summary_body

    country_result_body = _extract_js_function_body(app_js, "countryAreaFilterResult")
    for fragment in (
        'reason: "worker-filtered country report points only"',
        "traceSegments: []",
        "visibleTraceSegments: []",
        "neighborhoodSegments: []",
        "pointOnly: true",
        "chronologyIndexUsed: false",
        "needsTraceSegments: false",
    ):
        assert fragment in country_result_body
    for prohibited in (
        "currentChronologicalNeighborhoodIndex",
        "currentChronologicalNeighborhoodSeeds",
        "buildCanonicalTraceSegments",
    ):
        assert prohibited not in country_result_body

    trace_visibility_body = _extract_js_function_body(app_js, "traceLinkedVisibilityAffectsRendering")
    assert "if (areaFilterHasActiveSelection() && state.regionSelection.pointOnly) return false;" in trace_visibility_body

    clear_body = _extract_js_function_body(app_js, "clearAllRegionSelectionShapes")
    assert "const hadCountryArea = Boolean(state.analysisCountryAreaFilter);" in clear_body
    assert 'state.analysisCountryAreaFilter = "";' in clear_body
    assert "state.regionSelection.pointOnly = false;" in clear_body
    assert clear_body.count("refreshFilters().catch(function (error)") == 1

    undo_body = _extract_js_function_body(app_js, "undoLastRegionSelectionShape")
    assert 'state.analysisCountryAreaFilter = "";' in undo_body
    assert undo_body.count("refreshFilters().catch(function (error)") == 1

    bind_body = _extract_js_function_body(app_js, "attachEventHandlers")
    assert bind_body.count("clearAllRegionSelectionShapes();") >= 2


def test_context_only_evidence_loader_is_deduplicated_retryable_and_cache_safe():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")

    layer_status_body = _extract_js_function_body(app_js, "contextLayerAnalysisStatus")
    assert "const requestedEnabled = Boolean(" in layer_status_body
    assert "const merged = Object.assign({ loaded: false }, status || {});" in layer_status_body
    assert "merged.enabled = requestedEnabled;" in layer_status_body
    assert layer_status_body.index("Object.assign({ loaded: false }, status || {})") < layer_status_body.index("merged.enabled = requestedEnabled")

    initialize_body = _extract_js_function_body(app_js, "initializeAnalysisView")
    assert 'change && change.sectionKey === "context"' in initialize_body
    assert "ensureAnalysisContextEvidence().catch(function () { return null; });" in initialize_body
    assert "if (runtime.analysisContextEvidenceError)" in initialize_body
    assert "onRenderComplete: function ()" in initialize_body
    assert "if (runtime.analysisContextEvidenceRenderPending)" in initialize_body
    assert 'setAnalysisContextEvidenceSectionState("ready", "Context relationship and point-neighborhood evidence ready.");' in initialize_body

    result_context_body = _extract_js_function_body(app_js, "analysisResultHasContextEvidence")
    assert 'status.indexOf("context_evidence_ready") !== -1' in result_context_body
    assert "Array.isArray(associations.lanes)" in result_context_body
    assert "Array.isArray(relationships.cells)" in result_context_body

    render_result_body = _extract_js_function_body(app_js, "renderAnalysisWorkerResult")
    assert "runtime.analysisContextEvidenceRenderPending = true;" in render_result_body
    assert 'setAnalysisContextEvidenceSectionState("loading", "Context evidence computed; rendering the selected Context view...");' in render_result_body
    assert render_result_body.index("runtime.analysisContextEvidenceRenderPending = true;") < render_result_body.index("runtime.analysisViewController.renderAnalysisResult(result")

    context_body = _extract_js_function_body(app_js, "ensureAnalysisContextEvidence")
    for fragment in (
        "runtime.analysisContextEvidenceRequested = true;",
        "if (analysisContextEvidenceArtifactsReady())",
        "if (runtime.analysisContextEvidencePromise) return runtime.analysisContextEvidencePromise;",
        "ensureAnalysisRelationshipArtifact({ deferCompute: true })",
        "ensureAnalysisContextSpatialArtifact({ deferCompute: true })",
        "runtime.analysisCache.clear();",
        'setAnalysisContextEvidenceSectionState("loading", "Context evidence loaded; updating the selected date and filters...");',
        "if (!runtime.analysisSpatialRequested)",
        'scheduleAnalysisCompute("context evidence ready", { immediate: true });',
        "runtime.analysisContextEvidencePromise = null;",
        "runtime.analysisContextEvidenceRequested = false;",
        'setAnalysisContextEvidenceSectionState("error"',
    ):
        assert fragment in context_body
    assert context_body.count('scheduleAnalysisCompute("context evidence ready", { immediate: true });') == 1
    for prohibited in (
        "ensureAnalysisSpatialArtifacts(",
        "runtime.analysisSpatialRequested = true",
        "ufo_configuration",
        "Formation",
    ):
        assert prohibited not in context_body

    relationship_body = _extract_js_function_body(app_js, "setAnalysisRelationshipArtifactInWorker")
    context_spatial_body = _extract_js_function_body(app_js, "setAnalysisContextSpatialArtifactInWorker")
    assert 'type: "setAnalysisRelationshipArtifact"' in relationship_body
    assert 'type: "setAnalysisContextSpatialArtifact"' in context_spatial_body
    assert 'type: "setAnalysisSpatialArtifacts"' not in relationship_body
    assert 'type: "setAnalysisSpatialArtifacts"' not in context_spatial_body

    manifest_body = _extract_js_function_body(app_js, "ensureAnalysisV2Manifest")
    assert "if (runtime.analysisV2ManifestPromise) return runtime.analysisV2ManifestPromise;" in manifest_body
    assert 'fetch(manifestUrl, { cache: "force-cache" })' in manifest_body
    assert "runtime.analysisV2ManifestPromise = null;" in manifest_body

    full_spatial_body = _extract_js_function_body(app_js, "ensureAnalysisSpatialArtifacts")
    for fragment in (
        "runtime.analysisRelationshipPromise",
        "runtime.analysisContextSpatialPromise",
        "contextPartialSetupsSettled",
        "ensureAnalysisV2Manifest(manifestUrl)",
        "Promise.all([",
        "setAnalysisSpatialArtifactsInWorker(manifest, manifestUrl)",
    ):
        assert fragment in full_spatial_body
    assert full_spatial_body.index("contextPartialSetupsSettled") < full_spatial_body.index("setAnalysisSpatialArtifactsInWorker")

    cache_key_body = _extract_js_function_body(app_js, "analysisComputeCacheKey")
    for fragment in (
        "relationshipRequested:",
        "relationshipReady:",
        "contextSpatialRequested:",
        "contextSpatialReady:",
        "artifactHashes:",
    ):
        assert fragment in cache_key_body


def test_analysis_worker_envelope_invalidates_before_debounce_and_rechecks_full_signature():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")

    signature_body = _extract_js_function_body(app_js, "analysisComputeCacheKey")
    for fragment in (
        "generation:",
        "baselineMode:",
        "timeRange:",
        "filters:",
        "areaPointOnly:",
        "areaShapes:",
        "crops:",
        "animals:",
        "contextHashes:",
        "datasetHash:",
    ):
        assert fragment in signature_body

    response_guard_body = _extract_js_function_body(
        app_js, "analysisResponseEnvelopeMatchesCurrentState"
    )
    assert "analysisComputeCacheKey(snapshotOrSignature || getAnalysisFilterSnapshot())" in response_guard_body
    assert "window.UfoAnalysisView.analysisRequestEnvelopeMatches(pending, message, currentSignature)" in response_guard_body

    worker_body = _extract_js_function_body(app_js, "computeAnalysisViaWorker")
    assert "const analysisSignature = analysisComputeCacheKey(snapshot);" in worker_body
    assert "signature: analysisSignature" in worker_body
    assert "analysisSignature: analysisSignature" in worker_body
    assert "analysisResponseEnvelopeMatchesCurrentState(" in worker_body
    assert 'const analysisPhase = options.quickMode ? "quick" : "full";' in worker_body
    assert "quickMode: Boolean(options.quickMode)" in worker_body

    schedule_body = _extract_js_function_body(app_js, "scheduleAnalysisCompute")
    invalidation_index = schedule_body.index("runtime.analysisPendingRequest = null;")
    debounce_index = schedule_body.index("window.setTimeout(function ()")
    assert invalidation_index < debounce_index

    for hook in (
        "getAnalysisRequestSignatureForTest:",
        "analysisResponseEnvelopeMatchesForTest:",
        "scheduleAnalysisComputeForTest:",
    ):
        assert hook in app_js


def test_trace_facility_proximity_filter_is_wired_into_trace_rendering():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    index_html = Path("webapp/static_public/index.html").read_text(encoding="utf-8")
    styles_css = Path("webapp/static_public/styles.css").read_text(encoding="utf-8")

    assert 'id="trace-facility-filter-enabled"' in index_html
    assert 'id="trace-facility-filter-enabled" type="checkbox"' in index_html
    assert 'id="trace-facility-filter-enabled" type="checkbox" checked' not in index_html
    assert 'id="trace-facility-linked-only" type="checkbox" checked disabled' in index_html
    assert "Only show facilities linked to visible traces" in index_html
    assert 'data-trace-facility-class="start"' in index_html
    assert 'data-trace-facility-class="passes"' in index_html
    assert 'data-trace-facility-radius-preset="1"' in index_html
    assert 'data-trace-facility-radius-preset="5"' in index_html
    assert 'data-trace-facility-radius-preset="250"' in index_html
    assert 'data-trace-facility-class-action="all"' in index_html
    assert 'data-trace-facility-class-action="only:passes"' not in index_html
    assert 'data-trace-facility-source-action="none"' in index_html
    assert 'data-trace-facility-source-action="only:military"' in index_html
    assert ".trace-facility-chip-passes" in styles_css
    assert ".trace-facility-linked-only" in styles_css
    assert ".trace-facility-linked-only:has(input:disabled)" in styles_css
    assert "--trace-facility-color: #f59e0b" in styles_css
    assert 'data-trace-facility-source="military"' in index_html
    assert "TRACE_FACILITY_FILTER_STORAGE_KEY" in app_js
    assert "TRACE_FACILITY_MAIN_TRACE_COLOR" in app_js
    assert "TRACE_FACILITY_ENDPOINT_ACCENT_RATIO" in app_js
    assert "function traceFacilityAccentPlacement(classKey)" in app_js
    assert "function applyTraceFacilityAccentStyle(segment, classKey, style, baseWeight, baseOpacity)" in app_js
    assert "function defaultTraceFacilityFilterState()" in app_js
    assert "function readTraceFacilityFilterState()" in app_js
    assert "function persistTraceFacilityFilterState()" in app_js
    assert "function traceFacilityFilterSignature()" in app_js
    assert "function traceFacilityFilterHasActiveSelection()" in app_js
    assert "function traceFacilityLinkedDisplayOnlyEnabled()" in app_js
    assert "TRACE_FACILITY_FILTER_SOURCE_LABELS" in app_js
    assert "function traceFacilityActiveSourceLabels()" in app_js
    assert "function traceFacilityPointSourceCounts(index)" in app_js
    assert "function traceFacilityPointSourceCountText(index)" in app_js
    assert '"; sources: " + sourceText' in app_js
    assert "facilitySourceCounts: traceFacilityPointSourceCounts(index)" in app_js
    assert "choose at least one trace class" in app_js
    assert "choose at least one facility source" in app_js
    assert "if (!traceFacilityFilterHasActiveSelection()) return false;" in app_js
    assert "function ensureTraceFacilitySourcesLoaded()" in app_js
    assert "function classifyTraceSegmentFacilityProximity(segment)" in app_js
    assert "function applyTraceFacilityFilterToSegment(segment)" in app_js
    assert "facilityAccentColor" in app_js
    assert "playbackTrailCanvasLayer" in app_js
    assert "facilityAccentPlacement: accentPlacement" in app_js
    assert "_strokeTraceSegmentLine" in app_js
    assert "function traceSegmentPassesNearFacility(segment, index, radiusMeters)" in app_js
    assert "function distanceMetersFromFacilityToTraceSegment(facility, segment)" in app_js
    assert "traceFacilityFilterSignature()" in app_js
    assert 'config.areaFilterActive ? "areaFilter=1" : "areaFilter=0",\n      traceFacilityFilterSignature(),' in app_js
    assert "facilityTraceClass: segment.facilityTraceClass || \"\"" in app_js
    assert "traceRenderCacheFacilityStats" in app_js
    assert 'stats.passesSegments ? "Connector intersections " + formatNumber(stats.passesSegments)' in app_js
    assert "passesSkippedSegments" in app_js
    assert "function recordTraceFacilityPassesScanSkipped()" in app_js
    assert "traceFacilityClassActionButtons" in app_js
    assert "traceFacilitySourceActionButtons" in app_js
    assert "action.slice(5)" in app_js
    assert "traceFacilityRadiusPresetButtons" in app_js
    assert "traceFacilityLinkedOnly" in app_js
    assert "onlyShowTraceLinkedFacilities" in app_js
    assert "facilityTraceClass" in app_js
    assert "traceFacilityFilterEnabled()" in app_js
    assert "passesSegments" in app_js
    assert 'runtime.map.getPane("tracePane").style.zIndex = "430"' in app_js
    assert 'runtime.map.getPane("claimedBaseTracePane").style.zIndex = "440"' in app_js
    assert "getTraceFacilityFilterMetrics" in app_js
    assert "state.traceFacilityFilter = readTraceFacilityFilterState()" in app_js
    assert "persistTraceFacilityFilterState()" in app_js
    assert "traceFacilityFilterEnabled() && !traceFacilitySourcesLoaded()" in app_js
    assert "function resetTraceFacilityFilterStats(scope)" in app_js
    assert "function recordTraceFacilityFilterEvaluation(classKey, visible, reason, evidenceClass)" in app_js
    assert 'showing " + formatNumber(stats.matchedSegments)' in app_js
    assert "facilityFilterStats" in app_js
    assert "static trace facility filter preserved existing visible layer while sources load" in app_js
    assert "traceModeIncludesStatic() && traceFacilityFilterEnabled() && traceFacilitySourcesLoaded()" in app_js
    assert "function scheduleTraceFacilitySourceReadyRender()" in app_js
    assert "runtime.traceFacilitySourceReadyRenderTimerId = window.setTimeout(tick, 250);" in app_js
    assert "function invalidateStaticTraceRenderCaches()" in app_js
    assert "function queueTraceFacilityStaticRenderRefresh()" in app_js
    assert "runtime.traceFacilityRenderRefreshTimerId" in app_js
    assert "getStaticTraceLayerSnapshot" in app_js


def test_trace_facility_location_evidence_policy_is_conservative_and_truthful():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    index_html = Path("webapp/static_public/index.html").read_text(encoding="utf-8")
    styles_css = Path("webapp/static_public/styles.css").read_text(encoding="utf-8")

    required_app_fragments = [
        "const TRACE_FACILITY_FILTER_STORAGE_VERSION = 4",
        'const TRACE_FACILITY_DEFAULT_EVIDENCE_MODE = "source_coordinates"',
        'claimedUfoBases: false',
        'exact_coords: "Source-provided coordinates"',
        '"state",\n    "province",\n    "state_province"',
        "function eventHasSourceCoordinateEvidence(event)",
        "function eventHasExactDateEvidence(event)",
        "function traceSegmentEndpointEvidence(segment)",
        "function traceFacilityIntervalActivityAtOrdinal(interval, ordinal)",
        "function traceFacilityActivityAtOrdinal(facility, ordinal)",
        "function traceFacilityIntervalActivityDuringInterval(facilityInterval, startOrdinal, endOrdinal)",
        "function traceFacilityActivityDuringInterval(facility, startOrdinal, endOrdinal)",
        'context.evidenceMode === "include_generalized"',
        'relevantSourceCoordinateEvidence = classKey === "between"',
        'relevantExactDateEvidence = classKey === "between"',
        'recordTraceFacilityFilterEvaluation(classKey, false, "location_evidence_excluded")',
        'recordTraceFacilityFilterEvaluation(classKey, false, "date_evidence_excluded")',
        'facilityTraceEvidenceClass: match.evidenceClass || "possible"',
        'facilityTraceEvidenceClass: match.evidenceClass',
        'TRACE_FACILITY_POSSIBLE_TRACE_DASH_ARRAY',
        'segment.facilityTraceEvidenceClass === "possible"',
        'evidenceMode: normalizeTraceFacilityEvidenceMode(filter.evidenceMode)',
        'exactDateEventIds: exactDateEventIdsForWorker()',
        "fromSortOrdinal: endpointEvidence.fromOrdinal",
        "toSortOrdinal: endpointEvidence.toOrdinal",
        "temporalKnown: Boolean(point.temporalKnown)",
        "temporalIntervals: Array.isArray(point.temporalIntervals)",
        "startBoundaryEndOrdinal: serializeFacilityTemporalOrdinal(point.startBoundaryEndOrdinal)",
        "endBoundaryStartOrdinal: serializeFacilityTemporalOrdinal(point.endBoundaryStartOrdinal)",
        "supportedSegments: 0",
        "possibleSegments: 0",
        "excludedEvidenceSegments: 0",
        "if (traceFacilityFilterEnabled()) return false;",
        "return configuredValue || APP_SHELL_RELEASE_TOKEN",
        'url.pathname.endsWith("/data/app_config.json")',
        'const url = new URL("./trace_facility_worker.js", document.baseURI)',
    ]
    for fragment in required_app_fragments:
        assert fragment in app_js

    configure_body = _extract_js_function_body(app_js, "ensureTraceFacilityWorkerIndexConfigured")
    direct_classify_body = _extract_js_function_body(app_js, "classifyTraceFacilitySegmentsViaWorker")
    packed_classify_body = _extract_js_function_body(app_js, "buildAndClassifyPackedTraceFacilitySegmentsViaWorker")
    assert "sourceCoordinateEventIds: sourceCoordinateEventIdsForWorker()" in configure_body
    assert "exactDateEventIds: exactDateEventIdsForWorker()" in configure_body
    assert "sourceCoordinateEventIds:" not in direct_classify_body
    assert "exactDateEventIds:" not in direct_classify_body
    assert "sourceCoordinateEventIds:" not in packed_classify_body
    assert "exactDateEventIds:" not in packed_classify_body

    static_version_body = _normalize_js_body(_extract_js_function_body(app_js, "staticAssetVersionToken"))
    resolve_asset_body = _normalize_js_body(_extract_js_function_body(app_js, "resolveAssetPath"))
    worker_url_body = _normalize_js_body(_extract_js_function_body(app_js, "traceFacilityWorkerUrl"))
    assert "returnconfiguredValue||APP_SHELL_RELEASE_TOKEN" in static_version_body
    assert 'url.pathname.endsWith("/data/app_config.json")' in resolve_asset_body
    assert 'url.pathname.indexOf("/data/analysis_v2/")!==-1' in resolve_asset_body
    assert "APP_SHELL_RELEASE_TOKEN||staticAssetVersionToken()" in resolve_asset_body
    assert 'newURL("./trace_facility_worker.js",document.baseURI)' in worker_url_body
    assert "APP_SHELL_RELEASE_TOKEN||staticAssetVersionToken()" in worker_url_body

    required_ui_fragments = [
        'id="trace-facility-evidence-mode" disabled aria-describedby="trace-facility-evidence-help"',
        '<option value="source_coordinates" selected>Strict mode</option>',
        '<option value="include_generalized">Exploratory mode</option>',
        "exact event dates",
        "recorded operating period",
        "Start endpoint near facility",
        "End endpoint near facility",
        "Both endpoints near facilities",
        "Connector intersects facility radius",
        "Chronology lines connect records in date order; they are not observed travel paths.",
        'data-trace-facility-source="claimedUfoBases" disabled',
    ]
    for fragment in required_ui_fragments:
        assert fragment in index_html

    assert 'data-trace-facility-class-action="only:passes"' not in index_html
    assert ".trace-facility-evidence-field select:focus-visible" in styles_css
    assert ".playback-trail-line-facility-possible" in styles_css
    assert ".map-legend-note" in styles_css


def test_mobile_map_overlays_and_focus_styles_remain_accessible():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    index_html = Path("webapp/static_public/index.html").read_text(encoding="utf-8")
    styles_css = Path("webapp/static_public/styles.css").read_text(encoding="utf-8")

    assert "function compactMapOverlaysWouldCollide()" in app_js
    assert "state.mapLegendCollapsed && compactMapOverlaysWouldCollide()" in app_js
    assert "state.mapControlClusterCollapsed && compactMapOverlaysWouldCollide()" in app_js
    assert ".map-control-cluster:not(.is-collapsed) ~ .map-legend:not(.is-collapsed)" in styles_css
    assert "max-height: 180px" in styles_css
    assert ".trace-facility-chip:focus-within" in styles_css
    assert "outline: 3px solid var(--focus-ring)" in styles_css
    assert "overscroll-behavior: contain" in styles_css
    assert 'rel="dns-prefetch" href="//a.basemaps.cartocdn.com"' in index_html
    assert 'rel="preconnect" href="https://a.basemaps.cartocdn.com"' in index_html


def test_mobile_basemap_uses_lighter_single_origin_tiles():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")

    assert "const preferStandardResolutionTiles = Boolean(" in app_js
    assert "window.innerWidth <= 768" in app_js
    assert 'String(provider.url).replace(/\\{r\\}/g, "")' in app_js
    assert 'tileOptions.subdomains = "a"' in app_js


def test_packed_startup_preview_becomes_interactive_before_catalog_hydration():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")

    assert "const packedPreviewDecision = measureStartupStepSync" in app_js
    assert "packedPreviewDecision && packedPreviewDecision.rendered" in app_js
    assert 'setStartupPreviewInteractive("Map preview prepared.' in app_js
    assert 'recordStartupMilestoneIfUnset("time to packed startup preview render")' in app_js


def test_static_bundle_trace_facility_filter_matches_source_wiring():
    source_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    bundle_js = Path("static_bundle/app.js").read_text(encoding="utf-8")

    required_fragments = [
        "TRACE_FACILITY_FILTER_STORAGE_KEY",
        "TRACE_FACILITY_MAIN_TRACE_COLOR",
        "TRACE_FACILITY_ENDPOINT_ACCENT_RATIO",
        "function traceFacilityAccentPlacement(classKey)",
        "function applyTraceFacilityAccentStyle(segment, classKey, style, baseWeight, baseOpacity)",
        "TRACE_FACILITY_FILTER_SOURCE_LABELS",
        "function traceFacilityPointSourceCounts(index)",
        "function traceFacilityPointSourceCountText(index)",
        "function traceSegmentPassesNearFacility(segment, index, radiusMeters)",
        "facilitySourceCounts: traceFacilityPointSourceCounts(index)",
        "facilityTraceClass: segment.facilityTraceClass || \"\"",
        "facilityAccentColor",
        "playbackTrailCanvasLayer",
        "facilityAccentPlacement: accentPlacement",
        "_strokeTraceSegmentLine",
        "traceFacilityFilterSignature()",
        "traceFacilityClassActionButtons",
        "traceFacilitySourceActionButtons",
        "traceFacilityRadiusPresetButtons",
        "traceFacilityLinkedOnly",
        "onlyShowTraceLinkedFacilities",
        "function traceFacilityLinkedDisplayOnlyEnabled()",
        "getStaticTraceLayerSnapshot",
        "static trace facility filter preserved existing visible layer while sources load",
        "traceModeIncludesStatic() && traceFacilityFilterEnabled() && traceFacilitySourcesLoaded()",
        "function scheduleTraceFacilitySourceReadyRender()",
        "traceFacilitySourceReadyRenderTimerId",
        "function invalidateStaticTraceRenderCaches()",
        "function queueTraceFacilityStaticRenderRefresh()",
        "traceFacilityRenderRefreshTimerId",
        "function traceFacilityDisplayFilteringActiveForSource(sourceKey)",
        "function overlayFeaturesForDisplay(overlayId, payload)",
        "function claimedUfoBaseSitesForDisplay()",
        "function currentTraceFacilityDisplayKeys()",
        "function syncTraceFacilityDisplayRestriction()",
        "runtime.traceFacilityDisplayKeys.has(key)",
    ]

    for fragment in required_fragments:
        assert fragment in source_js
        assert fragment in bundle_js


def test_static_trace_categories_filter_visible_events_and_results():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    bundle_js = Path("static_bundle/app.js").read_text(encoding="utf-8")

    required_fragments = [
        "traceLinkedVisibilityCacheKey",
        "function traceLinkedVisibilityAffectsRendering()",
        "function currentTraceLinkedVisibilityResult()",
        "function filterCatalogByTraceLinkedVisibility(catalog)",
        "function eventVisibleUnderActiveTraceAndRegionFilters(eventId)",
        "function traceVisibleUnderActiveTraceAndRegionFilters(traceId)",
        "return suppressVisibleDisplayDuplicates(filterCatalogByTraceLinkedVisibility(catalog));",
        "return currentVisibleDisplayCatalog(visibleCatalog);",
        "return currentVisibleDisplayCatalog(visibleMappedCatalog);",
        "traceLinkedVisibilityAffectsRendering() ? runtime.traceLinkedVisibilityCacheKey : \"\"",
        "const visibilityModeChanged = previousMode === \"static\" || nextMode === \"static\";",
        "if (traceLinkedOrRegionVisibilityAffectsRendering()) {",
        "renderTraceLinkedVisibilityUi({ preserveScroll: true });",
    ]

    for fragment in required_fragments:
        assert fragment in app_js
        assert fragment in bundle_js


def test_trace_facility_main_thread_and_worker_geometry_stay_in_sync():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    worker_js = Path("webapp/static_public/trace_facility_worker.js").read_text(encoding="utf-8")
    bundle_worker_js = Path("static_bundle/trace_facility_worker.js").read_text(encoding="utf-8")

    app_distance = _normalize_js_body(
        _extract_js_function_body(app_js, "distanceMetersFromFacilityToTraceSegment")
    )
    worker_distance = _normalize_js_body(
        _extract_js_function_body(worker_js, "distanceMetersFromFacilityToTraceSegment")
    )
    assert app_distance == worker_distance
    assert worker_distance == _normalize_js_body(
        _extract_js_function_body(bundle_worker_js, "distanceMetersFromFacilityToTraceSegment")
    )

    shared_fragments = [
        "const toLon = fromLon + normalizeLongitudeDelta(Number(segment.to && segment.to[1]) - fromLon);",
        "const facilityLon = unwrapLongitudeNear(Number(facility && facility.lon), fromLon);",
        "const estimatedCells = Math.max(0, maxLatCell - minLatCell + 1) * Math.max(0, maxLonCell - minLonCell + 1);",
        "if (estimatedCells > 5000) {",
        "const key = facility.source + \":\" + facility.id;",
        "distanceMetersFromFacilityToTraceSegment(facility, segment) <= radiusMeters",
    ]
    for fragment in shared_fragments:
        assert fragment in app_js
        assert fragment in worker_js
        assert fragment in bundle_worker_js


def test_trace_legend_uses_descriptor_rows():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    index_html = Path("webapp/static_public/index.html").read_text(encoding="utf-8")
    styles_css = Path("webapp/static_public/styles.css").read_text(encoding="utf-8")
    static_rows = _extract_js_function_body(app_js, "buildStaticTraceDescriptorLegendRows")
    trail_rows = _extract_js_function_body(app_js, "buildMapLegendTrailRows")
    trail_heading = _extract_js_function_body(app_js, "mapLegendTrailSectionTitle")
    render_map_legend = _extract_js_function_body(app_js, "renderMapLegend")

    assert "TRACE_LEGEND_DESCRIPTORS" in app_js
    assert "buildStaticTraceDescriptorLegendRows" in app_js
    assert "buildStaticTraceChronologyLegendRows" not in app_js
    assert "Older trace segments use cooler colors; newer segments warm up." in app_js
    assert "#2b6cb0" in app_js
    assert "#00a6d6" in app_js
    assert "#14b8a6" in app_js
    assert "#84cc16" in app_js
    assert "#f97316" in app_js
    assert "#e11d48" in app_js

    # Render-mode diagnostics belong in traceStatusText(), not in the visual
    # key. The legend shows only the styles that explain the active context.
    assert "TRACE_LEGEND_DESCRIPTORS.chronology" in static_rows
    assert "TRACE_LEGEND_DESCRIPTORS.aggregate" not in static_rows
    assert "TRACE_LEGEND_DESCRIPTORS.sampled" not in static_rows
    assert "runtime.staticTraceAggregationStatus" not in static_rows
    assert '"Aggregated "' not in static_rows
    assert '"Sampled "' not in static_rows
    assert '"Aggregated "' not in trail_rows
    assert '"Sampled "' not in trail_rows

    # Facility, static chronology, and playback modes are mutually exclusive
    # legend contexts with headings and rows that describe the active mode.
    facility_branch = trail_rows.index("if (traceFacilityFilterEnabled())")
    static_branch = trail_rows.index("if (traceModeIncludesStatic())", facility_branch)
    playback_branch = trail_rows.index("PLAYBACK_TRAIL_BUCKETS.map", static_branch)
    assert facility_branch < static_branch < playback_branch
    assert "traceFacilityActiveClasses().map" in trail_rows
    assert "traceFacilityLegendLineStyle(classKey, style)" in trail_rows
    assert "return buildStaticTraceDescriptorLegendRows();" in trail_rows
    assert 'return "Facility proximity evidence";' in trail_heading
    assert 'return "Trace chronology";' in trail_heading
    assert 'return "Sequence trail";' in trail_heading
    assert "buildMapLegendSection(mapLegendTrailSectionTitle(), trailRows)" in render_map_legend

    assert 'id="trace-status"' in index_html
    assert "function traceStatusText()" in app_js
    assert "generalized \" + formatNumber(renderedSegments) + \" cells" in app_js
    assert "sampled \" + formatNumber(renderedSegments) + \" of \" + formatNumber(sourceSegments)" in app_js
    assert ".trace-status" in styles_css


def test_map_legend_event_and_overlay_controls_are_accessible_and_stateful():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    index_html = Path("webapp/static_public/index.html").read_text(encoding="utf-8")
    styles_css = Path("webapp/static_public/styles.css").read_text(encoding="utf-8")
    helper_js = Path("webapp/static_public/legend_controls.js").read_text(encoding="utf-8")
    worker_js = Path("webapp/static_public/catalog_filter_worker.js").read_text(encoding="utf-8")

    title_position = index_html.index('<strong class="map-legend-title">Legend</strong>')
    reset_position = index_html.index('id="reset-map-legend"')
    minimize_position = index_html.index('id="toggle-map-legend"')
    assert title_position < reset_position < minimize_position
    assert 'id="map-legend-status"' in index_html
    assert 'role="status" aria-live="polite"' in index_html
    assert (
        "legend_controls.js?v=2026-08-09-control-panel-area-v1"
        in index_html
    )
    assert index_html.index("legend_controls.js") < index_html.index("app.js?v=")

    for fragment in (
        'class="map-legend-toggle-button"',
        'aria-pressed="',
        "data-map-legend-event-key",
        "data-map-legend-overlay",
        "data-map-legend-military-branch",
        "data-map-legend-research-category",
        "data-map-legend-claimed-control",
        "function resetMapLegendControls()",
        "getMapLegendSnapshotForTest: function ()",
        "scheduleRefresh({ immediate: true });",
        "defaultResearchCategoryVisibilityState(categories)",
        "state.researchCategoryVisibility[category] = true;",
    ):
        assert fragment in app_js

    assert "function toggleEventKey" in helper_js
    assert "function toggleGroupedOverlay" in helper_js
    assert 'mode: "none"' in helper_js
    assert 'mode: "subset"' in helper_js
    assert "legendEventCounts" in worker_js
    assert "legendEventMode" in worker_js
    assert "selectedLegendEventKeys" in worker_js

    craft_row = _extract_js_function_body(app_js, "buildCraftLegendRow")
    for fragment in (
        'class="craft-legend-swatch-button"',
        'data-map-legend-event-key=',
        'data-craft-legend-toggle-key=',
        'class="craft-legend-label-button"',
        'data-craft-legend-solo-key=',
        'aria-pressed="',
        'aria-hidden="true"',
    ):
        assert fragment in craft_row
    assert "function toggleCraftLegendSoloKey(key)" in app_js
    assert "function applyCraftLegendBulkAction(action)" in app_js
    assert "LEGEND_CONTROLS.toggleCraftKey(" in app_js
    assert "LEGEND_CONTROLS.toggleCraftSolo(" in app_js
    assert "LEGEND_CONTROLS.applyCraftBulkSelection(" in app_js
    assert app_js.count("buildCraftLegendBulkControls()") >= 3
    assert app_js.count("clearCraftLegendSoloState();") >= 5

    for selector in (
        ".map-legend-reset-button",
        ".map-legend-toggle-button",
        '.map-legend-toggle-button[aria-pressed="false"]::after',
        ".map-legend-reset-button:focus-visible",
    ):
        assert selector in styles_css
    assert "grid-template-columns: minmax(0, 1fr) 44px 44px;" in styles_css
    assert "min-width: 44px;" in styles_css
    assert "touch-action: manipulation;" in styles_css
    assert "@media (pointer: coarse), (max-width: 768px)" in styles_css
    assert ".map-legend .compact-toggle-button" in styles_css
    assert "min-width: 204px;" in styles_css
    assert "max-width: min(220px, calc(100% - 20px));" in styles_css


def test_map_legend_counts_and_desktop_map_height_resizer_are_wired_and_accessible():
    for root in (Path("webapp/static_public"), Path("static_bundle")):
        app_js = (root / "app.js").read_text(encoding="utf-8")
        index_html = (root / "index.html").read_text(encoding="utf-8")
        styles_css = (root / "styles.css").read_text(encoding="utf-8")

        marker_row = _extract_js_function_body(app_js, "buildMapLegendMarkerRow")
        event_rows = _extract_js_function_body(app_js, "buildMapLegendEventRows")
        apply_height = _normalize_js_body(
            _extract_js_function_body(app_js, "applyMapSurfaceHeight")
        )
        resize_keydown = _extract_js_function_body(
            app_js, "handleMapSurfaceResizeKeydown"
        )

        assert 'class="map-legend-item-count"' in marker_row
        assert 'const singularNoun = String(config.countNounSingular || "event");' in marker_row
        assert 'const pluralNoun = String(config.countNounPlural || singularNoun + "s");' in marker_row
        assert 'const countNoun = count === 1 ? singularNoun : pluralNoun;' in marker_row
        assert 'formatNumber(count) + " " + countNoun + " under the current filters"' in marker_row
        assert "escapeHtml(formatNumber(count))" in marker_row
        assert "count: entry.count" in event_rows
        assert 'countNounSingular: "crop record"' in app_js
        assert 'countNounPlural: "crop records"' in app_js

        assert 'id="map-height-resize-rail"' in index_html
        assert 'role="separator"' in index_html
        assert 'tabindex="0"' in index_html
        assert 'aria-orientation="horizontal"' in index_html
        assert 'aria-controls="map map-control-cluster map-legend-panel"' in index_html
        assert "The default map height is the minimum." in index_html

        assert "function mapSurfaceHeightBounds()" in app_js
        assert "function startMapSurfaceResize(event)" in app_js
        assert "function finishMapSurfaceResize(event)" in app_js
        assert "function resetMapSurfaceHeight()" in app_js
        assert "initializeMapSurfaceHeightResize();" in app_js
        assert "mapSurfaceResize: {" in app_js
        assert "clamp(Math.round(Number(height)||bounds.minHeight),bounds.minHeight,bounds.maxHeight)" in apply_height
        assert 'event.key === "ArrowDown"' in resize_keydown
        assert 'event.key === "ArrowUp"' in resize_keydown
        assert 'event.key === "Home"' in resize_keydown
        assert 'event.key === "End"' in resize_keydown

        assert ".map-legend-item-count" in styles_css
        assert "font-variant-numeric: tabular-nums;" in styles_css
        assert "grid-template-columns: auto minmax(0, 1fr) max-content;" in styles_css
        assert ".map-height-resize-rail" in styles_css
        assert "cursor: ns-resize;" in styles_css
        assert ".map-height-resize-rail[hidden]" in styles_css
        assert ":root.mobile-landscape-ui .map-height-resize-rail" in styles_css
        assert "@media (max-width: 1080px)" in styles_css


def test_trace_facility_display_filter_uses_matched_facility_keys():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    active_for_source = _extract_js_function_body(
        app_js, "traceFacilityDisplayFilteringActiveForSource"
    )
    overlay_features = _extract_js_function_body(app_js, "overlayFeaturesForDisplay")
    claimed_sites = _extract_js_function_body(app_js, "claimedUfoBaseSitesForDisplay")
    display_keys = _extract_js_function_body(app_js, "currentTraceFacilityDisplayKeys")
    sync_restriction = _extract_js_function_body(
        app_js, "syncTraceFacilityDisplayRestriction"
    )
    refresh_layers = _extract_js_function_body(
        app_js, "refreshTraceFacilityDisplayLayers"
    )
    claimed_trace_layer = _extract_js_function_body(
        app_js, "syncClaimedUfoBaseTraceLayerFromCache"
    )
    filter_signature = _extract_js_function_body(app_js, "traceFacilityFilterSignature")

    # Once proximity is active, every facility overlay is restricted to the
    # exact connected-key set. Inactive sources therefore show no unrelated
    # facilities instead of escaping back to their full marker layer.
    assert "runtime.traceFacilityDisplayKeys instanceof Set" in active_for_source
    assert "traceFacilityLinkedDisplayOnlyEnabled()" in active_for_source
    assert "Object.prototype.hasOwnProperty.call(traceFacilityFilterState().sources, sourceKey)" in active_for_source
    assert "traceFacilityFilterState().sources[sourceKey]" not in active_for_source
    assert "!traceFacilityLinkedDisplayOnlyEnabled()" in display_keys
    assert "if (!traceFacilityFilterHasActiveSelection())" in display_keys
    assert "return new Set();" in display_keys

    # Static and playback traces contribute the exact matched facility keys;
    # unrelated facilities are then excluded from every source layer.
    assert "runtime.staticTraceLayer._segments" in display_keys
    assert "playbackTrailEntryVisibleUnderFacilityFilter(entry)" in display_keys
    assert "traceVisibleUnderActiveTraceAndRegionFilters(entry.traceId)" in display_keys
    assert "addTraceFacilityDisplayKeys(keys" in display_keys
    for body in (overlay_features, claimed_sites):
        assert "traceFacilityDisplayFilteringActiveForSource" in body
        assert "__traceFacilityKey" in body
        assert "runtime.traceFacilityDisplayKeys.has(key)" in body

    # A changed restriction rebuilds the cached facility layers so the visual
    # display, not only the trace classification, reflects it.
    assert "runtime.traceFacilityDisplayKeys = nextKeys;" in sync_restriction
    assert "refreshTraceFacilityDisplayLayers();" in sync_restriction
    assert "runtime.traceFacilityDisplayRefreshTimerId" in refresh_layers
    assert "window.setTimeout(function ()" in refresh_layers
    assert "state.overlayVisibility[overlayId]" in refresh_layers
    assert 'rebuildOverlayLayerFromCache(overlayId);' in refresh_layers
    assert "rebuildClaimedUfoBaseSitesLayerFromCache();" in refresh_layers

    # The preference controls marker pruning only. It must never reclassify
    # traces or trim the separate claimed-site trace overlay.
    assert "data.traceSegments" in claimed_trace_layer
    assert "claimedUfoBaseSitesForDisplay()" not in claimed_trace_layer
    assert "onlyShowTraceLinkedFacilities" not in filter_signature


def test_facility_proximity_never_filters_sighting_hotspots_or_results():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    bundle_js = Path("static_bundle/app.js").read_text(encoding="utf-8")

    for candidate in (app_js, bundle_js):
        visibility_gate = _extract_js_function_body(
            candidate, "traceLinkedVisibilityAffectsRendering"
        )
        facility_guard = visibility_gate.index("if (traceFacilityFilterEnabled()) return false;")
        startup_guard = visibility_gate.index(
            'if (startup.previewInteractive && startup.phase !== "Ready") return false;'
        )
        assert facility_guard < startup_guard
        assert "return suppressVisibleDisplayDuplicates(filterCatalogByTraceLinkedVisibility(catalog));" in candidate


def test_trace_width_slider_can_only_thin_existing_trace_weights():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    index_html = Path("webapp/static_public/index.html").read_text(encoding="utf-8")
    styles_css = Path("webapp/static_public/styles.css").read_text(encoding="utf-8")
    bundle_js = Path("static_bundle/app.js").read_text(encoding="utf-8")
    bundle_index_html = Path("static_bundle/index.html").read_text(encoding="utf-8")
    bundle_styles_css = Path("static_bundle/styles.css").read_text(encoding="utf-8")

    required_js_fragments = [
        'const TRACE_WIDTH_SCALE_STORAGE_KEY = "ufoTimeline.traceWidthScale"',
        'const TRACE_WIDTH_MODE_STORAGE_KEY = "ufoTimeline.traceWidthMode"',
        'const TRACE_BOLDNESS_SCALE_STORAGE_KEY = "ufoTimeline.traceBoldnessScale"',
        "const TRACE_WIDTH_SCALE_MIN = 0.05",
        "const TRACE_WIDTH_SCALE_MAX = 1",
        "const TRACE_BOLDNESS_SCALE_MAX = 1.8",
        'const TRACE_WIDTH_MODE_DEFAULT = "auto"',
        "const TRACE_WIDTH_PRESETS = Object.freeze",
        "function traceAutoWidthScale()",
        "function effectiveTraceWidthScale()",
        "function scaledTraceOpacity(opacity)",
        "function scaledTraceStrokeWeight(weight)",
        "function applyTraceWidthScale(value, options)",
        "function applyTraceWidthPreset(key, options)",
        "function applyTraceBoldnessScale(value, options)",
        "ctx.strokeStyle = hexToRgba(color || segment.bucket.color, scaledTraceOpacity(opacity))",
        "weight: scaledWeight",
        "rawWeight: rawWeight",
        "rawOpacity: rawOpacity",
        "state.traceWidthScale = normalizeTraceWidthScale(storedTraceWidthScale)",
        "state.traceBoldnessScale = normalizeTraceBoldnessScale(storedTraceBoldnessScale)",
        "state.traceWidthMode = storedTraceWidthMode == null && storedTraceWidthScale != null",
        "safeStorageSet(TRACE_WIDTH_MODE_STORAGE_KEY, traceWidthMode())",
        "getTraceWidthScale: function ()",
        "getTraceWidthMode: function ()",
        "getEffectiveTraceWidthScale: function ()",
        "getTraceBoldnessScale: function ()",
        "setTraceWidthScale: function (value)",
        "setTraceWidthPreset: function (key)",
        "setTraceBoldnessScale: function (value)",
    ]
    for fragment in required_js_fragments:
        assert fragment in app_js
        assert fragment in bundle_js

    required_index_fragments = [
        'id="trace-width-scale" type="range" min="5" max="100" step="5" value="100"',
        'id="trace-width-value" for="trace-width-scale">Auto 100%</output>',
        'id="trace-boldness-scale" type="range" min="50" max="180" step="5" value="100"',
        'id="trace-boldness-value" for="trace-boldness-scale">100%</output>',
        'data-trace-width-preset="auto"',
        'data-trace-width-preset="thin"',
        'data-trace-width-preset="hairline"',
        'data-trace-width-preset="default"',
        'id="trace-width-preview-line"',
    ]
    for fragment in required_index_fragments:
        assert fragment in index_html
        assert fragment in bundle_index_html

    required_css_fragments = [
        ".trace-width-control",
        ".trace-width-field",
        ".trace-boldness-field",
        ".trace-width-preview",
        ".trace-width-presets",
        ".trace-width-preset-button",
        "--trace-range-fill",
        "accent-color: var(--accent)",
    ]
    for fragment in required_css_fragments:
        assert fragment in styles_css
        assert fragment in bundle_styles_css


def test_responsive_startup_and_date_interaction_performance_guards_are_wired():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    index_html = Path("webapp/static_public/index.html").read_text(encoding="utf-8")
    styles_css = Path("webapp/static_public/styles.css").read_text(encoding="utf-8")
    bundle_js = Path("static_bundle/app.js").read_text(encoding="utf-8")
    bundle_index_html = Path("static_bundle/index.html").read_text(encoding="utf-8")
    bundle_styles_css = Path("static_bundle/styles.css").read_text(encoding="utf-8")

    for candidate in (index_html, bundle_index_html):
        assert '<html lang="en" class="app-initializing">' in candidate
        assert 'classList.remove("app-initializing")' in candidate
        assert 'id="follow-playback-results" type="checkbox" checked' in candidate
        assert "playback_performance.js?v=2026-07-31-area-lifecycle-v154" in candidate

    for candidate in (styles_css, bundle_styles_css):
        assert "html.app-initializing .page-shell" in candidate
        assert "visibility: hidden" in candidate
        assert ".map-startup-card" in candidate
        assert "min-height: 276px" in candidate
        assert "min-height: 5.8em" in candidate
        assert "grid-template-columns: minmax(0, 1fr);" in candidate
        assert "overflow-x: clip;" in candidate
        assert "text-overflow: ellipsis;" in candidate
        assert ".results-window-navigation" in candidate
        assert ".result-list.is-live-timeline-preview::before" in candidate
        assert ".playback-follow-toggle" in candidate

    required_app_fragments = [
        "function scheduleCurrentTimeRangeState()",
        "function scheduleTimelineHeavySync(delayOverride)",
        "function buildInteractiveTimelineDensityPreview()",
        "PLAYBACK_PERFORMANCE.weightedSamplePartitions",
        "approximateTraceLinked",
        "Release the timeline for exact results and trace-linked visibility",
        "function scheduleNextPlaybackStep()",
        "runtime.playbackAnimationFrameId = window.requestAnimationFrame(playbackFrame)",
        "function syncPlaybackTrailCanvas()",
        "MAP_HEAT_AGGREGATE_THRESHOLD",
        "progressive_exact_refinement",
        "function lowerBoundTimelineEventIndex(events, ordinal)",
        "function upperBoundTimelineEventIndex(events, ordinal)",
        "pendingTimeRangeApplyToken",
        "function visibleDisplayDuplicateFingerprint(event)",
        "function scheduleProgressiveVisibleDisplayDedupe(catalog)",
        "VISIBLE_DISPLAY_DEDUPE_FRAME_BUDGET_MS",
        "function scheduleProgressiveTraceLinkedVisibilityResult(cacheKey)",
        "progressive_exact_trace_linked_visibility",
        "Refining exact trace-linked sightings",
        "traceLinkedCatalogCache: new WeakMap()",
        "const cached = runtime.traceLinkedCatalogCache.get(catalog);",
        "function resultsRenderContextKey(visibleCatalog)",
        "function scheduleLargeWindowTraceRefinement(rangeGeneration)",
        "function scheduleProgressiveLargeWindowStaticTraceRender(rangeGeneration, options)",
        "TRACE_LARGE_WINDOW_BUILD_FRAME_BUDGET_MS",
        "TRACE_LARGE_WINDOW_REFINEMENT_DELAY_MS",
        "progressive large-window packed trace refinement in progress",
        "stale progressive trace result discarded",
        "deferLargeWindowDecorations",
        "function createTraceFacilityClassificationContext()",
        "applyTraceFacilityFilterToSegmentWithContext",
        "Math.max(MAP_DEFAULT_MIN_ZOOM, configuredZoom - 2)",
        'classList.remove("app-initializing")',
        "const canDismiss = ready;",
        "interactive startup profile already owns the provisional map",
    ]
    for fragment in required_app_fragments:
        assert fragment in app_js
        assert fragment in bundle_js

    playback_step = _extract_js_function_body(app_js, "stepPlaybackToIndex")
    assert "renderResults(" not in playback_step
    assert "updateRenderedResultCardStates(" in playback_step
    playback_status = _extract_js_function_body(app_js, "renderPlaybackStatus")
    assert "const lightweight = Boolean(options && options.playbackStep)" in playback_status
    assert 'if (!lightweight) {' in playback_status
    render_results = _extract_js_function_body(app_js, "renderResults")
    assert "runtime.resultsRenderContextKey !== catalogContextKey" in render_results
    assert "runtime.resultsRenderCatalogRef !== visibleCatalog" not in render_results
    progressive_trace = _extract_js_function_body(
        app_js,
        "scheduleProgressiveLargeWindowStaticTraceRender",
    )
    assert "window.requestAnimationFrame" in progressive_trace
    assert "performance.now() - batchStartedAt" in progressive_trace
    assert "TRACE_LARGE_WINDOW_BUILD_BATCH_ROW_LIMIT" in progressive_trace
    assert "renderStaticTraceLayer(" not in progressive_trace
    density_preview = _extract_js_function_body(
        app_js,
        "buildInteractiveTimelineDensityPreview",
    )
    assert "regionSelectionAffectsRendering()" in density_preview
    assert "approximateTraceLinked" in density_preview
    assert "traceLinkedVisibilityAffectsRendering()" not in density_preview.split(
        "const approximateTraceLinked",
        1,
    )[0]
    progressive_visibility = _extract_js_function_body(
        app_js,
        "scheduleProgressiveTraceLinkedVisibilityResult",
    )
    assert "window.requestAnimationFrame" in progressive_visibility
    assert "performance.now() - batchStartedAt" in progressive_visibility
    assert "buildLargeTraceLinkedVisibilityExclusionIndex(" not in progressive_visibility


def test_startup_cover_waits_for_complete_initial_visual_state():
    source_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    bundle_js = Path("static_bundle/app.js").read_text(encoding="utf-8")

    for candidate in (source_js, bundle_js):
        overlay = _extract_js_function_body(candidate, "renderMapStartupOverlay")
        coordinator = _extract_js_function_body(candidate, "finalizeInitialStartupVisuals")
        initialize = _extract_js_function_body(candidate, "initialize")

        assert 'startup.phase === "Ready" && startup.initialViewReady' in overlay
        assert "const canDismiss = ready;" in overlay
        assert "ready || previewInteractive" not in overlay
        assert 'data-startup-initial-view-ready' in candidate

        required_coordinator_tokens = [
            "applyStartupFitBeforeReady()",
            "requestCanonicalTraceRuntimePreload()",
            "ensureTraceFacilitySourcesLoaded()",
            "waitForInitialTraceWorkerToSettle()",
            "waitForTraceFacilityDisplayRefresh()",
            "waitForInitialTraceCanvasToSettle()",
            "waitForInitialMapTilesToSettle(4000)",
            'setBasemap("none")',
            'recordStartupDecision("initialVisualGate"',
        ]
        for token in required_coordinator_tokens:
            assert token in coordinator

        assert "if (!facilitySourcesReady)" in coordinator
        assert "if (!traceWorkerSettled || runtime.traceFacilityWorkerLastError)" in coordinator
        assert "if (!facilityDisplaySettled)" in coordinator
        assert "if (!traceCanvasSettled)" in coordinator
        automation_index = initialize.index("await runAutomationFromQuery();")
        final_visual_index = initialize.index("await finalizeInitialStartupVisuals();")
        ready_flag_index = initialize.index("startup.initialViewReady = true;")
        ready_phase_index = initialize.index('setStartupPhase("Ready"')
        assert automation_index < final_visual_index < ready_flag_index < ready_phase_index

        assert "Default flap preview is interactive." not in candidate
        assert "Map preview is interactive." not in candidate


def test_startup_failure_is_terminal_until_a_clean_reload():
    for app_path in (Path("webapp/static_public/app.js"), Path("static_bundle/app.js")):
        app_js = app_path.read_text(encoding="utf-8")
        set_phase = _normalize_js_body(_extract_js_function_body(app_js, "setStartupPhase"))
        initialize = _normalize_js_body(_extract_js_function_body(app_js, "initialize"))

        failure_guard = 'if(startup.phase==="Failed"&&phase!=="Failed"){return;}'
        ready_guard = 'if(startup.phase==="Failed"||startup.errorText){return;}'
        assert failure_guard in set_phase
        assert ready_guard in initialize
        assert initialize.index(ready_guard) < initialize.index("startup.initialViewReady=true;")
        assert "getMapViewSnapshot" in app_js
        assert "setMapViewForTest" in app_js


def test_chronological_neighborhood_release_contract_is_synchronized():
    source_root = Path("webapp/static_public")
    bundle_root = Path("static_bundle")
    for filename in (
        "index.html",
        "styles.css",
        "app.js",
        "catalog_filter_worker.js",
        "trace_facility_worker.js",
        "trace_neighborhood.js",
        "legend_controls.js",
        "flap_preset_labels.js",
        "playback_performance.js",
        "verify_timeline_features.html",
    ):
        assert (source_root / filename).read_bytes() == (bundle_root / filename).read_bytes()

    app_js = (source_root / "app.js").read_text(encoding="utf-8")
    index_html = (source_root / "index.html").read_text(encoding="utf-8")
    helper_js = (source_root / "trace_neighborhood.js").read_text(encoding="utf-8")

    assert 'id="area-selection-depth"' in index_html
    assert 'id="area-selection-direction"' in index_html
    assert "Chronological Neighborhood" in index_html
    assert "not evidence of travel" in index_html
    assert (
        "trace_neighborhood.js?v=2026-08-09-control-panel-area-v1"
        in index_html
    )
    assert "function currentChronologicalNeighborhoodIndex()" in app_js
    assert "TRACE_NEIGHBORHOOD.querySpatialIndex(index.spatial, [bounds])" in app_js
    assert "TRACE_NEIGHBORHOOD.traverseNeighborhood({" in app_js
    assert "renderChronologicalNeighborhoodOverlay();" in app_js
    assert "Derived implied speed" in app_js
    assert "function buildAdjacencyIndex(segments, generation)" in helper_js
    assert "function traverseNeighborhood(options)" in helper_js
    assert 'light: "#b517ff"' in helper_js


def test_craft_trace_filter_generation_and_hybrid_date_contracts():
    app_js = Path("webapp/static_public/app.js").read_text(encoding="utf-8")
    index_html = Path("webapp/static_public/index.html").read_text(encoding="utf-8")
    styles_css = Path("webapp/static_public/styles.css").read_text(encoding="utf-8")
    catalog_worker = Path("webapp/static_public/catalog_filter_worker.js").read_text(encoding="utf-8")
    trace_worker = Path("webapp/static_public/trace_facility_worker.js").read_text(encoding="utf-8")

    assert "function resolveTraceEndpointCraftStyle(segment)" in app_js
    assert "function clearCraftTraceDecoration(segment)" in app_js
    assert 'const DEFAULT_COLOR_MODE = "craft_type";' in app_js
    assert app_js.count("colorMode: DEFAULT_COLOR_MODE") == 2
    assert '<option value="craft_type" selected>Craft Type</option>' in index_html
    assert '<option value="single" selected>Single Color</option>' not in index_html
    assert "fromCraftColor" in app_js and "toCraftColor" in app_js
    assert 'return "Craft-type traces";' in app_js
    assert "Facility evidence uses outlines and dashes; craft hue takes precedence." in app_js
    assert "restylePlaybackTrailEntriesForColorMode();" in app_js
    assert "craftTraceColoringActive() && segment.fromCraftColor && segment.toCraftColor" in app_js
    aggregate_body = _extract_js_function_body(app_js, "addTraceSegmentToAggregateMap")
    assert "const craftStyle = craftTraceColoringActive()" in aggregate_body
    assert "segment.fromCraftKey =" not in aggregate_body
    assert "segment.fromCraftColor =" not in aggregate_body
    density_body = _extract_js_function_body(app_js, "styleTraceSegmentForDensity")
    assert "const nonCraftSegment = clearCraftTraceDecoration(segment);" in density_body
    assert "applyTraceFacilityAccentStyle(\n        nonCraftSegment," in density_body
    assert "state.filterGeneration" in app_js
    assert "runtime.discardedWorkerResults += 1" in app_js
    assert "scheduleRefresh({ immediate: true })" in app_js
    assert 'els.keywordInput.addEventListener("input"' in app_js
    assert "generation: Number(message.generation) || 0" in catalog_worker
    assert "generation: Number(message.generation) || 0" in trace_worker

    for element_id in (
        "start-date-picker",
        "end-date-picker",
        "timeline-start-date-picker",
        "timeline-end-date-picker",
    ):
        assert f'id="{element_id}"' in index_html
    assert 'class="two-column filter-date-grid"' in index_html
    assert "repeat(auto-fit, minmax(min(100%, 210px), 1fr))" in styles_css
    assert "font-variant-numeric: tabular-nums" in styles_css
    assert ".filter-date-quick-select {\n  flex: 1 1 220px;" in styles_css
    assert "function setDateRangeFeedback(message)" in app_js
    assert "FLAP_PRESET_LABELS.formatPresetLabel(preset)" in app_js
    assert "FLAP_PRESET_LABELS.formatPresetTitle(preset)" in app_js
    assert "escapeHtml(visibleLabel)" in app_js
    assert "parts[2] > daysInMonth(parts[0], parts[1])" in app_js
    assert "const era = Math.floor(shifted / 146097);" in app_js
    assert "Start date must be on or before End date. The last valid range is still active." in app_js
    assert "typeof picker.showPicker === \"function\"" in app_js
    assert "getNeighborhoodSnapshotForTest: function ()" in app_js
    assert "openNeighborhoodInspectorForTest: function (traceId)" in app_js


def test_hosted_feature_verifier_tracks_current_progressive_results_and_legends():
    verifier = Path("webapp/static_public/verify_timeline_features.html").read_text(encoding="utf-8")
    index_html = Path("webapp/static_public/index.html").read_text(encoding="utf-8")

    referenced_ids = set(
        re.findall(r'doc\.querySelector(?:All)?\("#([A-Za-z0-9_-]+)', verifier)
    )
    current_ids = set(re.findall(r'id="([A-Za-z0-9_-]+)"', index_html))

    assert referenced_ids <= current_ids
    assert "#results-limit" not in verifier
    assert "#trail-legend" not in verifier
    assert "#timeline-status" not in verifier
    assert "Progressive results window" in verifier
    assert "Results progressive rendering" in verifier
    assert 'doc.querySelector("#map-legend-body")' in verifier
    assert 'selectedMapMode === "heatmap"' in verifier
