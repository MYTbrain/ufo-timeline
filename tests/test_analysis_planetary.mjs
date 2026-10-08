import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const Planetary = require("../analysis_planetary.js");
const Astronomy = require("../analysis_astronomy_engine.js");
const day = value => Math.floor(Date.parse(value + "T00:00:00Z") / 86400000);
const row = (date, extra = {}) => ({ sortOrdinal: day(date), datePrecision: "exact_day", craftType: "disc", ...extra });
const near = (actual, expected, tolerance) => assert.ok(Math.abs(actual - expected) <= tolerance, actual + " vs " + expected);
const references = JSON.parse(fs.readFileSync(new URL("../data/analysis_comparisons/planetary_reference_fixtures.json", import.meta.url)));

// Independent JPL apparent geocentric true-ecliptic-of-date fixtures; a
// heliocentric helper or mean/J2000 frame fails these numerical comparisons.
for (const fixture of references.horizons) {
  for (const record of fixture.rows) {
    // Pluto's pinned ephemeris is numerically checked, but a full date-only
    // comparison is not offered because its bounded query exceeds the budget.
    const longitude = fixture.body === "Pluto" ? Astronomy.Ecliptic(Astronomy.GeoVector(Astronomy.Body.Pluto, new Date(record.utc), true)).elon
      : Planetary.positionAtUtc(fixture.body, record.utc).tropicalLongitudeDegrees;
    assert.ok(Planetary.angularDistance(longitude, record.longitudeDeg) < 0.002,
      fixture.id + " at " + record.utc + ": frame/light-time/aberration mismatch");
  }
}
for (const fixture of references.ayanamsa.filter(record => record.ayanamsaType === "true")) {
  const timestamp = (fixture.utJulianDay - 2440587.5) * 86400000;
  near(Planetary.ayanamsaDegreesAtUtc(timestamp, fixture.mode), fixture.ayanamsaDeg, 0.00007);
}
const tropicalIngress = Planetary.positionForDay(day("2024-03-20"), { planet: "Sun", zodiacSystem: "tropical" });
assert.deepEqual(tropicalIngress.possibleSignIndexes, [0, 11], "Wrap through the equinox must retain Pisces and Aries");
assert.equal(tropicalIngress.stableSign, false);
const siderealIngress = Planetary.positionForDay(day("2024-04-13"), { planet: "Sun" });
assert.equal(siderealIngress.signId, "pisces");
assert.deepEqual(siderealIngress.possibleSignIndexes, [0, 11], "Independent Lahiri ingress crosses the date-only UTC interval");
assert.equal(Planetary.positionForDay(day("2024-04-14"), { planet: "Sun" }).signId, "aries");
const station = Planetary.positionForDay(day("2024-04-01"), { planet: "Mercury" });
assert.ok(station.possibleMotionIndexes.includes(0) && station.possibleMotionIndexes.includes(1), "Endpoints cannot hide a Mercury direction reversal");
assert.equal(station.stableMotion, false);
assert.ok(station.sampleCount > 3, "Station dates require interval refinement");
const retrograde = Planetary.positionForDay(day("2024-04-15"), { planet: "Mercury" });
assert.equal(retrograde.motionId, "retrograde");
assert.equal(retrograde.stableMotion, true);
assert.equal((retrograde.utcIntervalMs[1] - retrograde.utcIntervalMs[0]) / 3600000, 50);
assert.equal(Planetary.positionForDay(null), null);
assert.equal(Planetary.positionForDay(false), null);
assert.equal(Planetary.positionForDay(day("1500-01-01")), null);
assert.equal(Planetary.positionForDay(day("1970-01-01")).ordinal, 0);
assert.equal(Planetary.positionForDay(day("2024-04-15") + 719163, { planet: "Mercury", ordinalEpoch: "python_day" }).motionId, "retrograde");
assert.throws(() => Planetary.positionForDay(1, { ordinalEpoch: "guessed" }), /ordinalEpoch/);
assert.throws(() => Planetary.computePlanetaryContext({ planet: "Pluto" }), /Unsupported/);
assert.throws(() => Planetary.computePlanetaryContext({ aspectPartner: "Venus" }), /differ/);
assert.throws(() => Planetary.computePlanetaryContext({ aspectOrbDegrees: 100 }), /orb/);

