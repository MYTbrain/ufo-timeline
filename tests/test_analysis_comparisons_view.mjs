import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { render, artifactLoadTimeoutMs } = require("../analysis_comparisons_view.js");
assert.equal(artifactLoadTimeoutMs(), 30000);
assert.equal(artifactLoadTimeoutMs({}), 30000);
assert.equal(artifactLoadTimeoutMs({ ephemerisAtlas: { gzipByteLength: 41307851 } }), 180000,
  "The initial large atlas download receives a finite network-aware budget");
assert.equal(artifactLoadTimeoutMs({ ephemerisAtlas: { gzipByteLength: 1024 } }), 30000);
assert.equal(artifactLoadTimeoutMs({ ephemerisAtlas: { gzipByteLength: Infinity } }), 30000);
assert.equal(artifactLoadTimeoutMs({ ephemerisAtlas: { gzipByteLength: -1 } }), 30000);
assert.equal(artifactLoadTimeoutMs({ ephemerisAtlas: { gzipByteLength: 10 ** 12 } }), 180000,
  "The download budget is bounded rather than growing with an arbitrary size");
const { computeLunarContext } = require("../analysis_lunar.js");
const { computeCrossContext } = require("../analysis_cross_context.js");
const { computeNuclearContext } = require("../analysis_nuclear.js");
const { computePlanetaryContext, computePlanetaryHeatmaps } = require("../analysis_planetary.js");

class Element {
  constructor(tagName, document) {
    this.tagName = tagName; this.ownerDocument = document; this.children = []; this.attributes = new Map();
    this.events = new Map(); this.style = {}; this.ownText = ""; this.value = "";
  }
  appendChild(node) { this.children.push(node); return node; }
  replaceChildren(...nodes) { this.children = nodes; this.ownText = ""; }
  setAttribute(key, value) { this.attributes.set(key, String(value)); }
  getAttribute(key) { return this.attributes.get(key) ?? null; }
  set textContent(value) { this.ownText = String(value); this.children = []; }
  get textContent() { return this.ownText + this.children.map((node) => node.textContent).join(""); }
  addEventListener(name, callback) { if (!this.events.has(name)) this.events.set(name, []); this.events.get(name).push(callback); }
  dispatch(name, extra = {}) { for (const callback of this.events.get(name) || []) callback({ target: this, preventDefault() {}, ...extra }); }
  click() { if (this.tagName === "a") this.ownerDocument.lastDownload = this; this.dispatch("click"); }
  focus() { this.ownerDocument.activeElement = this; }
}
function walk(node) { return [node, ...node.children.flatMap(walk)]; }
function fixture() {
  const document = {
    targets: [],
    createElement(tagName) { return new Element(tagName, this); },
    getElementById(id) { return this.targets.flatMap(walk).find((node) => node.id === id) || null; },
    defaultView: { Blob, URL: {
      createObjectURL(blob) { document.exportedBlob = blob; return "blob:comparison-evidence"; },
      revokeObjectURL(url) { document.revokedUrl = url; },
    }, setTimeout(callback) { callback(); } },
  };
  const target = document.createElement("div"); document.targets.push(target);
  return { document, target };
}
const byText = (target, tag, text) => walk(target).find((node) => node.tagName === tag && node.textContent === text);
const select = (target, label) => walk(target).find((node) => node.tagName === "select" && node.getAttribute("aria-label") === label);
const change = (node, value) => { assert.ok(node); node.value = value; node.dispatch("change"); };
const headings = (target) => walk(target).filter((node) => node.tagName === "h4").map((node) => node.textContent);
function metric(target, name) {
  const term = byText(target, "dt", name); assert.ok(term, "Missing metric: " + name);
  const group = walk(target).find((node) => node.children.includes(term));
  return group.children.find((node) => node.tagName === "dd").textContent;
}
function table(target, caption) {
  return walk(target).find((node) => node.tagName === "table" && node.children.some((child) => child.tagName === "caption" && child.textContent.includes(caption)));
}
function tableRows(node) {
  assert.ok(node, "Expected a labeled exact-value table");
  return walk(node).filter((child) => child.tagName === "tr").map((row) => row.children.map((cell) => cell.textContent));
}

