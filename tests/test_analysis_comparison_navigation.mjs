import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const Model = require("../analysis_session.js");
const View = require("../analysis_session_view.js");

// The two windows deliberately have equal sizes: stale caches must not make
// the 1989 group inherit the contents or distributions of the 1973 group.
const ordinal = iso => Date.parse(iso + "T00:00:00Z") / 86400000;
const rows = [
  { eventId: "1973-disc", sortOrdinal: ordinal("1973-10-11"), source: "ufocat", type: "Disk", craftType: "disc_saucer", country: "United States", adminRegion: "Ohio", lat: 40, lon: -83, mapped: true, precision: "city", datePrecision: "exact_day", craftConfidence: "high" },
  { eventId: "1973-unknown", sortOrdinal: ordinal("1973-10-12"), source: "ufocat", type: "Unknown", craftType: "unknown", country: "unknown", adminRegion: "unknown", mapped: false, precision: "unknown", datePrecision: "exact_day", craftConfidence: "none" },
  { eventId: "1989-triangle", sortOrdinal: ordinal("1989-11-29"), source: "nuforc", type: "Triangle", craftType: "triangle", country: "Belgium", adminRegion: "Liege", lat: 50.6, lon: 5.6, mapped: true, precision: "city", datePrecision: "exact_day", craftConfidence: "medium" },
  { eventId: "1989-orb", sortOrdinal: ordinal("1989-12-01"), source: "nuforc", type: "Sphere", craftType: "sphere_orb", country: "Belgium", adminRegion: "Brussels", lat: 50.8, lon: 4.3, mapped: true, precision: "city", datePrecision: "exact_day", craftConfidence: "high" },
  { eventId: "undated", sortOrdinal: null, source: "fixture", type: "Unknown", craftType: "unknown", mapped: false, precision: "unknown", datePrecision: "unknown", country: "unknown" },
];
const messages = [], workerSelf = { postMessage(message) { messages.push(message); } };
const workerContext = vm.createContext({ self: workerSelf, console });
for (const file of ["analysis_stats.js", "catalog_filter_worker.js"]) vm.runInContext(fs.readFileSync(file, "utf8"), workerContext);
const send = message => { messages.length = 0; workerSelf.onmessage({ data: message }); assert.equal(messages.length, 1); assert.notEqual(messages[0].type, "catalogFacetWorkerError", messages[0].error); return messages[0]; };
send({ type: "addCatalogFacetRows", rows });
const filters = { sourceMode: "all", typeMode: "all", precisionMode: "all" };
function capture(startIso, endIso) {
  const result = send({ type: "captureAnalysisSession", timeRangeMode: "window", fullTimeRange: false,
    timeRangeStartOrdinal: ordinal(startIso), timeRangeEndOrdinal: ordinal(endIso), filters }).result;
  return { ...JSON.parse(JSON.stringify(result)), label: "Current Analysis reports", scope: { timeRange: { mode: "window", startIso, endIso } } };
}
const a = capture("1973-08-01", "1974-01-31"), b = capture("1989-11-01", "1990-04-30");
assert.deepEqual([...a.eventIds], ["1973-disc", "1973-unknown"]);
assert.deepEqual([...b.eventIds], ["1989-triangle", "1989-orb"]);
const compare = Model.compareGroups(a, b);
assert.equal(compare.overlapCount, 0);
const category = (domain, key) => compare.distributions[domain]?.rows.find(row => row.key === key);
assert.deepEqual([category("craft", "disc_saucer").aCount, category("craft", "disc_saucer").bCount], [1, 0]);
assert.deepEqual([category("craft", "triangle").aCount, category("craft", "triangle").bCount], [0, 1]);
assert.deepEqual([category("year", "1973").aCount, category("year", "1973").bCount], [2, 0]);
assert.deepEqual([category("year", "1989").aCount, category("year", "1989").bCount], [0, 2]);
assert.deepEqual([category("country", "Belgium").aCount, category("country", "Belgium").bCount], [0, 2]);
assert.deepEqual([compare.distributions.country.unknown.aCount, compare.distributions.country.unknown.bCount], [1, 0]);
assert.equal(compare.distributions.being.a.available, false, "An unloaded encounter index is unavailable, not a zero count");
assert.equal(compare.distributions.duration.a.available, false, "An unloaded duration projection is unavailable, not a zero count");

