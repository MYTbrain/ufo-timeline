import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
import { isoToOrdinal, ordinalToIso } from "../webapp/static/app-utils.mjs";

const require = createRequire(import.meta.url);
const cases = require("../famous_case_presets.js");
const availability = require("../famous_case_availability.js");
const neighborhood = require("../trace_neighborhood.js");
const directions = require("../trace_direction_summary.js");
const chronology = require("../trace_chronology.js");
const source = readFileSync(new URL("../app.js", import.meta.url), "utf8");

function extractFunction(name) {
  const start = source.indexOf(`  function ${name}(`);
  assert.notEqual(start, -1, `missing integration function ${name}`);
  const nextFunction = source.indexOf("\n  function ", start + 1);
  assert.notEqual(nextFunction, -1, `missing end of integration function ${name}`);
  return source.slice(start, nextFunction);
}

const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g,
  character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);

function report(id, day, lat, lon) {
  return Object.freeze({ event_id: id, sort_date_iso: day, date_precision: "exact_day",
    craft_type_inferred: "sphere_orb", lat, lon, has_coordinates: true });
}

const events = Object.freeze([
  report("dalnegorsk-local", "1986-01-29", 44.55, 135.61),
  report("dalnegorsk-remote", "1986-01-29", -20, -60),
  report("kecksburg-isolated", "1965-12-09", 40.18, -79.46),
]);
const eventSnapshot = JSON.stringify(events);
const catalogSnapshot = JSON.stringify(cases.CASES);

function harness() {
  const scheduled = [];
  const calls = { summaries: 0 };
  const startup = { phase: "Loading", fullCatalogReady: false, backgroundError: "" };
  const runtime = { traceChronologyEvidence: null, traceChronologyStatus: "loading" };
  const state = {
    timelineDataVersion: 1,
    timelineMappedPlaybackEvents: events,
    // The open map is viewing dates far from the cases in the fixture.
    timeRangeStartOrdinal: isoToOrdinal("2000-01-01"),
    timeRangeEndOrdinal: isoToOrdinal("2000-01-02"),
    famousCaseId: "case_dalnegorsk", famousCaseOrder: "chronological",
    regionSelection: { knownDirectionOnly: false },
  };
  const control = { extent: { minOrdinal: isoToOrdinal("1500-01-01"), maxOrdinal: isoToOrdinal("2030-12-31") } };
  const els = {
    filterFamousCases: { innerHTML: "", value: "" },
    famousCaseSearch: { value: "Kecksburg" },
    famousCaseSearchStatus: { textContent: "" },
    famousCaseDetails: { innerHTML: "", hidden: true },
    famousCaseOrderButtons: ["alphabetical", "chronological"].map(order => ({
      dataset: { famousCaseOrder: order }, attributes: {},
      setAttribute(name, value) { this.attributes[name] = value; },
    })),
  };
  const context = vm.createContext({
    Array, Boolean, JSON, Map, Math, Number, Object, Set, String,
    state, runtime, startup, els,
    FAMOUS_CASES: cases, TRACE_NEIGHBORHOOD: neighborhood, TRACE_DIRECTIONS: directions, TRACE_CHRONOLOGY: chronology,
    CASE_AVAILABILITY: {
      summarizeCases(...args) { calls.summaries += 1; return availability.summarizeCases(...args); },
    },
    selectionClampExtent: () => control.extent,
    // Deterministic local-vs-remote geometry; all fixture locals are at their
    // actual preset centers and every remote endpoint is far outside.
    pointInsideCircleShape: (lat, lon, shape) =>
      Math.abs(lat - shape.center.lat) < 0.1 && Math.abs(lon - shape.center.lng) < 0.1,
    isoToOrdinal, ordinalToIso, escapeHtml, formatNumber: String,
    window: { setTimeout(callback) { scheduled.push(callback); } },
  });
  vm.runInContext(["traceChronologyIdentity", "famousCaseAvailabilitySummary", "renderFamousCasePicker"].map(extractFunction).join("\n"), context);
  function flush() {
    const pending = scheduled.splice(0);
    for (const callback of pending) callback();
  }
  function labels() {
    return new Map([...els.filterFamousCases.innerHTML.matchAll(/<option value="(case_[^"]+)"[^>]*>([\s\S]*?)<\/option>/g)]
      .map(match => [match[1], match[2].replace(/<[^>]*>/g, "")]));
  }
  return { context, state, startup, runtime, control, els, calls, scheduled, flush, labels };
}

