from pathlib import Path


APP_JS = Path("webapp/static_public/app.js")
BUNDLE_JS = Path("static_bundle/app.js")


def _packed_trace_render_cache_key_body(source: str) -> str:
    marker = 'function buildCanonicalPackedTraceRenderSegments'
    start = source.index(marker)
    cache_start = source.index('const cacheKey = [', start)
    cache_end = source.index('].join("|");', cache_start)
    return source[cache_start:cache_end]


def test_packed_static_trace_render_cache_key_depends_on_filtered_window_and_catalog():
    for path in (APP_JS, BUNDLE_JS):
        body = _packed_trace_render_cache_key_body(path.read_text(encoding="utf-8"))
        assert "state.timelineDataVersion" in body
        assert "state.timeRangeStartOrdinal" in body
        assert "state.timeRangeEndOrdinal" in body
        assert "catalogEventIdIdentityKey(state.filteredMappedCatalog)" in body
        assert "canonicalFilteredTraceAggregationRequested()" in body
        assert "config.areaFilterActive" in body


def test_static_trace_render_falls_back_when_packed_index_returns_empty_for_nonempty_window():
    for path in (APP_JS, BUNDLE_JS):
        source = path.read_text(encoding="utf-8")
        assert "function buildLegacyCanonicalTraceSegments()" in source
        assert "function packedTraceResultShouldFallbackToLegacy(result)" in source
        assert "function packedTraceRenderResultIsUsable(result)" in source
        assert "const scannedRows = result.aggregationStatus" in source
        assert "const facilityCandidateSegments = Math.max(0, Number(facilityStats.candidateSegments) || 0);" in source
        assert "return scannedRows === 0 || facilityCandidateSegments === 0;" in source
        assert "state.filteredMappedPlaybackEvents.length > 1" in source
        assert "const viewportSourceSegments = Math.max(0, Number(result.viewportSourceSegments) || 0);" in source
        assert "if (totalSegments > 0 || viewportSourceSegments > 0)" in source
        assert "if (packedTraceRenderResultIsUsable(runtime.packedTraceRenderCacheValue))" in source
        assert "runtime.packedTraceRenderCacheValue = null;" in source
        assert "if (!config.areaFilterActive && packedTraceRenderResultIsUsable(result))" in source
        assert "if (packedTraceRenderResultIsUsable(cachedPackedRender))" in source
        assert "if (!packedTraceRenderResultIsUsable(packedRender))" in source
        assert "runtime.packedStaticTraceRenderCache.delete(packedRenderCacheKey)" in source
        assert "runtime.traceRenderCacheKey = \"\";" in source
        assert "runtime.traceRenderCacheValue = null;" in source
