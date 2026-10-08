import assert from "node:assert/strict";
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { computeCrossContext, shiftYear, distanceKm } = require("../analysis_cross_context.js");
const day = (iso) => Date.parse(iso + "T00:00:00Z") / 86400000;
const record = (id, iso, extra = {}) => ({
  id, startOrdinal: day(iso), endOrdinal: day(iso), datePrecision: "exact_day",
  dateRole: "catalog_unspecified", lat: 0, lon: 0, uncertaintyKm: null,
  coordinateEvidenceClass: "locality_centroid", sourceFamilyIds: [id + "_source"],
  exclusionReasons: [], ...extra,
});
const result = (crops, animals, options = {}) => computeCrossContext({
  crops, animals, windows: [{ id: "test", radiusKm: 50, dayWindow: 7 }], ...options,
});
const publicRow = (value) => value.lanes.find((lane) => lane.id === "public_marker").rows[0];
const strictRow = (value) => value.lanes.find((lane) => lane.id === "strict_site").rows[0];

// No fabricated epoch-zero/1970 records; legitimate UNIX-day zero remains valid.
let value = result([record("epoch", "1970-01-01"), record("missing", "1970-01-01", { startOrdinal: null, endOrdinal: null })],
  [record("animal", "1970-01-01", { dateRole: "report_date" })]);
assert.equal(value.coverage.crops.exactDayN, 1);
assert.equal(publicRow(value).observedPairN, 1);
assert.equal(publicRow(value).samplePairs[0].cropOrdinal, 0);
assert.equal(publicRow(value).samplePairs[0].cropDateRole, "catalog_unspecified");
assert.equal(publicRow(value).samplePairs[0].animalDateRole, "report_date");
assert.equal(publicRow(value).unknownUncertaintyPairN, 1);
assert.equal(publicRow(value).definitelyNearPairN, 0);

// Generalized coordinates/dates cannot pass strict gates merely via a true flag.
value = result([record("crop", "2000-07-01", { strictEligible: true })],
  [record("animal", "2000-07-01", { strictEligible: true })]);
assert.equal(value.qualityGates.strictCropClusterN, 0);
assert.equal(value.qualityGates.strictAnimalClusterN, 0);
assert.equal(strictRow(value).observedPairN, 0);

// Verified occurrence/formation lanes retain explicit bounded uncertainty.
const sourceSite = { strictEligible: true, coordinateEvidenceClass: "source_bounded", uncertaintyKm: 0.1 };
value = result([record("crop", "2000-07-01", { ...sourceSite, dateRole: "formation_date" })],
  [record("animal", "2000-07-01", { ...sourceSite, dateRole: "death_interval" })]);
assert.equal(strictRow(value).observedPairN, 1);
assert.equal(strictRow(value).definitelyNearPairN, 1);
assert.equal(strictRow(value).inferenceEligible, false);
assert.equal(strictRow(value).pValue, null);

// Co-located same-day repeats are one pair, and every member's lineage is checked.
const crop = record("crop", "2000-07-01");
value = result([crop, { ...crop, id: "crop_repeat" }],
  [record("animal", "2000-07-01"), record("animal_repeat", "2000-07-01")]);
assert.equal(publicRow(value).observedPairN, 1);
assert.equal(value.lanes[0].cropClusterN, 1);
assert.equal(value.lanes[0].animalClusterN, 1);
value = result([crop], [record("animal", "2000-07-01"), record("animal_repeat", "2000-07-01", { sourceFamilyIds: crop.sourceFamilyIds })]);
assert.equal(publicRow(value).observedPairN, 0);
assert.equal(publicRow(value).lineageExclusions.shared_source_family, 1);

for (const [left, right, reason] of [
  [{ originUfoEventIds: ["17"] }, { originUfoEventIds: [17] }, "shared_originating_ufo"],
  [{ originPublisherCodes: ["NUFORC"] }, { publisherCodes: ["nuforc"] }, "shared_originating_publisher"],
  [{ lineageHash: "same" }, { lineageHash: "same" }, "shared_lineage"],
]) {
  value = result([record("crop", "2000-07-01", left)], [record("animal", "2000-07-01", right)]);
  assert.equal(publicRow(value).observedPairN, 0);
  assert.equal(publicRow(value).lineageExclusions[reason], 1);
}

// Exact-day temporal alignment is independent of mapped spatial eligibility.
value = result([crop, record("month", "2000-07-01", { datePrecision: "month", endOrdinal: day("2000-07-31") })],
  [record("unmapped", "2000-07-01", { lat: null, lon: null })]);
assert.equal(publicRow(value).observedPairN, 0);
assert.equal(value.lanes.find((lane) => lane.id === "calendar_alignment").rows[0].observedPairN, 1);
assert.equal(value.coverage.crops.nonExactOrUndatedN, 1);

