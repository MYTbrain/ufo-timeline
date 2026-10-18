import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const View = require("../analysis_session_view.js");
class Element {
  constructor(tagName, ownerDocument) { this.tagName = tagName; this.ownerDocument = ownerDocument; this.children = []; this.attributes = new Map(); this.events = new Map(); this.ownText = ""; this.open = false; this.style = {}; }
  appendChild(element) { this.children.push(element); element.parentNode = this; return element; }
  append(...elements) { elements.forEach(element => this.appendChild(element)); }
  replaceChildren(...elements) { this.children = []; this.ownText = ""; this.append(...elements); }
  set textContent(value) { this.ownText = String(value); this.children = []; }
  get textContent() { return this.ownText + this.children.map(child => child.textContent).join(" "); }
  setAttribute(key, value) { this.attributes.set(key, String(value)); }
  getAttribute(key) { return this.attributes.get(key) ?? null; }
  addEventListener(name, callback) { if (!this.events.has(name)) this.events.set(name, []); this.events.get(name).push(callback); }
  click() { if (this.disabled) return Promise.resolve(); return Promise.all((this.events.get("click") || []).map(callback => callback({ target: this }))); }
}
const walk = element => [element, ...element.children.flatMap(walk)];
const find = (target, tag, text) => walk(target).find(element => element.tagName === tag && element.textContent === text);
const cls = (target, value) => walk(target).find(element => (element.className || "").split(" ").includes(value));
const doc = { createElement(tag) { return new Element(tag, this); } }, target = doc.createElement("div");
let current = { groups: { A: null, B: null }, selection: null, activeGroup: null, comparison: null }, subscribed;
let removed = 0;
const store = { getState: () => current, subscribe(callback) { subscribed = callback; return () => { removed++; subscribed = null; }; },
  clearAll() { current = { groups: { A: null, B: null }, selection: null, activeGroup: null, comparison: null }; subscribed?.(); } };
const calls = []; let resolvePin, rejectPin;
const view = View.create(target, { store, onPinCurrent(slot) { calls.push(["pin", slot]); return new Promise((resolve, reject) => { resolvePin = resolve; rejectPin = reject; }); },
  onUseGroup(slot) { calls.push(["use", slot]); }, onReturnToFilters() { calls.push(["return"]); }, onOpenSection(section) { calls.push(["open", section]); } });
assert.match(target.textContent, /Try a comparison/);
assert.equal(cls(target, "analysis-session-groups").hidden, true);
assert.equal(cls(target, "analysis-session-comparison").hidden, true);
assert.equal(walk(target).some(element => element.tagName === "table"), false, "no comparison tables before groups are used");
assert.equal(find(target, "button", "Clear all").disabled, true);
const firstPin = find(target, "button", "Hold current as A").click();
assert.deepEqual(calls, [["pin", "A"]]);
assert.equal(find(target, "button", "Hold current as B").disabled, true, "pending pin disables concurrent mutations");
assert.equal(cls(target, "analysis-session").getAttribute("aria-busy"), "true");
rejectPin(new Error("This filter selection is still updating. Try again.")); await firstPin;
assert.match(cls(target, "analysis-session-status").textContent, /still updating/);
assert.equal(cls(target, "analysis-session-status").getAttribute("data-error"), "true");
assert.equal(find(target, "button", "Hold current as B").disabled, false, "error leaves an immediate retry");
const secondPin = find(target, "button", "Hold current as B").click(); resolvePin(); await secondPin;
const group = (label, n, mapped) => ({ label, reportCount: n, scope: { timeRange: { startIso: "1954-09-01", endIso: "1954-11-30" } },
  summary: { reportN: n, mappedN: mapped, unmappedN: n - mapped, datedN: n - 1, undatedN: 1 } });
current.groups.A = group("France <img src=x>", 4, 3); subscribed();
assert.equal(cls(target, "analysis-session-groups").hidden, false);
assert.equal(cls(target, "analysis-session-group").open, false, "group initially collapsed");
assert.match(target.textContent, /France <img src=x>/);
assert.equal(walk(target).some(element => element.tagName === "img"), false, "labels remain text");
assert.match(target.textContent, /1954-09-01 to 1954-11-30/);
await find(target, "button", "Use A in Analysis").click();
assert.deepEqual(calls.at(-1), ["use", "A"]);
current.groups.B = group("Other reports", 2, 1);
current.comparison = { a: current.groups.A.summary, b: current.groups.B.summary, overlapCount: 1,
  overlap: { reportN: 1, shareA: 0.25, shareB: 0.5 }, distributions: {
    source: { available: true, a: { available: true, eligibleN: 2 }, b: { available: true, eligibleN: 1 }, rows: [{ key: "ufocat", label: "UFOCAT", aCount: 2, bCount: 1, aShare: 1, bShare: 1, aShareOfReports: 0.5, bShareOfReports: 0.5 }],
      unknown: { aCount: 2, bCount: 1, aShareOfReports: 0.5, bShareOfReports: 0.5 } },
    being: { available: false, a: { available: true }, b: { available: false }, rows: [{ key: "humanoid", label: "Humanoid", aCount: 1, bCount: null, aShareOfReports: 0.25, bShareOfReports: null }] },
    craft: { available: false, a: { available: false }, b: { available: false }, rows: [] },
  } };
