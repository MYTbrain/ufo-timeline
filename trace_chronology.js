(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module && module.exports) module.exports = api;
  if (root) root.UfoTraceChronology = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const SCHEMA_ID = "trace-chronology-evidence-v1";
  const SOURCE_CONTRACT = "source-backed-clock-and-historical-zone-v1";
  const ROW_SCHEMA = Object.freeze(["eventId", "utcStartMs", "utcEndMs", "evidenceCode", "zoneCode"]);

  function identifier(value) {
    if (typeof value === "number") return Number.isSafeInteger(value) && value > 0 ? String(value) : "";
    if (typeof value !== "string" || !/^\d+$/.test(value)) return "";
    const number = Number(value);
    return Number.isSafeInteger(number) && number > 0 ? String(number) : "";
  }

  function finiteTimestamp(value) {
    return typeof value === "number" && Number.isFinite(value) && Number.isFinite(new Date(value).getTime());
  }

  async function verifyHash(bytes, expectedHash, label) {
    if (!expectedHash) return;
    if (typeof expectedHash !== "string" || !/^[a-f0-9]{64}$/i.test(expectedHash) ||
        typeof crypto === "undefined" || !crypto.subtle) throw new Error("Trace chronology " + label + " integrity verification is unavailable.");
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    const actual = Array.from(new Uint8Array(digest), function (value) { return value.toString(16).padStart(2, "0"); }).join("");
    if (actual !== expectedHash.toLowerCase()) throw new Error("Trace chronology " + label + " hash does not match its release pin.");
  }

  async function decodeEvidenceResponse(response, expected) {
    const pins = expected || {};
    if (!response || !response.ok) throw new Error("Trace chronology evidence response failed.");
    let bytes = new Uint8Array(await response.arrayBuffer());
    if (bytes[0] === 0x1f && bytes[1] === 0x8b) {
      await verifyHash(bytes, pins.gzipSha256, "gzip");
      if (typeof DecompressionStream !== "function") throw new Error("Trace chronology gzip decoding is unavailable.");
      const decoded = await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"))).arrayBuffer();
      bytes = new Uint8Array(decoded);
    }
    // Browsers can already decode Content-Encoding gzip. Always verify the
    // decoded bytes, and never attempt a second decompression in that case.
    await verifyHash(bytes, pins.sha256, "decoded");
    const payload = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
    if (pins.rowCount != null && (!Number.isSafeInteger(pins.rowCount) || !Array.isArray(payload.rows) || payload.rows.length !== pins.rowCount)) {
      throw new Error("Trace chronology row count does not match its release pin.");
    }
    return payload;
  }

  function createEvidenceIndex(payload) {
    if (!payload || payload.schemaId !== SCHEMA_ID || payload.sourceContract !== SOURCE_CONTRACT ||
        typeof payload.releaseId !== "string" || !payload.releaseId.trim() ||
        JSON.stringify(payload.rowSchema) !== JSON.stringify(ROW_SCHEMA) || !Array.isArray(payload.rows) ||
        !payload.codes || !Array.isArray(payload.codes.evidence) || !Array.isArray(payload.codes.zone)) {
      throw new Error("Trace chronology evidence does not satisfy its source-backed schema contract.");
    }
    const evidence = payload.codes.evidence.map(function (entry) {
      if (!entry || entry.status !== "accepted" || typeof entry.kind !== "string" || !entry.kind.trim() ||
          typeof entry.confidence !== "string" || !entry.confidence.trim() ||
          typeof entry.basis !== "string" || !entry.basis.trim()) {
        throw new Error("Trace chronology evidence contains an unaccepted or incomplete timing basis.");
      }
      if (entry.timezoneEvidence != null && (typeof entry.timezoneEvidence !== "string" || !entry.timezoneEvidence.trim())) {
        throw new Error("Trace chronology timezone evidence is incomplete.");
      }
      return Object.freeze({ status: "accepted", kind: entry.kind, confidence: entry.confidence, basis: entry.basis,
        timezoneEvidence: entry.timezoneEvidence || "" });
    });
    const zones = payload.codes.zone.map(function (zone) {
      if (typeof zone !== "string" || !zone.trim()) throw new Error("Trace chronology timezone is missing.");
      try { new Intl.DateTimeFormat("en", { timeZone: zone }); }
      catch (error) { throw new Error("Trace chronology timezone is unsupported: " + zone); }
      return zone;
    });
    const rows = payload.rows.slice();
    rows.forEach(function (row, rowIndex) {
      const id = Array.isArray(row) && row.length === ROW_SCHEMA.length ? identifier(row[0]) : "";
      if (!id || typeof row[0] !== "number" || !finiteTimestamp(row[1]) ||
          !finiteTimestamp(row[2]) || row[2] < row[1] ||
          !Number.isInteger(row[3]) || row[3] < 0 || row[3] >= evidence.length ||
          !Number.isInteger(row[4]) || row[4] < 0 || row[4] >= zones.length) {
        throw new Error("Trace chronology evidence has an invalid or duplicate row at " + rowIndex + ".");
      }
    });
    rows.sort(function (left, right) { return left[0] - right[0]; });
    const ids = new Float64Array(rows.length);
    const starts = new Float64Array(rows.length);
    const ends = new Float64Array(rows.length);
    const evidenceCodes = new Uint32Array(rows.length);
    const zoneCodes = new Uint32Array(rows.length);
    rows.forEach(function (row, position) {
      if (position && row[0] === rows[position - 1][0]) throw new Error("Trace chronology evidence has a duplicate event ID.");
      ids[position] = row[0]; starts[position] = row[1]; ends[position] = row[2];
      evidenceCodes[position] = row[3]; zoneCodes[position] = row[4];
    });
    const releaseId = payload.releaseId;
    return Object.freeze({
      releaseId: releaseId,
      rowCount: ids.length,
      interval: function (eventId) {
        const id = identifier(eventId);
        if (!id) return null;
        const target = Number(id);
        let low = 0, high = ids.length;
        while (low < high) {
          const middle = Math.floor((low + high) / 2);
          if (ids[middle] < target) low = middle + 1;
          else high = middle;
        }
        return low < ids.length && ids[low] === target ? {
          eventId: id, startMs: starts[low], endMs: ends[low],
          evidence: evidence[evidenceCodes[low]], zone: zones[zoneCodes[low]],
        } : null;
      },
      snapshot: function () {
        return { status: "ready", releaseId: releaseId, acceptedEventCount: ids.length,
          evidenceKinds: evidence.map(function (entry) { return entry.kind; }), zoneCount: zones.length,
          indexBytes: ids.byteLength + starts.byteLength + ends.byteLength + evidenceCodes.byteLength + zoneCodes.byteLength };
      },
    });
  }

  function dateInterval(eventId, ordinal) {
    if (typeof ordinal !== "number" || !Number.isInteger(ordinal)) return null;
    const midnight = ordinal * 86400000;
    if (!finiteTimestamp(midnight)) return null;
    return { eventId: String(eventId), startMs: midnight - (24 * 3600000), endMs: midnight + (48 * 3600000) - 1,
      zone: "Complete calendar-day bounds across time zones", evidence: { status: "accepted", kind: "date_only", confidence: "bounded",
        basis: "Separate source calendar dates; conservative UTC bounds allowing offsets through ±24 hours, without an invented clock" } };
  }

  function resolvePair(index, fromEventId, toEventId, dates) {
    let from = index && typeof index.interval === "function" ? index.interval(fromEventId) : null;
    let to = index && typeof index.interval === "function" ? index.interval(toEventId) : null;
    if (dates && typeof dates.gapDays === "number" && dates.gapDays > 2) {
      from = from || dateInterval(fromEventId, dates.fromOrdinal);
      to = to || dateInterval(toEventId, dates.toOrdinal);
    }
    if (!from || !to) return { status: "unknown", reason: "missing_source_backed_time", from: from, to: to, reversed: false };
    if (from.endMs < to.startMs) return { status: "ordered", reason: "non_overlapping_utc_intervals", from: from, to: to, reversed: false };
    if (to.endMs < from.startMs) return { status: "ordered", reason: "non_overlapping_utc_intervals", from: to, to: from, reversed: true };
    return { status: "unknown", reason: "overlapping_utc_intervals", from: from, to: to, reversed: false };
  }

  function orientSegment(index, segment) {
    if (!segment || typeof segment !== "object") return segment;
    const decision = resolvePair(index, segment.fromEventId, segment.toEventId, {
      gapDays: segment.gapDays, fromOrdinal: segment.fromSortOrdinal, toOrdinal: segment.toSortOrdinal,
    });
    const oriented = Object.assign({}, segment, {
      sameDayOrderKnown: decision.status === "ordered",
      chronology: Object.assign({ releaseId: index ? index.releaseId : "" }, decision),
    });
    if (decision.reversed) {
      [["fromEventId", "toEventId"], ["from", "to"], ["fromSortOrdinal", "toSortOrdinal"],
        ["fromOrdinal", "toOrdinal"], ["fromSortDateKey", "toSortDateKey"]].forEach(function (keys) {
        if (Object.prototype.hasOwnProperty.call(segment, keys[0]) || Object.prototype.hasOwnProperty.call(segment, keys[1])) {
          oriented[keys[0]] = segment[keys[1]];
          oriented[keys[1]] = segment[keys[0]];
        }
      });
      oriented.eventIds = [oriented.fromEventId, oriented.toEventId];
      oriented.traceId = String(oriented.fromEventId) + "->" + String(oriented.toEventId);
    }
    return oriented;
  }

  function intervalLabel(interval) {
    if (!interval) return "No accepted source-backed clock and timezone.";
    const start = new Date(interval.startMs).toISOString();
    const end = new Date(interval.endMs).toISOString();
    return (start === end ? start : start + " to " + end) + " · " + interval.zone + " · " +
      interval.evidence.basis + " (" + interval.evidence.confidence + ")" +
      (interval.evidence.timezoneEvidence ? "; timezone evidence: " + interval.evidence.timezoneEvidence : "");
  }

  function hypotheticalSpeedRange(decision, distanceKm) {
    if (!decision || decision.status !== "ordered" || !decision.from || !decision.to ||
        typeof distanceKm !== "number" || !Number.isFinite(distanceKm) || distanceKm < 0) return null;
    const minHours = (decision.to.startMs - decision.from.endMs) / 3600000;
    const maxHours = (decision.to.endMs - decision.from.startMs) / 3600000;
    if (!(minHours > 0) || maxHours < minHours) return null;
    return { lowerKph: distanceKm / maxHours, upperKph: distanceKm / minHours, minHours, maxHours };
  }

  return Object.freeze({ SCHEMA_ID, SOURCE_CONTRACT, ROW_SCHEMA, createEvidenceIndex, decodeEvidenceResponse, resolvePair, orientSegment, intervalLabel, hypotheticalSpeedRange });
});
