import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const View = require("../analysis_view.js");

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
for (const id of ["species-time", "craft-time", "country-time"]) tree.set(id, document.createElement("div"));
const controller = Object.create(View.AnalysisViewController.prototype);
controller.document = document;
controller.resultRenderVersion = 3;
controller.currentAnalysisMode = "comparative";


const source = {
  yearly: { rows: ["unknown", "bovine", "equine"], columns: ["unknown", ...Array.from({ length: 40 }, (_, i) => String(1940 + i))],
    cells: Array.from({ length: 40 }, (_, i) => ({ row: "bovine", column: String(1940 + i), observedCount: i === 0 ? 4 : 1, referenceCount: i === 0 ? 9 : 0, inferenceEligible: false }))
      .concat([{ row: "equine", column: "1941", observedCount: 2, referenceCount: 3, inferenceEligible: false }, { row: "unknown", column: "unknown", observedCount: 1, referenceCount: 2, inferenceEligible: false }]),
    metadata: { activeTimedReportCount: 45, activeUnknownDateCount: 1, activeAmbiguousPeriodCount: 2,
      referenceTimedReportCount: 12, referenceUnknownDateCount: 2, referenceAmbiguousPeriodCount: 3, activeUnknownLabelCount: 1, referenceUnknownLabelCount: 2 } },
  decadal: { rows: ["bovine", "equine", "unknown"], columns: ["1970", "1940", "unknown"],
    cells: [{ row: "bovine", column: "1940", observedCount: 12, referenceCount: 9, inferenceEligible: false },
      { row: "equine", column: "1970", observedCount: 2, referenceCount: 3, inferenceEligible: false },
      { row: "unknown", column: "unknown", observedCount: 1, referenceCount: 2, inferenceEligible: false }],
    metadata: { activeTimedReportCount: 14, activeUnknownDateCount: 1, activeAmbiguousPeriodCount: 0,
      referenceTimedReportCount: 12, referenceUnknownDateCount: 2, referenceAmbiguousPeriodCount: 1, activeUnknownLabelCount: 1, referenceUnknownLabelCount: 2 } }
};
const unchanged = JSON.stringify(source);
const root = tree.get("species-time");
const labels = node => walk(node).filter(el => el.tagName === "TH" && el.getAttribute("data-axis-key")).map(el => el.getAttribute("data-axis-key"));
const marks = node => walk(node).filter(el => hasClass(el, "analysis-heat-cell"));
const button = (node, label) => walk(node).find(el => el.tagName === "BUTTON" && el.ownText === label);
const select = node => walk(node).find(el => el.tagName === "SELECT");
controller._renderAnimalTemporalChart("species-time", source, {}, { kind: "species" });
assert.match(root.textContent, /Selected reports · descriptive counts only/);
assert.match(root.textContent, /Cattle/);
assert.match(root.textContent, /1940s.*1970s.*Unknown date/);
assert.match(root.textContent, /report counts, not counts of individual animals/);
assert.match(root.textContent, /0 cross-period date ranges excluded/);
const countingNotes = walk(root).find(el => hasClass(el, "analysis-supporting-details"));
assert.ok(countingNotes && !countingNotes.open, "Counting policies are collapsed by default");
assert.equal(countingNotes.children[0].textContent, "Counting & coverage notes");
assert.ok(root.children.some(el => el.tagName === "P" && hasClass(el, "analysis-chart-note") && /14 reports in dated periods/.test(el.textContent)), "A concise plain coverage line stays visible");
assert.ok(marks(root).every(el => !hasClass(el, "is-low-support")), "Raw counts must not look like unsupported residual estimates");
assert.ok(marks(root).every(el => el.tagName !== "BUTTON"), "Descriptive counts do not pretend to expose an unavailable record drilldown");
assert.ok(!/inferentially qualified|above expectation|p-value|q-value/i.test(root.textContent));
assert.equal(button(root, "Decade").getAttribute("aria-pressed"), "true");
select(root).value = "reference"; select(root).emit("change");
assert.match(root.textContent, /Reference reports · descriptive counts only/);
assert.match(root.textContent, /1 cross-period date ranges excluded/);
assert.match(marks(root).find(el => /Cattle, 1940s/.test(el.getAttribute("aria-label"))).getAttribute("aria-label"), /: 9; reports/);
button(root, "Year").emit("click");
const periodLabels = labels(root).filter(label => !["bovine", "equine", "unknown"].includes(label));
assert.equal(periodLabels.length, 40, "All chronological periods remain available beyond the generic 32-column cap");
assert.deepEqual(periodLabels, Array.from({ length: 40 }, (_, i) => String(1940 + i)));
assert.match(root.textContent, /3 cross-period date ranges excluded/);
const table = walk(root).find(el => el.tagName === "DETAILS");
table.open = true; table.emit("toggle");
assert.match(table.textContent, /Cattle.*1940.*9/);
assert.match(table.textContent, /Animal reports/);
assert.equal(JSON.stringify(source), unchanged);
// Preferences survive a fresh render and cannot be activated by stale controls.
const staleYear = button(root, "Year");
controller._renderAnimalTemporalChart("species-time", source, {}, { kind: "species" });
assert.equal(button(root, "Year").getAttribute("aria-pressed"), "true");
controller.resultRenderVersion += 1;
staleYear.emit("click");
assert.equal(button(root, "Year").getAttribute("aria-pressed"), "true");
controller.currentAnalysisMode = "whole_corpus_structure";
controller._renderAnimalTemporalChart("species-time", source, {}, { kind: "species" });
assert.equal(select(root), undefined);
assert.match(root.textContent, /All matched reports · descriptive counts only/);
assert.match(marks(root).find(el => /Cattle, 1940/.test(el.getAttribute("aria-label"))).getAttribute("aria-label"), /: 4; reports/);