const completeMonth = Array.from({ length: 30 }, (_, index) => row("2024-04-01", { sortOrdinal: day("2024-04-01") + index }));
const defaultContext = Planetary.computePlanetaryContext({ rows: [row("2024-04-08")] });
assert.equal(defaultContext.aspectPartner, "Mars");
assert.equal(Planetary.computePlanetaryContext({ planet: "Mars", rows: [row("2024-04-08")] }).aspectPartner, "Moon");
const full = Planetary.computePlanetaryContext({ rows: completeMonth, aspectPartner: "Moon" });
const domain = full.domains[0];
assert.equal(full.zodiacSystem, "sidereal");
assert.equal(full.ayanamsaId, "lahiri");
assert.equal(full.aspectPartner, "Moon");
assert.equal(domain.positionEligible, 30);
assert.equal(domain.exposure.calendarDays, 30);
assert.equal(domain.signBins.reduce((sum, bin) => sum + bin.count, 0), 30);
assert.equal(domain.stableSignCount + domain.ambiguousSignCount, 30);
assert.equal(domain.motion.stableCount + domain.motion.ambiguousCount, 30);
assert.equal(domain.motion.bins.reduce((sum, bin) => sum + bin.count, 0), 30);
assert.ok(domain.signBins.some(bin => Math.abs(bin.expectedCalendarShare - 1 / 12) > 0.2), "Actual unequal calendar opportunity must replace uniform zodiac expectations");
for (const bin of [...domain.signBins, ...domain.motion.bins, ...domain.aspectPartners[0].bins, domain.aspectPartners[0].outsideBand]) {
  if (bin.expectedCount > 0) near(bin.calendarAdjustedRatio, 1, 0.0001);
  assert.ok(bin.lowerCount <= bin.count && bin.count <= bin.upperCount);
  assert.equal(bin.boundStatus, "sampled_stability_not_formal_confidence_interval");
}
assert.ok(domain.aspectPartners[0].bins.some(bin => bin.id === "trine" && bin.count > 0));
assert.equal(domain.aspectPartners[0].bins.reduce((sum, bin) => sum + bin.count, 0) + domain.aspectPartners[0].outsideBand.count, 30);
assert.ok(domain.aspectPartners[0].variableAspectReports > 0);
assert.equal(domain.distinctEligibleDates, 30);
for (const entry of domain.aspectByCategory[0].rows) for (const bin of entry.bins.concat([entry.outsideBand])) if (bin.expectedCount > 0) near(bin.calendarAdjustedRatio, 1, 0.0001);
assert.equal(domain.houses.eligible, 0);
assert.equal(full.houses.calculated, false);
assert.equal(full.inferenceEligible, false);
assert.equal(full.patternFinderEligible, false);
const tropical = Planetary.computePlanetaryContext({ rows: completeMonth, zodiacSystem: "tropical", aspectPartner: "Moon" });
assert.notDeepEqual(tropical.domains[0].signBins.map(bin => bin.count), domain.signBins.map(bin => bin.count), "Changing the origin should change zodiac sectors");
assert.deepEqual(tropical.domains[0].aspectPartners[0].bins.map(bin => bin.count), domain.aspectPartners[0].bins.map(bin => bin.count), "Ayanamsa shifts cancel out of pairwise aspect separations");
assert.deepEqual(tropical.domains[0].motion.bins.map(bin => bin.count), domain.motion.bins.map(bin => bin.count), "Motion has an explicitly fixed apparent tropical frame");

