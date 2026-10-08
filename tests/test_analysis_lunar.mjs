import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const Lunar = require("../analysis_lunar.js");
const day = value => Math.floor(Date.parse(value + "T00:00:00Z") / 86400000);
const row = (date, extra = {}) => ({ sortOrdinal: day(date), datePrecision: "exact_day", craftType: "disc", ...extra });
const nearly = (actual, expected, tolerance) => assert.ok(Math.abs(actual - expected) <= tolerance, actual + " vs " + expected);

// Independent frozen JPL Horizons DE441 geocentric Moon illumination values,
// retrieved 2026-10-07. API requests use COMMAND='301', CENTER='500@399',
// QUANTITIES='10', TLIST in Julian days, CSV_FORMAT='YES'.
// https://ssd-api.jpl.nasa.gov/doc/horizons.html
for (const fixture of [
  ["2024-04-24T00:00:00Z", 99.97818],
  ["2024-03-16T00:00:00Z", 37.88335],
  ["2000-01-21T00:00:00Z", 99.94164],
]) nearly(Lunar.phaseAtUtc(Date.parse(fixture[0])).illumination * 100, fixture[1], 0.01);
assert.equal(Lunar.phaseForDay(day("2024-04-08")).phaseId, "new");
assert.equal(Lunar.phaseForDay(day("2024-04-24")).phaseId, "full");
assert.equal(Lunar.phaseForDay(null), null, "Missing date must not turn into 1970");
assert.equal(Lunar.phaseForDay(false), null);
assert.equal(Lunar.phaseForDay(day("1500-01-01")), null, "Historical calendar must not be silently promoted");
assert.equal(Lunar.phaseForDay(day("1970-01-01")).ordinal, 0, "Actual Unix epoch is supported");
assert.equal(Lunar.phaseForDay(day("2024-04-08") + 719163, "python_day").phaseId, "new");
assert.throws(() => Lunar.phaseForDay(1, "guessed"), /ordinalEpoch/);

const skyRecord = { utcTimestamp: "2024-04-08T18:00:00Z", utcTimestampVerified: true,
  timeZoneProvenance: "Frozen JPL fixture: explicitly UTC", lat: 36, lon: -80, coordinateEvidenceClass: "source_exact" };
// Independent JPL topocentric AIRLESS azimuth/elevation at SITE_COORD=-80,36,0,
// COMMAND='301', CENTER='coord@399', TLIST='2460409.25', QUANTITIES='4,10'.
const sky = Lunar.moonSkyPosition(skyRecord);
assert.equal(sky.eligible, true);
nearly(sky.azimuth, 200.186848, 0.02);
nearly(sky.elevation, 59.891401, 0.02);
assert.equal(sky.aboveHorizon, true);
assert.equal(Lunar.moonSkyPosition({ ...skyRecord, utcTimestampVerified: false }).eligible, false);
assert.equal(Lunar.moonSkyPosition({ ...skyRecord, timeZoneProvenance: null }).reason, "missing_timezone_provenance");
assert.equal(Lunar.moonSkyPosition({ ...skyRecord, utcTimestamp: "2024-04-08T18:00:00" }).reason, "timestamp_requires_explicit_offset");
assert.equal(Lunar.moonSkyPosition({ ...skyRecord, utcTimestamp: "2024-02-30T18:00:00Z" }).reason, "invalid_utc_timestamp");
assert.equal(Lunar.moonSkyPosition({ ...skyRecord, coordinateEvidenceClass: "locality_centroid" }).eligible, false);
assert.equal(Lunar.moonSkyPosition({ ...skyRecord, uncertaintyKm: 100 }).eligible, false);
assert.equal(Lunar.moonSkyPosition({ sourceTime: "18:00", lat: 36, lon: -80, datePrecision: "exact_day" }).eligible, false,
  "A source clock is not verified UTC");

const monthRows = Array.from({ length: 30 }, (_, index) => row("2024-04-01", { sortOrdinal: day("2024-04-01") + index }));
const completeMonth = Lunar.computeLunarContext({ rows: monthRows });
const ufo = completeMonth.domains[0];
assert.equal(ufo.phaseEligible, 30);
assert.equal(ufo.exposure.calendarDays, 30);
for (const bin of ufo.phaseBins) nearly(bin.calendarAdjustedRatio, 1, 1e-6);
assert.ok(ufo.phaseBins.some(bin => Math.abs(bin.expectedCalendarShare - 0.125) > 0.005),
  "Opportunity must come from actual calendar exposure, not equal eighths");