const ufoRows = [-1, 0, 1].map((ordinal) => ({ id: "ufo_" + ordinal, eventId: "ufo_" + ordinal,
  startOrdinal: ordinal, endOrdinal: ordinal, datePrecision: "exact_day", dateRole: "occurrence",
  lat: 40, lon: -100, craftType: ordinal ? "triangle" : "disc_saucer", type: "Craft", source: "fixture" }));
ufoRows.push({ ...ufoRows[1], id: "context", eventId: "context", type: "Nuclear / atomic event", visualTypeGroup: "Nuclear / atomic / weapons test" });
const context = { ordinalEpoch: "unix_day", crops: [{ id: "crop_a", startOrdinal: 0, endOrdinal: 0, datePrecision: "exact_day",
  dateRole: "discovery_date", lat: 40, lon: -100, coordinateEvidenceClass: "locality_centroid", uncertaintyKm: null,
  category: "ring", sourceFamilyIds: ["crop_source"] }],
  animals: [{ id: "animal_a", title: "Reviewed animal report", startOrdinal: 0, endOrdinal: 0, datePrecision: "exact_day",
    dateRole: "publication_date", lat: 40, lon: -100, coordinateEvidenceClass: "generalized_public_marker", uncertaintyKm: null,
    category: "bovine", sourceFamilyIds: ["animal_source"] }] };
const nuclearInput = { ordinalEpoch: "unix_day", windowDays: 7, distanceBandsKm: [25, 100],
  testRoles: ["peaceful"], startOrdinal: -2, endOrdinal: 2, rows: ufoRows, crops: context.crops, animals: context.animals,
  tests: [{ id: "target", ordinal: 0, lat: 40, lon: -100, role: "peaceful", country: "USA", region: "fixture" }],
  nuclearFacilities: [{ id: "nuclear", lat: 40, lon: -100, nuclearRoleSourceVerified: true, activeIntervals: [[1900, 2100]] }],
  broaderFacilities: [{ id: "broader", lat: 40, lon: -100.01, facilityClass: "research_test", activeIntervals: [[1900, 2100]] }],
  coverage: { countries: { USA: 1 }, firstDate: "1970-01-01", lastDate: "1970-01-01", facilityInventory: "A partial reviewed institution inventory." } };
const model = { status: "ready", ordinalEpoch: "unix_day", scope: "Fixture cohort scopes preserve date roles.",
  lunar: computeLunarContext({ ...context, rows: ufoRows }),
  planetary: computePlanetaryContext({ ...context, rows: ufoRows, planet: "Venus", aspectPartner: "Moon", zodiacSystem: "sidereal", aspectOrbDegrees: 3 }),
  crossContext: computeCrossContext(context), nuclear: computeNuclearContext(nuclearInput) };
const beforeModel = JSON.stringify(model);
const changes = [];
const { document, target } = fixture();
const callbacks = { onSettingsChange(settings) { changes.push(settings); } };
const planetaryModel = (settings = {}) => ({ ...model, planetary: computePlanetaryContext({ ...context,
  rows: ufoRows, planet: "Venus", aspectPartner: "Moon", zodiacSystem: "sidereal", aspectOrbDegrees: 3, ...settings }) });
render(target, model, callbacks);

// Real engine contracts: non-UFO context is excluded, date-only phase estimates
// remain separate from verified sky positions, and uncertainty spans are visible.
assert.equal(metric(target, "Exact-day phase estimates"), "3");
assert.equal(metric(target, "Verified time + location"), "0");
assert.match(target.textContent, /not treated as UTC/);
assert.equal(tableRows(table(target, "Lunar phase distribution"))[0].length, 6);
assert.equal(walk(target).filter((node) => node.className === "comparison-bar-interval").length, 8);
assert.ok(headings(target).some((heading) => /illumination/i.test(heading)));
assert.equal(document.getElementById("analysis-comparison-question-lunar").getAttribute("aria-selected"), "true");

