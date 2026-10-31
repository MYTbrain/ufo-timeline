(function (root, factory) {
  "use strict";
  const api = factory(root);
  if (typeof module === "object" && module && module.exports) module.exports = api;
  if (root) root.UfoShareView = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function (root) {
  "use strict";

  const VERSION = 1;
  const MAX_TOKEN_LENGTH = 32768;
  const MAX_JSON_BYTES = 24576;
  const MAX_DEPTH = 12;
  const MAX_ITEMS = 4096;
  const MAX_STRING_LENGTH = 8192;
  const ROOT_KEYS = new Set(["time", "map", "case", "filters", "settings", "region", "layers", "controls", "section", "selection"]);
  const FORBIDDEN_KEYS = new Set(["__proto__", "prototype", "constructor"]);

  // Wire format v2. These dictionaries are permanent protocol data, NOT app
  // defaults. Never edit them for a UI/default change: introduce a new format
  // version instead. Every omitted/different value is represented explicitly.
  const COMPACT_VERSION = 2;
  const V2_KEYS = Object.freeze((
    "abduction air airports analysisBaselineMode animals army basemap being beingSearch beingTypes between bounds case caseShapeIndex center chronology claimedUfoBaseVisibility claimedUfoBases classes colorMode combineMode connectionRadiusKm connectionsEnabled contractor controls convergence coordinateScope country craftScope craftTypeColorOverrides cropPositionQuality crops dateScope defense_research depth direction displayMode drawingActive east emphasizeIntersections enabled encounterSelectionIds encounters end endpointBuffer evidenceMode facets famousCaseOrder filterTarget filters fontScaleMode gap_gt_30 gap_le_1 gap_le_2 gap_le_30 gap_le_7 hiddenKinds hideLowPrecision hideNonExactDates hideTraces highlightedEventId highways hopDepth hopDirection id includeAmbiguous isolation keyword knownDirectionOnly lat layers legendDirectionExpanded lng map mapLabelScaleMode mapLegendCraftSolo mapLegendEventSelection mapMode maxDistanceKm maxIso maxOrdinal metric military militaryBranchVisibility military_test minIso minOrdinal mode modeActive national_lab naval north observatory onlyShowTraceLinkedFacilities other other_research overlayVisibility passes playbackSpeed playbackTracePersistence playbackWindowDays playbackWindowPreset pointOnly positionQuality precision radiusKm radiusMeters region relation relationWindow researchCategoryVisibility researchSites resolution resultsFollowPlayback resultsSortMode savedTraceMode section selectEvents selectTraces selectedCellId selectedKeys selectedRecordId selectedValues selection settings shapes showEventsAssociatedWithSelectedTraces showRadius showSelectedEvents showSelectedTraces showTraceDirectionArrows showTracesAssociatedWithSelectedEvents showTrailLegend sites source sources south space_launch start support themeMode time timeScope tool traceAnalysisEnabled traceBoldnessScale traceBucketVisibility traceFacilityFilter traceMode traceWidthMode traceWidthScale traces type ufoFocus visible west zoom"
  ).split(" "));
  const V2_KEY_TO_CODE = new Map(V2_KEYS.map(function (key, index) { return [key, "k" + index.toString(36)]; }));
  const V2_CODE_TO_KEY = new Map(V2_KEYS.map(function (key, index) { return ["k" + index.toString(36), key]; }));
  function freezeProtocol(value) {
    if (value && typeof value === "object") {
      Object.keys(value).forEach(function (key) { freezeProtocol(value[key]); });
      Object.freeze(value);
    }
    return value;
  }
  const V2_BASELINE = freezeProtocol({
    time: { start: null, end: null, mode: "full", visible: null }, map: null, case: "",
    filters: {
      facets: {
        source: { mode: "all", selectedValues: [] },
        type: { mode: "subset", selectedValues: ["Beam", "Changing / irregular", "Chevron", "Cigar", "Circle", "Cone", "Crescent", "Cross", "Cylinder", "Diamond", "Disk", "Fireball", "Flash", "Formation", "Landing", "Light", "Linear", "Oval / egg", "Rectangle", "Sphere / orb", "Star-like", "Teardrop", "Triangle"] },
        precision: { mode: "all", selectedValues: [] },
      },
      keyword: "", hideLowPrecision: false, hideNonExactDates: true, encounterSelectionIds: null,
    },
    settings: {
      colorMode: "craft_type", mapMode: "heatmap", traceMode: "static", resultsSortMode: "date_asc",
      famousCaseOrder: "chronological", traceWidthMode: "auto", resultsFollowPlayback: true,
      showTrailLegend: false, showTraceDirectionArrows: false, legendDirectionExpanded: true,
      overlayVisibility: { airports: false, highways: false, military: true, researchSites: true },
      claimedUfoBaseVisibility: { sites: false, traces: false },
      militaryBranchVisibility: { air: true, naval: true, army: true, other: false },
      researchCategoryVisibility: { national_lab: true, defense_research: true, military_test: true, contractor: true, observatory: true, space_launch: true, other_research: true },
      traceBucketVisibility: { gap_le_1: true, gap_le_2: true, gap_le_7: false, gap_le_30: false, gap_gt_30: false },
      traceWidthScale: 1, traceBoldnessScale: 1, playbackSpeed: 4, playbackWindowDays: 365,
      playbackWindowPreset: "365", playbackTracePersistence: "normal", themeMode: "dark",
      fontScaleMode: "default", mapLabelScaleMode: "default", craftTypeColorOverrides: {},
      traceFacilityFilter: { enabled: false, radiusKm: 10, evidenceMode: "source_coordinates", onlyShowTraceLinkedFacilities: true,
        sources: { military: true, researchSites: true, claimedUfoBases: false },
        classes: { start: true, end: true, between: true, passes: false } },
      mapLegendCraftSolo: null, analysisBaselineMode: "other_dates_balanced",
      mapLegendEventSelection: { mode: "all", colorMode: "craft_type", selectedKeys: [] },
    },
    region: {
      drawingActive: false, modeActive: false, tool: "rectangle", shapes: [], pointOnly: false,
      selectTraces: true, selectEvents: false, showSelectedTraces: true, showSelectedEvents: false,
      showEventsAssociatedWithSelectedTraces: true, showTracesAssociatedWithSelectedEvents: false,
      combineMode: "any", displayMode: "hide-unselected", depth: 0, direction: "forward",
      knownDirectionOnly: false, country: "", caseShapeIndex: -1,
    },
    layers: {
      encounters: { enabled: false, displayMode: "markers", connectionsEnabled: false, connectionRadiusKm: 250,
        hiddenKinds: [], includeAmbiguous: false, filterTarget: "overlay", abduction: "any", being: "any",
        beingTypes: [], beingSearch: "", highlightedEventId: null },
      crops: { enabled: false, dateScope: "window", chronology: { enabled: false, relation: "off", coordinateScope: "field", maxDistanceKm: 250 },
        ufoFocus: { relationWindow: "off", positionQuality: "source", cropPositionQuality: "field", radiusKm: 25,
          traceAnalysisEnabled: false, hopDepth: 1, hopDirection: "both", showRadius: true, emphasizeIntersections: true, isolation: false },
        selectedRecordId: null },
      animals: { enabled: false, dateScope: "window" },
      convergence: { enabled: false, hideTraces: true, endpointBuffer: "buffer5", resolution: "equal_area_259_km2",
        craftScope: "all_no_lights", timeScope: "all_time", metric: "lift", support: "limited_candidate",
        savedTraceMode: null, selectedCellId: null },
    },
    section: "map", selection: null,
  });

  function invalid() { return new Error("This shared view is invalid or incomplete. Ask for a new link."); }
  function tooLarge() { return new Error("This view is too large to share in a link. Reduce the selection and try again."); }

  function plainObject(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return false;
    const prototype = Object.getPrototypeOf(value);
    return prototype === null || prototype === Object.prototype;
  }

  // Read data descriptors rather than evaluating getters or toJSON methods.
  // Root shape validation remains separate from the application's field-level
  // validation; nothing decoded here should be blindly merged into app state.
  function cloneSnapshot(snapshot) {
    if (!plainObject(snapshot)) throw invalid();
    const ancestors = new Set();
    let items = 0;
    let characters = 0;
    function clone(value, depth) {
      items += 1;
      if (items > MAX_ITEMS || depth > MAX_DEPTH) throw tooLarge();
      if (value === null || typeof value === "boolean") return value;
      if (typeof value === "string") {
        characters += value.length;
        if (value.length > MAX_STRING_LENGTH || characters > MAX_JSON_BYTES) throw tooLarge();
        return value;
      }
      if (typeof value === "number") {
        if (!Number.isFinite(value)) throw invalid();
        return value;
      }
      const array = Array.isArray(value);
      if (!array && !plainObject(value)) throw invalid();
      if (ancestors.has(value)) throw invalid();
      const keys = Reflect.ownKeys(value);
      if (keys.length > MAX_ITEMS) throw tooLarge();
      if (keys.some(function (key) { return typeof key !== "string" || FORBIDDEN_KEYS.has(key); })) throw invalid();
      ancestors.add(value);
      let copy;
      if (array) {
        if (value.length > MAX_ITEMS) throw tooLarge();
        // Sparse arrays and extra named array properties are not JSON fields.
        if (keys.length !== value.length + 1) throw invalid();
        copy = [];
        for (let index = 0; index < value.length; index += 1) {
          const descriptor = Object.getOwnPropertyDescriptor(value, String(index));
          if (!descriptor || !descriptor.enumerable || !Object.prototype.hasOwnProperty.call(descriptor, "value")) throw invalid();
          copy.push(clone(descriptor.value, depth + 1));
        }
      } else {
        copy = {};
        keys.forEach(function (key) {
          if (key.length > 128) throw tooLarge();
          characters += key.length;
          if (characters > MAX_JSON_BYTES) throw tooLarge();
          if (depth === 0 && !ROOT_KEYS.has(key)) throw invalid();
          const descriptor = Object.getOwnPropertyDescriptor(value, key);
          if (!descriptor.enumerable || !Object.prototype.hasOwnProperty.call(descriptor, "value")) throw invalid();
          copy[key] = clone(descriptor.value, depth + 1);
        });
      }
      ancestors.delete(value);
      return copy;
    }
    return clone(snapshot, 0);
  }

  function utf8Bytes(text) {
    if (typeof root.TextEncoder === "function") return new root.TextEncoder().encode(text);
    if (root.Buffer) return root.Buffer.from(text, "utf8");
    throw new Error("This browser cannot create shared views. Try a newer browser.");
  }

  function utf8Text(bytes) {
    if (typeof root.TextDecoder === "function") return new root.TextDecoder("utf-8", { fatal: true }).decode(bytes);
    if (root.Buffer) {
      const buffer = root.Buffer.from(bytes);
      const text = buffer.toString("utf8");
      if (!root.Buffer.from(text, "utf8").equals(buffer)) throw invalid();
      return text;
    }
    throw new Error("This browser cannot open shared views. Try a newer browser.");
  }

  function base64url(bytes) {
    let encoded;
    if (root.Buffer) encoded = root.Buffer.from(bytes).toString("base64");
    else {
      let binary = "";
      for (let index = 0; index < bytes.length; index += 1) binary += String.fromCharCode(bytes[index]);
      encoded = root.btoa(binary);
    }
    return encoded.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  function encode(snapshot) {
    const copy = cloneSnapshot(snapshot);
    const bytes = utf8Bytes(JSON.stringify(Object.assign({ v: VERSION }, copy)));
    if (bytes.length > MAX_JSON_BYTES) throw tooLarge();
    const token = base64url(bytes);
    if (token.length > MAX_TOKEN_LENGTH) throw tooLarge();
    return token;
  }

  function decode(token) {
    if (typeof token !== "string" || !token) throw invalid();
    if (token.length > MAX_TOKEN_LENGTH) throw tooLarge();
    if (!/^[A-Za-z0-9_-]+$/.test(token) || token.length % 4 === 1) throw invalid();
    let payload;
    try {
      const base64 = token.replace(/-/g, "+").replace(/_/g, "/");
      const bytes = root.Buffer ? root.Buffer.from(base64, "base64") : Uint8Array.from(root.atob(base64), function (character) { return character.charCodeAt(0); });
      if (bytes.length > MAX_JSON_BYTES || base64url(bytes) !== token) throw invalid();
      payload = JSON.parse(utf8Text(bytes));
    } catch (_error) {
      throw invalid();
    }
    if (!plainObject(payload) || !Object.prototype.hasOwnProperty.call(payload, "v")) throw invalid();
    if (Number.isInteger(payload.v) && payload.v > VERSION) throw new Error("This link uses a newer shared-view format. Refresh the app and try again.");
    if (payload.v !== VERSION) throw new Error("This shared-view format is not supported. Ask for a new link.");
    delete payload.v;
    return cloneSnapshot(payload);
  }

  function sameValue(left, right) {
    if (left === right) return true;
    if (!left || !right || typeof left !== "object" || typeof right !== "object") return false;
    if (Array.isArray(left) !== Array.isArray(right)) return false;
    const keys = Object.keys(left);
    return keys.length === Object.keys(right).length && keys.every(function (key) {
      return Object.prototype.hasOwnProperty.call(right, key) && sameValue(left[key], right[key]);
    });
  }

  // Tagged delta nodes distinguish absent fields from explicit null/false/empty:
  // [0] keeps a baseline value; [1,value] replaces it; [2,changes,removed] edits
  // an object. Arrays are values and always retain their order.
  function makeDelta(value, baseline) {
    if (sameValue(value, baseline)) return [0];
    if (!plainObject(value) || !plainObject(baseline)) return [1, value];
    const changes = {};
    Object.keys(value).forEach(function (key) {
      if (!Object.prototype.hasOwnProperty.call(baseline, key) || !sameValue(value[key], baseline[key])) changes[key] = makeDelta(value[key], baseline[key]);
    });
    return [2, changes, Object.keys(baseline).filter(function (key) { return !Object.prototype.hasOwnProperty.call(value, key); })];
  }

  function packKeys(value) {
    if (!value || typeof value !== "object") return value;
    if (Array.isArray(value)) return value.map(packKeys);
    const packed = {};
    Object.keys(value).forEach(function (key) { packed[V2_KEY_TO_CODE.get(key) || "~" + key] = packKeys(value[key]); });
    return packed;
  }

  function unpackKeys(value) {
    let items = 0;
    function unpack(item, depth) {
      items += 1;
      // Delta tags add container levels. The reconstructed snapshot is checked
      // again against the original stricter depth, item and field-size limits.
      if (items > MAX_ITEMS * 5 || depth > MAX_DEPTH * 3 + 3) throw tooLarge();
      if (item === null || typeof item === "boolean") return item;
      if (typeof item === "number") { if (!Number.isFinite(item)) throw invalid(); return item; }
      if (typeof item === "string") { if (item.length > MAX_STRING_LENGTH) throw tooLarge(); return item; }
      if (Array.isArray(item)) return item.map(function (child) { return unpack(child, depth + 1); });
      if (!plainObject(item)) throw invalid();
      const decoded = Object.create(null);
      Object.keys(item).forEach(function (code) {
        let key;
        if (V2_CODE_TO_KEY.has(code)) key = V2_CODE_TO_KEY.get(code);
        else if (code.charAt(0) === "~") {
          key = code.slice(1);
          if (V2_KEY_TO_CODE.has(key)) throw invalid();
        } else throw invalid();
        if (key.length > 128) throw tooLarge();
        if (FORBIDDEN_KEYS.has(key) || Object.prototype.hasOwnProperty.call(decoded, key)) throw invalid();
        decoded[key] = unpack(item[code], depth + 1);
      });
      return decoded;
    }
    return unpack(value, 0);
  }

  function applyDelta(delta, baseline, depth) {
    if (depth > MAX_DEPTH) throw tooLarge();
    if (!Array.isArray(delta)) throw invalid();
    if (delta[0] === 0 && delta.length === 1 && baseline !== undefined) return baseline;
    if (delta[0] === 1 && delta.length === 2) return delta[1];
    if (delta[0] !== 2 || delta.length !== 3 || !plainObject(baseline) || !plainObject(delta[1]) || !Array.isArray(delta[2])) throw invalid();
    const result = Object.create(null);
    Object.keys(baseline).forEach(function (key) { result[key] = baseline[key]; });
    const removed = new Set();
    delta[2].forEach(function (key) {
      if (typeof key !== "string" || FORBIDDEN_KEYS.has(key) || removed.has(key) ||
          !Object.prototype.hasOwnProperty.call(baseline, key) || Object.prototype.hasOwnProperty.call(delta[1], key)) throw invalid();
      removed.add(key);
      delete result[key];
    });
    Object.keys(delta[1]).forEach(function (key) {
      if (FORBIDDEN_KEYS.has(key)) throw invalid();
      result[key] = applyDelta(delta[1][key], Object.prototype.hasOwnProperty.call(baseline, key) ? baseline[key] : undefined, depth + 1);
    });
    return result;
  }

  async function gzipBytes(bytes, decompress) {
    const Stream = decompress ? root.DecompressionStream : root.CompressionStream;
    if (typeof Stream !== "function" || typeof root.Blob !== "function") {
      throw new Error("This browser cannot " + (decompress ? "open compact" : "compress") + " shared views. Try a newer browser.");
    }
    const reader = new root.Blob([bytes]).stream().pipeThrough(new Stream("gzip")).getReader();
    const chunks = [];
    // Compression may add a small header to incompressible input. Permit that
    // candidate to finish so encodeCompact can choose the shorter v1 fallback;
    // decoded data always retains the stricter pre-parse size cap.
    const limit = decompress ? MAX_JSON_BYTES : MAX_TOKEN_LENGTH;
    let length = 0;
    try {
      for (;;) {
        const next = await reader.read();
        if (next.done) break;
        length += next.value.byteLength;
        if (length > limit) {
          await reader.cancel();
          throw tooLarge();
        }
        chunks.push(next.value);
      }
    } finally { reader.releaseLock(); }
    const result = new Uint8Array(length);
    let offset = 0;
    chunks.forEach(function (chunk) { result.set(chunk, offset); offset += chunk.byteLength; });
    return result;
  }

  async function encodeCompact(snapshot) {
    // v1 remains a valid fallback for small payloads and older browsers.
    const legacy = encode(snapshot);
    if (typeof root.CompressionStream !== "function" || typeof root.Blob !== "function") return legacy;
    const copy = cloneSnapshot(snapshot);
    const candidates = [["f", packKeys(copy)], ["d", packKeys(makeDelta(copy, V2_BASELINE))]];
    let best = legacy;
    for (const candidate of candidates) {
      const bytes = utf8Bytes(JSON.stringify(candidate));
      if (bytes.length > MAX_JSON_BYTES) continue;
      const compressed = await gzipBytes(bytes, false);
      const token = "2." + base64url(compressed);
      if (token.length < best.length) best = token;
    }
    return best;
  }

  async function decodeAny(token) {
    if (typeof token !== "string" || !token) throw invalid();
    if (token.length > MAX_TOKEN_LENGTH) throw tooLarge();
    const prefix = /^(\d+)\./.exec(token);
    if (!prefix) return decode(token);
    if (Number(prefix[1]) > COMPACT_VERSION) throw new Error("This link uses a newer shared-view format. Refresh the app and try again.");
    if (prefix[1] !== "2") throw new Error("This shared-view format is not supported. Ask for a new link.");
    const encoded = token.slice(2);
    if (!encoded || !/^[A-Za-z0-9_-]+$/.test(encoded) || encoded.length % 4 === 1) throw invalid();
    let bytes;
    try {
      const base64 = encoded.replace(/-/g, "+").replace(/_/g, "/");
      bytes = root.Buffer ? root.Buffer.from(base64, "base64") : Uint8Array.from(root.atob(base64), function (character) { return character.charCodeAt(0); });
      if (bytes.length > MAX_JSON_BYTES || base64url(bytes) !== encoded) throw invalid();
    } catch (_error) { throw invalid(); }
    let unpacked;
    try {
      const payload = JSON.parse(utf8Text(await gzipBytes(bytes, true)));
      if (!Array.isArray(payload) || payload.length !== 2 || !["f", "d"].includes(payload[0])) throw invalid();
      unpacked = unpackKeys(payload[1]);
      if (payload[0] === "d") unpacked = applyDelta(unpacked, V2_BASELINE, 0);
    } catch (error) {
      if (error && /too large|This browser/.test(error.message)) throw error;
      throw invalid();
    }
    return cloneSnapshot(unpacked);
  }

  function parseUrl(value) {
    if (typeof value !== "string" || value.length > MAX_TOKEN_LENGTH + 8192) throw invalid();
    let url;
    try { url = new root.URL(value); } catch (_error) { throw new Error("A complete website address is needed to share this view."); }
    if (!["https:", "http:"].includes(url.protocol) || url.username || url.password) throw new Error("Shared views need an ordinary HTTP or HTTPS website address.");
    return url;
  }

  function safeSectionHash(hash) {
    return /^#analysis-section-[a-z][a-z0-9-]{0,63}$/.test(hash) ||
      /^#analysis-(?:crop|animal|relationship)-context$/.test(hash) ? hash : "";
  }

  function fragmentParams(url) {
    return new root.URLSearchParams(url.hash.slice(1));
  }

  // Detect presence separately from validation so malformed shared links never
  // fall through to progressive startup or unrelated query automation.
  function hasViewUrl(value) {
    try {
      const url = new root.URL(value);
      return url.searchParams.has("view") || fragmentParams(url).has("view");
    } catch (_error) { return false; }
  }

  function readSectionHash(value) {
    const url = parseUrl(value);
    const direct = safeSectionHash(url.hash);
    if (direct) return direct;
    const params = fragmentParams(url);
    const sections = params.getAll("section");
    return params.has("view") && sections.length === 1 ? safeSectionHash("#" + sections[0]) : "";
  }

  function sharedTokens(url) {
    // Keep old query links readable, but reject ambiguous combinations.
    const views = url.searchParams.getAll("view").concat(fragmentParams(url).getAll("view"));
    if (views.length > 1) throw invalid();
    return views;
  }

  function withViewFragment(url, token) {
    const section = readSectionHash(url.toString());
    const params = new root.URLSearchParams();
    params.set("view", token);
    if (section) params.set("section", section.slice(1));
    // Fragments stay in the browser rather than entering the HTTP request URL.
    url.search = "";
    url.hash = params.toString();
    return url.toString();
  }

  function buildUrl(snapshot, baseUrl) {
    return withViewFragment(parseUrl(baseUrl), encode(snapshot));
  }

  function readUrl(value) {
    const url = parseUrl(value);
    const views = sharedTokens(url);
    if (!views.length) return null;
    if (views.length !== 1) throw invalid();
    return decode(views[0]);
  }

  async function buildCompactUrl(snapshot, baseUrl) {
    return withViewFragment(parseUrl(baseUrl), await encodeCompact(snapshot));
  }

  async function readAnyUrl(value) {
    const url = parseUrl(value);
    const views = sharedTokens(url);
    if (!views.length) return null;
    if (views.length !== 1) throw invalid();
    return decodeAny(views[0]);
  }

  return Object.freeze({ VERSION: VERSION, COMPACT_VERSION: COMPACT_VERSION, MAX_TOKEN_LENGTH: MAX_TOKEN_LENGTH,
    hasViewUrl: hasViewUrl, readSectionHash: readSectionHash,
    encode: encode, decode: decode, buildUrl: buildUrl, readUrl: readUrl,
    encodeCompact: encodeCompact, decodeAny: decodeAny, buildCompactUrl: buildCompactUrl, readAnyUrl: readAnyUrl });
});
