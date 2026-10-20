(function (root, factory) {
  "use strict";
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.UfoUfocatReferences = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const CATALOG_URL = "https://cufos.org/PDFs/books/Physical_Traces.pdf";
  const CATALOG_PDF_SHA256 = "e824270528264c2563df17f79540171dc216fb9be85968a5eb844ecb1b2be17b";
  // Original scan visually checked by independent reviewers; no OCR inference.
  const VERIFIED_CATALOG_PAGES = new Map([[253, [44, 62]], [537, [86, 104]], [585, [90, 108]]]);
  const FAMILY_ID = "ted_phillips_physical_trace_lineage";
  // UFOCAT 2023 Sources.xlsx, rows 748-751; no inference from AUTHOR alone.
  const WORKS = new Map([
    ["TPhillips", ["investigation_files", "Ted Phillips - investigation files"]],
    ["TPhillips1", ["physical_traces_1975", "Ted Phillips - Physical Traces Associated with UFO Sightings (CUFOS, 1975)"]],
    ["TPhillips2", ["trace_cases", "Ted Phillips - Trace Cases"]],
    ["TPhillips3", ["missouri_and_newspaper_reports", "Ted Phillips - Missouri Cases and other newspaper reports"]],
  ]);
  const object = value => value && typeof value === "object" && !Array.isArray(value);
  const validatedIndexes = new WeakSet();
  const text = value => typeof value === "string" ? value.trim().replace(/\s+/g, " ") : typeof value === "number" && Number.isFinite(value) ? String(value) : "";
  function ufocatOwner(value) {
    const names = [value.source_name, value.source].map(text).filter(Boolean).map(value => value.toLowerCase());
    if (names.length) return names.every(name => ["ufocat", "ufocat2023", "ufocat2023.csv"].includes(name));
    return text(value.source_file).replace(/\\/g, "/").split("/").pop().toLowerCase() === "ufocat2023.csv";
  }
  function rawRows(event) {
    const result = [], canonical = object(event.extra_data) && object(event.extra_data.canonical) ? event.extra_data.canonical : {};
    if (ufocatOwner(event)) [event.raw_fields, canonical.raw_fields, event.raw_source_row].filter(object).forEach(value => result.push(value));
    for (const owner of [event, canonical]) for (const key of ["source_records", "source_provenance"]) {
      if (!Array.isArray(owner[key])) continue;
      for (const member of owner[key]) {
        if (!object(member) || !ufocatOwner(member)) continue;
        [member.raw_fields, member.raw_source_row].filter(object).forEach(value => result.push(value));
      }
    }
    return result;
  }
  function referenceEntries(event) {
    if (!object(event)) return [];
    const entries = [], seen = new Set(), originals = typeof event.references === "string" ? [event.references] : event.references;
    if (Array.isArray(originals)) for (const original of originals) {
      const value = typeof original === "string" ? text(original) : "";
      if (value && !seen.has(value)) { entries.push({text: value, citationRole: "existing"}); seen.add(value); }
    }
    for (const raw of rawRows(event)) for (const [role, codeField, locatorField] of [["direct", "SOURCE", "PAGEVOL"], ["indirect", "ISOURCE", "IPAGEVOL"]]) {
      const code = text(raw[codeField]);
      if (!code) continue;
      const locator = text(raw[locatorField]), work = WORKS.get(code), entry = {sourceCode: code, citationRole: role,
        locatorRaw: locator || null, locatorType: "source_locator_unresolved", catalogCaseNumber: null, flags: []};
      const title = work ? `${work[1]} [${code}]` : `UFOCAT source code ${code}`;
      let suffix = locator ? `, locator ${locator}` : "", legacyValue = null;
      if (work) { entry.sourceWorkId = work[0]; entry.familyId = FAMILY_ID; }
      if (code === "TPhillips1") {
        entry.url = CATALOG_URL;
        if (role === "direct") {
          if (/^[0-9]+$/.test(locator) && Number(locator) >= 1 && Number(locator) <= 831) {
            entry.catalogCaseNumber = Number(locator); entry.locatorType = "catalog_case_number"; suffix = `, case ${locator}`;
            const pages = VERIFIED_CATALOG_PAGES.get(entry.catalogCaseNumber);
            if (pages) {
              legacyValue = `${title}${suffix} (${role} citation)`;
              [entry.catalogPrintedPage, entry.catalogPdfPage] = pages;
              entry.catalogPdfSha256 = CATALOG_PDF_SHA256;
              entry.url = `${CATALOG_URL}#page=${entry.catalogPdfPage}`;
              suffix += `, printed p. ${entry.catalogPrintedPage}, PDF page ${entry.catalogPdfPage}`;
            }
          } else {
            entry.flags.push("missing_or_invalid_catalog_case_number"); suffix = locator ? `, unverified locator ${locator}` : ", case number unavailable";
          }
        } else {
          entry.locatorType = "ambiguous_catalog_case_number_or_printed_page";
          suffix = locator ? `, locator ${locator} (page or case number unverified)` : ", locator unavailable";
        }
      }
      const value = `${title}${suffix} (${role} citation)`;
      entry.text = value;
      // Upgrade only this owned row's exact former helper string. Unrelated
      // references, and a bare old citation without owned raw fields, survive.
      if (legacyValue && legacyValue !== value) {
        const legacyIndex = entries.findIndex(item => item.text === legacyValue && item.citationRole === "existing");
        if (legacyIndex >= 0) {
          seen.delete(legacyValue);
          if (seen.has(value)) entries.splice(legacyIndex, 1);
          else { Object.assign(entries[legacyIndex], entry); seen.add(value); }
        }
      }
      if (!seen.has(value)) { entries.push(entry); seen.add(value); }
      else {
        const existing = entries.find(item => item.text === value && item.citationRole === "existing");
        if (existing) Object.assign(existing, entry);
      }
    }
    return entries;
  }
  function safeEventId(value) {
    if (typeof value === "number") return Number.isSafeInteger(value) && value > 0 ? value : null;
    if (typeof value !== "string" || !/^[1-9][0-9]*$/.test(value)) return null;
    const number = Number(value);
    return Number.isSafeInteger(number) ? number : null;
  }
  function createIndex(payload, manifest) {
    const fail = () => { throw new Error("Invalid Phillips citation index"); };
    if (!object(payload) || payload.schemaId !== "ufo-timeline-phillips-detail-citations-v1" || !object(payload.events) || !object(payload.counts)) fail();
    const entries = Object.create(null);
    let recordN = 0;
    for (const [key, value] of Object.entries(payload.events)) {
      const eventId = safeEventId(key);
      if (!eventId || !object(value) || safeEventId(value.eventId) !== eventId || !/^evt_[0-9a-f]{24}$/.test(value.canonicalEventId || "") ||
          !Array.isArray(value.sourceRecords) || !value.sourceRecords.length) fail();
      const members = [], seen = new Set();
      for (const member of value.sourceRecords) {
        if (!object(member) || member.source_name !== "ufocat" || member.source_file !== "ufocat2023.csv" ||
            !text(member.source_native_id) || !Number.isSafeInteger(member.source_row_number) || member.source_row_number < 2 ||
            !/^cin_[0-9a-f]{24}$/.test(member.canonical_input_id || "") || !/^[0-9a-f]{40}$/.test(member.source_row_hash || "") || !object(member.raw_fields)) fail();
        const raw = {};
        for (const [field, value] of Object.entries(member.raw_fields)) {
          if (!["SOURCE", "PAGEVOL", "ISOURCE", "IPAGEVOL"].includes(field) || typeof value !== "string" || value.length > 2048) fail();
          raw[field] = value;
        }
        if (!WORKS.has(text(raw.SOURCE)) && !WORKS.has(text(raw.ISOURCE))) fail();
        if (seen.has(member.canonical_input_id)) fail();
        seen.add(member.canonical_input_id);
        members.push(Object.freeze({source_name: "ufocat", source_file: "ufocat2023.csv", source_native_id: text(member.source_native_id),
          source_row_number: member.source_row_number, source_row_hash: member.source_row_hash,
          canonical_input_id: member.canonical_input_id, raw_fields: Object.freeze(raw)}));
        recordN += 1;
      }
      entries[key] = Object.freeze({eventId, canonicalEventId: value.canonicalEventId, sourceRecords: Object.freeze(members)});
    }
    const eventN = Object.keys(entries).length;
    if (payload.counts.eventN !== eventN || payload.counts.sourceRecordN !== recordN) fail();
    if (manifest !== undefined && (!object(manifest) || manifest.schemaId !== "ufo-timeline-phillips-detail-citations-manifest-v1" ||
        !object(manifest.artifact) || manifest.artifact.schemaId !== payload.schemaId || !object(manifest.counts) ||
        manifest.counts.eventN !== eventN || manifest.counts.sourceRecordN !== recordN ||
        !object(manifest.inputPins) || !object(manifest.inputPins.sourceIndex) ||
        manifest.inputPins.sourceIndex.sha256 !== payload.sourceIndexSha256 || !/^[0-9a-f]{64}$/.test(payload.sourceIndexSha256 || ""))) fail();
    const index = Object.freeze({schemaId: payload.schemaId, eventN, sourceRecordN: recordN, entries: Object.freeze(entries)});
    validatedIndexes.add(index);
    return index;
  }
  function withIndexedCitations(event, index) {
    if (!object(event) || !object(index) || !validatedIndexes.has(index)) return event;
    const eventId = safeEventId(event.event_id ?? event.eventId), expected = eventId && index.entries[String(eventId)];
    if (!expected || text(event.canonical_event_id ?? event.canonicalEventId) !== expected.canonicalEventId) return event;
    const canonical = object(event.extra_data) && object(event.extra_data.canonical) ? event.extra_data.canonical : {};
    const inputIds = event.canonical_input_ids ?? canonical.canonical_input_ids;
    const provenance = event.source_provenance ?? canonical.source_provenance;
    if (!Array.isArray(inputIds) || !Array.isArray(provenance)) return event;
    const ids = new Set(inputIds), existing = Array.isArray(event.source_records) ? event.source_records : [], additions = [];
    for (const member of expected.sourceRecords) {
      if (!ids.has(member.canonical_input_id) || !provenance.some(source => object(source) && ufocatOwner(source) &&
          source.canonical_input_id === member.canonical_input_id && source.source_row_hash === member.source_row_hash &&
          text(source.source_native_id) === member.source_native_id)) continue;
      if (existing.some(source => object(source) && ufocatOwner(source) && source.canonical_input_id === member.canonical_input_id &&
          source.source_row_hash === member.source_row_hash)) continue;
      additions.push(member);
    }
    return additions.length ? {...event, source_records: [...existing, ...additions]} : event;
  }
  return Object.freeze({referenceEntries, references: event => referenceEntries(event).map(entry => entry.text), createIndex, withIndexedCitations});
});
