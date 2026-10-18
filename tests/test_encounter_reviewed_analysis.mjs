import assert from "node:assert/strict";
import fs from "node:fs";
import zlib from "node:zlib";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const encounters = require("../encounter_evidence.js");
const stats = require("../analysis_stats.js");
const { AnalysisViewController } = require("../analysis_view.js");
const read = file => JSON.parse(fs.readFileSync(file, "utf8"));
const unzip = file => JSON.parse(zlib.gunzipSync(fs.readFileSync(file)));
const manifest = read("data/encounters/manifest.json");
const payload = unzip("data/encounters/evidence.json.gz");
const base = encounters.createIndex(payload, manifest.attributeReviews, manifest.artifact.decodedSha256);
const origins = encounters.createLabelOriginsIndex(unzip("data/encounters/label_origins.json.gz"), base, manifest.artifact.decodedSha256);
const enrichmentPayload = unzip("data/encounters/" + manifest.enrichment.file);
const enrichment = encounters.createEnrichmentIndex(enrichmentPayload, base, manifest.artifact.decodedSha256);

class Element {
  constructor(tagName) { this.tagName = tagName; this.children = []; this.ownText = ""; this.events = new Map(); }
  appendChild(node) { this.children.push(node); return node; }
  set textContent(value) { this.ownText = String(value); this.children = []; }
  get textContent() { return this.ownText + this.children.map(node => node.textContent).join(" "); }
  addEventListener(name, callback) { this.events.set(name, callback); }
  click() { this.events.get("click")?.({ target: this }); }
}
const document = { createElement(tag) { return new Element(tag); } };
const controller = Object.assign(Object.create(AnalysisViewController.prototype), { document });
const walk = node => [node, ...node.children.flatMap(walk)];
let renderedLinks = 0, renderedFindings = 0, renderedEntities = 0, outsideBase = 0;
const seenReviews = new Set(), seenEntities = new Set();
for (const id of new Set(enrichmentPayload.reportLinks.map(link => link.eventId))) {
  const context = enrichment.get(id), target = new Element("div");
  controller._appendEncounterEnrichment(target, context);
  assert.ok(!target.textContent.includes("[object Object]"), `${id}: structured source locators remain readable`);
  assert.equal(walk(target).filter(node => node.className === "encounter-reviewed-link").length, context.links.length);
  if (!base.has(id)) outsideBase++;
  for (const link of context.links) {
    renderedLinks++;
    for (const entity of link.entityObservations) {
      renderedEntities++;
      seenEntities.add(entity.entityObservationId);
      for (const attribute of entity.attributes || []) {
        if (attribute.value != null) assert.ok(target.textContent.includes(String(attribute.value)), `${id}: attributed ${attribute.field} is visible`);
        if (attribute.attribution) assert.ok(target.textContent.includes(attribute.attribution), `${id}: attribution remains visible`);
      }
    }
    for (const review of link.qualityReviews) {
      assert.ok(!seenReviews.has(review.reviewId), "Each additional source review is attached once");
      seenReviews.add(review.reviewId);
      for (const finding of review.findings) {
        renderedFindings++;
        assert.ok(target.textContent.includes(finding.text), `${id}: additional-source finding is rendered`);
        const entry = review.sourceEntries.find(value => value.entryId === finding.sourceEntryId);
        assert.ok(entry?.source?.url && walk(target).some(node => node.tagName === "a" && node.href === entry.source.url), `${id}: finding source is inspectable`);
      }
    }
  }
}
assert.equal(renderedLinks, 202);
const unlinkedEntities = enrichmentPayload.entityObservations.filter(entity => !seenEntities.has(entity.entityObservationId));
assert.equal(seenEntities.size, enrichmentPayload.entityObservations.length - 1);
assert.equal(unlinkedEntities.length, 1);
assert.equal(unlinkedEntities[0].episodeId, "episode:torphins-first", "The unlinked first Torphins episode does not acquire an invented catalog association");
assert.equal(renderedFindings, 18);
assert.equal(seenReviews.size, 8);
assert.equal(outsideBase, 2, "Nonvisual/held reviewed accounts do not become positive being classifications");

const browse = [], inventory = new Element("div");
const fields = enrichmentPayload.entityObservations.reduce((sum, entity) => sum + (entity.attributes || []).length, 0);
const unlinkedEntry = enrichmentPayload.sourceEntries.find(entry => entry.entryId === "entry:torphins-first");
const unlinkedAccount = { sourceEntry: { ...unlinkedEntry, source: enrichmentPayload.sources.find(source => source.sourceId === unlinkedEntry.sourceId) },
  case: enrichmentPayload.cases.find(value => value.caseId === unlinkedEntry.caseId),
  episodes: enrichmentPayload.episodes.filter(value => value.episodeId === unlinkedEntry.episodeId), entityObservations: unlinkedEntities };