subscribed();
assert.equal(cls(target, "analysis-session-comparison").hidden, false);
assert.equal(cls(target, "analysis-session-comparison").open, false, "comparison starts collapsed");
assert.match(cls(target, "analysis-session-overlap").textContent, /1 report belongs to both groups · 25.0% of A · 50.0% of B/);
assert.match(target.textContent, /Reports with a date/);
assert.doesNotMatch(target.textContent, /exact.day/i, "any-precision dates are not labeled exact");
const sourceRow = walk(target).find(element => element.tagName === "tr" && element.children[0]?.textContent === "UFOCAT");
assert.equal(sourceRow.children[1].ownText, "2");
assert.equal(sourceRow.children[1].children[0].textContent, "50.0%", "uses full report denominator, not eligible-field share of100%");
assert.equal(sourceRow.children[1].children[1].getAttribute("aria-hidden"), "true", "visual proportion does not repeat screen-reader text");
assert.equal(sourceRow.children[1].children[1].children[0].style.width, "50%");
assert.match(target.textContent, /Field coverage · A: 2 of 4 captured reports · B: 1 of 2 captured reports/);
const beingRow = walk(target).find(element => element.tagName === "tr" && element.children[0]?.textContent === "Humanoid");
assert.equal(beingRow.children[2].textContent, "Not available", "unavailable is distinct from zero");
assert.match(target.textContent, /Missing information is not a zero count/);
const sourceDetails = walk(target).find(element => element.getAttribute("data-axis") === "source"); sourceDetails.open = true;
subscribed();
assert.equal(walk(target).find(element => element.getAttribute("data-axis") === "source").open, true, "refresh preserves disclosure state");
current.selection = current.groups.A; current.activeGroup = "A"; subscribed();
assert.equal(cls(target, "analysis-session-selection").hidden, false);
assert.match(cls(target, "analysis-session-selection").textContent, /Shared filters are kept/);
await find(target, "button", "Return to filters").click();
assert.deepEqual(calls.at(-1), ["return"], "return routed through runtime callback");
await find(target, "button", "Encounters").click();
assert.deepEqual(calls.at(-1), ["open", "encounters"]);
view.setBusy(true); assert.equal(find(target, "button", "Hold current as A").disabled, true); view.setBusy(false);
view.setStatus("Ready"); assert.equal(cls(target, "analysis-session-status").textContent, "Ready");
await find(target, "button", "Clear all").click();
assert.equal(current.groups.A, null); assert.equal(current.groups.B, null); assert.equal(current.selection, null);
assert.equal(cls(target, "analysis-session-groups").hidden, true);
view.destroy(); view.destroy(); assert.equal(removed, 1); assert.equal(target.children.length, 0);
const Model = require("../analysis_session.js"), actualStore = Model.createStore(), actualTarget = doc.createElement("div");
const actualView = View.create(actualTarget, { store: actualStore, onPinCurrent() {} });
actualStore.setGroup("A", { eventIds: ["1", "2"], label: "Two reports", summary: { reportN: 2, mappedN: 1, unmappedN: 1,
  distributions: { being: { rows: [{ key: "humanoid", label: "Humanoid", count: 1 }], eligibleN: 1, unknownN: 1, multiLabel: true },
    craft: { rows: [{ key: "disc_saucer", label: "disc_saucer", count: 1 }, { key: "rectangle_box", label: "Recorded rectangular object", count: 1 }], eligibleN: 2, unknownN: 0 } } } });
actualStore.setGroup("B", { eventIds: ["2", "3"], label: "Other two reports", summary: { reportN: 2 } });
const actualBeing = walk(actualTarget).find(element => element.tagName === "tr" && element.children[0]?.textContent === "Humanoid");
assert.ok(actualBeing, "actual model's one-sided unavailable distribution remains inspectable");
assert.equal(actualBeing.children[1].children[0].textContent, "50.0%");
assert.equal(actualBeing.children[2].textContent, "Not available");
assert.ok(find(actualTarget, "th", "Disc / saucer"), "known machine craft keys receive established display labels");
assert.ok(find(actualTarget, "th", "Recorded rectangular object"), "explicit supplied labels are preserved");
const actualDated = walk(actualTarget).find(element => element.tagName === "tr" && element.children[0]?.textContent === "Reports with a date");
assert.equal(actualDated.children[1].textContent, "Not available", "null coverage never becomes zero");
actualStore.useGroup("A"); assert.equal(cls(actualTarget, "analysis-session-selection").hidden, false);
actualStore.clearAll(); assert.equal(cls(actualTarget, "analysis-session-comparison").hidden, true);
actualView.destroy();
console.log("Analysis session view tests passed");
