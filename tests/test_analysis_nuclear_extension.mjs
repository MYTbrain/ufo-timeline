import assert from "node:assert/strict";
import fs from "node:fs";
import crypto from "node:crypto";
import zlib from "node:zlib";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const nuclear = require("../analysis_nuclear.js");
const root = new URL("../", import.meta.url);
const read = (path) => fs.readFileSync(new URL(path, root));
const digest = (data) => crypto.createHash("sha256").update(data).digest("hex");
const manifest = JSON.parse(read("data/analysis_comparisons/manifest.json"));
const metadata = manifest.artifacts.nuclearExtension;
const encoded = read("data/analysis_comparisons/nuclear_extension_v1.json");
const gzip = read("data/analysis_comparisons/nuclear_extension_v1.json.gz");
const extension = JSON.parse(encoded);
const base = JSON.parse(read("data/analysis_comparisons/nuclear_context_v1.json"));
assert.equal(extension.schemaId, "ufo-nuclear-context-extension-v1");
assert.equal(extension.ordinalEpoch, "unix_day");
assert.equal(digest(encoded), metadata.sha256);
assert.equal(digest(gzip), metadata.gzipSha256);
assert.deepEqual(zlib.gunzipSync(gzip), encoded);
assert.equal(encoded.length, metadata.bytes);
assert.equal(gzip.length, metadata.gzipBytes);
assert.equal(digest(read("data/analysis_comparisons/nuclear_context_v1.json")), extension.baseArtifact.sha256);
assert.equal(digest(read("data/analysis_comparisons/nuclear_context_v1.json.gz")), extension.baseArtifact.gzipSha256);
assert.equal(extension.tests.length, 6);
assert.equal(new Set(extension.tests.map((row) => row.id)).size, 6);
assert.deepEqual(extension.tests.map((row) => row.date), ["2006-10-09", "2009-05-25", "2013-02-12", "2016-01-06", "2016-09-09", "2017-09-03"]);
assert.equal(extension.nuclearFacilities.length, 1);
for (const source of extension.sources) {
  const data = read("data/analysis_comparisons/" + source.capturedFile);
  assert.equal(digest(data), source.sha256);
  assert.equal(data.length, source.bytes);
}
for (const test of extension.tests) {
  assert.equal(test.country, "DPRK");
  assert.equal(test.role, "weapons");
  assert.equal(test.dateRole, "explosion_GMT_day");
  assert.equal(test.originTimeUtc.slice(0, 10), test.date);
  assert.equal(test.ordinal, Math.floor(Date.parse(test.date + "T00:00:00Z") / 86400000));
  assert.equal(test.yieldLowerKt, null);
  assert.equal(test.yieldUpperKt, null);
  assert.equal(test.uncertaintyKm, null);
  assert.equal(test.strictSpatialEligible, false);
  assert.equal(test.deployment, null, "A test deployment category is not inferred from a seismic event marker");
  const source = test.sources.find((entry) => entry.url.includes("earthquake.usgs.gov/fdsnws"));
  const capture = JSON.parse(read("data/analysis_comparisons/" + source.capturedFile));
  const event = capture.features.find((row) => row.id === test.usgsEventId);
  assert.equal(event.properties.type, "nuclear explosion");
  assert.equal(event.geometry.coordinates[0], test.lon);
  assert.equal(event.geometry.coordinates[1], test.lat);
  assert.equal(new Date(event.properties.time).toISOString(), test.originTimeUtc);
  assert.equal(event.properties.mag, test.usgsMagnitude);
  assert.equal(event.properties.place, test.region);
}
assert.match(extension.coverage.post1998Coverage, /not_comprehensive/);
assert.equal(extension.policy.missingTestsMeanNoTest, false);
const sandia = extension.nuclearFacilities[0];
assert.equal(sandia.id, "facility:1a022b4a6b36149071a0");
assert.deepEqual([sandia.lat, sandia.lon], [35.05, -106.536]);
assert.match(sandia.nuclearRole, /nonnuclear_component/);
assert.equal(sandia.nuclearRoleSourceVerified, true);
assert.equal(sandia.strictSpatialEligible, false);
assert.equal(sandia.activeIntervals[0].boundaryUncertaintyYears, 1);
assert.equal(sandia.activityEndMeaning, "source_capture_horizon_not_shutdown_year");
assert.equal(nuclear.facilityActivity(sandia, Math.floor(Date.parse("1945-07-01T00:00:00Z") / 86400000)), "unknown");
assert.equal(nuclear.facilityActivity(sandia, Math.floor(Date.parse("2000-01-01T00:00:00Z") / 86400000)), "active");
const tests = [...base.tests, ...extension.tests];
const facilities = [...base.nuclearFacilities, sandia];
const report = { id: "fixture-dprk", source: "fixture", type: "sighting", craftType: "disc_saucer",
  startOrdinal: extension.tests[5].ordinal, endOrdinal: extension.tests[5].ordinal, datePrecision: "exact_day",
  lat: extension.tests[5].lat, lon: extension.tests[5].lon, mapped: true };
const result = nuclear.computeNuclearContext({ tests, nuclearFacilities: facilities, rows: [report],
  range: { start: report.startOrdinal, end: report.startOrdinal }, ordinalEpoch: "unix_day" });
assert.equal(result.coverage.catalogRows, base.tests.length + 6);
assert.equal(result.domains.ufo.linkedReportsN, 1);
assert.equal(result.domains.ufo.phases.find((entry) => entry.id === "same_day").uniqueReports, 1);
assert.equal(result.facilities.nuclearSitesN, base.nuclearFacilities.length + 1);
assert.equal(result.readiness.strictInference, "blocked");
const fixtureDay = Math.floor(Date.parse("2000-01-01T00:00:00Z") / 86400000);
const facilityReport = nuclear.computeNuclearContext({ tests, nuclearFacilities: facilities,
  broaderFacilities: [{ ...sandia, facilityClass: "research_test" }],
  rows: [{ ...report, id: "fixture-sandia", lat: sandia.lat, lon: sandia.lon, startOrdinal: fixtureDay, endOrdinal: fixtureDay }],
  range: { start: fixtureDay, end: fixtureDay }, ordinalEpoch: "unix_day" });
assert.equal(facilityReport.facilities.broaderSitesN, 0, "Reviewed institution identity is excluded from the unreviewed broader comparator");
assert.equal(facilityReport.facilities.byDomain.ufo.groups.find((entry) => entry.id === "nuclear_only").reportsN, 1);
console.log("Nuclear extension: six primary-source event joins, original hashes, unknown yields/errors and native marker/activity checks passed.");
