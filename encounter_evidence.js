(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module && module.exports) module.exports = api;
  if (root) {
    root.UFOEncounterEvidence = api;
    root.UfoEncounterEvidence = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const SCHEMA_ID = "ufo-encounter-evidence-v1";
  const RELEASE_ID = "encounters-20261013-v1";
  const CATALOG_COUNT = 702893;
  const TAXONOMY = Object.freeze([
    ["grey", "Grey", "described_type"], ["nordic", "Nordic", "described_type"],
    ["reptilian", "Reptilian", "described_type"], ["mantis_like", "Mantis-like", "described_type"],
    ["insectoid", "Insectoid", "described_type"], ["human_like", "Human-like", "appearance"],
    ["humanoid", "Humanoid", "appearance"], ["small_humanoid", "Small humanoid", "appearance"],
    ["tall_humanoid", "Tall humanoid", "appearance"], ["giant", "Giant", "appearance"],
    ["hairy", "Hairy", "appearance"], ["robotic", "Robotic", "appearance"],
    ["luminous", "Luminous", "appearance"], ["animal_like", "Animal-like", "appearance"],
    ["men_in_black", "Men in black", "reported_context"], ["apparition", "Apparition", "reported_context"],
    ["mixed", "Mixed types", "coverage"], ["other_described", "Other described being", "coverage"],
    ["unspecified", "Unspecified being", "coverage"],
  ].map(function (row, index) { return Object.freeze({ key: row[0], label: row[1], group: row[2], bit: index }); }));
  const TYPE_BY_KEY = new Map(TAXONOMY.map(function (entry) { return [entry.key, entry]; }));
  const ALL_BEING_MASK = (Math.pow(2, TAXONOMY.length) - 1) >>> 0;
  const ABDUCTION_CODES = Object.freeze({ "": 0, source_reported: 1, narrative_reported: 2, ambiguous: 3 });
  const ASSOCIATION_CODES = Object.freeze({ not_established: 0, explicit: 1, co_reported: 2, none_reported: 3 });
  const ABDUCTION_LABELS = Object.freeze([
    "No indexed abduction evidence", "Abduction reported · source classification", "Abduction reported · narrative", "Abduction category or mention · unclear",
  ]);
  const ASSOCIATION_LABELS = Object.freeze([
    "Craft association not established", "Explicit craft association in the report", "Craft and beings co-reported", "No craft association reported",
  ]);

  function requireValue(condition, message) {
    if (!condition) throw new Error("Encounter evidence refused: " + message);
  }
  function plain(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value) &&
      (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null);
  }
  function nonempty(value) { return typeof value === "string" && value.trim().length > 0; }
  function validHash(value) { return typeof value === "string" && /^[a-f0-9]{64}$/i.test(value); }
  function identifier(value) {
    if (typeof value === "number") return Number.isSafeInteger(value) && value > 0 ? String(value) : "";
    if (typeof value !== "string" || !/^[1-9]\d*$/.test(value)) return "";
    return Number.isSafeInteger(Number(value)) ? value : "";
  }
  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (character) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character];
    });
  }
  function beingMask(keys) {
    requireValue(Array.isArray(keys), "being types must be an array");
    const seen = new Set();
    let mask = 0;
    keys.forEach(function (key) {
      requireValue(typeof key === "string" && TYPE_BY_KEY.has(key) && !seen.has(key), "unknown or repeated being type");
      seen.add(key);
      mask |= 1 << TYPE_BY_KEY.get(key).bit;
    });
    return mask >>> 0;
  }
  function validMask(value) { return Number.isInteger(value) && value >= 0 && value <= ALL_BEING_MASK && (value & ~ALL_BEING_MASK) === 0; }
  function beingTypes(mask) {
    requireValue(validMask(mask), "invalid being type mask");
    return TAXONOMY.filter(function (entry) { return (mask & (1 << entry.bit)) !== 0; }).map(function (entry) { return entry.key; });
  }
  function beingLabel(key, index) {
    const taxonomy = index && Array.isArray(index.taxonomy) ? index.taxonomy : TAXONOMY;
    const entry = taxonomy.find(function (value) { return value.key === key; });
    return entry ? entry.label : "Unknown being category";
  }
  function abductionLabel(code) { return ABDUCTION_LABELS[code] || ABDUCTION_LABELS[0]; }
  function craftAssociationLabel(code) { return ASSOCIATION_LABELS[code] || ASSOCIATION_LABELS[0]; }

  function createIndex(payload) {
    requireValue(plain(payload) && payload.schemaId === SCHEMA_ID && payload.releaseId === RELEASE_ID &&
      payload.catalogCount === CATALOG_COUNT && (payload.schemaVersion == null || payload.schemaVersion === 1), "unsupported release or catalog schema");
    requireValue(Array.isArray(payload.taxonomy) && payload.taxonomy.length === TAXONOMY.length, "incomplete being taxonomy");
    const taxonomy = payload.taxonomy.map(function (entry, position) {
      requireValue(plain(entry) && entry.key === TAXONOMY[position].key && nonempty(entry.label) && nonempty(entry.group), "unknown, repeated, or reordered taxonomy key");
      return Object.freeze({ key: entry.key, label: entry.label, group: entry.group, bit: position });
    });
    Object.freeze(taxonomy);
    requireValue(Array.isArray(payload.rows) && payload.rows.length <= CATALOG_COUNT, "invalid sparse row collection");
    if (payload.rowCount != null) requireValue(payload.rowCount === payload.rows.length, "partial sparse evidence collection");
    const records = new Map();
    const abductionCounts = [0, 0, 0, 0];
    const associationCounts = [0, 0, 0, 0];
    const typeCounts = Object.fromEntries(taxonomy.map(function (entry) { return [entry.key, 0]; }));
    let beingReportCount = 0;
    payload.rows.forEach(function (row, position) {
      requireValue(plain(row) && typeof row.eventId === "string" && identifier(row.eventId) && !records.has(row.eventId), "invalid or duplicate event ID at row " + position);
      requireValue(nonempty(row.source) && typeof row.sourceEventId === "string", "missing source identity at row " + position);
      requireValue(Object.prototype.hasOwnProperty.call(ABDUCTION_CODES, row.abductionStatus) &&
        Object.prototype.hasOwnProperty.call(ASSOCIATION_CODES, row.craftAssociation), "unknown encounter status at row " + position);
      const mask = beingMask(row.beingTypes);
      requireValue(Array.isArray(row.evidence) && row.evidence.length > 0, "missing source evidence at row " + position);
      const evidence = row.evidence.map(function (entry) {
        requireValue(plain(entry) && nonempty(entry.field) && nonempty(entry.excerpt) && nonempty(entry.ruleId), "incomplete evidence excerpt at row " + position);
        return Object.freeze({ field: entry.field, excerpt: entry.excerpt, ruleId: entry.ruleId });
      });
      const ref = row.sourceRef;
      requireValue(plain(ref) && typeof ref.chunk === "string" && /^chunk_\d{6}(?:\.json(?:\.gz)?)?$/.test(ref.chunk) &&
        Number.isSafeInteger(ref.detailIndex) && ref.detailIndex >= 0 && validHash(ref.chunkSha256), "invalid source locator or hash at row " + position);
      const record = {
        eventId: row.eventId, source: row.source, sourceEventId: row.sourceEventId,
        abductionStatus: row.abductionStatus, beingTypes: Object.freeze(row.beingTypes.slice()), craftAssociation: row.craftAssociation,
        evidence: Object.freeze(evidence),
        sourceRef: Object.freeze({ chunk: ref.chunk, detailIndex: ref.detailIndex, chunkSha256: ref.chunkSha256.toLowerCase() }),
        encounterAbductionCode: ABDUCTION_CODES[row.abductionStatus], encounterBeingMask: mask,
        encounterCraftAssociationCode: ASSOCIATION_CODES[row.craftAssociation], encounterEvidenceReady: true,
      };
      if (row.heightFeet != null) {
        requireValue(typeof row.heightFeet === "number" && Number.isFinite(row.heightFeet) && row.heightFeet > 0, "invalid reported height at row " + position);
        record.heightFeet = row.heightFeet;
      }
      if (row.uniform != null) {
        requireValue(typeof row.uniform === "boolean" || nonempty(row.uniform), "invalid uniform description at row " + position);
        record.uniform = row.uniform;
      }
      if (row.reviewFlags != null) {
        requireValue(Array.isArray(row.reviewFlags) && row.reviewFlags.every(nonempty) && new Set(row.reviewFlags).size === row.reviewFlags.length, "invalid review flags at row " + position);
        record.reviewFlags = Object.freeze(row.reviewFlags.slice());
      }
      records.set(row.eventId, Object.freeze(record));
      abductionCounts[record.encounterAbductionCode] += 1;
      associationCounts[record.encounterCraftAssociationCode] += 1;
      if (mask) beingReportCount += 1;
      row.beingTypes.forEach(function (key) { typeCounts[key] += 1; });
    });
    // No caller-visible index is returned until every source row has validated.
    return Object.freeze({
      ready: true, status: "ready", releaseId: payload.releaseId, catalogCount: CATALOG_COUNT, rowCount: records.size, taxonomy,
      get: function (id) { return records.get(identifier(id)) || null; },
      has: function (id) { return records.has(identifier(id)); },
      snapshot: function () {
        return { status: "ready", ready: true, releaseId: payload.releaseId, catalogCount: CATALOG_COUNT,
          rowCount: records.size, indexedCount: records.size, notIndexedCount: CATALOG_COUNT - records.size,
          abductionReportedCount: abductionCounts[1] + abductionCounts[2], sourceClassifiedAbductionCount: abductionCounts[1],
          narrativeAbductionCount: abductionCounts[2], ambiguousAbductionCount: abductionCounts[3],
          abductionNotIndexedCount: CATALOG_COUNT - abductionCounts[1] - abductionCounts[2] - abductionCounts[3],
          beingReportCount, beingNotIndexedCount: CATALOG_COUNT - beingReportCount,
          beingTypeCounts: Object.assign({}, typeCounts), craftAssociationCounts: associationCounts.slice(),
          taxonomy: taxonomy.map(function (entry) { return Object.assign({}, entry); }) };
      },
    });
  }

  function decorate(event, index) {
    if (!event || typeof event !== "object") return event;
    const ready = Boolean(index && index.ready === true && typeof index.get === "function");
    const record = ready ? index.get(event.event_id == null ? event.eventId : event.event_id) : null;
    const mismatch = Boolean(record && sourceIdentityMismatch(event, record));
    return Object.assign({}, event, {
      encounterAbductionCode: record && !mismatch ? record.encounterAbductionCode : 0,
      encounterBeingMask: record && !mismatch ? record.encounterBeingMask : 0,
      encounterCraftAssociationCode: record && !mismatch ? record.encounterCraftAssociationCode : 0,
      encounterEvidenceReady: ready && !mismatch,
      encounterIdentityMismatch: mismatch,
    });
  }
  function parsedFilters(filters) {
    const value = filters || {};
    const abduction = value.abduction == null ? "any" : value.abduction;
    const being = value.being == null ? "any" : value.being;
    requireValue(["any", "reported", "source_reported", "ambiguous", "not_indexed"].includes(abduction), "unknown abduction filter");
    requireValue(["any", "reported", "not_indexed"].includes(being), "unknown being filter");
    const keys = value.beingTypes == null ? [] : value.beingTypes;
    const mask = beingMask(keys);
    return { abduction, being, mask };
  }
  function normalizeFilters(filters) {
    const selected = parsedFilters(filters);
    return { abduction: selected.abduction, being: selected.being, beingTypes: beingTypes(selected.mask) };
  }
  function matches(event, filters) {
    const raw = filters || {};
    // The ordinary catalog path runs for every report; an inactive selection
    // needs neither an evidence lookup nor a taxonomy traversal.
    if ((raw.abduction == null || raw.abduction === "any") && (raw.being == null || raw.being === "any") &&
        (raw.beingTypes == null || Array.isArray(raw.beingTypes) && raw.beingTypes.length === 0)) return true;
    let selected;
    try { selected = parsedFilters(raw); } catch (error) { return false; }
    if (!event || event.encounterEvidenceReady !== true) return false;
    const abduction = event.encounterAbductionCode;
    const mask = event.encounterBeingMask;
    if (!Number.isInteger(abduction) || abduction < 0 || abduction > 3 || !validMask(mask)) return false;
    if (selected.abduction === "reported" && abduction !== 1 && abduction !== 2) return false;
    if (selected.abduction === "source_reported" && abduction !== 1) return false;
    if (selected.abduction === "ambiguous" && abduction !== 3) return false;
    if (selected.abduction === "not_indexed" && abduction !== 0) return false;
    if (selected.being === "reported" && mask === 0) return false;
    if (selected.being === "not_indexed" && mask !== 0) return false;
    return selected.mask === 0 || (mask & selected.mask) !== 0;
  }

  function resolveRecord(value, index) {
    if (value == null) return null;
    if (index && typeof index.get === "function") {
      const id = typeof value === "object" ? (value.event_id == null ? value.eventId : value.event_id) : value;
      const record = index.get(id);
      return record && typeof value === "object" && sourceIdentityMismatch(value, record) ? null : record;
    }
    return typeof value === "object" ? value : null;
  }
  function sourceIdentityMismatch(event, record) {
    return event && event.source != null && event.source !== "" && event.source !== record.source;
  }
  function renderBadges(value, index) {
    const record = resolveRecord(value, index);
    if (!record || record.encounterEvidenceReady !== true) return "";
    const badges = [];
    if (record.encounterAbductionCode) badges.push('<span class="badge badge-encounter badge-encounter-abduction">' + escapeHtml(abductionLabel(record.encounterAbductionCode)) + '</span>');
    if (validMask(record.encounterBeingMask) && record.encounterBeingMask) {
      badges.push('<span class="badge badge-encounter badge-encounter-beings">Reported beings: ' +
        beingTypes(record.encounterBeingMask).map(function (key) { return escapeHtml(beingLabel(key, index)); }).join(" · ") + '</span>');
    }
    return badges.join("");
  }
  function renderEvidence(value, index) {
    const record = resolveRecord(value, index);
    if (!record || record.encounterEvidenceReady !== true || !record.sourceRef || !Array.isArray(record.evidence)) {
      return "";
    }
    const categories = beingTypes(record.encounterBeingMask).map(function (key) { return beingLabel(key, index); });
    const facts = [
      ["Abduction", abductionLabel(record.encounterAbductionCode)],
      ["Reported beings", categories.length ? categories.join(" · ") : "No indexed being description"],
      ["Craft association", craftAssociationLabel(record.encounterCraftAssociationCode)],
    ];
    if (record.heightFeet != null) facts.push(["Reported height", String(record.heightFeet) + " feet"]);
    if (record.uniform != null) facts.push(["Uniform in source", typeof record.uniform === "boolean" ? (record.uniform ? "Reported" : "Not reported in the source field") : record.uniform]);
    const ref = record.sourceRef;
    const html = '<section class="detail-block encounter-evidence"><h4>Reported encounters</h4><p class="note-copy">These categories describe retained source claims. They do not verify an abduction, identify a biological species, or establish that reports concern the same craft.</p>' +
      '<dl class="encounter-evidence-facts">' + facts.map(function (pair) { return '<dt>' + escapeHtml(pair[0]) + '</dt><dd>' + escapeHtml(pair[1]) + '</dd>'; }).join("") + '</dl>' +
      '<div class="encounter-evidence-excerpts">' + record.evidence.map(function (entry) {
        return '<div class="encounter-evidence-excerpt"><p class="note-copy">Source field: <strong>' + escapeHtml(entry.field) + '</strong> · Rule: ' + escapeHtml(entry.ruleId) + '</p><blockquote>' + escapeHtml(entry.excerpt) + '</blockquote></div>';
      }).join("") + '</div>' +
      (record.reviewFlags && record.reviewFlags.length ? '<p class="note-copy">Review notes: ' + record.reviewFlags.map(escapeHtml).join(" · ") + '</p>' : '') +
      '<details class="encounter-evidence-provenance"><summary>Source provenance</summary><dl>' +
      [["Event ID", record.eventId], ["Source", record.source], ["Source event ID", record.sourceEventId || "Not supplied"],
        ["Detail chunk", ref.chunk], ["Detail index", ref.detailIndex], ["Original chunk SHA-256", ref.chunkSha256]].map(function (pair) {
        return '<dt>' + escapeHtml(pair[0]) + '</dt><dd>' + escapeHtml(pair[1]) + '</dd>';
      }).join("") + '</dl></details></section>';
    return html;
  }

  async function verifyHash(bytes, expectedHash, label) {
    requireValue(validHash(expectedHash) && typeof crypto !== "undefined" && crypto.subtle && typeof crypto.subtle.digest === "function", label + " integrity pin or verification is unavailable");
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    const actual = Array.from(new Uint8Array(digest), function (value) { return value.toString(16).padStart(2, "0"); }).join("");
    requireValue(actual === expectedHash.toLowerCase(), label + " hash mismatch");
  }
  async function decodeEvidenceResponse(response, expected) {
    const pins = expected || {};
    requireValue(response && response.ok && typeof response.arrayBuffer === "function", "evidence response failed");
    let bytes = new Uint8Array(await response.arrayBuffer());
    if (bytes[0] === 0x1f && bytes[1] === 0x8b) {
      if (pins.gzipBytes != null) requireValue(bytes.byteLength === pins.gzipBytes, "compressed length mismatch");
      await verifyHash(bytes, pins.gzipSha256, "compressed payload");
      requireValue(typeof DecompressionStream === "function", "gzip decoding is unavailable");
      bytes = new Uint8Array(await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"))).arrayBuffer());
    }
    // Content-Encoding may already have decompressed the response; always verify
    // decoded bytes and never treat decompression as evidence of integrity.
    if (pins.bytes != null) requireValue(bytes.byteLength === pins.bytes, "decoded length mismatch");
    await verifyHash(bytes, pins.sha256 || pins.decodedSha256, "decoded payload");
    const payload = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
    if (pins.rowCount != null) requireValue(Array.isArray(payload.rows) && payload.rows.length === pins.rowCount, "delivery row count mismatch");
    return payload;
  }

  return Object.freeze({ SCHEMA_ID, RELEASE_ID, CATALOG_COUNT, TAXONOMY, ALL_BEING_MASK, ABDUCTION_CODES, ASSOCIATION_CODES,
    createIndex, decorate, normalizeFilters, matches, beingMask, beingTypes, beingLabel, abductionLabel, craftAssociationLabel,
    renderBadges, renderEvidence, decodeEvidenceResponse, escapeHtml });
});
