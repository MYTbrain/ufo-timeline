import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
const require = createRequire(import.meta.url), View = require("../analysis_readiness_view.js"), { readinessMatrix } = require("../analysis_view.js");

class Element {
  constructor(tagName, ownerDocument) { this.tagName = tagName; this.ownerDocument = ownerDocument; this.children = []; this.attributes = new Map(); this.events = new Map(); this.ownText = ""; this.style = { setProperty(key, value) { this[key] = value; } }; }
  appendChild(el) { this.children.push(el); el.parentNode = this; return el; }
  append(...els) { els.forEach(el => this.appendChild(el)); }
  replaceChildren(...els) { this.children.forEach(el => { el.parentNode = null; }); this.children = []; this.ownText = ""; this.append(...els); }
  set textContent(value) { this.replaceChildren(); this.ownText = String(value); }
  get textContent() { return this.ownText + this.children.map(child => child.textContent).join(" "); }
  setAttribute(key, value) { this.attributes.set(key, String(value)); }
  getAttribute(key) { return this.attributes.get(key) ?? null; }
  addEventListener(key, fn) { if (!this.events.has(key)) this.events.set(key, []); this.events.get(key).push(fn); }
  dispatchEvent(event) { event.target ||= this; event.preventDefault ||= () => { event.defaultPrevented = true; }; return Promise.all((this.events.get(event.type) || []).map(fn => fn(event))); }
  click() { return this.disabled ? Promise.resolve() : this.dispatchEvent({ type: "click" }); }
  focus() { this.ownerDocument.activeElement = this; }
  querySelectorAll(selector) { const selectors = selector.split(",").map(value => value.trim()); return walk(this).slice(1).filter(el => selectors.some(value => value === el.tagName)); }
}
const walk = root => [root, ...root.children.flatMap(walk)];
const cls = (root, value) => walk(root).filter(el => String(el.className || "").split(" ").includes(value));
const byAttribute = (root, name, value) => walk(root).find(el => el.getAttribute(name) === value);
function fixture(api = View) { const doc = { createElement(tag) { return new Element(tag, this); } }, target = doc.createElement("div"), calls = [], view = api.create(target, { onOpenSection(...args) { calls.push(args); } }); return { doc, target, calls, view }; }
const gate = (key, inputN, passedN, status, extra = {}) => ({ gateId: key, label: key.replace(/_/g, " "), status, inputN, passedN, unit: "records", policyId: "preserved_policy", evidenceHash: "abc123", ...extra });
const strictGates = [gate("crop_exact_site_formation_date", 7745, 1, "blocked", { reasonCodes: ["joint_site_date_review_requirement"] }), gate("crop_strict_context_clusters", 1, 1, "blocked", { unit: "clusters", minimumRequiredN: 25, reasonCodes: ["minimum_25_context_clusters_required"] })];
const strictAudit = { minimumStrictClusters: 25, eligibleUnit: "clusters", inventoryUnit: "records", cohortBalance: { strictUniqueClusters: 1, sourceFamilyClusterCounts: { familyA: 1, familyB: 1 }, qualifyingMacroregionsAtLeast25: [], maximumSourceFamilyShare: 1, maximumMacroregionShare: 1,
  policy: { minimumStrictUniqueClusters: 100, minimumSourceFamilies: 2, minimumMacroregions: 2, minimumClustersPerMacroregion: 25, maximumSourceFamilyOrMacroregionShare: .6 } } };
