import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const app = fs.readFileSync(new URL("../app.js", import.meta.url), "utf8");
function actualFunction(name) {
  const begin = app.indexOf("  function " + name + "(");
  const end = app.indexOf("\n  function ", begin + 3);
  assert.ok(begin >= 0 && end > begin, "Expected actual application function " + name);
  return app.slice(begin, end);
}
let canonical = true;
const calls = [], decorations = [];
const context = vm.createContext({ Object, Number, String, Array, Date, Math, Boolean,
  runtime: { catalogSummaryMemory: { fallbackPlaybackKeysReleased: 0, compactPlaybackKeys: 0, unusedPropertiesReleased: 0, prunedEvents: 0 },
    encounterEvidence: { ready: true }, encounterLabelOrigins: { ready: true }, traceChronologyEvidence: null },
  activeCatalogUsesCanonicalWebArtifacts: () => canonical,
  canonicalPlaybackSortKeyIsDefaultFallback: () => false,
  internCanonicalSummaryString: value => value,
  applyLocationLabelOverlay: event => event,
  getVisualTypeGroup: () => "UFO/UAP sighting",
  DEFAULT_CANONICAL_PLAYBACK_SORT_KEY: [3, null, null, 3, 0],
  ENCOUNTERS: {
    decorateInPlace(event) { decorations.push("owned"); event.encounterEvidenceReady = true; return event; },
    decorate(event) { decorations.push("borrowed"); return { ...event, encounterEvidenceReady: true }; },
  },
});
for (const name of ["parseIsoParts", "daysFromCivil", "isoToOrdinal", "finiteChronologyNumber",
  "applyMufonDateReview", "compactCanonicalSummaryEventForRuntime", "hydrateCatalogEvent"]) {
  vm.runInContext(actualFunction(name), context, { filename: "app.js:" + name });
}
const nativeOrdinal = context.isoToOrdinal;
context.isoToOrdinal = value => { calls.push(value); return nativeOrdinal(value); };
const fixtures = [
  { sort_date_iso: "1954-09-16", sort_ordinal: 999, expected: nativeOrdinal("1954-09-16"), conversions: 1 },
  { sort_date_iso: "1970-01-01", sort_ordinal: 999, expected: 0, conversions: 1 },
  { sort_date_iso: null, sort_ordinal: 999, expected: null, conversions: 0 },
  { sort_date_iso: "", sort_ordinal: 0, expected: null, conversions: 0 },
  { sort_ordinal: 999, expected: null, conversions: 0 },
];
for (canonical of [true, false]) {
  for (const fixture of fixtures) {
    calls.length = 0; decorations.length = 0;
    const event = { event_id: 123, chunk_id: "chunk_000001", detail_index: 4, source: "ufocat", type: "Disk",
      date_precision: fixture.sort_date_iso ? "exact_day" : "unknown", has_coordinates: true, lat: 10, lon: 20,
      ...fixture };
    const before = JSON.stringify(event);
    const hydrated = context.hydrateCatalogEvent(event);
    assert.equal(hydrated.sort_ordinal, fixture.expected, "Canonical and borrowed legacy records retain date/null/epoch-zero semantics");
    assert.equal(calls.length, fixture.conversions,
      canonical ? "Canonical hydration must reuse the ordinal calculated by its actual compactor" : "Borrowed legacy ordinals must be recomputed from their current date rather than trusting a stale value");
    assert.equal(JSON.stringify(event), before, "Hydration does not mutate a borrowed source record through the encounter decorator");
    assert.deepEqual(decorations, [canonical ? "owned" : "borrowed"]);
    assert.equal(hydrated.encounterEvidenceReady, true);
    assert.equal(hydrated.encounterOccurrenceDateExcluded, null);
  }
}
canonical = false;
context.runtime.traceChronologyEvidence = { exclusion: id => id === 123 ? { reason: "source_date_withheld" } : null };
const legacy = context.hydrateCatalogEvent({ event_id: 123, sort_date_iso: "1970-01-01", sort_ordinal: 444,
  parsed_time_local_minutes: "0", estimated_utc_timestamp_ms: "", lat: 0, lon: 0 });
assert.equal(legacy.sort_ordinal, 0);
assert.equal(legacy.parsed_time_local_minutes, 0);
assert.equal(legacy.estimated_utc_timestamp_ms, null);
assert.equal(legacy.encounterOccurrenceDateExcluded, true);
assert.equal(legacy.has_coordinates, true);
console.log("Actual canonical compaction and hydration perform each date conversion once; borrowed legacy records, unknown dates, epoch zero and occurrence exclusions retain their semantics.");
