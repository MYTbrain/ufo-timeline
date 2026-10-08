(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UfoAnalysisComparisonsView = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const states = new WeakMap();
  const icons = ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘"];
  function artifactLoadTimeoutMs(manifestValue) {
    const atlas = manifestValue && manifestValue.ephemerisAtlas;
    const bytes = atlas && atlas.gzipByteLength;
    // This budget covers the initial download and integrity/decompression work,
    // not cached selections or subsequent comparison calculations.
    return typeof bytes === "number" && Number.isFinite(bytes) && bytes >= 25 * 1024 * 1024
      ? 180000 : 30000;
  }
  function number(value) { return typeof value === "number" && Number.isFinite(value) ? value : null; }
  function count(value) { return number(value) == null ? "—" : Math.round(value).toLocaleString("en-US"); }
  function percent(value) { return number(value) == null ? "—" : (value * 100).toFixed(1) + "%"; }
  function ratio(value) { return number(value) == null ? "Not estimable" : value.toFixed(2) + "×"; }
  function element(doc, tag, cls, text) {
    const node = doc.createElement(tag); if (cls) node.className = cls;
    if (text != null) node.textContent = String(text); return node;
  }
  function paragraph(doc, text, cls) { return element(doc, "p", cls || "comparison-note", text); }
  function card(doc, title) {
    const node = element(doc, "article", "comparison-card");
    node.appendChild(element(doc, "h4", "", title)); return node;
  }
  function stats(doc, values) {
    const node = element(doc, "dl", "comparison-metrics");
    values.forEach(function (item) {
      const group = element(doc, "div", "");
      group.appendChild(element(doc, "dt", "", item[0]));
      group.appendChild(element(doc, "dd", "", typeof item[1] === "number" ? count(item[1]) : item[1]));
      node.appendChild(group);
    }); return node;
  }
  function table(doc, headers, rows, caption) {
    const details = element(doc, "details", "comparison-data");
    details.appendChild(element(doc, "summary", "", "View exact values (" + rows.length + " rows)"));
    const wrap = element(doc, "div", "comparison-table-scroll");
    const node = element(doc, "table", "comparison-table");
    node.appendChild(element(doc, "caption", "", caption));
    const head = doc.createElement("thead"), tr = doc.createElement("tr");
    headers.forEach(function (title) { const th = element(doc, "th", "", title); th.scope = "col"; tr.appendChild(th); });
    head.appendChild(tr); node.appendChild(head);
    const body = doc.createElement("tbody");
    rows.forEach(function (row) { const line = doc.createElement("tr");
      row.forEach(function (value, index) { const cell = element(doc, index ? "td" : "th", "", value); if (!index) cell.scope = "row"; line.appendChild(cell); });
      body.appendChild(line);
    }); node.appendChild(body); wrap.appendChild(node); details.appendChild(wrap); return details;
  }
  function bars(doc, rows, options) {
    const config = options || {};
    const node = element(doc, "div", "comparison-bars");
    node.setAttribute("role", "img"); node.setAttribute("aria-label", config.caption || "Observed and calendar-control counts");
    const max = Math.max(config.percent ? 0.01 : 1, ...rows.map(function (row) { return Math.max(row.value || 0, row.expected || 0, row.upper || 0); }));
    rows.forEach(function (row) {
      const line = element(doc, "div", "comparison-bar-row");
      const label = element(doc, "span", "comparison-bar-label", row.label);
      const track = element(doc, "div", "comparison-bar-track");
      const actual = element(doc, "span", "comparison-bar-actual");
      actual.style.width = Math.max(0, (row.value || 0) / max * 100) + "%";
      track.appendChild(actual);
      if (number(row.lower) != null && number(row.upper) != null) {
        const interval = element(doc, "span", "comparison-bar-interval");
        interval.style.left = Math.max(0, row.lower / max * 100) + "%";
        interval.style.width = Math.max(0, (row.upper - row.lower) / max * 100) + "%";
        track.appendChild(interval);
      }
      if (number(row.expected) != null) { const expected = element(doc, "span", "comparison-bar-expected");
        expected.style.left = Math.max(0, row.expected / max * 100) + "%"; track.appendChild(expected); }
      line.title = row.description || row.label + ": " + count(row.value);
      line.appendChild(label); line.appendChild(track); line.appendChild(element(doc, "span", "comparison-bar-value", config.percent ? percent(row.value) : count(row.value)));
      node.appendChild(line);
    });
    if (!rows.length) node.appendChild(paragraph(doc, "No records pass the required gates for this selection."));
    return node;
  }
  function selector(doc, label, entries, selected, onSelect) {
    const field = element(doc, "label", "comparison-selector");
    field.appendChild(element(doc, "span", "", label));
    const select = doc.createElement("select"); select.setAttribute("aria-label", label);
    entries.forEach(function (item) { const option = element(doc, "option", "", item[1]); option.value = item[0]; select.appendChild(option); });
    select.value = selected; select.addEventListener("change", function () { onSelect(select.value); });
    field.appendChild(select); return field;
  }
  function policies(doc, title, notes, links) {
    const node = element(doc, "details", "comparison-methods");
    node.appendChild(element(doc, "summary", "", title));
    (notes || []).filter(Boolean).forEach(function (note) { node.appendChild(paragraph(doc, note)); });
    (links || []).forEach(function (link) { if (!/^https:\/\//.test(link[1] || "")) return;
      const a = element(doc, "a", "", link[0]); a.href = link[1]; a.target = "_blank"; a.rel = "noopener noreferrer";
      node.appendChild(a);
    }); return node;
  }
  function renderLunar(doc, host, model, state, update) {
    const domains = model.domains || [];
    const domain = domains.find(function (item) { return item.id === state.domain; }) || domains[0];
    if (!domain) { host.appendChild(paragraph(doc, "Lunar evidence is still calculating.")); return; }
    host.appendChild(selector(doc, "Compare Moon phase with", domains.map(function (item) { return [item.id, item.label]; }), domain.id,
      function (id) { state.domain = id; update(); }));
    const profile = card(doc, "Reports across the lunar cycle");
    profile.appendChild(paragraph(doc, "Cyan bars show estimated report share. Gold markers show calendar opportunity matched to the same years and months. Thin gray spans show possible shares given date uncertainty."));
    profile.appendChild(stats(doc, [["Matched records", domain.total], ["Exact-day phase estimates", domain.phaseEligible],
      ["Phase remains certain across date bounds", domain.stablePhaseCount], ["Could cross a phase boundary", domain.ambiguousPhaseCount]]));
    if (!domain.phaseEligible) profile.appendChild(paragraph(doc, "No selected records have eligible exact dates for lunar phase estimates. Broader or unsupported calendar dates remain excluded."));
    profile.appendChild(bars(doc, (domain.phaseBins || []).map(function (row, index) { return {
      label: icons[index] + " " + row.label, value: row.share, expected: row.expectedCalendarShare,
      lower: domain.phaseEligible ? row.lowerCount / domain.phaseEligible : 0,
      upper: domain.phaseEligible ? row.upperCount / domain.phaseEligible : 0,
      description: row.label + ": " + count(row.count) + " UTC-noon estimates; " + count(row.lowerCount) + "–" + count(row.upperCount)
        + " possible with date uncertainty; opportunity ratio " + ratio(row.calendarAdjustedRatio),
    }; }), { percent: true, caption: "Estimated report share and matched calendar share across eight lunar phases" }));
    profile.appendChild(paragraph(doc, "Phase counts use a UTC-noon estimate. Unknown observation time and time zone remain a full civil-day interval; the exact-value table includes stable-to-possible count bounds."));
    profile.appendChild(table(doc, ["Phase", "Estimated count", "Stable–possible", "Report share", "Calendar share", "Opportunity ratio"],
      (domain.phaseBins || []).map(function (row) { return [row.label, count(row.count), count(row.lowerCount) + "–" + count(row.upperCount),
        percent(row.share), percent(row.expectedCalendarShare), ratio(row.calendarAdjustedRatio)]; }), "Lunar phase distribution and date uncertainty"));
    host.appendChild(profile);
    const categories = card(doc, domain.categoryLabel + " by lunar phase");
    const wrap = element(doc, "div", "comparison-table-scroll");
    const grid = element(doc, "table", "comparison-table comparison-heatmap");
    grid.appendChild(element(doc, "caption", "", "Within-category estimated phase shares; dominant categories shown first"));
    const thead = doc.createElement("thead"), head = doc.createElement("tr"); head.appendChild(element(doc, "th", "", domain.categoryLabel));
    (model.phaseBins || []).forEach(function (phase, index) { const th = element(doc, "th", "", icons[index]); th.title = phase.label; th.setAttribute("aria-label", phase.label); head.appendChild(th); });
    thead.appendChild(head); grid.appendChild(thead); const tbody = doc.createElement("tbody");
    (domain.phaseByCategory || []).forEach(function (row) { const tr = doc.createElement("tr");
      tr.appendChild(element(doc, "th", "", row.category.replace(/_/g, " ") + " · " + count(row.total)));
      (row.bins || []).forEach(function (cell) { const td = element(doc, "td", "", percent(cell.share));
        td.style.backgroundColor = "color-mix(in srgb, var(--accent) " + Math.min(40, (cell.share || 0) * 180) + "%, transparent)";
        td.title = (cell.label || cell.id) + ": " + count(cell.count) + " reports"; tr.appendChild(td); }); tbody.appendChild(tr);
    }); grid.appendChild(tbody); wrap.appendChild(grid); categories.appendChild(wrap); host.appendChild(categories);
    const illumination = card(doc, "Estimated Moon illumination");
    illumination.appendChild(paragraph(doc, "The illuminated fraction is estimated at UTC noon for each eligible date. It describes the Moon’s phase, not its visibility or brightness at the report site."));
    illumination.appendChild(stats(doc, [["Mean illuminated fraction", percent(domain.illumination && domain.illumination.mean)]]));
    illumination.appendChild(bars(doc, (domain.illumination && domain.illumination.bins || []).map(function (row) { return {
      label: row.label, value: domain.phaseEligible ? row.count / domain.phaseEligible : null,
    }; }), { percent: true, caption: "Estimated report share across Moon illumination bands" }));
    illumination.appendChild(table(doc, ["Illumination band", "Reports", "Share"], (domain.illumination && domain.illumination.bins || []).map(function (row) {
      return [row.label, count(row.count), percent(domain.phaseEligible ? row.count / domain.phaseEligible : null)];
    }), "UTC-noon illumination estimates; date uncertainty is preserved in the phase profile"));
    host.appendChild(illumination);
    const position = card(doc, "Moon position & horizon");
    const sky = domain.sky || {};
    position.appendChild(stats(doc, [["Verified time + location", sky.eligible || 0], ["Above horizon", sky.aboveHorizon || 0], ["Below horizon", sky.belowHorizon || 0]]));
    position.appendChild(paragraph(doc, sky.eligible ? "Moon-center elevation and compass direction use verified UTC timestamps and source coordinates."
      : "No selected records have the verified time-zone-aware timestamps and location evidence needed for Moon position. Source clock times are preserved; they are not treated as UTC."));
    if (sky.eligible) position.appendChild(bars(doc, (sky.azimuthBins || []).map(function (row) { return { label: row.label, value: row.count }; })));
    host.appendChild(position);
    const excluded = Object.entries(domain.excluded || {}).map(function (entry) { return entry[0].replace(/_/g, " ") + ": " + count(entry[1]); });
    const roles = Object.entries(domain.dateRoles || {}).map(function (entry) { return entry[0].replace(/_/g, " ") + ": " + count(entry[1]); });
    host.appendChild(policies(doc, "Date roles, exclusions & astronomy method", (model.warnings || []).concat(roles, excluded),
      [["Astronomy calculation source", model.method && model.method.source], ["Independent NASA/JPL reference", model.method && model.method.independentReference]]));
  }
  function heatmapCellShade(cell, metric) {
    const value = metric === "difference" && number(cell.share) != null && number(cell.expectedCalendarShare) != null
      ? cell.share - cell.expectedCalendarShare : metric === "share" ? number(cell.share) : null;
    if (value == null) return null;
    if (metric === "difference" && value === 0) return "var(--panel)";
    const distance = metric === "difference" ? Math.min(1, Math.abs(value) / 0.2) : Math.sqrt(Math.max(0, Math.min(1, value)));
    const color = metric === "difference" && value < 0 ? "186,150,80" : "75,185,207";
    const alpha = 0.04 + distance * 0.46;
    return "linear-gradient(rgba(" + color + "," + alpha + "),rgba(" + color + "," + alpha + ")),var(--panel)";
  }
  function renderPlanetaryHeatmaps(doc, host, model, heatmaps, state, update, callbacks) {
    const kind = state.heatmapKind || "zodiac", metric = state.heatmapMetric || "difference";
    const system = state.zodiacSystem || model.zodiacSystem || "sidereal";
    const orb = number(state.aspectOrbDegrees) == null ? model.aspectOrbDegrees || 3 : state.aspectOrbDegrees;
    const titles = { zodiac: "Zodiac positions", aspects: "Planet pairs & aspects", motion: "Direct & retrograde" };
    const controls = element(doc, "div", "comparison-heatmap-controls");
    const navigation = element(doc, "div", "comparison-heatmap-nav"); navigation.setAttribute("role", "tablist"); navigation.setAttribute("aria-label", "Planetary heatmap");
    const kinds = ["zodiac", "aspects", "motion"];
    function changeKind(id) { state.heatmapKind = id; state.heatmapCell = null; state.heatmapFocusCell = null; update(); doc.getElementById("comparison-heatmap-question-" + id).focus(); }
    kinds.forEach(function (id, index) {
      const button = element(doc, "button", "", titles[id]); button.type = "button"; button.id = "comparison-heatmap-question-" + id;
      button.setAttribute("role", "tab"); button.setAttribute("aria-controls", "comparison-planetary-heatmap");
      button.setAttribute("aria-selected", kind === id ? "true" : "false"); button.tabIndex = kind === id ? 0 : -1;
      button.addEventListener("click", function () { changeKind(id); });
      button.addEventListener("keydown", function (event) {
        let next; if (event.key === "ArrowRight") next = (index + 1) % kinds.length;
        if (event.key === "ArrowLeft") next = (index + kinds.length - 1) % kinds.length;
        if (event.key === "Home") next = 0; if (event.key === "End") next = kinds.length - 1;
        if (next == null) return; event.preventDefault(); changeKind(kinds[next]);
      }); navigation.appendChild(button);
    }); controls.appendChild(navigation);
    const fields = element(doc, "div", "comparison-controls");
    fields.appendChild(selector(doc, "Heatmap values", [["difference", "Difference from calendar"], ["share", "Report share"]], metric,
      function (value) { state.heatmapMetric = value; update(); }));
    function changeSettings(settings) {
      Object.assign(state, settings); state.heatmapCell = null;
      if (callbacks.onSettingsChange) callbacks.onSettingsChange(Object.assign({}, settings, { heatmapOnly: true }));
      update();
    }
    if (kind === "zodiac") fields.appendChild(selector(doc, "Zodiac system", [["sidereal", "Sidereal · Lahiri"], ["tropical", "Tropical"]], system,
      function (value) { changeSettings({ zodiacSystem: value, ayanamsaId: "lahiri" }); }));
    if (kind === "aspects") fields.appendChild(selector(doc, "Aspect tolerance", [["1", "Within 1°"], ["3", "Within 3°"], ["5", "Within 5°"]], String(orb),
      function (value) { changeSettings({ aspectOrbDegrees: Number(value) }); }));
    controls.appendChild(fields); host.appendChild(controls);
    const request = { zodiacSystem: system, ayanamsaId: "lahiri", aspectOrbDegrees: orb };
    const matches = heatmaps && heatmaps.status === "ready" && heatmaps.zodiacSystem === system && heatmaps.aspectOrbDegrees === orb &&
      (system !== "sidereal" || heatmaps.ayanamsaId === "lahiri");
    if (!matches) {
      const waiting = card(doc, heatmaps && heatmaps.status === "error" ? "Heatmap could not be loaded" : "Loading planetary heatmaps");
      const status = paragraph(doc, heatmaps && heatmaps.status === "error" ? heatmaps.message || "Try loading the heatmap again." : "Preparing all bodies and planet pairs for the current report filters. The detailed comparison remains available.");
      status.setAttribute("role", "status"); waiting.appendChild(status); host.appendChild(waiting);
      const identity = JSON.stringify(request);
      if (!(heatmaps && heatmaps.status === "error") && callbacks.onHeatmapRequest &&
          (state.heatmapRequestModel !== model || state.heatmapRequestKey !== identity)) {
        state.heatmapRequestModel = model; state.heatmapRequestKey = identity; callbacks.onHeatmapRequest(request);
      }
      if (heatmaps && heatmaps.status === "error" && callbacks.onHeatmapRequest) {
        const retry = element(doc, "button", "secondary-button", "Retry heatmap"); retry.type = "button";
        retry.addEventListener("click", function () { callbacks.onHeatmapRequest(request); }); waiting.appendChild(retry);
      }
      return;
    }
    const domain = (heatmaps.domains || []).find(function (item) { return item.id === state.domain; }) || (heatmaps.domains || [])[0];
    const matrix = domain && domain.matrices && domain.matrices[kind];
    if (!matrix) { host.appendChild(paragraph(doc, "No heatmap evidence is available for this report domain.")); return; }
    const columns = matrix.columns || [], rows = matrix.rows || [];
    const hasFocusCell = rows.some(function (row) { return columns.some(function (column) { return state.heatmapFocusCell === kind + "|" + domain.id + "|" + row.id + "|" + column.id; }); });
    const convention = system === "sidereal" ? "Lahiri sidereal" : "Tropical";
    const node = card(doc, titles[kind] + " · " + domain.label); node.className += " comparison-heatmap-card";
    node.appendChild(paragraph(doc, kind === "zodiac" ? "Compare every body across the twelve " + convention + " zodiac sectors. Select a cell to inspect its exact counts."
      : kind === "aspects" ? "Each unordered planet pair appears once. The five major aspect bands use a " + orb + "° tolerance; reports outside the bands remain visible."
      : "Compare apparent direct, retrograde and near-stationary motion for all nine bodies."));
    node.appendChild(stats(doc, [["Eligible dated reports", domain.positionEligible], ["Distinct report dates", domain.distinctEligibleDates],
      [kind === "aspects" ? "Planet pairs" : "Bodies", rows.length]]));
    const legend = element(doc, "div", "comparison-heatmap-legend");
    legend.appendChild(element(doc, "span", "", metric === "difference" ? "Below calendar share" : "Lower report share"));
    const scale = element(doc, "span", "comparison-heatmap-scale" + (metric === "difference" ? " comparison-heatmap-scale-difference" : "")); scale.setAttribute("aria-hidden", "true"); legend.appendChild(scale);
    legend.appendChild(element(doc, "span", "", metric === "difference" ? "Above calendar share" : "Higher report share"));
    node.appendChild(legend);
    node.appendChild(paragraph(doc, metric === "difference" ? "Cells show report share minus calendar share in percentage points. Gold is below calendar share, cyan is above, and neutral is zero. Fill caps at ±20 points; numerical values still show differences beyond that limit. A dash means a share is unavailable."
      : "Cyan fill runs from 0% to 100% with a square-root scale to keep smaller shares visible. Values are shares of eligible reports, not probabilities of an effect.", "comparison-heatmap-key"));
    if (!domain.positionEligible) node.appendChild(paragraph(doc, "No eligible exact dates. Missing shares are shown as dashes, not zero-percent observations."));
    const wrap = element(doc, "div", "comparison-heatmap-scroll" + (kind === "aspects" ? " comparison-heatmap-pairs" : ""));
    wrap.setAttribute("role", "region"); wrap.setAttribute("aria-label", titles[kind] + " heatmap; scroll to inspect all cells"); wrap.tabIndex = 0;
    const grid = element(doc, "table", "comparison-heatmap-grid"); grid.id = "comparison-planetary-heatmap";
    grid.setAttribute("aria-labelledby", "comparison-heatmap-question-" + kind);
    const caption = element(doc, "caption", "", titles[kind] + ": " + (metric === "difference" ? "report minus calendar share, in percentage points" : "report shares")); grid.appendChild(caption);
    const head = doc.createElement("thead"), headingRow = doc.createElement("tr");
    const corner = element(doc, "th", "", kind === "aspects" ? "Planet pair" : "Body"); corner.scope = "col"; headingRow.appendChild(corner);
    columns.forEach(function (column) { const heading = element(doc, "th", "", (column.symbol ? column.symbol + " " : "") + column.label);
      heading.scope = "col"; if (number(column.angleDegrees) != null) heading.appendChild(element(doc, "small", "", column.angleDegrees + "°")); headingRow.appendChild(heading); });
    head.appendChild(headingRow); grid.appendChild(head);
    const body = doc.createElement("tbody"), cellButtons = [];
    rows.forEach(function (row, rowIndex) {
      const line = doc.createElement("tr"), label = element(doc, "th", "", row.label); label.scope = "row"; line.appendChild(label);
      columns.forEach(function (column, columnIndex) {
        const cell = (row.cells || []).find(function (value) { return value.id === column.id; }) || (row.cells || [])[columnIndex] || {};
        const key = kind + "|" + domain.id + "|" + row.id + "|" + column.id;
        const difference = number(cell.share) != null && number(cell.expectedCalendarShare) != null ? (cell.share - cell.expectedCalendarShare) * 100 : null;
        const displayedDifference = difference == null ? null : Math.round(difference * 100) / 100;
        const value = metric === "difference" ? displayedDifference == null ? "—" : (displayedDifference > 0 ? "+" : "") + displayedDifference.toFixed(2) + " pp" : percent(cell.share);
        const unavailable = metric === "difference" ? difference == null : number(cell.share) == null;
        const container = doc.createElement("td"), button = element(doc, "button", "comparison-heatmap-cell" + (unavailable ? " comparison-heatmap-unavailable" : ""), unavailable ? "—" : value);
        button.type = "button"; button.id = "comparison-heatmap-cell-" + rowIndex + "-" + columnIndex;
        button.tabIndex = state.heatmapFocusCell === key || (!hasFocusCell && rowIndex === 0 && columnIndex === 0) ? 0 : -1;
        button.setAttribute("aria-pressed", state.heatmapCell === key ? "true" : "false");
        button.setAttribute("aria-controls", "comparison-heatmap-cell-details");
        button.setAttribute("aria-label", row.label + " · " + column.label + ": " + (unavailable ? "not estimable" : value) + "; " + count(cell.count) + " reports; calendar share " + percent(cell.expectedCalendarShare));
        button.title = row.label + " · " + column.label + ": " + count(cell.count) + " reports; sampled stable–possible " + count(cell.lowerCount) + "–" + count(cell.upperCount);
        const shade = heatmapCellShade(cell, metric); if (shade) button.style.background = shade;
        button.addEventListener("focus", function () { state.heatmapFocusCell = key; });
        button.addEventListener("keydown", function (event) {
          let nextRow = rowIndex, nextColumn = columnIndex;
          if (event.key === "ArrowRight") nextColumn = Math.min(columns.length - 1, columnIndex + 1);
          else if (event.key === "ArrowLeft") nextColumn = Math.max(0, columnIndex - 1);
          else if (event.key === "ArrowDown") nextRow = Math.min(rows.length - 1, rowIndex + 1);
          else if (event.key === "ArrowUp") nextRow = Math.max(0, rowIndex - 1);
          else if (event.key === "Home") nextColumn = 0;
          else if (event.key === "End") nextColumn = columns.length - 1;
          else return;
          event.preventDefault(); const next = cellButtons[nextRow * columns.length + nextColumn];
          cellButtons.forEach(function (item) { item.tabIndex = item === next ? 0 : -1; });
          state.heatmapFocusCell = kind + "|" + domain.id + "|" + rows[nextRow].id + "|" + columns[nextColumn].id; next.focus();
        });
        button.addEventListener("click", function () { state.heatmapCell = key; state.heatmapFocusCell = key; update(); doc.getElementById(button.id).focus(); });
        cellButtons.push(button);
        container.appendChild(button); line.appendChild(container);
      }); body.appendChild(line);
    }); grid.appendChild(body); wrap.appendChild(grid); node.appendChild(wrap);
    const details = element(doc, "div", "comparison-heatmap-cell-details"); details.id = "comparison-heatmap-cell-details"; details.setAttribute("aria-live", "polite");
    let selection;
    rows.some(function (row) { return columns.some(function (column, columnIndex) {
      if (state.heatmapCell !== kind + "|" + domain.id + "|" + row.id + "|" + column.id) return false;
      selection = { row, column, cell: (row.cells || []).find(function (value) { return value.id === column.id; }) || (row.cells || [])[columnIndex] || {} }; return true;
    }); });
    if (selection) {
      const cell = selection.cell, row = selection.row;
      details.appendChild(element(doc, "h5", "", row.label + " · " + selection.column.label));
      details.appendChild(stats(doc, [["Estimated reports", cell.count], ["Report share", percent(cell.share)], ["Calendar share", percent(cell.expectedCalendarShare)],
        ["Calendar-weighted count", number(cell.expectedCount) == null ? "—" : cell.expectedCount.toLocaleString("en-US", { maximumFractionDigits: 1 })],
        ["Report / calendar", ratio(cell.calendarAdjustedRatio)], ["Sampled stable–possible", count(cell.lowerCount) + "–" + count(cell.upperCount)],
        ["Reports in months with contrast", cell.variableOpportunityReports]]));
      if (number(cell.variableOpportunityReports) === 0 && domain.positionEligible) details.appendChild(paragraph(doc,
        "This cell has no within-month calendar contrast. The comparison cannot separate this state from calendar era or season."));
      else if (number(row.variableStateReports) === 0 && domain.positionEligible) details.appendChild(paragraph(doc,
        "This body or planet pair has no state variation within any represented calendar month. The calendar comparison cannot separate it from the selected era."));
      if (number(cell.expectedCalendarShare) === 0) details.appendChild(paragraph(doc, "There is no matched calendar opportunity for this cell, so its report / calendar ratio is not estimable."));
      details.appendChild(paragraph(doc, "Count bounds reflect sampled dates and unknown observation times. They are not statistical confidence intervals."));
      const open = element(doc, "button", "secondary-button", "Open detailed comparison"); open.type = "button";
      open.addEventListener("click", function () {
        const changes = { planet: row.planet, samplingMode: "common_grid" };
        if (kind === "aspects") changes.aspectPartner = row.partner;
        else if (row.planet === (state.aspectPartner || model.aspectPartner)) changes.aspectPartner = row.planet === "Moon" ? "Sun" : "Moon";
        state.planetaryFocus = kind === "aspects" ? "aspects" : kind === "motion" ? "motion" : "zodiac";
        state.heatmapDetailSelection = row.label + " · " + selection.column.label;
        Object.assign(state, changes); if (callbacks.onSettingsChange) callbacks.onSettingsChange(changes); update();
      }); details.appendChild(open);
    } else details.appendChild(paragraph(doc, "Select any cell for exact counts, calendar opportunity and date uncertainty. Then open its detailed comparison if needed."));
    node.appendChild(details);
    node.appendChild(paragraph(doc, "Keyboard: Tab into the grid, use arrow keys to move, and Enter or Space to inspect a cell.", "comparison-heatmap-key"));
    node.appendChild(table(doc, [kind === "aspects" ? "Planet pair" : "Body", "State", "Reports", "Sampled stable–possible", "Report share", "Calendar share", "Report / calendar"],
      rows.flatMap(function (row) { return columns.map(function (column, index) { const cell = (row.cells || []).find(function (value) { return value.id === column.id; }) || (row.cells || [])[index] || {};
        return [row.label, column.label, count(cell.count), count(cell.lowerCount) + "–" + count(cell.upperCount), percent(cell.share), percent(cell.expectedCalendarShare), ratio(cell.calendarAdjustedRatio)]; }); }), titles[kind] + " heatmap exact values"));
    host.appendChild(node);
    const method = heatmaps.method || {};
    const roles = Object.entries(domain.dateRoles || {}).map(function (entry) { return entry[0].replace(/_/g, " ") + ": " + count(entry[1]) + " records"; });
    const exclusions = Object.entries(domain.excluded || {}).map(function (entry) { return entry[0].replace(/_/g, " ") + ": " + count(entry[1]) + " excluded"; });
    host.appendChild(policies(doc, "Heatmap dates, calendar controls & limits", [method.dateOnly, method.bounds, method.aspects, method.calendar].concat(heatmaps.warnings || [], roles, exclusions),
      [["Astronomy calculation source", method.source || model.method && model.method.source]]));
  }
  function renderPlanetary(doc, host, model, state, update, callbacks, heatmaps) {
    const domains = model.domains || [];
    const domain = domains.find(function (item) { return item.id === state.domain; }) || domains[0];
    if (!domain) { host.appendChild(paragraph(doc, "Planetary comparisons are still calculating.")); return; }
    const focus = state.planetaryFocus || "heatmaps";
    const planet = state.planet || model.planet || "Venus";
    const partner = state.aspectPartner || model.aspectPartner || "Mars";
    const orb = number(state.aspectOrbDegrees) == null ? model.aspectOrbDegrees || 3 : state.aspectOrbDegrees;
    const system = state.zodiacSystem || model.zodiacSystem || "sidereal";
    const bodies = model.planets || ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"];
    function settingsChange(settings) {
      state.heatmapDetailSelection = null;
      Object.assign(state, settings);
      if (callbacks.onSettingsChange) callbacks.onSettingsChange(settings);
      update();
    }
    const controls = element(doc, "div", "comparison-controls");
    controls.appendChild(selector(doc, "Planetary comparison", [["heatmaps", "Heatmap overview"], ["aspects", "Aspects · trines & other angles"], ["zodiac", "Zodiac positions"],
      ["motion", "Direct & retrograde motion"], ["houses", "Houses · data availability"]], focus,
      function (id) { state.planetaryFocus = id; state.heatmapDetailSelection = null; update(); }));
    controls.appendChild(selector(doc, "Compare with", domains.map(function (item) { return [item.id, item.label]; }), domain.id,
      function (id) { state.domain = id; state.heatmapCell = null; state.heatmapFocusCell = null; update(); }));
    host.appendChild(controls);
    if (focus === "heatmaps") { renderPlanetaryHeatmaps(doc, host, model, heatmaps, state, update, callbacks); return; }
    if (focus !== "houses") {
      const options = element(doc, "div", "comparison-controls");
      options.appendChild(selector(doc, "Planet or luminary", bodies.map(function (body) { return [body, body]; }), planet, function (body) {
        const change = { planet: body };
        if (partner === body) change.aspectPartner = body === "Moon" ? "Sun" : "Moon";
        settingsChange(change);
      }));
      if (focus === "aspects") {
        options.appendChild(selector(doc, "Aspect partner", bodies.filter(function (body) { return body !== planet; }).map(function (body) { return [body, body]; }), partner,
          function (body) { settingsChange({ aspectPartner: body }); }));
        options.appendChild(selector(doc, "Aspect tolerance", [["1", "Within 1°"], ["3", "Within 3°"], ["5", "Within 5°"]], String(orb),
          function (value) { settingsChange({ aspectOrbDegrees: Number(value) }); }));
      }
      if (focus === "zodiac") options.appendChild(selector(doc, "Zodiac system", [["sidereal", "Sidereal · Lahiri"], ["tropical", "Tropical"]], system,
        function (value) { settingsChange({ zodiacSystem: value, ayanamsaId: "lahiri" }); }));
      host.appendChild(options);
    }
    const pending = planet !== model.planet || partner !== model.aspectPartner || orb !== model.aspectOrbDegrees || system !== model.zodiacSystem ||
      (state.samplingMode || model.samplingMode || "adaptive") !== (model.samplingMode || "adaptive");
    if (pending && focus !== "houses") {
      host.appendChild(paragraph(doc, "Updating the selected planetary comparison…")); return;
    }
    if (state.heatmapDetailSelection && focus !== "houses") {
      host.appendChild(paragraph(doc, "Opened from heatmap: " + state.heatmapDetailSelection + ". The chart shows the complete comparison for this selection.", "comparison-note comparison-heatmap-detail-origin"));
      const back = element(doc, "button", "secondary-button comparison-heatmap-back", "Back to heatmap"); back.type = "button";
      back.addEventListener("click", function () { state.planetaryFocus = "heatmaps"; update(); }); host.appendChild(back);
    }
    function plotRows(rows, angle) { return (rows || []).map(function (row) { return {
      label: (row.symbol ? row.symbol + " " : "") + row.label + (angle && number(row.angleDegrees) != null ? " · " + row.angleDegrees + "°" : ""),
      value: row.share, expected: row.expectedCalendarShare,
      lower: domain.positionEligible ? row.lowerCount / domain.positionEligible : null,
      upper: domain.positionEligible ? row.upperCount / domain.positionEligible : null,
      description: row.label + ": " + count(row.count) + " noon estimates; " + count(row.lowerCount) + "–" + count(row.upperCount)
        + " sampled-stability counts; report/calendar ratio " + ratio(row.calendarAdjustedRatio),
    }; }); }
    function exactTable(rows, caption) { return table(doc, ["State", "Noon estimate", "Sampled stable–possible", "Report share", "Calendar share", "Report / calendar"],
      (rows || []).map(function (row) { return [row.label, count(row.count), count(row.lowerCount) + "–" + count(row.upperCount),
        percent(row.share), percent(row.expectedCalendarShare), ratio(row.calendarAdjustedRatio)]; }), caption); }
    function legend(node) {
      node.appendChild(paragraph(doc, "Cyan bars show estimated report share. Gold markers show calendar opportunity in the same years and months. Gray spans show sampled date uncertainty."));
      if (!domain.positionEligible) node.appendChild(paragraph(doc, "No selected records have eligible exact dates. A missing denominator does not produce a zero-percent distribution."));
    }
    if (focus === "aspects") {
      const group = (domain.aspectPartners || []).find(function (item) { return item.partner === partner; }) || {};
      const node = card(doc, planet + " & " + partner + " · angular relationships");
      node.appendChild(paragraph(doc, "A trine is a 120° relationship. The other bands below represent conjunctions (0°), sextiles (60°), squares (90°) and oppositions (180°), allowing " + orb + "° on either side."));
      node.appendChild(stats(doc, [["Eligible dated reports", group.eligible || 0], ["Distinct report dates", domain.distinctEligibleDates || 0], ["Noon estimates within bands", group.anyAspectCount || 0],
        ["Verified observation times", domain.verifiedTimeCount || 0]]));
      const rows = (group.bins || []).slice();
      if (group.outsideBand) rows.push(group.outsideBand);
      legend(node);
      if (group.anyAspectCount && !(group.bins || []).some(function (row) { return row.stableCount > 0; })) node.appendChild(paragraph(doc,
        "None of these major-aspect estimates remain inside their band throughout the sampled unknown-time interval. This is especially common with the fast-moving Moon; the bands describe UTC-noon estimates."));
      node.appendChild(bars(doc, plotRows(rows, true), { percent: true, caption: "Report share and calendar opportunity for " + planet + " and " + partner + " aspects" }));
      node.appendChild(paragraph(doc, "Angles use Earth-centered ecliptic longitudes. They are unchanged by switching between sidereal and tropical zodiac conventions. Reports outside these bands remain in the denominator."));
      if (group.variableAspectReports === 0 && domain.positionEligible) node.appendChild(paragraph(doc,
        "These aspect bands do not change within any represented calendar month. This selection has no within-month contrast against its calendar controls."));
      node.appendChild(exactTable(rows, planet + "–" + partner + " aspects, with a " + orb + "° tolerance")); host.appendChild(node);
      const aspectCategories = (domain.aspectByCategory || []).find(function (item) { return item.partner === partner; });
      if (aspectCategories && aspectCategories.rows && aspectCategories.rows.length) {
        const categories = card(doc, domain.categoryLabel + " across aspects");
        categories.appendChild(paragraph(doc, "Each category uses its own year-month calendar opportunity. Ratios describe catalog patterns; they do not establish a planetary effect."));
        categories.appendChild(table(doc, [domain.categoryLabel, "Aspect", "Reports", "Within-category share", "Calendar share", "Report / calendar"],
          aspectCategories.rows.flatMap(function (row) { return (row.bins || []).concat(row.outsideBand ? [row.outsideBand] : []).map(function (bin) { return [row.category.replace(/_/g, " "), bin.label,
            count(bin.count), percent(bin.share), percent(bin.expectedCalendarShare), ratio(bin.calendarAdjustedRatio)]; }); }), "Category-specific aspect counts and calendar opportunity"));
        host.appendChild(categories);
      }
    } else if (focus === "zodiac") {
      const convention = system === "sidereal" ? "Lahiri sidereal" : "Tropical";
      const node = card(doc, planet + " · " + convention + " zodiac positions");
      node.appendChild(paragraph(doc, system === "sidereal" ? "Lahiri is the selected sidereal convention. These are twelve equal 30° zodiac sectors, with a date-dependent offset from the equinox."
        : "Tropical zodiac positions use twelve equal 30° sectors starting at the equinox. These sectors are distinct from astronomical constellation boundaries."));
      node.appendChild(stats(doc, [["Eligible dated reports", domain.positionEligible], ["Sign stable at sampled times", domain.stableSignCount],
        ["Could cross a sign boundary", domain.ambiguousSignCount]]));
      legend(node);
      node.appendChild(bars(doc, plotRows(domain.signBins), { percent: true, caption: planet + " report shares across twelve " + convention + " signs" }));
      if (domain.exposure && domain.exposure.variableSignReports === 0 && domain.positionEligible) node.appendChild(paragraph(doc,
        "The selected planet does not change signs within any represented calendar month. This selection cannot separate a sign pattern from its calendar era."));
      node.appendChild(exactTable(domain.signBins, planet + " " + convention + " sign distribution")); host.appendChild(node);
      const categoryRows = domain.signByCategory || [];
      if (categoryRows.length) {
        const categories = card(doc, domain.categoryLabel + " across zodiac signs");
        categories.appendChild(paragraph(doc, "Compare exact counts and report/calendar ratios using each category’s own year-month mix."));
        categories.appendChild(table(doc, [domain.categoryLabel, "Sign", "Reports", "Within-category share", "Calendar share", "Report / calendar"],
          categoryRows.flatMap(function (row) { return (row.bins || []).map(function (bin) { return [row.category.replace(/_/g, " "), bin.label,
            count(bin.count), percent(bin.share), percent(bin.expectedCalendarShare), ratio(bin.calendarAdjustedRatio)]; }); }), "Category-specific zodiac counts and calendar opportunity")); host.appendChild(categories);
      }
    } else if (focus === "motion") {
      const motion = domain.motion || {}, node = card(doc, planet + " · apparent direct & retrograde motion");
      node.appendChild(paragraph(doc, "Retrograde means the planet’s Earth-centered longitude is decreasing. Near stationary means its tropical-longitude rate is within 0.01° per day of zero; it is a display threshold."));
      node.appendChild(stats(doc, [["Eligible dated reports", domain.positionEligible], ["Motion stable at sampled times", motion.stableCount || 0],
        ["Could cross a motion boundary", motion.ambiguousCount || 0]]));
      legend(node);
      node.appendChild(bars(doc, plotRows(motion.bins), { percent: true, caption: planet + " direct, retrograde and near-stationary report shares" }));
      if (domain.exposure && domain.exposure.variableMotionReports === 0 && domain.positionEligible) node.appendChild(paragraph(doc,
        "Motion does not change within any represented calendar month. These calendar controls offer no within-month contrast for this selection."));
      node.appendChild(exactTable(motion.bins, planet + " apparent motion and calendar opportunity")); host.appendChild(node);
    } else {
      const houses = domain.houses || {}, node = card(doc, "Houses need a verified observation time & place");
      node.appendChild(stats(doc, [["Qualified time + location records", houses.eligibleInputs || 0], ["House calculations", "Unavailable"]]));
      node.appendChild(paragraph(doc, houses.eligibleInputs ? "Qualifying time-and-location records are present, but house calculations are not implemented. A named house system and its own verification are needed before assigning houses."
        : "Houses depend on the local sky at the observation time. The current catalog lacks verified time-zone-aware observation times paired with reliable locations, so assigning houses would require guessing."));
      node.appendChild(paragraph(doc, "Once qualifying records are available, a named house system can be added. UTC noon estimates and approximate case markers do not qualify.")); host.appendChild(node);
    }
    const exposure = domain.exposure || {};
    const roleNotes = Object.entries(domain.dateRoles || {}).map(function (item) { return item[0].replace(/_/g, " ") + ": " + count(item[1]) + " records"; });
    const exclusions = Object.entries(domain.excluded || {}).map(function (item) { return item[0].replace(/_/g, " ") + ": " + count(item[1]) + " excluded"; });
    const method = model.method || {};
    host.appendChild(policies(doc, "Dates, conventions & calculation limits", [method.dateOnly, method.uncertainty, method.zodiac,
      method.ayanamsa, exposure.weighting, exposure.opportunity].concat(model.warnings || [], roleNotes, exclusions),
      [["Astronomy calculation source", method.source], ["Independent JPL reference", method.independentReference], ["Sidereal convention reference", method.ayanamsaReference]]));
  }
  function renderCross(doc, host, model) {
    const coverage = model.coverage || {}, crops = coverage.crops || {}, animals = coverage.animals || {};
    const summary = card(doc, "Crop and animal report overlap");
    summary.appendChild(paragraph(doc, "Compare location-date clusters directly, with repeated reports at the same marker counted once."));
    summary.appendChild(paragraph(doc, "Exploratory marker comparisons only. Strict occurrence/formation-site inference does not pass the current evidence gates."));
    summary.appendChild(stats(doc, [["Crop records in scope", crops.scopedN], ["Animal records in scope", animals.scopedN],
      ["Strict eligible crop records", crops.strictEligibleN], ["Strict eligible animal records", animals.strictEligibleN]])); host.appendChild(summary);
    const publicLane = (model.lanes || []).find(function (lane) { return lane.id === "public_marker"; });
    if (publicLane) {
      const node = card(doc, "Exploratory public-marker neighborhoods");
      node.appendChild(paragraph(doc, "Bars compare matched candidate pairs with the average from four same-season control dates. These are distances between catalog markers; uncertainty is not assumed to be zero."));
      node.appendChild(paragraph(doc, count(publicLane.cropClusterN) + " crop location-date clusters and " + count(publicLane.animalClusterN) + " animal location-date clusters pass the marker comparison gates."));
      node.appendChild(bars(doc, (publicLane.rows || []).map(function (row) { return {
        label: count(row.radiusKm) + " km · ±" + count(row.dayWindow) + " days",
        value: row.matchedObservedPairN, expected: row.expectedMatchedPairN,
        description: count(row.observedPairN) + " candidate marker pairs; " + count(row.unknownUncertaintyPairN) + " with unknown uncertainty",
      }; }), { caption: "Matched candidate marker pairs and same-season controls" }));
      node.appendChild(table(doc, ["Distance / date window", "Candidate pairs", "Matched pairs", "Control average", "Ratio", "Unknown uncertainty"],
        (publicLane.rows || []).map(function (row) { return [count(row.radiusKm) + " km / ±" + count(row.dayWindow) + " d",
          count(row.observedPairN), count(row.matchedObservedPairN), number(row.expectedMatchedPairN) == null ? "—" : row.expectedMatchedPairN.toFixed(2),
          ratio(row.descriptiveObservedControlRatio), count(row.unknownUncertaintyPairN)]; }), "Direct crop–animal marker comparisons"));
      const widest = publicLane.rows && publicLane.rows[publicLane.rows.length - 1];
      if (widest && widest.unknownUncertaintyPairN) node.appendChild(paragraph(doc,
        count(widest.unknownUncertaintyPairN) + " candidate pairs in the widest window have unknown location uncertainty. Small counts and incomplete control coverage limit interpretation."));
      if (widest && widest.samplePairs && widest.samplePairs.length) {
        const date = function (ordinal) { return new Date(ordinal * 86400000).toISOString().slice(0, 10); };
        node.appendChild(table(doc, ["Crop record", "Crop date / role", "Animal record", "Animal date / role", "Marker distance"], widest.samplePairs.map(function (pair) {
          return [pair.cropId, date(pair.cropOrdinal) + " · " + pair.cropDateRole.replace(/_/g, " "),
            pair.animalTitle + " · " + pair.animalId, date(pair.animalOrdinal) + " · " + pair.animalDateRole.replace(/_/g, " "),
            pair.distanceKm.toFixed(1) + " km · " + (pair.uncertaintyKnown ? "bounded" : "uncertainty unknown")];
        }), "Candidate crop and animal records, preserving their recorded date roles"));
      }
      host.appendChild(node);
    }
    const calendar = (model.lanes || []).find(function (lane) { return lane.id === "calendar_alignment"; });
    if (calendar) { const node = card(doc, "Calendar alignment"); node.appendChild(paragraph(doc, "Worldwide alignment of recorded dates provides a timing-only view. It does not imply local overlap."));
      node.appendChild(table(doc, ["Date window", "Date-cluster pairs", "Matched pairs", "Control average", "Ratio"], (calendar.rows || []).map(function (row) {
        return ["±" + count(row.dayWindow) + " days", count(row.observedPairN), count(row.matchedObservedPairN), number(row.expectedMatchedPairN) == null ? "—" : row.expectedMatchedPairN.toFixed(2), ratio(row.descriptiveObservedControlRatio)];
      }), "Worldwide recorded-date alignment")); host.appendChild(node); }
    host.appendChild(policies(doc, "Eligibility, controls & source lineage", model.policyWarnings || []));
  }
  function renderNuclear(doc, host, model, state, update, callbacks) {
    const focus = state.nuclearFocus || "timing";
    host.appendChild(selector(doc, "Nuclear comparison", [["timing", "Explosion timing & distance"], ["categories", "Report categories"], ["facilities", "Nuclear institutions"]], focus,
      function (value) { state.nuclearFocus = value; update(); }));
    const settings = element(doc, "div", "comparison-controls");
    if (focus !== "facilities") {
    settings.appendChild(selector(doc, "Before / after window", [["7", "7 days"], ["30", "30 days"], ["90", "90 days"]], String(state.windowDays || 30), function (value) {
      state.windowDays = Number(value); if (callbacks.onSettingsChange) callbacks.onSettingsChange({ windowDays: Number(value) }); update();
    }));
    settings.appendChild(selector(doc, "Explosion role", [["all", "Weapons, peaceful & combat"], ["weapons", "Weapons tests"],
      ["peaceful", "Peaceful nuclear explosions"], ["combat", "Combat use"]], state.testRole || "all", function (value) {
      state.testRole = value; if (callbacks.onSettingsChange) callbacks.onSettingsChange({ testRoles: value === "all" ? ["weapons", "peaceful", "combat"] : [value] }); update();
    }));
    }
    settings.appendChild(selector(doc, "Maximum marker distance", [["25", "25 km"], ["100", "100 km"], ["250", "250 km"], ["500", "500 km"]], String(state.radius || 500), function (value) {
      state.radius = Number(value); if (callbacks.onSettingsChange) callbacks.onSettingsChange({ distanceBandsKm: [25, 100, 250, 500].filter(function (km) { return km <= Number(value); }) }); update();
    })); host.appendChild(settings);
    const currentSettings = model.settings || {};
    const currentRole = Array.isArray(currentSettings.testRoles) && currentSettings.testRoles.length === 1 ? currentSettings.testRoles[0] : "all";
    if ((state.windowDays || 30) !== currentSettings.windowDays || (state.radius || 500) !== currentSettings.maxDistanceKm ||
      (state.testRole || "all") !== currentRole) {
      host.appendChild(paragraph(doc, "Updating the selected nuclear comparison…")); return;
    }
    const overview = card(doc, focus === "facilities" ? "Reviewed nuclear institutions" : "Independent nuclear-test chronology");
    overview.appendChild(paragraph(doc, "The comparison uses an independently sourced explosion chronology, separate from the UFO catalog’s nuclear event labels."));
    const coverage = model.coverage || {};
    overview.appendChild(stats(doc, [["Chronology records", coverage.catalogRows],
      ["Selected explosion records", coverage.selectedTests], ["Testing states", Object.keys(coverage.countries || {}).length], ["Safety records excluded", coverage.excludedSafetyN]]));
    overview.appendChild(paragraph(doc, "Source coverage: " + (coverage.firstDate || "unknown") + " to " + (coverage.lastDate || "unknown")
      + ". " + (coverage.excludedPost1998 || "") + " Safety and mixed-safety records are excluded from these explosion comparisons."));
    if (coverage.summaryDiscrepancy) overview.appendChild(paragraph(doc, coverage.summaryDiscrepancy));
    if (focus !== "facilities") host.appendChild(overview);
    const labels = { ufo: "UFO / craft reports", crops: "Crop-circle reports", animals: "Animal reports" };
    const domains = Array.isArray(model.domains) ? model.domains : Object.entries(model.domains || {}).map(function (entry) {
      return Object.assign({ id: entry[0], label: labels[entry[0]] || entry[0] }, entry[1]);
    });
    if (Array.isArray(domains) && domains.length) {
      const domain = domains.find(function (item) { return item.id === state.domain; }) || domains[0];
      host.appendChild(selector(doc, "Compare nuclear activity with", domains.map(function (item) { return [item.id, item.label]; }), domain.id,
        function (id) { state.domain = id; update(); }));
      if (focus === "timing") {
      const node = card(doc, "Reports before and after nuclear events");
      node.appendChild(stats(doc, [["Reports in scope", domain.inputN], ["Dated report markers", domain.eligibleN], ["Distinct reports linked", domain.linkedReportsN], ["Tests with nearby reports", domain.testsWithReportsN]]));
      node.appendChild(paragraph(doc, "Earlier and later dates each span " + (model.settings && model.settings.windowDays || state.windowDays || 30)
        + " days. Same-date counts cover one recorded calendar date; report/test time zones may differ, so observation order is unknown."));
      const rows = domain.phases || [];
      node.appendChild(bars(doc, rows.map(function (row) { return { label: row.label || row.period || row.id,
        value: row.uniqueReports,
      }; }), { caption: "Recorded-date report counts around nuclear explosions" }));
      node.appendChild(table(doc, ["Window", "Reports", "Report–test pairs"], rows.map(function (row) {
        return [row.label || row.period || row.id, count(row.uniqueReports), count(row.pairCount)];
      }), "Report-event windows; a report may be paired with multiple tests"));
      node.appendChild(table(doc, ["Calendar-boundary sensitivity", "Report–test pairs"], [
        ["Same date or within one recorded date", count(domain.calendarBoundaryPairs)],
        ["Earlier, excluding the adjacent date", count(domain.dayBoundaryExcluded && domain.dayBoundaryExcluded.before)],
        ["Later, excluding the adjacent date", count(domain.dayBoundaryExcluded && domain.dayBoundaryExcluded.after)],
      ], "Calendar-date sensitivity to unknown report time zones")); host.appendChild(node);
      const proximity = card(doc, "Distance from explosion markers");
      proximity.appendChild(bars(doc, (domain.distanceBands || []).map(function (row) { return { label: row.label, value: row.uniqueReports }; }), { caption: "Distinct reports across distance bands" }));
      proximity.appendChild(table(doc, ["Marker band", "Distinct reports", "Earlier pairs", "Same-date pairs", "Later pairs", "Unknown uncertainty"],
        (domain.distanceBands || []).map(function (row) { return [row.label, count(row.uniqueReports), count(row.before), count(row.sameDay), count(row.after), count(row.unknownUncertaintyPairs)]; }),
        "Distances between report markers and historical explosion markers"));
      proximity.appendChild(paragraph(doc, "Historical test coordinates are often approximate. Missing uncertainty remains unknown; these counts do not establish proximity to an exact detonation or observation site.")); host.appendChild(proximity);
      const control = domain.matchedControls || {};
      const reference = card(doc, "Same-site calendar controls");
      reference.appendChild(paragraph(doc, control.label || "Compare the same spatial neighborhoods at matched calendar dates."));
      reference.appendChild(stats(doc, [["Matched test windows", control.testWindows], ["Control windows", control.controlWindows],
        ["Report–test-window pairs", control.testPairCount], ["Report–control-window pairs", control.controlPairCount]]));
      if (control.status === "no_uncontaminated_calendar_controls") reference.appendChild(paragraph(doc, "No uncontaminated calendar controls are available for this selection. A comparison ratio cannot be estimated."));
      if (control.unavailableControls) reference.appendChild(paragraph(doc, count(control.unavailableControls) + " test records have no usable matched calendar control."));
      reference.appendChild(paragraph(doc, "Descriptive pairs per window-day ratio: " + ratio(control.relativeReportDensity)
        + ". Windows can overlap and reporting effort is unmeasured; this is not an independent-sample significance test."));
      (control.warnings || []).forEach(function (warning) { reference.appendChild(paragraph(doc, warning)); });
      reference.appendChild(table(doc, ["Window type", "Window-days", "Report-window pairs", "Unique reports", "Pairs per 1,000 window-days"], [
        ["Test dates", count(control.testWindowDays), count(control.testPairCount), count(control.uniqueTestReports), number(control.testReportsPerWindowDay) == null ? "—" : (control.testReportsPerWindowDay * 1000).toFixed(3)],
        ["Control dates", count(control.controlWindowDays), count(control.controlPairCount), count(control.uniqueControlReports), number(control.controlReportsPerWindowDay) == null ? "—" : (control.controlReportsPerWindowDay * 1000).toFixed(3)],
      ], "Matched report-window density; controls may lie outside the active date range")); host.appendChild(reference);
      }
      if (focus === "categories") {
        const composition = card(doc, domain.id === "ufo" ? "Reported craft categories" : domain.id === "crops" ? "Crop morphology context" : "Animal species context");
        const categoryRows = (domain.craftComposition || []).slice(0, 16);
        composition.appendChild(paragraph(doc, "Counts describe distinct linked reports within the selected explosion role, date window and marker radius. A report can appear in several timing groups."));
        composition.appendChild(bars(doc, categoryRows.map(function (row) { return { label: row.category.replace(/_/g, " "), value: row.total }; })));
        composition.appendChild(table(doc, ["Category", "Distinct reports", "Earlier", "Same date", "Later"], categoryRows.map(function (row) {
          return [row.category.replace(/_/g, " "), count(row.total), count(row.before), count(row.sameDay), count(row.after)];
        }), "Unique category counts; a report can appear in more than one timing group")); host.appendChild(composition);
      }
      const facilities = model.facilities || {}, facilityDomain = facilities.byDomain && facilities.byDomain[domain.id];
      if (focus === "facilities" && facilityDomain) {
        const node = card(doc, "Source-confirmed nuclear institutions");
        node.appendChild(paragraph(doc, (coverage.facilityInventory || "The nuclear facility inventory is partial.")
          + " Broader military/research markers have unreviewed nuclear status; they are not verified non-nuclear controls."));
        node.appendChild(stats(doc, [["Reviewed nuclear institutions", facilities.nuclearSitesN], ["Broader markers", facilities.broaderSitesN], ["Unknown activity evidence", facilityDomain.unknownActivityN]]));
        node.appendChild(paragraph(doc, "Groups use the selected " + (model.settings && model.settings.maxDistanceKm || state.radius || 500)
          + " km marker radius and documented institutional-history year ranges. Daily operation is not established; annual boundaries remain uncertain."));
        node.appendChild(bars(doc, (facilityDomain.groups || []).map(function (row) { return { label: row.label, value: row.reportsN }; })));
        node.appendChild(table(doc, ["Group", "Reports", "Share"], (facilityDomain.groups || []).map(function (row) { return [row.label, count(row.reportsN), percent(row.share)]; }),
          "Report marker composition around the two facility groups")); host.appendChild(node);
      }
      host.appendChild(policies(doc, "Recorded date roles & excluded records", (domain.byDateRole || []).map(function (row) {
        return row.dateRole.replace(/_/g, " ") + ": " + count(row.eligibleN) + " eligible markers; " + count(row.uniqueReports) + " reports paired with tests.";
      }).concat(Object.entries(domain.exclusions || {}).map(function (entry) { return entry[0].replace(/_/g, " ") + ": " + count(entry[1]); }))));
    }
    const links = (Array.isArray(model.sources) ? model.sources : []).filter(function (source) { return source.url; }).map(function (source) { return [source.title || source.label || "Source record", source.url]; });
    host.appendChild(policies(doc, "Source coverage, facility roles & limits", model.policyWarnings || model.warnings || [], links));
  }
  function render(target, modelValue, callbacksValue) {
    const model = modelValue || {}, callbacks = callbacksValue || {}, doc = target.ownerDocument;
    let state = states.get(target); if (!state) { state = { topic: "lunar", domain: "ufo", windowDays: 30 }; states.set(target, state); }
    if (model.status === "ready" && model.nuclear && state.settingsModel !== model.nuclear) {
      const settings = model.nuclear.settings || {};
      if (number(settings.windowDays) != null) state.windowDays = settings.windowDays;
      if (number(settings.maxDistanceKm) != null) state.radius = settings.maxDistanceKm;
      state.testRole = Array.isArray(settings.testRoles) && settings.testRoles.length === 1 ? settings.testRoles[0] : "all";
      state.settingsModel = model.nuclear;
    }
    if (model.status === "ready" && model.planetary && state.planetarySettingsModel !== model.planetary) {
      ["planet", "aspectPartner", "aspectOrbDegrees", "zodiacSystem", "ayanamsaId", "samplingMode"].forEach(function (key) {
        if (model.planetary[key] != null) state[key] = model.planetary[key];
      });
      state.planetarySettingsModel = model.planetary;
    }
    target.replaceChildren();
    if (model.status !== "ready") {
      target.appendChild(paragraph(doc, model.status === "error" ? model.message : model.status === "calculating"
        ? "Updating comparisons for the selected filters…" : "Loading comparison evidence and saved planetary positions. The first download may take a little longer; later selections reuse the loaded data."));
      if (model.status === "error" && callbacks.retry) { const retry = element(doc, "button", "secondary-button", "Retry loading"); retry.type = "button"; retry.addEventListener("click", callbacks.retry); target.appendChild(retry); }
      return;
    }
    const nav = element(doc, "div", "comparison-topic-nav"); nav.setAttribute("role", "tablist"); nav.setAttribute("aria-label", "Comparison question");
    const topics = [["lunar", "Moon"], ["nuclear", "Nuclear activity"], ["crossContext", "Crop ↔ animal reports"], ["planetary", "Planets"]];
    const host = element(doc, "div", "comparison-dashboard"); host.id = "analysis-comparison-focused-view"; host.setAttribute("role", "tabpanel");
    function update() { render(target, model, callbacks); }
    topics.forEach(function (entry, index) { const button = element(doc, "button", "", entry[1]); button.type = "button";
      button.id = "analysis-comparison-question-" + entry[0]; button.setAttribute("role", "tab");
      button.setAttribute("aria-controls", host.id); button.setAttribute("aria-selected", state.topic === entry[0] ? "true" : "false");
      button.tabIndex = state.topic === entry[0] ? 0 : -1;
      button.addEventListener("click", function () { state.topic = entry[0]; update(); doc.getElementById(button.id).focus(); });
      button.addEventListener("keydown", function (event) { let next;
        if (event.key === "ArrowRight") next = (index + 1) % topics.length;
        if (event.key === "ArrowLeft") next = (index + topics.length - 1) % topics.length;
        if (event.key === "Home") next = 0; if (event.key === "End") next = topics.length - 1;
        if (next == null) return; event.preventDefault(); state.topic = topics[next][0]; update(); doc.getElementById("analysis-comparison-question-" + state.topic).focus();
      }); nav.appendChild(button);
    });
    target.appendChild(nav); host.setAttribute("aria-labelledby", "analysis-comparison-question-" + state.topic);
    if (state.topic === "lunar") renderLunar(doc, host, model.lunar || {}, state, update);
    else if (state.topic === "nuclear") renderNuclear(doc, host, model.nuclear || {}, state, update, callbacks);
    else if (state.topic === "planetary") renderPlanetary(doc, host, model.planetary || {}, state, update, callbacks, model.planetaryHeatmaps);
    else renderCross(doc, host, model.crossContext || {});
    target.appendChild(host); target.appendChild(paragraph(doc, model.scope, "comparison-scope"));
    target.appendChild(paragraph(doc, "These questions use their own calendar references. The general Analysis reference baseline does not change these comparison results.", "comparison-scope"));
    const download = element(doc, "button", "secondary-button comparison-download", "Download comparison evidence"); download.type = "button";
    download.addEventListener("click", function () { const view = doc.defaultView;
      const url = view.URL.createObjectURL(new view.Blob([JSON.stringify(model, null, 2)], { type: "application/json" }));
      const link = doc.createElement("a"); link.href = url; link.download = "ufo-context-comparison-evidence.json"; link.click(); view.setTimeout(function () { view.URL.revokeObjectURL(url); }, 1000);
    }); target.appendChild(download);
  }
  return { render, artifactLoadTimeoutMs };
});
