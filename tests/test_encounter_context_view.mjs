import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { renderEncounterContext } = require("../analysis_comparisons_view.js");
const engine = require("../analysis_encounter_context.js");
const encounter = require("../encounter_evidence.js");
const { AnalysisViewController } = require("../analysis_view.js");

const walk = (node) => [node, ...node.children.flatMap(walk)];
class Element {
  constructor(tagName, document) {
    this.tagName = tagName; this.ownerDocument = document; this.children = []; this.attributes = new Map();
    this.events = new Map(); this.style = {}; this.ownText = ""; this.value = "";
  }
  appendChild(node) { this.children.push(node); node.parentNode = this; return node; }
  replaceChildren(...nodes) { this.children = []; this.ownText = ""; nodes.forEach((node) => this.appendChild(node)); }
  setAttribute(key, value) { this.attributes.set(key, String(value)); }
  getAttribute(key) { return this.attributes.get(key) ?? null; }
  set textContent(value) { this.ownText = String(value); this.children = []; }
  get textContent() { return this.ownText + this.children.map((node) => node.textContent).join(" "); }
  addEventListener(name, callback) { if (!this.events.has(name)) this.events.set(name, []); this.events.get(name).push(callback); }
  dispatch(name, extra = {}) { for (const callback of this.events.get(name) || []) callback({ target: this, preventDefault() {}, ...extra }); }
  click() { if (this.tagName === "a") this.ownerDocument.lastDownload = this; this.dispatch("click"); }
  focus() { this.ownerDocument.activeElement = this; this.dispatch("focus"); }
  querySelectorAll(selector) {
    return walk(this).slice(1).filter((node) => selector === "button" ? node.tagName === "button"
      : selector.startsWith(".") ? (node.className || "").split(" ").includes(selector.slice(1))
        : selector.startsWith("#") ? node.id === selector.slice(1) : node.tagName === selector);
  }
}
function fixture() {
  const document = {
    targets: [], createElement(tag) { return new Element(tag, this); },
    getElementById(id) { return this.targets.flatMap(walk).find((node) => node.id === id) || null; },
    defaultView: { Blob, URL: {
      createObjectURL(blob) { document.exportedBlob = blob; return "blob:encounter-context"; },
      revokeObjectURL(url) { document.revokedUrl = url; },
    }, setTimeout(callback) { callback(); } },
  };
  const target = document.createElement("div"); target.id = "analysis-encounter-context-chart"; document.targets.push(target);
  return { document, target };
}
const byText = (target, tag, text) => walk(target).find((node) => node.tagName === tag && node.textContent === text);
const picker = (target, label) => walk(target).find((node) => node.tagName === "select" && node.getAttribute("aria-label") === label);
const change = (target, label, value) => { const node = picker(target, label); assert.ok(node, "Missing selector: " + label); node.value = value; node.dispatch("change"); };
const exactTable = (target, caption) => walk(target).find((node) => node.tagName === "table" && node.children.some((child) => child.tagName === "caption" && child.textContent === caption));
const tableRows = (node) => { assert.ok(node, "Missing exact-value table"); return walk(node).filter((child) => child.tagName === "tr").map((row) => row.children.map((cell) => cell.textContent)); };
const cells = (target) => walk(target).filter((node) => node.className?.includes("comparison-heatmap-cell") && node.tagName === "button");
const day = Date.parse("2000-07-01T00:00:00Z") / 86400000;
const row = (id, offset, keys, abduction, lat = 0, lon = 0, more = {}) => ({ id, eventId: id,
  startOrdinal: offset == null ? null : day + offset, endOrdinal: offset == null ? null : day + offset,
  datePrecision: "exact_day", source: "independent_ufo", craftType: "disc_saucer", lat, lon,
  encounterBeingMask: encounter.beingMask(keys), encounterAbductionCode: abduction, encounterEvidenceReady: true, ...more });
const reports = [row("1", 0, ["grey", "small_humanoid"], 1), row("2", 0, ["grey"], 2, null, null),
  row("3", 10, ["nordic"], 0, 40, 40), row("4", 0, ["reptilian"], 3, 0, 0, { datePrecision: "month", endOrdinal: day + 30 }),
  row("5", null, ["humanoid"], 0)];
const marker = { id: "crop", startOrdinal: day, endOrdinal: day, datePrecision: "exact_day", dateRole: "discovery_date",
  lat: 0, lon: 0, sourceFamilyIds: ["independent_context"] };
