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
  const view = View.create(target, Object.assign({ store,
    onPinCurrent(slot) { calls.push(["pin", slot]); },
    onUseGroup(slot) { calls.push(["use", slot]); return store.useGroup(slot); },
    onReturnToFilters() { calls.push(["return"]); return store.clearSelection(); },
    onOpenSection(section) { calls.push(["open", section]); }
  }, config));
  return { doc, target, store, calls, view };
}
const groupA = {
  eventIds: ["1", "2", "3", "4"], label: "France <img src=x>",
  scope: { timeRange: { startIso: "1954-09-01", endIso: "1954-11-30" } },
  summary: { reportN: 4, mappedN: 3, unmappedN: 1, datedN: 3, undatedN: 1, distributions: {
    source: { rows: [{ key: "ufocat", label: "UFOCAT", count: 2 }], eligibleN: 2, unknownN: 2 },
    craft: { rows: [{ key: "disc_saucer", count: 1 }, { key: "rectangle_box", label: "Recorded rectangular object", count: 1 }], eligibleN: 2, unknownN: 2 },
    being: { rows: [{ key: "humanoid", label: "Humanoid", count: 1 }], eligibleN: 1, unknownN: 3, multiLabel: true }
  } }
};
const groupB = {
  eventIds: ["4", "5"], label: "Other reports", scope: "All reports",
  summary: { reportN: 2, mappedN: 1, unmappedN: 1, distributions: {
    source: { rows: [{ key: "ufocat", label: "UFOCAT", count: 1 }], eligibleN: 1, unknownN: 1 },
    craft: { rows: [{ key: "disc_saucer", count: 2 }], eligibleN: 2, unknownN: 0 }
  } }
};
const f = fixture(), { target, doc, store, calls, view } = f;
const dialog = walk(target).find(element => element.tagName === "dialog"), chart = cls(target, "analysis-session-chart");
const compare = button(target, "Compare A / B");
assert.equal(dialog.open, false);
assert.equal(compare.disabled, true);
assert.equal(button(target, "Clear all").disabled, true);
assert.equal(chart.children.length, 0, "comparison data is not rendered into the Analysis page before it is requested");
store.setGroup("A", groupA);
assert.equal(compare.disabled, true, "a single group cannot open an A/B comparison");
store.setGroup("B", groupB);
assert.equal(compare.disabled, false);
assert.equal(chart.children.length, 0, "holding both groups still leaves the comparison out of the page flow");
compare.focus(); await compare.click();
assert.equal(dialog.open, true);
assert.equal(doc.activeElement, button(dialog, "Close"), "opening gives the comparison a keyboard focus target");
assert.match(dialog.textContent, /France <img src=x>/);
assert.equal(walk(dialog).some(element => element.tagName === "img"), false, "captured labels remain plain text");
assert.match(dialog.textContent, /1954-09-01 to 1954-11-30/);
assert.match(cls(dialog, "analysis-session-overlap").textContent, /1 shared report · 25\.0% of A · 50\.0% of B/);
const activeTopic = () => walk(dialog).find(element => element.getAttribute("role") === "tab" && element.getAttribute("aria-selected") === "true");
const row = label => walk(chart).find(element => (element.className || "").split(" ").includes("analysis-session-chart-row") && find(element, "strong", label));
const rowValues = label => walk(row(label)).filter(element => (element.className || "").split(" ").includes("analysis-session-bar-line")).map(element =>
  cls(element, "analysis-session-bar-letter").textContent + ": " + cls(element, "analysis-session-bar-value").textContent);
const tableRow = label => walk(chart).find(element => element.tagName === "tr" && element.children[0]?.textContent === label);
assert.equal(activeTopic().textContent, "Craft");
assert.deepEqual(rowValues("Disc / saucer"), ["A: 25.0% · 1", "B: 100.0% · 2"]);
assert.deepEqual(tableRow("Disc / saucer").children.slice(1).map(element => element.textContent), ["25.0% · 1", "100.0% · 2"], "exact table agrees with the visible chart");
assert.ok(row("Recorded rectangular object"), "explicit category labels are preserved");
assert.deepEqual(rowValues("Unknown / not indexed"), ["A: 50.0% · 2", "B: 0.0% · 0"]);
assert.match(chart.textContent, /all captured reports.*A\s*[:=]\s*4.*B\s*[:=]\s*2/);
const aDiscBar = cls(row("Disc / saucer").children[1], "analysis-session-bar-fill");
assert.equal(aDiscBar.style.width, "25%", "bar width uses all captured reports rather than the indexed-only denominator");
assert.equal(aDiscBar.parentNode.getAttribute("aria-hidden"), "true", "the visual bar does not repeat the accessible exact value");
assert.notEqual(cls(row("Disc / saucer").children[1], "analysis-session-bar-value").getAttribute("aria-hidden"), "true", "screen readers retain the exact count and percentage");