const app = harness();
assert.equal(app.context.famousCaseAvailabilitySummary(), null, "a partial startup catalog cannot report a false zero");
assert.equal(app.calls.summaries, 0);
assert.equal(app.scheduled.length, 0);
app.context.renderFamousCasePicker();
assert.equal(app.labels().get("case_dalnegorsk"), "1986 · Dalnegorsk / Height 611");
assert.equal(app.labels().get("case_kecksburg"), "1965 · Kecksburg");
assert.match(app.els.famousCaseSearchStatus.textContent, /Checking links…$/);
assert.doesNotMatch(app.els.filterFamousCases.innerHTML, /No local reports|Reports only|0 links/);

app.startup.phase = "Map ready";
assert.equal(app.context.famousCaseAvailabilitySummary(), null, "a progressively rendered map is not the full catalog");
app.context.renderFamousCasePicker();
assert.equal(app.labels().get("case_dalnegorsk"), "1986 · Dalnegorsk / Height 611");
assert.match(app.els.famousCaseSearchStatus.textContent, /Checking links…$/);
assert.equal(app.scheduled.length, 0, "partial map readiness does not schedule availability from incomplete data");
app.startup.phase = "Failed";
app.context.renderFamousCasePicker();
assert.equal(app.labels().get("case_dalnegorsk"), "1986 · Dalnegorsk / Height 611");
assert.equal(app.labels().get("case_kecksburg"), "1965 · Kecksburg");
assert.match(app.els.famousCaseSearchStatus.textContent, /Link counts unavailable$/);
assert.equal(app.scheduled.length, 0);
app.startup.phase = "Map ready";
app.startup.backgroundError = "Catalog loading failed";
app.context.renderFamousCasePicker();
assert.equal(app.labels().get("case_dalnegorsk"), "1986 · Dalnegorsk / Height 611");
assert.match(app.els.famousCaseSearchStatus.textContent, /Link counts unavailable$/, "background catalog failure remains explicit in shared status after the map renders");
assert.doesNotMatch(app.els.filterFamousCases.innerHTML, /No local reports|Reports only|0 links/);
app.startup.backgroundError = "";
app.startup.fullCatalogReady = true;
app.control.extent = null;
assert.equal(app.context.famousCaseAvailabilitySummary(), null, "an unavailable catalog extent remains unknown");
assert.equal(app.scheduled.length, 0);
app.control.extent = { minOrdinal: isoToOrdinal("1500-01-01"), maxOrdinal: isoToOrdinal("2030-12-31") };
assert.equal(app.context.famousCaseAvailabilitySummary(), null, "first complete-catalog evaluation is deferred");
assert.equal(app.calls.summaries, 0, "rendering does not synchronously scan the catalog");
assert.equal(app.scheduled.length, 1);
assert.equal(app.context.famousCaseAvailabilitySummary(), null);
assert.equal(app.scheduled.length, 1, "repeated calls share the pending computation");
app.flush();
assert.equal(app.calls.summaries, 1);
const first = app.context.famousCaseAvailabilitySummary();
assert.equal(first.case_dalnegorsk.localReportCount, 1);
assert.equal(first.case_dalnegorsk.connectionCount, 1, "the all-date report pool includes connections outside current viewing dates");
assert.equal(first.case_kecksburg.label, "Reports only");
assert.equal(first.case_ariel_school.label, "No local reports");
assert.equal(app.labels().get("case_dalnegorsk"), "1986 · Dalnegorsk / Height 611 1 link");
assert.equal(app.labels().get("case_kecksburg"), "1965 · Kecksburg");
assert.match(app.els.filterFamousCases.innerHTML, /<span class="famous-case-link-count">1 link<\/span>/);
assert.equal((app.els.filterFamousCases.innerHTML.match(/class="famous-case-link-count"/g) || []).length, 1, "only a positive visible connection count receives a badge");
assert.doesNotMatch(app.els.famousCaseSearchStatus.textContent, /Checking links|unavailable/);
assert.equal(app.els.filterFamousCases.value, "case_dalnegorsk", "the active case remains selected even when the search excludes it");
assert.equal(app.els.famousCaseSearch.value, "Kecksburg");
assert.equal(app.labels().size, 2, "only the search match and retained active case are shown");
assert.equal(app.els.famousCaseOrderButtons[1].attributes["aria-pressed"], "true");
assert.equal(app.els.famousCaseOrderButtons[0].attributes["aria-pressed"], "false");

