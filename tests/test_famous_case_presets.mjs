import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const require = createRequire(import.meta.url);
const cases = require("../famous_case_presets.js");
const moduleSource = readFileSync(new URL("../famous_case_presets.js", import.meta.url), "utf8");

assert.ok(cases.CASES.length >= 75, "A substantial curated catalog should be available");
assert.equal(new Set(cases.CASES.map((item) => item.id)).size, cases.CASES.length);
assert.match(cases.CATALOG_NOTE, /not verified case membership/);
assert.ok(Object.isFrozen(cases));
assert.ok(Object.isFrozen(cases.CASES));

for (const item of cases.CASES) {
  assert.match(item.id, /^case_[a-z0-9_]+$/);
  assert.ok(item.name && item.location && item.description && item.dateNote);
  for (const date of [item.startIso, item.endIso]) {
    assert.match(date, /^\d{4}-\d{2}-\d{2}$/);
    assert.equal(new Date(date + "T00:00:00.000Z").toISOString().slice(0, 10), date);
  }
  assert.ok(item.startIso <= item.endIso, item.id + " has an ordered date window");
  assert.ok(["day", "range", "month", "year"].includes(item.datePrecision));
  assert.ok(item.center.length === 2);
  assert.ok(Number.isFinite(item.center[0]) && Math.abs(item.center[0]) <= 90);
  assert.ok(Number.isFinite(item.center[1]) && Math.abs(item.center[1]) <= 180);
  assert.ok(item.zoom >= 1 && item.zoom <= 18);
  assert.ok(item.radiusKm >= 25 && item.radiusKm <= 1000);
  assert.match(item.coordinateStatus, /Approximate/);
  assert.ok(item.sources.length > 0);
  for (const citation of item.sources) {
    assert.ok(citation.title && citation.kind);
    assert.equal(new URL(citation.url).protocol, "https:");
    assert.ok(Object.isFrozen(citation));
  }
  assert.ok(Object.isFrozen(item) && Object.isFrozen(item.center));
  assert.ok(Object.isFrozen(item.aliases) && Object.isFrozen(item.sources));
}

const requested = [
  ["case_kecksburg", "1965-12-09", "1965-12-09", "1965-12-08", "1965-12-10"],
  ["case_falcon_lake", "1967-05-20", "1967-05-20", "1967-05-19", "1967-05-21"],
  ["case_ariel_school", "1994-09-16", "1994-09-16", "1994-09-15", "1994-09-17"],
  ["case_betty_barney_hill", "1961-09-19", "1961-09-20", "1961-09-18", "1961-09-21"],
  ["case_kenneth_arnold", "1947-06-24", "1947-06-24", "1947-06-23", "1947-06-25"],
];
for (const [id, first, last, contextFirst, contextLast] of requested) {
  const item = cases.getCase(id);
  assert.equal(item.startIso, first);
  assert.equal(item.endIso, last);
  assert.deepEqual(cases.buildSelectionWindow(id), {
    startIso: contextFirst, endIso: contextLast, center: item.center,
    zoom: item.zoom, radiusKm: item.radiusKm, datePrecision: item.datePrecision,
  });
}

// Real case presets exercise multi-day and month/year-crossing context windows.
assert.equal(cases.buildSelectionWindow("case_valensole").startIso, "1965-06-30");
assert.equal(cases.buildSelectionWindow("case_kaikoura").endIso, "1979-01-01");
assert.equal(cases.buildSelectionWindow("case_colares").startIso, "1976-12-31");
assert.equal(cases.buildSelectionWindow("case_colares").endIso, "1978-01-01");
assert.equal(cases.buildSelectionWindow("case_colares").datePrecision, "year");
assert.equal(cases.getCase("case_colares").startIso, "1977-01-01", "Padding leaves sourced dates intact");
assert.equal(cases.getCase("case_colares").endIso, "1977-12-31");
assert.equal(cases.formatCaseDate("case_valensole"), "1965-07-01", "Labels retain the source date");

