import assert from "node:assert/strict";
import fs from "node:fs";
import zlib from "node:zlib";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url), api = require("../encounter_evidence.js");
const manifest = JSON.parse(fs.readFileSync("data/encounters/manifest.json", "utf8"));
const payload = JSON.parse(zlib.gunzipSync(fs.readFileSync("data/encounters/enrichment.json.gz")));
const base = api.createIndex(JSON.parse(zlib.gunzipSync(fs.readFileSync("data/encounters/evidence.json.gz"))), manifest.attributeReviews, manifest.artifact.decodedSha256);
const index = api.createEnrichmentIndex(payload, base, manifest.artifact.decodedSha256);
let accepted = 0, held = 0, findings = 0, reviews = 0;
for (const id of new Set(payload.reportLinks.map(row => row.eventId))) {
  const context = index.get(id), html = api.renderReviewedContext(id, index);
  assert.equal(api.renderReviewedContext({ event_id: Number(id) }, index), html);
  assert.match(html, /^<details class="encounter-reviewed-context"><summary>/);
  assert.doesNotMatch(html, /<details[^>]*\bopen(?:\s|=|>)/, "Context starts collapsed on map and Results");
  assert.match(html, /do not add independent incidents/);
  assert.doesNotMatch(html, /C:[/\\]|D:[/\\]|sourceBlockPrivate|narrativeFulltext|capturePath/);
  const values = context.links;
  const expectedFindings = values.reduce((n, link) => n + link.qualityReviews.reduce((sum, review) => sum + review.findings.length, 0), 0);
  assert.equal((html.match(/class="encounter-source-finding"/g) || []).length, expectedFindings);
  findings += expectedFindings;
  reviews += values.reduce((sum, link) => sum + link.qualityReviews.length, 0);
  for (const link of values) {
    accepted += link.acceptedForRuntime ? 1 : 0; held += link.acceptedForRuntime ? 0 : 1;
    assert.ok(html.includes(api.escapeHtml(link.case.title)));
    assert.match(html, /Verified UTC:<\/strong> Not established/);
    assert.ok(link.episodes.every(ep => ep.time.utcVerified === false && ep.site.sourceVerified === false));
  }
}
assert.deepEqual({ accepted, held, findings, reviews }, { accepted: 128, held: 74, findings: 18, reviews: 8 });
const poole = api.renderReviewedContext("3356684600748588", index);
assert.match(poole, /Prior decision retained/); assert.match(poole, /1964/); assert.match(poole, /about 1965/);
assert.match(poole, /Date conflicts retained/); assert.match(poole, /native record cites Harris/);
const calama = api.renderReviewedContext("4258007715704332", index);
assert.match(calama, /Candidate or held association; not accepted/); assert.match(calama, /contradicted/);
assert.equal(api.renderReviewedContext("999", index), "");
assert.equal(api.renderReviewedContext("3356684600748588", null), "");

const malicious = '<img src=x onerror="alert(1)">';
const fake = structuredClone(index.get("3356684600748588"));
fake.links[0].case.title = malicious;
fake.links[0].episodes[0].date.raw = malicious;
fake.links[0].episodes[0].recallStages = [{ method: malicious, content: malicious, status: "planned_only" }];
fake.links[0].sourceEntries[0].source.url = "javascript:alert(1)";
fake.links[0].sourceEntries[0].source.title = malicious;
fake.links[0].sourceEntries[0].locator = malicious;
fake.links[0].sourceEntries[0].capturePath = "C:/private/capture.txt";
fake.links[0].sourceEntries[0].shortExcerpt = "PRIVATE FULL SOURCE NOT FOR DISPLAY";
fake.links[0].qualityReviews[0].findings[0].text = malicious;
fake.links[0].qualityReviews[0].sourceEntries[0].source.url = 'https://example.test/?value=" onclick="alert(1)';
const safe = api.renderReviewedContext("3356684600748588", { ready: true, get: () => fake });
assert.doesNotMatch(safe, /<img|href="javascript:|C:\/private|PRIVATE FULL SOURCE/);
assert.match(safe, /&lt;img/); assert.match(safe, /&quot; onclick=&quot;/);
assert.match(safe, /rel="noopener noreferrer"/); assert.match(safe, /planned only/);
console.log("Shared reviewed encounter context: all 202 associations, 128 effective accepted/74 held, eight reviews/18 findings, collapsed scope/unknowns/recall stages, source safety and private-field exclusion passed.");