controller.callbacks = { onEncounterReviewSummaryRequested: () => ({ status: "ready", reportCount: 202, acceptedLinks: 128, heldLinks: 74,
  sourceEntries: 210, entityGroups: 214, attributedFields: fields, sourceReviews: 8, sourceFindings: 18, unclassifiedReports: 2,
  unlinkedSourceEntries: 1, unlinkedSourceAccounts: [unlinkedAccount] }) };
controller._openEncounterReports = (query, detail) => { browse.push({ query, detail }); };
controller._renderEncounterReviewCoverage(inventory);
assert.match(inventory.textContent, /202 catalog reports.*128 accepted associations.*74 candidate or held/);
assert.match(inventory.textContent, /full reviewed collection.*current shared filters and date window/);
assert.match(inventory.textContent, /2 reviewed reports have no indexed being or abduction classification/);
assert.match(inventory.textContent, /1 unlinked source account/);
assert.match(inventory.textContent, /Torphins: first forestry episode/);
assert.match(inventory.textContent, /HC3943/);
assert.match(inventory.textContent, /dark human-shaped/);
assert.match(inventory.textContent, /excluded from report counts, current-cohort lists and comparison charts/);
assert.ok(!inventory.textContent.includes("[object Object]"));
const buttons = walk(inventory).filter(node => node.tagName === "button");
assert.equal(buttons.length, 3);
buttons.forEach(button => button.click());
assert.deepEqual(browse.map(value => value.query), ["all", "accepted", "held"].map(reviewStatus => ({ domain: "reviewed_context", reviewStatus })));
const unavailable = new Element("div");
controller.callbacks.onEncounterReviewSummaryRequested = () => ({ status: "unavailable" });
controller._renderEncounterReviewCoverage(unavailable);
assert.match(unavailable.textContent, /Reviewed source context is unavailable/);
assert.equal(walk(unavailable).filter(node => node.tagName === "button").length, 0);

// Replay the current index through the actual field classifier. This deliberately
// tests the indexed-report population, without inventing absent geography/dates.
const rows = payload.rows.map(record => {
  const decorated = encounters.decorate({ event_id: record.eventId, source: record.source,
    chunk_id: record.sourceRef.chunk, detail_index: record.sourceRef.detailIndex }, base, origins);
  return { ...decorated, eventId: record.eventId, source: record.source };
});
const result = stats.computeAnalysis({ rows, fullTimeRange: true, baselineMode: "full_catalog", quickMode: true,
  selectedDomains: ["encounters"], encounterEvidenceReady: true });
assert.equal(result.encounters.beingRows, 12595);
assert.equal(result.encounters.abductionRows, 3217);
for (const population of ["being", "abduction"]) {
  const atlas = result.encounters.comparisonAtlas.populations[population];
  assert.equal(atlas.axes.filter(axis => axis.status !== "external_comparison").length, 33);
  const height = atlas.axes.find(axis => axis.key === "height");
  const supported = rows.filter(row => (population === "being" ? row.encounterBeingMask > 0 : [1, 2].includes(row.encounterAbductionCode))
    && typeof row.encounterHeightFeet === "number" && Number.isFinite(row.encounterHeightFeet) && row.encounterHeightFeet > 0).length;
  assert.equal(height.coverage.supportedReports, supported);
  for (const axis of atlas.axes.filter(axis => axis.status !== "external_comparison")) {
    assert.equal(axis.coverage.supportedReports + axis.coverage.unknownReports + axis.coverage.notLoadedReports, axis.coverage.eligibleReports);
    assert.equal(axis.coverage.eligibleReports + axis.coverage.excludedReports, atlas.reportCount);
  }
}
for (const review of manifest.attributeReviews.rows) {
  const row = rows.find(value => value.eventId === review.eventId);
  assert.equal(row.encounterHeightFeet, null, "A disputed source unit never re-enters the height comparison");
  const membership = stats.encounterAtlasRowMembership(row, { population: "being" });
  if (membership.eligible) assert.equal(membership.fields.height.state, "unknown");
}
console.log(JSON.stringify({ status: "passed", indexedReports: rows.length, beingReports: result.encounters.beingRows,
  abductionReports: result.encounters.abductionRows, coreAxesPerPopulation: 33, renderedLinks, renderedEntities,
  uniqueEntities: seenEntities.size, attributedFields: fields, renderedFindings, sourceReviews: seenReviews.size, outsideBase,
  withheldHeights: manifest.attributeReviews.rows.length, reviewedContextBrowseControls: buttons.length }));
