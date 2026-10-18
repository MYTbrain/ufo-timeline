(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UfoAnalysisCollectionsView = api;
})(typeof self !== "undefined" ? self : globalThis, function () {
  "use strict";
  const AXES = [
    ["being", "Being descriptions"], ["action", "Collection actions"], ["decade", "Decades"],
    ["country", "Countries"], ["source", "Source collections"], ["craft", "Craft categories"], ["abduction", "Abduction classifications"],
  ];
  const number = value => Number(value || 0).toLocaleString();
  function label(value) { return String(value == null ? "" : value).replace(/_/g, " "); }
  function sourceText(value) { return value && typeof value === "object" ? Object.entries(value).map(([key, text]) => label(key) + ": " + (typeof text === "object" ? JSON.stringify(text) : text)).join(" · ") : value; }
  function entries(values) { return (values || []).map(value => typeof value === "string" ? { key: value, label: label(value) }
    : { key: String(value.key ?? value.id ?? value.value ?? ""), label: value.label || value.title || label(value.key ?? value.id) }); }
  function safeUrl(value) { try { const url = new URL(value); return ["http:", "https:"].includes(url.protocol) ? url.href : null; } catch (_) { return null; } }
  function csvValue(value) { let text = String(value == null ? "" : value); if (/^[\s]*[=+@-]/.test(text)) text = "'" + text; return '"' + text.replace(/"/g, '""') + '"'; }

  function create(target, configuration) {
    const config = configuration || {}, api = config.evidenceApi, doc = target.ownerDocument;
    const state = { allRecords: false, scope: "soilplants", disposition: "direct", includeMemberVariants: false, axis: "being", metric: "count", material: "", action: "", being: "", country: "", decade: "", source: "", query: "", page: 0, mode: "reports", cell: null };
    let evidence, model, context, generation = 0, loading;
    const controls = {}, PAGE = 15;
    function node(tag, className, text) { const element = doc.createElement(tag); if (className) element.className = className; if (text != null) element.textContent = String(text); return element; }
    function button(text, callback, className) { const element = node("button", className || "secondary-button", text); element.type = "button"; element.addEventListener("click", callback); return element; }
    function picker(parent, key, title, choices, initial, callback) {
      const field = node("label", "collection-picker"); field.appendChild(node("span", "", title));
      const select = node("select"); select.id = "collection-study-" + key; select.setAttribute("aria-label", title);
      entries(choices).forEach(item => { const option = node("option", "", item.label); option.value = item.key; select.appendChild(option); });
      select.value = initial; field.appendChild(select); parent.appendChild(field); controls[key] = select;
      select.addEventListener("change", () => { callback(select.value); }); return select;
    }
    const status = node("p", "collection-study-status"); status.setAttribute("role", "status");
    const retry = button("Refresh collection view", () => refresh()); retry.hidden = true;
    const toolbar = node("div", "collection-toolbar");
    picker(toolbar, "cohort", "Report scope", [{ key: "shared", label: "Current shared filters & dates" }, { key: "all", label: "All collection reports" }], "shared", value => { state.allRecords = value === "all"; state.page = 0; state.cell = null; refresh(); });
    picker(toolbar, "axis", "Compare materials against", AXES.map(item => ({ key: item[0], label: item[1] })), "being", value => { state.axis = value; state.cell = null; state.page = 0; render(); });
    picker(toolbar, "disposition", "Evidence included", [{ key: "direct", label: "Directly described acts" }, { key: "includeuncertain", label: "Include uncertain interpretations" }, { key: "allcontexts", label: "Include adjacent contexts" }, { key: "controls", label: "Excluded / negative controls only" }], "direct", value => { state.disposition = value; if (value === "controls") { state.scope = "allmaterials"; controls.scope.value = "allmaterials"; } resetAndCompute(); });
    const refine = node("details", "analysis-supporting-details collection-refine"); refine.appendChild(node("summary", "", "Refine materials, actions, beings & places"));
    const refinements = node("div", "collection-toolbar"); refine.appendChild(refinements);
    picker(refinements, "scope", "Collection subject", [{ key: "soilplants", label: "Soil & plants" }, { key: "allmaterials", label: "All reviewed materials" }], "soilplants", value => { state.scope = value; resetAndCompute(); });
    const filters = [["material", "Material"], ["action", "Action"], ["being", "Being description"], ["country", "Country"], ["decade", "Decade"], ["source", "Source collection"]];
    filters.forEach(([key, title]) => picker(refinements, key, title, [{ key: "", label: "All" }], "", value => { state[key] = value; resetAndCompute(); }));
    const variantLabel = node("label", "collection-variant-toggle");
    const variants = node("input"); variants.type = "checkbox"; variants.id = "collection-study-member-variants";
    variantLabel.append(variants, node("span", "", "Include differing source versions")); refinements.appendChild(variantLabel);
    variants.addEventListener("change", () => { state.includeMemberVariants = variants.checked; resetAndCompute(); });
    refine.appendChild(node("p", "analysis-chart-policy", "Differing versions use a matched source passage that differs from the catalog's main account. Their combined date, place or being fields may belong to different descriptions, so they are excluded by default."));
    refinements.appendChild(button("Reset study filters", () => {
      state.scope = "soilplants"; state.disposition = "direct"; state.query = ""; search.value = "";
      state.includeMemberVariants = false; variants.checked = false;
      filters.forEach(([key]) => { state[key] = ""; controls[key].value = ""; });
      controls.scope.value = "soilplants"; controls.disposition.value = "direct"; resetAndCompute();
    }));
    const summary = node("div", "collection-stat-grid");
    const empty = node("div", "collection-empty"); empty.hidden = true;
    empty.appendChild(node("p", "", "No retained collection reports match this selection. The shared date window or other filters may be excluding them."));
    empty.appendChild(button("Show all collection reports", () => { state.allRecords = true; controls.cohort.value = "all"; resetAndCompute(); }));
    const matrixHeading = node("div", "collection-matrix-heading"); matrixHeading.appendChild(node("h5", "", "Collection comparison"));
    picker(matrixHeading, "metric", "Heatmap value", [{ key: "count", label: "Report count" }, { key: "share", label: "Within-material share" }], "count", value => { state.metric = value; renderMatrix(); });
    const chart = node("div", "collection-matrix-container"), matrixNote = node("p", "analysis-chart-policy");
    const policy = node("details", "analysis-supporting-details collection-method"); policy.appendChild(node("summary", "", "Coverage, source limits & counting method"));
    const method = node("div"); policy.appendChild(method);
    const tabs = node("div", "collection-list-tabs");
    const reportsTab = button("Matched reports", () => { state.mode = "reports"; state.page = 0; renderList(); });
    const casesTab = button("Source dossiers & controls", () => { state.mode = "cases"; state.page = 0; renderList(); });
    tabs.append(reportsTab, casesTab);
    const searchLabel = node("label", "collection-search", "Search the displayed collection records");
    const search = node("input"); search.type = "search"; search.id = "collection-study-search"; search.placeholder = "Material, place, source or report ID"; searchLabel.appendChild(search);
    search.addEventListener("input", () => { state.query = search.value.toLocaleLowerCase().trim(); state.page = 0; renderList(); });
    const listStatus = node("p", "collection-list-status"), list = node("div", "collection-report-list"), pagination = node("div", "collection-pagination");
    const exports = node("div", "collection-exports");
    exports.append(button("Export comparison JSON", () => download("json")), button("Export matched reports CSV", () => download("csv")));
    target.replaceChildren(status, retry, toolbar, refine, summary, empty, matrixHeading, chart, matrixNote, policy, tabs, searchLabel, listStatus, list, pagination, exports);

    function resetAndCompute() { state.page = 0; state.cell = null; compute(); }
    function compute() {
      if (!evidence) return;
      model = api.compute({ evidence, allowedEventIds: state.allRecords ? undefined : context && context.allowedEventIds,
        scope: state.scope, disposition: state.disposition, includeMemberVariants: state.includeMemberVariants, material: state.material || undefined, action: state.action || undefined,
        being: state.being || undefined, country: state.country || undefined, decade: state.decade || undefined, source: state.source || undefined });
      render();
    }
    function refreshOptions() {
      const all = api.compute({ evidence, scope: "allmaterials", disposition: "allcontexts", includeMemberVariants: true });
      filters.forEach(([key]) => {
        const plural = { material: "materials", action: "actions", being: "beings", country: "countries", decade: "decades", source: "sources" }[key];
        let values = all.options && (all.options[key] || all.options[plural]);
        if (!values && all.taxonomy) values = all.taxonomy[key] || all.taxonomy[key + "s"];
        const select = controls[key], selected = state[key]; select.replaceChildren();
        [{ key: "", label: "All" }].concat(entries(values)).forEach(item => { const option = node("option", "", item.label); option.value = item.key; select.appendChild(option); });
        select.value = selected;
      });
    }
    function render() {
      if (!model) return;
      const stats = model.stats || {}, snapshot = context && context.snapshot, time = snapshot && snapshot.timeRange;
      status.textContent = state.allRecords ? "Full collection study · shared map filters are not applied."
        : "Following shared filters" + (time ? " · " + (time.mode === "full" ? "All time" : [time.startIso, time.endIso].filter(Boolean).join(" to ")) : "") + ".";
      summary.replaceChildren();
      [["Reports in comparison", (model.reports || []).length], ["Beings not indexed", stats.unknownBeingN], ["Geography unknown", stats.unknownGeographyN], ["Source dossiers · full inventory", (evidence.cases || []).length]].forEach(([title, value]) => {
        const item = node("div", "collection-stat"); item.append(node("strong", "", number(value)), node("span", "", title)); summary.appendChild(item);
      });
      empty.hidden = (model.reports || []).length > 0;
      method.replaceChildren();
      method.appendChild(node("p", "", "Counts are catalog report representations, not independent encounters or evidence of a collection program. A report may describe several materials and beings, so cells can overlap. Unclassified fields remain unknown."));
      method.appendChild(node("p", "", number((evidence.reports || []).length) + " retained catalog reports · " + number((evidence.cases || []).length) + " source dossiers, including uncertain examples and controls. Dossiers without a reviewed catalog association never enter the report heatmaps. Date, place and being fields retain their recorded precision and source limits."));
      const policies = Array.isArray(model.policy) ? model.policy : Array.isArray(evidence.policy) ? evidence.policy : [evidence.policy && evidence.policy.coding].filter(Boolean);
      policies.forEach(text => method.appendChild(node("p", "", text)));
      const coverage = node("details"); coverage.appendChild(node("summary", "", "Exact study coverage"));
      const details = node("dl", "collection-coverage-values");
      [["Retained report representations", stats.indexedReportN], ["Reports in this comparison", stats.filteredReportN], ["Differing source versions held outside this comparison", stats.heldMemberVariantN], ["Source dossiers without an indexed report link", stats.unjoinedDossierN], ["Reports without a supported date", stats.unknownDateN], ["Reports with qualified source dates", stats.uncertainSourceDateN], ["Original catalog records screened", evidence.coverage && evidence.coverage.catalogReportsScanned], ["Original candidates reviewed", evidence.coverage && evidence.coverage.originalReviewedCandidateN]].forEach(([title, value]) => {
        details.append(node("dt", "", title), node("dd", "", number(value)));
      }); coverage.appendChild(details);
      const recall = evidence.coverage && evidence.coverage.complementaryPass;
      if (recall) coverage.appendChild(node("p", "", "Complementary pass: " + number(recall.recordsScreened) + " records screened; " + number(recall.newLexicalCandidates) + " new lexical candidates; " + number(recall.manualContextsReviewed) + " contexts manually reviewed; " + number(recall.retainedRows) + " representations retained in that review lane. " + number(recall.remainingUnreviewed) + " leads remain unreviewed. Keyword matches are not positive collection reports."));
      (evidence.coverage && evidence.coverage.methodLimits || []).forEach(text => coverage.appendChild(node("p", "", text)));
      method.appendChild(coverage);
      renderMatrix(); renderList();
    }
    function renderMatrix() {
      if (!model) return;
      chart.replaceChildren();
      const matrix = model.matrices && model.matrices[state.axis];
      if (!matrix || !matrix.rows || !matrix.rows.length) { chart.appendChild(node("p", "", "No eligible collection data for this comparison.")); return; }
      const allColumns = matrix.columns || [], totals = allColumns.map((column, index) => ({ column, index, total: matrix.rows.reduce((sum, row) => sum + Number(row.cells[index] || 0), 0) }));
      let columns = totals;
      if (columns.length > 24) {
        columns = totals.slice().sort((a, b) => b.total - a.total).slice(0, 20);
        totals.filter(item => /unknown|unspecified|unclassified|not_recorded/i.test(item.column.key)).forEach(item => { if (!columns.includes(item)) columns.push(item); });
      }
      const table = node("table", "collection-heatmap"); table.appendChild(node("caption", "", "Reported material × " + (AXES.find(item => item[0] === state.axis) || ["", state.axis])[1]));
      const head = node("thead"), heading = node("tr"); const corner = node("th", "", "Material · reports"); corner.scope = "col"; heading.appendChild(corner);
      columns.forEach(item => { const cell = node("th", "", item.column.label); cell.scope = "col"; heading.appendChild(cell); }); head.appendChild(heading); table.appendChild(head);
      const body = node("tbody"), peak = Math.max(1, ...matrix.rows.flatMap(row => row.cells.map(Number))), gridButtons = [];
      matrix.rows.forEach((row, rowIndex) => {
        const tr = node("tr"), th = node("th", "", row.label + " · " + number(row.total)); th.scope = "row"; tr.appendChild(th);
        columns.forEach((item, columnIndex) => {
          const count = Number(row.cells[item.index] || 0), eligible = Number(row.total || 0), value = state.metric === "share" ? eligible ? (100 * count / eligible).toFixed(1) + "%" : "—" : number(count);
          const td = node("td"), cell = button(value, () => { state.mode = "reports"; state.page = 0; state.cell = { material: row.key, axis: state.axis, key: item.column.key, title: row.label + " × " + item.column.label }; renderList(); listStatus.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, "collection-heatmap-cell");
          cell.disabled = count === 0;
          cell.title = row.label + " × " + item.column.label + ": " + number(count) + " reports / " + number(eligible) + " material reports";
          cell.setAttribute("aria-label", cell.title); cell.style.setProperty("--collection-intensity", String(count ? 0.10 + 0.70 * (state.metric === "share" ? count / Math.max(1, eligible) : count / peak) : 0));
          cell.tabIndex = !cell.disabled && !gridButtons.length ? 0 : -1;
          if (!cell.disabled) gridButtons.push({ row: rowIndex, column: columnIndex, button: cell });
          td.appendChild(cell); tr.appendChild(td);
        }); body.appendChild(tr);
      }); table.appendChild(body); chart.appendChild(table);
      gridButtons.forEach((entry, index) => entry.button.addEventListener("keydown", event => {
        let next;
        if (event.key === "ArrowRight") next = gridButtons[index + 1];
        if (event.key === "ArrowLeft") next = gridButtons[index - 1];
        if (event.key === "ArrowDown") next = gridButtons.find(item => item.row > entry.row && item.column === entry.column);
        if (event.key === "ArrowUp") next = gridButtons.slice().reverse().find(item => item.row < entry.row && item.column === entry.column);
        if (event.key === "Home") next = gridButtons[0];
        if (event.key === "End") next = gridButtons[gridButtons.length - 1];
        if (next) { event.preventDefault(); gridButtons.forEach(item => { item.button.tabIndex = item === next ? 0 : -1; }); next.button.focus(); }
      }));
      matrixNote.textContent = "Each material row uses its own unique-report denominator. Unknown values are retained; multi-label categories overlap. Click a populated cell to inspect its reports."
        + (columns.length < allColumns.length ? " Showing " + columns.length + " of " + allColumns.length + " columns by report count; JSON export includes the full matrix." : "");
    }
    function filteredReports() {
      if (!state.cell) return model.reports || [];
      const selection = { evidence, allowedEventIds: new Set((model.reports || []).map(row => String(row.eventId))), scope: "allmaterials", disposition: state.disposition, includeMemberVariants: state.includeMemberVariants, material: state.cell.material };
      selection[state.cell.axis] = state.cell.key;
      return api.compute(selection).reports || [];
    }
    function sourceLinks(parent, values) {
      (values || []).forEach(value => {
        const url = safeUrl(typeof value === "string" ? value : value.url); if (!url) return;
        const link = node("a", "", typeof value === "string" ? new URL(url).hostname : value.title || value.locator || new URL(url).hostname);
        link.href = url; link.target = "_blank"; link.rel = "noopener noreferrer"; parent.appendChild(link);
      });
    }
    function reportCard(report) {
      const card = node("details", "collection-report"), heading = node("summary");
      heading.append(node("strong", "", report.title || report.caseTitle || report.location || "Collection report"), node("span", "collection-record-meta", [report.dateLabel || report.dateIso || report.dateRaw || "Date unknown", report.country || "Country unknown", label(report.disposition)].join(" · "))); card.appendChild(heading);
      card.appendChild(node("p", "", report.excerpt || report.datasetExcerpt || "No public excerpt retained."));
      card.appendChild(node("p", "collection-record-meta", report.reviewReason || report.reason || "Source-context classification; not an event verification."));
      card.appendChild(node("p", "collection-record-meta", "Report " + report.eventId + " · " + (report.source || "Source unknown") + " · " + (report.sourceId || "") + " · " + (report.datePrecision || "Date precision unknown")));
      if (report.sourceDateNote) card.appendChild(node("p", "collection-record-meta", report.sourceDateNote));
      card.appendChild(node("p", "collection-record-meta", "Being descriptions: " + (report.beingTypes && report.beingTypes.length ? report.beingTypes.map(label).join(", ") : "Not indexed")
        + " · Craft: " + (report.craftLabel || label(report.craftType) || "Not indexed")));
      if (report.sourceActorNote) card.appendChild(node("p", "collection-record-meta", report.sourceActorNote));
      if (report.canonicalPrimaryDiffers) card.appendChild(node("p", "collection-record-meta", "Differing source version: this matched passage differs from the catalog's main account. Treat cross-field associations as a sensitivity view."));
      const sources = node("div", "collection-source-links"); sourceLinks(sources, report.sourceUrls || []); card.appendChild(sources);
      if (config.onOpenReport) card.appendChild(button("Read preserved catalog report", async event => {
        const control = event.currentTarget; control.disabled = true;
        try { await config.onOpenReport(report.eventId); } catch (_) { control.textContent = "Could not open report · retry"; } finally { control.disabled = false; }
      })); return card;
    }
    function caseCard(record) {
      const card = node("details", "collection-report"), heading = node("summary");
      heading.append(node("strong", "", record.title || record.caseId || record.case_id), node("span", "collection-record-meta", [record.dateLabel || record.date || "Date unknown", record.location || record.place || record.country || "Place unknown", label(record.disposition)].join(" · "))); card.appendChild(heading);
      card.appendChild(node("p", "", record.observedBehavior || record.observed_behavior || record.behavior || "See the retained source descriptions."));
      card.appendChild(node("p", "collection-record-meta", "Date precision: " + label(record.datePrecision || "Not established")));
      const chronology = sourceText(record.earliestSource || record.earliest_source)
        || [record.reportedDate ? "Source report filed: " + record.reportedDate : "", record.postedDate ? "Published: " + record.postedDate : ""].filter(Boolean).join(" · ");
      card.appendChild(node("p", "collection-record-meta", chronology || "Source chronology is not established."));
      (record.limitations || []).forEach(text => card.appendChild(node("p", "collection-record-meta", text)));
      const ids = record.indexedReportIds || record.acceptedEventIds || [];
      card.appendChild(node("p", "collection-record-meta", ids.length ? "Catalog representations: " + ids.join(", ") + ". This association does not establish incident identity or source independence." : "No accepted catalog association · excluded from report comparisons."));
      const sources = node("div", "collection-source-links"); sourceLinks(sources, record.sources || record.sourceUrls || []); card.appendChild(sources); return card;
    }
    function renderList() {
      if (!model) return;
      const cases = state.mode === "cases";
      reportsTab.setAttribute("aria-pressed", String(!cases)); casesTab.setAttribute("aria-pressed", String(cases));
      let values = cases ? evidence.cases || [] : filteredReports();
      if (state.query) { const words = state.query.split(/\s+/); values = values.filter(row => words.every(word => JSON.stringify(row).toLocaleLowerCase().includes(word))); }
      const pages = Math.max(1, Math.ceil(values.length / PAGE)); state.page = Math.min(state.page, pages - 1);
      listStatus.replaceChildren(node("span", "", cases ? number(values.length) + " source dossiers · full inventory, including controls; excluded from report counts."
        : number(values.length) + " matching report representations" + (state.cell ? " · " + state.cell.title : "") + "."));
      if (!cases && state.cell) listStatus.appendChild(button("Clear cell selection", () => { state.cell = null; state.page = 0; renderList(); }));
      list.replaceChildren(); values.slice(state.page * PAGE, (state.page + 1) * PAGE).forEach(row => list.appendChild(cases ? caseCard(row) : reportCard(row)));
      if (!values.length) list.appendChild(node("p", "", "No matching records."));
      pagination.replaceChildren();
      const previous = button("Previous", () => { state.page -= 1; renderList(); }), next = button("Next", () => { state.page += 1; renderList(); });
      previous.disabled = state.page === 0; next.disabled = state.page >= pages - 1; pagination.append(previous, node("span", "", "Page " + (state.page + 1) + " of " + pages), next);
    }
    function download(kind) {
      if (!model) return;
      let data, mime;
      if (kind === "json") { data = JSON.stringify({ schemaId: "ufo-collection-comparison-export-v1", generatedUtc: new Date().toISOString(), filters: state, listFiltersDoNotChangeMatrices: true, sharedFilters: context && context.snapshot, countUnit: "catalog report representations", matrices: model.matrices, stats: model.stats, reportIds: (model.reports || []).map(row => row.eventId), provenance: evidence.provenance, policy: model.policy }, null, 2); mime = "application/json"; }
      else { const words = state.query.split(/\s+/).filter(Boolean);
        const rows = filteredReports().filter(row => words.every(word => JSON.stringify(row).toLocaleLowerCase().includes(word)));
        const fields = ["eventId", "source", "sourceId", "sourceFamily", "canonicalPrimaryDiffers", "dateLabel", "dateIso", "datePrecision", "sourceDatePrecision", "sourceDateNote", "country", "countryBasis", "location", "disposition", "scope", "materials", "actions", "beingTypes", "sourceActorNote", "reviewReason", "sourceUrls"];
        data = [fields.join(",")].concat(rows.map(row => fields.map(key => csvValue(Array.isArray(row[key]) ? row[key].join("; ") : row[key])).join(","))).join("\r\n"); mime = "text/csv;charset=utf-8"; }
      const view = doc.defaultView, url = view.URL.createObjectURL(new view.Blob([data], { type: mime })), link = node("a");
      link.href = url; link.download = "collection-study." + kind; link.click(); view.setTimeout(() => view.URL.revokeObjectURL(url), 1000);
    }
    async function load() {
      if (loading) return loading;
      loading = api.load({ manifestUrl: config.manifestUrl }).then(value => { evidence = value; refreshOptions(); return refresh(true); }).catch(error => { loading = null; throw error; }); return loading;
    }
    async function refresh(throwOnError) {
      if (!evidence) return;
      const token = ++generation;
      try {
        const next = await (config.getContext ? config.getContext({ reportIds: evidence.reports.map(row => String(row.eventId)), allRecords: state.allRecords }) : { allowedEventIds: undefined });
        if (token !== generation) return;
        context = next; retry.hidden = true;
        [summary, matrixHeading, chart, matrixNote, tabs, searchLabel, listStatus, list, pagination, exports].forEach(element => { element.hidden = false; });
        compute();
      } catch (error) { if (token === generation) {
        model = null; status.textContent = "Collection view could not refresh: " + (error.message || error); retry.hidden = false;
        [summary, empty, matrixHeading, chart, matrixNote, tabs, searchLabel, listStatus, list, pagination, exports].forEach(element => { element.hidden = true; });
        if (throwOnError) throw error;
      } }
    }
    return { load, refresh, getModel: () => model, getState: () => Object.assign({}, state) };
  }
  return Object.freeze({ create, safeUrl, csvValue });
});
