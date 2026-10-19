(function (root, factory) {
  "use strict";
  const api = factory(root);
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UfoAnalysisSessionSources = api;
})(typeof self !== "undefined" ? self : globalThis, function (root) {
  "use strict";
  const MAX_COMPRESSED = 8 * 1024 * 1024, MAX_DECODED = 16 * 1024 * 1024;
  const text = value => String(value == null ? "" : value).trim();
  const list = value => Array.isArray(value) ? value : [];
  const safeUrl = value => { try { const parsed = new URL(value); return ["http:", "https:"].includes(parsed.protocol) ? parsed.href : ""; } catch (_) { return ""; } };
  function create(input) {
    const options = input || {}, fetcher = options.fetch || root.fetch && root.fetch.bind(root), crypto = options.crypto || root.crypto;
    const base = new URL(options.baseUrl || root.location && root.location.href || "http://localhost/");
    const manifests = new Map(), catalogs = new Map(), chunks = new Map(), queue = []; let active = 0;
    if (typeof fetcher !== "function") throw new Error("Source inspection requires a fetch implementation.");
    function limited(job) { return new Promise((resolve, reject) => { queue.push({ job, resolve, reject }); pump(); }); }
    function pump() { while (active < 6 && queue.length) { const item = queue.shift(); active++; Promise.resolve().then(item.job).then(item.resolve, item.reject).finally(() => { active--; pump(); }); } }
    function cached(map, key, factory) {
      if (map.has(key)) { const value = map.get(key); map.delete(key); map.set(key, value); return value; }
      const promise = Promise.resolve().then(factory).catch(error => { if (map.get(key) === promise) map.delete(key); throw error; }); map.set(key, promise); return promise;
    }
    async function readBytes(url, max, cache) {
      const response = await fetcher(url, { cache: cache || "force-cache" });
      if (!response || !response.ok) throw new Error("Source metadata request failed" + (response ? " (" + response.status + ")" : "") + ".");
      const length = Number(response.headers && response.headers.get("content-length")); if (length > max) throw new Error("Source metadata response exceeds its size limit.");
      // Read with a strict bound before concatenating; malformed declarations
      // cannot turn a lazy source lookup into an unbounded response allocation.
      if (response.body && typeof response.body.getReader === "function") {
        const reader = response.body.getReader(), parts = []; let total = 0;
        try { for (;;) { const item = await reader.read(); if (item.done) break; total += item.value.byteLength; if (total > max) { await reader.cancel(); throw new Error("Source metadata response exceeds its size limit."); } parts.push(item.value); } }
        finally { reader.releaseLock(); }
        const joined = new Uint8Array(total); let offset = 0; parts.forEach(part => { joined.set(part, offset); offset += part.byteLength; }); return joined;
      }
      const bytes = new Uint8Array(await response.arrayBuffer()); if (bytes.length > max) throw new Error("Source metadata response exceeds its size limit."); return bytes;
    }
    function assetUrl(manifestUrl, manifest, path) {
      const target = new URL(path, manifest.assetBaseUrl ? new URL(manifest.assetBaseUrl, manifestUrl) : new URL(".", manifestUrl));
      if (!["http:", "https:"].includes(target.protocol)) throw new Error("Source metadata URL must use HTTP or HTTPS."); return target.href;
    }
    function manifest(kind) { return cached(manifests, kind, () => limited(async () => {
      const domain = kind === "crops" ? "crop_circles" : "animal_mutilations", url = new URL("data/" + domain + "/manifest.json", base).href;
      const bytes = await readBytes(url, 512 * 1024, "no-cache"), data = JSON.parse(new TextDecoder().decode(bytes));
      if (!data.details || !Array.isArray(data.details.files) || !Number.isSafeInteger(data.details.chunkSize) || data.details.chunkSize <= 0 || !data.releaseId) throw new Error("Source metadata manifest has no validated detail layout.");
      return { data, url };
    })); }
    async function decode(bytes, limit) {
      if (options.decompress) { const decoded = new Uint8Array(await options.decompress(bytes)); if (decoded.length > limit) throw new Error("Decoded source metadata exceeds its size limit."); return decoded; }
      if (typeof DecompressionStream !== "function") throw new Error("This browser cannot decompress the pinned source metadata.");
      const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip")), reader = stream.getReader(), parts = []; let total = 0;
      try { for (;;) { const item = await reader.read(); if (item.done) break; total += item.value.byteLength; if (total > limit) { await reader.cancel(); throw new Error("Decoded source metadata exceeds its size limit."); } parts.push(item.value); } }
      finally { reader.releaseLock(); }
      const decoded = new Uint8Array(total); let offset = 0; parts.forEach(part => { decoded.set(part, offset); offset += part.byteLength; }); return decoded;
    }
    async function artifact(value, declaration, fallbackPath) {
      if (!declaration || !Number.isSafeInteger(declaration.bytes) || declaration.bytes <= 0 || declaration.bytes > MAX_COMPRESSED || !/^[a-f0-9]{64}$/i.test(text(declaration.sha256))) throw new Error("Source metadata artifact lacks a bounded size and SHA-256 declaration.");
      const decodedSize = declaration.decodedBytes ?? declaration.decoded_bytes;
      if (!Number.isSafeInteger(decodedSize) || decodedSize <= 0 || decodedSize > MAX_DECODED) throw new Error("Source metadata artifact lacks a bounded decoded-size declaration.");
      const url = assetUrl(value.url, value.data, declaration.path || fallbackPath), bytes = await readBytes(url, declaration.bytes);
      if (bytes.length !== declaration.bytes) throw new Error("Source metadata compressed-byte count does not match its manifest.");
      if (!crypto || !crypto.subtle) throw new Error("Source metadata integrity checking is unavailable.");
      const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)), byte => byte.toString(16).padStart(2, "0")).join("");
      if (digest !== text(declaration.sha256).toLowerCase()) throw new Error("Source metadata SHA-256 does not match its pinned manifest.");
      const decoded = await decode(bytes, decodedSize); if (decoded.length !== decodedSize) throw new Error("Source metadata decoded-byte count does not match its manifest.");
      return JSON.parse(new TextDecoder().decode(decoded));
    }
    function catalog(kind, value) { return cached(catalogs, kind + ":" + value.data.releaseId, () => limited(async () => {
      const data = await artifact(value, value.data.catalog, "catalog.json.gz"), rows = new Map(); if (!Array.isArray(data)) throw new Error("Animal source catalog is malformed.");
      data.forEach(row => { const id = text(row[0]); if (!id || rows.has(id)) throw new Error("Animal source catalog has duplicate or missing IDs."); rows.set(id, row); });
      if (Number.isInteger(value.data.catalog.recordCount) && rows.size !== value.data.catalog.recordCount) throw new Error("Animal source catalog record count disagrees with its manifest."); return rows;
    })); }
    function chunk(kind, value, index) {
      const key = kind + ":" + value.data.releaseId + ":" + index;
      return cached(chunks, key, () => limited(async () => {
        const declaration = value.data.details.files[index]; if (!declaration) throw new Error("The exact source metadata chunk is not declared.");
        const data = await artifact(value, declaration), count = declaration.recordCount ?? declaration.record_count;
        if (!data || Array.isArray(data) || typeof data !== "object" || Number.isInteger(count) && Object.keys(data).length !== count) throw new Error("Source metadata detail count disagrees with its manifest."); return data;
      })).finally(() => { while (chunks.size > 8) chunks.delete(chunks.keys().next().value); });
    }
    function source(detail, kind) {
      if (kind === "crops") {
        const exact = safeUrl(detail.sourceDescriptionUrl) || list(detail.sources).map(item => safeUrl(item && item.recordUrl)).find(Boolean);
        if (exact) return { url: exact, label: "Source record" };
        const archive = list(detail.sources).map(item => safeUrl(item && item.collectionUrl)).find(Boolean) || list(detail.links).map(safeUrl).find(Boolean);
        return { url: archive || "", label: archive ? "Source catalog / archive" : "" };
      }
      const exact = list(detail.sourceRefs).map(item => safeUrl(item && item.url)).find(Boolean); return { url: exact || "", label: exact ? "Source record" : "" };
    }
    async function enrichRow(original) {
      const identity = original.contextRecord; if (!identity || !["crops", "animals"].includes(identity.kind) || !text(identity.id)) return original;
      const kind = identity.kind, value = await manifest(kind); let index, metadata;
      if (kind === "crops") {
        if (!Number.isSafeInteger(identity.rank) || identity.rank < 0 || Number.isInteger(value.data.counts && value.data.counts.events) && identity.rank >= value.data.counts.events) throw new Error("The crop source ID has no validated full-catalog rank.");
        index = Math.floor(identity.rank / value.data.details.chunkSize);
      } else {
        const records = await catalog(kind, value); metadata = records.get(text(identity.id)); if (!metadata) throw new Error("The exact animal source ID is absent from the pinned catalog."); index = metadata[9];
        if (!Number.isSafeInteger(index) || index < 0) throw new Error("The exact animal source ID has no declared detail chunk.");
      }
      const details = await chunk(kind, value, index), detail = details[text(identity.id)];
      if (!detail || text(detail.id) !== text(identity.id)) throw new Error("The exact context ID is absent from its declared source chunk; no approximate join was used.");
      if (detail.legalPublicationRestriction === true) throw new Error("This source record is withheld from public display.");
      const row = Object.assign({}, original), location = text(detail.location || metadata && metadata[3]), name = text(detail.title || metadata && metadata[1]) || (kind === "crops" ? "Reported crop formation" : "Reported animal case") + (location ? " · " + location : "");
      const summary = text(detail.sourceDescription || detail.catalogSummary || detail.summary || metadata && metadata[2]), families = list(detail.sourceFamilies).filter(item => typeof item === "string" && text(item));
      const names = families.length ? families : kind === "crops" ? list(detail.sources).map(item => text(item && item.name)).filter(Boolean) : list(detail.sourceRefs).map(item => text(item && (item.publisher || item.title))).filter(Boolean), link = source(detail, kind);
      // Pair identity and source-calendar membership remain untouched; source
      // records merely decorate the actual held context endpoint on this page.
      row.label = original.id === identity.id ? name : name + " · " + text(original.label);
      if (location) row.location = location;
      if (names.length) row.source = Array.from(new Set(names)).join("; ");
      row.description = summary;
      row.detail = [text(original.detail), summary, detail.mappingNotes ? "Location evidence: " + detail.mappingNotes : ""].filter(Boolean).join("\n");
      row.sourceUrl = link.url; row.sourceLinkLabel = link.label; row.sourceMetadataStatus = "ready"; delete row.sourceMetadataError;
      return row;
    }
    async function enrich(result) {
      const output = Object.assign({}, result, { groups: Object.assign({}, result && result.groups), notes: list(result && result.notes).slice() });
      const errors = [];
      await Promise.all(["A", "B"].map(async slot => {
        const original = result && result.groups && result.groups[slot]; if (!original) return;
        const side = Object.assign({}, original); side.rows = await Promise.all(list(original.rows).map(async row => {
          try { return await enrichRow(row); } catch (error) { const note = text(error && error.message || error); errors.push(note); return Object.assign({}, row, { sourceMetadataStatus: "unavailable", sourceMetadataError: note }); }
        })); output.groups[slot] = side;
      }));
      if (errors.length) output.notes.push("Some source details could not be loaded; category membership and counts are unchanged. Retry opening this category. " + Array.from(new Set(errors)).join(" "));
      return output;
    }
    return Object.freeze({ enrich });
  }
  return Object.freeze({ create });
});