await button(dialog, "Sources").click();
assert.equal(activeTopic().textContent, "Sources");
assert.deepEqual(rowValues("UFOCAT"), ["A: 50.0% · 2", "B: 50.0% · 1"], "eligible source pool must not turn these shares into 100%");
assert.match(chart.textContent, /Field indexed · A: 2 of 4 · B: 1 of 2/);
assert.deepEqual(tableRow("Unknown / not indexed").children.slice(1).map(element => element.textContent), ["50.0% · 2", "50.0% · 1"]);
await button(dialog, "Beings").click();
assert.deepEqual(rowValues("Humanoid"), ["A: 25.0% · 1", "B: Not available"]);
assert.deepEqual(rowValues("Unknown / not indexed"), ["A: 75.0% · 3", "B: Not available"]);
assert.match(chart.textContent, /Missing information is not a zero count/);
assert.match(chart.textContent, /A report may have several labels/);
await button(dialog, "Abductions").click();
assert.match(chart.textContent, /unavailable for both groups/);
assert.match(chart.textContent, /No indexed categories/);
assert.equal(walk(chart).some(element => element.tagName === "table"), false, "an entirely unavailable field does not invent a zero table");
await button(dialog, "Coverage").click();
assert.deepEqual(rowValues("With a date"), ["A: 75.0% · 3", "B: Not available"]);
assert.match(chart.textContent, /dates of any recorded precision/);
assert.doesNotMatch(chart.textContent, /exact.day/i, "any-precision date coverage is not described as exact dates");

const chartBeforeSelection = chart.children[0], exactData = cls(chart, "analysis-session-data");
exactData.open = true; await exactData.dispatchEvent({ type: "toggle" });
store.useGroup("A");
assert.equal(activeTopic().textContent, "Coverage", "changing the current Analysis selection does not jump comparison topic");
assert.equal(chart.children[0], chartBeforeSelection, "same captured groups do not rebuild an inspected chart");
assert.equal(cls(chart, "analysis-session-data").open, true, "current selection changes preserve the inspected exact-data disclosure");
assert.equal(cls(target, "analysis-session-selection").hidden, false);
assert.match(cls(target, "analysis-session-selection").textContent, /Using France <img src=x> · 4 reports across Analysis/);
await button(target, "Encounters").click(); assert.deepEqual(calls.at(-1), ["open", "encounters"]);
await button(target, "Return to filters").click(); assert.deepEqual(calls.at(-1), ["return"]);
assert.equal(store.getState().selection, null);
assert.equal(store.getState().groups.A.reportCount, 4, "returning to filters preserves the captured comparison");
await button(dialog, "Close").click();
assert.equal(dialog.open, false); assert.equal(doc.activeElement, compare, "closing returns keyboard focus to its launcher");
await compare.click();
assert.equal(activeTopic().textContent, "Craft", "a fresh comparison opens at its advertised default topic");
const craftTab = activeTopic();
await craftTab.dispatchEvent({ type: "keydown", key: "ArrowRight" });
assert.equal(activeTopic().textContent, "Beings"); assert.equal(doc.activeElement, activeTopic(), "topic tabs support keyboard movement");
await activeTopic().dispatchEvent({ type: "keydown", key: "End" }); assert.equal(activeTopic().textContent, "Coverage");
await dialog.dispatchEvent({ type: "cancel" });
assert.equal(dialog.open, false, "Escape/cancel closes the dialog"); assert.equal(doc.activeElement, compare);
await compare.click(); await button(dialog, "Use B in Analysis").click();
assert.deepEqual(calls.at(-1), ["use", "B"]);
assert.equal(store.getState().activeGroup, "B"); assert.equal(dialog.open, false, "successful Analysis use closes the comparison");
await compare.click(); await button(dialog, "Clear A").click();
assert.equal(store.getState().groups.A, null); assert.equal(dialog.open, false, "clearing a required group closes the obsolete comparison");
assert.equal(compare.disabled, true);
assert.equal(doc.activeElement, button(target, "Set A"), "clearing a group moves focus to the action that can restore it");
store.setGroup("A", groupA); await compare.click();
assert.equal(activeTopic().textContent, "Craft");
assert.deepEqual(rowValues("Disc / saucer"), ["A: 25.0% · 1", "B: 100.0% · 2"], "clearing and recapturing cannot retain a stale chart");
await button(target, "Clear all").click();
assert.equal(store.getState().groups.A, null); assert.equal(store.getState().groups.B, null); assert.equal(store.getState().selection, null);
assert.equal(dialog.open, false); assert.equal(compare.disabled, true);
view.setStatus("Ready"); assert.equal(cls(target, "analysis-session-status").textContent, "Ready");
view.setBusy(true); assert.equal(button(target, "Set A").disabled, true); view.setBusy(false); assert.equal(button(target, "Set A").disabled, false);
view.destroy(); view.destroy(); assert.equal(target.children.length, 0);
store.setGroup("A", groupA); assert.equal(target.children.length, 0, "destroyed views no longer react to store changes");