// Minimal DOM boundary shared in spirit with the comparison view tests. This
// test exercises user-visible mode/section transitions with real worker data.
class Element {
  constructor(tagName, ownerDocument) { Object.assign(this, { tagName, ownerDocument, children: [], attributes: new Map(), events: new Map(), ownText: "", open: false, hidden: false, style: {} }); }
  appendChild(element) { if (element.parentNode) element.parentNode.children = element.parentNode.children.filter(child => child !== element); this.children.push(element); element.parentNode = this; return element; }
  append(...elements) { elements.forEach(element => this.appendChild(element)); }
  replaceChildren(...elements) { this.children.forEach(child => { child.parentNode = null; }); this.children = []; this.ownText = ""; this.append(...elements); }
  set textContent(value) { this.replaceChildren(); this.ownText = String(value); }
  get textContent() { return this.ownText + this.children.map(child => child.textContent).join(" "); }
  setAttribute(key, value) { this.attributes.set(key, String(value)); }
  getAttribute(key) { return this.attributes.get(key) ?? null; }
  removeAttribute(key) { this.attributes.delete(key); }
  addEventListener(name, callback) { if (!this.events.has(name)) this.events.set(name, []); this.events.get(name).push(callback); }
  removeEventListener(name, callback) { this.events.set(name, (this.events.get(name) || []).filter(value => value !== callback)); }
  dispatchEvent(event) { event.target ||= this; event.currentTarget = this; event.preventDefault ||= () => { event.defaultPrevented = true; }; return Promise.all((this.events.get(event.type) || []).map(callback => callback(event))); }
  click() { return this.disabled ? Promise.resolve() : this.dispatchEvent({ type: "click", target: this }); }
  focus() { this.ownerDocument.activeElement = this; }
  contains(element) { return walk(this).includes(element); }
  get isConnected() { let node = this; while (node.parentNode) node = node.parentNode; return node === this.ownerDocument.body; }
  showModal() { this.open = true; this.setAttribute("open", ""); }
  close() { this.open = false; this.removeAttribute("open"); return this.dispatchEvent({ type: "close" }); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  querySelectorAll(selector) { return walk(this).slice(1).filter(element => selector.startsWith(".") ? (element.className || "").split(" ").includes(selector.slice(1)) : element.tagName === selector); }
}
const walk = element => [element, ...element.children.flatMap(walk)];
const doc = { activeElement: null, createElement(tag) { return new Element(tag, this); } }; doc.body = doc.createElement("body");
const target = doc.createElement("div"), comparisonTarget = doc.createElement("div"); doc.body.append(target, comparisonTarget);
const store = Model.createStore(), modes = [];
const view = View.create(target, { store, comparisonTarget, onModeChange(mode) { modes.push(mode); }, onPinCurrent() {} });
const classNode = (target, className) => walk(target).find(element => (element.className || "").split(" ").includes(className));
const chart = () => classNode(comparisonTarget, "analysis-session-chart");
const rowValues = label => {
  const row = walk(chart()).find(element => (element.className || "").split(" ").includes("analysis-session-chart-row") && walk(element).some(item => item.tagName === "strong" && item.textContent === label));
  assert.ok(row, "Missing comparison category: " + label);
  return walk(row).filter(element => (element.className || "").split(" ").includes("analysis-session-bar-value")).map(element => element.textContent);
};
const clickMeasure = async label => {
  const tab = walk(comparisonTarget).find(element => element.tagName === "button" && element.textContent === label);
  assert.ok(tab && !tab.hidden, "Missing comparison measure: " + label); await tab.click();
};
assert.equal(view.getMode(), "current");
view.setSection("analysis-section-craft");
store.setGroup("A", a); assert.equal(view.getMode(), "current", "A alone does not masquerade as a completed comparison");
store.setGroup("B", b); assert.equal(view.getMode(), "compare", "Completing both groups presents the comparison where the user is working");
assert.match(comparisonTarget.textContent, /Disc \/ saucer/);
assert.match(comparisonTarget.textContent, /Triangle/);
assert.match(comparisonTarget.textContent, /1973-08-01/);
assert.match(comparisonTarget.textContent, /1989-11-01/);
assert.deepEqual(rowValues("Disc / saucer"), ["50.0% · 1", "0.0% · 0"]);
assert.deepEqual(rowValues("Triangle"), ["0.0% · 0", "50.0% · 1"]);
view.setSection("analysis-section-time");
await clickMeasure("Year");
assert.deepEqual(rowValues("1973"), ["100.0% · 2", "0.0% · 0"]);
assert.deepEqual(rowValues("1989"), ["0.0% · 0", "100.0% · 2"]);
view.setSection("analysis-section-geography");
assert.deepEqual(rowValues("Belgium"), ["0.0% · 0", "100.0% · 2"]);
assert.deepEqual(rowValues("Unknown / not indexed"), ["50.0% · 1", "0.0% · 0"]);
view.setSection("analysis-section-sources_quality");
assert.deepEqual(rowValues("ufocat"), ["100.0% · 2", "0.0% · 0"]);
assert.deepEqual(rowValues("nuforc"), ["0.0% · 0", "100.0% · 2"]);
view.setSection("analysis-section-encounters");
assert.match(comparisonTarget.textContent, /unavailable|not (?:available|loaded)|no indexed/i);
view.setSection("analysis-section-crop-circles");
assert.match(comparisonTarget.textContent, /not (?:available|supported)|unavailable|no .*compar|current filters|current analysis/i, "Context categories disclose that their record universe is not captured by A/B report IDs");
view.setMode("current");
assert.equal(view.getMode(), "current");
assert.equal(classNode(comparisonTarget, "analysis-session-board").hidden, true, "Current mode removes the paired comparison from the visible category content");
store.useGroup("A");
assert.equal(view.getMode(), "current", "Selecting a held group does not unexpectedly reactivate A/B");
view.setSection("analysis-section-time");
assert.equal(view.getMode(), "current", "Category navigation preserves the explicit current-filter mode");
view.setMode("compare"); assert.equal(view.getMode(), "compare");
assert.equal(classNode(comparisonTarget, "analysis-session-board").hidden, false);
store.clearGroup("B"); assert.equal(view.getMode(), "current", "Removing a required group restores single-population navigation");
assert.equal(store.getState().groups.A.reportCount, 2, "Mode changes retain the captured group");
assert.ok(modes.includes("compare") && modes.includes("current"));
view.destroy();

// Exercise the production application visibility and controller callbacks.
// An ordinary Analysis render may reset visibility/ARIA, so the completion
// callback must reassert the comparison boundary after every such render.
const appSource = fs.readFileSync("app.js", "utf8").replace(/\r\n/g, "\n");
function actualFunction(name) {
  const start = appSource.search(new RegExp("^  (?:async )?function " + name + "\\(", "m"));
  assert.ok(start >= 0, "Missing production function " + name);
  const next = appSource.slice(start + 1).search(/\n  (?:async )?function \w+\(/);
  assert.ok(next >= 0); return appSource.slice(start, start + 1 + next);
}
const elements = new Map();
for (const id of ["analysis-panel", "analysis-content", "analysis-comparison-workspace", "analysis-section-nav"]) {
  const element = doc.createElement("div"); element.id = id; elements.set(id, element);
}
const craftNav = doc.createElement("button"), timeNav = doc.createElement("button");
craftNav.id = "analysis-section-tab-craft"; timeNav.id = "analysis-section-tab-time";
craftNav.setAttribute("aria-selected", "true"); timeNav.setAttribute("aria-selected", "false");
elements.get("analysis-section-nav").querySelectorAll = selector => { assert.equal(selector, '[role="tab"]'); return [craftNav, timeNav]; };
const content = elements.get("analysis-content"), host = elements.get("analysis-comparison-workspace");
const appCalls = [], appRuntime = { analysisSessionMode: "current", analysisSessionView: { setSection(key) { appCalls.push(["section", key]); } } };
const appContext = vm.createContext({ console, clearTimeout() {}, scheduleAnalysisCompute() {}, requestAnalysisCurrentSectionEvidence() {}, runtime: appRuntime, state: { activeView: "analysis" },
  document: { getElementById(id) { return elements.get(id) || null; } },
  getAnalysisFilterSnapshot() {}, applyAnalysisFilterPatch() {}, setContextLayerEnabled() {},
  requestEncounterReports() {}, openEncounterInspectedReport() {}, applyEncounterInspectedSelection() {}, requestPlanetaryHeatmaps() {},
  initializeAnalysisSession() { appCalls.push(["initialize-session"]); },
  requestAnalysisTimeEvidence() { appCalls.push(["time-evidence"]); },
});
appContext.window = appContext;
appContext.UfoAnalysisView = { AnalysisViewController: class {
  constructor(options) { this.options = options; this.activeSectionId = "analysis-section-craft"; }
  setAnalysisEnabled() {}
  setActiveView() {}
} };
for (const name of ["setAnalysisComparisonMode", "syncAnalysisComparisonWorkspace", "initializeAnalysisView"]) vm.runInContext(actualFunction(name), appContext);
appContext.setAnalysisComparisonMode("compare");
assert.equal(elements.get("analysis-panel").getAttribute("data-session-mode"), "compare");
assert.equal(content.inert, true); assert.equal(content.getAttribute("aria-hidden"), "true");
assert.equal(host.hidden, false); assert.equal(host.inert, false);
assert.equal(craftNav.getAttribute("aria-controls"), "analysis-comparison-workspace");
assert.equal(host.getAttribute("aria-labelledby"), craftNav.id);
const controller = appContext.initializeAnalysisView();
controller.options.onSectionActivate({ sectionKey: "time" });
assert.deepEqual(appCalls.find(call => call[0] === "section"), ["section", "time"], "The real Analysis navigator forwards its active category into the A/B view");
assert.ok(!appCalls.some(call => call[0] === "time-evidence"), "Held comparison navigation does not compute hidden live charts");
craftNav.setAttribute("aria-selected", "false"); timeNav.setAttribute("aria-selected", "true");
content.inert = false; content.removeAttribute("aria-hidden");
timeNav.setAttribute("aria-controls", "analysis-section-time");
controller.options.onRenderComplete();
assert.equal(content.inert, true); assert.equal(content.getAttribute("aria-hidden"), "true");
assert.equal(timeNav.getAttribute("aria-controls"), "analysis-comparison-workspace", "An ordinary rerender cannot leave category tabs pointing at hidden single-group charts");
assert.equal(host.getAttribute("aria-labelledby"), timeNav.id);
appContext.setAnalysisComparisonMode("current");
assert.equal(content.inert, false); assert.equal(content.getAttribute("aria-hidden"), null);
assert.equal(host.hidden, true); assert.equal(host.inert, true);
assert.equal(timeNav.getAttribute("aria-controls"), "analysis-section-time");
content.hidden = true; appContext.syncAnalysisComparisonWorkspace();
assert.equal(content.inert, true, "A hidden loading-state panel remains inert when returning to current reports");
elements.delete("analysis-panel"); assert.doesNotThrow(() => appContext.setAnalysisComparisonMode("compare"));
console.log("Analysis comparison navigation: distinct 1973/1989 populations, worker summaries, automatic A/B, category routing, missing fields, context limits and current-mode restoration passed.");
