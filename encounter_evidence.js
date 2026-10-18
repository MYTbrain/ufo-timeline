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

  function createIndex(payload, attributeReviews, expectedHash) {
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
    const heightReviews = new Map();
    if (attributeReviews != null) {
      requireValue(attributeReviews.schemaId === "ufo-encounter-attribute-reviews-v1" && validHash(expectedHash) && attributeReviews.baseEvidenceDecodedSha256 === expectedHash && Array.isArray(attributeReviews.rows), "attribute-review base mismatch");
      attributeReviews.rows.forEach(function (review) {
        requireValue(identifier(review.eventId) && !heightReviews.has(review.eventId) && review.action === "withhold_height_feet" && typeof review.originalHeightFeet === "number" && Number.isFinite(review.originalHeightFeet) && review.originalHeightFeet > 0 && nonempty(review.reason) && review.reason.length <= 120 && nonempty(review.reportedMetricText) && review.reportedMetricText.length <= 80, "invalid measurement review");
        heightReviews.set(review.eventId, review);
      });
    }
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
      const measurementReview = heightReviews.get(row.eventId);
      if (measurementReview) {
        const pin = measurementReview.sourceRef || {};
        requireValue(row.source === measurementReview.source && row.sourceEventId === measurementReview.sourceEventId && ref.chunk === pin.chunk && ref.detailIndex === pin.detailIndex && ref.chunkSha256 === pin.chunkSha256 && record.heightFeet === measurementReview.originalHeightFeet, "measurement-review source identity mismatch");
        record.reportedHeightFeet = record.heightFeet;
        delete record.heightFeet;
        record.measurementReview = Object.freeze({ action: measurementReview.action, reason: measurementReview.reason, reportedMetricText: measurementReview.reportedMetricText });
        record.reviewFlags = Object.freeze(Array.from(new Set((record.reviewFlags || []).concat([measurementReview.reason]))));
      }
      records.set(row.eventId, Object.freeze(record));
      abductionCounts[record.encounterAbductionCode] += 1;
      associationCounts[record.encounterCraftAssociationCode] += 1;
      if (mask) beingReportCount += 1;
      row.beingTypes.forEach(function (key) { typeCounts[key] += 1; });
    });
    requireValue(Array.from(heightReviews.keys()).every(function (id) { return records.has(id); }), "measurement-review report missing");
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

  function createLabelOriginsIndex(payload, evidenceIndex, expectedHash) {
    requireValue(payload && payload.schemaId === "ufo-encounter-being-label-origins-v1" && payload.catalogCount === CATALOG_COUNT, "label-origin schema mismatch");
    requireValue(expectedHash && payload.baseEvidenceDecodedSha256 === expectedHash, "label-origin base hash mismatch");
    requireValue(JSON.stringify(payload.taxonomyKeys) === JSON.stringify(TAXONOMY.map(function (value) { return value.key; })), "label-origin taxonomy mismatch");
    requireValue(evidenceIndex && evidenceIndex.ready && Array.isArray(payload.rows) && payload.rows.length === evidenceIndex.rowCount, "label-origin coverage mismatch");
    const records = new Map();
    payload.rows.forEach(function (row) {
      const base = evidenceIndex.get(row.eventId), ref = row.sourceRef || {};
      requireValue(base && !records.has(row.eventId) && row.source === base.source && ref.chunk === base.sourceRef.chunk && ref.detailIndex === base.sourceRef.detailIndex && ref.chunkSha256 === base.sourceRef.chunkSha256, "label-origin identity mismatch");
      requireValue([row.beingMask, row.sourceBeingMask, row.narrativeBeingMask, row.bothBeingMask, row.unknownBeingMask].every(validMask), "invalid label-origin mask");
      requireValue(row.beingMask === base.encounterBeingMask && (row.sourceBeingMask | row.narrativeBeingMask | row.unknownBeingMask) === row.beingMask && (row.sourceBeingMask & row.narrativeBeingMask) === row.bothBeingMask && !(row.unknownBeingMask & (row.sourceBeingMask | row.narrativeBeingMask)), "label-origin mask partition mismatch");
      records.set(row.eventId, Object.freeze(Object.assign({}, row)));
    });
    return Object.freeze({ ready: true, releaseId: payload.releaseId, rowCount: records.size, get: function (id) { return records.get(identifier(id)) || null; } });
  }
  function decorate(event, index, originsIndex) {
    if (!event || typeof event !== "object") return event;
    const ready = Boolean(index && index.ready === true && typeof index.get === "function");
    const record = ready ? index.get(event.event_id == null ? event.eventId : event.event_id) : null;
    const mismatch = Boolean(record && sourceIdentityMismatch(event, record));
    const origins = record && originsIndex && originsIndex.ready && originsIndex.get(record.eventId);
    return Object.assign({}, event, {
      encounterAbductionCode: record && !mismatch ? record.encounterAbductionCode : 0,
      encounterBeingMask: record && !mismatch ? record.encounterBeingMask : 0,
      encounterSourceBeingMask: origins && !mismatch ? origins.sourceBeingMask : 0,
      encounterNarrativeBeingMask: origins && !mismatch ? origins.narrativeBeingMask : 0,
      encounterEvidenceProvenanceReady: Boolean(originsIndex && originsIndex.ready && !mismatch && (!record || origins)),
      encounterCraftAssociationCode: record && !mismatch ? record.encounterCraftAssociationCode : 0,
      encounterHeightFeet: record && !mismatch && record.heightFeet != null ? record.heightFeet : null,
      encounterUniform: record && !mismatch && record.uniform != null
        ? (typeof record.uniform === "boolean" ? (record.uniform ? "Reported" : "Not reported in source field") : record.uniform) : null,
      encounterEvidenceReady: ready && !mismatch,
      encounterIdentityMismatch: mismatch,
    });
  }
  function createEnrichmentIndex(payload, evidenceIndex, expectedHash) {
    requireValue(payload && payload.schemaId === "ufo-encounter-enrichment-v1" && payload.catalogCount === CATALOG_COUNT && payload.baseEvidenceDecodedSha256 === expectedHash, "enrichment catalog/base mismatch");
    const arrays = ["sources", "sourceEntries", "cases", "episodes", "entityObservations", "reportLinks"];
    requireValue(arrays.every(function (key) { return Array.isArray(payload[key]); }), "enrichment tables incomplete");
    function table(key, idKey) { const map = new Map(); payload[key].forEach(function (row) { requireValue(nonempty(row[idKey]) && !map.has(row[idKey]), "enrichment identity collision"); map.set(row[idKey], row); }); return map; }
    const sources = table("sources", "sourceId"), entries = table("sourceEntries", "entryId"), cases = table("cases", "caseId"), episodes = table("episodes", "episodeId"), entities = table("entityObservations", "entityObservationId"), links = new Map();
    const qualityByEntry = new Map(), reviewIds = new Set();
    requireValue(payload.qualityReviews == null || Array.isArray(payload.qualityReviews), "invalid additional-source reviews");
    (payload.qualityReviews || []).forEach(function (review) {
      const subject = entries.get(review.subjectEntryId);
      requireValue(nonempty(review.reviewId) && !reviewIds.has(review.reviewId) && subject && subject.caseId === review.caseId && episodes.has(review.episodeId) && episodes.get(review.episodeId).caseId === review.caseId && (subject.episodeIds || [subject.episodeId]).includes(review.episodeId), "additional-source target identity mismatch");
      requireValue(["additional_source_context", "conflicting_version", "identity_conflict", "source_chain_dependency"].includes(review.disposition) && review.classificationEffect === "none", "invalid additional-source disposition");
      requireValue(Array.isArray(review.sourceEntryIds) && review.sourceEntryIds.length && review.sourceEntryIds.every(function (id) { const entry = entries.get(id); return entry && entry.caseId === review.caseId && entry.episodeId === review.episodeId && sources.has(entry.sourceId); }), "additional-source evidence reference mismatch");
      requireValue(Array.isArray(review.findings) && review.findings.length && review.findings.every(function (fact) { return nonempty(fact.field) && nonempty(fact.text) && fact.text.length <= 650 && review.sourceEntryIds.includes(fact.sourceEntryId); }), "additional-source fact attribution missing");
      if (review.associationRevision) {
        const revision = review.associationRevision;
        const prior = payload.reportLinks.filter(function (link) { return link.eventId === revision.eventId && link.caseId === review.caseId && link.sourceEntryIds.includes(review.subjectEntryId); });
        requireValue(prior.length === 1 && revision.previousStatus === "candidate" && prior[0].status === revision.previousStatus && prior[0].acceptedForRuntime === false && revision.status === "linked" && review.disposition === "additional_source_context" && review.associationEffect === "reviewed_identity_resolution_prior_row_retained" && Array.isArray(revision.identityBasis) && revision.identityBasis.length >= 2 && review.findings.some(function (fact) { return fact.field === "episode_identity"; }), "unreviewed association revision");
      }
      reviewIds.add(review.reviewId);
      if (!qualityByEntry.has(review.subjectEntryId)) qualityByEntry.set(review.subjectEntryId, []);
      qualityByEntry.get(review.subjectEntryId).push(Object.assign({}, review, { sourceEntries: review.sourceEntryIds.map(function (id) { const entry = entries.get(id); return Object.assign({}, entry, { source: sources.get(entry.sourceId) }); }) }));
    });
    payload.reportLinks.forEach(function (link) {
      requireValue(identifier(link.eventId) && nonempty(link.source) && ["linked", "candidate", "contradicted"].includes(link.status), "invalid enrichment report link");
      const base = evidenceIndex.get(link.eventId), ref = link.sourceRef || {};
      requireValue(nonempty(ref.chunk) && Number.isInteger(ref.detailIndex) && ref.detailIndex >= 0 && validHash(ref.chunkSha256), "enrichment source pin missing");
      if (base) requireValue(link.source === base.source && ref.chunk === base.sourceRef.chunk && ref.detailIndex === base.sourceRef.detailIndex && ref.chunkSha256 === base.sourceRef.chunkSha256, "enrichment source identity mismatch");
      requireValue(cases.has(link.caseId) && Array.isArray(link.episodeIds) && link.episodeIds.every(function (id) { return episodes.has(id) && episodes.get(id).caseId === link.caseId; }) && Array.isArray(link.sourceEntryIds) && link.sourceEntryIds.every(function (id) { return entries.has(id); }) && Array.isArray(link.entityObservationIds) && link.entityObservationIds.every(function (id) { return entities.has(id) && link.episodeIds.includes(entities.get(id).episodeId); }), "enrichment reference mismatch");
      requireValue(link.acceptedForRuntime !== true || link.status === "linked", "unreviewed link promoted to runtime");
      const qualityReviews = link.sourceEntryIds.flatMap(function (id) { return qualityByEntry.get(id) || []; });
      const revisions = qualityReviews.filter(function (review) { return review.associationRevision && review.associationRevision.eventId === link.eventId; });
      requireValue(revisions.length <= 1, "conflicting association revisions");
      const item = { status: revisions.length ? "linked" : link.status, acceptedForRuntime: revisions.length ? true : link.acceptedForRuntime === true, originalStatus: link.status, qualityReviews, case: cases.get(link.caseId),
        episodes: link.episodeIds.map(function (id) { return episodes.get(id); }), entityObservations: link.entityObservationIds.map(function (id) { return entities.get(id); }),
        sourceEntries: link.sourceEntryIds.map(function (id) { const entry = entries.get(id); requireValue(sources.has(entry.sourceId), "enrichment source missing"); return Object.assign({}, entry, { source: sources.get(entry.sourceId) }); }),
        matchBasis: link.matchBasis, reviewFlags: link.reviewFlags, sourceRef: ref };
      if (!links.has(link.eventId)) links.set(link.eventId, []); links.get(link.eventId).push(Object.freeze(item));
    });
    return Object.freeze({ ready: true, releaseId: payload.releaseId, rowCount: links.size,
      get: function (id) { const records = links.get(identifier(id)); return records ? Object.freeze({ links: Object.freeze(records.slice()), policy: payload.policy }) : null; } });
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
    if (record.measurementReview) facts.push(["Height comparison", "Withheld: source units conflict (coded value " + record.reportedHeightFeet + "; narrative " + record.measurementReview.reportedMetricText + "). Original fields are preserved."]);
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

  // The same source-reviewed context is available from a map report and Results
  // as from Analysis. Associations stay separate from the base classifications.
  function renderReviewedContext(value, enrichmentIndex) {
    const id = identifier(value && typeof value === "object" ? (value.event_id == null ? value.eventId : value.event_id) : value);
    const enrichment = id && enrichmentIndex && enrichmentIndex.ready === true && typeof enrichmentIndex.get === "function" && enrichmentIndex.get(id);
    const links = enrichment && Array.isArray(enrichment.links) ? enrichment.links : [];
    if (!links.length) return "";
    const label = function (text) { return String(text == null ? "Not recorded" : text).replace(/_/g, " "); };
    const text = function (value) {
      if (value == null || value === "") return "Not recorded";
      if (Array.isArray(value)) return value.map(text).join("; ");
      if (typeof value === "object") return Object.keys(value).map(function (key) { return label(key) + ": " + text(value[key]); }).join("; ");
      return String(value);
    };
    const paragraph = function (name, value) { return '<p class="note-copy"><strong>' + escapeHtml(name) + ':</strong> ' + escapeHtml(text(value)) + '</p>'; };
    const publicSource = function (entry) {
      const source = entry && entry.source || {}, title = entry && entry.title || source.title || "Source title unavailable";
      let link = escapeHtml(title);
      if (typeof source.url === "string" && /^https?:\/\//i.test(source.url)) {
        link = '<a href="' + escapeHtml(source.url) + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(title) + '</a>';
      }
      const locator = entry && entry.locator;
      const located = locator && typeof locator === "object" ? [Number.isInteger(locator.pageIndex) ? "PDF page " + (locator.pageIndex + 1) : "", locator.section ? "section " + locator.section : ""].filter(Boolean).join(" · ") : locator;
      return '<p class="note-copy">' + link + (located ? ' · ' + escapeHtml(text(located)) : '') + '</p>' +
        (entry && entry.upstreamCitation ? paragraph("Cited upstream source", entry.upstreamCitation) : '') +
        (source.dependency ? paragraph("Source relationship", source.dependency) : '');
    };
    const accepted = links.filter(function (link) { return link.acceptedForRuntime === true; }).length;
    return '<details class="encounter-reviewed-context"><summary>Reviewed case context · ' + accepted + ' accepted links · ' + (links.length - accepted) + ' candidate or held links</summary>' +
      '<p class="note-copy">These source associations add context to existing reports. They do not add independent incidents or change encounter filter classifications. Conflicting accounts and held associations remain visible.</p>' + links.map(function (link) {
        const content = ['<article class="encounter-reviewed-link"><h5>' + escapeHtml(link.case && link.case.title || "Case title unavailable") + '</h5>',
          paragraph("Association", link.acceptedForRuntime === true ? "Reviewed case association" : "Candidate or held association; not accepted"),
          paragraph("Status", label(link.status))];
        if (link.originalStatus && link.originalStatus !== link.status) content.push(paragraph("Prior decision retained", label(link.originalStatus)));
        if (link.reviewFlags && link.reviewFlags.length) content.push(paragraph("Association review notes", link.reviewFlags.map(label)));
        (link.episodes || []).forEach(function (episode) {
          const date = episode.date || {}, time = episode.time || {}, site = episode.site || {};
          content.push('<details class="encounter-reviewed-episode"><summary>Episode · ' + escapeHtml(text(date.raw || date.startIso)) + '</summary>',
            paragraph("Episode scope", label(episode.scope)), paragraph("Reported date", date.raw || date.startIso), paragraph("Date precision", label(date.precision)),
            paragraph("Reported clock", time.raw), paragraph("Clock precision", label(time.precision)),
            paragraph("Verified UTC", time.utcVerified === true ? "Source-verified interval" : "Not established"),
            paragraph("Reported locality", site.raw), paragraph("Verified exact site", site.sourceVerified === true ? "Source verified" : "Not established"),
            paragraph("Recall method", label(episode.recallMethod)), paragraph("Reported interaction", label(episode.contactKind)), paragraph("Witness aboard craft", label(episode.onboardStatus)));
          if (date.conflicts && date.conflicts.length) content.push(paragraph("Date conflicts retained", date.conflicts));
          if (time.conflicts && time.conflicts.length) content.push(paragraph("Clock conflicts retained", time.conflicts));
          (episode.recallStages || []).forEach(function (stage) { content.push(paragraph("Recall stage", [label(stage.method), stage.content, stage.recalledAt ? "Recorded/recalled " + stage.recalledAt : "", stage.status ? label(stage.status) : ""].filter(Boolean).join(" · "))); });
          if (episode.reviewFlags && episode.reviewFlags.length) content.push(paragraph("Episode review notes", episode.reviewFlags.map(label)));
          content.push('</details>');
        });
        (link.entityObservations || []).forEach(function (entity) {
          content.push('<details class="encounter-reviewed-entity"><summary>' + escapeHtml(entity.label || "Reported entity description") + '</summary>',
            paragraph("Reported descriptions", (entity.reportedTypes || []).map(function (key) { return beingLabel(key); })),
            paragraph("Observation scope", label(entity.scope)), paragraph("Reported count", entity.count),
            paragraph("Craft association", label(entity.craftAssociation)));
          (entity.attributes || []).forEach(function (attribute) {
            content.push(paragraph(label(attribute.field), text(attribute.value) + (attribute.unit ? ' ' + attribute.unit : '') + ' · attribution ' + label(attribute.attribution) + (attribute.subjectScope ? ' · subject ' + label(attribute.subjectScope) : '')));
          });
          if (entity.reviewFlags && entity.reviewFlags.length) content.push(paragraph("Description review notes", entity.reviewFlags.map(label)));
          content.push('</details>');
        });
        (link.sourceEntries || []).forEach(function (entry) {
          content.push(publicSource(entry));
          if (entry.reviewFlags && entry.reviewFlags.length) content.push(paragraph("Original source review notes (retained)", entry.reviewFlags.map(label)));
        });
        (link.qualityReviews || []).forEach(function (review) {
          const sources = new Map((review.sourceEntries || []).map(function (entry) { return [entry.entryId, entry]; }));
          content.push('<details class="encounter-additional-source-review"><summary>Additional source review · ' + escapeHtml(label(review.disposition)) + '</summary>');
          if (review.associationRevision) content.push(paragraph("Association review", "This review resolves the association; the earlier candidate decision and conflicting dates remain preserved."));
          (review.findings || []).forEach(function (fact) {
            content.push('<div class="encounter-source-finding">' + paragraph(label(fact.field), fact.text));
            if (sources.has(fact.sourceEntryId)) content.push(publicSource(sources.get(fact.sourceEntryId)));
            content.push('</div>');
          });
          if (review.rationale) content.push(paragraph("Review basis", review.rationale));
          content.push('</details>');
        });
        content.push('</article>'); return content.join("");
      }).join("") + '</details>';
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
    createIndex, createLabelOriginsIndex, createEnrichmentIndex, decorate, normalizeFilters, matches, beingMask, beingTypes, beingLabel, abductionLabel, craftAssociationLabel,
    renderBadges, renderEvidence, renderReviewedContext, decodeEvidenceResponse, escapeHtml });
});