const options = { rows: reports, range: { start: day - 30, end: day + 31 }, ordinalEpoch: "unix_day", encounterEvidenceReady: true,
  crops: [marker], animals: [{ ...marker, id: "animal", dateRole: "report_date" }],
  nuclear: { tests: [{ id: "test", ordinal: day, lat: 0, lon: 0, role: "weapons" }], nuclearFacilities: [
    { id: "facility", lat: 0, lon: 0, nuclearRoleSourceVerified: true, activeIntervals: [[1900, 2100]] }],
    coverage: { firstDate: "2000-07-01", lastDate: "2000-07-01", countries: { fixture: 1 } } },
  artifactHashes: { encounters: "a".repeat(64), independentContext: "b".repeat(64) } };
const model = engine.computeEncounterContext(options);
const planetary = engine.computeEncounterPlanetary({ ...options, artifactHashes: { savedEphemeris: "c".repeat(64) },
  planetarySettings: { zodiacSystem: "sidereal", ayanamsaId: "lahiri", aspectOrbDegrees: 3 } });
const complete = { status: "ready", encounters: model, encounterPlanetary: planetary, artifactHashes: options.artifactHashes };
const before = JSON.stringify(complete);
const requests = [];
const { document, target } = fixture();
const hooks = { onComparisonSettingsChange: (settings) => requests.push(settings) };
renderEncounterContext(target, complete, hooks);
assert.equal(picker(target, "Encounter context comparison").value, "lunar");
assert.equal(picker(target, "Encounter population").value, "being");
assert.equal(cells(target).length, 19 * 8);
assert.ok(target.textContent.includes("row uses its own eligible-report denominator"));
const lunarExact = tableRows(exactTable(target, "Encounter category × Moon phase exact values"));
assert.equal(lunarExact[0].length, 9);
assert.equal(lunarExact.length, 19 * 8 + 1);
const grey = model.lunar.matrix.rows.find((item) => item.id === "grey");
const zeroColumn = grey.cells.findIndex((item) => item.count === 0 && item.share === 0);
assert.ok(zeroColumn >= 0);
assert.equal(document.getElementById("encounter-context-cell-0-" + zeroColumn).textContent, "0.0%", "A supported zero is not unavailable");
change(target, "Encounter heatmap value", "count");
assert.equal(document.getElementById("encounter-context-cell-0-" + zeroColumn).textContent, "0");
assert.equal(document.getElementById("encounter-context-cell-2-0").textContent, "—", "Zero eligible reports must remain unavailable");
change(target, "Encounter heatmap value", "calendarAdjustedRatio");
assert.ok(cells(target).some((cell) => cell.textContent === "—"), "Unavailable calendar ratios remain unavailable");
change(target, "Encounter heatmap value", "share");

// Arrow navigation and population changes must retain one tabbable grid cell.
document.getElementById("encounter-context-cell-0-0").focus();
document.getElementById("encounter-context-cell-0-0").dispatch("keydown", { key: "ArrowRight" });
assert.equal(document.activeElement.id, "encounter-context-cell-0-1");
assert.equal(document.activeElement.tabIndex, 0, "Arrow-selected cell must become the roving tab stop");
assert.equal(cells(target).filter((cell) => cell.tabIndex === 0).length, 1);
document.getElementById("encounter-context-cell-18-7").focus();
change(target, "Encounter population", "abduction");
assert.equal(cells(target).length, 4 * 8);
assert.equal(cells(target).filter((cell) => cell.tabIndex === 0).length, 1, "A smaller population must not inherit a nonexistent focus cell");
assert.match(target.textContent, /Source-classified abduction|Narrative-reported abduction/);

change(target, "Encounter context comparison", "nuclear");
assert.equal(picker(target, "Encounter nuclear axis").value, "phases");
assert.equal(tableRows(exactTable(target, "Encounter category × Recorded dates around nuclear tests exact values")).length, 4 * model.nuclear.phases.columns.length + 1);
change(target, "Encounter nuclear date window", "7");
assert.deepEqual(requests.at(-1), { encounterContext: true, windowDays: 7 });
change(target, "Encounter nuclear axis", "facilities");
assert.ok(exactTable(target, "Encounter category × Reviewed nuclear & broader facility markers exact values"));
change(target, "Encounter nuclear axis", "distances");
assert.ok(exactTable(target, "Encounter category × Distances to nuclear-test markers exact values"));
change(target, "Encounter population", "being");
change(target, "Encounter context comparison", "crops");
assert.equal(picker(target, "Encounter context lane").value, "calendar");
assert.ok(exactTable(target, "Encounter category × crop-circle reports exact values"));
assert.match(target.textContent, /worldwide|not local co-occurrence/);
change(target, "Encounter context lane", "marker");
assert.match(target.textContent, /public markers|Public-marker/);
change(target, "Encounter context comparison", "animals");
assert.ok(exactTable(target, "Encounter category × animal reports exact values"));
assert.match(target.textContent, /not assumed formation or death times/);

