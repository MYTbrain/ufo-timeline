import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const View = require("../analysis_view.js");
const Spatial = require("../analysis_spatial.js");

// Exercise the actual chart renderer, including cell inspection and lazy exact
// tables, without creating another catalog or requiring a browser dependency.
class Element {
  constructor(tagName, ownerDocument) {
    this.tagName = tagName.toUpperCase(); this.ownerDocument = ownerDocument;
    this.children = []; this.attributes = new Map(); this.events = new Map(); this.ownText = "";
    this.style = { setProperty(key, value) { this[key] = value; } };
    this.classList = { add: (...names) => { this.className = [...new Set(String(this.className || "").split(" ").filter(Boolean).concat(names))].join(" "); } };
  }
  appendChild(el) { this.children.push(el); el.parentNode = this; return el; }
  insertBefore(el, before) { const index = this.children.indexOf(before); this.children.splice(index < 0 ? this.children.length : index, 0, el); el.parentNode = this; return el; }
  removeChild(el) { const index = this.children.indexOf(el); if (index >= 0) this.children.splice(index, 1); el.parentNode = null; return el; }
  replaceChildren(...els) { this.children.forEach(el => { el.parentNode = null; }); this.children = []; this.ownText = ""; els.forEach(el => this.appendChild(el)); }
  set textContent(value) { this.replaceChildren(); this.ownText = String(value); }
  get textContent() { return this.ownText + this.children.map(child => child.textContent).join(" "); }
  get firstChild() { return this.children[0] || null; }
  setAttribute(key, value) { this.attributes.set(key, String(value)); }
  getAttribute(key) { return this.attributes.get(key) ?? null; }
  addEventListener(key, fn) { if (!this.events.has(key)) this.events.set(key, []); this.events.get(key).push(fn); }
  emit(type) { (this.events.get(type) || []).forEach(fn => fn({ type, target: this, preventDefault() {} })); }
}
const walk = el => [el, ...el.children.flatMap(walk)];
const hasClass = (el, name) => String(el.className || "").split(" ").includes(name);
const tree = new Map();
const document = { createElement(tag) { return new Element(tag, this); }, getElementById(id) { return tree.get(id) || null; } };
for (const id of ["animal", "crop", "animal-card", "crop-card", "all-species"]) tree.set(id, document.createElement("div"));
const controller = Object.create(View.AnalysisViewController.prototype);
controller.document = document;
const inspections = [];
controller.showPreview = value => { inspections.push(value); };

const activeRows = [], neighbors = [];
for (let i = 0; i < 5; i += 1) {
  activeRows.push({ eventId: String(i) });
  const row = { contextDomainCode: "animal", contextLaneCode: "animal_public_marker", contextId: "animal-" + i,
    contextClusterId: "cluster-" + i, contextOrdinal: 730486, ufoEventId: String(i), distanceDecameters: 100,
    dayLag: 0, distanceRingCode: "0_25_km", dayLagBandCode: "same_day", uncertaintyClassCode: "public_marker_ambiguous",
    ufoCraftCode: "triangle", featureGroupCode: i < 4 ? "bovine" : "equine", independentAssociationEligible: true };
  neighbors.push({ ...row, dateRoleCode: "observed_reported_date" }, { ...row, dateRoleCode: "matched_control_minus_1y" });
}
neighbors.push({ ...neighbors[0], contextId: "control-only-bird", contextClusterId: "bird-cluster", featureGroupCode: "avian", dateRoleCode: "matched_control_plus_1y" });
const association = Spatial.computeContextAssociations({ activeRows, neighbors, permutationCount: 0, bootstrapCount: 0 });
const animalLane = association.lanes.find(lane => lane.lane === "animal_public_marker");
assert.ok(animalLane.featureAssociation.pooledFeatureGroups.includes("bovine"), "The fixture reproduces cattle hidden by the existing small-sample pool");
assert.ok(animalLane.featureAssociation.axes.columns.includes("avian"), "Control-only birds demonstrate why the pooled display was misleading");
const before = JSON.stringify(association);
controller._renderContextCategoryAssociations("animal", "animal-card", association, {}, { allowedLanes: ["animal_public_marker"] });
assert.equal(JSON.stringify(association), before, "Display wrappers must not mutate pooled estimates, complete values or source counts");
const animal = tree.get("animal");
const headers = root => walk(root).filter(el => el.tagName === "TH" && el.getAttribute("data-axis-key")).map(el => el.getAttribute("data-axis-key"));
assert.ok(headers(animal).includes("bovine"));
assert.ok(headers(animal).includes("equine"));
assert.ok(headers(animal).includes("avian"), "A species with no observed clusters but positive matched-date counts remains inspectable");
assert.ok(!headers(animal).includes("other_sparse_species"));
assert.match(animal.textContent, /Craft by animal species/);
assert.doesNotMatch(animal.textContent, /Craft by pooled animal species/);
assert.match(animal.textContent, /Species stay separate, including small samples/);
assert.match(animal.textContent, /No cells qualify for inference/);
const marks = walk(animal).filter(el => hasClass(el, "analysis-heat-cell") && el.tagName === "BUTTON");
assert.equal(marks.length, 3);
assert.ok(marks.every(el => hasClass(el, "is-low-support")));
const cattle = marks.find(el => /Cattle/.test(el.getAttribute("aria-label")));
assert.match(cattle.getAttribute("aria-label"), /O 4.*E 1.*descriptive estimate.*Limited sample/);
cattle.emit("click");
assert.equal(inspections.at(-1).cohortSize, 4);
assert.match(inspections.at(-1).comparison, /Observed n=4.*matched-date expected average=1/);
assert.ok(inspections.at(-1).criteria.some(item => item.label === "Count unit" && /location\/date clusters/.test(item.value)));
assert.ok(!inspections.at(-1).criteria.some(item => /p-value|q-value/.test(item.label)));
const controlOnly = marks.find(el => /Birds/.test(el.getAttribute("aria-label")));
assert.match(controlOnly.getAttribute("aria-label"), /O 0.*E 0\.25.*descriptive estimate/);
controlOnly.emit("click");
assert.match(inspections.at(-1).comparison, /Observed n=0.*matched-date expected average=0\.25/);
const details = walk(animal).filter(el => el.tagName === "DETAILS");
assert.equal(details.length, 2, "Both the chart evidence table and original complete unpooled table remain accessible");
details[1].open = true; details[1].emit("toggle");
assert.match(details[1].textContent, /Cattle.*4.*1/);
assert.equal(JSON.stringify(association), before);