// Calendar boundaries absent from the catalog still exercise its shared date helper.
const shiftHelperSource = moduleSource.match(/  function shiftIsoDay\(iso, days\) \{[\s\S]*?\r?\n  \}/);
assert.ok(shiftHelperSource, "The private calendar helper should be available to boundary checks");
const shiftIsoDay = vm.runInNewContext("(" + shiftHelperSource[0] + ")");
assert.equal(shiftIsoDay("2000-02-28", 1), "2000-02-29");
assert.equal(shiftIsoDay("2000-02-29", 1), "2000-03-01");
assert.equal(shiftIsoDay("2000-03-01", -1), "2000-02-29");
assert.equal(shiftIsoDay("1900-03-01", -1), "1900-02-28");
assert.equal(shiftIsoDay("2026-01-01", -1), "2025-12-31");
assert.equal(shiftIsoDay("2026-04-30", 1), "2026-05-01");
assert.equal(shiftIsoDay("2026-03-08", 1), "2026-03-09", "DST changes do not affect calendar-day padding");
assert.equal(shiftIsoDay("2026-02-30", 1), null);
assert.equal(shiftIsoDay("invalid", 1), null);
assert.equal(shiftIsoDay("2026-03-01", 0.5), null);

assert.ok(cases.getCase("case_kecksburg").sources.some((citation) => citation.kind === "government records"));
assert.ok(cases.getCase("case_falcon_lake").sources.some((citation) => citation.url.includes("canada.ca")));
assert.ok(cases.getCase("case_betty_barney_hill").sources.some((citation) => citation.url.includes("unh.edu")));
assert.ok(cases.getCase("case_kenneth_arnold").sources.some((citation) => citation.url.includes("si.edu")));

assert.equal(cases.filterCases("Kecksberg")[0].id, "case_kecksburg");
assert.equal(cases.filterCases("Betty Barney 1961")[0].id, "case_betty_barney_hill");
assert.equal(cases.filterCases("Ariel Zimbabwe")[0].id, "case_ariel_school");
assert.equal(cases.filterCases("Masse Valensole")[0].id, "case_valensole");
assert.equal(cases.filterCases("Antônio Vilas-Boas")[0].id, "case_vilas_boas");
assert.equal(cases.filterCases("O'Hare")[0].id, "case_ohare");
assert.equal(cases.filterCases("O’Hare")[0].id, "case_ohare");
assert.equal(cases.filterCases("TIC TAC")[0].id, "case_nimitz");
assert.deepEqual(cases.filterCases("no-such-case-zzzz"), []);
assert.deepEqual(cases.filterCases("Kenneth Zimbabwe"), []);
const all = cases.filterCases(null);
assert.equal(all.length, cases.CASES.length);
all.pop();
assert.equal(cases.filterCases("").length, cases.CASES.length, "Filtering returns independent arrays");

