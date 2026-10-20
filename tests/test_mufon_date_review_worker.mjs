import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import {createRequire} from "node:module";

const require = createRequire(import.meta.url);
const Review = require("../mufon_date_review.js");
const Session = require("../analysis_session.js");
const fixtures = JSON.parse(fs.readFileSync(new URL("../docs/qa/mufon-date-review-20261019/fixtures.json", import.meta.url), "utf8"));
const source = fs.readFileSync("catalog_filter_worker.js", "utf8");
const messages = [], self = {postMessage: message => messages.push(message)};
const context = vm.createContext({self, console});
vm.runInContext(fs.readFileSync("analysis_stats.js", "utf8"), context);
// Expose the actual private decoder and artifact validators only in this VM.
// No production test hook, copied decoder or corpus-sized fixtures are needed.
const instrumented = source.replace(/\}\)\(\);\s*$/, `
  self.reviewFixture = {
    read: function () { return chunks.flatMap(function (chunk) {
      return Array.from({length:chunk.length}, function (_, index) {
        return {...readRowValuesInto({}, chunk, index)};
      });
    }); },
    seed: function (delayRows, delayManifest, dictionary, timeRows, timeManifest) {
      const delay = applyReportingDelayProjection(delayRows, delayManifest);
      const time = applyTimeOfDayProjection(dictionary, timeRows, timeManifest);
      analysisReportingDelayArtifact = {loaded:true, manifest:delayManifest, typedRows:delay.typedRows};
      analysisTimeOfDayArtifact = {loaded:true, manifest:timeManifest, typedRows:time.typedRows};
      invalidateAnalysisCache();
    },
    withheldN: function () { return occurrenceDateWithheldIds.size; }
  };
})();`);
assert.notEqual(instrumented, source);
vm.runInContext(instrumented, context);
function send(message) {
  messages.length = 0;
  self.onmessage({data:message});
  assert.equal(messages.length, 1);
  assert.notEqual(messages[0].type, "catalogFacetWorkerError", messages[0].error);
  return JSON.parse(JSON.stringify(messages[0].result || messages[0]));
}
const reviewedRows = fixtures.map(fixture => {
  const event = Review.apply(fixture.summary);
  return {eventId:event.event_id, source:event.source, type:event.type, craftType:event.craft_type_inferred,
    datePrecision:event.date_precision, sortOrdinal:event.sort_ordinal, occurrenceDateWithheld:true,
    mapped:event.has_coordinates === true, precision:event.location_precision};
});
const base = {source:"mufon", type:"Light", craftType:"light", mapped:false, precision:"unknown"};
const rows = [...reviewedRows,
  {...base, eventId:1, datePrecision:"unknown", sortOrdinal:null},
  // A current, dated projection wins even if an older withheld flag is retained.
  {...base, eventId:2, datePrecision:"exact_day", sortOrdinal:0, occurrenceDateWithheld:true}];
send({type:"addCatalogFacetRows", rows});
assert.equal(self.reviewFixture.withheldN(), 6, "Sparse state holds only explicit exceptions, without a catalog-sized array");
const delayManifest = {codes:{source:["mufon"], era:["unknown"], macroregion:["unknown"],
  selectedRole:["reported"], status:["reported_valid"], delayBin:["over_365_days"]}, counts:{typedRows:rows.length}};
const timeManifest = {codes:{source:["mufon"], macroregion:["unknown"], status:["exact_clock"], timeBin:["night_00_05"]},
  counts:{typedRows:rows.length}};