const craft = { yearly: { cells: [{ row: "disc_saucer", column: "1950", observedCount: 2, referenceCount: null, inferenceEligible: false }], rows: ["disc_saucer"], columns: ["1950"], metadata: { activeTimedReportCount: 1, activeUnknownDateCount: 0, activeAmbiguousPeriodCount: 0 } } };
craft.decadal = { ...craft.yearly, cells: [{ ...craft.yearly.cells[0], column: "1950" }] };
controller.currentAnalysisMode = "comparative";
controller._renderAnimalTemporalChart("craft-time", craft, {}, { kind: "craft" });
const craftRoot = tree.get("craft-time");
assert.equal(select(craftRoot), undefined, "No reference picker exists for observed-neighborhood craft counts");
assert.match(craftRoot.textContent, /Disc \/ saucer/);
assert.match(craftRoot.textContent, /2 clusters/);
assert.match(craftRoot.textContent, /animal marker's date.*matched-date controls are excluded/);
assert.match(craftRoot.textContent, /not evidence of the same incident or a causal connection/);
const craftTable = walk(craftRoot).find(el => el.tagName === "DETAILS");
craftTable.open = true; craftTable.emit("toggle");
assert.match(craftTable.textContent, /Animal-report clusters/);

const countries = Array.from({ length: 14 }, (_, i) => i === 13 ? "unknown" : "Country " + i);
const location = { yearly: { cells: countries.map((row, i) => ({ row, column: "1980", observedCount: 14 - i, referenceCount: 0, inferenceEligible: false })), rows: countries, columns: ["1980"], metadata: { activeTimedReportCount: 105, activeUnknownDateCount: 0, activeAmbiguousPeriodCount: 0, activeUnknownLabelCount: 1 } } };
location.decadal = location.yearly;
controller._renderAnimalTemporalChart("country-time", location, {}, { kind: "locations" });
const locationRoot = tree.get("country-time");
assert.ok(labels(locationRoot).includes("unknown"), "Unknown country stays visible with more than 12 country rows");
assert.ok(labels(locationRoot).includes("Country 12"));
assert.match(locationRoot.textContent, /map centroids are not used to guess a country/);
const countryTable = walk(locationRoot).find(el => el.tagName === "DETAILS");
countryTable.open = true; countryTable.emit("toggle");
assert.match(countryTable.textContent, /Unknown country/);
assert.match(countryTable.textContent, /Country 12/);
assert.match(countryTable.textContent, /14 rows/);
const expanded = Array.from({ length: 40 }, (_, i) => ({ row: i === 39 ? "unknown" : i === 0 ? "US" : i === 1 ? "GB" : "Country " + i, column: "1980", observedCount: 40 - i, referenceCount: 0, inferenceEligible: false }));
const expandedLocations = { yearly: { ...location.yearly, rows: expanded.map(cell => cell.row), cells: expanded } };
expandedLocations.decadal = expandedLocations.yearly;
controller._renderAnimalTemporalChart("country-time", expandedLocations, {}, { kind: "locations" });
assert.ok(labels(locationRoot).includes("unknown"), "Unknown country remains visible even beyond the 32-row limit");
assert.match(locationRoot.textContent, /United States/);
assert.match(locationRoot.textContent, /United Kingdom/);
assert.match(locationRoot.textContent, /largest country rows and Unknown country/);
// Empty period matrices retain denominator and exclusion disclosures rather than
// implying that a cohort containing only cross-period dates has no reports.
const ambiguousPeriod = { cells: [], rows: [], columns: [], metadata: { activeReportCount: 2,
  activeTimedReportCount: 0, activeUnknownDateCount: 0, activeAmbiguousPeriodCount: 2,
  referenceReportCount: 3, referenceTimedReportCount: 0, referenceUnknownDateCount: 0, referenceAmbiguousPeriodCount: 3 } };
controller._renderAnimalTemporalChart("species-time", { yearly: ambiguousPeriod, decadal: ambiguousPeriod }, {}, { kind: "species" });
assert.match(root.textContent, /No records can be assigned to this period view/);
assert.match(root.textContent, /2 cross-period date ranges excluded/);
assert.ok(root.children.some(el => el.tagName === "P" && /2 cross-period date ranges excluded/.test(el.textContent)), "Empty-period exclusions remain visible outside the collapsed notes");
assert.match(root.textContent, /not counts of individual animals/);
assert.ok(select(root), "Reference selection stays available when all selected and reference dates cross a period boundary");
select(root).value = "reference"; select(root).emit("change");
assert.match(root.textContent, /3 cross-period date ranges excluded/);
assert.doesNotMatch(root.textContent, /No animal-report timing records are available/);
const invalidCraftDates = { cells: [], rows: [], columns: [], metadata: { activeReportCount: 3,
  activeTimedReportCount: 0, activeUnknownDateCount: 3, activeAmbiguousPeriodCount: 0, referenceReportCount: null } };
controller._renderAnimalTemporalChart("craft-time", { yearly: invalidCraftDates, decadal: invalidCraftDates }, {}, { kind: "craft" });
assert.match(craftRoot.textContent, /No records can be assigned to this period view/);
assert.match(craftRoot.textContent, /3 with unknown dates/);
assert.match(craftRoot.textContent, /Unknown-date clusters are excluded/);
assert.match(craftRoot.textContent, /not evidence of the same incident or a causal connection/);
assert.equal(select(craftRoot), undefined);
console.log("Animal temporal renderer: chronological count heatmaps, cattle labels, reference/unknowns, cluster units and complete tables passed.");

