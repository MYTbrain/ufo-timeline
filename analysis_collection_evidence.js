(function (root, factory) {
  "use strict";
  const api = factory(typeof module === "object" && module.exports ? require("./encounter_evidence.js") : root.UFOEncounterEvidence);
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UfoAnalysisCollectionEvidence = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function (Encounter) {
  "use strict";
  const SCHEMA_ID = "ufo-collection-evidence-v1", MAX_GZIP = 2 * 1024 * 1024, MAX_DECODED = 5 * 1024 * 1024;
  const pending = new Map();
  const UNKNOWN_BEING = "not_indexed", UNKNOWN = "unknown";
  const SOIL_PLANT = new Set(["soil", "flowers", "grass", "leaves_wood", "crops_fruit", "plants_unspecified", "fungi"]);
  function assert(value, message) { if (!value) throw new Error("Collection evidence: " + message); }
  function array(value) { return Array.isArray(value) ? value : []; }
  function id(value) { return String(value == null ? "" : value); }
  function finite(value) { return typeof value === "number" && Number.isFinite(value); }
  function unknownSelection(value) { return !value || value === "all"; }
  function validHash(value) { return typeof value === "string" && /^[a-f0-9]{64}$/i.test(value); }
  async function sha256(bytes) {
    const webCrypto = typeof crypto !== "undefined" && crypto.subtle ? crypto : typeof require === "function" ? require("node:crypto").webcrypto : null;
    assert(webCrypto, "integrity verification is unavailable");
    const result = await webCrypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(result), function (n) { return n.toString(16).padStart(2, "0"); }).join("");
  }
  async function decodeGzip(bytes) {
    if (typeof DecompressionStream === "function") {
      const reader = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip")).getReader();
      const chunks = []; let count = 0;
      while (true) { const part = await reader.read(); if (part.done) break; count += part.value.byteLength; if (count > MAX_DECODED) { await reader.cancel(); throw new Error("Collection evidence: decoded artifact is too large"); } chunks.push(part.value); }
      const decoded = new Uint8Array(count); let offset = 0; chunks.forEach(function (chunk) { decoded.set(chunk, offset); offset += chunk.byteLength; }); return decoded;
    }
    if (typeof require === "function") return new Uint8Array(require("node:zlib").gunzipSync(bytes, { maxOutputLength: MAX_DECODED }));
    throw new Error("Collection evidence: gzip decoding is unavailable");
  }
  function validate(payload, manifest) {
    assert(payload && payload.schemaId === SCHEMA_ID && payload.schemaVersion === 1, "unsupported payload schema");
    assert(Array.isArray(payload.reports) && Array.isArray(payload.cases) && payload.taxonomy, "missing evidence arrays");
    assert(payload.reports.length === manifest.artifact.reportCount && payload.cases.length === manifest.artifact.caseCount, "partial evidence artifact");
    const seen = new Set();
    payload.reports.forEach(function (row) {
      assert(row && /^[1-9][0-9]+$/.test(id(row.eventId)) && !seen.has(id(row.eventId)), "invalid or repeated report identity"); seen.add(id(row.eventId));
      assert(row.canonicalJoinStatus === "validated_id_source_chunk_index", "unvalidated catalog join");
      assert(["direct_report", "ambiguous", "adjacent", "excluded"].includes(row.disposition), "unknown review disposition");
      assert(Array.isArray(row.materials) && Array.isArray(row.actions) && Array.isArray(row.beingTypes), "invalid facets");
      assert(!(finite(row.startOrdinal) !== finite(row.endOrdinal)) && (!finite(row.startOrdinal) || row.endOrdinal >= row.startOrdinal), "invalid date interval");
    });
    return payload;
  }
  function load(options) {
    options = options || {};
    const manifestUrl = options.manifestUrl || "./data/collections/manifest.json";
    if (pending.has(manifestUrl)) return pending.get(manifestUrl);
    const fetcher = options.fetch || (typeof fetch === "function" ? fetch.bind(globalThis) : null);
    const promise = (async function () {
      assert(fetcher, "fetch is unavailable");
      const response = await fetcher(manifestUrl, { credentials: "same-origin" }); assert(response.ok, "manifest could not be loaded");
      const manifest = await response.json();
      assert(manifest && manifest.schemaId === SCHEMA_ID && manifest.schemaVersion === 1 && manifest.artifact, "unsupported manifest");
      const artifact = manifest.artifact;
      assert(validHash(artifact.gzipSha256) && validHash(artifact.decodedSha256) && artifact.gzipBytes > 0 && artifact.gzipBytes <= MAX_GZIP && artifact.decodedBytes > 0 && artifact.decodedBytes <= MAX_DECODED, "invalid integrity or size limits");
      const artifactBase = artifact.url || "./data/collections/" + artifact.file;
      const artifactUrl = artifactBase + (artifactBase.includes("?") ? "&" : "?") + "sha256=" + artifact.gzipSha256;
      const dataResponse = await fetcher(artifactUrl, { credentials: "same-origin" }); assert(dataResponse.ok, "artifact could not be loaded");
      const bytes = new Uint8Array(await dataResponse.arrayBuffer()); assert(bytes.byteLength <= MAX_DECODED, "artifact is too large");
      // Some servers transparently decode gzip; validate the appropriate pinned bytes.
      const gzip = bytes[0] === 31 && bytes[1] === 139;
      if (gzip) { assert(bytes.byteLength === artifact.gzipBytes && await sha256(bytes) === artifact.gzipSha256, "compressed integrity mismatch"); }
      const decoded = gzip ? await decodeGzip(bytes) : bytes;
      assert(decoded.byteLength === artifact.decodedBytes && await sha256(decoded) === artifact.decodedSha256, "decoded integrity mismatch");
      const payload = validate(JSON.parse(new TextDecoder().decode(decoded)), manifest);
      return Object.assign(payload, { manifest, provenance: { artifact: manifest.artifact, inputPins: manifest.inputPins, canonicalChunkPins: manifest.canonicalChunkPins, builderPin: manifest.builderPin, metadataOverlayReceipt: manifest.metadataOverlayReceipt } });
    })();
    pending.set(manifestUrl, promise);
    promise.catch(function () { if (pending.get(manifestUrl) === promise) pending.delete(manifestUrl); });
    return promise;
  }
  function beingKeys(row) { return row.beingTypes.length ? row.beingTypes : [UNKNOWN_BEING]; }
  function decadeKey(row) {
    if (!finite(row.startOrdinal) || !finite(row.endOrdinal)) return UNKNOWN;
    const first = new Date(row.startOrdinal * 86400000).getUTCFullYear(), last = new Date(row.endOrdinal * 86400000).getUTCFullYear();
    return Math.floor(first / 10) === Math.floor(last / 10) ? String(Math.floor(first / 10) * 10) : UNKNOWN;
  }
  function soilPlant(row) { return ["occupant_soil_plant", "craft_collection"].includes(row.scope) && (row.materials.some(function (value) { return SOIL_PLANT.has(value); }) || row.scope === "occupant_soil_plant" && row.materials.includes("unspecified")); }
  function optionsFor(rows, taxonomy) {
    const known = Encounter && Encounter.TAXONOMY ? Encounter.TAXONOMY.map(function (x) { return { key: x.key, label: x.label }; }) : [];
    function unique(key, label) { return Array.from(new Set(rows.map(key))).sort().map(function (value) { return { key: value, label: label ? label(value) : value }; }); }
    return { materials: taxonomy.materials, actions: taxonomy.actions, beings: known.concat([{ key: UNKNOWN_BEING, label: "No indexed being type" }]),
      countries: unique(function (r) { return r.country || "Unknown / unresolved"; }), decades: unique(decadeKey, function (x) { return x === UNKNOWN ? "Date / decade unresolved" : x + "s"; }),
      sources: unique(function (r) { return r.source; }), scopes: unique(function (r) { return r.scope; }),
      dispositions: [{ key: "direct", label: "Directly described acts" }, { key: "includeuncertain", label: "Include uncertain reports" }, { key: "allcontexts", label: "Include adjacent contexts" }, { key: "controls", label: "Excluded review controls" }] };
  }
  function matrix(rows, materials, columns, keys, multiLabel) {
    const index = new Map(columns.map(function (x, i) { return [x.key, i]; }));
    return { countUnit: "unique catalog reports within each material row", multiLabel: Boolean(multiLabel), columns,
      rows: materials.map(function (material) {
        const subset = rows.filter(function (r) { return r.materials.includes(material.key); }); const cells = columns.map(function () { return 0; });
        subset.forEach(function (r) { new Set(keys(r)).forEach(function (value) { if (index.has(value)) cells[index.get(value)] += 1; }); });
        return { key: material.key, label: material.label, total: subset.length, cells };
      }) };
  }
  function compute(options) {
    options = options || {}; const evidence = options.evidence; assert(evidence && evidence.schemaId === SCHEMA_ID, "evidence is not loaded");
    const all = array(evidence.reports), cases = array(evidence.cases), taxonomy = evidence.taxonomy;
    const available = optionsFor(all, taxonomy);
    const allowed = options.allowedEventIds == null ? null : options.allowedEventIds instanceof Set ? new Set(Array.from(options.allowedEventIds, id)) : new Set(array(options.allowedEventIds).map(id));
    const range = options.range, rangeStart = range && (Array.isArray(range) ? range[0] : range.start), rangeEnd = range && (Array.isArray(range) ? range[1] : range.end);
    const disposition = options.disposition || "direct", accepted = disposition === "controls" ? ["excluded"] : disposition === "allcontexts" ? ["direct_report", "ambiguous", "adjacent"] : disposition === "includeuncertain" ? ["direct_report", "ambiguous"] : ["direct_report"];
    const matchingReports = all.filter(function (row) {
      if (allowed && !allowed.has(id(row.eventId))) return false;
      if (finite(rangeStart) && finite(rangeEnd) && (!finite(row.startOrdinal) || row.endOrdinal < rangeStart || row.startOrdinal > rangeEnd)) return false;
      if (!accepted.includes(row.disposition)) return false;
      if ((options.scope || "soilplants") !== "allmaterials" && !soilPlant(row)) return false;
      if (!unknownSelection(options.material) && !row.materials.includes(options.material)) return false;
      if (!unknownSelection(options.action) && !row.actions.includes(options.action)) return false;
      if (!unknownSelection(options.being) && !beingKeys(row).includes(options.being)) return false;
      if (!unknownSelection(options.country) && (row.country || "Unknown / unresolved") !== options.country) return false;
      if (!unknownSelection(options.decade) && decadeKey(row) !== id(options.decade)) return false;
      if (!unknownSelection(options.source) && row.source !== options.source) return false;
      if (!unknownSelection(options.craft) && (row.craftType || UNKNOWN) !== options.craft) return false;
      if (!unknownSelection(options.abduction) && (row.abductionStatus || "not_indexed") !== options.abduction) return false;
      return true;
    });
    const memberVariantN = matchingReports.filter(function (row) { return row.canonicalPrimaryDiffers === true; }).length;
    const reports = options.includeMemberVariants === true ? matchingReports : matchingReports.filter(function (row) { return row.canonicalPrimaryDiffers !== true; });
    function countBy(key) { const result = {}; reports.forEach(function (row) { const value = key(row); result[value] = (result[value] || 0) + 1; }); return result; }
    const craftColumns = Array.from(new Map(all.map(function (r) { return [r.craftType || UNKNOWN, { key: r.craftType || UNKNOWN, label: r.craftLabel || "Craft not indexed" }]; })).values()).sort(function (a, b) { return a.label.localeCompare(b.label); });
    const abductions = [{ key: "source_reported", label: "Source-classified abduction" }, { key: "narrative_reported", label: "Narrative-reported abduction" }, { key: "ambiguous", label: "Abduction mention unclear" }, { key: "not_indexed", label: "No indexed abduction evidence" }];
    const matrices = {
      being: matrix(reports, taxonomy.materials, available.beings, beingKeys, true),
      action: matrix(reports, taxonomy.materials, taxonomy.actions, function (r) { return r.actions; }, true),
      decade: matrix(reports, taxonomy.materials, available.decades, function (r) { return [decadeKey(r)]; }, false),
      country: matrix(reports, taxonomy.materials, available.countries, function (r) { return [r.country || "Unknown / unresolved"]; }, false),
      source: matrix(reports, taxonomy.materials, available.sources, function (r) { return [r.source]; }, false),
      craft: matrix(reports, taxonomy.materials, craftColumns, function (r) { return [r.craftType || UNKNOWN]; }, false),
      abduction: matrix(reports, taxonomy.materials, abductions, function (r) { return [r.abductionStatus || "not_indexed"]; }, false)
    };
    const stats = { indexedReportN: all.length, filteredReportN: reports.length, memberVariantN, heldMemberVariantN: options.includeMemberVariants === true ? 0 : memberVariantN, includedMemberVariantN: options.includeMemberVariants === true ? memberVariantN : 0, dossierN: cases.length,
      unjoinedDossierN: cases.filter(function (x) { return !array(x.indexedReportIds).length; }).length,
      provisionalFamilyN: new Set(reports.map(function (x) { return x.provisionalGroup || x.sourceFamily || "unjoined:" + x.eventId; })).size,
      unknownBeingN: reports.filter(function (x) { return !x.beingTypes.length; }).length,
      unknownGeographyN: reports.filter(function (x) { return !x.country || x.country === "Unknown / unresolved"; }).length,
      unknownDateN: reports.filter(function (x) { return !finite(x.startOrdinal); }).length,
      dispositionCounts: countBy(function (x) { return x.disposition; }),
      uncertainSourceDateN: reports.filter(function (x) { return x.sourceDatePrecision && x.sourceDatePrecision !== "exact_day"; }).length };
    return { schemaId: SCHEMA_ID, reports, filteredReports: reports, cases, stats, taxonomy, options: Object.assign(available, { crafts: craftColumns, abductions }), matrices, policy: evidence.policy };
  }
  return Object.freeze({ SCHEMA_ID, load, compute, validate, decadeKey, soilPlant });
});