change(target, "Encounter context comparison", "planetary");
assert.equal(walk(picker(target, "Encounter body or pair")).filter((node) => node.tagName === "option").length, 9);
assert.equal(picker(target, "Encounter zodiac convention").value, "sidereal");
change(target, "Encounter planetary axis", "motion");
assert.equal(walk(picker(target, "Encounter body or pair")).filter((node) => node.tagName === "option").length, 9);
change(target, "Encounter planetary axis", "aspects");
assert.equal(walk(picker(target, "Encounter body or pair")).filter((node) => node.tagName === "option").length, 36);
change(target, "Encounter zodiac convention", "tropical");
assert.deepEqual(requests.at(-1), { encounterContext: true, encounterPlanetaryOnly: true, zodiacSystem: "tropical", ayanamsaId: "lahiri" });
change(target, "Encounter aspect orb", "5");
assert.deepEqual(requests.at(-1), { encounterContext: true, encounterPlanetaryOnly: true, aspectOrbDegrees: 5 });
assert.match(target.textContent, /Houses remain unavailable/);
byText(target, "button", "Download encounter context evidence").click();
assert.equal(document.lastDownload.download, "encounter-context-evidence.json");
const downloaded = JSON.parse(await document.exportedBlob.text());
assert.deepEqual(downloaded.encounters.artifactHashes, options.artifactHashes);
assert.deepEqual(downloaded.encounterPlanetary.artifactHashes, { savedEphemeris: "c".repeat(64) });
assert.equal(downloaded.encounterPlanetary.matrices.aspects[Object.keys(planetary.matrices.aspects)[0]].rows.length, 23);
assert.equal(JSON.stringify(complete), before, "Render and interactions must not mutate measured result data");

const deferredFixture = fixture();
renderEncounterContext(deferredFixture.target, { status: "ready", encounters: model }, hooks);
change(deferredFixture.target, "Encounter context comparison", "planetary");
byText(deferredFixture.target, "button", "Load encounter planetary heatmaps").click();
assert.deepEqual(requests.at(-1), { encounterContext: true, encounterPlanetaryOnly: true });

const disabled = engine.computeEncounterContext({ ...options, cropCirclesEnabled: false });
const disabledFixture = fixture();
renderEncounterContext(disabledFixture.target, { status: "ready", encounters: disabled }, hooks);
change(disabledFixture.target, "Encounter context comparison", "crops");
assert.ok(cells(disabledFixture.target).every((cell) => cell.textContent === "—"), "Disabled context must not plot false zeros");
assert.match(disabledFixture.target.textContent, /context layer is disabled/);
const unavailableFixture = fixture();
renderEncounterContext(unavailableFixture.target, { status: "ready", encounters: { status: "unavailable_encounter_evidence" } }, hooks);
assert.match(unavailableFixture.target.textContent, /cannot be classified/);
assert.equal(cells(unavailableFixture.target).length, 0);

// Verify the actual native controller forwards its shared settings callbacks
// to the actual context renderer, not just a test-only direct invocation.
const bridgeFixture = fixture();
const bridgeChanges = [];
const controller = Object.create(AnalysisViewController.prototype);
Object.assign(controller, { document: bridgeFixture.document, callbacks: { onComparisonSettingsChange: (value) => bridgeChanges.push(value) } });
globalThis.UfoAnalysisComparisonsView = { renderEncounterContext };
controller._renderEncounterContextEvidence(complete);
change(bridgeFixture.target, "Encounter context comparison", "planetary");
change(bridgeFixture.target, "Encounter zodiac convention", "tropical");
assert.deepEqual(bridgeChanges.at(-1), { encounterContext: true, encounterPlanetaryOnly: true, zodiacSystem: "tropical", ayanamsaId: "lahiri" });
let retries = 0;
controller.callbacks.onComparisonRetry = () => { retries += 1; };
controller._renderEncounterContextEvidence({ status: "error", message: "Fixture evidence request failed" });
assert.match(bridgeFixture.target.textContent, /Fixture evidence request failed/);
byText(bridgeFixture.target, "button", "Retry loading").click();
assert.equal(retries, 1, "The actual controller retry hook must reach the context renderer");
delete globalThis.UfoAnalysisComparisonsView;
console.log("Actual encounter context UI topics, populations, null/zero counts, exact tables/exports, settings bridge and keyboard navigation tests passed.");
