import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const View = require("../analysis_session_view.js"), Model = require("../analysis_session.js");

// A small DOM boundary, including dialog lifecycle and focus. Assertions below
// concern visible report values and user actions, not a particular node layout.
class Element {
  constructor(tagName, ownerDocument) {
    this.tagName = tagName; this.ownerDocument = ownerDocument; this.children = [];
    this.attributes = new Map(); this.events = new Map(); this.ownText = "";
    this.open = false; this.hidden = false; this.style = {};
  }
  appendChild(element) {
    if (element.parentNode) element.parentNode.children = element.parentNode.children.filter(child => child !== element);
    this.children.push(element); element.parentNode = this; return element;
  }
  append(...elements) { elements.forEach(element => this.appendChild(element)); }
  replaceChildren(...elements) { this.children.forEach(child => { child.parentNode = null; }); this.children = []; this.ownText = ""; this.append(...elements); }
  set textContent(value) { this.replaceChildren(); this.ownText = String(value); }
  get textContent() { return this.ownText + this.children.map(child => child.textContent).join(" "); }
  setAttribute(key, value) { this.attributes.set(key, String(value)); }
  getAttribute(key) { return this.attributes.get(key) ?? null; }
  removeAttribute(key) { this.attributes.delete(key); }
  addEventListener(name, callback) { if (!this.events.has(name)) this.events.set(name, []); this.events.get(name).push(callback); }
  removeEventListener(name, callback) { this.events.set(name, (this.events.get(name) || []).filter(value => value !== callback)); }
  dispatchEvent(event) {
    event.target ||= this; event.currentTarget = this; event.preventDefault ||= () => { event.defaultPrevented = true; };
    return Promise.all((this.events.get(event.type) || []).map(callback => callback(event)));
  }
  click() { return this.disabled ? Promise.resolve() : this.dispatchEvent({ type: "click", target: this }); }
  focus() { this.ownerDocument.activeElement = this; }
  contains(element) { return walk(this).includes(element); }
  get isConnected() { let node = this; while (node.parentNode) node = node.parentNode; return node === this.ownerDocument.body; }
  showModal() { this.open = true; this.setAttribute("open", ""); }
  close() { this.open = false; this.removeAttribute("open"); return this.dispatchEvent({ type: "close" }); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  querySelectorAll(selector) { return walk(this).slice(1).filter(element => matches(element, selector)); }
}
const walk = element => [element, ...element.children.flatMap(walk)];
const matches = (element, selector) => {
  if (selector.startsWith(".")) return (element.className || "").split(" ").includes(selector.slice(1));
  return element.tagName === selector;
};
const find = (target, tag, text) => walk(target).find(element => element.tagName === tag && element.textContent === text);
const cls = (target, value) => walk(target).find(element => (element.className || "").split(" ").includes(value));
const button = (target, text) => { const found = find(target, "button", text); assert.ok(found, `Missing action: ${text}`); return found; };
function document() { const doc = { activeElement: null, createElement(tag) { return new Element(tag, this); } }; doc.body = doc.createElement("body"); return doc; }
function fixture(config = {}) {
  const doc = document(), target = doc.createElement("div"), store = Model.createStore(), calls = [];
  doc.body.appendChild(target);
  const comparisonTarget = doc.createElement("div"); doc.body.appendChild(comparisonTarget);
  const modes = [];
  const view = View.create(target, Object.assign({ store, comparisonTarget, onModeChange(mode) { modes.push(mode); },
    onPinCurrent(slot) { calls.push(["pin", slot]); },
    onUseGroup(slot) { calls.push(["use", slot]); return store.useGroup(slot); },
    onReturnToFilters() { calls.push(["return"]); return store.clearSelection(); },
    onOpenSection(section) { calls.push(["open", section]); }
  }, config));
  return { doc, target, comparisonTarget, store, calls, modes, view };
}
const groupA = {
  eventIds: ["1", "2", "3", "4"], label: "France <img src=x>",
  scope: { timeRange: { startIso: "1954-09-01", endIso: "1954-11-30" } },
  summary: { reportN: 4, mappedN: 3, unmappedN: 1, datedN: 3, undatedN: 1, distributions: {
    source: { rows: [{ key: "ufocat", label: "UFOCAT", count: 2 }], eligibleN: 2, unknownN: 2 },
    craft: { rows: [{ key: "disc_saucer", count: 1 }, { key: "rectangle_box", label: "Recorded rectangular object", count: 1 }], eligibleN: 2, unknownN: 2 },
    being: { rows: [{ key: "humanoid", label: "Humanoid", count: 1 }], eligibleN: 1, unknownN: 3, multiLabel: true },
    calendarMonth: { rows: [{ key: "9", label: "September", count: 3 }], eligibleN: 3, unknownN: 1 },
    country: { rows: [{ key: "FR", label: "France", count: 3 }], eligibleN: 3, unknownN: 1 }
  } }
};
const groupB = {
  eventIds: ["4", "5"], label: "Other reports", scope: "All reports",
  summary: { reportN: 2, mappedN: 1, unmappedN: 1, distributions: {
    source: { rows: [{ key: "ufocat", label: "UFOCAT", count: 1 }], eligibleN: 1, unknownN: 1 },
    craft: { rows: [{ key: "disc_saucer", count: 2 }], eligibleN: 2, unknownN: 0 },
    calendarMonth: { rows: [{ key: "11", label: "November", count: 2 }], eligibleN: 2, unknownN: 0 },
    country: { rows: [{ key: "US", label: "United States", count: 2 }], eligibleN: 2, unknownN: 0 }
  } }
};
const f = fixture(), { target, comparisonTarget, doc, store, calls, modes, view } = f;
const board = cls(comparisonTarget, "analysis-session-board"), chart = cls(board, "analysis-session-chart");
const compare = button(target, "Compare A / B"), current = button(target, "Current reports");
assert.equal(view.getMode(), "current"); assert.equal(board.hidden, true); assert.equal(compare.disabled, true);
assert.equal(button(target, "Clear all").disabled, true);
assert.match(cls(target, "analysis-session-instructions").textContent, /Apply dates and filters.*Set A.*Set B/);
assert.equal(cls(target, "analysis-session-inspection").open, false, "an ordinary comparison does not open a record-inspection modal");
assert.equal(walk(target).includes(board), false, "a separate host places the chart beside topic navigation rather than above it");
view.setSection("craft"); store.setGroup("A", groupA);
assert.equal(compare.disabled, true); assert.equal(board.hidden, true);
assert.match(cls(target, "analysis-session-instructions").textContent, /One group is held.*Set B/);
store.setGroup("B", groupB);
assert.equal(view.getMode(), "compare", "capturing a second group makes the comparison visible immediately");
assert.equal(board.hidden, false); assert.equal(compare.getAttribute("aria-pressed"), "true");
assert.deepEqual(modes, ["compare"]);
assert.match(board.textContent, /Reported craft categories · Compare A \/ B/);
assert.match(board.textContent, /France <img src=x>/);
assert.equal(walk(board).some(element => element.tagName === "img"), false, "captured labels remain plain text");
assert.match(cls(board, "analysis-session-overlap").textContent, /1 shared report · 25\.0% of A · 50\.0% of B/);
const activeTopic = () => walk(board).find(element => element.getAttribute("role") === "tab" && element.getAttribute("aria-selected") === "true");
const row = label => walk(chart).find(element => (element.className || "").split(" ").includes("analysis-session-chart-row") && find(element, "strong", label));
const rowValues = label => walk(row(label)).filter(element => (element.className || "").split(" ").includes("analysis-session-bar-line")).map(element =>
  cls(element, "analysis-session-bar-letter").textContent + ": " + cls(element, "analysis-session-bar-value").textContent);
const tableRow = label => walk(chart).find(element => element.tagName === "tr" && element.children[0]?.textContent === label);
assert.equal(activeTopic().textContent, "Craft composition");
assert.deepEqual(rowValues("Disc / saucer"), ["A: 25.0% · 1", "B: 100.0% · 2"]);
assert.deepEqual(tableRow("Disc / saucer").children.slice(1).map(element => element.textContent), ["25.0% · 1", "100.0% · 2"]);
assert.deepEqual(rowValues("Unknown / not indexed"), ["A: 50.0% · 2", "B: 0.0% · 0"]);
assert.equal(cls(row("Disc / saucer").children[1], "analysis-session-bar-fill").style.width, "25%");
assert.equal(cls(row("Disc / saucer").children[1], "analysis-session-bar-track").getAttribute("aria-hidden"), "true");
assert.notEqual(cls(row("Disc / saucer").children[1], "analysis-session-bar-value").getAttribute("aria-hidden"), "true");
const chartBeforeSelection = chart.children[0], exactData = cls(chart, "analysis-session-data");
exactData.open = true; await exactData.dispatchEvent({ type: "toggle" });
store.useGroup("A");
assert.equal(chart.children[0], chartBeforeSelection, "selection changes do not rebuild an inspected comparison");
assert.equal(cls(chart, "analysis-session-data").open, true);
assert.equal(cls(target, "analysis-session-selection").hidden, false);
assert.match(cls(target, "analysis-session-selection").textContent, /Current Analysis selection: France <img src=x> · 4 reports/);
await current.click(); assert.equal(view.getMode(), "current"); assert.equal(board.hidden, true);
store.clearSelection(); store.setGroup("A", { ...groupA, label: "Updated A" });
assert.equal(view.getMode(), "current", "unrelated group and selection updates cannot unexpectedly reopen comparison");
await compare.click(); assert.equal(board.hidden, false);
assert.match(cls(target, "analysis-session-slot-label").textContent, /4 reports · 1954-09-01 to 1954-11-30/);
view.setSection("analysis-section-sources-quality");
assert.equal(activeTopic().textContent, "Sources");
assert.deepEqual(rowValues("UFOCAT"), ["A: 50.0% · 2", "B: 50.0% · 1"]);
assert.match(chart.textContent, /Field indexed · A: 2 of 4 · B: 1 of 2/);
assert.deepEqual(tableRow("Unknown / not indexed").children.slice(1).map(element => element.textContent), ["50.0% · 2", "50.0% · 1"]);
view.setSection("encounters"); assert.equal(activeTopic().textContent, "Beings");
assert.deepEqual(rowValues("Humanoid"), ["A: 25.0% · 1", "B: Not available"]);
assert.deepEqual(rowValues("Unknown / not indexed"), ["A: 75.0% · 3", "B: Not available"]);
assert.match(chart.textContent, /Missing information is not a zero count/); assert.match(chart.textContent, /A report may have several labels/);
await activeTopic().dispatchEvent({ type: "keydown", key: "ArrowRight" });
assert.equal(activeTopic().textContent, "Abductions"); assert.equal(doc.activeElement, activeTopic());
assert.match(chart.textContent, /unavailable for both groups/); assert.match(chart.textContent, /No indexed categories/);
assert.equal(walk(chart).some(element => element.tagName === "table"), false);
await activeTopic().dispatchEvent({ type: "keydown", key: "Home" }); assert.equal(activeTopic().textContent, "Beings");
view.setSection("time"); assert.equal(activeTopic().textContent, "Month of year");
assert.deepEqual(rowValues("September"), ["A: 75.0% · 3", "B: 0.0% · 0"]);
assert.deepEqual(rowValues("November"), ["A: 0.0% · 0", "B: 100.0% · 2"]);
view.setSection("geography"); assert.equal(activeTopic().textContent, "Countries");
assert.deepEqual(rowValues("France"), ["A: 75.0% · 3", "B: 0.0% · 0"]);
assert.deepEqual(rowValues("United States"), ["A: 0.0% · 0", "B: 100.0% · 2"]);
view.setSection("sources_quality"); assert.equal(activeTopic().textContent, "Sources", "the controller's underscore key maps to the same topic");
view.setSection("overview"); assert.equal(activeTopic().textContent, "Coverage");
assert.deepEqual(rowValues("With a date"), ["A: 75.0% · 3", "B: Not available"]);
assert.match(chart.textContent, /dates of any recorded precision/);
for (const key of ["crops", "animals", "facilities", "spatial", "comparisons", "context"]) {
  view.setSection(key); assert.equal(chart.hidden, true, key + " must not show a misleading current-B chart");
  assert.equal(chart.children.length, 0, "pending views cannot retain the previous topic's chart");
  assert.equal(cls(board, "analysis-session-external-status").hidden, false);
  await new Promise(resolve => setImmediate(resolve));
  assert.match(cls(board, "analysis-session-external-status").textContent, /does not yet provide.*Retry comparison/);
}
view.setSection("unknown-topic"); assert.equal(cls(board, "analysis-session-unavailable").hidden, false);
assert.match(cls(board, "analysis-session-missing").textContent, /not yet captured/);
await button(board, "View current reports").click(); assert.equal(view.getMode(), "current"); assert.equal(board.hidden, true);
assert.equal(doc.activeElement, current); view.setSection("craft"); await compare.click();
await button(board, "Use B in Analysis").click();
assert.deepEqual(calls.at(-1), ["use", "B"]); assert.equal(store.getState().activeGroup, "B");
assert.equal(view.getMode(), "current", "using one group switches to the single-population charts");
assert.equal(doc.activeElement, current);
await button(target, "Return to filters").click(); assert.deepEqual(calls.at(-1), ["return"]);
assert.equal(store.getState().selection, null); assert.equal(store.getState().groups.A.reportCount, 4);
await compare.click(); await button(board, "Clear A").click();
assert.equal(store.getState().groups.A, null); assert.equal(board.hidden, true); assert.equal(compare.disabled, true);
assert.equal(doc.activeElement, button(target, "Set A"));
store.setGroup("A", groupA); assert.equal(board.hidden, false, "recapturing the missing second group reactivates comparison");
await button(target, "Clear all").click(); assert.equal(view.getMode(), "current"); assert.equal(board.hidden, true);
assert.equal(store.getState().groups.A, null); assert.equal(store.getState().groups.B, null); assert.equal(store.getState().selection, null);
view.setStatus("Ready"); assert.equal(cls(target, "analysis-session-status").textContent, "Ready");
view.setBusy(true); assert.equal(button(target, "Set A").disabled, true); view.setBusy(false); assert.equal(button(target, "Set A").disabled, false);
view.destroy(); view.destroy(); assert.equal(target.children.length, 0); assert.equal(comparisonTarget.children.length, 0);
store.setGroup("A", groupA); assert.equal(target.children.length, 0);

let resolvePin, rejectPin;
const asyncCalls = [], pending = fixture({ onPinCurrent(slot) { asyncCalls.push(["pin", slot]); return new Promise((resolve, reject) => { resolvePin = resolve; rejectPin = reject; }); } });
const firstPin = button(pending.target, "Set A").click();
assert.deepEqual(asyncCalls, [["pin", "A"]]); assert.equal(button(pending.target, "Set B").disabled, true);
assert.equal(cls(pending.target, "analysis-session").getAttribute("aria-busy"), "true");
rejectPin(new Error("This filter selection is still updating. Try again.")); await firstPin;
assert.match(cls(pending.target, "analysis-session-status").textContent, /still updating/);
assert.equal(cls(pending.target, "analysis-session-status").getAttribute("data-error"), "true");
assert.equal(button(pending.target, "Set B").disabled, false);
const secondPin = button(pending.target, "Set B").click(); resolvePin(); await secondPin;
assert.equal(cls(pending.target, "analysis-session-status").getAttribute("data-error"), "false"); pending.view.destroy();
const replacing = fixture({ onPinCurrent(slot) { replacing.store.setGroup(slot, { ...groupA, label: "Recaptured " + slot }); } });
replacing.store.setGroup("A", groupA); replacing.store.setGroup("B", groupB); await button(replacing.target, "Current reports").click();
await button(replacing.target, "Replace A").click(); assert.equal(replacing.view.getMode(), "compare", "successful explicit replacement shows the updated comparison"); replacing.view.destroy();
const failedUse = fixture({ onUseGroup() { return Promise.reject(new Error("Selection is still updating.")); } });
failedUse.store.setGroup("A", groupA); failedUse.store.setGroup("B", groupB);
await button(failedUse.comparisonTarget, "Use A in Analysis").click();
assert.equal(failedUse.view.getMode(), "compare", "failed Analysis actions preserve the comparison");
assert.match(cls(failedUse.target, "analysis-session-status").textContent, /still updating/); failedUse.view.destroy();

const many = fixture(), categories = Array.from({ length: 10 }, (_, index) => ({ key: "category-" + index, label: "Category " + index, count: 1 }));
many.view.setSection("craft");
many.store.setGroup("A", { eventIds: categories.map((_, index) => String(index)), summary: { distributions: { craft: { rows: categories, eligibleN: 10, unknownN: 0 } } } });
many.store.setGroup("B", { eventIds: ["other"], summary: { distributions: { craft: { rows: [{ ...categories[9], count: 1 }], eligibleN: 1, unknownN: 0 } } } });
const manyChart = cls(many.comparisonTarget, "analysis-session-chart");
const chartLabels = () => walk(manyChart).filter(element => (element.className || "").split(" ").includes("analysis-session-row-heading")).flatMap(element => element.children.filter(child => child.tagName === "strong").map(child => child.textContent));
const initiallyOmitted = categories.find(category => !chartLabels().includes(category.label)); assert.ok(initiallyOmitted);
assert.ok(walk(manyChart).some(element => element.tagName === "th" && element.textContent === initiallyOmitted.label));
await button(many.comparisonTarget, "Show all 10 categories").click(); assert.ok(chartLabels().includes(initiallyOmitted.label));
await button(many.comparisonTarget, "Show fewer").click(); assert.equal(chartLabels().includes(initiallyOmitted.label), false); many.view.destroy();

const context = fixture(), sameTime = { startIso: "1973-10-01", endIso: "1973-10-31" };
const captured = (id, source, type) => ({ eventIds: [id], label: "Current Analysis reports", scope: { timeRange: sameTime },
  provenance: { capturedSnapshot: { filters: { sourceMode: "subset", selectedSources: [source], typeMode: "subset", selectedTypes: [type], encounters: { being: "any", abduction: "any", beingTypes: [] } } } } });
context.store.setGroup("A", captured("same-date-a", "ufocat", "Disk")); context.store.setGroup("B", captured("same-date-b", "nuforc", "Sphere"));
const card = side => walk(context.comparisonTarget).find(element => element.tagName === "section" && (element.className || "").split(" ").includes("analysis-session-side-" + side));
assert.match(cls(card("a"), "analysis-session-card-filters").textContent, /Sources: UFOCAT.*Types: Disk/);
assert.match(cls(card("b"), "analysis-session-card-filters").textContent, /Sources: NUFORC.*Types: Sphere/);
assert.doesNotMatch(cls(card("a"), "analysis-session-card-filters").textContent, /NUFORC|Sphere/);
context.store.setGroup("A", { eventIds: ["full-study"], label: "Collection reports", scope: { allRecords: true, material: "soil", action: "collection", timeRange: sameTime },
  provenance: { capturedSnapshot: { filters: { sourceMode: "subset", selectedSources: ["map-only-sentinel"], typeMode: "subset", selectedTypes: ["map-only-type"] } } } });
assert.equal(cls(card("a"), "analysis-session-date").textContent, "All-time collection study");
assert.match(cls(card("a"), "analysis-session-card-filters").textContent, /Full collection study.*Material: Soil.*Action: Collection/);
assert.doesNotMatch(card("a").textContent, /map.only.sentinel|map.only.type|1973-10/);
context.store.setGroup("A", { eventIds: ["reheld-selection"], label: "Current Analysis reports", scope: { timeRange: { mode: "full" } },
  provenance: { capturedSnapshot: { selection: { key: "selected", label: "School encounters", reportCount: 1 }, filters: { sourceMode: "all", typeMode: "all" } } } });
assert.ok(find(card("a"), "h3", "Captured selection")); assert.doesNotMatch(card("a").textContent, /All time/);
assert.match(cls(card("a"), "analysis-session-card-filters").textContent, /Captured selection: School encounters/); context.view.destroy();

const inlineDoc = document(), inline = inlineDoc.createElement("div"), inlineStore = Model.createStore(); inlineDoc.body.appendChild(inline);
const inlineView = View.create(inline, { store: inlineStore }); inlineStore.setGroup("A", groupA); inlineStore.setGroup("B", groupB);
assert.equal(cls(inline, "analysis-session-board").hidden, false, "standalone consumers have a working inline fallback host"); inlineView.destroy();
// External topic adapters run lazily against exact held IDs, including groups
// captured before these derived views existed. Counts below deliberately use
// context denominators different from the held UFO report populations.
const flush = () => new Promise(resolve => setImmediate(resolve));
const requests = [];
const derived = fixture({ onLoadComparison(request) { return new Promise((resolve, reject) => requests.push({ request, resolve, reject })); } });
const derivedBoard = cls(derived.comparisonTarget, "analysis-session-board"), derivedChart = cls(derivedBoard, "analysis-session-chart");
const derivedAxis = () => walk(derivedBoard).find(element => element.getAttribute("role") === "tab" && element.getAttribute("aria-selected") === "true");
const makeDimension = (key, label, unit = "context records") => ({ key, label, unit, notes: ["The same eligibility rule applies to A and B."],
  a: { totalN: 2, eligibleN: 1, unknownN: 1, rows: [{ key: "one", label: label + " one", count: 1 }] },
  b: { totalN: 3, eligibleN: 1, unknownN: 2, rows: [{ key: "one", label: label + " one", count: 1 }] } });
const ready = (...dimensions) => ({ status: "ready", dimensions, notes: ["Independent catalog record counts; not the held UFO report denominator."], artifactHashes: { fixture: "pinned-one" } });
derived.store.setGroup("A", { eventIds: groupA.eventIds, scope: groupA.scope });
derived.store.setGroup("B", { eventIds: groupB.eventIds, scope: groupB.scope });
await flush(); assert.equal(requests.length, 0, "holding A/B does not eagerly load derived comparisons");
derived.view.setSection("encounters"); await flush(); assert.equal(requests.length, 0, "Beings remains an immediate captured field");
await button(derivedBoard, "Collection materials").click(); await flush();
assert.equal(requests.length, 1); assert.equal(requests[0].request.section, "encounters");
assert.equal(requests[0].request.groups.A, derived.store.getState().groups.A, "the adapter receives the exact immutable group");
assert.equal(requests[0].request.groups.B, derived.store.getState().groups.B);
assert.equal(requests[0].request.settings.collectionEvidence, "direct"); assert.equal(requests[0].request.settings.orb, 3);
assert.equal(derivedChart.children.length, 0); assert.match(cls(derivedBoard, "analysis-session-external-status").textContent, /Preparing collection/);
assert.equal(derivedBoard.getAttribute("aria-busy"), "true");
requests[0].resolve(ready(makeDimension("collection_materials", "Material", "collection accounts"), makeDimension("collection_actions", "Collection actions", "collection accounts")));
await flush();
assert.equal(derivedAxis().textContent, "Collection materials"); assert.match(derivedChart.textContent, /Share of all collection accounts · A: 2 · B: 3/);
assert.match(derivedChart.textContent, /50\.0% · 1.*33\.3% · 1/);
assert.match(derivedChart.textContent, /Unknown \/ not indexed/); assert.match(derivedChart.textContent, /Independent catalog record counts/);
assert.equal(cls(derivedChart, "analysis-session-method-details").open, false, "long source/scope notes remain available in a collapsed disclosure");
assert.doesNotMatch(derivedChart.textContent, /Recapture/);
assert.equal(derivedBoard.getAttribute("aria-busy"), "false");
await derivedAxis().dispatchEvent({ type: "keydown", key: "End" }); assert.equal(derivedAxis().textContent, "Collection actions");
assert.equal(derived.doc.activeElement, derivedAxis()); assert.equal(requests.length, 1, "switching loaded dimensions reuses one topic result");
await button(derivedBoard, "Beings").click(); assert.equal(derivedAxis().textContent, "Beings");
assert.equal(cls(derivedBoard, "analysis-session-settings").hidden, true);
await button(derivedBoard, "Collection materials").click(); assert.equal(requests.length, 1);
assert.equal(cls(derivedBoard, "analysis-session-settings").hidden, false);

derived.view.setSection("crops"); await flush(); const cropRequest = requests.at(-1);
assert.equal(cropRequest.request.section, "crops"); assert.equal(derivedChart.children.length, 0);
derived.view.setSection("animals"); await flush(); const animalRequest = requests.at(-1);
animalRequest.resolve(ready(makeDimension("animal_species", "Animal species", "animal records"))); await flush();
assert.match(derivedChart.textContent, /Animal species one/);
cropRequest.resolve(ready(makeDimension("crop_profile", "Crop profile", "crop-circle records"))); await flush();
assert.match(derivedChart.textContent, /Animal species one/); assert.doesNotMatch(derivedChart.textContent, /Crop profile one/, "a late previous topic cannot replace the active chart");
const beforeCropReturn = requests.length;
derived.view.setSection("crops"); await flush(); assert.equal(requests.length, beforeCropReturn);
assert.match(derivedChart.textContent, /Crop profile one/); assert.match(derivedChart.textContent, /Share of all crop-circle records · A: 2 · B: 3/);
assert.match(walk(derivedChart).find(element => element.tagName === "caption").textContent, /all crop-circle records/);

derived.view.setSection("comparisons"); await flush(); const venusRequest = requests.at(-1);
derived.view.setSettings({ planet: "jupiter" }); await flush(); const jupiterRequest = requests.at(-1);
assert.equal(jupiterRequest.request.settings.planet, "jupiter"); assert.equal(jupiterRequest.request.settings.zodiac, "sidereal_lahiri");
venusRequest.resolve(ready(makeDimension("planet", "Venus"))); await flush(); assert.equal(derivedChart.children.length, 0, "late old settings must not populate a new settings view");
jupiterRequest.resolve(ready(makeDimension("planet", "Jupiter"))); await flush(); assert.match(derivedChart.textContent, /Jupiter one/);
const beforeVenusReturn = requests.length;
derived.view.setSettings({ planet: "venus" }); await flush(); assert.equal(requests.length, beforeVenusReturn); assert.match(derivedChart.textContent, /Venus one/);
assert.throws(() => derived.view.setSettings({ planet: "mars" }), /different planets/);
assert.throws(() => derived.view.setSettings({ orb: 100 }), /valid orb/);
assert.equal(derived.view.getSettings().planet, "venus", "invalid settings leave the accepted chart scope intact");
const planetControl = walk(derivedBoard).find(el => el.getAttribute("aria-label") === "Planet for both groups");
planetControl.value = "mars"; await button(derivedBoard, "Apply to both groups").click();
assert.equal(cls(derivedBoard, "analysis-session-settings-error").hidden, false); assert.match(cls(derivedBoard, "analysis-session-settings-error").textContent, /different planets/);
planetControl.value = "moon"; await button(derivedBoard, "Apply to both groups").click(); await flush(); const oldGroupRequest = requests.at(-1);
assert.equal(oldGroupRequest.request.settings.planet, "moon"); assert.equal(cls(derivedBoard, "analysis-session-settings-error").hidden, true);
derived.store.setGroup("A", { eventIds: ["replacement"], label: "Replacement A" }); await flush(); const newGroupRequest = requests.at(-1);
assert.notEqual(newGroupRequest.request.groups.A, oldGroupRequest.request.groups.A);
oldGroupRequest.resolve(ready(makeDimension("planet", "Stale group"))); await flush(); assert.equal(derivedChart.children.length, 0);
newGroupRequest.resolve(ready(makeDimension("planet", "New group"))); await flush(); assert.match(derivedChart.textContent, /New group one/); assert.doesNotMatch(derivedChart.textContent, /Stale group/);

derived.view.setSettings({ planet: "mercury" }); await flush(); requests.at(-1).reject(new Error("Fixture source unavailable")); await flush();
assert.equal(derivedChart.children.length, 0); assert.match(cls(derivedBoard, "analysis-session-external-status").textContent, /Fixture source unavailable.*Retry comparison/);
await button(derivedBoard, "Retry comparison").click(); await flush(); const retried = requests.at(-1);
retried.resolve(ready(makeDimension("planet", "Mercury"))); await flush(); assert.match(derivedChart.textContent, /Mercury one/);
derived.view.setSettings({ planet: "neptune" }); await flush(); const offscreenRequest = requests.at(-1);
await button(derived.target, "Current reports").click(); offscreenRequest.resolve(ready(makeDimension("planet", "Neptune"))); await flush();
assert.equal(derivedBoard.hidden, true); const beforeCompareReturn = requests.length;
await button(derived.target, "Compare A / B").click(); await flush(); assert.equal(requests.length, beforeCompareReturn); assert.match(derivedChart.textContent, /Neptune one/);

derived.view.setSettings({ planet: "sun" }); await flush(); const destroyedRequest = requests.at(-1);
derived.view.destroy(); destroyedRequest.resolve(ready(makeDimension("planet", "Destroyed"))); await flush();
assert.equal(derived.target.children.length, 0); assert.equal(derived.comparisonTarget.children.length, 0);
const manyMeasures = fixture({ onLoadComparison() { return Promise.resolve(ready(...Array.from({ length: 12 }, (_, index) => makeDimension("measure-" + index, "Measure " + index)))); } });
manyMeasures.store.setGroup("A", groupA); manyMeasures.store.setGroup("B", groupB); manyMeasures.view.setSection("comparisons"); await flush();
const manyBoard = cls(manyMeasures.comparisonTarget, "analysis-session-board"), manyPicker = cls(manyBoard, "analysis-session-measure-picker");
assert.equal(manyPicker.hidden, false); assert.equal(cls(manyBoard, "analysis-session-tabs").hidden, true, "large measure sets do not become a wall of wrapped tabs");
const measureSelect = manyPicker.children.find(el => el.tagName === "select");
assert.equal(measureSelect.children.length, 12); measureSelect.value = "external:measure-11"; await measureSelect.dispatchEvent({ type: "change" });
assert.match(cls(manyBoard, "analysis-session-chart").textContent, /Measure 11 one/);
assert.doesNotMatch(cls(manyBoard, "analysis-session-chart").textContent, /Measure 0 one/);
assert.equal(cls(manyBoard, "analysis-session-chart").getAttribute("role"), "region");
assert.match(cls(manyBoard, "analysis-session-chart").getAttribute("aria-label"), /Measure 11/); manyMeasures.view.destroy();
const missingScope = fixture({ onLoadComparison() { return Promise.resolve({ status: "unavailable", dimensions: [], reason: "No captured date or geographic scope defines these context records.", notes: ["Exact report membership is preserved."] }); } });
missingScope.store.setGroup("A", groupA); missingScope.store.setGroup("B", groupB); missingScope.view.setSection("crops"); await flush();
const missingBoard = cls(missingScope.comparisonTarget, "analysis-session-board");
assert.match(cls(missingBoard, "analysis-session-unavailable").textContent, /No captured date or geographic scope/);
assert.equal(cls(missingBoard, "analysis-session-external-status").hidden, true, "a legitimate unavailable scope is not an endless retry error");
assert.equal(cls(missingBoard, "analysis-session-chart").hidden, true);
await button(missingBoard, "View current reports").click(); assert.equal(missingScope.view.getMode(), "current"); missingScope.view.destroy();
const unavailableFields = fixture({ onLoadComparison() { return Promise.resolve(ready({ key: "gate", label: "Evidence gate", unit: "context records",
  a: { available: false, totalN: 4, reason: "No source location in A." }, b: { available: false, totalN: 2, reason: "No source location in B." } })); } });
unavailableFields.store.setGroup("A", groupA); unavailableFields.store.setGroup("B", groupB); unavailableFields.view.setSection("spatial"); await flush();
const unavailableChart = cls(unavailableFields.comparisonTarget, "analysis-session-chart");
assert.match(unavailableChart.textContent, /Share of all context records · A: 4 · B: 2/);
assert.match(cls(unavailableChart, "analysis-session-missing").textContent, /A: No source location in A.*B: No source location in B/);
assert.equal(cls(unavailableChart, "analysis-session-method-details").open, false); unavailableFields.view.destroy();
// The inspector preserves exact source identities and independent counting
// units. A record's display ID must never become an invented UFO report ID.
const recordRequests = [], openedRecords = [];
const inspecting = fixture({ onInspectComparison(request) { return new Promise((resolve, reject) => recordRequests.push({ request, resolve, reject })); },
  onOpenInspectedRecord(payload) { openedRecords.push(payload); } });
const longA = { eventIds: Array.from({ length: 40 }, (_, i) => "a" + i), label: "Large A", scope: groupA.scope,
  summary: { distributions: { craft: { eligibleN: 40, unknownN: 0, rows: [{ key: "disc_saucer", count: 40 }] } } } };
const shortB = { eventIds: ["b0", "b1", "b2"], label: "Small B", scope: groupB.scope,
  summary: { distributions: { craft: { eligibleN: 3, unknownN: 0, rows: [{ key: "disc_saucer", count: 3 }] } } } };
assert.equal(cls(inspecting.target, "analysis-session-edits").open, true);
inspecting.view.setSection("craft"); inspecting.store.setGroup("A", longA); inspecting.store.setGroup("B", shortB);
assert.equal(cls(inspecting.target, "analysis-session-edits").open, false, "post-capture edit controls collapse while mode controls remain available");
assert.equal(cls(inspecting.target, "analysis-session-held-summary").hidden, false);
assert.match(cls(inspecting.target, "analysis-session-held-summary").textContent, /A · 40 reports.*B · 3 reports/);
assert.equal(button(inspecting.target, "Current reports").disabled, false);
const inspector = cls(inspecting.target, "analysis-session-inspection"), inspectingChart = cls(inspecting.comparisonTarget, "analysis-session-chart");
const inspectRow = key => walk(inspectingChart).find(el => el.getAttribute("data-comparison-row-key") === key);
const reportRows = (start, end) => Array.from({ length: end - start }, (_, offset) => { const i = start + offset; return { id: "source-a" + i, label: i === 0 ? "Preserved <img src=x>" : "Report " + i,
  date: "1954-10-01", location: "Fixture place", source: "Source family one", detail: i === 0 ? "Long preserved account. ".repeat(30) : "Short account.",
  eventIds: ["a" + i], sourceLinkLabel: i === 0 ? "Open catalog <img src=x>" : undefined, sourceUrl: i === 0 ? "https://example.org/source" : i === 1 ? "javascript:alert(1)" : null }; });
const recordPage = (aRows, bRows = []) => ({ title: "disc_saucer", unit: "canonical_reports", groups: {
  A: { totalN: 40, matchedN: 40, rows: aRows }, B: { totalN: 3, matchedN: 3, rows: bRows }
}, notes: ["Records retain their source-family provenance."] });
const firstRow = inspectRow("disc_saucer"); const failedInspection = firstRow.click();
assert.equal(inspector.open, true); assert.equal(inspecting.doc.activeElement, button(inspector, "Close records"));
assert.equal(recordRequests.at(-1).request.domainKey, "craft"); assert.equal(recordRequests.at(-1).request.rowKey, "disc_saucer");
assert.equal(recordRequests.at(-1).request.offset, 0); assert.equal(recordRequests.at(-1).request.limit, 25);
assert.equal(recordRequests.at(-1).request.groups.A, inspecting.store.getState().groups.A);
assert.equal(recordRequests.at(-1).request.dimension.row.aCount, 40); assert.equal(recordRequests.at(-1).request.dimension.a.totalN, 40);
recordRequests.at(-1).reject(new Error("Preserved source temporarily unavailable")); await failedInspection;
assert.match(cls(inspector, "analysis-session-inspection-status").textContent, /temporarily unavailable/);
const retriedInspection = button(inspector, "Retry records").click();
recordRequests.at(-1).resolve(recordPage(reportRows(0, 25), [{ id: "context-only", label: "Context source without report join", sourceUrl: "https://example.org/context" }, { id: "second-context", label: "Second context" }, { id: "third-context", label: "Third context" }])); await retriedInspection;
assert.equal(walk(inspector).filter(el => el.tagName === "article").length, 28);
assert.match(inspector.textContent, /Disc \/ saucer/); assert.doesNotMatch(walk(inspector).find(el => el.tagName === "h2").textContent, /disc_saucer/);
assert.equal(walk(inspector).some(el => el.tagName === "img"), false);
assert.equal(walk(inspector).filter(el => el.tagName === "button" && el.textContent === "Open preserved report").length, 25);
assert.equal(walk(inspector).filter(el => el.tagName === "a").length, 2, "only safe HTTP sources become links; context IDs do not become report actions");
assert.equal(walk(inspector).find(el => el.tagName === "a").rel, "noopener noreferrer");
assert.equal(walk(inspector).find(el => el.tagName === "a").textContent, "Open catalog <img src=x>", "source-link roles remain plain text rather than HTML");
assert.equal(walk(inspector).some(el => el.tagName === "a" && el.textContent === "Open source"), true, "unlabeled exact sources retain the existing default");
const accountDisclosure = walk(inspector).find(el => el.tagName === "details" && (el.className || "").includes("analysis-session-record-detail"));
accountDisclosure.open = true; await accountDisclosure.dispatchEvent({ type: "toggle" });
button(inspector, "Load more records").focus();
const loadMore = button(inspector, "Load more records").click(); assert.equal(recordRequests.at(-1).request.offset, 25);
recordRequests.at(-1).resolve(recordPage(reportRows(25, 40))); await loadMore;
assert.equal(walk(inspector).filter(el => el.tagName === "article").length, 43);
assert.equal(button(inspector, "Load more records").hidden, true);
assert.equal(inspecting.doc.activeElement, button(inspector, "Close records"), "the last page never strands focus on a hidden pagination button");
assert.equal(walk(inspector).find(el => el.tagName === "details" && (el.className || "").includes("analysis-session-record-detail")).open, true, "pagination retains open source details");
await button(inspector, "Close records").click(); assert.equal(inspector.open, false); assert.equal(inspecting.doc.activeElement, firstRow);

const partialInspection = inspectRow("disc_saucer").click();
recordRequests.at(-1).resolve({ unit: "canonical_reports", groups: { A: { totalN: 40, matchedN: 40, rows: reportRows(0, 1) }, B: { totalN: 3, matchedN: null, available: false, reason: "The held field is unavailable for B.", rows: [] } } }); await partialInspection;
assert.match(inspector.textContent, /B · Unavailable/); assert.match(inspector.textContent, /held field is unavailable for B/);
await button(inspector, "Open preserved report").click(); assert.equal(inspector.open, false); assert.equal(openedRecords.at(-1).eventId, "a0");
const bOnlyInspection = inspectRow("disc_saucer").click();
recordRequests.at(-1).resolve({ unit: "canonical_reports", groups: { A: { totalN: 40, matchedN: null, available: false, reason: "A field unavailable.", rows: [] }, B: { totalN: 3, matchedN: 3, rows: [{ id: "b-preserved", label: "Available B", eventIds: ["b0"] }] } } }); await bOnlyInspection;
assert.equal(inspector.getAttribute("data-active-side"), "B", "the phone starts with usable B when A is unavailable"); inspecting.view.closeInspection();

const staleTopic = inspectRow("disc_saucer").click(), staleTopicRequest = recordRequests.at(-1);
inspecting.view.setSection("time"); assert.equal(inspector.open, false); staleTopicRequest.resolve(recordPage(reportRows(0, 1))); await staleTopic;
assert.equal(inspector.open, false); inspecting.view.setSection("craft");
const staleSettings = inspectRow("disc_saucer").click(), staleSettingsRequest = recordRequests.at(-1);
inspecting.view.setSettings({ planet: "jupiter" }); assert.equal(inspector.open, false); staleSettingsRequest.resolve(recordPage(reportRows(0, 1))); await staleSettings;
const staleGroups = inspectRow("disc_saucer").click(), staleGroupsRequest = recordRequests.at(-1);
inspecting.store.setGroup("A", { eventIds: ["new-a"], summary: { distributions: { craft: { eligibleN: 1, unknownN: 0, rows: [{ key: "triangle", count: 1 }] } } } });
assert.equal(inspector.open, false); staleGroupsRequest.resolve(recordPage(reportRows(0, 1))); await staleGroups;
const staleCurrent = inspectRow("disc_saucer").click(), staleCurrentRequest = recordRequests.at(-1);
await button(inspecting.target, "Current reports").click(); assert.equal(inspector.open, false); staleCurrentRequest.resolve(recordPage(reportRows(0, 1))); await staleCurrent;
await button(inspecting.target, "Compare A / B").click();
inspecting.store.setGroup("A", { ...longA, summary: { distributions: { craft: { eligibleN: 39, unknownN: 1, rows: [{ key: "disc_saucer", count: 39 }] } } } });
const unknownInspection = inspectRow("__unknown__").click(); assert.equal(recordRequests.at(-1).request.rowKey, "__unknown__");
recordRequests.at(-1).resolve({ unit: "canonical_reports", groups: { A: { totalN: 40, matchedN: 1, rows: [{ id: "unknown-a39", label: "Unknown craft", eventIds: ["a39"] }] }, B: { totalN: 3, matchedN: 0, rows: [] } } }); await unknownInspection;
assert.match(inspector.textContent, /No matching records in this group/); inspecting.view.closeInspection(); assert.equal(inspector.open, false);
const doomedInspection = inspectRow("disc_saucer").click(), doomedRequest = recordRequests.at(-1); inspecting.view.destroy(); doomedRequest.resolve(recordPage(reportRows(0, 1))); await doomedInspection;
assert.equal(inspecting.target.children.length, 0);

const bounded = fixture({ onLoadComparison() { return Promise.resolve(ready({ key: "phase", label: "Estimated phase", unit: "canonical_reports", uncertainty: {
  kind: "sampled_time_interval", label: "Stable–possible counts", estimate: "utc_noon_with_verified_utc_overrides", note: "Counts span sampled source-time intervals, not confidence intervals."
}, a: { totalN: 4, eligibleN: 4, unknownN: 0, coverage: { verifiedTimeN: 1, dateOnlyN: 3 }, rows: [{ key: "one", label: "Phase one", count: 2, lowerCount: 1, upperCount: 3 }, { key: "other", label: "Other phase", count: 2, lowerCount: 1, upperCount: 3 }] },
  b: { totalN: 2, eligibleN: 2, unknownN: 0, coverage: { verifiedTimeN: 0, dateOnlyN: 2 }, rows: [{ key: "one", label: "Phase one", count: 1, lowerCount: 0, upperCount: 2 }, { key: "other", label: "Other phase", count: 1, lowerCount: 0, upperCount: 2 }] } })); } });
bounded.store.setGroup("A", groupA); bounded.store.setGroup("B", groupB); bounded.view.setSection("comparisons"); await flush();
const boundedChart = cls(bounded.comparisonTarget, "analysis-session-chart");
assert.match(boundedChart.textContent, /1–3 stable–possible/); assert.match(boundedChart.textContent, /0–2 stable–possible/);
assert.match(cls(boundedChart, "analysis-session-uncertainty-note").textContent, /not confidence intervals/);
assert.match(cls(boundedChart, "analysis-session-method-details").textContent, /1 verified times.*3 date-only estimates/);
assert.match(walk(boundedChart).find(el => el.tagName === "table").textContent, /stable–possible/); bounded.view.destroy();
console.log("Analysis comparison view: inline modes, category routing, unit-aware derived results, lazy loads, scope disclosures, compact measure picker, settings/cache/race guards, errors/retry, keyboard access, capture scopes and reset passed.");
