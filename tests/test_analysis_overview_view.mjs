import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url), View = require("../analysis_overview_view.js");

// Deliberately small DOM boundary: checks concern exact populations, keyboard
// access and topic navigation without a browser or a graphics dependency.
class Element {
  constructor(tagName, ownerDocument) { this.tagName = tagName; this.ownerDocument = ownerDocument; this.children = []; this.attributes = new Map(); this.events = new Map(); this.ownText = ""; this.style = { setProperty(key, value) { this[key] = value; } }; }
  appendChild(el) { this.children.push(el); el.parentNode = this; return el; }
  append(...els) { els.forEach(el => this.appendChild(el)); }
  replaceChildren(...els) { this.children = []; this.ownText = ""; this.append(...els); }
  set textContent(value) { this.children = []; this.ownText = String(value); }
  get textContent() { return this.ownText + this.children.map(child => child.textContent).join(" "); }
  setAttribute(key, value) { this.attributes.set(key, String(value)); }
  getAttribute(key) { return this.attributes.get(key) ?? null; }
  addEventListener(key, fn) { if (!this.events.has(key)) this.events.set(key, []); this.events.get(key).push(fn); }
  dispatchEvent(event) { event.target ||= this; event.preventDefault ||= () => { event.defaultPrevented = true; }; return Promise.all((this.events.get(event.type) || []).map(fn => fn(event))); }
  click() { return this.dispatchEvent({ type: "click" }); }
  focus() { this.ownerDocument.activeElement = this; }
  querySelector(selector) {
    const display = selector.match(/^\[data-overview-display="(.*)"\]$/);
    if (display) return walk(this).find(el => el.getAttribute("data-overview-display") === display[1]);
    if (selector === ".analysis-overview-lens select") return walk(this).find(el => el.tagName === "select");
    return null;
  }
}
const walk = el => [el, ...el.children.flatMap(walk)];
const withClass = (root, value) => walk(root).filter(el => String(el.className || "").split(" ").includes(value));
const findButton = (root, text) => walk(root).find(el => el.tagName === "button" && el.textContent === text);
function fixture(config = {}) { const doc = { createElement(tag) { return new Element(tag, this); } }, target = doc.createElement("div"), calls = []; const view = View.create(target, { onOpenSection(...args) { calls.push(args); }, ...config }); return { doc, target, view, calls }; }
function values(totalN, eligibleN, unknownN, rows, columns) { return { totalN, eligibleN, unknownN, rows: rows.map(([key, label, total, counts]) => ({ key, label, totalN: total, counts })), columns: columns.map(([key, label, total]) => ({ key, label, totalN: total })) }; }
const craftRows = [["disc", "Disc / saucer", 8, [3, 4, 1]], ["triangle", "Triangle", 3, [1, 2, 0]], ["__unknown__", "Craft not indexed", 2, [1, 0, 1]]];
const decades = [["1950", "1950s", 5], ["1990", "1990s", 6], ["__unknown__", "Time unknown", 2]];
const all = values(13, 10, 3, craftRows, decades);
const beings = values(3, 2, 1, [["disc", "Disc / saucer", 2, [1, 0, 1]], ["triangle", "Triangle", 1, [1, 0, 0]], ["__unknown__", "Craft not indexed", 0, [0, 0, 0]]], decades);
const abduction = values(0, 0, 0, [], decades);
const matrixCard = (key, title, section = "craft") => ({ key, title, question: "How do the reports differ?", section, rowLabel: "Craft", columnLabel: "Era", rowDimension: "craft", columnDimension: "decade", columnOrder: "chronological", notes: ["Dates describe source reports, not proven events."], lanes: { all, beings, abduction } });
const country = values(13, 11, 2, [["US", "United States", 9, [5, 3, 1]], ["FR", "France", 4, [3, 0, 1]]], [["disc", "Disc / saucer", 8], ["triangle", "Triangle", 3], ["__unknown__", "Craft not indexed", 2]]);
const model = { status: "ready", totalN: 13, lanes: [{ key: "all", label: "All reports", totalN: 13, available: true }, { key: "beings", label: "Being reported", totalN: 3, available: true, evidenceUnavailableN: 2 }, { key: "abduction", label: "Abduction reported", totalN: 0, available: true }],
  cards: [matrixCard("craft_decade", "Craft through time"), { ...matrixCard("craft_country", "Craft by place", "geography"), lanes: { all: country, beings: country, abduction } },
    { ...matrixCard("being_craft", "Beings and craft", "encounters"), multiLabel: true }, matrixCard("craft_month", "Craft seasonality", "time"), matrixCard("month_decade", "Seasonality by era", "time"), matrixCard("source_decade", "Sources through time", "sources-quality")],
  contexts: [{ section: "crops", label: "Crop circles", detail: "27 active / 7,745 catalog entries", available: true }, { section: "comparisons", label: "Moon & planets", detail: "Context not loaded; open topic", available: false }] };
