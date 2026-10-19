(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UfoAnalysisOverviewModel = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const SCHEMA_ID = "ufo-analysis-overview-v1";
  const UNKNOWN = "__unknown__", NOT_INDEXED = "__not_indexed__", UNAVAILABLE = "__unavailable__";
  const SPECIAL = new Set([UNKNOWN, NOT_INDEXED, UNAVAILABLE]);
  const UNKNOWN_VALUES = new Set(["", "unknown", "unavailable", "unresolved", "unparsed", "not_indexed", "not_provided", "none", "null", "undefined", "n/a", "not provided"]);
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const DEFINITIONS = [
    ["craft_decade", "Craft through time", "How does the mix of reported craft categories vary by decade?", "craft", "decade", "craft"],
    ["craft_country", "Craft across places", "How does reported craft composition vary between recorded countries?", "geography", "country", "craft"],
    ["being_craft", "Beings and craft", "Which being descriptions and craft categories occur in the same reports?", "encounters", "being", "craft"],
    ["craft_month", "Craft across the calendar", "How does reported craft composition vary by calendar month?", "craft", "month", "craft"],
    ["month_decade", "Seasonality through time", "How does the distribution of reporting months vary between decades?", "time", "decade", "month"],
    ["source_decade", "Sources through time", "How does catalog source composition vary between decades?", "sources-quality", "decade", "source"],
    ["being_decade", "Being descriptions through time", "How does the mix of indexed being descriptions vary by decade?", "encounters", "decade", "being"],
  ];
  function integer(value) { return typeof value === "number" && Number.isSafeInteger(value) ? value : null; }
  function known(value) {
    if (typeof value !== "string" && typeof value !== "number") return "";
    const text = String(value).trim();
    return UNKNOWN_VALUES.has(text.toLowerCase()) ? "" : text;
  }
  function category(key, label) { return { key, label: label == null ? key : label }; }
  function unknown() { return category(UNKNOWN, "Unknown / unspecified"); }
  function civilFromOrdinal(value) {
    const ordinal = integer(value);
    if (ordinal == null || ordinal < 1) return null;
    const z = ordinal - 719163 + 719468;
    const era = Math.floor(z / 146097), dayOfEra = z - era * 146097;
    const yearOfEra = Math.floor((dayOfEra - Math.floor(dayOfEra / 1460) + Math.floor(dayOfEra / 36524) - Math.floor(dayOfEra / 146096)) / 365);
    let year = yearOfEra + era * 400;
    const dayOfYear = dayOfEra - (365 * yearOfEra + Math.floor(yearOfEra / 4) - Math.floor(yearOfEra / 100));
    const part = Math.floor((5 * dayOfYear + 2) / 153);
    const month = part + (part < 10 ? 3 : -9), day = dayOfYear - Math.floor((153 * part + 2) / 5) + 1;
    year += month <= 2 ? 1 : 0;
    return { year, month, day };
  }
  function calendar(row) {
    const empty = { decade: [unknown()], month: [unknown()] };
    if (row.encounterOccurrenceDateExcluded === true) return empty;
    const precision = known(row.datePrecision).toLowerCase();
    if (!precision || precision === "century") return empty;
    const fallback = integer(row.sortOrdinal);
    const startOrdinal = row.dateStartOrdinal == null ? fallback : integer(row.dateStartOrdinal);
    const endOrdinal = row.dateEndOrdinal == null ? fallback : integer(row.dateEndOrdinal);
    const start = civilFromOrdinal(startOrdinal), end = civilFromOrdinal(endOrdinal);
    if (!start || !end || startOrdinal > endOrdinal) return empty;
    const firstDecade = Math.floor(start.year / 10) * 10, lastDecade = Math.floor(end.year / 10) * 10;
    if (firstDecade === lastDecade) empty.decade = [category(String(firstDecade), firstDecade === 0 ? "1–9" : firstDecade + "s")];
    if (!["year", "year_only", "decade", "century"].includes(precision) && start.year === end.year && start.month === end.month) {
      empty.month = [category(String(start.month).padStart(2, "0"), MONTHS[start.month - 1])];
    }
    return empty;
  }
  function compareCategories(order) {
    return function (a, b) {
      const aSpecial = SPECIAL.has(a.key), bSpecial = SPECIAL.has(b.key);
      if (aSpecial !== bSpecial) return aSpecial ? 1 : -1;
      if (order === "chronological" && !aSpecial && !bSpecial) return Number(a.key) - Number(b.key);
      return a.label.localeCompare(b.label, "en") || a.key.localeCompare(b.key, "en");
    };
  }
  function createLane() { return { totalN: 0, eligibleN: 0, rows: new Map(), columns: new Map(), cells: new Map() }; }
  function addMargin(map, item) {
    const value = map.get(item.key);
    if (value) value.count += 1;
    else map.set(item.key, { key: item.key, label: item.label, count: 1 });
  }
  function addToLane(lane, rows, columns) {
    lane.totalN += 1;
    if (rows.some(item => !SPECIAL.has(item.key)) && columns.some(item => !SPECIAL.has(item.key))) lane.eligibleN += 1;
    rows.forEach(item => addMargin(lane.rows, item)); columns.forEach(item => addMargin(lane.columns, item));
    rows.forEach(row => columns.forEach(column => {
      const key = JSON.stringify([row.key, column.key]), value = lane.cells.get(key);
      if (value) value.count += 1;
      else lane.cells.set(key, { rowKey: row.key, columnKey: column.key, count: 1 });
    }));
  }
  function finishLane(lane, definition) {
    const rowOrder = ["decade", "month"].includes(definition[4]) ? "chronological" : "label";
    const columnOrder = ["decade", "month"].includes(definition[5]) ? "chronological" : "label";
    const rowTotals = Array.from(lane.rows.values()).sort(compareCategories(rowOrder));
    const columnTotals = Array.from(lane.columns.values()).sort(compareCategories(columnOrder));
    const lookup = lane.cells;
    return { totalN: lane.totalN, eligibleN: lane.eligibleN, unknownN: lane.totalN - lane.eligibleN, excludedN: 0,
      rowTotals, columnTotals,
      columns: columnTotals.map(item => ({ key: item.key, label: item.label, totalN: item.count })),
      rows: rowTotals.map(item => ({ key: item.key, label: item.label, totalN: item.count,
        counts: columnTotals.map(column => { const cell = lookup.get(JSON.stringify([item.key, column.key])); return cell ? cell.count : 0; }) })),
      cells: rowTotals.flatMap(row => columnTotals.flatMap(column => { const value = lookup.get(JSON.stringify([row.key, column.key])); return value ? [value] : []; })) };
  }
  function compute(options) {
    options = options || {};
    const api = options.encounterApi, taxonomy = api && Array.isArray(api.TAXONOMY) ? api.TAXONOMY : [];
    const maskLimit = Math.pow(2, taxonomy.length), mode = ["source_fields", "narrative"].includes(options.encounterEvidenceMode) ? options.encounterEvidenceMode : "all";
    const cards = DEFINITIONS.map(definition => ({ definition, lanes: { all: createLane(), beings: createLane(), abduction: createLane() } }));
    const coverage = { mappedN: 0, knownCraftN: 0, knownCountryN: 0, knownSourceN: 0, knownDecadeN: 0, knownMonthN: 0,
      encounterReadyN: 0, encounterUnavailableN: 0, beingN: 0, abductionN: 0, ambiguousAbductionN: 0,
      beingEvidenceUnavailableN: 0, abductionEvidenceUnavailableN: 0, beingNotIndexedN: 0, abductionNotIndexedN: 0,
      abductionOtherEvidenceModeN: 0, clockN: 0, durationN: 0 };
    let totalN = 0;
    function consume(row) {
      if (!row || typeof row !== "object") throw new Error("Overview rows must be report objects.");
      totalN += 1;
      const craft = known(row.craftType), source = known(row.source);
      const country = known(row.analysisCountry) || known(row.country) || known(row.sourceCountry);
      const date = calendar(row);
      const rawMask = integer(row.encounterBeingMask), ready = row.encounterEvidenceReady === true && options.encounterEvidenceReady !== false;
      let mask = rawMask, beingAvailable = ready && taxonomy.length > 0 && rawMask != null && rawMask >= 0 && rawMask < maskLimit;
      if (beingAvailable && mode !== "all" && rawMask > 0) {
        const sourceMask = integer(row.encounterSourceBeingMask), narrativeMask = integer(row.encounterNarrativeBeingMask);
        const selected = mode === "source_fields" ? sourceMask : narrativeMask;
        beingAvailable = row.encounterEvidenceProvenanceReady === true && [sourceMask, narrativeMask].every(value => value != null && value >= 0 && value < maskLimit)
          && (sourceMask | narrativeMask) === rawMask;
        mask = beingAvailable ? selected : 0;
      }
      const beings = beingAvailable && mask > 0 ? taxonomy.filter((item, index) => Boolean(mask & (1 << (Number.isInteger(item.bit) ? item.bit : index)))) : [];
      const code = integer(row.encounterAbductionCode), abductionAvailable = ready && code != null && code >= 0 && code <= 3;
      const reportedAbduction = abductionAvailable && (mode === "all" && (code === 1 || code === 2) || mode === "source_fields" && code === 1 || mode === "narrative" && code === 2);
      if (row.mapped === true || row.mapped == null && Number.isFinite(row.lat) && row.lat >= -90 && row.lat <= 90 && Number.isFinite(row.lon) && row.lon >= -180 && row.lon <= 180) coverage.mappedN += 1;
      if (craft) coverage.knownCraftN += 1; if (country) coverage.knownCountryN += 1; if (source) coverage.knownSourceN += 1;
      if (!SPECIAL.has(date.decade[0].key)) coverage.knownDecadeN += 1;
      if (!SPECIAL.has(date.month[0].key)) coverage.knownMonthN += 1;
      if (ready) coverage.encounterReadyN += 1; else coverage.encounterUnavailableN += 1;
      if (!beingAvailable) coverage.beingEvidenceUnavailableN += 1;
      if (!abductionAvailable) coverage.abductionEvidenceUnavailableN += 1;
      if (beingAvailable && !beings.length) coverage.beingNotIndexedN += 1;
      if (abductionAvailable && code === 0) coverage.abductionNotIndexedN += 1;
      if (abductionAvailable && (code === 1 || code === 2) && !reportedAbduction) coverage.abductionOtherEvidenceModeN += 1;
      if (beings.length) coverage.beingN += 1;
      if (reportedAbduction) coverage.abductionN += 1;
      if (abductionAvailable && code === 3 && mode === "all") coverage.ambiguousAbductionN += 1;
      if (row.analysisTimeOfDayAvailable === true && known(row.analysisTimeOfDayDescriptiveBin)) coverage.clockN += 1;
      if (row.analysisDurationAvailable === true && known(row.analysisDurationDescriptiveBin)) coverage.durationN += 1;
      const values = { craft: [craft ? category(craft) : unknown()], source: [source ? category(source) : unknown()],
        country: [country ? category(country) : unknown()], decade: date.decade, month: date.month,
        being: beings.length ? beings.map(item => category(item.key, item.label)) : [category(beingAvailable ? NOT_INDEXED : UNAVAILABLE,
          beingAvailable ? "No indexed being description" : "Being evidence unavailable")] };
      cards.forEach(card => {
        const rows = values[card.definition[4]], columns = values[card.definition[5]];
        addToLane(card.lanes.all, rows, columns);
        if (beings.length) addToLane(card.lanes.beings, rows, columns);
        if (reportedAbduction) addToLane(card.lanes.abduction, rows, columns);
      });
    }
    if (typeof options.forEachRow === "function") options.forEachRow(consume);
    else if (options.rows && typeof options.rows[Symbol.iterator] === "function") for (const row of options.rows) consume(row);
    else throw new Error("Overview requires rows or a synchronous forEachRow visitor.");
    const laneInfo = [
      { key: "all", label: "All active reports", totalN, available: true, evidenceUnavailableN: 0 },
      { key: "beings", label: "Reports describing beings", totalN: coverage.beingN, available: coverage.beingEvidenceUnavailableN < totalN || totalN === 0,
        partial: coverage.beingEvidenceUnavailableN > 0, evidenceUnavailableN: coverage.beingEvidenceUnavailableN },
      { key: "abduction", label: "Reported abductions", totalN: coverage.abductionN, available: coverage.abductionEvidenceUnavailableN < totalN || totalN === 0,
        partial: coverage.abductionEvidenceUnavailableN > 0, evidenceUnavailableN: coverage.abductionEvidenceUnavailableN },
    ];
    return { schemaId: SCHEMA_ID, status: "ready_descriptive", totalN, unit: "report representations", encounterEvidenceMode: mode,
      lanes: laneInfo, coverage,
      notes: ["Counts describe retained report representations, not independent events. These comparisons do not establish a flight path, physical association, observing rate, statistical significance, or cause.",
        "Being labels can overlap within a report; their category memberships can exceed the report denominator. No indexed description is not evidence that no being was present.",
        "Dates crossing a displayed calendar boundary remain unknown for that axis. Withheld occurrence dates are not assigned to a reporting season.",
        options.geographyProjectionLoaded === true ? "Countries use the reviewed geography projection when known, with retained source-country fallback. Unmapped reports remain included."
          : "Countries use recorded country fields; the optional reviewed geography projection has not loaded. Unmapped reports remain included."],
      inferentialTestsRun: 0,
      cards: cards.map(card => {
        const d = card.definition, multiLabel = d[4] === "being" || d[5] === "being";
        return { key: d[0], title: d[1], question: d[2], section: d[3], rowDimension: d[4], columnDimension: d[5],
          rowOrder: ["decade", "month"].includes(d[4]) ? "chronological" : "label",
          columnOrder: ["decade", "month"].includes(d[5]) ? "chronological" : "label", unit: "report representations", multiLabel,
          notes: [multiLabel ? "Categories describe beings and other fields within the same retained report; physical craft association is not established. Labels overlap."
            : "Descriptive composition of retained reports; source coverage and classification practices can vary between cells.",
            "Unknown, unavailable, and not indexed categories are retained. Each lane uses its own report denominator."],
          lanes: Object.fromEntries(Object.keys(card.lanes).map(key => [key, finishLane(card.lanes[key], d)])) };
      }) };
  }
  return Object.freeze({ SCHEMA_ID, compute, civilFromOrdinal });
});