app.state.timeRangeStartOrdinal = isoToOrdinal("1994-09-16");
app.state.timeRangeEndOrdinal = isoToOrdinal("1994-09-16");
app.context.renderFamousCasePicker();
assert.equal(app.context.famousCaseAvailabilitySummary(), first, "date navigation reuses all-date availability");
assert.equal(app.calls.summaries, 1);
assert.equal(app.scheduled.length, 0);

app.state.regionSelection.knownDirectionOnly = true;
assert.equal(app.context.famousCaseAvailabilitySummary(), null, "the direction filter invalidates cached availability");
app.flush();
const knownOnly = app.context.famousCaseAvailabilitySummary();
assert.notEqual(knownOnly, first);
assert.equal(knownOnly.case_dalnegorsk.availableConnectionCount, 1);
assert.equal(knownOnly.case_dalnegorsk.connectionCount, 0, "the real same-day graph does not claim a definite direction");
assert.equal(app.labels().get("case_dalnegorsk"), "1986 · Dalnegorsk / Height 611");
assert.equal(app.labels().get("case_kecksburg"), "1965 · Kecksburg");
assert.doesNotMatch(app.els.filterFamousCases.innerHTML, /class="famous-case-link-count"/, "hidden connections do not retain a badge");
assert.equal(app.els.famousCaseSearch.value, "Kecksburg");
assert.equal(app.els.filterFamousCases.value, "case_dalnegorsk");
assert.equal(app.calls.summaries, 2);

// Report/source filters replace the shared all-date pool and advance its version.
app.state.regionSelection.knownDirectionOnly = false;
app.state.timelineMappedPlaybackEvents = Object.freeze(events.filter(event => event.event_id !== "dalnegorsk-remote"));
app.state.timelineDataVersion += 1;
assert.equal(app.context.famousCaseAvailabilitySummary(), null);
app.flush();
const filtered = app.context.famousCaseAvailabilitySummary();
assert.notEqual(filtered, first);
assert.equal(filtered.case_dalnegorsk.connectionCount, 0);
assert.equal(filtered.case_dalnegorsk.label, "Reports only", "updated report filters change the picker preview");
assert.equal(app.labels().get("case_dalnegorsk"), "1986 · Dalnegorsk / Height 611");
assert.equal(app.calls.summaries, 3);
assert.equal(app.context.famousCaseAvailabilitySummary(), filtered);
assert.equal(app.scheduled.length, 0);

// A newer pending filter state supersedes its predecessor without rendering
// the predecessor's availability under a stale cache key.
app.state.timelineDataVersion += 1;
app.context.famousCaseAvailabilitySummary();
app.state.timelineMappedPlaybackEvents = events;
app.state.timelineDataVersion += 1;
app.context.famousCaseAvailabilitySummary();
assert.equal(app.scheduled.length, 2);
app.flush();
assert.equal(app.calls.summaries, 4, "superseded pending work is discarded");
assert.equal(app.context.famousCaseAvailabilitySummary().case_dalnegorsk.connectionCount, 1);
assert.match(app.labels().get("case_dalnegorsk"), /1 link$/);

app.control.extent = { minOrdinal: isoToOrdinal("1990-01-01"), maxOrdinal: isoToOrdinal("2030-12-31") };
assert.equal(app.context.famousCaseAvailabilitySummary(), null, "catalog extent changes invalidate availability");
app.flush();
assert.equal(app.context.famousCaseAvailabilitySummary().case_dalnegorsk.label, "Outside catalog");
assert.equal(app.labels().get("case_dalnegorsk"), "1986 · Dalnegorsk / Height 611");
assert.equal(JSON.stringify(events), eventSnapshot, "availability does not mutate or reorder shared reports");
assert.equal(JSON.stringify(cases.CASES), catalogSnapshot, "availability does not alter the editorial case catalog");

