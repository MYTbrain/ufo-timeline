import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const neighborhood = require("../trace_neighborhood.js");

function report(id, craft, day = "1965-12-09", extra = {}) {
  return { event_id: id, craft_type_inferred: craft, sort_date_iso: day, date_precision: "exact_day", lat: 40, lon: -79, has_coordinates: true, ...extra };
}
const events = [
  report("triangle-3", "triangle", undefined, { lat: 42, lon: 179, playback_sort_key: [2, 180, 0, 0, 0] }),
  report("orb-2", "sphere_orb", undefined, { lat: 51, lon: 1, playback_sort_key: [2, 120, 0, 0, 0] }),
  report("triangle-1", "triangle", undefined, { lat: 38, lon: -81, playback_sort_key: [2, 60, 0, 0, 0] }),
  report("orb-1", "sphere_orb", undefined, { lat: 50, lon: 0, playback_sort_key: [2, 30, 0, 0, 0] }),
  report("triangle-2", "triangle", undefined, { lat: 41, lon: -78, playback_sort_key: [2, 120, 0, 0, 0] }),
  report("next-day", "triangle", "1965-12-10"),
];
const snapshot = JSON.stringify(events);
const segments = neighborhood.buildSameDayCraftTraceSegments(events);
assert.deepEqual(segments.map(segment => segment.traceId), ["orb-1->orb-2", "triangle-1->triangle-2", "triangle-2->triangle-3"], "interleaved craft classes connect their own consecutive same-day reports");
assert.equal(JSON.stringify(events), snapshot, "building connections does not modify source reports");
assert.ok(segments.every(segment => segment.gapDays === 0 && segment.sameDayOrderKnown === false), "same-day display order never claims known travel timing");
assert.ok(segments.every(segment => segment.source === "famous_case_same_day_craft"));
assert.deepEqual(segments[1].eventIds, ["triangle-1", "triangle-2"], "original report ids remain endpoints");
assert.deepEqual(segments[1].from, [38, -81]);
assert.deepEqual(segments[1].to, [41, -78]);
assert.ok(!segments.some(segment => segment.eventIds.includes("next-day")), "a one-day gap is excluded despite ordinary <=1-day trace bucket");
assert.deepEqual(neighborhood.buildSameDayCraftTraceSegments(events.slice().reverse()), segments, "input order does not alter the chain");
assert.deepEqual(neighborhood.buildSameDayCraftTraceSegments(events.concat(events[2], { ...events[2] })), segments, "duplicate report copies do not add links or move neighbors");

const ineligible = [
  report("unknown", "unknown"), report("unrecognized", "invented_shape"),
  report("aircraft", "conventional_or_explained"), report("context", "non_ufo_context"),
  report("month", "triangle", undefined, { date_precision: "month" }),
  report("missing-lat", "triangle", undefined, { lat: null }),
  report("blank-lon", "triangle", undefined, { lon: "" }),
  report("boolean-lat", "triangle", undefined, { lat: false }),
  report("non-finite", "triangle", undefined, { lon: Infinity }),
  report("bad-lat", "triangle", undefined, { lat: 91 }),
  report("bad-lon", "triangle", undefined, { lon: -181 }),
  report("unmapped", "triangle", undefined, { has_coordinates: false }),
  report("bad-calendar", "triangle", "1965-02-30"),
  report("missing-id", "triangle", undefined, { event_id: null }),
];
assert.deepEqual(neighborhood.buildSameDayCraftTraceSegments(events.concat(ineligible)), segments, "unknown craft, imprecise dates and unusable endpoints cannot produce case connections");
assert.deepEqual(neighborhood.buildSameDayCraftTraceSegments([report("single", "triangle")]), [], "one report never creates a synthetic connection to a case-center point");
assert.deepEqual(neighborhood.buildSameDayCraftTraceSegments([]), []);

const conflicting = [report("duplicate", "triangle"), report("duplicate", "triangle", undefined, { lat: 20 }), report("other", "triangle")];
assert.deepEqual(neighborhood.buildSameDayCraftTraceSegments(conflicting), [], "conflicting locations for a duplicate id are excluded instead of choosing an invented unique location");
assert.deepEqual(neighborhood.buildSameDayCraftTraceSegments(conflicting.slice().reverse()), []);

const metadataOrder = [
  report("z", "disc_saucer", undefined, { parsed_time_local_minutes: 60, lat: 39 }),
  report("a", "disc_saucer", undefined, { parsed_time_local_minutes: 120, lat: 40 }),
  report("none", "disc_saucer", undefined, { lat: 41 }),
];
assert.deepEqual(neighborhood.buildSameDayCraftTraceSegments(metadataOrder).map(segment => segment.traceId), ["z->a", "a->none"], "available presentation time metadata precedes deterministic unknown-time fallback");
const utcOrder = [
  report("late", "light", undefined, { estimated_utc_timestamp_ms: 200, estimated_utc_range_start_ms: 190, estimated_utc_range_end_ms: 210, lat: 41 }),
  report("early", "light", undefined, { estimated_utc_timestamp_ms: 100, estimated_utc_range_start_ms: 90, estimated_utc_range_end_ms: 110, lat: 40 }),
];
assert.deepEqual(neighborhood.buildSameDayCraftTraceSegments(utcOrder).map(segment => segment.traceId), ["early->late"]);
assert.equal(neighborhood.buildSameDayCraftTraceSegments(utcOrder)[0].sameDayOrderKnown, false, "estimated UTC metadata still does not establish flight timing");
assert.deepEqual(neighborhood.buildSameDayCraftTraceSegments([report(12, "triangle", undefined, { lat: 41 }), report(10, "triangle")])[0].eventIds, ["10", "12"], "numeric catalog ids retain their original values as canonical strings");

// Repeated coordinates remain records in the group sequence. Their own
// zero-length links are omitted; the last repeated report still connects to
// its next distinct-location neighbor rather than fabricating a merged event.
const repeatedPlace = [
  report("a", "triangle"), report("b", "triangle"),
  report("c", "triangle", undefined, { lat: 41, lon: -78 }),
];
assert.deepEqual(neighborhood.buildSameDayCraftTraceSegments(repeatedPlace).map(segment => segment.traceId), ["b->c"], "identical coordinates contribute no invisible link but retain the next real chain neighbor");
const datelinePlace = [
  report("a", "triangle", undefined, { lon: 180 }),
  report("b", "triangle", undefined, { lon: -180 }),
  report("c", "triangle", undefined, { lon: -179 }),
];
assert.deepEqual(neighborhood.buildSameDayCraftTraceSegments(datelinePlace).map(segment => segment.traceId), ["b->c"], "equivalent 180/-180 coordinates also omit zero-length links");
assert.deepEqual(neighborhood.buildSameDayCraftTraceSegments([report("north-a", "light", undefined, { lat: 90, lon: 1 }), report("north-b", "light", undefined, { lat: 90, lon: 120 })]), [], "one geographic pole is one location regardless of longitude");
console.log("Famous-case trace tests passed: exact-day craft chains, truthful timing, eligibility and deterministic duplicates.");
