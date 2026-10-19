import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
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
  click() { return this.disabled ? Promise.resolve() : this.dispatchEvent({ type: "click" }); }
  focus() { this.ownerDocument.activeElement = this; }
  querySelector(selector) {
    const display = selector.match(/^\[data-overview-display="(.*)"\]$/);
    if (display) return walk(this).find(el => el.getAttribute("data-overview-display") === display[1]);
    if (selector === ".analysis-overview-lens select") return walk(this).find(el => el.tagName === "select");
    return null;
  }
  querySelectorAll(selector) { return walk(this).slice(1).filter(el => selector === el.tagName || selector.startsWith(".") && String(el.className || "").split(" ").includes(selector.slice(1))); }
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
assert.deepEqual(withClass(f.target, "analysis-overview-card-lead").map(el => el.children[0].children[0].children[0].textContent), ["Craft through time", "Seasonality by era"], "the two time matrices span the full dashboard, leaving being and geography comparisons paired");
assert.equal(withClass(f.target, "analysis-overview-more")[0].open, false, "secondary patterns start collapsed");
assert.equal(withClass(f.target, "analysis-overview-profile").length, 2, "geography uses readable row profiles rather than another undifferentiated heatmap");
assert.match(f.target.textContent, /catalog report representations, not independent incidents/);
assert.match(f.target.textContent, /Being labels may overlap/);
assert.match(f.target.textContent, /27 active \/ 7,745 catalog entries/);
assert.equal(withClass(f.target, "analysis-overview-exact").length, 0, "full exact tables are built only on request");
const firstCard = withClass(f.target, "analysis-overview-card")[0], firstMatrix = withClass(firstCard, "analysis-overview-matrix")[0];
const cells = withClass(firstMatrix, "analysis-overview-cell"), buttons = cells.filter(el => el.tagName === "button");
assert.equal(firstMatrix.style["--overview-column-count"], 3, "matrix layout receives its actual column count so labels retain a readable minimum width");
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

const rich = fixture(), richColumns = [["disc_saucer", "Disc / saucer", 60], ["triangle", "Triangle", 40], ["__unknown__", "Craft unknown", 10]];
const richValues = values(110, 90, 20, [["1950", "1950s", 60, [50, 0, 10]], ["1990", "1990s", 40, [10, 30, 0]], ["__unknown__", "Time unknown", 10, [0, 10, 0]]], richColumns);
const richCard = { key: "craft_decade", title: "Craft through time", section: "craft", rowDimension: "decade", columnDimension: "craft", rowOrder: "chronological", lanes: { all: richValues } };
const richCountries = values(110, 100, 10, [["US", "United States", 60, [50, 0, 10]], ["FR", "France", 50, [10, 40, 0]]], richColumns);
const season = values(110, 90, 20, [["1950", "1950s", 60, [50, 0, 10]], ["1990", "1990s", 40, [10, 30, 0]], ["__unknown__", "Time unknown", 10, [0, 10, 0]]], [["01", "Jan", 60], ["02", "Feb", 40], ["__unknown__", "Month unknown", 10]]);
const richModel = { status: "ready", totalN: 110, coverage: { knownCraftN: 100, knownCountryN: 110, knownDecadeN: 100 }, lanes: [{ key: "all", label: "All reports", totalN: 110, available: true }], cards: [richCard,
  { ...richCard, key: "craft_country", title: "Country profiles", section: "geography", rowDimension: "country", lanes: { all: richCountries } },
  { ...richCard, key: "month_decade", title: "Seasonality", section: "time", columnDimension: "month", lanes: { all: season } }] };
