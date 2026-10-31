import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";

const require = createRequire(import.meta.url);
const playbackPerformance = require("../playback_performance.js");
const directions = require("../trace_direction_summary.js");
const source = readFileSync(new URL("../app.js", import.meta.url), "utf8");

function extractFunction(name) {
  const start = source.indexOf(`function ${name}(`);
  const end = source.indexOf("\n  function ", start + 1);
  assert.ok(start >= 0 && end > start, `Actual app controller function ${name} exists`);
  return source.slice(start, end);
}

const controllerNames = [
  "catalogEventIdIdentityKey", "currentPlaybackEvent", "playbackIntervalMs",
  "cancelPlaybackLoop", "syncPlaybackOverlayToCurrentEvent", "resetPlayback",
  "pausePlayback", "finishPlayback", "currentPlaybackContextKey", "buildPlaybackSequence",
  "findNearestMappedEvent", "stepPlaybackToIndex", "playbackStep", "scheduleNextPlaybackStep",
  "ensurePlaybackSequenceForCurrentContext", "startPlayback", "togglePlayback", "applyPlaybackSpeed",
];

function createController({ unmappedAt = -1 } = {}) {
  let now = 0;
  let nextFrameId = 0;
  const frames = new Map();
  const cancelledFrames = [];
  const statuses = [];
  const cursorMoves = [];
  const catalog = Array.from({ length: 8 }, (_, index) => ({
    event_id: index + 1, sort_ordinal: index + 100,
    has_coordinates: index !== unmappedAt, lat: index, lon: index + 10,
  }));
  const state = {
    playbackState: "stopped", playbackCursorIndex: -1, playbackSequence: [],
    playbackSequenceEventIdIndex: new Map(), playbackSequenceContextKey: "",
    playbackSessionId: 0, playbackSpeed: 4, playbackEffectiveSpeed: 4,
    playbackPerformanceLimited: false, resultsFollowPlayback: false,
    selectedEventId: null, highlightedMapEventId: null,
    filteredPlaybackEvents: catalog, filteredPlaybackEventCount: catalog.length,
    timelineDataVersion: 1, filterGeneration: 1, timeRangeStartOrdinal: 100, timeRangeEndOrdinal: 107,
  };
  const runtime = {
    playbackTimerId: null, playbackAnimationFrameId: null, playbackNextDueAt: 0,
    playbackStepCostEwmaMs: 0, filteredCatalogDateAsc: true,
  };
  let clearedHistory = 0;
  const context = vm.createContext({
    state, runtime, PLAYBACK_PERFORMANCE: playbackPerformance,
    PLAYBACK_BASE_INTERVAL_MS: 1200, PLAYBACK_MIN_INTERVAL_MS: 20,
    performance: { now: () => now },
    window: {
      requestAnimationFrame(callback) { const id = ++nextFrameId; frames.set(id, callback); return id; },
      cancelAnimationFrame(id) { cancelledFrames.push(id); frames.delete(id); },
      clearTimeout() {},
    },
    currentVisibleResultsCatalog: () => catalog,
    visibleResultsEventIdSet: () => new Set(catalog.map(event => event.event_id)),
    setBusyState() {}, clearBusyState() {}, clearPlaybackAnimationFrames() {},
    clearPlaybackTrailHistory: () => { clearedHistory++; },
    traceFacilityFilterEnabled: () => false,
    clearPlaybackOverlay() {},
    setPlaybackActiveMarker() {},
    setPlaybackCursorPosition: (lat, lon) => cursorMoves.push([lat, lon]),
    animateChronologicalCursor() {}, renderMapSelectionOverlay() {},
    updateRenderedResultCardStates() {}, scheduleResultsPaneSync() {},
    syncPlaybackSpeedControls() {},
    renderPlaybackStatus: () => statuses.push({ state: state.playbackState, index: state.playbackCursorIndex }),
  });
  vm.runInContext(controllerNames.map(extractFunction).join("\n"), context);

  return {
    context, state, runtime, catalog, frames, cancelledFrames, statuses, cursorMoves,
    clearedHistory: () => clearedHistory,
    now: () => now,
    frameAfter(milliseconds) {
      now += milliseconds;
      const pending = [...frames.values()];
      frames.clear();
      for (const callback of pending) callback(now);
    },
  };
}