// Same location and season controls have four independent date anchors, not
// duplicated records or fabricated continuous-surveillance denominators.
const controls = [1998, 1999, 2000, 2001, 2002].map((year) => record("animal" + year, year + "-07-01"));
controls.push(record("early", "1997-01-01", { lon: 100 }), record("late", "2003-12-31", { lon: 100 }));
value = result([crop], controls);
assert.equal(publicRow(value).observedPairN, 1);
assert.equal(publicRow(value).controlPairN, 4);
assert.equal(publicRow(value).controlWindowN, 4);
assert.equal(publicRow(value).expectedMatchedPairN, 1);
assert.equal(publicRow(value).descriptiveObservedControlRatio, 1);
assert.equal(publicRow(value).lineageUnverifiedPairN, 1);
assert.equal(publicRow(value).qValue, null);

// Date-window edges exclude partially observed anchors from the control ratio.
value = result([crop], controls, { filters: { startOrdinal: day("2000-07-01"), endOrdinal: day("2000-07-01") } });
assert.equal(publicRow(value).observedPairN, 1);
assert.equal(publicRow(value).matchedCropAnchorN, 0);
assert.equal(publicRow(value).descriptiveObservedControlRatio, null);

// Missing controls/zero control pairs never produce an infinite enrichment.
value = result([crop], [record("animal", "2000-07-01")]);
assert.equal(publicRow(value).controlStatus, "no_complete_same_season_controls");
assert.equal(publicRow(value).descriptiveObservedControlRatio, null);
const zeroControls = [record("animal", "2000-07-01"), record("early", "1997-01-01", { lon: 100 }), record("late", "2003-12-31", { lon: 100 })];
value = result([crop], zeroControls);
assert.equal(publicRow(value).controlStatus, "zero_control_pairs_ratio_unavailable");
assert.equal(publicRow(value).descriptiveObservedControlRatio, null);

// Uncertainty that crosses a threshold is explicitly ambiguous, even strict.
value = result([record("crop", "2000-07-01", { ...sourceSite, dateRole: "formation_date", uncertaintyKm: 1 })],
  [record("animal", "2000-07-01", { ...sourceSite, dateRole: "occurrence_date", uncertaintyKm: 1, lon: 0.44 })]);
assert.equal(strictRow(value).observedPairN, 1);
assert.equal(strictRow(value).definitelyNearPairN, 0);
assert.equal(strictRow(value).uncertaintyBoundaryPairN, 1);
assert.ok(distanceKm({ lat: 0, lon: 179.9 }, { lat: 0, lon: -179.9 }) < 23);
assert.equal(shiftYear(day("2000-02-29"), 1), day("2001-02-28"));
assert.equal(shiftYear(day("2000-02-29"), -1), day("1999-02-28"));

// The actual changed-only context package preserves source pins and strict 1/0.
const dirname = path.dirname(fileURLToPath(import.meta.url));
const payloadPath = path.resolve(dirname, "../data/analysis_comparisons/context_rows.json");
if (fs.existsSync(payloadPath)) {
  const bytes = fs.readFileSync(payloadPath);
  const payload = JSON.parse(bytes);
  const manifest = JSON.parse(fs.readFileSync(path.resolve(dirname, "../data/analysis_comparisons/context_manifest.json")));
  assert.equal(crypto.createHash("sha256").update(bytes).digest("hex"), manifest.artifacts.contextRows.sha256);
  assert.equal(payload.ordinalEpoch, "unix_day");
  assert.equal(payload.crops.length, 7745);
  assert.equal(payload.animals.length, 1184);
  const started = performance.now();
  value = computeCrossContext(payload);
  assert.ok(performance.now() - started < 5000, "Indexed full-context comparison should remain lightweight");
  assert.equal(value.qualityGates.strictCropClusterN, 1);
  assert.equal(value.qualityGates.strictAnimalClusterN, 0);
  assert.equal(value.qualityGates.inferenceEligible, false);
  assert.equal(value.lanes[0].cropClusterN, 3579);
  assert.equal(value.lanes[0].animalClusterN, 308);
  assert.deepEqual(value.lanes[0].rows.map((row) => row.observedPairN), [5, 8, 19]);
  assert.deepEqual(value.lanes[0].rows.map((row) => row.unknownUncertaintyPairN), [5, 8, 19]);
  assert.ok(payload.crops.every((row) => !row.utcTimestamp));
  assert.ok(payload.animals.every((row) => !row.utcTimestamp));
  assert.equal(payload.animals.find((row) => row.title.includes("Crosby County")).dateRole, "publication_date");
}
console.log("Cross-context eligibility, source collisions, deduplication, date roles, controls, uncertainty and real-artifact checks passed.");