// Keyboard tab navigation preserves a single focused tab and labeled panel.
document.getElementById("analysis-comparison-question-lunar").dispatch("keydown", { key: "ArrowRight" });
assert.equal(document.activeElement.id, "analysis-comparison-question-nuclear");
assert.equal(document.getElementById("analysis-comparison-focused-view").getAttribute("aria-labelledby"), "analysis-comparison-question-nuclear");
assert.equal(select(target, "Before / after window").value, "7", "Settings must describe the model actually being displayed");
assert.equal(select(target, "Explosion role").value, "peaceful");
assert.equal(select(target, "Maximum marker distance").value, "100");
assert.equal(metric(target, "Dated report markers"), "3");
const phases = tableRows(table(target, "Report-event windows"));
assert.equal(phases[0].length, 3);
assert.deepEqual(phases.slice(1).map((row) => row.slice(1)), [["1", "1"], ["1", "1"], ["1", "1"]]);
assert.match(target.textContent, /No uncontaminated calendar controls/);
assert.match(target.textContent, /Not estimable/);
assert.match(target.textContent, /uncertainty remains unknown/);

// Focused nuclear navigation hides the irrelevant dashboards, and verified
// nuclear institutions remain distinct from broader sites with unknown status.
change(select(target, "Nuclear comparison"), "facilities");
assert.ok(headings(target).includes("Source-confirmed nuclear institutions"));
assert.ok(!headings(target).includes("Reports before and after nuclear events"));
assert.equal(metric(target, "Reviewed nuclear institutions"), "1");
assert.equal(metric(target, "Broader markers"), "1");
assert.match(target.textContent, /not verified non-nuclear controls/);
assert.match(target.textContent, /Daily operation is not established/);
change(select(target, "Nuclear comparison"), "categories");
assert.ok(headings(target).includes("Reported craft categories"));
assert.ok(!headings(target).includes("Source-confirmed nuclear institutions"));
change(select(target, "Before / after window"), "30");
assert.deepEqual(changes.at(-1), { windowDays: 30 });
assert.match(target.textContent, /Updating the selected nuclear comparison/);
assert.equal(headings(target).length, 0, "Changed nuclear controls must not sit above the old-window charts");
render(target, model, callbacks);
assert.equal(select(target, "Before / after window").value, "30", "Local selection persists while a new model is calculating");
render(target, planetaryModel({ planet: "Saturn", aspectPartner: "Mars" }), callbacks);
assert.equal(select(target, "Before / after window").value, "30", "An unrelated planetary response must not reset pending nuclear settings");
assert.match(target.textContent, /Updating the selected nuclear comparison/);
const nuclearThirty = { ...model, nuclear: computeNuclearContext({ ...nuclearInput, windowDays: 30 }) };
render(target, nuclearThirty, callbacks);
assert.equal(select(target, "Before / after window").value, "30");
assert.ok(headings(target).includes("Reported craft categories"));
assert.ok(!target.textContent.includes("Updating the selected nuclear comparison"));

document.getElementById("analysis-comparison-question-crossContext").click();
assert.match(target.textContent, /Strict occurrence\/formation-site inference does not pass/);
const crossRows = tableRows(table(target, "Direct crop–animal marker comparisons"));
assert.equal(crossRows[0].length, 6);
assert.ok(crossRows[1].includes("Not estimable"), "Absent controls cannot produce a zero or infinite ratio");
const samples = tableRows(table(target, "Candidate crop and animal records"));
assert.ok(samples[1].some((value) => value.includes("1970-01-01 · discovery date")));
assert.ok(samples[1].some((value) => value.includes("1970-01-01 · publication date")));
assert.ok(samples[1].at(-1).includes("uncertainty unknown"));
const calendarHeaders = tableRows(table(target, "Worldwide recorded-date alignment"))[0];
assert.ok(calendarHeaders.includes("Matched pairs"), "The ratio denominator must be paired with its matched observation count");