// Use the real controller and timing helper. Only rendering/DOM boundaries are
// stubbed; this catches a UI state change that fails to schedule further steps.
const mapped = createController();
mapped.context.togglePlayback();
assert.equal(mapped.state.playbackState, "playing");
assert.equal(mapped.state.playbackCursorIndex, 0);
mapped.frameAfter(299);
assert.equal(mapped.state.playbackCursorIndex, 0, "A frame before its deadline must not advance");
mapped.frameAfter(1);
mapped.frameAfter(300);
assert.equal(mapped.state.playbackCursorIndex, 2);
const oldSessionFrame = [...mapped.frames.values()][0];
const oldSessionId = mapped.state.playbackSessionId;
const oldFrameId = mapped.runtime.playbackAnimationFrameId;
const sequence = mapped.state.playbackSequence;
const historyClears = mapped.clearedHistory();
mapped.context.togglePlayback();
assert.equal(mapped.state.playbackState, "paused");
assert.equal(mapped.state.playbackCursorIndex, 2);
assert.ok(mapped.cancelledFrames.includes(oldFrameId));
assert.equal(mapped.frames.size, 0);
mapped.frameAfter(5000);
assert.equal(mapped.state.playbackCursorIndex, 2, "Paused time cannot move the current event");

mapped.context.togglePlayback();
assert.equal(mapped.state.playbackState, "playing");
assert.equal(mapped.state.playbackCursorIndex, 2, "Resume keeps the paused event until the next step");
assert.equal(mapped.state.playbackSequence, sequence, "Resume retains the current sequence");
assert.equal(mapped.clearedHistory(), historyClears, "Resume does not discard trace history");
assert.ok(mapped.state.playbackSessionId > oldSessionId);
assert.equal(mapped.frames.size, 1, "Resume schedules a real animation frame, not only a playing label");
oldSessionFrame(mapped.now() + 10000);
assert.equal(mapped.state.playbackCursorIndex, 2, "A cancelled session cannot advance after resume");
mapped.frameAfter(299);
assert.equal(mapped.state.playbackCursorIndex, 2);
mapped.frameAfter(1);
assert.equal(mapped.state.playbackCursorIndex, 3, "The resumed callback advances to the next event");
mapped.frameAfter(300);
assert.equal(mapped.state.playbackCursorIndex, 4, "Resume continues through successive animation frames");

// Retiming a running session replaces its scheduled callback and preserves its
// position; another pause/resume must still advance at the chosen speed.
mapped.context.applyPlaybackSpeed(8);
assert.equal(mapped.frames.size, 1);
mapped.frameAfter(149);
assert.equal(mapped.state.playbackCursorIndex, 4);
mapped.frameAfter(1);
assert.equal(mapped.state.playbackCursorIndex, 5);
mapped.context.pausePlayback();
mapped.context.togglePlayback();
mapped.frameAfter(150);
assert.equal(mapped.state.playbackCursorIndex, 6);
mapped.frameAfter(150);
assert.equal(mapped.state.playbackCursorIndex, 7);
mapped.frameAfter(150);
assert.equal(mapped.state.playbackState, "finished");
assert.equal(mapped.frames.size, 0);
mapped.context.togglePlayback();
assert.equal(mapped.state.playbackState, "playing");
assert.equal(mapped.state.playbackCursorIndex, 0, "Play after completion restarts from the first event");
assert.equal(mapped.clearedHistory(), historyClears + 1);
mapped.frameAfter(150);
assert.equal(mapped.state.playbackCursorIndex, 1);

const unmapped = createController({ unmappedAt: 2 });
unmapped.context.togglePlayback();
unmapped.frameAfter(300);
unmapped.frameAfter(300);
unmapped.context.pausePlayback();
assert.equal(unmapped.context.currentPlaybackEvent().has_coordinates, false);
unmapped.context.togglePlayback();
unmapped.frameAfter(300);
assert.equal(unmapped.state.playbackCursorIndex, 3, "An unmapped paused report does not block playback resume");

// Run the actual click callback bodies used by the timeline and both map
// controls. All three must share the tested controller, with no second toggle.
for (const button of ["playPauseButton", "clusterPlayPauseButton", "clusterHeaderPlayPauseButton"]) {
  const pattern = new RegExp(`els\\.${button}\\.addEventListener\\("click", function \\(\\) \\{([\\s\\S]*?)\\n\\s*\\}\\);`, "g");
  const bindings = [...source.matchAll(pattern)];
  assert.equal(bindings.length, 1, `${button} has one Play/Pause handler`);
  const controller = createController();
  const click = vm.runInContext(`(function () { ${bindings[0][1]} })`, controller.context);
  click();
  controller.frameAfter(300);
  click();
  assert.equal(controller.state.playbackState, "paused", `${button} pauses`);
  assert.equal(controller.state.playbackCursorIndex, 1);
  click();
  controller.frameAfter(300);
  assert.equal(controller.state.playbackCursorIndex, 2, `${button} resumes actual event advancement`);
}