// Current production graph semantics: accepted, disjoint UTC intervals can
// order a same-day link, while a third report without accepted timing stays
// unresolved. This fixture exercises the real evidence and orientation helpers.
const timedEvents = Object.freeze([
  report(101, "1986-01-29", 44.55, 135.61),
  report(102, "1986-01-29", -20, -60),
  report(103, "1986-01-29", 44.56, 135.62),
]);
const timedSnapshot = JSON.stringify(timedEvents);
const baseMs = Date.parse("1986-01-29T00:00:00Z");
function evidenceIndex(releaseId, rows) {
  return chronology.createEvidenceIndex({
    schemaId: chronology.SCHEMA_ID, sourceContract: chronology.SOURCE_CONTRACT,
    rowSchema: [...chronology.ROW_SCHEMA], releaseId, rows,
    codes: { evidence: [{ status: "accepted", kind: "source_clock", confidence: "high",
      basis: "Synthetic integration fixture with separate accepted UTC intervals" }], zone: ["UTC"] },
  });
}
const timedApp = harness();
timedApp.startup.phase = "Map ready";
timedApp.startup.fullCatalogReady = true;
timedApp.state.timelineMappedPlaybackEvents = timedEvents;
timedApp.runtime.traceChronologyEvidence = evidenceIndex("fixture-accepted-v1", [
  [101, baseMs + 4 * 3600000, baseMs + 4 * 3600000 + 59999, 0, 0],
  [102, baseMs + 6 * 3600000, baseMs + 6 * 3600000 + 59999, 0, 0],
]);
assert.equal(timedApp.context.traceChronologyIdentity(), "fixture-accepted-v1");
const fixtureSegments = neighborhood.buildSameDayCraftTraceSegments(timedEvents,
  { chronology: timedApp.runtime.traceChronologyEvidence, timingSupport: chronology });
assert.equal(fixtureSegments.length, 2);
assert.equal(fixtureSegments.filter(directions.segmentHasKnownDirection).length, 1);
assert.equal(fixtureSegments.find(segment => segment.sameDayOrderKnown).chronology.status, "ordered");
assert.equal(fixtureSegments.find(segment => !segment.sameDayOrderKnown).chronology.status, "unknown");
assert.equal(timedApp.context.famousCaseAvailabilitySummary(), null);
timedApp.flush();
assert.equal(timedApp.context.famousCaseAvailabilitySummary().case_dalnegorsk.connectionCount, 2);
assert.match(timedApp.labels().get("case_dalnegorsk"), /2 links$/);

timedApp.state.regionSelection.knownDirectionOnly = true;
assert.equal(timedApp.context.famousCaseAvailabilitySummary(), null);
timedApp.flush();
const timedKnown = timedApp.context.famousCaseAvailabilitySummary();
assert.equal(timedKnown.case_dalnegorsk.availableConnectionCount, 2);
assert.equal(timedKnown.case_dalnegorsk.connectionCount, 1, "known-only preserves the actually ordered same-day link and hides the unresolved one");
assert.match(timedApp.labels().get("case_dalnegorsk"), /1 link$/);
assert.equal(timedApp.context.famousCaseAvailabilitySummary(), timedKnown);
assert.equal(timedApp.calls.summaries, 2);

const unchangedTimelineVersion = timedApp.state.timelineDataVersion;
timedApp.runtime.traceChronologyEvidence = evidenceIndex("fixture-without-accepted-times-v2", []);
assert.equal(timedApp.context.famousCaseAvailabilitySummary(), null, "a chronology release change invalidates the availability cache");
timedApp.flush();
assert.equal(timedApp.state.timelineDataVersion, unchangedTimelineVersion, "chronology refresh is independent of report-filter versioning");
assert.equal(timedApp.context.famousCaseAvailabilitySummary().case_dalnegorsk.availableConnectionCount, 2);
assert.equal(timedApp.context.famousCaseAvailabilitySummary().case_dalnegorsk.connectionCount, 0);
assert.equal(timedApp.labels().get("case_dalnegorsk"), "1986 · Dalnegorsk / Height 611");
assert.doesNotMatch(timedApp.els.filterFamousCases.innerHTML, /class="famous-case-link-count"/);
assert.equal(timedApp.calls.summaries, 3);
assert.equal(JSON.stringify(timedEvents), timedSnapshot, "evidence-aware previews preserve shared source events");

console.log("Case availability integration passed: positive-link badges, shared loading status, deferred caching, report and chronology filters, accepted directions and picker state.");