// Planetary comparisons begin with the requested angular relationships, while
// zodiac positions, motion and houses remain separate focused views.
document.getElementById("analysis-comparison-question-planetary").click();
assert.equal(select(target, "Planetary comparison").value, "heatmaps");
change(select(target, "Planetary comparison"), "aspects");
assert.equal(document.getElementById("analysis-comparison-question-planetary").textContent, "Planets");
assert.equal(document.getElementById("analysis-comparison-focused-view").getAttribute("aria-labelledby"), "analysis-comparison-question-planetary");
assert.equal(select(target, "Planetary comparison").value, "aspects");
assert.equal(select(target, "Planet or luminary").value, "Venus");
assert.equal(select(target, "Aspect partner").value, "Moon");
assert.equal(select(target, "Aspect tolerance").value, "3");
assert.equal(metric(target, "Eligible dated reports"), "3", "Explicit non-UFO records must stay outside aspect denominators");
assert.equal(metric(target, "Verified observation times"), "0");
assert.equal(metric(target, "Noon estimates within bands"), String(model.planetary.domains[0].aspectPartners[0].anyAspectCount));
assert.ok(headings(target).includes("Venus & Moon · angular relationships"));
assert.ok(!headings(target).some((heading) => /zodiac positions|retrograde motion/.test(heading)));
assert.match(target.textContent, /trine is a 120° relationship/);
assert.match(target.textContent, /Reports outside these bands remain in the denominator/);
assert.match(target.textContent, /None of these major-aspect estimates remain inside their band throughout the sampled unknown-time interval/);
assert.match(target.textContent, /especially common with the fast-moving Moon/);
let aspectRows = tableRows(table(target, "Venus–Moon aspects, with a 3° tolerance"));
assert.equal(aspectRows[0].length, 6);
assert.equal(aspectRows.length, 7, "All five aspect bands plus the outside-band denominator must be inspectable");
assert.ok(aspectRows.some((row) => row[0] === "Trine"));
assert.ok(aspectRows.some((row) => row[0] === "Outside these bands"));
assert.equal(aspectRows.slice(1).reduce((sum, row) => sum + Number(row[1]), 0), 3);
assert.equal(walk(target).filter((node) => node.className === "comparison-bar-interval").length, aspectRows.length - 1);
const categoryAspectRows = tableRows(table(target, "Category-specific aspect counts and calendar opportunity"));
assert.equal(categoryAspectRows.length, 13, "Two craft categories each retain five bands and the outside-band population");
assert.equal(categoryAspectRows[0].length, 6);
assert.ok(categoryAspectRows.some((row) => row[0] === "triangle"));
assert.ok(categoryAspectRows.some((row) => row[0] === "disc saucer"));
assert.equal(categoryAspectRows.slice(1).reduce((sum, row) => sum + Number(row[2]), 0), 3,
  "Category comparison counts must preserve the same report denominator as the main chart");

change(select(target, "Compare with"), "crops");
assert.equal(metric(target, "Eligible dated reports"), "1");
assert.match(target.textContent, /discovery date: 1 records/);
change(select(target, "Compare with"), "animals");
assert.equal(metric(target, "Eligible dated reports"), "1");
assert.match(target.textContent, /publication date: 1 records/);
change(select(target, "Compare with"), "ufo");

change(select(target, "Planetary comparison"), "zodiac");
assert.equal(select(target, "Zodiac system").value, "sidereal");
assert.ok(headings(target).includes("Venus · Lahiri sidereal zodiac positions"));
assert.equal(tableRows(table(target, "Venus Lahiri sidereal sign distribution")).length, 13);
assert.match(target.textContent, /twelve equal 30° zodiac sectors/);
assert.ok(!select(target, "Aspect partner"));
change(select(target, "Planetary comparison"), "motion");
assert.ok(headings(target).includes("Venus · apparent direct & retrograde motion"));
assert.equal(tableRows(table(target, "Venus apparent motion and calendar opportunity")).length, 4);
assert.match(target.textContent, /0.01° per day/);
change(select(target, "Planetary comparison"), "houses");
assert.equal(metric(target, "Qualified time + location records"), "0");
assert.equal(metric(target, "House calculations"), "Unavailable");
assert.ok(headings(target).includes("Houses need a verified observation time & place"));
assert.match(target.textContent, /UTC noon estimates and approximate case markers do not qualify/);
assert.ok(!select(target, "Planet or luminary"));