assert.equal(cases.normalizeCaseOrder("chronological"), "chronological");
assert.equal(cases.normalizeCaseOrder(" CHRONOLOGICAL "), "chronological");
for (const order of [undefined, null, "", "alphabetical", "unexpected"]) {
  assert.equal(cases.normalizeCaseOrder(order), "alphabetical");
}
const catalogIdsBefore = cases.CASES.map((item) => item.id);
const chronology = cases.filterCases("", "chronological");
assert.equal(chronology[0].id, "case_nuremberg");
assert.equal(chronology.at(-1).id, "case_hangzhou");
assert.equal(chronology.length, cases.CASES.length);
assert.deepEqual(new Set(chronology.map((item) => item.id)), new Set(catalogIdsBefore));
for (let index = 1; index < chronology.length; index += 1) {
  assert.ok(chronology[index - 1].startIso <= chronology[index].startIso, "Chronology runs from oldest to newest");
}
assert.deepEqual(cases.filterCases("1952", "chronological").map((item) => item.id), [
  "case_tremonton", "case_washington", "case_nash_fortenberry", "case_flatwoods", "case_oloron",
]);
assert.deepEqual(
  new Set(cases.filterCases("1952", "alphabetical").map((item) => item.id)),
  new Set(cases.filterCases("1952", "chronological").map((item) => item.id)),
  "Order changes preserve search membership"
);
const orderingFixture = Object.freeze([
  Object.freeze({ id: "z", name: "Same", startIso: "2000-01-01" }),
  Object.freeze({ id: "a", name: "Same", startIso: "2000-01-01" }),
  Object.freeze({ id: "later", name: "Alpha", startIso: "2010-01-01" }),
  Object.freeze({ id: "early", name: "Zulu", startIso: "1990-01-01" }),
  Object.freeze({ id: "same_earlier", name: "Same", startIso: "1999-01-01" }),
  Object.freeze({ id: "other_name", name: "Beta", startIso: "2000-01-01" }),
]);
assert.deepEqual(cases.sortCases(orderingFixture, "alphabetical").map((item) => item.id), [
  "later", "other_name", "same_earlier", "a", "z", "early",
]);
assert.deepEqual(cases.sortCases(orderingFixture, "chronological").map((item) => item.id), [
  "early", "same_earlier", "other_name", "a", "z", "later",
]);
assert.deepEqual(orderingFixture.map((item) => item.id), ["z", "a", "later", "early", "same_earlier", "other_name"]);
assert.deepEqual(cases.sortCases(null, "chronological"), []);
assert.notEqual(cases.sortCases(cases.CASES), cases.CASES, "Sorting always returns a fresh array");
chronology.reverse();
assert.deepEqual(cases.CASES.map((item) => item.id), catalogIdsBefore, "Ordering never mutates the catalog");
assert.deepEqual(cases.filterCases("").map((item) => item.id), catalogIdsBefore, "Default remains alphabetical");

assert.equal(cases.formatCaseLabel("case_kecksburg"), "Kecksburg · 1965");
assert.equal(cases.formatCaseLabel("case_gulf_breeze"), "Gulf Breeze photographs · 1987–1988");
assert.equal(cases.formatCaseLabel("case_kenneth_arnold", "chronological"), "1947 · Kenneth Arnold");
assert.equal(cases.formatCaseLabel("case_gulf_breeze", "chronological"), "1987–1988 · Gulf Breeze photographs");
assert.equal(cases.formatCaseLabel(cases.getCase("case_kecksburg"), " CHRONOLOGICAL "), "1965 · Kecksburg");
assert.equal(cases.formatCaseLabel("case_kenneth_arnold", "alphabetical"), "Kenneth Arnold · 1947");
assert.equal(cases.formatCaseLabel("case_kenneth_arnold", "unexpected"), "Kenneth Arnold · 1947");
assert.equal(cases.formatCaseLabel(null, "chronological"), "");
assert.equal(cases.formatCaseDate("case_falcon_lake"), "1967-05-20");
assert.equal(cases.formatCaseDate("case_betty_barney_hill"), "1961-09-19 to 1961-09-20");
assert.equal(cases.formatCaseDate("case_colares"), "1977 (year context)");
assert.equal(cases.getCase("unknown"), null);
assert.equal(cases.buildSelectionWindow({ id: "unknown", center: [0, 0] }), null);
assert.equal(cases.formatCaseLabel(null), "");
assert.equal(cases.formatCaseDate(undefined), "");
assert.ok(Object.isFrozen(cases.buildSelectionWindow("case_nimitz")));

const browser = vm.createContext({});
vm.runInContext(moduleSource, browser);
assert.equal(browser.UfoFamousCasePresets.CASES.length, cases.CASES.length);
assert.equal(browser.UfoFamousCasePresets.getCase("case_ariel_school").startIso, "1994-09-16");
assert.equal(browser.UfoFamousCasePresets.filterCases("", "chronological")[0].id, "case_nuremberg");
assert.equal(browser.UfoFamousCasePresets.formatCaseLabel("case_kenneth_arnold", "chronological"), "1947 · Kenneth Arnold");

console.log(`famous case preset assertions passed (${cases.CASES.length} cases)`);