// Retained playback trails make a full Pause/Resume status render exercise the
// legend. Use the actual status, trail and viewport functions here: stubbing
// the bounds/intersection contract hid a TypeError after the icon became Play
// or Pause but before the controller could schedule the next animation frame.
const retainedTrail = createController();
const bounds = { getSouth: () => -5, getWest: () => -5, getNorth: () => 5, getEast: () => 5 };
const fakeElement = () => ({ textContent: "", setAttribute() {} });
const els = {
  playPauseButton: fakeElement(), playbackResetButton: fakeElement(),
  playbackStatus: fakeElement(), playbackCurrentEvent: fakeElement(), openCurrentEventButton: fakeElement(),
};
retainedTrail.runtime.map = { getBounds: () => bounds, hasLayer: () => false, removeLayer() {} };
retainedTrail.runtime.playbackLayer = { hasLayer: () => false, removeLayer() {} };
retainedTrail.runtime.playbackTrailLines = [];
retainedTrail.runtime.playbackTrailCanvasLayer = {
  _segments: [], setSegments(segments) { this._segments = segments; }, addTo() {},
};
Object.assign(retainedTrail.state, {
  traceMode: "playback", playbackTracePersistence: "persistent",
  regionSelection: { knownDirectionOnly: true }, showTraceDirectionArrows: true, resultsFollowPlayback: true,
});
const summaries = [];
Object.assign(retainedTrail.context, {
  TRACE_DIRECTIONS: directions, TRACE_VIEWPORT_LAT_PAD: 0, TRACE_VIEWPORT_LON_PAD: 0,
  SMALL_SCREEN_WIDTH: 768, els,
  document: { body: { classList: { toggle() {} } } },
  traceModeIncludesPlayback: () => true, regionSelectionAffectsRendering: () => false,
  traceVisibleUnderActiveTraceAndRegionFilters: () => true,
  eventVisibleUnderActiveTraceAndRegionFilters: () => true,
  syncTraceFacilityDisplayRestriction() {}, scheduleLegendTraceDirectionRefresh() {},
  updateTrailLegendVisibility() {}, renderPlaybackMapDateBadge() {}, renderTimelinePlaybackMarker() {},
  eventDateLabel: event => String(event.sort_ordinal), displayLocationForEvent: () => "fixture location",
  getColorKeyForEvent: () => "sphere", labelForColorKey: key => key,
  renderMapLegend: () => summaries.push(retainedTrail.context.legendTraceDirectionView().summary),
});
retainedTrail.context.window.innerWidth = 1024;
vm.runInContext([
  "renderPlaybackStatus", "syncPlaybackTrailVisibility", "syncPlaybackTrailEntryVisibility",
  "syncPlaybackTrailCanvas", "playbackTrailEntryVisibleUnderFacilityFilter", "traceSegmentVisibleUnderDirectionFilter",
  "legendTraceDirectionView", "currentMapViewportBoundsSnapshot", "traceSegmentMayIntersectBounds",
  "wrappedSegmentCopies", "worldIndicesNearReferenceLongitude", "normalizeLongitude",
].map(extractFunction).join("\n"), retainedTrail.context);
retainedTrail.context.togglePlayback();
retainedTrail.frameAfter(300);
retainedTrail.frameAfter(300);
const retainedSegments = [
  { traceId: "known", from: [0, 0], to: [1, 1], chronology: { status: "ordered" } },
  { traceId: "unknown", from: [1, 1], to: [2, 2], chronology: { status: "unknown" } },
  { traceId: "offscreen", from: [40, 40], to: [41, 41], chronology: { status: "ordered" } },
];
retainedTrail.runtime.playbackTrailLines = retainedSegments.map(segment => ({ traceId: segment.traceId, segment, lines: [] }));
assert.doesNotThrow(() => retainedTrail.context.togglePlayback(), "Pause must render a populated persistent-trail legend without a bounds error");
assert.equal(retainedTrail.state.playbackState, "paused");
assert.equal(retainedTrail.state.playbackCursorIndex, 2);
assert.equal(summaries.at(-1).uniqueSegments, 1, "The compass counts only the known, visible trail link");
assert.equal(retainedTrail.runtime.playbackTrailCanvasLayer._segments.length, 2, "Viewport selection does not destroy an offscreen retained trail");
assert.equal(retainedTrail.runtime.playbackTrailLines.length, 3, "Known-only filtering preserves unknown trail history");
assert.doesNotThrow(() => retainedTrail.context.togglePlayback(), "Resume must finish its full status render and schedule another frame");
assert.equal(retainedTrail.state.playbackState, "playing");
assert.equal(retainedTrail.frames.size, 1);
retainedTrail.frameAfter(300);
assert.equal(retainedTrail.state.playbackCursorIndex, 3, "Playback really advances after the populated legend renders on resume");
retainedTrail.frameAfter(300);
assert.equal(retainedTrail.state.playbackCursorIndex, 4);

console.log("Playback controller resume passed: mapped/unmapped reports, successive timed frames, cancelled session rejection, preserved position/history, speed changes, finished restart, all three controls and full persistent-trail legend rendering with real viewport bounds.");