// Pending settings must hide the previous charts until an actual matching model
// arrives. Selecting the current partner as the main body repairs the pair.
change(select(target, "Planetary comparison"), "aspects");
change(select(target, "Planet or luminary"), "Moon");
assert.deepEqual(changes.at(-1), { planet: "Moon", aspectPartner: "Sun" });
assert.equal(select(target, "Aspect partner").value, "Sun");
assert.ok(!walk(select(target, "Aspect partner")).some((node) => node.tagName === "option" && node.value === "Moon"));
assert.match(target.textContent, /Updating the selected planetary comparison/);
assert.equal(headings(target).length, 0, "Stale planetary charts must not describe newly selected settings");
render(target, model, callbacks);
assert.match(target.textContent, /Updating the selected planetary comparison/);
let latestPlanetaryModel = planetaryModel({ planet: "Moon", aspectPartner: "Sun" });
render(target, latestPlanetaryModel, callbacks);
assert.ok(headings(target).includes("Moon & Sun · angular relationships"));
assert.ok(!target.textContent.includes("Updating the selected planetary comparison"));
change(select(target, "Aspect partner"), "Mars");
assert.deepEqual(changes.at(-1), { aspectPartner: "Mars" });
latestPlanetaryModel = planetaryModel({ planet: "Moon", aspectPartner: "Mars" });
render(target, latestPlanetaryModel, callbacks);
assert.ok(headings(target).includes("Moon & Mars · angular relationships"));
change(select(target, "Aspect tolerance"), "1");
assert.deepEqual(changes.at(-1), { aspectOrbDegrees: 1 });
latestPlanetaryModel = planetaryModel({ planet: "Moon", aspectPartner: "Mars", aspectOrbDegrees: 1 });
render(target, latestPlanetaryModel, callbacks);
assert.equal(select(target, "Aspect tolerance").value, "1");
assert.ok(table(target, "Moon–Mars aspects, with a 1° tolerance"));
change(select(target, "Planetary comparison"), "zodiac");
change(select(target, "Zodiac system"), "tropical");
assert.deepEqual(changes.at(-1), { zodiacSystem: "tropical", ayanamsaId: "lahiri" });
assert.equal(headings(target).length, 0);
latestPlanetaryModel = planetaryModel({ planet: "Moon", aspectPartner: "Mars", aspectOrbDegrees: 1, zodiacSystem: "tropical" });
render(target, latestPlanetaryModel, callbacks);
assert.equal(select(target, "Zodiac system").value, "tropical");
assert.ok(headings(target).includes("Moon · Tropical zodiac positions"));
assert.equal(tableRows(table(target, "Moon Tropical sign distribution")).length, 13);
assert.equal(JSON.stringify(model), beforeModel, "Rendering and local navigation must not mutate the evidence model");

// The export includes the current selected planetary model, not only its chart.
byText(target, "button", "Download comparison evidence").click();
assert.deepEqual(JSON.parse(await document.exportedBlob.text()), JSON.parse(JSON.stringify(latestPlanetaryModel)));
render(target, model, callbacks);
document.getElementById("analysis-comparison-question-crossContext").click();
assert.equal(JSON.stringify(model), beforeModel, "Rendering and local navigation must not mutate the evidence model");

byText(target, "button", "Download comparison evidence").click();
assert.equal(document.lastDownload.download, "ufo-context-comparison-evidence.json");
assert.equal(document.exportedBlob.type, "application/json");
assert.deepEqual(JSON.parse(await document.exportedBlob.text()), JSON.parse(beforeModel));

// Missing exact dates are unavailable evidence, not a zero-percent distribution.
const empty = fixture();
const emptyLunar = computeLunarContext({ ordinalEpoch: "unix_day", rows: [{ id: "month", startOrdinal: 0, endOrdinal: 30, datePrecision: "month" }] });
render(empty.target, { ...model, lunar: emptyLunar }, callbacks);
assert.match(empty.target.textContent, /No selected records have eligible exact dates/);
const illumination = walk(empty.target).find((node) => node.tagName === "article" && node.textContent.includes("illumination"));
assert.ok(illumination);
assert.ok(!illumination.textContent.includes("0.0%"), "Empty exact-day denominators must remain unavailable, not zero share");

