import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";

const require = createRequire(import.meta.url);
const cases = require("../famous_case_presets.js");
const source = readFileSync(new URL("../app.js", import.meta.url), "utf8");
function extract(name) {
  const start = source.indexOf(`function ${name}(`);
  assert.ok(start >= 0);
  const brace = source.indexOf("{", start);
  let depth = 0;
  for (let end = brace; end < source.length; end++) {
    if (source[end] === "{") depth++;
    if (source[end] === "}") depth--;
    if (!depth) return source.slice(start, end + 1);
  }
  assert.fail(name);
}
const cash = cases.getCase("case_cash_landrum");
assert.ok(cash.catalogRefs.length >= 6);
const cashMappedRef = cash.catalogRefs.find(ref => ref.eventId === "4435047138615330");
assert.ok(cashMappedRef, "The original reviewed Cash source reference is retained");
const auditedCaseIds = new Set(["a", "b", "c"].flatMap(group => {
  const audit = JSON.parse(readFileSync(new URL(`../docs/releases/famous-case-identity-audit/group-${group}.json`, import.meta.url), "utf8"));
  return audit.cases.map(review => review.caseId);
}));
assert.equal(auditedCaseIds.size, 85, "The original completed identity review retains its historical scope");
for (const caseId of auditedCaseIds) {
  const preset = cases.getCase(caseId);
  assert.ok(preset, `The originally reviewed preset ${caseId} is retained`);
  assert.ok(Object.isFrozen(preset.catalogReview), "Every original audited case retains its completed identity review");
  assert.ok(["matched", "no_confirmed_match"].includes(preset.catalogReview.status));
  assert.equal(preset.catalogReview.status === "matched", preset.catalogRefs.length > 0);
  assert.ok(Object.isFrozen(preset.catalogRefs));
  assert.equal(new Set(preset.catalogRefs.map(ref => ref.eventId)).size, preset.catalogRefs.length);
  for (const ref of preset.catalogRefs) {
    assert.ok(Object.isFrozen(ref));
    assert.ok(Number.isSafeInteger(Number(ref.eventId)));
    assert.ok(ref.identityEvidence && ref.sourceRef);
  }
}
const dalnegorsk = cases.getCase("case_dalnegorsk");
assert.ok(dalnegorsk && !auditedCaseIds.has(dalnegorsk.id));
assert.equal(dalnegorsk.catalogReview, null, "Dalnegorsk is a newly sourced historical preset, not an asserted completed database identity review");
assert.deepEqual(dalnegorsk.catalogRefs, [], "No identity crosswalk is invented for the new case");
assert.ok(Object.isFrozen(dalnegorsk.catalogRefs));
assert.deepEqual(cases.CASES.filter(preset => !auditedCaseIds.has(preset.id)).map(preset => preset.id), ["case_dalnegorsk"]);
const records = new Map(cash.catalogRefs.map(ref => [ref.eventId, {
  event_id: Number(ref.eventId), source: ref.source, sort_date_iso: ref.dateIso,
  has_coordinates: ref.mappingStatus !== "unmapped", lat: ref.reviewedLat, lon: ref.reviewedLon,
}]));
let opened;
const context = vm.createContext({
  FAMOUS_CASES: cases, state: { famousCaseId: cash.id }, runtime: {}, console,
  getCatalogEventById: id => records.get(String(id)), formatNumber: String,
  escapeHtml: value => String(value),
  openFullEventView: async (id, options) => { opened = { id, options }; },
  clearFamousCasePreset() {}, fitFamousCaseTraces() {},
});
vm.runInContext(["famousCaseCatalogEntries", "renderFamousCaseCatalogEntries", "bindFamousCaseActions"].map(extract).join("\n"), context);
assert.equal(context.famousCaseCatalogEntries(cash).filter(row => row.mappingIssue).length,
  cash.catalogRefs.filter(ref => ref.mappingStatus !== "mapped").length);
assert.ok(context.renderFamousCaseCatalogEntries(cash).includes(`${cash.catalogRefs.length} matched database records · mapping issues`));
assert.match(context.renderFamousCaseCatalogEntries(cash), /not separate incidents/);
const handlers = {};
context.bindFamousCaseActions({ addEventListener: (name, handler) => { handlers[name] = handler; } });
const targetFor = id => ({ closest: selector => selector === "[data-inspect-famous-case-record]"
  ? { getAttribute: () => id } : null });
handlers.click({ target: targetFor(cashMappedRef.eventId) });
assert.equal(opened.id, Number(cashMappedRef.eventId));
assert.equal(opened.options.centerMap, false, "inspecting a misplaced record must not pan the map to it");
assert.equal(opened.options.openPopup, false);
opened = undefined;
handlers.click({ target: targetFor("12345") });
assert.equal(opened, undefined, "only a reviewed active-case reference can be opened through this action");
records.get(cashMappedRef.eventId).lat = 30.03;
assert.equal(context.famousCaseCatalogEntries(cash).find(row => row.reference.eventId === cashMappedRef.eventId).mappingIssue, false, "old mapping notes do not override a future coordinate change");
records.get(cashMappedRef.eventId).source = "different-source";
assert.equal(context.famousCaseCatalogEntries(cash).find(row => row.reference.eventId === cashMappedRef.eventId).event, null, "identity drift fails closed");
assert.match(context.renderFamousCaseCatalogEntries(cash), /disabled/);
assert.ok(cases.getCase("case_mariana").catalogRefs.length > 0, "Nonempty vicinities also receive actual source identity review");
assert.match(context.renderFamousCaseCatalogEntries({ startIso: "2020-01-01", endIso: "2020-01-01", catalogRefs: [], catalogReview: { status: "no_confirmed_match" } }), /no confirmed case record/);
assert.match(context.renderFamousCaseCatalogEntries(dalnegorsk), /database identity not yet checked/);
const dateConflict = { ...cash, startIso: "1981-01-01", endIso: "1981-01-01" };
assert.match(context.renderFamousCaseCatalogEntries(dateConflict), /source dates differ from the preset/);
assert.match(context.renderFamousCaseCatalogEntries(dateConflict), /1980-12-29.*outside reported dates/);
console.log("Famous case catalog reference checks passed");
