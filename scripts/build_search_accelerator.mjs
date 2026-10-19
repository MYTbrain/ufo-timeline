/** Exact unions of existing vocabulary postings for common word fragments. */
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import zlib from "node:zlib";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { appendVarint } from "./build_search_index.mjs";
const require = createRequire(import.meta.url);
const Query = require("../search_query.js");
const MIB = 1024 * 1024;
const MAX_TOTAL = 900 * MIB, MAX_ADDITION = 100 * MIB, MAX_PACK = 32 * MIB;
const sha = value => crypto.createHash("sha256").update(value).digest("hex");

export const DEFAULT_TERMS = Object.freeze([...new Set((
  "abcdefghijklmnopqrstuvwxyz0123456789".split("").join(" ") + " " +
  `us uk et ufo uap usa united states america canada mexico brazil argentina chile peru
  england britain scotland ireland france germany italy spain portugal russia china japan india australia
  zealand africa zimbabwe zambia south north east west europe asia
  red white black blue green orange yellow pink purple silver gold brown gray grey dark light lights
  bright glowing luminous metallic color colour
  craft saucer disc disk orb triangle triangular cigar cylinder oval egg diamond sphere spherical
  boomerang chevron rectangle rectangular box fireball cone formation teardrop dumbbell
  object flying aircraft helicopter balloon satellite meteor rocket drone
  being beings humanoid human alien reptilian nordic insect insectoid mantis robot entity creature
  occupant figure tall short small
  abduction abduct contact encounter collection collect soil plant plants sample water animal cow cattle
  mutilation crop circle vegetation grass flower tree rock stone mineral earth sand dirt leaf leaves
  dna blood hair tissue biological material specimen taking taken gather digging
  sighting report witness observation saw seen landed landing trace flight direction time date
  morning evening night midnight radar pilot police military navy army airforce base nuclear missile weapon
  power radiation sound silent noise humming beam shape size speed distance height duration minute hour
  photograph photo video film evidence
  missing memory paralysis telepathy communication school ariel roswell lake forest`
).split(/\s+/).filter(Boolean))].sort());

function readPinned(directory, member) {
  if (path.basename(member.file) !== member.file || member.file.includes("..")) throw new Error("Unsafe index member.");
  const bytes = fs.readFileSync(path.join(directory, member.file));
  if (bytes.length !== member.bytes || sha(bytes) !== member.sha256) throw new Error("Source member pin drift: " + member.file);
  return bytes;
}

export function unionPosting(target, bytes, expectedCount) {
  let ordinal = 0, value = 0, multiplier = 1, count = 0;
  for (const byte of bytes) {
    value += (byte & 127) * multiplier;
    if (byte & 128) multiplier *= 128;
    else {
      ordinal += value;
      if (ordinal >= target.length) throw new Error("Posting ordinal exceeds the corpus.");
      target[ordinal] = 1;
      value = 0; multiplier = 1; count++;
    }
  }
  if (multiplier !== 1 || count !== expectedCount) throw new Error("Source posting is truncated or differs from its frequency.");
}