const mixed = {};
const context = Planetary.computePlanetaryContext({
  forEachRow(accept) {
    for (const value of [row("2024-04-08"), row("2024-04-24", { craftType: "triangle" }), row("2024-04-08", { craftType: "non_ufo_context" }),
      row("2024-04-08", { isContext: true }), row("2024-04-08", { type: "Nuclear / atomic event" }), row("2024-04-08", { datePrecision: "month" })]) {
      for (const key of Object.keys(mixed)) delete mixed[key];
      Object.assign(mixed, value); accept(mixed);
    }
  },
  crops: [ { startOrdinal: day("2024-04-08"), endOrdinal: day("2024-04-08"), datePrecision: "exact_day", dateRole: "discovery", category: "radial" },
    { startOrdinal: day("2024-04-01"), endOrdinal: day("2024-04-30"), datePrecision: "month" }, { startOrdinal: null } ],
  animals: [ { startOrdinal: day("2024-04-24"), endOrdinal: day("2024-04-24"), datePrecision: "exact_day", dateRole: "publication_date", category: "bovine" } ],
});
assert.equal(context.domains[0].nonReportContextCount, 3);
assert.equal(context.domains[0].positionEligible, 2);
assert.equal(context.domains[0].signByCategory.length, 2, "Mutable iterator input must not be retained");
assert.equal(context.domains[1].positionEligible, 1);
assert.equal(context.domains[1].dateRoles.discovery, 1);
assert.equal(context.domains[1].excluded.date_not_exact_day, 1);
assert.equal(context.domains[1].excluded.missing_or_invalid_date, 1);
assert.equal(context.domains[2].dateRoles.publication_date, 1);
const clipped = Planetary.computePlanetaryContext({ rows: completeMonth, range: { start: day("2024-04-10"), end: day("2024-04-13") } });
assert.equal(clipped.domains[0].positionEligible, 4);
assert.equal(clipped.domains[0].outsideRange, 26);
assert.equal(clipped.domains[0].exposure.calendarDays, 4);
near(clipped.domains[0].signBins.reduce((sum, bin) => sum + bin.expectedCount, 0), 4, 0.0001);

const verified = row("2024-04-13", { utcTimestamp: "2024-04-13T12:00:00Z", utcTimestampVerified: true, timeZoneProvenance: "Independent UTC fixture", lat: 36, lon: -80, coordinateEvidenceClass: "source_exact" });
const timestampGate = Planetary.computePlanetaryContext({ planet: "Sun", rows: [verified, { ...verified, utcTimestampVerified: false },
  { ...verified, timeZoneProvenance: null }, { ...verified, utcTimestamp: "2024-04-13T12:00:00" }, { ...verified, utcTimestamp: "2024-02-30T12:00:00Z" } ] });
assert.equal(timestampGate.domains[0].verifiedTimeCount, 1);
assert.equal(timestampGate.domains[0].stableSignCount, 1, "Source clock strings do not become verified UTC positions");
assert.equal(timestampGate.domains[0].houses.eligibleInputs, 1);
assert.equal(timestampGate.domains[0].houses.eligible, 0, "Verified inputs must not pretend an unimplemented house calculation exists");

// Category-specific opportunity must retain its own month distribution.
const categoryMonths = Planetary.computePlanetaryContext({ planet: "Saturn", rows: [...Array.from({ length: 31 }, (_, index) => row("2024-01-01", { sortOrdinal: day("2024-01-01") + index, craftType: "disc" })),
  ...Array.from({ length: 31 }, (_, index) => row("1990-01-01", { sortOrdinal: day("1990-01-01") + index, craftType: "triangle" }))] });
for (const entry of categoryMonths.domains[0].signByCategory) for (const bin of entry.bins) if (bin.expectedCount > 0) near(bin.calendarAdjustedRatio, 1, 0.0001);
assert.ok(categoryMonths.domains[0].exposure.variableSignReports < categoryMonths.domains[0].positionEligible, "Slow-planet months with no sign change need a visible readiness limitation");

// In a worker the pinned Astronomy object lives on self.
const workerSandbox = { self: { Astronomy }, Date };
vm.runInNewContext(fs.readFileSync(new URL("../analysis_planetary.js", import.meta.url), "utf8"), workerSandbox);
assert.equal(workerSandbox.self.UfoAnalysisPlanetary.computePlanetaryContext({ rows: [row("2024-04-08")] }).domains[0].positionEligible, 1);

