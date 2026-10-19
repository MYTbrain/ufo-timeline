import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createRequire } from "node:module";
import { gzipSync, gunzipSync } from "node:zlib";
import { createHash, webcrypto } from "node:crypto";
const require = createRequire(import.meta.url), Sources = require("../analysis_session_sources.js"), Inspect = require("../analysis_session_inspection.js");
const domainBase = "https://assets.example/releases/";
const compressed = value => {
  const decoded = Buffer.from(JSON.stringify(value)), bytes = gzipSync(decoded);
  return { bytes, declaration: { bytes: bytes.length, decodedBytes: decoded.length, sha256: createHash("sha256").update(bytes).digest("hex") } };
};
const payloads = new Map(), requests = []; let active = 0, maximumActive = 0;
function addArtifact(path, data) { const item = compressed(data); payloads.set(domainBase + path, item.bytes); return { ...item.declaration, path: path.slice(path.indexOf("/") + 1) }; }
const crop0 = addArtifact("crops/details/chunk_000.json.gz", {
  crop_a: { id: "crop_a", eventId: 999999, location: "Hoeven, Netherlands", country: "Netherlands", catalogSummary: "Reported catalog formation; attribution unreviewed.", sourceFamilies: ["Crop Circle Center"], sources: [{ name: "Crop Circle Center", recordUrl: "https://sources.example/exact-crop-a" }], mappingNotes: "Locality centroid only.", legalPublicationRestriction: false },
  crop_b: { id: "crop_b", location: "Wiltshire, England", catalogSummary: "Reported crop formation.", sourceFamilies: ["Archive"], sources: [{ name: "Archive", collectionUrl: "https://archive.example/catalog/" }] },
});
const crop1 = addArtifact("crops/details/chunk_001.json.gz", { crop_z: { id: "crop_z", location: "Late fixture", catalogSummary: "Later chunk.", sources: [{ recordUrl: "javascript:alert(1)" }], links: ["https://archive.example/"] } });
const cropManifest = { releaseId: "pinned-crops", assetBaseUrl: domainBase + "crops/", counts: { events: 251 }, details: { chunkSize: 250, files: [crop0, crop1] } };
const animalCatalog = addArtifact("animals/catalog.json.gz", [ ["animal_a", "Named animal account", "Catalog summary", "Crosby County, Texas", "1978-08-10", "1978-08-10", 0, [1], false, 0] ]);
animalCatalog.recordCount = 1;
const animalDetail = addArtifact("animals/details/chunk_000.json.gz", { animal_a: { id: "animal_a", title: "Reviewed animal account", location: "Crosby County, Texas", summary: "Published rumor resolved as natural death.", sourceRefs: [{ publisher: "The Crosbyton Review", url: "https://texashistory.example/page" }], legalPublicationRestriction: false } });
const animalManifest = { releaseId: "pinned-animals", assetBaseUrl: domainBase + "animals/", catalog: animalCatalog, details: { chunkSize: 250, files: [animalDetail] } };
payloads.set("https://preview.example/data/crop_circles/manifest.json", Buffer.from(JSON.stringify(cropManifest)));
payloads.set("https://preview.example/data/animal_mutilations/manifest.json", Buffer.from(JSON.stringify(animalManifest)));
const fetcher = async url => { requests.push(String(url)); active++; maximumActive = Math.max(maximumActive, active); await new Promise(resolve => setImmediate(resolve)); active--; return new Response(payloads.get(String(url)) || "missing", { status: payloads.has(String(url)) ? 200 : 404 }); };
const loader = Sources.create({ fetch: fetcher, crypto: webcrypto, baseUrl: "https://preview.example/index.html" });
const row = (kind, id, rank, extra = {}) => ({ id, label: id, date: "Recorded source date", location: "Country only", source: "legacy_sf_hash", detail: "Date role: catalog unspecified", eventIds: [], contextRecord: { kind, id, rank }, ...extra });
const input = { title: "Exact category", unit: "crop catalog records", groups: { A: { totalN: 9, matchedN: 9, offset: 0, hasMore: false, rows: [row("crops", "crop_a", 0), row("crops", "crop_b", 1), row("animals", "animal_a", 0)] },
  B: { totalN: 32, matchedN: 32, offset: 25, hasMore: true, rows: [row("crops", "crop_a", 0), row("crops", "crop_z", 250), { id: "held1", label: "Held UFO", eventIds: ["held1"], source: "original" }] } }, notes: ["Original scientific note."] };
