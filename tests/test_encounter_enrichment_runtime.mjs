import assert from "node:assert/strict";
import fs from "node:fs";
import zlib from "node:zlib";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url), api = require("../encounter_evidence.js");
const manifest = JSON.parse(fs.readFileSync("data/encounters/manifest.json", "utf8"));
const base = api.createIndex(JSON.parse(zlib.gunzipSync(fs.readFileSync("data/encounters/evidence.json.gz"))));
const entry = manifest.enrichment, bytes = fs.readFileSync("data/encounters/" + entry.file), decoded = zlib.gunzipSync(bytes);
const hash = value => createHash("sha256").update(value).digest("hex");
assert.equal(hash(bytes), entry.gzipSha256); assert.equal(hash(decoded), entry.decodedSha256);
const payload = JSON.parse(decoded), index = api.createEnrichmentIndex(payload, base, manifest.artifact.decodedSha256);
assert.equal(payload.sourceEntries.length, 24); assert.equal(payload.cases.length, 20);
assert.equal(payload.episodes.length, 25); assert.equal(payload.entityObservations.length, 36);
assert.equal(index.rowCount, 25); assert.equal(payload.reportLinks.filter(row => row.acceptedForRuntime).length, 22);
for (const link of payload.reportLinks) {
  const value = index.get(link.eventId); assert.ok(value);
  assert.equal(value.links[0].status, link.status);
  if (link.status !== "linked") assert.equal(value.links[0].acceptedForRuntime, false);
}
assert.ok(payload.episodes.every(row => row.time.utcVerified === false && row.time.utcStartMs == null && row.time.utcEndMs == null));
assert.ok(payload.episodes.every(row => row.site.sourceVerified === false && row.site.lat == null && row.site.lon == null));
assert.throws(() => api.createEnrichmentIndex(payload, base, "0".repeat(64)), /catalog\/base/);
const bad = structuredClone(payload), hold = bad.reportLinks.find(row => row.status === "candidate"); hold.acceptedForRuntime = true;
assert.throws(() => api.createEnrichmentIndex(bad, base, manifest.artifact.decodedSha256), /unreviewed/);
const wrong = structuredClone(payload), pinned = wrong.reportLinks.find(row => base.has(row.eventId)); pinned.sourceRef.detailIndex += 1;
assert.throws(() => api.createEnrichmentIndex(wrong, base, manifest.artifact.decodedSha256), /identity/);
assert.ok(index.get(payload.reportLinks[0].eventId), "Rejected replacements do not mutate the accepted index");
console.log("Reviewed pilot runtime: 24 entries, 25 pinned links, 22 accepted and 3 held; entity/episode attribution, null UTC/sites and atomic refusal passed.");