// Folding keeps every original denominator/source/date-role gate while avoiding
// a corpus scan whenever a physical body or zodiac convention changes.
const foldOptions = { rows: [row("2024-04-08", { source: "a" }), row("2024-04-08", { source: "b" }), row("2024-04-24", { craftType: "triangle" }),
  row("2024-04-13", { ...verified, utcTimestamp: "2024-04-13T12:34:00Z" }), row("2024-04-08", { isContext: true }), row("2024-04-08", { datePrecision: "month" })],
  crops: [{ startOrdinal: day("2024-04-08"), endOrdinal: day("2024-04-08"), datePrecision: "exact_day", dateRole: "discovery_date", category: "radial" }],
  animals: [{ startOrdinal: day("2024-04-24"), endOrdinal: day("2024-04-24"), datePrecision: "exact_day", dateRole: "publication_date", category: "bovine" }] };
const prepared = Planetary.preparePlanetaryCohort(foldOptions);
assert.ok(prepared.foldedGroupN < prepared.inputRows);
for (const planet of ["Mercury", "Venus", "Moon", "Saturn"]) {
  const direct = Planetary.computePlanetaryContext({ ...foldOptions, planet });
  const folded = Planetary.computePlanetaryContext({ preparedCohort: prepared, planet });
  assert.deepEqual(folded.domains, direct.domains, "Prepared cohort must preserve all categories/roles/source and eligibility totals");
}
const atlasDates = Array.from({ length: 33 }, (_, index) => day("2024-03-31") + index);
const fixtureAtlas = Planetary.buildEphemerisAtlasBuffer(atlasDates);
assert.equal(fixtureAtlas.metadata.dateCount % 2, 1, "Odd day index exercises Float64 block alignment");
const decoded = Planetary.decodeEphemerisAtlas(fixtureAtlas.buffer, fixtureAtlas.metadata);
assert.equal(decoded.dates.length, 33);
assert.throws(() => Planetary.decodeEphemerisAtlas(fixtureAtlas.buffer, { ...fixtureAtlas.metadata, byteLength: fixtureAtlas.metadata.byteLength + 1 }), /byte length/);
assert.throws(() => Planetary.decodeEphemerisAtlas(fixtureAtlas.buffer, { ...fixtureAtlas.metadata, utcHours: [0] }), /order/);
const badHeader = fixtureAtlas.buffer.slice(0);
new DataView(badHeader).setUint32(36, 65, true);
assert.throws(() => Planetary.decodeEphemerisAtlas(badHeader, fixtureAtlas.metadata), /dimensions/);
const invalidValue = fixtureAtlas.buffer.slice(0), invalidView = new DataView(invalidValue);
invalidView.setFloat64(invalidView.getUint32(36, true), NaN, true);
assert.throws(() => Planetary.decodeEphemerisAtlas(invalidValue, fixtureAtlas.metadata), /physical/);
for (const planet of Planetary.PLANETS) {
  Planetary.clearEphemerisAtlas();
  const direct = Planetary.computePlanetaryContext({ preparedCohort: prepared, planet });
  Planetary.setEphemerisAtlas(decoded);
  const cached = Planetary.computePlanetaryContext({ preparedCohort: prepared, planet });
  assert.deepEqual(cached.domains, direct.domains, "Atlas must preserve nine-body classifications and calendar controls: " + planet);
  assert.equal(cached.precomputation.status, "precomputed_raw_ephemeris");
  assert.ok(cached.precomputation.atlasHits > 0);
  assert.ok(cached.precomputation.directEphemerisCalls > 0, "The verified fixture's arbitrary UTC timestamp explicitly falls back");
}
const noClock = Planetary.preparePlanetaryCohort({ rows: completeMonth });
Planetary.setEphemerisAtlas(decoded);
const allPrecomputed = Planetary.computePlanetaryContext({ preparedCohort: noClock });
assert.equal(allPrecomputed.precomputation.directEphemerisCalls, 0, "Covered date-only states use the atlas without ephemeris computation");
assert.equal(allPrecomputed.precomputation.precessionFallbackCalls, 0);
const uncovered = Planetary.computePlanetaryContext({ rows: [row("1990-01-01")] });
assert.ok(uncovered.precomputation.directEphemerisCalls > 0, "Outside atlas coverage remains an explicit original-method fallback");
Planetary.clearEphemerisAtlas();
console.log("Planetary comparisons: primary-reference geometry, sidereal origin, stations, civil bounds, roles, exposure, UTC gates and worker loading passed.");