const emptyPlanetary = computePlanetaryContext({ ordinalEpoch: "unix_day", aspectPartner: "Moon", rows: [{ id: "month", startOrdinal: 0, endOrdinal: 30, datePrecision: "month" }] });
render(empty.target, { ...model, planetary: emptyPlanetary }, callbacks);
empty.document.getElementById("analysis-comparison-question-planetary").click();
change(select(empty.target, "Planetary comparison"), "aspects");
assert.equal(metric(empty.target, "Eligible dated reports"), "0");
assert.match(empty.target.textContent, /A missing denominator does not produce a zero-percent distribution/);
const emptyAspectRows = tableRows(table(empty.target, "Venus–Moon aspects, with a 3° tolerance"));
assert.equal(emptyAspectRows.length, 7);
assert.ok(emptyAspectRows.slice(1).every((row) => row[3] === "—" && row[4] === "—" && row[5] === "Not estimable"));
assert.ok(!empty.target.textContent.includes("0.0%"));

// The overview is generated by the actual engine, not placeholder matrix data.
// All bodies and unique pairs are visible one question at a time; display-only
// interactions must neither mutate the model nor launch additional requests.
const heat = fixture(), heatRequests = [], heatChanges = [];
const heatCallbacks = { onHeatmapRequest(settings) { heatRequests.push(settings); }, onSettingsChange(settings) { heatChanges.push(settings); } };
const heatmapEvidence = computePlanetaryHeatmaps({ ...context, rows: ufoRows, zodiacSystem: "sidereal", aspectOrbDegrees: 3 });
const heatModel = { ...model, planetaryHeatmaps: heatmapEvidence };
const beforeHeatModel = JSON.stringify(heatModel);
render(heat.target, model, heatCallbacks);
heat.document.getElementById("analysis-comparison-question-planetary").click();
assert.equal(select(heat.target, "Planetary comparison").value, "heatmaps");
assert.match(heat.target.textContent, /Loading planetary heatmaps/);
assert.equal(heatRequests.length, 1);
assert.deepEqual(heatRequests[0], { zodiacSystem: "sidereal", ayanamsaId: "lahiri", aspectOrbDegrees: 3 });
render(heat.target, model, heatCallbacks);
assert.equal(heatRequests.length, 1, "A loading render must not repeatedly request the same overview");
render(heat.target, heatModel, heatCallbacks);
const heatCells = () => walk(heat.target).filter((node) => node.tagName === "button" && String(node.className || "").startsWith("comparison-heatmap-cell"));
assert.equal(heatCells().length, 108);
assert.equal(select(heat.target, "Heatmap values").value, "difference");
assert.equal(metric(heat.target, "Eligible dated reports"), "3");
assert.equal(metric(heat.target, "Distinct report dates"), "3");
assert.equal(metric(heat.target, "Bodies"), "9");
assert.equal(tableRows(table(heat.target, "Zodiac positions heatmap exact values")).length, 109);
assert.match(heat.target.textContent, /percentage points/);
assert.match(heat.target.textContent, /full\s*11-point grid/);
assert.match(heat.target.textContent, /statistical confidence intervals/);
assert.ok(heatCells().some((node) => node.textContent === "0.00 pp" && node.style.background === "var(--panel)"), "Zero difference must use neutral fill");
assert.equal(heatCells().filter((node) => node.tabIndex === 0).length, 1, "The grid has one entry in the page Tab sequence");
heatCells()[0].dispatch("keydown", { key: "ArrowDown" });
assert.equal(heat.document.activeElement.id, "comparison-heatmap-cell-1-0");
assert.equal(heatCells().filter((node) => node.tabIndex === 0).length, 1);
heat.document.activeElement.dispatch("keydown", { key: "End" });
assert.equal(heat.document.activeElement.id, "comparison-heatmap-cell-1-11");
heatCells()[0].click();
assert.equal(heatCells()[0].getAttribute("aria-pressed"), "true");
assert.equal(metric(heat.target, "Estimated reports"), "0");
assert.equal(metric(heat.target, "Report / calendar"), "Not estimable");
assert.match(heat.target.textContent, /no matched calendar opportunity/);
assert.equal(heatChanges.length, 0, "Inspecting a cell stays in the overview without calculating a detailed model");
change(select(heat.target, "Heatmap values"), "share");
assert.equal(heatCells().length, 108);
assert.ok(heatCells().some((node) => node.textContent === "0.0%"));
change(select(heat.target, "Compare with"), "crops");
assert.equal(metric(heat.target, "Eligible dated reports"), "1");
assert.match(heat.target.textContent, /discovery date: 1 records/);
change(select(heat.target, "Compare with"), "animals");
assert.match(heat.target.textContent, /publication date: 1 records/);
change(select(heat.target, "Compare with"), "ufo");
heat.document.getElementById("comparison-heatmap-question-zodiac").dispatch("keydown", { key: "ArrowRight" });
assert.equal(heat.document.activeElement.id, "comparison-heatmap-question-aspects");
assert.equal(heatCells().length, 216, "Thirty-six unique pairs have five aspect cells and an outside-band cell");
assert.equal(metric(heat.target, "Planet pairs"), "36");
assert.equal(tableRows(table(heat.target, "Planet pairs & aspects heatmap exact values")).length, 217);
assert.ok(!select(heat.target, "Zodiac system"));
assert.equal(select(heat.target, "Aspect tolerance").value, "3");
assert.ok(walk(heat.target).some((node) => node.className === "comparison-heatmap-scroll comparison-heatmap-pairs"));
heat.document.getElementById("comparison-heatmap-question-motion").click();
assert.equal(heatCells().length, 27);
assert.equal(tableRows(table(heat.target, "Direct & retrograde heatmap exact values")).length, 28);
assert.ok(!select(heat.target, "Aspect tolerance"));
assert.equal(heatRequests.length, 1, "Domain, metric and matrix switches use the already loaded overview");
assert.equal(JSON.stringify(heatModel), beforeHeatModel);
byText(heat.target, "button", "Download comparison evidence").click();
assert.deepEqual(JSON.parse(await heat.document.exportedBlob.text()), JSON.parse(beforeHeatModel));

