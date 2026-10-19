import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url), Catalog = require("../search_catalog.js"), Query = require("../search_query.js");
const records = [
  { event_id: 0, location_display: "Harare", description: "A soil sample was examined", has_coordinates: false },
  { event_id: "001", location_display: "Lyon", mapping_notes: "Corrected location from local source", description: "A humanoid stood nearby" },
  { event_id: "2", references: ["Author Éloïse", "UFO catalogue"], description: "水と植物 were reported" },
  { event_id: "3", extra_data: { corrected: "Harare", material: "soil sample" } },
  { event_id: "4", description: "Soil was reported. A sample was not mentioned." },
  { event_id: "001", location_raw: "Lyon" },
  { event_id: null, id: "invented", description: "Harare soil sample humanoid" },
];
const plan = Query.compile('"soil sample" AND Harare'), progress = [];
const leaves = await Catalog.supplementalMatches(plan, records, { yieldEvery: 2, onProgress: value => progress.push(value) });
assert.deepEqual(Object.keys(leaves), ["soil sample", "harare"]);
assert.deepEqual(leaves["soil sample"], ["0", "3"], "phrases remain exact; separated words cannot make a phrase");
assert.deepEqual(leaves.harare, ["0", "3"]);
assert.equal(Object.getPrototypeOf(leaves), null, "arbitrary query terms cannot read object prototype values");
assert.deepEqual(progress.map(value => value.completedReports), [0, 2, 4, 6, 7]);
assert.ok(progress.every(value => value.totalReports === records.length));
const split = Query.compile('humanoid AND Harare'), splitLeaves = await Catalog.supplementalMatches(split, records);
assert.deepEqual(splitLeaves.humanoid, ["001"]); assert.deepEqual(splitLeaves.harare, ["0", "3"]);
// The raw-index side supplies humanoid for event 0; metadata supplies its newly
// corrected place. The engine must union per leaf before intersecting the AND.
const rawLeaves = { humanoid: ["0"], harare: [] };
const union = term => new Set([...rawLeaves[term], ...splitLeaves[term]]);
const humanoid = union("humanoid"), harare = union("harare");
assert.deepEqual([...humanoid].filter(id => harare.has(id)), ["0"]);
assert.equal(Query.matchEvent(split, records[0]), false, "whole-metadata matching alone would have lost this valid split-source match");

const unicode = await Catalog.supplementalMatches(Query.compile('ÉLOÏSE OR 植物'), records);
assert.deepEqual(unicode["éloïse"], ["2"]); assert.deepEqual(unicode["植物"], ["2"]);
const unchanged = records[1].mapping_notes;
let current = await Catalog.supplementalMatches(Query.compile("corrected location"), records);
assert.deepEqual(current["corrected location"], ["001"]);
records[1].mapping_notes = "Updated metadata";
current = await Catalog.supplementalMatches(Query.compile("corrected location"), records);
assert.deepEqual(current["corrected location"], [], "new requests use current corrected metadata rather than a serialized text cache");
records[1].mapping_notes = unchanged;
const duplicate = await Catalog.supplementalMatches(Query.compile("Lyon"), records);
assert.deepEqual(duplicate.lyon, ["001"], "duplicate report IDs do not duplicate per-leaf hits");
const reserved = await Catalog.supplementalMatches(Query.compile("__proto__"), [{ event_id: "1", description: "__proto__" }]);
assert.deepEqual(reserved.__proto__, ["1"]);
const thirtyTwo = Query.compile(Array.from({ length: 32 }, (_, index) => '"term' + index + 'x"').join(" OR "));
const many = await Catalog.supplementalMatches(thirtyTwo, [
  { event_id: 0, description: thirtyTwo.terms.join(" ") }, { event_id: 0, description: thirtyTwo.terms.join(" ") },
]);
assert.equal(Object.keys(many).length, 32);
assert.ok(Object.values(many).every(ids => ids.length === 1 && ids[0] === "0"), "32nd-term bit is correctly deduplicated");
const empty = await Catalog.supplementalMatches(Query.compile(""), records);
assert.deepEqual(Object.keys(empty), []);

assert.deepEqual(Catalog.filteredIds(new Set([0, "001", 2, "2", "not-here"]), [
  records[2], records[0], records[1], records[1], { event_id: "5", has_coordinates: true },
]), ["2", "0", "001"], "scope intersection keeps current catalog order, unmapped reports, exact IDs, and unique strings");
assert.deepEqual(Catalog.filteredIds(["1"], [{ event_id: "001" }, { event_id: 0 }]), [], "IDs are not loosely coerced");
assert.deepEqual(Catalog.filteredIds(["x"], [{ id: "x" }]), [], "generic record IDs are not invented canonical IDs");
assert.deepEqual(Catalog.filteredIds(["x"], [{ eventId: "x", has_coordinates: false }]), ["x"]);
assert.deepEqual(Catalog.filteredIds(null, records), []);
assert.deepEqual(Catalog.filteredIds(["0"], null), []);

const already = new AbortController(); already.abort();
await assert.rejects(Catalog.supplementalMatches(plan, records, { signal: already.signal }), error => error.name === "AbortError");
const middle = new AbortController(), cancelledProgress = [];
await assert.rejects(Catalog.supplementalMatches(plan, records, { signal: middle.signal, yieldEvery: 1, onProgress(value) {
  cancelledProgress.push(value.completedReports); if (value.completedReports === 2) middle.abort();
} }), error => error.name === "AbortError");
assert.deepEqual(cancelledProgress, [0, 1, 2], "cancellation stops progress immediately without reporting unscanned rows");
let isCurrent = true;
await assert.rejects(Catalog.supplementalMatches(plan, records, { yieldEvery: 1, isCurrent: () => isCurrent,
  onProgress(value) { if (value.completedReports === 1) isCurrent = false; } }), error => error.name === "AbortError");
let pageYielded = false;
setTimeout(() => { pageYielded = true; }, 0);
await Catalog.supplementalMatches(Query.compile("Lyon"), records, { yieldEvery: 1 });
assert.equal(pageYielded, true, "catalog scanning yields so the page can process input");
console.log("Search catalog: exact metadata leaves, split-source AND, live corrections, canonical IDs, Unicode, cancellation, and page yielding passed.");