let resolvePin, rejectPin;
const asyncCalls = [], pending = fixture({ onPinCurrent(slot) { asyncCalls.push(["pin", slot]); return new Promise((resolve, reject) => { resolvePin = resolve; rejectPin = reject; }); } });
const firstPin = button(pending.target, "Set A").click();
assert.deepEqual(asyncCalls, [["pin", "A"]]);
assert.equal(button(pending.target, "Set B").disabled, true, "a pending capture prevents overlapping mutations");
assert.equal(cls(pending.target, "analysis-session").getAttribute("aria-busy"), "true");
rejectPin(new Error("This filter selection is still updating. Try again.")); await firstPin;
assert.match(cls(pending.target, "analysis-session-status").textContent, /still updating/);
assert.equal(cls(pending.target, "analysis-session-status").getAttribute("data-error"), "true");
assert.equal(button(pending.target, "Set B").disabled, false, "an unsuccessful capture leaves an immediate retry");
const secondPin = button(pending.target, "Set B").click(); resolvePin(); await secondPin;
assert.equal(cls(pending.target, "analysis-session-status").getAttribute("data-error"), "false");
pending.store.setGroup("A", groupA); pending.store.setGroup("B", groupB);
await button(pending.target, "Compare A / B").click();
const failedUse = fixture({ onUseGroup() { return Promise.reject(new Error("Selection is still updating.")); } });
failedUse.store.setGroup("A", groupA); failedUse.store.setGroup("B", groupB);
const failedDialog = walk(failedUse.target).find(element => element.tagName === "dialog");
await button(failedUse.target, "Compare A / B").click(); await button(failedDialog, "Use A in Analysis").click();
assert.equal(failedDialog.open, true, "a failed Analysis action keeps the comparison open");
assert.match(cls(failedDialog, "analysis-session-status").textContent, /still updating/);
assert.equal(button(failedDialog, "Use A in Analysis").disabled, false);
failedUse.view.destroy(); pending.view.destroy();

const many = fixture(), categories = Array.from({ length: 10 }, (_, index) => ({ key: "category-" + index, label: "Category " + index, count: 1 }));
many.store.setGroup("A", { eventIds: categories.map((_, index) => String(index)), summary: { distributions: { craft: { rows: categories, eligibleN: 10, unknownN: 0 } } } });
many.store.setGroup("B", { eventIds: ["other"], summary: { distributions: { craft: { rows: [{ ...categories[9], count: 1 }], eligibleN: 1, unknownN: 0 } } } });
await button(many.target, "Compare A / B").click();
const manyChart = cls(many.target, "analysis-session-chart");
const chartLabels = () => walk(manyChart).filter(element => (element.className || "").split(" ").includes("analysis-session-row-heading")).flatMap(element => element.children.filter(child => child.tagName === "strong").map(child => child.textContent));
const initiallyOmitted = categories.find(category => !chartLabels().includes(category.label));
assert.ok(initiallyOmitted, "the initial comparison gives a short overview of long category lists");
assert.ok(walk(manyChart).some(element => element.tagName === "th" && element.textContent === initiallyOmitted.label), "exact data remains complete while the chart is abbreviated");
await button(many.target, "Show all 10 categories").click();
assert.ok(chartLabels().includes(initiallyOmitted.label), "expanding reveals categories omitted from the overview");
await button(many.target, "Show fewer").click(); assert.equal(chartLabels().includes(initiallyOmitted.label), false);
many.view.destroy();

