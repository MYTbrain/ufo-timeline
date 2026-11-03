(function (root) {
  "use strict";

  const lanes = [
    { id: "impression", label: "Ground impressions", short: "Impressions", kind: "impression" },
    { id: "scorching", label: "Scorching", short: "Scorching", kind: "scorching" },
    { id: "twist", label: "Vegetation swirl or twist", short: "Swirl or twist", kind: "deformation" },
    { id: "deformation", label: "Other vegetation deformation", short: "Other deformation", kind: "deformation" },
    { id: "surface", label: "Other surface traces", short: "Surface traces", kind: "surface" },
  ];
  const layouts = [
    ["three_point", "Three marks or sectors"],
    ["four_point", "Four marks or arms"],
    ["ring", "Ring or circular area"],
    ["oval", "Oval or elongated"],
    ["radial", "Radial marks"],
    ["opposed", "Opposed sectors"],
    ["rows", "Linear or parallel"],
    ["swirl", "Swirled vegetation"],
    ["twist", "Localized twisting"],
    ["irregular", "Uneven or interrupted"],
    ["isolated", "Isolated mark or patch"],
    ["unknown", "Layout unspecified"],
  ];
  const handedness = {
    clockwise: "Clockwise",
    counterclockwise: "Counterclockwise",
    mixed: "Mixed directions",
    uncertain: "Uncertain or unreported",
  };
  const number = new Intl.NumberFormat("en");

  function traceLane(trace) {
    if (trace.kind === "deformation" &&
        (trace.pattern?.families?.some((family) => family === "swirl" || family === "twist") ||
         trace.pattern?.handedness)) return "twist";
    return trace.kind;
  }

  function addSite(map, site, trace) {
    const existing = map.get(site.id);
    if (existing) {
      existing.traces.push(trace);
      return;
    }
    map.set(site.id, { site, traces: [trace] });
  }

  function diagramLanes(site) {
    const deformationLanes = new Set(site.traces.filter((trace) => trace.kind === "deformation").map(traceLane));
    return new Set((site.diagram?.layers || []).map((layer) => {
      if (layer.channel) return layer.channel;
      if (layer.kind !== "deformation") return layer.kind;
      return deformationLanes.size === 1 ? deformationLanes.values().next().value : null;
    }));
  }

  function analyze(cases, options = {}) {
    const selected = cases.filter((site) => {
      const linkedToPhillips = site.phillipsCaseNumber || options.phillipsCaseIds?.has(site.id);
      if (options.source === "phillips" && !linkedToPhillips) return false;
      if (options.source === "other" && linkedToPhillips) return false;
      if (options.origin && site.evidenceOrigin !== options.origin) return false;
      return !options.diagramsOnly || Boolean(site.diagram);
    });
    const byLane = new Map(lanes.map(({ id }) => [id, new Map()]));
    const byLayout = new Map(layouts.map(([id]) => [id, new Map(lanes.map((lane) => [lane.id, new Map()]))]));
    const byDirection = new Map(Object.keys(handedness).map((id) => [id, new Map()]));
    for (const site of selected) {
      for (const trace of site.traces) {
        if (options.dimensionsOnly && trace.pattern?.basis !== "dimensions") continue;
        const lane = traceLane(trace);
        addSite(byLane.get(lane), site, trace);
        const families = trace.pattern?.families;
        for (const family of new Set(families?.length ? families : ["unknown"])) {
          if (byLayout.has(family)) addSite(byLayout.get(family).get(lane), site, trace);
        }
        if (lane === "twist") addSite(byDirection.get(trace.pattern?.handedness) || byDirection.get("uncertain"), site, trace);
      }
    }

    const pairs = [];
    for (const [index, left] of lanes.entries()) {
      for (const right of lanes.slice(index + 1)) {
        const shared = [...byLane.get(left.id).values()]
          .filter(({ site }) => byLane.get(right.id).has(site.id))
          .map(({ site, traces }) => ({ site, traces: [...traces, ...byLane.get(right.id).get(site.id).traces] }));
        const sharedPlans = shared.filter(({ site }) => {
          const layers = diagramLanes(site);
          return layers.has(left.id) && layers.has(right.id);
        });
        pairs.push({ left, right, shared, sharedPlans });
      }
    }
    return { selected, byLane, byLayout, byDirection, pairs };
  }

  function render(document, cases, catalogs, openCase, metrics, audit) {
    function el(tag, className, text) {
      const node = document.createElement(tag);
      if (className) node.className = className;
      if (text != null) node.textContent = text;
      return node;
    }

    function selectField(label, choices) {
      const wrapper = el("label", "", label);
      const select = el("select");
      for (const [id, text] of choices) {
        const option = el("option", "", text);
        option.value = id;
        select.append(option);
      }
      wrapper.append(select);
      return { wrapper, select };
    }

    function tableBlock(title, headings) {
      const section = el("section", "analysis-card landing-comparison-card");
      section.append(el("h4", "", title));
      const scroll = el("div", "landing-catalog-scroll");
      scroll.tabIndex = 0;
      scroll.setAttribute("role", "region");
      scroll.setAttribute("aria-label", title);
      const table = el("table", "landing-layout-table landing-comparison-table");
      const row = table.createTHead().insertRow();
      for (const label of headings) {
        const heading = el("th", "", label);
        heading.scope = "col";
        row.append(heading);
      }
      const body = table.createTBody();
      scroll.append(table);
      section.append(scroll);
      return { section, body };
    }

    function rowHeading(row, label) {
      const heading = el("th", "", label);
      heading.scope = "row";
      row.append(heading);
    }

    const panel = el("section", "landing-combined");
    const filters = el("div", "landing-catalog-filters");
    const source = selectField("Reviewed case set", [["all", "All reviewed cases"],
      ["phillips", "Linked to a Phillips case number"], ["other", "Other reviewed cases"]]);
    const evidence = selectField("Layout evidence", [["all", "Descriptions and dimensions"],
      ["dimensions", "Recorded dimensions only"]]);
    const availability = selectField("Diagram coverage", [["all", "All reviewed cases"],
      ["diagrams", "Cases with diagrams"]]);
    const origin = selectField("Source checked", [["", "All reviewed cases"], ["original", "Original reporting checked"],
      ["catalog", "Compiled accounts checked"]]);
    filters.append(source.wrapper, evidence.wrapper, availability.wrapper, origin.wrapper);
    const scope = el("p", "landing-scope-note");
    scope.setAttribute("role", "status");
    const matrix = tableBlock("Recurring layouts by trace type", ["Layout", ...lanes.map(({ short }) => short)]);
    const details = el("section", "analysis-card landing-comparison-card landing-comparison-detail");
    details.hidden = true;
    details.tabIndex = -1;
    const pairs = tableBlock("Trace types reported at the same site", ["Trace pair", "Case dossiers", "Plans with both layers"]);
    const twists = tableBlock("Vegetation handedness", ["Reported direction", "Case dossiers"]);
    const dimensions = tableBlock("Compare recorded dimensions", ["Case", "Trace", "Measurements", "Descriptive comparison"]);
    dimensions.section.append(el("p", "landing-scope-note",
      "Length spread is the difference between the longest and shortest values divided by their mean. Edge gaps and measured sides keep their source labels. Single reported diameters stay in the case dossiers."));
    const sideBySide = el("section", "analysis-card landing-comparison-card");
    sideBySide.append(el("h4", "", "Compare two site diagrams"),
      el("p", "landing-scope-note", "Each diagram uses its own local scale and orientation. Use its layer controls to isolate marks."));
    const left = selectField("Left site", []);
    const right = selectField("Right site", []);
    const compareFields = el("div", "landing-catalog-filters");
    compareFields.append(left.wrapper, right.wrapper);
    const diagrams = el("div", "landing-diagram-pair");
    sideBySide.append(compareFields, diagrams);

    function showDetails(title, entries) {
      const list = el("ul", "landing-comparison-cases");
      for (const { site, traces } of entries) {
        const li = el("li");
        const link = el("button", "landing-catalog-case-link", site.title);
        link.type = "button";
        link.addEventListener("click", () => openCase(site.id));
        li.append(link);
        const observations = el("ul");
        for (const trace of traces) {
          const pattern = trace.pattern;
          const evidence = pattern?.basis === "dimensions" ? "Recorded dimensions" : "Description";
          observations.append(el("li", "", (pattern?.label || trace.observation) + " · " + evidence));
        }
        li.append(observations);
        list.append(li);
      }
      details.replaceChildren(el("h4", "", title), list);
      details.hidden = false;
      details.focus();
    }

    function countCell(cell, entries, title, maxCount) {
      if (!entries.length) {
        cell.textContent = "0";
        return;
      }
      const button = el("button", "landing-comparison-count", number.format(entries.length));
      button.type = "button";
      button.setAttribute("aria-label", title + ", " + entries.length + " cases");
      if (maxCount) button.style.setProperty("--landing-count-share", entries.length / maxCount);
      button.addEventListener("click", () => showDetails(title, entries));
      cell.append(button);
    }

    const phillipsReviews = Object.values(audit?.phillipsRecords || {});
    const phillipsCaseIds = new Set(phillipsReviews.map((review) => review.caseId).filter(Boolean));
    let comparisonCases = [];
    function drawDiagrams() {
      diagrams.replaceChildren();
      if (!comparisonCases.length) {
        diagrams.append(el("p", "landing-scope-note", "No site diagrams in this case set."));
        return;
      }
      for (const field of [left, right]) {
        const site = comparisonCases.find((candidate) => candidate.id === field.select.value);
        if (!site) continue;
        const card = el("article", "landing-diagram-pair-case");
        const title = el("button", "landing-catalog-case-link", site.title);
        title.type = "button";
        title.addEventListener("click", () => openCase(site.id));
        card.append(title);
        const graphic = root.UfoLandingSiteDiagrams?.render(document, site.diagram, (id) => {
          const item = site.sources.find((candidate) => candidate.id === id);
          if (!item) return null;
          const link = el("a", "", item.label);
          link.href = item.url;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          return link;
        });
        if (graphic) card.append(graphic);
        diagrams.append(card);
      }
    }

    function refresh() {
      const model = analyze(cases, {
        source: source.select.value,
        phillipsCaseIds,
        origin: origin.select.value,
        dimensionsOnly: evidence.select.value === "dimensions",
        diagramsOnly: availability.select.value === "diagrams",
      });
      const eligible = new Set([...model.byLane.values()].flatMap((group) => [...group.keys()]));
      scope.textContent = model.selected.length + " reviewed case dossiers in this selection. " +
        eligible.size + " have traces that meet the selected evidence filter. A site counts once per cell and can appear in several layout rows. A layout is a symmetry lead. Repeated shapes and reported angles leave exact symmetry, mechanism, and source count open.";
      details.hidden = true;
      const layoutRows = layouts.map(([id, label]) => {
        const groups = model.byLayout.get(id);
        return { label, entries: lanes.map((lane) => [...groups.get(lane.id).values()]) };
      });
      const maxCount = Math.max(1, ...layoutRows.flatMap(({ entries }) => entries.map((group) => group.length)));
      matrix.body.replaceChildren();
      const totals = matrix.body.insertRow();
      rowHeading(totals, "Cases with trace type");
      for (const lane of lanes) {
        countCell(totals.insertCell(), [...model.byLane.get(lane.id).values()], lane.label, 0);
      }
      for (const { label, entries } of layoutRows) {
        const row = matrix.body.insertRow();
        rowHeading(row, label);
        for (const [index, group] of entries.entries()) {
          countCell(row.insertCell(), group, label + " · " + lanes[index].label, maxCount);
        }
      }

      pairs.body.replaceChildren();
      for (const { left, right, shared, sharedPlans } of model.pairs) {
        const row = pairs.body.insertRow();
        const label = left.short + " + " + right.short;
        rowHeading(row, label);
        countCell(row.insertCell(), shared, label, 0);
        countCell(row.insertCell(), sharedPlans, label + " · Both layers plotted", 0);
      }
      twists.body.replaceChildren();
      for (const [id, label] of Object.entries(handedness)) {
        const row = twists.body.insertRow();
        rowHeading(row, label);
        countCell(row.insertCell(), [...model.byDirection.get(id).values()], label + " vegetation", 0);
      }
      dimensions.body.replaceChildren();
      const measureFormat = new Intl.NumberFormat("en", { maximumFractionDigits: 2 });
      for (const site of model.selected) {
        for (const trace of site.traces) {
          const pattern = trace.pattern;
          if (pattern?.basis !== "dimensions") continue;
          const spread = metrics.edgeSpread(pattern.edgesM);
          const spans = metrics.spanMetrics(pattern.dimensions);
          if (spread === null && !spans) continue;
          const row = dimensions.body.insertRow();
          rowHeading(row, site.title);
          row.insertCell().textContent = lanes.find(({ id }) => id === traceLane(trace)).short;
          row.insertCell().textContent = spread !== null ?
            (pattern.edgeLabel || "Side") + " lengths " + pattern.edgesM.map((value) => measureFormat.format(value)).join(", ") + " m" :
            measureFormat.format(spans.longM) + " × " + measureFormat.format(spans.shortM) + " m";
          row.insertCell().textContent = spread !== null ?
            measureFormat.format(spread) + "% spread" : measureFormat.format(spans.aspectRatio) + " : 1 span ratio";
        }
      }
      if (!dimensions.body.rows.length) {
        const row = dimensions.body.insertRow();
        const cell = row.insertCell();
        cell.colSpan = 4;
        cell.textContent = "No comparable measured lengths in this case set.";
      }

      comparisonCases = model.selected.filter(({ diagram }) => diagram);
      for (const [index, { select }] of [left, right].entries()) {
        const prior = select.value;
        select.replaceChildren(...comparisonCases.map((site) => {
          const option = el("option", "", site.title);
          option.value = site.id;
          return option;
        }));
        select.disabled = !comparisonCases.length;
        if (comparisonCases.some(({ id }) => id === prior)) select.value = prior;
        else select.selectedIndex = Math.min(index, comparisonCases.length - 1);
      }
      drawDiagrams();
    }

    const inventory = tableBlock("Catalog screening coverage", ["Source inventory", "Indexed reports",
      "Impression leads", "Scorch leads", "Swirl or twist leads", "Any layout lead"]);
    for (const catalog of catalogs.filter(Boolean)) {
      const groups = new Map();
      for (const record of catalog.rows) {
        const label = record.source?.label || catalog.source.shortLabel || catalog.source.label;
        if (!groups.has(label)) groups.set(label, []);
        groups.get(label).push(record);
      }
      for (const [label, records] of groups) {
        const row = inventory.body.insertRow();
        rowHeading(row, label);
        row.insertCell().textContent = number.format(records.length);
        row.insertCell().textContent = number.format(records.filter(({ traces }) => traces.includes("impression")).length);
        row.insertCell().textContent = number.format(records.filter(({ traces }) => traces.includes("scorching")).length);
        row.insertCell().textContent = number.format(records.filter(({ patterns }) => patterns.includes("swirl")).length);
        row.insertCell().textContent = number.format(records.filter(({ patterns }) => patterns.length).length);
      }
    }
    inventory.section.append(el("p", "landing-scope-note",
      "Catalog totals count source records and can overlap across inventories. Keyword and classification leads are displayed separately from reviewed geometry."));
    if (audit) {
      const { counts } = audit;
      inventory.section.append(el("h5", "", "Source review of other reports"), el("p", "landing-scope-note",
        number.format(counts.access.original_reviewed || 0) + " records checked against original reporting, " +
        number.format(counts.access.catalog_reviewed || 0) + " checked against catalog accounts, " +
        number.format(counts.access.citation_only || 0) + " citation-only records and " +
        number.format(counts.access.unresolved || 0) + " unresolved sources. " +
        number.format(counts.linkedRecords) + " records link to " + number.format(counts.linkedCases) +
        " reviewed dossiers. " + number.format(counts.sharedDossiers) + " of those dossiers have multiple inventory records. " +
        number.format(counts.possibleOverlapRecords) + " records have possible same-day locality matches. Those matches do not merge cases."),
      el("p", "landing-scope-note", number.format(counts.geometry.diagram || 0) +
        " records link to supported diagrams, " + number.format(counts.geometry.description || 0) +
        " have descriptive details and " + number.format(counts.geometry.insufficient || 0) +
        " have insufficient geometry. The matrix uses reviewed case dossiers with coded layouts."));
    }
    if (phillipsReviews.length) {
      const originals = phillipsReviews.filter(({ access }) => access === "original_reviewed").length;
      inventory.section.append(el("p", "landing-scope-note",
        number.format(phillipsReviews.length) + " Phillips records have separate source review notes. " +
        number.format(originals) + " were checked against original reporting."));
    }
    pairs.section.append(el("p", "landing-scope-note",
      "Traces in the same dossier can reflect observations made at different times. Ground impressions include possible supports and marks with other explanations."));
    const published = tableBlock("Phillips’s published summary", ["Original chart", "Published percentages"]);
    for (const [label, values] of [
      ["Site outline", "Circular 77% · Oval 14% · Irregular 9%"],
      ["Site condition", "Burned 51% · Depressed 38% · Dehydrated 11%"],
      ["Number of imprints", "Three 38% · Four 15% · Two, five or six 47%"],
    ]) {
      const row = published.body.insertRow();
      rowHeading(row, label);
      row.insertCell().textContent = values;
    }
    const chartSource = el("a", "landing-catalog-case-link", "Open Phillips’s original charts");
    chartSource.href = "https://cufos.org/PDFs/books/Physical_Traces.pdf#page=135";
    chartSource.target = "_blank";
    chartSource.rel = "noopener noreferrer";
    published.section.append(el("p", "landing-scope-note",
      "The charts give percentages without sample sizes or a cross-tabulation. These figures are shown separately from this review’s case counts."), chartSource);
    panel.append(filters, scope, matrix.section, details, twists.section, pairs.section,
      dimensions.section, sideBySide, inventory.section, published.section);
    for (const field of [source, evidence, availability, origin]) field.select.addEventListener("change", refresh);
    for (const field of [left, right]) field.select.addEventListener("change", drawDiagrams);
    refresh();
    return panel;
  }

  const api = { analyze, traceLane, render };
  if (typeof module === "object" && module.exports) module.exports = api;
  root.UfoLandingSiteComparison = api;
})(globalThis);