assert.ok(ufo.ambiguousPhaseCount > 0);
assert.equal(ufo.stablePhaseCount + ufo.ambiguousPhaseCount, ufo.phaseEligible);
assert.equal(ufo.phaseBins.reduce((sum, bin) => sum + bin.count, 0), 30);
assert.equal(ufo.phaseBins.reduce((sum, bin) => sum + bin.stableCount, 0), ufo.stablePhaseCount);
for (const bin of ufo.phaseBins) assert.ok(bin.lowerCount <= bin.count && bin.count <= bin.upperCount);
assert.equal(ufo.sky.eligible, 0, "All date-only observations must stay out of sky-position inference");
assert.equal(completeMonth.inferenceEligible, false);
assert.equal(completeMonth.patternFinderEligible, false);

const mutable = {};
const fixture = Lunar.computeLunarContext({
  forEachRow(accept) {
    for (const value of [row("2024-04-08"), row("2024-04-24", { craftType: "triangle" })]) {
      for (const key of Object.keys(mutable)) delete mutable[key];
      Object.assign(mutable, value); accept(mutable);
    }
  },
  crops: [ { startOrdinal: day("2024-04-08"), endOrdinal: day("2024-04-08"), datePrecision: "exact_day", dateRole: "discovery", category: "radial" },
    { startOrdinal: day("2024-04-01"), endOrdinal: day("2024-04-30"), datePrecision: "month" },
    { startOrdinal: null, datePrecision: "unknown" } ],
  animals: [ { startOrdinal: day("2024-04-24"), endOrdinal: day("2024-04-24"), datePrecision: "exact_day", dateRole: "report_date", category: "bovine" } ],
});
assert.equal(fixture.domains[0].phaseEligible, 2, "The transient worker row must not be retained");
assert.equal(fixture.domains[0].phaseByCategory.length, 2);
assert.equal(fixture.domains[1].dateRoles.discovery, 1);
assert.equal(fixture.domains[1].dateRoles.catalog_or_discovery_date_not_verified_formation, 2);
assert.equal(fixture.domains[1].phaseEligible, 1);
assert.equal(fixture.domains[1].excluded.date_not_exact_day, 1);
assert.equal(fixture.domains[1].excluded.missing_date, 1);
assert.equal(fixture.domains[2].dateRoles.report_date, 1);
assert.equal(fixture.domains[2].phaseBins[4].count, 1);

const clipped = Lunar.computeLunarContext({ rows: monthRows, range: { start: day("2024-04-08"), end: day("2024-04-08") } });
assert.equal(clipped.domains[0].total, 1);
assert.equal(clipped.domains[0].outsideRange, 29);
assert.equal(clipped.domains[0].exposure.calendarDays, 1);
assert.equal(clipped.domains[0].phaseBins[0].expectedCalendarShare, 1);
const python = Lunar.computeLunarContext({ ordinalEpoch: "python_day", rows: [row("2024-04-08", { sortOrdinal: day("2024-04-08") + 719163 })],
  contextOrdinalEpoch: "unix_day", crops: [ { startOrdinal: day("2024-04-08"), endOrdinal: day("2024-04-08"), datePrecision: "exact_day" } ] });
assert.equal(python.domains[0].phaseBins[0].count, 1);
assert.equal(python.domains[1].phaseBins[0].count, 1);
const mixedCatalog = Lunar.computeLunarContext({ rows: [row("2024-04-08", { type: "Unknown" }),
  row("2024-04-08", { type: "Nuclear / atomic event" }),
  row("2024-04-08", { visualTypeGroup: "Military / government / intelligence / aerospace" }),
  row("2024-04-08", { craftType: "non_ufo_context", type: "Unknown", visualTypeGroup: "Other / unknown" }),
  row("2024-04-08", { isUfoReport: false }), row("2024-04-08", { isContext: true })] });
assert.equal(mixedCatalog.domains[0].total, 6);
assert.equal(mixedCatalog.domains[0].reportCount, 1);
assert.equal(mixedCatalog.domains[0].phaseEligible, 1);
assert.equal(mixedCatalog.domains[0].nonReportContextCount, 5);
assert.equal(mixedCatalog.domains[0].excluded.non_ufo_context, 5);
assert.ok(!mixedCatalog.domains[0].phaseByCategory.some(value => value.category === "non_ufo_context"));

// Verify browser/worker UMD loading, independently of Node's require path.
const browser = vm.createContext({ console, Date, Math, Number, Object, Array, Map, Set });
browser.self = browser;
vm.runInContext(fs.readFileSync(new URL("../analysis_astronomy_engine.js", import.meta.url), "utf8"), browser);
vm.runInContext(fs.readFileSync(new URL("../analysis_lunar.js", import.meta.url), "utf8"), browser);
assert.equal(browser.UfoAnalysisLunar.phaseForDay(day("2024-04-08")).phaseId, "new");
console.log("Lunar comparisons passed: independent JPL illumination/sky references, calendar opportunity, uncertain days, timestamp gating, source-date roles, iterator and UMD runtime.");
