(function (root) {
  "use strict";

  const traceKinds = [
    { id: "impression", label: "Ground impressions", short: "Impressions" },
    { id: "scorching", label: "Scorching", short: "Scorching" },
    { id: "deformation", label: "Vegetation deformation", short: "Deformation" },
    { id: "surface", label: "Other surface traces", short: "Surface traces" },
  ];

  const patternBases = {
    description: "Reported layout",
    dimensions: "Recorded dimensions",
  };

  const number = new Intl.NumberFormat("en", { maximumFractionDigits: 2 });
  const date = new Intl.DateTimeFormat("en", { dateStyle: "long", timeZone: "UTC" });
  const month = new Intl.DateTimeFormat("en", { month: "long", year: "numeric", timeZone: "UTC" });
  const catalogKinds = {
    sighting_trace: "Sighting and trace reported",
    trace_discovery: "Trace discovery without a sighting",
    insufficient: "Insufficient detail in the catalog",
    unclear: "Category unconfirmed",
  };
  const layoutTerms = {
    circular: "Ring or circle",
    triangular: "Triangle",
    linear: "Line or row",
    rectangular: "Rectangle or square",
    radial: "Radial",
    swirl: "Swirl or twist",
  };
  const reviewAccess = {
    original_reviewed: "Original report reviewed",
    catalog_reviewed: "Catalog account reviewed",
    citation_only: "Citation located",
    unresolved: "Source unresolved",
  };
  const reviewGeometry = {
    diagram: "Diagram supported",
    description: "Description only",
    insufficient: "Geometry insufficient",
  };
  const pageSize = 24;

  function spanMetrics(dimensions) {
    if (!dimensions) return null;
    const { longM, shortM } = dimensions;
    if (!Number.isFinite(longM) || !Number.isFinite(shortM) || shortM <= 0 || longM < shortM) {
      return null;
    }
    return { longM, shortM, aspectRatio: longM / shortM };
  }

  function edgeSpread(edges) {
    if (!Array.isArray(edges) || edges.length < 3 ||
        edges.some((length) => !Number.isFinite(length) || length <= 0)) return null;
    const mean = edges.reduce((sum, length) => sum + length, 0) / edges.length;
    return (Math.max(...edges) - Math.min(...edges)) / mean * 100;
  }

  function casesWithTrace(cases, kind) {
    return kind === "all" ? cases : cases.filter((site) => site.traces.some((trace) => trace.kind === kind));
  }

  function formatDate(value) {
    if (!value) return "Date unconfirmed";
    if (value.length === 4) return value;
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return "Date unconfirmed";
    return value.length === 7 ? month.format(parsed) : date.format(parsed);
  }

  function searchText(value) {
    return value.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
  }

  function filterCatalog(rows, query, kind, trace, layout, access, source, evidence, review, overlap, geometry) {
    const terms = searchText(query).split(" ").filter(Boolean);
    const caseNumber = /^#?\s*\d{1,3}$/.test(query.trim()) ? Number(terms[0]) : null;
    return rows.filter((row) => {
      if (review && row.audit?.access !== review) return false;
      if (geometry && row.audit?.geometry !== geometry) return false;
      if (overlap === "linked" && !row.audit?.caseId) return false;
      if (overlap === "possible" && !row.audit?.possibleMatches?.length) return false;
      if (source && row.source?.key !== source) return false;
      if (evidence && row.evidenceBasis !== evidence) return false;
      if (access === "scan" && !row.page) return false;
      if (access === "citation" && row.page) return false;
      if (kind && row.kind !== kind) return false;
      if (trace && !row.traces.includes(trace)) return false;
      if (layout && !row.patterns.includes(layout)) return false;
      if (caseNumber !== null && typeof row.id === "number") return row.id === caseNumber;
      const searchable = searchText([row.id, row.date, row.location, row.source?.label].join(" "));
      return terms.every((term) => /^\d{1,3}$/.test(term) ?
        searchable.split(" ").includes(term) : searchable.includes(term));
    });
  }

  function renderCatalog(element, catalog, cases, openReviewedCase, isPhillips) {
    const { source, rows } = catalog;
    const panel = element("section", "analysis-card landing-catalog");
    const title = element("h4", "", source.label);
    const sourceLink = element("a", "", isPhillips ? "Open the complete catalog scan" : "Open source documentation");
    sourceLink.href = source.url;
    sourceLink.target = "_blank";
    sourceLink.rel = "noopener noreferrer";
    const linkedPages = rows.filter((row) => row.page).length;
    const citationOnly = rows.length - linkedPages;
    const coverage = element("p", "landing-scope-note", isPhillips ?
      number.format(linkedPages) + " of the " + number.format(source.declaredCount) +
      " reports in the 1975 edition have a recovered scan-page link. The book covers ground traces as well as other physical effects." :
      number.format(rows.length) + " source records. " + (source.methods ||
        "The underlying collections can contain separate accounts of the same event."));
    if (isPhillips && citationOnly) {
      const concordance = element("a", "", "UFOCAT 2023");
      concordance.href = source.referenceIndex?.url || "https://cufos.org/PDFs/UFOCAT%20Codebook%202023.pdf";
      concordance.target = "_blank";
      concordance.rel = "noopener noreferrer";
      coverage.append(" Another " + number.format(citationOnly) + " case numbers come from direct ",
        concordance, " citations with scan pages still unconfirmed.");
    }
    const counts = source.declaredCategories;
    const edition = counts && element("p", "landing-scope-note",
      "Phillips reports " + number.format(counts.sighting_trace) + " sightings with traces, " +
      number.format(counts.trace_discovery) + " trace discoveries without a sighting, and " +
      number.format(counts.insufficient) + " reports with insufficient detail.");
    const guidance = element("p", "landing-scope-note", isPhillips ?
      "Search uses indexed case numbers, dates and places. Category, trace and layout leads are screened from scan text. Check the linked page before treating a tag or location as evidence." :
      "Use the source and record identifier to inspect an entry. Category codes and narrative terms indicate leads for review. Several records may refer to the same event.");
    const filters = element("div", "landing-catalog-filters");
    const search = element("input");
    search.type = "search";
    search.placeholder = isPhillips ? "e.g. Socorro, 1966 or 537" : "e.g. France, 1967 or UFOCAT";
    const searchLabel = element("label", "", isPhillips ? "Search the Phillips catalog" : "Search other landing reports");
    searchLabel.append(search);
    filters.append(searchLabel);

    function addSelect(label, any, choices) {
      const wrapper = element("label", "", label);
      const select = element("select");
      const first = element("option", "", any);
      first.value = "";
      select.append(first);
      for (const [id, name] of choices) {
        const option = element("option", "", name);
        option.value = id;
        select.append(option);
      }
      wrapper.append(select);
      filters.append(wrapper);
      return select;
    }
    const kind = isPhillips && addSelect("Category lead", "All categories", Object.entries(catalogKinds));
    const trace = addSelect("Trace lead", "All trace types", traceKinds.map(({ id, label }) => [id, label]));
    const pattern = addSelect("Layout lead", "All layouts", Object.entries(layoutTerms));
    const access = isPhillips && addSelect("Source access", "All indexed records",
      [["scan", "Scan page linked"], ["citation", "UFOCAT citation only"]]);
    const sourceOptions = new Map(rows.filter((row) => row.source?.key).map((row) =>
      [row.source.key, row.source.key === "specialist" ? "Historical compilations" : row.source.label]));
    const catalogSource = !isPhillips && addSelect("Source collection", "All collections", [...sourceOptions]);
    const screeningLabels = {
      described_trace: "Trace language in source",
      classification_only: "Classification code",
      catalog_only: "Catalog entry",
    };
    const evidence = !isPhillips && addSelect("Screening basis", "All screening bases", Object.entries(screeningLabels));
    const reviewedAccess = !isPhillips && addSelect("Source review", "All review outcomes", Object.entries(reviewAccess));
    const geometry = !isPhillips && addSelect("Geometry review", "All geometry outcomes", Object.entries(reviewGeometry));
    const overlap = !isPhillips && addSelect("Case linkage", "All report records",
      [["linked", "Linked to reviewed case"], ["possible", "Possible same-day overlap"]]);
    const pager = element("div", "landing-catalog-pager");
    const status = element("p");
    status.setAttribute("role", "status");
    const previous = element("button", "secondary-button", "Previous");
    const next = element("button", "secondary-button", "Next");
    previous.type = next.type = "button";
    pager.append(status, previous, next);
    const scroll = element("div", "landing-catalog-scroll");
    scroll.tabIndex = 0;
    scroll.setAttribute("role", "region");
    scroll.setAttribute("aria-label", isPhillips ? "Phillips catalog results" : "Other landing report results");
    const table = element("table", "landing-layout-table landing-catalog-table");
    const head = table.createTHead().insertRow();
    for (const label of [isPhillips ? "Case and source page" : "Record and source", "Date and location",
      isPhillips ? "Category lead" : "Source and overlap review", "Trace and layout leads"]) {
      const cell = element("th", "", label);
      cell.scope = "col";
      head.append(cell);
    }
    const body = table.createTBody();
    scroll.append(table);
    const reviewed = new Map(cases.filter((site) => site.phillipsCaseNumber).map((site) => [site.phillipsCaseNumber, site.id]));
    let matches = rows;
    let pageIndex = 0;

    function paint() {
      body.replaceChildren();
      const start = pageIndex * pageSize;
      const page = matches.slice(start, start + pageSize);
      status.textContent = matches.length ?
        "Showing " + number.format(start + 1) + "–" + number.format(start + page.length) +
          " of " + number.format(matches.length) + " records" : "No catalog records match these filters.";
      scroll.hidden = !matches.length;
      previous.disabled = pageIndex === 0;
      next.disabled = start + pageSize >= matches.length;
      for (const record of page) {
        const row = body.insertRow();
        const ref = element("th");
        ref.scope = "row";
        const caseLabel = "Case " + record.id;
        if (!isPhillips && record.source) {
          const link = element("a", "", record.source.label);
          link.href = record.source.url;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          ref.append(link, element("div", "", record.source.locator || record.id));
        } else if (record.page) {
          const link = element("a", "", caseLabel + " · PDF p. " + record.page);
          link.href = source.url + "#page=" + record.page;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          ref.append(link);
        } else {
          ref.textContent = caseLabel + " · UFOCAT citation, page unconfirmed";
        }
        const dossierId = reviewed.get(record.id) || record.audit?.caseId;
        if (dossierId) {
          const details = element("button", "landing-catalog-case-link", "View case details");
          details.type = "button";
          details.addEventListener("click", () => openReviewedCase(dossierId));
          ref.append(details);
        }
        row.append(ref);
        const where = row.insertCell();
        where.append(element("strong", "", record.location || "Location unconfirmed"), element("div", "", formatDate(record.date)));
        const screen = row.insertCell();
        const audit = record.audit;
        screen.textContent = isPhillips ? catalogKinds[record.kind] :
          audit ? reviewAccess[audit.access] + " · " + reviewGeometry[audit.geometry] : screeningLabels[record.evidenceBasis];
        if (audit) {
          const detail = element("details", "landing-report-audit");
          detail.append(element("summary", "", "Review notes"));
          if (audit.url) {
            const link = element("a", "", audit.locator || "Open checked source");
            link.href = audit.url;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            detail.append(link);
          }
          if (audit.note) detail.append(element("p", "", audit.note));
          if (audit.sharedCaseRecords) detail.append(element("p", "",
            audit.sharedCaseRecords + " inventory records link to the same reviewed dossier."));
          if (audit.possibleMatches?.length) detail.append(element("p", "",
            "Same reported day and locality candidates: " + audit.possibleMatches.join(", ") + "."));
          screen.append(detail);
        }
        const leads = [...record.traces.map((id) => traceKinds.find((entry) => entry.id === id)?.short),
          ...record.patterns.map((id) => layoutTerms[id])].filter(Boolean);
        const media = (record.media || []).map((id) => id === "sketch" ? "Sketch mentioned" : "Photo mentioned");
        row.insertCell().textContent = [...leads, ...media].join(" · ") || "No indexed lead";
      }
    }

    function applyFilters() {
      matches = filterCatalog(rows, search.value, kind?.value, trace.value, pattern.value, access?.value,
        catalogSource?.value, evidence?.value, reviewedAccess?.value, overlap?.value, geometry?.value);
      pageIndex = 0;
      paint();
    }
    search.addEventListener("input", applyFilters);
    for (const select of [kind, trace, pattern, access, catalogSource, evidence, reviewedAccess, overlap, geometry].filter(Boolean)) {
      select.addEventListener("change", applyFilters);
    }
    previous.addEventListener("click", () => { pageIndex -= 1; paint(); });
    next.addEventListener("click", () => { pageIndex += 1; paint(); });
    panel.append(title);
    if (source.url) panel.append(sourceLink);
    panel.append(coverage);
    if (edition) panel.append(edition);
    panel.append(guidance, filters, pager, scroll);
    paint();
    return panel;
  }

  function mount(container, cases, catalog, otherCatalogs) {
    if (container.dataset.mounted) return;
    container.dataset.mounted = "true";
    const document = container.ownerDocument;

    function element(tag, className, label) {
      const node = document.createElement(tag);
      if (className) node.className = className;
      if (label != null) node.textContent = label;
      return node;
    }

    if (!Array.isArray(cases) || !cases.length) {
      container.replaceChildren(element("p", "analysis-card", "The landing-site case register is unavailable."));
      return;
    }

    function sourceLink(source) {
      const link = element("a", "", source.locator ? source.label + " · " + source.locator : source.label);
      link.href = source.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      return link;
    }

    function renderPattern(pattern) {
      const box = element("div", "landing-pattern");
      if (!pattern) {
        box.append(element("strong", "", "Layout undocumented"),
          element("p", "", "The reviewed record gives too little spatial detail to assess symmetry."));
        return box;
      }
      box.append(element("span", "landing-basis", patternBases[pattern.basis]),
        element("strong", "", pattern.label), element("p", "", pattern.details));

      function renderLengths(lengths) {
        const comparison = element("div", "landing-span-comparison");
        const max = Math.max(...lengths.map(([, metres]) => metres));
        for (const [label, metres] of lengths) {
          const row = element("div", "landing-span-row");
          const bar = element("meter");
          bar.min = 0;
          bar.max = max;
          bar.value = metres;
          bar.setAttribute("aria-label", label + " in metres");
          row.append(element("span", "", label), bar, element("strong", "", number.format(metres) + " m"));
          comparison.append(row);
        }
        box.append(comparison);
      }

      const span = spanMetrics(pattern.dimensions);
      if (span) {
        renderLengths([["Long span", span.longM], ["Short span", span.shortM]]);
        box.append(element("p", "landing-metric",
          "Long-to-short span ratio " + number.format(span.aspectRatio) + " : 1"));
      }

      const spread = edgeSpread(pattern.edgesM);
      if (spread !== null) {
        const edgeLabel = pattern.edgeLabel || "Side";
        renderLengths(pattern.edgesM.map((length, index) => [edgeLabel + " " + (index + 1), length]));
        box.append(element("p", "landing-metric", edgeLabel + " length spread " +
          number.format(spread) + "% of the mean"));
        if (pattern.edgesM.length === 4) {
          const [a, b, c, d] = pattern.edgesM;
          box.append(element("p", "landing-metric", "Opposite sides differ by " +
            number.format(Math.abs(a - c)) + " m and " + number.format(Math.abs(b - d)) +
            " m. A half-turn would pair sides of equal length."));
        }
      }
      return box;
    }

    function renderTrace(trace, sourceById) {
      const card = element("article", "landing-trace");
      card.dataset.traceKind = trace.kind;
      const kind = traceKinds.find(({ id }) => id === trace.kind);
      card.append(element("h5", "", kind.label), element("p", "", trace.observation));
      if (trace.context) card.append(element("p", "landing-trace-context", trace.context));
      card.append(renderPattern(trace.pattern));
      const refs = element("ul", "landing-sources");
      for (const id of trace.sourceIds) {
        const source = sourceById.get(id);
        if (!source) continue;
        const item = element("li");
        item.append(sourceLink(source));
        refs.append(item);
      }
      card.append(refs);
      return card;
    }

    const toolbar = element("div", "landing-toolbar");
    const filter = element("select");
    const caseSelect = element("select");
    const diagramFilter = element("input");
    diagramFilter.type = "checkbox";
    const filterLabel = element("label", "", "Find cases with");
    const caseLabel = element("label", "", "Inspect a case");
    const diagramLabel = element("label", "landing-diagram-filter");
    diagramLabel.append(diagramFilter, document.createTextNode("Cases with site diagrams"));
    filterLabel.append(filter);
    caseLabel.append(caseSelect);
    toolbar.append(filterLabel, caseLabel, diagramLabel);
    for (const { id, label } of [{ id: "all", label: "Any trace type" }, ...traceKinds]) {
      const count = casesWithTrace(cases, id).length;
      const option = element("option", "", label + " (" + count + ")");
      option.value = id;
      option.disabled = count === 0;
      filter.append(option);
    }

    const stats = element("dl", "landing-stats");
    for (const { id, short } of [{ id: "all", short: "Reviewed cases" }, ...traceKinds]) {
      const metric = element("div", "analysis-summary-card");
      metric.append(element("dt", "", short), element("dd", "", casesWithTrace(cases, id).length));
      stats.append(metric);
    }

    const casePanel = element("article", "analysis-card landing-case");
    casePanel.setAttribute("aria-labelledby", "landing-case-title");
    const selectionStatus = element("p", "sr-only");
    selectionStatus.setAttribute("role", "status");
    const comparison = element("details", "analysis-methodology landing-methods");
    const comparisonBody = element("div", "analysis-methodology-body");
    const layoutTable = element("table", "landing-layout-table");
    const header = layoutTable.createTHead().insertRow();
    for (const label of ["Case", "Trace", "Layout", "Evidence"]) {
      const heading = element("th", "", label);
      heading.scope = "col";
      header.append(heading);
    }
    const layouts = layoutTable.createTBody();
    comparisonBody.append(layoutTable);
    comparison.append(element("summary", "", "Compare layouts across cases"), comparisonBody);

    function renderCase() {
      const site = cases.find((candidate) => candidate.id === caseSelect.value);
      if (!site) {
        casePanel.hidden = true;
        selectionStatus.textContent = "No matching cases.";
        return;
      }
      const title = element("h4", "", site.title);
      title.id = "landing-case-title";
      const meta = element("p", "landing-case-meta", formatDate(site.date) + " · " + site.location);
      const traces = element("div", "landing-traces");
      const sourceById = new Map(site.sources.map((source) => [source.id, source]));
      traces.append(...site.traces.map((trace) => renderTrace(trace, sourceById)));
      const diagram = root.UfoLandingSiteDiagrams?.render(document, site.diagram, (id) => {
        const source = sourceById.get(id);
        return source && sourceLink(source);
      });
      const limits = element("div", "landing-limits");
      limits.append(element("h5", "", "Evidence limits"), element("p", "", site.limits));
      if (site.controls) limits.append(element("h5", "", "Comparison samples and controls"),
        element("p", "", site.controls));
      casePanel.replaceChildren(meta, title, element("p", "", site.summary), traces, limits);
      if (site.evidenceOrigin) traces.before(element("p", "landing-scope-note",
        site.evidenceOrigin === "original" ? "Reviewed against original reporting." : "Reviewed against a compiled account."));
      if (diagram) traces.before(diagram);
      casePanel.hidden = false;
      selectionStatus.textContent = "Showing " + site.title + ".";
    }

    function applyFilter() {
      const previous = caseSelect.value;
      const matchingCases = casesWithTrace(cases, filter.value);
      const matches = diagramFilter.checked ? matchingCases.filter((site) => site.diagram) : matchingCases;
      caseSelect.replaceChildren(...matches.map((site) => {
        const option = element("option", "", site.title);
        option.value = site.id;
        return option;
      }));
      caseSelect.disabled = matches.length === 0;
      if (matches.some((site) => site.id === previous)) caseSelect.value = previous;
      layouts.replaceChildren();
      for (const site of matches) {
        for (const trace of site.traces) {
          if (filter.value !== "all" && trace.kind !== filter.value) continue;
          const row = layouts.insertRow();
          const name = element("th", "", site.title);
          name.scope = "row";
          row.append(name);
          row.insertCell().textContent = traceKinds.find(({ id }) => id === trace.kind).short;
          row.insertCell().textContent = trace.pattern?.label || "Layout undocumented";
          row.insertCell().textContent = patternBases[trace.pattern?.basis] || "Insufficient spatial detail";
        }
      }
      renderCase();
      empty.hidden = matches.length > 0;
    }

    const methods = element("details", "analysis-methodology landing-methods");
    const methodBody = element("div", "analysis-methodology-body");
    methodBody.append(
      element("p", "", "Ground impressions are evaluated as possible contact traces. Scorching, plant flattening or twisting, and other surface changes are tracked in separate groups, even when they occur at the same site."),
      element("p", "", "A reported shape suggests a pattern to test. Where two comparable spans are available, their ratio describes elongation. For measured sides, the difference between the longest and shortest is expressed as a percentage of the mean side length. Testing rotational or mirror symmetry more fully requires positions or angles."),
      element("p", "", "Diagrams use source sketches, documented bearings or reported dimensions. Their captions state the basis and limits. Toggle the trace layers to compare them in the same local frame."),
      element("p", "", "These comparisons are descriptive. A test of symmetry needs measurement uncertainty, and a test of multiple sources needs positions for each kind of trace in the same site plan. Assessing heat or RF as a cause would require mechanism-specific evidence and suitable controls.")
    );
    methods.append(element("summary", "", "How symmetry and evidence are assessed"), methodBody);
    const empty = element("p", "analysis-card", "No cases match these filters.");
    const reviewPanel = element("section", "landing-review");
    reviewPanel.append(stats, element("p", "landing-scope-note",
      "Cases can appear in several trace categories. The filter finds cases with a trace type and keeps every documented trace visible in the selected case."),
    toolbar, selectionStatus, empty, casePanel, comparison, methods);
    filter.addEventListener("change", applyFilter);
    diagramFilter.addEventListener("change", applyFilter);
    caseSelect.addEventListener("change", renderCase);
    applyFilter();
    const modes = element("div", "landing-mode-switch");
    modes.setAttribute("role", "group");
    modes.setAttribute("aria-label", "Landing Sites views");
    const views = [];
    function openReviewedCase(id) {
      filter.value = "all";
      diagramFilter.checked = false;
      applyFilter();
      caseSelect.value = id;
      renderCase();
      setMode("review");
      caseSelect.focus();
    }
    function addView(id, label, panel) {
      const button = element("button", "secondary-button", label);
      button.type = "button";
      button.addEventListener("click", () => setMode(id));
      modes.append(button);
      views.push({ id, button, panel });
    }
    function setMode(id) {
      for (const view of views) {
        view.panel.hidden = view.id !== id;
        view.button.setAttribute("aria-pressed", String(view.id === id));
      }
    }
    if (root.UfoLandingSiteComparison) {
      addView("combined", "Combined analysis", root.UfoLandingSiteComparison.render(
        document, cases, [catalog, ...otherCatalogs], openReviewedCase,
        { edgeSpread, spanMetrics }, root.UfoLandingSiteReviewAudit));
    }
    if (catalog?.rows?.length) addView("phillips", "Phillips catalog (" + number.format(catalog.rows.length) + ")",
      renderCatalog(element, catalog, cases, openReviewedCase, true));
    const sourceReviews = root.UfoLandingSiteReviewAudit?.records || {};
    const otherRows = otherCatalogs.flatMap(({ rows }) => rows.map((row) => ({ ...row, audit: sourceReviews[row.id] })));
    if (otherRows.length) {
      const otherCatalog = { source: { label: "Other landing and trace inventories",
        methods: "Browse the additional catalogs by source. Each record shows its own source and screening basis." }, rows: otherRows };
      addView("other", "Other landing reports (" + number.format(otherRows.length) + ")",
        renderCatalog(element, otherCatalog, cases, openReviewedCase, false));
    }
    addView("review", "Case details & diagrams (" + number.format(cases.length) + ")", reviewPanel);
    container.replaceChildren(modes, ...views.map((view) => view.panel));
    setMode(views[0].id);
  }

  if (typeof module === "object" && module.exports) {
    module.exports = { spanMetrics, edgeSpread, casesWithTrace, filterCatalog };
  }
  if (root.document) {
    const container = root.document.getElementById("analysis-landing-sites");
    if (container) {
      const cases = [...(root.UfoLandingSiteCases || []), ...(root.UfoLandingSiteExpandedCases || []),
        ...(root.UfoLandingSitePhillipsEarlyCases || []), ...(root.UfoLandingSitePhillipsLateCases || []),
        ...(root.UfoLandingSiteDirectReviewedCases || []), ...(root.UfoLandingSiteAustralianReviewedCases || []),
        ...(root.UfoLandingSiteHistoricalReviewedCases || []), ...(root.UfoLandingSiteUfocatReviewedCases || [])];
      cases.sort((a, b) => a.date.localeCompare(b.date));
      mount(container, cases, root.UfoLandingSitePhillipsCatalog,
        [root.UfoLandingSiteOtherCatalog, root.UfoLandingSiteAustralianCatalog].filter(Boolean));
    }
  }
})(globalThis);