// Every named taxonomy column fits without raising the 12-row/global limit or
// dropping cattle merely because another species has a larger effect.
const species = ["avian", "bovine", "camelid", "canid", "caprine", "cervid", "equine", "felid", "fish", "lagomorph", "marine_mammal", "other_mammal", "ovine", "porcine", "unknown"];
const many = { lanes: [{ lane: "animal_public_marker", featureAssociation: {
  poolingThreshold: 25, cells: [{ row: "triangle", column: "other_sparse_species", observedClusterCount: 50, expectedClusterCount: 1, log2Enrichment: 5 }],
  completeAccessibleTable: { cells: species.map((column, i) => ({ row: "triangle", column,
    observedClusterCount: column === "bovine" ? 1 : i + 2, expectedClusterCount: 1, log2Enrichment: column === "bovine" ? .01 : i + 1,
    p_value: .001, q_value: .002, inferenceEligible: true, patternFinderEligible: true })) },
} }] };
const originalMany = JSON.stringify(many);
const observedDisplay = [];
const render = controller._renderHeatmap;
controller._renderHeatmap = function (id, values, summary, config) { observedDisplay.push({ values, config }); return render.call(this, id, values, summary, config); };
controller._renderContextCategoryAssociations("all-species", "animal-card", many, {}, { allowedLanes: ["animal_public_marker"] });
const allSpecies = tree.get("all-species"), display = observedDisplay.at(-1);
assert.equal(headers(allSpecies).length, species.length + 1, "All 15 named species plus the craft row are present");
assert.ok(headers(allSpecies).includes("bovine"));
assert.equal(display.config.columnAxisLimit, 16);
assert.ok(display.values.every(cell => cell.inferenceEligible === false && cell.patternFinderEligible === false && cell.pValue === null && cell.p_value === null && cell.qValue === null && cell.q_value === null));
assert.ok(display.values.every(cell => cell.estimateAvailable && cell.evidenceStatus === "sensitivity_only"));
assert.equal(JSON.stringify(many), originalMany);
assert.equal(View.HEATMAP_AXIS_LIMIT, 12);
assert.equal(headers(allSpecies).filter(key => species.includes(key)).at(-1), "unknown");
const wide = structuredClone(many);
wide.lanes[0].featureAssociation.completeAccessibleTable.cells = Array.from({ length: 16 }, (_, row) => species.map((column, i) => ({ row: "craft-" + row, column,
  observedClusterCount: 1, expectedClusterCount: .25, log2Enrichment: i + 1 }))).flat();
controller._renderContextCategoryAssociations("all-species", "animal-card", wide, {}, { allowedLanes: ["animal_public_marker"] });
assert.match(tree.get("all-species").textContent, /12 of 16 highest-information rows.*at most 192 cells/);

const crop = { lanes: [{ lane: "crop_bounded", featureAssociation: {
  poolingThreshold: 25,
  cells: [{ row: "triangle", column: "other_sparse_morphology", observedCount: 30, expectedCount: 12, log2Enrichment: 1.25, estimateAvailable: true, inferenceEligible: true }],
  completeAccessibleTable: { cells: [{ row: "triangle", column: "circular", observedCount: 30, expectedCount: 12, log2Enrichment: 1.25 }] },
} }] };
const cropBefore = JSON.stringify(crop);
controller._renderContextCategoryAssociations("crop", "crop-card", crop, {}, { allowedLanes: ["crop_bounded"] });
const cropDisplay = observedDisplay.at(-1);
assert.equal(cropDisplay.values, crop.lanes[0].featureAssociation.cells, "Crop pooling inputs remain unchanged");
assert.ok(headers(tree.get("crop")).includes("other_sparse_morphology"));
assert.ok(!headers(tree.get("crop")).includes("circular"));
assert.match(tree.get("crop").textContent, /Sparse context features are pooled below N=25/);
assert.equal(cropDisplay.config.columnAxisLimit, undefined);
assert.equal(cropDisplay.config.expectedCountFormatter, undefined, "Fractional expected formatting stays scoped to the animal species view");
assert.equal(JSON.stringify(crop), cropBefore);
console.log("Animal species display regression checks passed.");