const delayRows = rows.map((row, index) => [index, row.eventId, 0, 0, 0, 0, 0, 43000, 0]);
const timeRows = rows.map((row, index) => [index, row.eventId, 0, 0]);
const dictionary = [[0, "fixture", "00:01", 0, 0, 1, 1, 0, 0, 1, 1, 1, 1, rows.length]];
self.reviewFixture.seed(delayRows, delayManifest, dictionary, timeRows, timeManifest);
const decoded = self.reviewFixture.read();
for (const row of decoded.slice(0, 5)) {
  assert.equal(row.occurrenceDateWithheld, true);
  assert.equal(row.sortOrdinal, null);
  assert.equal(row.datePrecision, "unknown");
  assert.equal(row.analysisReportingDelayAvailable, false);
  assert.equal(row.analysisReportingDelayStatus, "unavailable");
  assert.equal(row.analysisReportingDelayBin, "unknown");
  assert.equal(row.analysisReportingDelayDays, null);
  assert.equal(row.analysisReportingDelaySelectedRole, "reported", "Preserved source-role evidence is not rewritten");
  assert.equal(row.analysisTimeOfDayAvailable, false);
  assert.equal(row.analysisTimeOfDayStatus, "unavailable");
  assert.equal(row.analysisTimeOfDayDescriptiveBin, "unknown");
  assert.equal(row.analysisTimeOfDayInferentialBin, "unknown");
  assert.equal(row.analysisTimeOfDayLowerMinute, null);
  assert.equal(row.analysisTimeOfDayUpperMinute, null);
  assert.equal(row.source, "mufon");
  assert.ok(fixtures.some(fixture => fixture.event_id === row.eventId), "Source report identity remains present");
}
for (const row of decoded.slice(5)) {
  assert.equal(row.occurrenceDateWithheld, false);
  assert.equal(row.analysisTimeOfDayAvailable, true, "Other unknown dates may retain an independently supported clock");
  assert.equal(row.analysisTimeOfDayStatus, "exact_clock");
  assert.equal(row.analysisTimeOfDayLowerMinute, 1);
  assert.equal(row.analysisReportingDelayAvailable, true, "The specific review does not rewrite unrelated artifact values");
}
const filters = {sourceMode:"all", typeMode:"all", precisionMode:"all", hideNonExactDates:false};
const targetIds = fixtures.map(fixture => String(fixture.event_id));
const result = send({type:"computeAnalysis", baselineMode:"full_catalog", fullTimeRange:true,
  selectedDomains:["time"], quickMode:false, filters:{...filters, analysisSessionEventIds:targetIds}});
assert.equal(result.summary.activeCount, 5, "Reports remain inspectable in All Time");
assert.equal(result.time.reportingDelay.coverage.active.typedRows, 0, "Stale 43,000-day delays cannot be counted");
assert.equal(result.time.timeOfDay.coverage.active.typedRows, 0, "Stale exact-clock artifacts cannot resurrect withheld times");
const capture = ids => send({type:"captureAnalysisSession", requestedEventIds:ids, fullTimeRange:true, filters});
const a = capture(targetIds), b = capture(["1"]);
assert.equal(a.summary.distributions.timeOfDay.eligibleN, 0);
assert.equal(a.summary.distributions.timeOfDay.unknownN, 5);
assert.equal(b.summary.distributions.timeOfDay.eligibleN, 1, "A/B capture uses the same reviewed row decoder");
const store = Session.createStore();
store.setGroup("A", {...a, label:"Reviewed dates"});
store.setGroup("B", {...b, label:"Independent clock"});
const comparison = store.getState().comparison.distributions.timeOfDay;
assert.equal(comparison.rows.find(row => row.key === "night_00_05").aCount, 0);
assert.equal(comparison.rows.find(row => row.key === "night_00_05").bCount, 1);
send({type:"resetCatalogFacetRows"});
assert.equal(self.reviewFixture.withheldN(), 0, "Catalog reset clears sparse review state");
send({type:"addCatalogFacetRows", rows:[{...reviewedRows[0], occurrenceDateWithheld:false}]});
assert.equal(self.reviewFixture.withheldN(), 0, "A replacement catalog does not inherit old exceptions");
console.log("Reviewed occurrence dates suppress stale typed delay/time artifacts in Analysis and A/B captures, preserve independent clocks and clear sparse state on reset.");
