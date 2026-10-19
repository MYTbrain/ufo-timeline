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
assert.equal(walk(target).some(el => el.tagName === "dialog"), false, "comparison must not require a hidden modal");
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
for (const key of ["crops", "animals", "facilities", "spatial", "comparisons", "context", "unknown-topic"]) {
  view.setSection(key); assert.equal(chart.hidden, true, key + " must not show a misleading current-B chart");
  assert.equal(chart.children.length, 0, "unsupported views cannot retain the previous topic's chart");
  assert.equal(cls(board, "analysis-session-unavailable").hidden, false);
  assert.match(cls(board, "analysis-session-missing").textContent, /not (?:yet captured|included)/);
}
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
console.log("Analysis comparison view: automatic inline A/B, explicit current/compare modes, topic-linked measures, exact shares, unknowns, unavailable context, keyboard navigation, capture instructions, scopes, async recovery and reset passed.");