export async function buildSearchAccelerator(options) {
  const directory = path.resolve(options.directory);
  const manifestPath = path.join(directory, "manifest.json");
  const beforeBytes = fs.readFileSync(manifestPath), beforeSha = sha(beforeBytes);
  if (options.expectedManifestSha256 && options.expectedManifestSha256 !== beforeSha) throw new Error("Source manifest pin drift.");
  const manifest = JSON.parse(beforeBytes.toString("utf8"));
  if (manifest.schemaVersion !== 1 || !manifest.coverage.complete ||
      manifest.coverage.currentCatalogIdSetSha256 !== manifest.coverage.indexedIdSetSha256) throw new Error("Current index coverage is not verified.");
  if (manifest.fragments || manifest.fragmentPacks) throw new Error("An accelerator already exists; no pack or manifest is overwritten.");
  const terms = [...new Set((options.terms || DEFAULT_TERMS).map(term => String(term).toLowerCase()))].sort();
  if (terms.some(term => !Query.isWordFragment(term))) throw new Error("Accelerator terms must be pure Unicode word fragments.");
  const termsSha = sha(Buffer.from(JSON.stringify(terms)));
  const existing = fs.readdirSync(directory, { withFileTypes: true });
  if (existing.some(entry => entry.isDirectory())) throw new Error("Index directory must contain only reviewed derivative files.");
  const initialBytes = existing.reduce((sum, entry) => sum + fs.statSync(path.join(directory, entry.name)).size, 0);
  const additionCap = Math.min(MAX_ADDITION, options.maxAddedBytes ?? MAX_ADDITION);
  const totalCap = Math.min(MAX_TOTAL, options.maxTotalBytes ?? MAX_TOTAL);
  const packCap = Math.min(MAX_PACK, options.maxPackBytes ?? MAX_PACK);
  const proof = { status: "building", sourceManifestSha256: beforeSha,
    currentCatalogIdSetSha256: manifest.coverage.currentCatalogIdSetSha256,
    initialDerivativeBytes: initialBytes, terms, termsSha256: termsSha,
    sourceLexiconSha256: manifest.lexicon.sha256,
    sourcePostingPacks: manifest.postingPacks.map(pack => ({ file: pack.file, bytes: pack.bytes, sha256: pack.sha256 })),
    policy: "Exact vocabulary substring unions only; existing source packs remain unchanged." };
  if (options.proofPath) {
    fs.mkdirSync(path.dirname(options.proofPath), { recursive: true });
    fs.writeFileSync(options.proofPath, JSON.stringify(proof, null, 2) + "\n");
  }
  const lexicon = JSON.parse(zlib.gunzipSync(readPinned(directory, manifest.lexicon)).toString());
  const cachedPacks = new Map();
  function postingBytes(offset, length) {
    const pack = manifest.postingPacks.find(pack => offset >= pack.start && offset + length <= pack.start + pack.bytes);
    if (!pack) throw new Error("Posting crosses source pack boundary.");
    if (!cachedPacks.has(pack.file)) cachedPacks.set(pack.file, readPinned(directory, pack));
    return cachedPacks.get(pack.file).subarray(offset - pack.start, offset - pack.start + length);
  }
  const fragments = [], packs = [];
  const bitmap = new Uint8Array(manifest.recordCount);
  let globalOffset = 0, fd = null, packHash = null, currentPack = null;
  const close = () => {
    if (fd !== null) { fs.closeSync(fd); fd = null; currentPack.sha256 = packHash.digest("hex"); }
  };
  const reserve = addition => {
    if (globalOffset + addition > additionCap || initialBytes + globalOffset + addition > totalCap) {
      throw new Error("Search accelerator reached its bounded disk budget; partial files retained for explicit review.");
    }
  };
  const write = bytes => {
    if (bytes.length > packCap) throw new Error("Fragment member exceeds pack cap.");
    reserve(bytes.length);
    if (!currentPack || currentPack.bytes + bytes.length > packCap) {
      close();
      const file = "fragments_" + String(packs.length).padStart(3, "0") + ".pack";
      currentPack = { file, start: globalOffset, bytes: 0, sha256: null };
      fd = fs.openSync(path.join(directory, file), "wx");
      packs.push(currentPack);
      packHash = crypto.createHash("sha256");
    }
    fs.writeSync(fd, bytes); packHash.update(bytes);
    currentPack.bytes += bytes.length;
    globalOffset += bytes.length;
  };
  try {
    for (let index = 0; index < terms.length; index++) {
      const term = terms[index];
      bitmap.fill(0);
      let wordCount = 0;
      for (const [word, offset, length, count] of lexicon) if (word.includes(term)) {
        unionPosting(bitmap, postingBytes(offset, length), count);
        wordCount++;
      }
      const encoded = { bytes: new Uint8Array(64), length: 0 };
      let previous = 0, count = 0;
      for (let ordinal = 0; ordinal < bitmap.length; ordinal++) if (bitmap[ordinal]) {
        appendVarint(encoded, ordinal - previous); previous = ordinal; count++;
      }
      const offset = globalOffset;
      if (encoded.length) write(encoded.bytes.subarray(0, encoded.length));
      fragments.push([term, encoded.length ? offset : 0, encoded.length, count]);
      options.onProgress?.({ term, terms: terms.length, completed: index + 1, vocabularyMatches: wordCount,
        reportCount: count, fragmentBytes: encoded.length, addedPackBytes: globalOffset });
    }
    close();
    manifest.fragments = fragments;
    manifest.fragmentPacks = packs;
    manifest.fragmentBuild = { algorithm: "exact vocabulary substring union", sourceManifestSha256: beforeSha,
      termsSha256: termsSha, terms: terms.length, addedPackBytes: globalOffset };
    const afterBytes = Buffer.from(JSON.stringify(manifest, null, 2) + "\n");
    const manifestGrowth = Math.max(0, afterBytes.length - beforeBytes.length);
    reserve(manifestGrowth);
    // Preserve the source manifest hash in the QA proof before replacing only
    // this small descriptor. Existing text and posting packs are never written.
    if (!options.proofPath) throw new Error("A QA proof path is required before updating the manifest.");
    Object.assign(proof, { status: "ready_to_update_descriptor", nextManifestSha256: sha(afterBytes),
      fragmentPacks: packs, addedPackBytes: globalOffset, manifestGrowthBytes: manifestGrowth,
      finalDerivativeBytes: initialBytes + globalOffset + afterBytes.length - beforeBytes.length,
      newFilesAbove100MiB: [], sourcePacksChanged: false });
    fs.writeFileSync(options.proofPath, JSON.stringify(proof, null, 2) + "\n");
    if (sha(fs.readFileSync(manifestPath)) !== beforeSha) throw new Error("Manifest changed concurrently; descriptor not replaced.");
    fs.writeFileSync(manifestPath, afterBytes);
    proof.status = "complete";
    fs.writeFileSync(options.proofPath, JSON.stringify(proof, null, 2) + "\n");
    return { manifest, proof };
  } catch (error) { close(); throw error; }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2);
  const option = key => { const index = args.indexOf(key); return index < 0 ? null : args[index + 1]; };
  const directory = option("--index"), proofPath = option("--proof");
  if (!directory || !proofPath) throw new Error("--index and --proof are required.");
  if (!/^d:/i.test(path.resolve(directory))) throw new Error("Full accelerator derivatives must remain on primary data drive D:.");
  buildSearchAccelerator({ directory, proofPath, expectedManifestSha256: option("--expected-manifest-sha256"),
    onProgress: event => process.stdout.write(JSON.stringify(event) + "\n") }).then(result => {
      process.stdout.write(JSON.stringify({ complete: true, terms: result.manifest.fragments.length,
        addedPackBytes: result.proof.addedPackBytes, manifestSha256: result.proof.nextManifestSha256,
        finalDerivativeBytes: result.proof.finalDerivativeBytes }) + "\n");
    }).catch(error => { process.stderr.write(error.stack + "\n"); process.exitCode = 1; });
}