const source = [
  { key: "ufoCraftPoints", label: "Qualified UFO report points", status: "ready_inferential", eligibleN: 33800, totalN: 702893, reasons: ["First explicit reason", "Second explicit reason"], gates: [gate("source_coordinates", 702893, 582877, "ready_inferential")] },
  { key: "crop_strict", label: "Strict crop association", status: "blocked", eligibleN: 1, totalN: 7745, evidenceAudit: strictAudit, reasons: ["Joint source review not met", "More clusters required", "Joint source review not met"], gates: strictGates },
  { key: "cropBounded", label: "Bounded crop markers", status: "ready_sensitivity", eligibleN: 427, totalN: 7745, evidenceAudit: { ...strictAudit, eligibleUnit: "records" }, gates: [gate("crop_bounded_marker_lane", 7745, 427, "ready_sensitivity"), ...strictGates.map(value => ({ ...value, applicableToLane: false }))] },
  { key: "cropCircles", label: "Crop marker aggregate", status: "ready_sensitivity", eligibleN: 3652, totalN: 7745, gates: [] },
  { key: "militaryFacilities", label: "Military facilities", status: "limited", eligibleN: 70, totalN: 1800, gates: [gate("facility_inferential_markers", 1800, 70, "limited")] },
  { key: "researchFacilities", label: "Research facilities", status: "limited", eligibleN: 70, totalN: 1800, gates: [gate("facility_inferential_markers", 1800, 70, "limited")] },
  { key: "claimedUfoSites", label: "Claimed UFO sites", status: "ready_descriptive", eligibleN: 0, totalN: 11, reasonCodes: ["descriptive_only_prohibited_from_inference"], gates: [] },
  { key: "relationshipReconciliation", label: "Relationship review", status: "ready_descriptive", eligibleN: null, totalN: 1804, gates: [gate("relationship_reconciliation", 1804, null, "not_evaluated"), gate("relationship_inference", null, null, "data_unavailable")] },
  { key: "unknown_lane", label: "<img src=x>", status: "data_unavailable", eligibleN: null, totalN: null, gates: [] }
];
const matrix = readinessMatrix(source), matrixBefore = JSON.stringify(matrix), scope = { kind: "release_inventory", label: "Release-wide evidence inventory", activeQueryReports: 15, activeQualifiedEndpoints: 2 };
const f = fixture();
f.view.render({ matrix: { status: "loading" } }); assert.match(f.target.textContent, /Loading evidence requirements/); assert.equal(walk(f.target).find(el => el.getAttribute("role") === "status").tagName, "div");
f.view.render({ matrix, scope });
assert.match(f.target.textContent, /9 analysis lanes/); assert.match(f.target.textContent, /not a quality score/); assert.match(f.target.textContent, /do not change with the date controls/);
assert.match(cls(f.target, "analysis-readiness-status-summary")[0].textContent, /1 lane with qualified inputs/); assert.match(cls(f.target, "analysis-readiness-status-summary")[0].textContent, /2 sensitivity lanes/); assert.match(cls(f.target, "analysis-readiness-status-summary")[0].textContent, /2 descriptive lanes/); assert.match(cls(f.target, "analysis-readiness-status-summary")[0].textContent, /2 limited lanes/); assert.match(cls(f.target, "analysis-readiness-status-summary")[0].textContent, /1 blocked lane/);
assert.match(f.target.textContent, /15 reports in the current filters · 2 qualified endpoints/); assert.match(f.target.textContent, /different denominators/);
assert.equal(cls(f.target, "analysis-readiness-inspector").length, 1, "one focused inspector replaces an unreadable wall of lane cards");
assert.match(cls(f.target, "analysis-readiness-inspector")[0].textContent, /33,800/); assert.match(cls(f.target, "analysis-readiness-inspector")[0].textContent, /702,893/);
assert.match(cls(f.target, "analysis-readiness-lane-reasons")[0].textContent, /First explicit reason · Second explicit reason/);
assert.equal(cls(f.target, "analysis-readiness-original").length, 0, "the dense original matrix is available on demand without occupying the landing view");
assert.equal(cls(f.target, "analysis-readiness-gate-detail").length, 0, "detailed policies and hashes are built only when opened");
assert.doesNotMatch(f.target.textContent, /\[object Object\]/, "typed actions are explained with their source reason rather than stringified objects");
let family = byAttribute(f.target, "data-readiness-family", "crops"); family.focus(); await family.click();
assert.equal(f.view.getState().laneKey, "crop_strict"); assert.equal(f.doc.activeElement.getAttribute("data-readiness-family"), "crops", "family selection restores the focused button after replacing the DOM");
let inspector = cls(f.target, "analysis-readiness-inspector")[0];
assert.match(inspector.textContent, /Eligible unique context clusters/); assert.match(inspector.textContent, /Catalog records \(different unit\)/);
assert.match(inspector.textContent, /Strict cluster minimum 1 \/ 25/); assert.match(inspector.textContent, /Balanced cohort size 1 \/ 100/);
assert.deepEqual(cls(inspector, "analysis-readiness-milestone-track").map(el => el.children[0].style.width), ["4%", "1%"], "strict cluster counts are compared with the two actual typed policy targets");
assert.match(inspector.textContent, /Recorded source families 2 · minimum 2/); assert.match(inspector.textContent, /Macroregions with ≥25 clusters 0 · minimum 2/); assert.match(inspector.textContent, /Largest source-family share 100.0% · maximum 60%/); assert.match(inspector.textContent, /Largest macroregion share 100.0% · maximum 60%/);
assert.match(inspector.textContent, /meeting one count target does not satisfy the other evidence requirements/);
const releaseNotes = cls(inspector, "analysis-readiness-release-notes")[0]; assert.equal(releaseNotes.open, false); assert.match(releaseNotes.textContent, /Additional release notes · 2/); assert.equal(cls(inspector, "analysis-readiness-lane-reasons").length, 0, "blocked lanes keep repeated release-level reasons out of the default inspector");
releaseNotes.open = true; await releaseNotes.dispatchEvent({ type: "toggle" }); assert.equal(cls(releaseNotes, "analysis-readiness-lane-reasons")[0].textContent, "Joint source review not met · More clusters required", "the disclosure preserves each distinct exact reason once");
assert.equal(inspector.children.filter(el => String(el.className).startsWith("analysis-readiness-retention")).length, 0, "unique clusters divided by catalog records is never drawn as a lane-retention bar");
assert.match(inspector.textContent, /Failed defined checks · 2/); assert.match(inspector.textContent, /1 \/ 1/);
assert.ok(cls(inspector, "analysis-readiness-retention").some(el => String(el.className).includes("is-blocked") && el.textContent.trim() === "1 / 1"), "a 1/1 recorded gate ratio remains visibly blocked when the required minimum is unmet");
assert.match(inspector.textContent, /not a sequential funnel or a readiness percentage/);
assert.match(inspector.textContent, /Separate gate counts/); assert.doesNotMatch(inspector.textContent, /Independent gate counts/);
let details = cls(inspector, "analysis-readiness-all-gates")[0]; details.open = true; await details.dispatchEvent({ type: "toggle" });
assert.equal(cls(details, "analysis-readiness-gate-detail").length, 2); assert.match(details.textContent, /preserved_policy/); assert.match(details.textContent, /abc123/);
const sourceDetail = cls(cls(details, "analysis-readiness-gate-detail")[1], "analysis-readiness-disclosure")[0]; sourceDetail.open = true; await sourceDetail.dispatchEvent({ type: "toggle" }); assert.match(sourceDetail.textContent, /"minimumRequiredN": 25/);
details.open = false; await details.dispatchEvent({ type: "toggle" }); details.open = true; await details.dispatchEvent({ type: "toggle" }); assert.equal(cls(details, "analysis-readiness-gate-detail").length, 2, "reopening advanced details does not duplicate the gate list");
const strictTab = byAttribute(f.target, "data-readiness-lane", "crop_strict"); strictTab.focus(); await strictTab.dispatchEvent({ type: "keydown", key: "ArrowDown" });
assert.equal(f.view.getState().laneKey, "cropBounded"); assert.equal(f.doc.activeElement.getAttribute("data-readiness-lane"), "cropBounded", "arrow-key lane navigation selects and focuses the next tab");
inspector = cls(f.target, "analysis-readiness-inspector")[0]; assert.match(inspector.textContent, /Sensitivity use/); assert.match(inspector.textContent, /No recorded blocking checks for this lane/); assert.equal(cls(inspector, "analysis-readiness-issues").length, 0, "an available lane does not begin with a red empty failure section");
assert.equal(cls(inspector, "analysis-readiness-assessment-disclosure")[0].open, false, "unavailable or separate-result details initially stay collapsed for available lanes");
assert.equal(cls(inspector, "analysis-readiness-milestones").length, 0, "strict count targets are not presented as failures of an available marker lane");
assert.equal(cls(inspector, "analysis-readiness-gate-retention").length, 1, "context-only strict gates are not promoted as failures or retention checks of an available marker lane");
const aggregate = byAttribute(f.target, "data-readiness-lane", "cropCircles"); await aggregate.click(); inspector = cls(f.target, "analysis-readiness-inspector")[0];
assert.match(inspector.textContent, /Included in summary/); assert.match(inspector.textContent, /3,652/); assert.doesNotMatch(inspector.textContent, /No test defined in this release/);
let mobileFamily = byAttribute(f.target, "data-readiness-control", "family"); mobileFamily.value = "facilities"; mobileFamily.focus(); await mobileFamily.dispatchEvent({ type: "change" });
assert.equal(f.view.getState().groupKey, "facilities"); assert.equal(f.doc.activeElement.getAttribute("data-readiness-control"), "family");
assert.match(cls(f.target, "analysis-readiness-inspector")[0].textContent, /share the same facility inventory/);
let mobileLane = byAttribute(f.target, "data-readiness-control", "lane"); mobileLane.value = "claimedUfoSites"; mobileLane.focus(); await mobileLane.dispatchEvent({ type: "change" });
inspector = cls(f.target, "analysis-readiness-inspector")[0]; assert.match(inspector.textContent, /Inferentially eligible records 0/); assert.match(inspector.textContent, /Descriptive inventory records 11/); assert.match(inspector.textContent, /explicitly excludes this descriptive inventory from inference/);
const open = cls(inspector, "analysis-readiness-open-section")[0]; await open.click(); assert.equal(f.calls.at(-1)[0], "facilities"); assert.equal(f.calls.at(-1)[1].lane, "claimedUfoSites");
family = byAttribute(f.target, "data-readiness-family", "relationships"); await family.click(); inspector = cls(f.target, "analysis-readiness-inspector")[0];
const relationshipAssessments = cls(inspector, "analysis-readiness-assessment-disclosure")[0]; assert.equal(relationshipAssessments.open, false); relationshipAssessments.open = true; await relationshipAssessments.dispatchEvent({ type: "toggle" });
assert.match(inspector.textContent, /Checks without an available result · 2/); assert.match(inspector.textContent, /Not assessed/); assert.match(inspector.textContent, /Unavailable/); assert.doesNotMatch(inspector.textContent, /Failed defined checks · 2/);
const raw = cls(f.target, "analysis-readiness-original-disclosure")[0]; raw.open = true; await raw.dispatchEvent({ type: "toggle" }); assert.equal(cls(raw, "analysis-readiness-original").length, 1);
assert.equal(cls(raw, "analysis-readiness-original")[0].children.find(el => el.tagName === "tbody").children.length, source.length); assert.match(raw.textContent, /Gate matrix by analysis lane/); assert.match(raw.textContent, /not independent coverage counts/);
raw.open = false; await raw.dispatchEvent({ type: "toggle" }); raw.open = true; await raw.dispatchEvent({ type: "toggle" }); assert.equal(cls(raw, "analysis-readiness-original").length, 1);
const focused = byAttribute(f.target, "data-readiness-control", "lane"); focused.focus(); f.view.render({ matrix, scope: { ...scope, activeQueryReports: 100, activeQualifiedEndpoints: 5 } });
assert.equal(f.doc.activeElement.getAttribute("data-readiness-control"), "lane", "incoming data rerenders preserve the focused native selector"); assert.match(f.target.textContent, /100 reports in the current filters/); assert.match(f.target.textContent, /1,804/);
assert.equal(JSON.stringify(matrix), matrixBefore, "rendering never mutates original gate values, counts, statuses, policies or hashes");
assert.equal(walk(f.target).some(el => el.tagName === "img"), false, "all source labels remain plain text");
const other = byAttribute(f.target, "data-readiness-family", "other"); await other.click(); assert.match(f.target.textContent, /<img src=x>/); assert.match(cls(f.target, "analysis-readiness-lane-numbers")[0].textContent, /Not available/);
const otherAssessments = cls(f.target, "analysis-readiness-assessment-disclosure")[0]; assert.equal(otherAssessments.open, false); otherAssessments.open = true; await otherAssessments.dispatchEvent({ type: "toggle" });
assert.match(f.target.textContent, /No separate gate result/); assert.match(f.target.textContent, /Some requirements may be evaluated together in the joint checks; an absent separate result is not a failed check/);
f.view.render({ matrix: { rows: [] } }); assert.match(f.target.textContent, /No missing requirement is counted as a failed test/);
const fallbackGlobal = {}; runInNewContext(readFileSync(new URL("../analysis_readiness_view.js", import.meta.url), "utf8"), { globalThis: fallbackGlobal }); const fallback = fixture(fallbackGlobal.UfoAnalysisReadinessView); fallback.view.render({ matrix, scope });
assert.match(fallback.target.textContent, /summary is unavailable/); const fallbackDetails = cls(fallback.target, "analysis-readiness-disclosure")[0]; fallbackDetails.open = true; await fallbackDetails.dispatchEvent({ type: "toggle" }); assert.equal(cls(fallbackDetails, "analysis-readiness-original").length, 1, "the original evidence matrix survives even if the optional explanatory model is absent");
const withoutTargets = fixture(); withoutTargets.view.render({ matrix: readinessMatrix([{ ...source[1], evidenceAudit: undefined }]), scope });
assert.equal(cls(withoutTargets.target, "analysis-readiness-milestones").length, 0, "strict milestone targets are never guessed when the typed audit metadata is absent");
const noClusters = fixture(); noClusters.view.render({ matrix: readinessMatrix([{ ...source[1], eligibleN: 0, evidenceAudit: { ...strictAudit, cohortBalance: { ...strictAudit.cohortBalance, strictUniqueClusters: 0, sourceFamilyClusterCounts: {}, maximumSourceFamilyShare: 0, maximumMacroregionShare: 0 } } }]), scope });
assert.deepEqual(cls(noClusters.target, "analysis-readiness-milestone-track").map(el => el.children[0].style.width), ["0%", "0%"]); assert.match(noClusters.target.textContent, /Not measurable: 0 clusters/); assert.doesNotMatch(cls(noClusters.target, "analysis-readiness-balance-facts")[0].textContent, /0.0%/, "an empty cohort's placeholder max-share zero is not presented as measured low concentration");
const reconciled = fixture(); reconciled.view.render({ matrix: readinessMatrix([{ key: "relationshipReconciliation", label: "Relationship inventory", status: "ready_descriptive", eligibleN: 0, totalN: 1804, gates: [gate("relationship_reconciliation", 1804, 1320, "limited"), gate("relationship_inference", 1804, 0, "blocked")] }]), scope });
const relationshipNumbers = cls(reconciled.target, "analysis-readiness-lane-numbers")[0];
assert.match(relationshipNumbers.textContent, /Association-eligible relationship records 0/); assert.match(relationshipNumbers.textContent, /1,804/); assert.match(relationshipNumbers.textContent, /Reconciled relationship records 1,320/, "usable reconciled inventory is shown separately from zero association eligibility");
assert.equal(relationshipNumbers.children.length, 3);
f.view.destroy(); f.view.render({ matrix, scope }); assert.equal(f.target.children.length, 0, "destroyed readiness views cannot return after late work completes");
console.log("Analysis readiness view checks passed.");