// Relevant settings withhold an old matrix; the lazily requested overview and
// detailed models keep separate identities and a declared common sample grid.
heat.document.getElementById("comparison-heatmap-question-zodiac").click();
change(select(heat.target, "Zodiac system"), "tropical");
assert.deepEqual(heatChanges.at(-1), { zodiacSystem: "tropical", ayanamsaId: "lahiri", heatmapOnly: true });
assert.equal(heatCells().length, 0, "Old sidereal matrices must not appear beneath tropical controls");
assert.equal(heatRequests.length, 2);
const tropicalHeatModel = { ...heatModel, planetaryHeatmaps: computePlanetaryHeatmaps({ ...context, rows: ufoRows, zodiacSystem: "tropical", aspectOrbDegrees: 3 }) };
render(heat.target, tropicalHeatModel, heatCallbacks);
assert.equal(heatCells().length, 108);
assert.match(heat.target.textContent, /Tropical zodiac sectors/);
heatCells()[0].click();
byText(heat.target, "button", "Open detailed comparison").click();
assert.deepEqual(heatChanges.at(-1), { planet: "Sun", samplingMode: "common_grid" });
assert.equal(select(heat.target, "Planetary comparison").value, "zodiac");
assert.match(heat.target.textContent, /Updating the selected planetary comparison/);
const drilledModel = { ...tropicalHeatModel, planetary: computePlanetaryContext({ ...context, rows: ufoRows,
  planet: "Sun", aspectPartner: "Moon", zodiacSystem: "tropical", aspectOrbDegrees: 3, samplingMode: "common_grid" }) };
