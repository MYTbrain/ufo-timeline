import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import vm from "node:vm";
const require = createRequire(import.meta.url);
const availability = require("../famous_case_availability.js");
const neighborhood = require("../trace_neighborhood.js");

function report(id, lat, day = "1986-01-29", extra = {}) {
  return { event_id: id, lat, lon: 135.6, sort_date_iso: day, date_precision: "exact_day",
    craft_type_inferred: "sphere_orb", has_coordinates: true, ...extra };
}
const cases = [
  { id: "near", startIso: "1986-01-28", endIso: "1986-01-30", lat: 44.55 },
  { id: "far", startIso: "1986-01-28", endIso: "1986-01-30", lat: -30 },
  { id: "outside", outside: true },
];
const options = {
  selectionWindow: item => item.outside ? null : item,
  containsPoint: (item, lat) => Math.abs(item.lat - lat) < 0.1,
  buildSegments: neighborhood.buildSameDayCraftTraceSegments,
};
const events = [report("local", 44.55), report("remote", 20), report("another-day", 10, "1986-01-31")];
const before = JSON.stringify({ cases, events });
const result = availability.summarizeCases(cases, events, options);
assert.deepEqual(result.near, { localReportCount: 1, availableConnectionCount: 1, connectionCount: 1, status: "connections", label: "1 link" });
assert.equal(result.far.status, "no_reports");
assert.equal(result.far.label, "No local reports");
assert.equal(result.outside.status, "outside_catalog");
assert.equal(result.outside.label, "Outside catalog");
assert.equal(JSON.stringify({ cases, events }), before, "previews never mutate reports or presets");

const isolated = availability.summarizeCases(cases, [events[0]], options).near;
assert.equal(isolated.status, "reports_only");
assert.equal(isolated.label, "Reports only");
assert.equal(isolated.connectionCount, 0);
assert.equal(availability.summarizeCases(cases, [], options).near.status, "no_reports");

const hidden = availability.summarizeCases(cases, events, { ...options, filterSegment: () => false }).near;
assert.equal(hidden.availableConnectionCount, 1);
assert.equal(hidden.connectionCount, 0);
assert.equal(hidden.localReportCount, 1);
assert.equal(hidden.label, "Links hidden by filters");
const visible = availability.summarizeCases(cases, events, { ...options, filterSegment: segment => segment }).near;
assert.equal(visible.connectionCount, 1, "a map filter may return its accepted segment rather than a boolean");

const dateScope = [report("padding-local", 44.55, "1986-01-28"), report("padding-remote", 20, "1986-01-28"),
  report("out-local", 44.55, "1986-01-31"), report("out-remote", 20, "1986-01-31")];
assert.equal(availability.summarizeCases(cases, dateScope, options).near.connectionCount, 1, "use the supplied padded window inclusively");
assert.equal(availability.summarizeCases(cases, [report("local", 44.55), report("remote", 20, "1986-01-30")], options).near.connectionCount, 0, "different dates do not create same-day links");

const unknownCraft = [report("local", 44.55, undefined, { craft_type_inferred: "unknown" }), report("remote", 20)];
assert.equal(availability.summarizeCases(cases, unknownCraft, options).near.status, "reports_only", "local reports without eligible craft categories still appear as reports");
const inexactDate = [report("local", 44.55, undefined, { date_precision: "month" }), report("remote", 20)];
assert.equal(availability.summarizeCases(cases, inexactDate, options).near.connectionCount, 0, "inexact dates never become links even if the current report filters allow them");

let graphCalls = 0;
const crossing = availability.summarizeCases(cases, [report("south", 40), report("north", 50)], {
  ...options, buildSegments(rows) { graphCalls += 1; return options.buildSegments(rows); },
});
assert.equal(crossing.near.status, "no_reports", "a crossing line cannot substitute for a local report");
assert.equal(graphCalls, 0, "empty vicinities do not build unnecessary graphs");

const duplicates = availability.summarizeCases(cases, events.concat(events[0], { ...events[0] }), options).near;
assert.equal(duplicates.localReportCount, 1);
assert.equal(duplicates.connectionCount, 1);
const distinctIds = availability.summarizeCases(cases, [report("local-a", 44.54), report("local-b", 44.56), report("remote", 20)], options).near;
assert.equal(distinctIds.localReportCount, 2);
assert.equal(distinctIds.connectionCount, 2);

const invalid = [report("null", null), report("blank", ""), report("boolean", false), report("too-far", 91),
  report("unmapped", 44.55, undefined, { has_coordinates: false }), report("invalid-day", 44.55, "1986-02-30"),
  report("no-id", 44.55, undefined, { event_id: "" }), report("bad-lon", 44.55, undefined, { lon: Infinity })];
assert.equal(availability.summarizeCases(cases, invalid, options).near.localReportCount, 0, "invalid and unmapped records cannot advertise available reports");
const numeric = availability.summarizeCases(cases, [report(0, "44.55"), report(1, 20)], options).near;
assert.equal(numeric.localReportCount, 1);
assert.equal(numeric.connectionCount, 1, "numeric IDs and numeric coordinates follow the graph's accepted schema");

const wrapped = availability.summarizeCases([{ ...cases[0], id: "wrapped" }], [report("local", 44.55, undefined, { lon: -179.9 }), report("remote", 20)], {
  ...options, containsPoint: (_item, lat, lon) => Math.abs(lat - 44.55) < 0.1 && Math.abs((((lon - 179.9 + 180) % 360) + 360) % 360 - 180) < 1,
});
assert.equal(wrapped.wrapped.connectionCount, 1, "vicinity membership delegates to the map's wrapped geometry");
assert.deepEqual(availability.summarizeCases(cases, events.slice().reverse(), options), result, "input order does not change availability");

const browser = vm.createContext({});
vm.runInContext(readFileSync(new URL("../famous_case_availability.js", import.meta.url), "utf8"), browser);
assert.equal(typeof browser.UfoFamousCaseAvailability.summarizeCases, "function");
console.log("Famous-case availability tests passed: real local endpoints, same-day craft links, padded dates, filters, duplicates and browser export.");