const f = fixture();
f.view.render({ model: { status: "loading" } }); assert.match(f.target.textContent, /Cross-tabulating/); assert.equal(walk(f.target).find(el => el.getAttribute("role") === "status")?.tagName, "div");
f.view.render({ model });
assert.equal(withClass(f.target, "analysis-overview-card").length, 6);
assert.deepEqual(withClass(f.target, "analysis-overview-grid")[0].children.map(el => el.children[0].children[0].children[0].textContent), ["Craft through time", "Beings and craft", "Craft by place", "Seasonality by era"]);
assert.equal(withClass(f.target, "analysis-overview-more")[0].open, false, "secondary patterns start collapsed");
assert.equal(withClass(f.target, "analysis-overview-profile").length, 2, "geography uses readable row profiles rather than another undifferentiated heatmap");
assert.match(f.target.textContent, /catalog report representations, not independent incidents/);
assert.match(f.target.textContent, /Being labels may overlap/);
assert.match(f.target.textContent, /27 active \/ 7,745 catalog entries/);
assert.equal(withClass(f.target, "analysis-overview-exact").length, 0, "full exact tables are built only on request");
const firstCard = withClass(f.target, "analysis-overview-card")[0], firstMatrix = withClass(firstCard, "analysis-overview-matrix")[0];
const cells = withClass(firstMatrix, "analysis-overview-cell"), buttons = cells.filter(el => el.tagName === "button");
assert.equal(buttons.filter(el => el.tabIndex === 0).length, 1, "a matrix offers one tab stop, then arrow navigation");
assert.equal(buttons[0].textContent, "37.5%"); assert.match(buttons[0].getAttribute("aria-label"), /Disc \/ saucer; 1950s: 3 report representations, 37.5% of 8 row reports/);
assert.equal(withClass(firstMatrix, "is-unknown").length, 5, "missing-axis cells remain visible including the zero at a missing intersection");
await buttons[0].dispatchEvent({ type: "keydown", key: "ArrowRight" }); assert.equal(f.doc.activeElement, buttons[1]); assert.equal(buttons[0].tabIndex, -1);
await buttons[1].click(); assert.equal(f.calls.at(-1)[0], "craft"); assert.deepEqual(f.calls.at(-1)[1].focus, { rowKey: "disc", columnKey: "1990", count: 4, rowTotalN: 8 });
const exact = withClass(firstCard, "analysis-overview-details")[0]; exact.open = true; await exact.dispatchEvent({ type: "toggle" });
assert.equal(withClass(exact, "analysis-overview-exact")[0].children.find(el => el.tagName === "tbody").children.length, 7, "all and only nonzero cells appear in the exact count table");
assert.match(exact.textContent, /10 with both fields indexed; 3 missing at least one field/);
await findButton(f.target, "Report count").click(); assert.equal(f.view.getState().mode, "count");
assert.equal(withClass(withClass(f.target, "analysis-overview-card")[0], "analysis-overview-cell")[0].textContent, "3");
assert.equal(withClass(f.target, "analysis-overview-details")[0].open, true, "a display change preserves the reader's open coverage table");
const lens = walk(f.target).find(el => el.tagName === "select"); lens.value = "beings"; await lens.dispatchEvent({ type: "change" });
assert.equal(f.view.getState().lane, "beings"); assert.match(f.target.textContent, /3 Being reported/); assert.match(f.target.textContent, /2 reports have unavailable encounter indexing/);
assert.equal(f.doc.activeElement, walk(f.target).find(el => el.tagName === "select"), "switching report lenses restores keyboard focus to the new lens control");
const focusedLens = f.doc.activeElement; f.view.render({ model });
assert.notEqual(f.doc.activeElement, focusedLens); assert.equal(f.doc.activeElement, walk(f.target).find(el => el.tagName === "select"), "a fresh data render preserves a focused lens even though the DOM is replaced");
const countControl = findButton(f.target, "Report count"); countControl.focus(); f.view.render({ model });
assert.equal(f.doc.activeElement, findButton(f.target, "Report count"), "a fresh data render preserves the focused display option by its key");
await findButton(f.target, "Row share").click(); assert.equal(f.doc.activeElement, findButton(f.target, "Row share"), "switching heatmap modes preserves keyboard focus");
assert.equal(withClass(withClass(f.target, "analysis-overview-card")[0], "analysis-overview-cell")[0].textContent, "50.0%", "the shared positive encounter lens updates actual cross-tab values");
const noPositive = walk(f.target).find(el => el.tagName === "select"); noPositive.value = "abduction"; await noPositive.dispatchEvent({ type: "change" });
assert.match(f.target.textContent, /No positive indexed reports/); assert.equal(withClass(f.target, "analysis-overview-cell").length, 0, "a zero-positive lens does not invent populated cells");
f.view.render({ model: { status: "ready", totalN: 0, lanes: [{ key: "all", label: "All reports", totalN: 0, available: true }], cards: [] } }); assert.match(f.target.textContent, /No reports match/);
f.view.render({ model: { status: "unavailable", reason: "Index not ready" } }); assert.match(f.target.textContent, /Index not ready/);
for (const unknown of [null, undefined, "", "   ", false, true]) {
  f.view.render({ model: { ...model, lanes: [{ key: "all", label: "All reports", totalN: unknown, available: true }] } });
  assert.match(withClass(f.target, "analysis-overview-population")[0].textContent, /Not available All reports/, "unavailable totals must not be presented as a zero-count finding");
}
const rare = fixture(), broadColumns = Array.from({ length: 8 }, (_, i) => ["craft" + i, i === 7 ? "Rare craft" : "Common craft " + i, i === 7 ? 1 : 10]);
const broad = values(71, 71, 0, [["1990", "1990s", 71, [10, 10, 10, 10, 10, 10, 10, 1]]], broadColumns), rareOnly = values(1, 1, 0, [["1990", "1990s", 1, [1]]], [["craft7", "Rare craft", 1]]);
const rareModel = { status: "ready", totalN: 71, lanes: [{ key: "all", label: "All reports", totalN: 71, available: true }, { key: "beings", label: "Being reported", totalN: 1, available: true }], cards: [{ key: "craft_decade", title: "Rare positive lens", section: "craft", rowDimension: "decade", columnDimension: "craft", lanes: { all: broad, beings: rareOnly } }] };
rare.view.render({ model: rareModel }); const rareLens = walk(rare.target).find(el => el.tagName === "select"); rareLens.value = "beings"; await rareLens.dispatchEvent({ type: "change" });
assert.match(rare.target.textContent, /Rare craft/); assert.equal(withClass(rare.target, "analysis-overview-cell")[0].textContent, "100.0%", "a positive lens containing only a craft outside the all-report top seven still shows its real cross-tab");
assert.equal(withClass(rare.target, "analysis-overview-details").length, 1, "the exact table remains reachable for rare positive categories");
f.view.render({ model: { ...model, cards: [matrixCard("craft_decade", "<img src=x>")] } }); assert.match(f.target.textContent, /<img src=x>/); assert.equal(walk(f.target).some(el => el.tagName === "img"), false, "catalog labels remain plain text");
f.view.destroy(); f.view.render({ model }); assert.equal(f.target.children.length, 0, "destroyed dashboards cannot reappear after a delayed result");
console.log("Analysis overview view tests passed");