rich.view.render({ model: richModel });
assert.equal(withClass(rich.target, "analysis-overview-field").length, 3, "coverage is shown as three compact labelled tracks");
assert.match(withClass(rich.target, "analysis-overview-field")[0].title, /100 of 110 report representations indexed/);
assert.equal(withClass(rich.target, "analysis-overview-field-track")[0].children[0].style.width, (10000 / 110) + "%");
const rowVolumes = withClass(withClass(rich.target, "analysis-overview-card")[0], "analysis-overview-row-volume");
assert.deepEqual(rowVolumes.map(el => el.children[0].style.width), ["100%", (200 / 3) + "%", (50 / 3) + "%"]);
assert.match(rich.target.textContent, /Row volumes scaled within this chart · longest bar = 60 reports/);
const contrastBox = withClass(withClass(rich.target, "analysis-overview-card")[0], "analysis-overview-contrasts")[0];
assert.equal(withClass(contrastBox, "analysis-overview-contrast").length, 2, "no card adds more than two supported descriptive contrasts");
assert.equal(withClass(contrastBox, "analysis-overview-contrast-row").length, 2, "each contrast has a row-share marker alongside a report-lens marker");
assert.match(contrastBox.textContent, /0–100%/); assert.match(contrastBox.textContent, /30\/40 reports/);
await withClass(contrastBox, "analysis-overview-contrast")[0].click(); assert.equal(rich.calls.at(-1)[0], "craft"); assert.equal(rich.calls.at(-1)[1].focus.rowKey, "1990");
const richExact = withClass(rich.target, "analysis-overview-details")[0]; richExact.open = true; await richExact.dispatchEvent({ type: "toggle" });
const exactBeforeDifference = withClass(richExact, "analysis-overview-exact")[0].children.find(el => el.tagName === "tbody").children.map(row => row.children.map(cell => cell.textContent));
await findButton(rich.target, "Difference").click(); assert.equal(rich.view.getState().mode, "difference"); assert.equal(rich.doc.activeElement, findButton(rich.target, "Difference"));
assert.match(rich.target.textContent, /pooled baseline includes this row and all retained categories/); assert.match(rich.target.textContent, /Color clips at ±50 pp/);
const diffMatrix = withClass(withClass(rich.target, "analysis-overview-card")[0], "analysis-overview-matrix")[0], diffCells = withClass(diffMatrix, "analysis-overview-cell");
assert.equal(diffCells[0].textContent, "+28.8 pp", "difference uses the full 60/110 column marginal, including unknown-date reports in the population");
assert.match(diffCells[0].getAttribute("aria-label"), /versus this report lens's 54.5% category share/);
assert.equal(diffCells[1].textContent, "−36.4 pp", "zero observed reports versus a positive baseline remains a valid negative composition difference");
assert.equal(diffCells[1].tagName, "span"); assert.ok(String(diffCells[1].className).includes("is-below")); assert.ok(!String(diffCells[1].className).includes("is-zero"));
assert.equal(diffCells[1].style["--overview-intensity"], (40 / 110 * 100) / 50, "zero-count differences retain their diverging color rather than neutral zero styling");
assert.equal(diffCells[2].textContent, "16.7%"); assert.ok(String(diffCells[2].className).includes("is-unknown")); assert.ok(!String(diffCells[2].className).includes("is-difference"), "missing categories retain unsigned shares and striped encoding");
const differenceDetails = withClass(rich.target, "analysis-overview-details")[0], differenceTable = withClass(differenceDetails, "analysis-overview-exact")[0], differenceRows = differenceTable.children.find(el => el.tagName === "tbody").children.map(row => row.children.map(cell => cell.textContent));
for (const previous of exactBeforeDifference) assert.deepEqual(differenceRows.find(row => row[0] === previous[0] && row[1] === previous[1]).slice(0, 5), previous, "difference mode leaves every original exact count, denominator and row share unchanged");
assert.match(differenceTable.textContent, /Pooled report-lens baseline includes each row/); assert.match(differenceTable.textContent, /Report-lens share Difference \(pp\)/);
assert.deepEqual(differenceRows.find(row => row[0] === "1950s" && row[1] === "Triangle"), ["1950s", "Triangle", "0", "60", "0.0%", "36.4%", "−36.4 pp"], "a supported zero-count contrast can be inspected alongside its pooled reference");
assert.equal(differenceRows.find(row => row[0] === "1950s" && row[1] === "Craft unknown").at(-1), "—", "unknown axes never receive a signed contrast in the exact table");
differenceDetails.open = false; await differenceDetails.dispatchEvent({ type: "toggle" }); differenceDetails.open = true; await differenceDetails.dispatchEvent({ type: "toggle" }); await differenceDetails.dispatchEvent({ type: "toggle" });
assert.equal(withClass(differenceDetails, "analysis-overview-exact").length, 1, "repeated disclosure toggles do not append duplicate exact tables");
assert.equal(withClass(rich.target, "analysis-overview-scale-zero")[0].textContent, "0", "the diverging scale visibly labels its zero midpoint");
const craftHeader = withClass(rich.target, "analysis-overview-header-craft").find(el => el.getAttribute("data-overview-craft-key") === "disc_saucer");
assert.equal(craftHeader.style["--overview-category"], "#38bdf8", "categorical header dots use the canonical map legend color");
const sameCraftSegment = walk(rich.target).find(el => el.getAttribute("data-overview-craft-segment") === "disc_saucer"); assert.equal(sameCraftSegment.style["--overview-category"], "#38bdf8", "country profiles retain the same craft color independently of category rank");
craftHeader.focus(); await craftHeader.click(); assert.equal(rich.view.getState().craftFocus, "disc_saucer");
assert.equal(rich.doc.activeElement.getAttribute("data-overview-craft-key"), "disc_saucer"); assert.equal(rich.doc.activeElement.getAttribute("aria-pressed"), "true", "focus controls retain keyboard focus and pressed state after a redraw");
assert.match(rich.target.textContent, /visual emphasis only; report populations unchanged/);
const highlightedCards = withClass(rich.target, "analysis-overview-card"), seasonCard = highlightedCards.find(el => el.children[0].children[0].children[0].textContent === "Seasonality");
assert.ok(withClass(highlightedCards[0], "is-craft-muted").length > 0); assert.equal(withClass(seasonCard, "is-craft-muted").length, 0, "charts without a craft dimension are never dimmed by craft highlighting");
assert.equal(withClass(highlightedCards[0], "analysis-overview-cell")[0].textContent, "+28.8 pp", "highlighting changes emphasis without recalculating or filtering counts");
await findButton(rich.target, "Clear highlight").click(); assert.equal(rich.view.getState().craftFocus, null); assert.equal(withClass(rich.target, "is-craft-muted").length, 0);

// Selecting a rare category in the positive lens must keep it visible when
// returning to the broad population where it falls outside the top seven.
const focusRare = fixture(), actualKeys = ["disc_saucer", "sphere_orb", "triangle", "cigar_cylinder", "oval_egg", "chevron_boomerang", "rectangle_box", "teardrop"];
const actualBroad = values(71, 71, 0, [["1990", "1990s", 71, [10, 10, 10, 10, 10, 10, 10, 1]]], actualKeys.map((key, i) => [key, key, i === 7 ? 1 : 10]));
const actualPositive = values(1, 1, 0, [["1990", "1990s", 1, [1]]], [["teardrop", "teardrop", 1]]), absentPositive = values(1, 1, 0, [["1990", "1990s", 1, [1]]], [["disc_saucer", "disc_saucer", 1]]);
const focusRareModel = { ...rareModel, cards: [{ ...rareModel.cards[0], lanes: { all: actualBroad, beings: actualPositive } }] };
focusRare.view.render({ model: focusRareModel }); let focusLens = walk(focusRare.target).find(el => el.tagName === "select"); focusLens.value = "beings"; await focusLens.dispatchEvent({ type: "change" });
let rareHeader = withClass(focusRare.target, "analysis-overview-header-craft").find(el => el.getAttribute("data-overview-craft-key") === "teardrop"); rareHeader.focus(); await rareHeader.click();
focusLens = walk(focusRare.target).find(el => el.tagName === "select"); focusLens.value = "all"; await focusLens.dispatchEvent({ type: "change" });
assert.equal(focusRare.view.getState().craftFocus, "teardrop"); assert.equal(withClass(focusRare.target, "analysis-overview-matrix")[0].style["--overview-column-count"], 8, "a focused rare craft is forced into the otherwise truncated axis");
focusRare.view.render({ model: { ...focusRareModel, cards: [{ ...focusRareModel.cards[0], lanes: { all: actualBroad, beings: absentPositive } }] } });
focusLens = walk(focusRare.target).find(el => el.tagName === "select"); focusLens.value = "beings"; await focusLens.dispatchEvent({ type: "change" });
assert.equal(focusRare.view.getState().craftFocus, null); assert.match(focusRare.target.textContent, /Highlight cleared: Teardrop is not indexed in this report lens/); assert.equal(withClass(focusRare.target, "is-craft-muted").length, 0);

const fallbackGlobal = {}; runInNewContext(readFileSync(new URL("../analysis_overview_view.js", import.meta.url), "utf8"), { globalThis: fallbackGlobal });
const fallbackDoc = { createElement(tag) { return new Element(tag, this); } }, fallbackTarget = fallbackDoc.createElement("div");
const fallback = fallbackGlobal.UfoAnalysisOverviewView.create(fallbackTarget); fallback.render({ model: richModel });
assert.equal(findButton(fallbackTarget, "Difference").disabled, true, "a missing optional helper explicitly disables differences rather than fabricating metrics");
await findButton(fallbackTarget, "Report count").click(); assert.equal(fallback.getState().mode, "count", "ordinary count charts remain available when the optional visual helper is unavailable");
for (const [totalN, expected] of [[2500, "−0.04 pp"], [16667, "−0.006 pp"], [1e15, "0.0 pp"]]) {
  const tiny = fixture(), tinyValue = values(totalN, totalN, 0, [["1950", "1950s", 1, [0, 1]], ["1990", "1990s", totalN - 1, [1, totalN - 2]]], [["conventional_or_explained", "conventional_or_explained", 1], ["disc_saucer", "disc_saucer", totalN - 1]]);
  tiny.view.render({ model: { status: "ready", totalN, lanes: [{ key: "all", label: "All reports", totalN, available: true }], cards: [{ ...richCard, lanes: { all: tinyValue } }] } });
  await findButton(tiny.target, "Difference").click();
  const tinyCell = withClass(tiny.target, "analysis-overview-cell").find(cell => cell.getAttribute("aria-label").startsWith("1950s; Conventional / explained:"));
  assert.equal(tinyCell.textContent, expected, "a nonzero contrast below 0.1 pp retains one significant digit rather than becoming signed zero");
  const details = withClass(tiny.target, "analysis-overview-details")[0]; details.open = true; await details.dispatchEvent({ type: "toggle" });
  assert.match(withClass(details, "analysis-overview-exact")[0].textContent, new RegExp(expected.replace(".", "\\.")), "the exact table uses the same small-contrast formatting as the heatmap");
  assert.doesNotMatch(tiny.target.textContent, /[+−]0\.0 pp/, "rounded signed zero does not appear anywhere in the chart or supporting table");
}
console.log("Analysis overview view tests passed");
