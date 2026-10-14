import assert from "node:assert/strict";
import fs from "node:fs";
import zlib from "node:zlib";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url), api = require("../encounter_evidence.js");
const manifest = JSON.parse(fs.readFileSync("data/encounters/manifest.json", "utf8"));
const base = api.createIndex(JSON.parse(zlib.gunzipSync(fs.readFileSync("data/encounters/evidence.json.gz"))));
const entry = manifest.labelOrigins, bytes = fs.readFileSync("data/encounters/" + entry.file), decoded = zlib.gunzipSync(bytes);
const hash = value => createHash("sha256").update(value).digest("hex");
assert.equal(hash(bytes), entry.gzipSha256); assert.equal(hash(decoded), entry.decodedSha256);
const payload = JSON.parse(decoded), index = api.createLabelOriginsIndex(payload, base, manifest.artifact.decodedSha256);
assert.equal(index.rowCount, 16319);
for (const row of payload.rows) {
  const value = api.decorate({ event_id: Number(row.eventId), source: row.source }, base, index);
  assert.equal(value.encounterEvidenceProvenanceReady, true);
  assert.equal(value.encounterSourceBeingMask | value.encounterNarrativeBeingMask, value.encounterBeingMask);
}
assert.throws(() => api.createLabelOriginsIndex(payload, base, "0".repeat(64)), /base hash/);
const bad = structuredClone(payload); bad.rows[0].sourceRef.detailIndex += 1;
assert.throws(() => api.createLabelOriginsIndex(bad, base, manifest.artifact.decodedSha256), /identity/);
assert.equal(api.decorate({ event_id: 123, source: "unknown" }, base, index).encounterEvidenceProvenanceReady, true);
assert.equal(api.decorate({ event_id: Number(payload.rows[0].eventId), source: "wrong" }, base, index).encounterEvidenceProvenanceReady, false);
console.log("All 16,319 label-origin identities/masks, hash pins, atomic refusal and unavailable-source behavior passed.");