render(heat.target, drilledModel, heatCallbacks);
assert.ok(headings(heat.target).includes("Sun · Tropical zodiac positions"));
assert.match(heat.target.textContent, /Opened from heatmap: Sun · Aries/);
byText(heat.target, "button", "Back to heatmap").click();
assert.equal(heatCells().length, 108);
assert.equal(heatRequests.length, 2);
heat.document.getElementById("comparison-heatmap-question-aspects").click();
heatCells()[0].click();
byText(heat.target, "button", "Open detailed comparison").click();
assert.deepEqual(heatChanges.at(-1), { planet: "Sun", aspectPartner: "Moon", samplingMode: "common_grid" });
assert.equal(select(heat.target, "Planetary comparison").value, "aspects");

const emptyHeat = fixture();
const emptyHeatModel = { ...model, planetaryHeatmaps: computePlanetaryHeatmaps({ ordinalEpoch: "unix_day", rows: [], zodiacSystem: "sidereal", aspectOrbDegrees: 3 }) };
render(emptyHeat.target, emptyHeatModel, heatCallbacks);
emptyHeat.document.getElementById("analysis-comparison-question-planetary").click();
const emptyHeatCells = walk(emptyHeat.target).filter((node) => node.tagName === "button" && String(node.className || "").startsWith("comparison-heatmap-cell"));
assert.equal(emptyHeatCells.length, 108);
assert.ok(emptyHeatCells.every((node) => node.textContent === "—" && node.className.includes("unavailable")));
assert.match(emptyHeat.target.textContent, /Missing shares are shown as dashes/);
assert.ok(!emptyHeat.target.textContent.includes("0.0%"));

const heatError = fixture();
render(heatError.target, { ...model, planetaryHeatmaps: { status: "error", message: "Overview failed" } }, heatCallbacks);
const beforeErrorRequests = heatRequests.length;
heatError.document.getElementById("analysis-comparison-question-planetary").click();
assert.match(heatError.target.textContent, /Overview failed/);
assert.equal(heatRequests.length, beforeErrorRequests, "An overview error must wait for explicit retry");
byText(heatError.target, "button", "Retry heatmap").click();
assert.equal(heatRequests.length, beforeErrorRequests + 1);

// Keep small fractional percentage-point differences readable and normalize
// rounded zero on both sides without suggesting a positive or negative signal.
const preciseHeat = fixture();
const preciseModel = structuredClone(heatModel);
const preciseCells = preciseModel.planetaryHeatmaps.domains.find((domain) => domain.id === "ufo").matrices.zodiac.rows[0].cells;
for (const [index, share, expectedCalendarShare] of [
  [0, 0.2, 0.20001], [1, 0.20001, 0.2], [2, 0.20123, 0.2], [3, 0.2, 0.20123],
]) Object.assign(preciseCells[index], { share, expectedCalendarShare });
render(preciseHeat.target, preciseModel, heatCallbacks);
preciseHeat.document.getElementById("analysis-comparison-question-planetary").click();
const preciseValues = walk(preciseHeat.target).filter((node) => node.tagName === "button" && String(node.className || "").startsWith("comparison-heatmap-cell"))
  .map((node) => node.textContent);
assert.deepEqual(preciseValues.slice(0, 4), ["0.00 pp", "0.00 pp", "+0.12 pp", "-0.12 pp"]);
assert.ok(preciseValues.every((value) => !/^[+-]0\.00 pp$/.test(value)), "Rounded zero must never retain a sign");

// A loading or error state does not retain stale charts. Retry is explicit.
let retried = 0;
render(empty.target, { status: "error", message: "Evidence hash mismatch" }, { retry() { retried += 1; } });
assert.equal(headings(empty.target).length, 0);
byText(empty.target, "button", "Retry loading").click(); assert.equal(retried, 1);
render(empty.target, { status: "calculating" });
assert.match(empty.target.textContent, /Updating comparisons for the selected filters/);
assert.equal(headings(empty.target).length, 0);
render(empty.target, { status: "loading" });
assert.match(empty.target.textContent, /first download.*later selections reuse the loaded data/);
assert.equal(headings(empty.target).length, 0);
console.log("Comparison renderer actual-model counts, uncertainty, settings, focused navigation, unavailable states and evidence export passed.");
