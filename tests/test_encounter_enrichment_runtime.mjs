import assert from "node:assert/strict";
import fs from "node:fs";
import zlib from "node:zlib";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url), api = require("../encounter_evidence.js");
const manifest = JSON.parse(fs.readFileSync("data/encounters/manifest.json", "utf8"));
const basePayload = JSON.parse(zlib.gunzipSync(fs.readFileSync("data/encounters/evidence.json.gz")));
const base = api.createIndex(basePayload, manifest.attributeReviews, manifest.artifact.decodedSha256);
assert.equal(manifest.attributeReviews.rows.length, 5);
for (const review of manifest.attributeReviews.rows) {
  assert.equal(base.get(review.eventId).heightFeet, undefined);
  assert.equal(base.get(review.eventId).reportedHeightFeet, review.originalHeightFeet);
  assert.ok(base.get(review.eventId).measurementReview);
}
const entry = manifest.enrichment, bytes = fs.readFileSync("data/encounters/" + entry.file), decoded = zlib.gunzipSync(bytes);
const hash = value => createHash("sha256").update(value).digest("hex");
assert.equal(hash(bytes), entry.gzipSha256); assert.equal(hash(decoded), entry.decodedSha256);
const payload = JSON.parse(decoded), index = api.createEnrichmentIndex(payload, base, manifest.artifact.decodedSha256);
const priorPilot = {
  sources: [9, "3527802067415492cba8b3952f0ac1a36b11574f5e56aff01008b86578d6f56e"],
  sourceEntries: [24, "54f22d670a24030d7dc30aeeef816666f4f5b3d133513f23bbe2ec25b743b8a8"],
  cases: [20, "67ed1aabbca44fdc07398663cc5bf88b315c9ad2a78c9cccf91ff1186974a603"],
  episodes: [25, "dc7c1412b00ac4c725551a8c41c29c16f56a64bd60197d9b239eb62aacce094c"],
  entityObservations: [36, "f654c77d067c8283bac6f63938c8add72ba4bf6658b5dd75b6c0b532e9e0b852"],
  reportLinks: [25, "f4227b5df5a2dc37d0346f831ed6302c8c32dd8acad4024fd41d3187b79a0df4"],
};
for (const [key, [count, digest]] of Object.entries(priorPilot)) {
  assert.equal(hash(JSON.stringify(payload[key].slice(0, count))), digest, `Preserved pilot ${key}`);
  assert.equal(payload[key].length, entry.counts[key], `Runtime/manifest ${key}`);
}
assert.equal(index.rowCount, 202);
assert.equal(payload.reportLinks.filter(row => row.acceptedForRuntime).length, 127);
assert.deepEqual(entry.reviewBatch, { reviewedAccounts: 177, linked: 105, candidate: 69, contradicted: 3 });
for (const link of payload.reportLinks) {
  const value = index.get(link.eventId); assert.ok(value);
  const actual = value.links.find(row => row.sourceEntries.some(source => link.sourceEntryIds.includes(source.entryId)));
  assert.ok(actual);
  const revision = (actual.qualityReviews || []).find(row => row.associationRevision?.eventId === link.eventId);
  assert.equal(actual.status, revision ? revision.associationRevision.status : link.status);
  if (link.status !== "linked" && !revision) assert.equal(actual.acceptedForRuntime, false);
}
assert.ok(payload.episodes.every(row => row.time.utcVerified === false && row.time.utcStartMs == null && row.time.utcEndMs == null));
assert.ok(payload.episodes.every(row => row.site.sourceVerified === false && row.site.lat == null && row.site.lon == null));
assert.throws(() => api.createEnrichmentIndex(payload, base, "0".repeat(64)), /catalog\/base/);
const bad = structuredClone(payload), hold = bad.reportLinks.find(row => row.status === "candidate"); hold.acceptedForRuntime = true;
assert.throws(() => api.createEnrichmentIndex(bad, base, manifest.artifact.decodedSha256), /unreviewed/);
const wrong = structuredClone(payload), pinned = wrong.reportLinks.find(row => base.has(row.eventId)); pinned.sourceRef.detailIndex += 1;
assert.throws(() => api.createEnrichmentIndex(wrong, base, manifest.artifact.decodedSha256), /identity/);
assert.ok(index.get(payload.reportLinks[0].eventId), "Rejected replacements do not mutate the accepted index");
const added = id => payload.sourceEntries.find(row => row.externalSourceEntryId === id);
const entitiesFor = id => payload.entityObservations.filter(row => row.sourceEntryIds.includes(added(id).entryId));
const padova = entitiesFor("rosales-original:1994:139:3c7d3ac26f92");
assert.equal(padova.length, 1); assert.equal(padova[0].count, 1);
assert.ok(padova[0].attributes.some(row => row.field === "reported_claim" && /fourteen.*not seen/.test(row.value)), "Unseen others remain a claim, not visible-entity counts");
const ipswich = entitiesFor("rosales-original:1996:120:faa666c99a65");
assert.ok(ipswich.some(row => row.reportedTypes.includes("luminous")));
assert.ok(ipswich.every(row => !row.reportedTypes.includes("small_humanoid")), "Unresolved shape cannot establish humanoid form");
for (const id of ["rosales-original:1994:233:cf6949d17f9b", "rosales-original:1996:175:cb0bfa56bc2d"]) assert.equal(entitiesFor(id).length, 0);
const calama = index.get("4258007715704332").links;
assert.ok(calama.some(row => row.status === "contradicted"));
assert.ok(calama.every(row => !row.acceptedForRuntime), "Matching citation/date/place cannot override incompatible event accounts");
for (const episode of payload.episodes.filter(row => row.scope === "source_account_unsplit")) {
  assert.equal(episode.date.startIso, null); assert.equal(episode.date.endIso, null);
}
for (const entity of payload.entityObservations.slice(36)) {
  for (const attribute of entity.attributes) if (entity.scope === "group" && attribute.attribution === "explicit_individual") {
    assert.equal(attribute.subjectScope, "one_unresolved_member");
    assert.ok(entity.reviewFlags.includes("individual_attribute_target_not_separately_identified"));
  }
}
assert.equal(hash(zlib.gunzipSync(fs.readFileSync("data/encounters/evidence.json.gz"))), "0a26ec2f83c9c2f368c9e457c94d7ec0d651f8da514cdfd27662ee2735bbe8b8", "Base classifications remain unchanged");
assert.equal(payload.qualityReviews.length, 8);
const poole = index.get("3356684600748588").links.find(row => row.case.caseId === "case:poole");
assert.ok(poole.acceptedForRuntime);
assert.equal(poole.originalStatus, "candidate");
assert.ok(poole.episodes[0].date.conflicts.length > 0, "Resolved identity does not erase conflicting years");
assert.equal(new Set(payload.reportLinks.map(row => row.eventId)).size, index.rowCount);
let effectiveAccepted = 0;
for (const id of new Set(payload.reportLinks.map(row => row.eventId))) effectiveAccepted += index.get(id).links.filter(row => row.acceptedForRuntime).length;
assert.equal(effectiveAccepted, 128);
const wrongReview = structuredClone(payload); wrongReview.qualityReviews[0].associationRevision.previousStatus = "contradicted";
assert.throws(() => api.createEnrichmentIndex(wrongReview, base, manifest.artifact.decodedSha256), /unreviewed association revision/);
console.log("Reviewed runtime: all prior rows preserved; eight source reviews, one resolved identity, five disputed height values withheld, 128 effective accepted links; UTC/sites remain unknown.");