const context = fixture(), sameTime = { startIso: "1973-10-01", endIso: "1973-10-31" };
const captured = (id, source, type) => ({ eventIds: [id], label: "Current Analysis reports", scope: { timeRange: sameTime },
  provenance: { capturedSnapshot: { filters: { sourceMode: "subset", selectedSources: [source], typeMode: "subset", selectedTypes: [type], encounters: { being: "any", abduction: "any", beingTypes: [] } } } } });
context.store.setGroup("A", captured("same-date-a", "ufocat", "Disk"));
context.store.setGroup("B", captured("same-date-b", "nuforc", "Sphere"));
await button(context.target, "Compare A / B").click();
const contextDialog = walk(context.target).find(element => element.tagName === "dialog");
const card = side => walk(contextDialog).find(element => element.tagName === "section" && (element.className || "").split(" ").includes("analysis-session-side-" + side));
assert.equal(find(card("a"), "h3", "1973-10-01 to 1973-10-31").textContent, find(card("b"), "h3", "1973-10-01 to 1973-10-31").textContent, "the fixtures intentionally share their date window");
assert.match(cls(card("a"), "analysis-session-card-filters").textContent, /Sources: UFOCAT.*Types: Disk/);
assert.match(cls(card("b"), "analysis-session-card-filters").textContent, /Sources: NUFORC.*Types: Sphere/);
assert.doesNotMatch(cls(card("a"), "analysis-session-card-filters").textContent, /NUFORC|Sphere/, "same-date groups remain distinguishable by their actual filters");
context.store.setGroup("A", { eventIds: ["full-study"], label: "Collection reports", scope: { allRecords: true, material: "soil", action: "collection", timeRange: sameTime },
  provenance: { capturedSnapshot: { filters: { sourceMode: "subset", selectedSources: ["map-only-sentinel"], typeMode: "subset", selectedTypes: ["map-only-type"] } } } });
assert.equal(cls(card("a"), "analysis-session-date").textContent, "All-time collection study", "full-study selections do not inherit a misleading current-map date window");
assert.match(cls(card("a"), "analysis-session-card-filters").textContent, /Full collection study.*Material: Soil.*Action: Collection/);
assert.doesNotMatch(card("a").textContent, /map.only.sentinel|map.only.type|1973-10/, "the full-study card shows its own scope rather than inherited map restrictions");
context.store.setGroup("A", { eventIds: ["reheld-selection"], label: "Current Analysis reports", scope: { timeRange: { mode: "full" } },
  provenance: { capturedSnapshot: { selection: { key: "selected", label: "School encounters", reportCount: 1 }, filters: { sourceMode: "all", typeMode: "all" } } } });
assert.ok(find(card("a"), "h3", "Captured selection"), "a reheld selection is not mislabeled as the entire all-time corpus");
assert.doesNotMatch(card("a").textContent, /All time/);
assert.match(cls(card("a"), "analysis-session-card-filters").textContent, /Captured selection: School encounters/);
context.view.destroy();

// Platforms without HTMLDialogElement still get an operable modal boundary.
const fallback = fixture(), fallbackDialog = walk(fallback.target).find(element => element.tagName === "dialog");
fallbackDialog.showModal = undefined; fallbackDialog.close = undefined;
fallback.store.setGroup("A", groupA); fallback.store.setGroup("B", groupB);
const fallbackCompare = button(fallback.target, "Compare A / B"); fallbackCompare.focus(); await fallbackCompare.click();
assert.equal(fallbackDialog.open, true); assert.equal(fallbackDialog.getAttribute("open"), "");
await button(fallbackDialog, "Close").click(); assert.equal(fallbackDialog.open, false); assert.equal(fallbackDialog.getAttribute("open"), null); assert.equal(fallback.doc.activeElement, fallbackCompare);
fallback.view.destroy();
console.log("Analysis comparison view: compact launcher, modal focus/lifecycle, real-model chart/table shares, explicit unknowns, overlap, topic navigation, current cohort, reset and async recovery passed.");