const original = JSON.stringify(input), result = await loader.enrich(input);
assert.equal(JSON.stringify(input), original, "Source decoration never mutates worker result or held records");
for (const slot of ["A", "B"]) for (const key of ["totalN", "matchedN", "offset", "hasMore"]) assert.equal(result.groups[slot][key], input.groups[slot][key]);
const crop = result.groups.A.rows[0]; assert.equal(crop.label, "Reported crop formation · Hoeven, Netherlands"); assert.equal(crop.location, "Hoeven, Netherlands"); assert.equal(crop.source, "Crop Circle Center");
assert.equal(crop.sourceUrl, "https://sources.example/exact-crop-a"); assert.equal(crop.sourceLinkLabel, "Source record"); assert.equal(crop.date, "Recorded source date"); assert.deepEqual(crop.eventIds, [], "Numeric overlay eventId is never promoted into a UFO join");
assert.match(crop.detail, /Date role: catalog unspecified/); assert.match(crop.detail, /Locality centroid only/);
assert.equal(result.groups.A.rows[1].sourceLinkLabel, "Source catalog / archive", "Archive fallback is labeled as a catalog, not a case-level source");
assert.equal(result.groups.A.rows[2].label, "Reviewed animal account"); assert.equal(result.groups.A.rows[2].source, "The Crosbyton Review"); assert.equal(result.groups.A.rows[2].sourceUrl, "https://texashistory.example/page");
assert.equal(result.groups.B.rows[1].sourceUrl, "https://archive.example/"); assert.equal(result.groups.B.rows[2], input.groups.B.rows[2], "Unrelated held UFO rows remain untouched");
assert.equal(requests.filter(url => url.endsWith("crops/details/chunk_000.json.gz")).length, 1, "A/B page lookups share in-flight exact chunk requests");
assert.ok(maximumActive <= 6);

const pair = await loader.enrich({ groups: { A: { rows: [row("crops", "crop_a", 0, { id: "crop_a|nuclear_test", label: "Catalog crop_a / test", detail: "Pair distance 20 km." })] } } });
assert.match(pair.groups.A.rows[0].label, /Reported crop formation.*Catalog crop_a \/ test/); assert.match(pair.groups.A.rows[0].detail, /Pair distance 20 km/); assert.deepEqual(pair.groups.A.rows[0].eventIds, []);
const badRank = await loader.enrich({ groups: { A: { rows: [row("crops", "crop_a", 250)] } } });
assert.equal(badRank.groups.A.rows[0].sourceMetadataStatus, "unavailable"); assert.match(badRank.groups.A.rows[0].sourceMetadataError, /exact context ID is absent/); assert.equal(badRank.groups.A.rows[0].label, "crop_a");
const noRank = await loader.enrich({ groups: { A: { rows: [row("crops", "crop_a", null)] } } }); assert.match(noRank.groups.A.rows[0].sourceMetadataError, /validated full-catalog rank/);

// Fail closed on bytes/hash errors, retain counts, then retry successfully.
let failures = true; const retryRequests = [];
const retry = Sources.create({ baseUrl: "https://preview.example/", crypto: webcrypto, fetch: async url => {
  retryRequests.push(url); const value = payloads.get(String(url));
  return new Response(failures && String(url).endsWith("crops/details/chunk_000.json.gz") ? Buffer.from(value).map((byte, index) => index === 10 ? byte ^ 1 : byte) : value);
} });
const one = { groups: { A: { totalN: 1, matchedN: 1, rows: [row("crops", "crop_a", 0)] } } };
const failed = await retry.enrich(one); assert.match(failed.groups.A.rows[0].sourceMetadataError, /SHA-256/); assert.equal(failed.groups.A.matchedN, 1); assert.match(failed.notes.join(" "), /Retry opening/);
failures = false; const recovered = await retry.enrich(one); assert.equal(recovered.groups.A.rows[0].sourceMetadataStatus, "ready"); assert.equal(retryRequests.filter(url => String(url).endsWith("crops/details/chunk_000.json.gz")).length, 2, "Failed chunk promises are evicted so retry can recover");
const decodedFailure = Sources.create({ baseUrl: "https://preview.example/", crypto: webcrypto, fetch: fetcher, decompress: bytes => Buffer.concat([gunzipSync(bytes), Buffer.from(" ")]) });
assert.match((await decodedFailure.enrich(one)).groups.A.rows[0].sourceMetadataError, /Decoded source metadata exceeds|decoded-byte count/);

// Full-catalog ranks come from exact IDs across both groups' shared original
// catalog, not the selected page or date-filtered subset.
const context = { crops: [{ id: "crop_z", startOrdinal: 1, endOrdinal: 1, morphology: ["disc"] }, { id: "crop_a", startOrdinal: 0, endOrdinal: 0, morphology: ["disc"] }, { id: "crop_b", startOrdinal: 1, endOrdinal: 1, morphology: ["ring"] }] };
const held = { cohort: { eventIds: [], scope: { timeRange: { mode: "window", startOrdinal: 1, endOrdinal: 1 } } }, rows: [] };
const inspected = Inspect.inspect({ groups: { A: held, B: held }, context, domainKey: "crops_morphology", rowKey: "disc" });
assert.deepEqual(inspected.groups.A.rows[0].contextRecord, { kind: "crops", id: "crop_z", rank: 2 }); assert.deepEqual(inspected.groups.A.rows[0].eventIds, []);
const browser = vm.createContext({ URL, TextDecoder, Uint8Array, Blob, Response, DecompressionStream }); vm.runInContext(fs.readFileSync("analysis_session_sources.js", "utf8"), browser);
const injected = browser.UfoAnalysisSessionSources.create({ fetch: fetcher, crypto: webcrypto, baseUrl: "https://preview.example/" }); assert.equal((await injected.enrich(one)).groups.A.rows[0].sourceMetadataStatus, "ready");
console.log("Exact source metadata: readable crop/animal identities, verified URLs and archive labels, original dates/counts/joins preserved, pinned compressed hashes and decoded sizes, bounded shared requests, retry after failure, pair endpoint decoration and full-catalog ranks passed.");
