(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module && module.exports) module.exports = api;
  if (root) root.UfoEncounterMap = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  // The shapes identify reported content, never a biological type or an event
  // verification level. Existing craft colors and report-adjacency lines belong
  // to their own layers. This module neither creates nor reorders trace edges.
  const ALL_BEING_MASK = (1 << 19) - 1;
  const MAX_MERCATOR_LATITUDE = 85.0511287798066;
  const KINDS = Object.freeze([
    Object.freeze({ key: "abduction", label: "Reported abduction", description: "Abduction reported; no indexed being description" }),
    Object.freeze({ key: "being", label: "Reported beings", description: "Being description; no reported-abduction classification" }),
    Object.freeze({ key: "both", label: "Abduction and beings", description: "Both in the same catalog report" }),
    Object.freeze({ key: "ambiguous", label: "Unclear abduction mention", description: "An ambiguous category or mention; not counted as a reported abduction" }),
  ]);
  const KIND_KEYS = new Set(KINDS.map(function (entry) { return entry.key; }));
  const ASSOCIATIONS = Object.freeze([
    Object.freeze({ key: "not_established", label: "Craft association not established", code: 0 }),
    Object.freeze({ key: "explicit", label: "Explicit craft association in the same report", code: 1 }),
    Object.freeze({ key: "co_reported", label: "Craft and beings co-reported", code: 2 }),
    Object.freeze({ key: "none_reported", label: "No craft association reported", code: 3 }),
  ]);
  const POLICY = "Symbols mark catalog reports, not verified incidents or exact encounter sites. Craft relationships refer to the same report; map proximity and trace adjacency do not establish the same craft, being, or flight path.";

  function number(value) {
    if (typeof value !== "number" && typeof value !== "string") return null;
    if (typeof value === "string" && !value.trim()) return null;
    const result = Number(value);
    return Number.isFinite(result) ? result : null;
  }
  function eventId(value) {
    const id = value && (value.event_id != null ? value.event_id : value.eventId);
    if (typeof id === "number") return Number.isSafeInteger(id) && id > 0 ? String(id) : "";
    return typeof id === "string" && /^[1-9]\d*$/.test(id) && Number.isSafeInteger(Number(id)) ? id : "";
  }
  function compareIds(a, b) { return Number(a) - Number(b); }
  function validMask(value) { return Number.isInteger(value) && value >= 0 && value <= ALL_BEING_MASK; }
  function maskSize(value) {
    let mask = value;
    let count = 0;
    while (mask) { mask &= mask - 1; count += 1; }
    return count;
  }
  function classify(event) {
    if (!event || event.encounterEvidenceReady !== true || event.encounterIdentityMismatch === true) {
      return { ready: false, kind: null, reportedAbduction: false, ambiguousAbduction: false, reportedBeings: false, reason: "evidence_unavailable" };
    }
    const abduction = event.encounterAbductionCode;
    const mask = event.encounterBeingMask;
    if (![0, 1, 2, 3].includes(abduction) || !validMask(mask)) {
      return { ready: false, kind: null, reportedAbduction: false, ambiguousAbduction: false, reportedBeings: false, reason: "invalid_classification" };
    }
    const reportedAbduction = abduction === 1 || abduction === 2;
    const reportedBeings = mask > 0;
    const ambiguousAbduction = abduction === 3;
    const kind = reportedAbduction ? reportedBeings ? "both" : "abduction" : reportedBeings ? "being" : ambiguousAbduction ? "ambiguous" : null;
    const rawAssociation = event.encounterCraftAssociationCode;
    const association = ASSOCIATIONS[[0, 1, 2, 3].includes(rawAssociation) ? rawAssociation : 0];
    return {
      ready: true, kind, reportedAbduction, ambiguousAbduction, reportedBeings,
      abductionStatus: abduction === 1 ? "source_reported" : abduction === 2 ? "narrative_reported" : ambiguousAbduction ? "ambiguous" : "not_indexed",
      beingMask: mask, beingTypeCount: maskSize(mask),
      craftAssociation: association.key, craftAssociationCode: association.code,
      craftAssociationAvailable: [0, 1, 2, 3].includes(rawAssociation),
      // Collection names are never used as proxies for field/narrative origin.
      beingOriginsReady: event.encounterEvidenceProvenanceReady === true,
      sourceBeingMask: event.encounterEvidenceProvenanceReady === true && validMask(event.encounterSourceBeingMask) ? event.encounterSourceBeingMask : null,
      narrativeBeingMask: event.encounterEvidenceProvenanceReady === true && validMask(event.encounterNarrativeBeingMask) ? event.encounterNarrativeBeingMask : null,
      reason: kind ? null : "no_indexed_encounter",
    };
  }
  function pointForEvent(event) {
    if (!event || event.has_coordinates === false || event.coordinate_source === "unresolved") return null;
    const lat = number(event.lat);
    const lon = number(event.lon);
    if (lat == null || lon == null || lat < -90 || lat > 90 || lon < -180 || lon > 180) return null;
    return {
      lat, lon, locationPrecision: typeof event.location_precision === "string" && event.location_precision ? event.location_precision : "unknown",
      coordinateSource: typeof event.coordinate_source === "string" && event.coordinate_source ? event.coordinate_source : "unknown",
      // Retain the actual canonical coordinate; no inferred location or radius.
      locationDisplay: typeof event.location_display === "string" ? event.location_display : "",
    };
  }
  function describeRelationship(event) {
    const classification = classify(event);
    if (!classification.ready || !classification.kind) return {
      key: "unavailable", label: "No indexed encounter relationship available", sameReport: false, canInferFlight: false,
    };
    const association = ASSOCIATIONS[classification.craftAssociationCode];
    return {
      key: association.key, label: association.label, sameReport: association.code === 1 || association.code === 2,
      sourceReportedAssociation: association.code === 1, coReportedOnly: association.code === 2,
      canInferFlight: false, canInferSameCraftAcrossReports: false,
      evidenceAvailable: classification.craftAssociationAvailable,
    };
  }
  function normalizedLongitude(value) { return (((value + 180) % 360) + 360) % 360 - 180; }
  function inViewport(point, viewport) {
    if (!viewport) return true;
    const north = number(viewport.north), south = number(viewport.south), west = number(viewport.west), east = number(viewport.east);
    if (north == null || south == null || west == null || east == null || north < south) return false;
    if (point.lat < south || point.lat > north) return false;
    if (east - west >= 360) return true;
    const lon = normalizedLongitude(point.lon), low = normalizedLongitude(west), high = normalizedLongitude(east);
    return low <= high ? lon >= low && lon <= high : lon >= low || lon <= high;
  }
  function projection(point, zoom) {
    const scale = 256 * Math.pow(2, zoom);
    const lat = Math.max(-MAX_MERCATOR_LATITUDE, Math.min(MAX_MERCATOR_LATITUDE, point.lat)) * Math.PI / 180;
    return [(normalizedLongitude(point.lon) + 180) / 360 * scale, (1 - Math.log(Math.tan(Math.PI / 4 + lat / 2)) / Math.PI) / 2 * scale];
  }
  function emptyCounts() {
    return { reports: 0, mapped: 0, unmapped: 0, reportedAbductions: 0, reportedBeings: 0, ambiguousAbductionMentions: 0,
      sourceClassifiedAbductions: 0, narrativeAbductions: 0,
      kinds: { abduction: 0, being: 0, both: 0, ambiguous: 0 },
      craftAssociations: { not_established: 0, explicit: 0, co_reported: 0, none_reported: 0 },
      locationPrecisions: {}, sourceCollections: {} };
  }
  function incrementKey(target, key) {
    const previous = Object.prototype.hasOwnProperty.call(target, key) ? target[key] : 0;
    Object.defineProperty(target, key, { value: previous + 1, writable: true, enumerable: true, configurable: true });
  }
  function addCounts(counts, entry) {
    const classification = entry.classification;
    counts.reports += 1;
    counts[entry.point ? "mapped" : "unmapped"] += 1;
    counts.kinds[classification.kind] += 1;
    if (classification.reportedAbduction) counts.reportedAbductions += 1;
    if (classification.reportedBeings) counts.reportedBeings += 1;
    if (classification.ambiguousAbduction) counts.ambiguousAbductionMentions += 1;
    if (classification.abductionStatus === "source_reported") counts.sourceClassifiedAbductions += 1;
    if (classification.abductionStatus === "narrative_reported") counts.narrativeAbductions += 1;
    counts.craftAssociations[classification.craftAssociation] += 1;
    const precision = entry.point ? entry.point.locationPrecision : "unmapped";
    incrementKey(counts.locationPrecisions, precision);
    incrementKey(counts.sourceCollections, entry.source);
  }
  function accepts(classification, options) {
    const kind = classification.kind;
    if (!kind) return false;
    const filter = options.population || "all";
    if (kind === "ambiguous" && options.includeAmbiguous !== true && filter !== "ambiguous") return false;
    return filter === "abduction" ? classification.reportedAbduction : filter === "being" ? classification.reportedBeings : filter === "both" ? kind === "both" : filter === "ambiguous" ? classification.ambiguousAbduction : filter === "all";
  }
  function groupPoints(entries, size) {
    const groups = new Map();
    entries.forEach(function (entry) {
      const key = Math.floor(entry.projected[0] / size) + ":" + Math.floor(entry.projected[1] / size);
      let group = groups.get(key);
      if (!group) { group = []; groups.set(key, group); }
      group.push(entry);
    });
    return Array.from(groups.entries()).map(function (pair) { return { key: pair[0], entries: pair[1] }; });
  }
  function clusterModel(group) {
    const entries = group.entries.slice().sort(function (a, b) { return compareIds(a.eventId, b.eventId); });
    const representative = entries[0];
    const counts = emptyCounts();
    entries.forEach(function (entry) { addCounts(counts, entry); });
    const presentKinds = Object.keys(counts.kinds).filter(function (key) { return counts.kinds[key] > 0; });
    return {
      key: "encounter:" + group.key, eventId: representative.eventId, eventIds: entries.map(function (entry) { return entry.eventId; }),
      lat: representative.point.lat, lon: representative.point.lon, point: representative.point,
      anchorPolicy: "existing_report_coordinate", reportCount: entries.length, isCluster: entries.length > 1,
      kind: presentKinds.length === 1 ? presentKinds[0] : "mixed", kinds: presentKinds, counts,
      ambiguousAbduction: counts.ambiguousAbductionMentions > 0,
      // A spatial display group is not incident deduplication or a common site.
      records: entries.map(function (entry) { return { eventId: entry.eventId, point: entry.point, classification: entry.classification, source: entry.source }; }),
    };
  }
  function buildModel(events, options) {
    const config = options || {};
    if (!Array.isArray(events)) throw new TypeError("Encounter map expects a catalog report array");
    const cohort = emptyCounts(), visible = emptyCounts(), exclusions = { evidenceUnavailable: 0, invalidIdentity: 0, duplicateEventIds: 0, notIndexed: 0, hiddenUnclearMentions: 0, population: 0, outsideViewport: 0, projectionUnavailable: 0 };
    const seen = new Set(), entries = [], reports = [], unmappedEventIds = [];
    const zoomValue = number(config.zoom);
    const zoom = zoomValue == null ? 3 : Math.max(0, Math.min(24, zoomValue));
    const maxValue = number(config.maxMarkers);
    const maxMarkers = maxValue == null ? 400 : Math.max(1, Math.min(1500, Math.floor(maxValue)));
    const sizeValue = number(config.cellSize);
    let cellSize = sizeValue == null ? 40 : Math.max(16, Math.min(256, sizeValue));
    events.forEach(function (event) {
      if (config.evidenceReady === false) { exclusions.evidenceUnavailable += 1; return; }
      const id = eventId(event);
      if (!id) { exclusions.invalidIdentity += 1; return; }
      if (seen.has(id)) { exclusions.duplicateEventIds += 1; return; }
      seen.add(id);
      const classification = classify(event);
      if (!classification.ready) { exclusions.evidenceUnavailable += 1; return; }
      if (!classification.kind) { exclusions.notIndexed += 1; return; }
      if (!accepts(classification, config)) {
        exclusions[classification.kind === "ambiguous" && config.includeAmbiguous !== true ? "hiddenUnclearMentions" : "population"] += 1;
        return;
      }
      const point = pointForEvent(event);
      const entry = { eventId: id, classification, point, source: typeof event.source === "string" && event.source ? event.source : "unknown" };
      reports.push({ eventId: id, classification, point, source: entry.source });
      addCounts(cohort, entry);
      if (!point) { unmappedEventIds.push(id); return; }
      if (!inViewport(point, config.viewport)) { exclusions.outsideViewport += 1; return; }
      addCounts(visible, entry);
      let projected;
      try { projected = typeof config.project === "function" ? config.project([point.lat, point.lon]) : projection(point, zoom); } catch (_) { projected = null; }
      if (!Array.isArray(projected) || projected.length < 2 || number(projected[0]) == null || number(projected[1]) == null || Math.abs(Number(projected[0])) > 1e12 || Math.abs(Number(projected[1])) > 1e12) {
        exclusions.projectionUnavailable += 1;
        return;
      }
      entry.projected = [Number(projected[0]), Number(projected[1])];
      entries.push(entry);
    });
    let groups = groupPoints(entries, cellSize);
    // World-pixel bins are independent of input order and viewport panning.
    // Increase spatial aggregation before considering an arbitrary point cap.
    for (let iteration = 0; groups.length > maxMarkers && iteration < 40; iteration += 1) {
      cellSize *= 2;
      groups = groupPoints(entries, cellSize);
    }
    // At most four bins can straddle a world-pixel origin at large sizes. If a
    // caller asks for fewer, retain all records in one explicitly broad group.
    if (groups.length > maxMarkers) groups = [{ key: "viewport", entries }];
    const markers = groups.map(clusterModel).sort(function (a, b) { return compareIds(a.eventId, b.eventId); });
    unmappedEventIds.sort(compareIds);
    reports.sort(function (a, b) { return compareIds(a.eventId, b.eventId); });
    return {
      schemaId: "ufo-encounter-map-v1", status: config.evidenceReady === false ? "unavailable" : "ready",
      countsAvailable: config.evidenceReady !== false,
      scopeLabel: "Selected dates, sources and geography; independent of craft-type visibility", population: config.population || "all",
      includeAmbiguous: config.includeAmbiguous === true || config.population === "ambiguous", cohort, viewport: visible, exclusions, markers, reports, unmappedEventIds,
      rendering: { maxMarkers, markerCount: markers.length, displayedReports: markers.reduce(function (sum, entry) { return sum + entry.reportCount; }, 0), cellSize, zoom,
        clustering: "display_group_only", centroidUsed: false }, policy: POLICY,
    };
  }
  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (character) { return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]; });
  }
  function markerSvg(kind, options) {
    const config = options || {};
    const knownKind = KIND_KEYS.has(kind) || kind === "mixed" ? kind : "ambiguous";
    const label = KINDS.find(function (entry) { return entry.key === knownKind; });
    const count = Number.isSafeInteger(config.count) && config.count > 1 ? config.count : 0;
    const title = (label ? label.label : "Mixed encounter reports") + (count ? " · " + count + " reports in this display group" : "") + (config.ambiguousAbduction && knownKind !== "ambiguous" ? " · includes an unclear abduction mention" : "");
    const dashed = knownKind === "ambiguous" || config.ambiguousAbduction === true;
    const frame = '<rect x="2" y="2" width="24" height="24" rx="6" fill="#18232b" fill-opacity=".94" stroke="#f0f3f4" stroke-width="1.7"' + (dashed ? ' stroke-dasharray="3 2"' : '') + '/>';
    // A generic person pictogram denotes a source-described being category. It
    // deliberately has no alien anatomy, species, craft, beam, or travel arrow.
    const person = '<circle cx="14" cy="9" r="2.4"/><path d="M9.5 19v-2.3a4.5 4.5 0 0 1 9 0V19M14 13.2V20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>';
    const diamond = '<path d="M14 6 22 14 14 22 6 14Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>';
    const both = '<path d="M14 4.7 23.3 14 14 23.3 4.7 14Z" fill="none" stroke="currentColor" stroke-width="1.3"/>' + '<circle cx="14" cy="10.5" r="1.8"/><path d="M10.6 18a3.4 3.4 0 0 1 6.8 0M14 13.3V19" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>';
    const unclear = '<path d="M14 6 22 14 14 22 6 14Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-dasharray="2.5 2"/>';
    const mixed = '<circle cx="10" cy="11" r="2"/><path d="M6.8 17a3.2 3.2 0 0 1 6.4 0M18 8l4 6-4 6-4-6Z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>';
    const glyph = knownKind === "being" ? person : knownKind === "abduction" ? diamond : knownKind === "both" ? both : knownKind === "mixed" ? mixed : unclear;
    const counter = count ? '<rect x="17" y="19" width="18" height="12" rx="5" fill="#f0f3f4" stroke="#18232b" stroke-width="1"/><text x="26" y="27.5" fill="#18232b" stroke="none" text-anchor="middle" font-family="system-ui,sans-serif" font-weight="700" font-size="8">' + (count > 999 ? "999+" : count) + '</text>' : "";
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 32" width="36" height="32" role="img" aria-label="' + escapeHtml(title) + '" style="color:#f0f3f4"><title>' + escapeHtml(title) + '</title>' + frame + '<g fill="currentColor">' + glyph + '</g>' + counter + '</svg>';
  }
  function traceEndpointSummary(segments, events) {
    const byId = new Map();
    (Array.isArray(events) ? events : []).forEach(function (event) {
      const id = eventId(event), classification = classify(event);
      if (id && classification.ready && classification.kind && classification.kind !== "ambiguous" && !byId.has(id)) byId.set(id, classification);
    });
    const result = { inspectedLinks: 0, linksWithEncounterEndpoint: 0, linksWithBothEncounterEndpoints: 0, encounterEndpointReportCount: 0,
      associations: { explicit: 0, co_reported: 0, not_established: 0, none_reported: 0 }, links: [],
      policy: "These existing traces share a catalog report ID with an encounter. Their adjacency does not establish a common craft, entity, encounter route, or flight path." };
    const seenReports = new Set();
    (Array.isArray(segments) ? segments : []).forEach(function (segment, index) {
      if (!segment || typeof segment !== "object") return;
      result.inspectedLinks += 1;
      // Exact report IDs only: coordinate, date, type and nearest-neighbor
      // matching are deliberately absent from this membership operation.
      const fromId = eventId({ eventId: segment.fromEventId }), toId = eventId({ eventId: segment.toEventId });
      const from = byId.get(fromId) || null, to = byId.get(toId) || null;
      if (!from && !to) return;
      result.linksWithEncounterEndpoint += 1;
      if (from && to) result.linksWithBothEncounterEndpoints += 1;
      [[fromId, from], [toId, to]].forEach(function (pair) {
        if (!pair[1] || seenReports.has(pair[0])) return;
        seenReports.add(pair[0]);
        result.associations[pair[1].craftAssociation] += 1;
      });
      result.links.push({ segmentIndex: index, fromEventId: fromId || null, toEventId: toId || null,
        fromEncounter: from ? { kind: from.kind, craftAssociation: from.craftAssociation } : null,
        toEncounter: to ? { kind: to.kind, craftAssociation: to.craftAssociation } : null,
        relationshipBasis: "same_catalog_report_id", canInferFlight: false, canInferSameCraft: false });
    });
    result.encounterEndpointReportCount = seenReports.size;
    return result;
  }

  return Object.freeze({ KINDS, ASSOCIATIONS, POLICY, classify, pointForEvent, describeRelationship, inViewport, buildModel, markerSvg, traceEndpointSummary });
});
