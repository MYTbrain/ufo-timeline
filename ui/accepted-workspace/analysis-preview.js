/* Local whole-site review. Uses the existing Analysis DOM, state and handlers. */
(function () {
  "use strict";

  const shortcuts = {
    time: [
      ["Reporting delay", "analysis-reporting-delay-chart"],
      ["Observation duration", "analysis-duration-chart"],
      ["Time of day", "analysis-time-of-day-chart"],
      ["Month & craft", "analysis-month-year-chart"],
    ],
    craft: [
      ["Craft by era", "analysis-craft-era-chart"],
      ["Classification confidence", "analysis-craft-confidence-chart"],
      ["Reported colors", "analysis-color-chart"],
    ],
    geography: [
      ["Geography by era", "analysis-geography-time-chart"],
      ["Equal-area sensitivity", "analysis-geography-sensitivity-chart"],
    ],
    spatial: [
      ["Co-occurrence matrix", "analysis-cooccurrence-chart"],
      ["Coordinate quality", "analysis-coordinate-evidence-spatial-chart"],
      ["Context neighborhoods", "analysis-context-neighborhood-chart"],
    ],
    crops: [
      ["Formation & source fields", "analysis-crop-morphology-chart"],
      ["Locations & coverage", "analysis-crop-coverage-chart"],
      ["Nearby report context", "analysis-crop-spatial-chart"],
    ],
    animals: [
      ["Species & review status", "analysis-animal-species-chart"],
      ["Dates & coverage", "analysis-animal-coverage-chart"],
      ["Public-marker evidence", "analysis-animal-spatial-chart"],
    ],
    "sources-quality": [
      ["Source mix over time", "analysis-source-time-chart"],
      ["Witness counts", "analysis-witness-count-chart"],
      ["Coordinate provenance", "analysis-coordinate-evidence-chart"],
      ["Coverage & event types", "analysis-quality-missingness-chart"],
      ["Classifier audit", "analysis-quality-audit-chart"],
    ],
  };

  const number = new Intl.NumberFormat();
  const byId = (id) => document.getElementById(id);

  function setText(element, value) {
    if (element && element.textContent !== value) element.textContent = value;
  }

  function signature(snapshot) {
    if (!snapshot) return "";
    const context = snapshot.contextLayers || {};
    return JSON.stringify({
      baseline: snapshot.baselineMode,
      dates: snapshot.timeRange,
      filters: snapshot.filters,
      area: snapshot.areaFilter,
      crops: !!(context.crops && context.crops.enabled),
      animals: !!(context.animals && context.animals.enabled),
    });
  }

  function revealExistingChart(chartId) {
    const chart = byId(chartId);
    if (!chart) return;
    const disclosures = [];
    for (let node = chart.parentElement; node && node.id !== "analysis-panel"; node = node.parentElement) {
      if (node.tagName === "DETAILS") disclosures.unshift(node);
    }
    disclosures.forEach((details) => { details.open = true; });
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      chart.scrollIntoView({ block: "center", behavior: reducedMotion ? "auto" : "smooth" });
      chart.setAttribute("tabindex", "-1");
      chart.focus({ preventScroll: true });
    }));
  }

  function install() {
    const panel = byId("analysis-panel");
    if (!panel || byId("preview-analysis-cohort")) return;
    document.documentElement.classList.add("faithful-polish-preview");

    const header = panel.querySelector(".analysis-header");
    const actions = panel.querySelector(".analysis-header-actions");
    const scope = byId("analysis-scope-summary");
    if (scope) {
      const about = document.createElement("details");
      about.className = "preview-analysis-purpose";
      const summary = document.createElement("summary");
      summary.textContent = "About these patterns";
      scope.before(about);
      about.appendChild(summary);
      about.appendChild(scope);
    }
    if (header && actions) {
      const utilities = document.createElement("details");
      utilities.className = "preview-analysis-utilities";
      const summary = document.createElement("summary");
      summary.textContent = "Context & downloads";
      utilities.appendChild(summary);
      utilities.appendChild(actions);
      header.appendChild(utilities);
    }

    const cohort = document.createElement("p");
    cohort.id = "preview-analysis-cohort";
    cohort.className = "preview-analysis-cohort";
    cohort.setAttribute("role", "status");
    cohort.setAttribute("aria-live", "polite");
    const toolbar = byId("analysis-workspace-toolbar");
    if (toolbar) toolbar.insertAdjacentElement("afterend", cohort);
    const sectionNav = byId("analysis-section-nav");
    let sectionSelect = null;
    if (sectionNav) {
      const field = document.createElement("label");
      field.className = "preview-analysis-section-picker";
      const label = document.createElement("span");
      label.textContent = "Explore";
      field.appendChild(label);
      sectionSelect = document.createElement("select");
      sectionSelect.setAttribute("aria-label", "Analysis section");
      sectionNav.querySelectorAll("[role=tab]").forEach((tab) => {
        const option = document.createElement("option");
        option.value = tab.id;
        option.textContent = tab.textContent;
        sectionSelect.appendChild(option);
      });
      sectionSelect.addEventListener("change", () => {
        const tab = byId(sectionSelect.value);
        if (tab) tab.click();
        sectionSelect.focus({preventScroll:true});
      });
      field.appendChild(sectionSelect);
      sectionNav.before(field);
    }
    const overview = byId("analysis-section-overview");
    const briefing = overview && overview.querySelector(".analysis-visual-briefing");
    const counts = byId("analysis-cohort-banner");
    if (briefing && counts && briefing.parentElement === counts.parentElement) {
      briefing.after(counts);
      const pathwayNote = counts.querySelector(".analysis-card-note");
      if (pathwayNote) pathwayNote.textContent = "The visual briefing shows pathway percentages. Open these details for exact record counts retained at each gate.";
    }

    Object.entries(shortcuts).forEach(([key, entries]) => {
      const section = byId("analysis-section-" + key);
      if (!section) return;
      const navigation = document.createElement("nav");
      navigation.className = "preview-analysis-shortcuts";
      navigation.setAttribute("aria-label", key.replace(/-/g, " ") + " evidence shortcuts");
      const label = document.createElement("span");
      label.textContent = "Also explore:";
      navigation.appendChild(label);
      entries.forEach(([title, chartId]) => {
        if (!byId(chartId)) return;
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = title;
        button.setAttribute("aria-controls", chartId);
        button.addEventListener("click", () => revealExistingChart(chartId));
        navigation.appendChild(button);
      });
      const heading = section.querySelector(".analysis-section-heading");
      if (heading) heading.insertAdjacentElement("afterend", navigation);
    });

    function updateExplanation() {
      if (sectionSelect && sectionNav) {
        const activeTab = sectionNav.querySelector("[aria-selected=true]");
        if (activeTab && sectionSelect.value !== activeTab.id) sectionSelect.value = activeTab.id;
      }
      const controller = window.AnalysisViewController;
      const result = controller && controller.latestResult;
      const accepted = controller && controller.latestMeta && controller.latestMeta.filterSnapshot;
      let current = null;
      try {
        if (typeof window.getAnalysisFilterSnapshot === "function") current = window.getAnalysisFilterSnapshot();
      } catch (_error) { /* Native Analysis states remain visible if no snapshot is available. */ }
      const snapshot = accepted || current;
      if (!result || !snapshot) {
        setText(cohort, "Uses the map's dates, source and craft filters, precision settings, and selected area. Chart selections let you review changes before applying them.");
        return;
      }
      const time = snapshot.timeRange || {};
      const filters = snapshot.filters || {};
      const summary = result.summary || {};
      const parts = [];
      if (Number.isFinite(Number(summary.activeCount))) parts.push(number.format(summary.activeCount) + " reports");
      if (Number.isFinite(Number(summary.mappedCount)) && Number.isFinite(Number(summary.unmappedCount))) {
        parts.push(number.format(summary.mappedCount) + " mapped / " + number.format(summary.unmappedCount) + " unmapped");
      }
      parts.push(time.mode === "full" ? "All time" : [time.startIso, time.endIso].filter(Boolean).join(" to "));
      if (filters.keyword) parts.push('Search: "' + filters.keyword + '"');
      if (filters.sourceMode === "all") parts.push("All sources");
      else if (Array.isArray(filters.selectedSources)) parts.push(number.format(filters.selectedSources.length) + " selected sources");
      if (filters.legendEventMode && filters.legendEventMode !== "all" && Array.isArray(filters.selectedLegendEventKeys)) {
        parts.push(number.format(filters.selectedLegendEventKeys.length) + " legend categories");
      }
      if (snapshot.areaFilter && snapshot.areaFilter.active) parts.push("Selected area · report points only");
      if (filters.hideNonExactDates) parts.push("Exact dates only");
      if (filters.hideLowPrecision) parts.push("Low-precision locations hidden");
      const updating = !!accepted && !!current && signature(accepted) !== signature(current);
      cohort.dataset.updating = String(updating);
      setText(cohort, (updating ? "Updating filters. Currently displayed cohort: " : "Current cohort: ") + parts.filter(Boolean).join(" · ") + ".");

      // Label deferred chart preparation honestly, without inserting chart data or changing gates.
      const geography = result.geography || {};
      const geographyChart = byId("analysis-geography-grid-chart");
      const geographyPlaceholder = geographyChart && geographyChart.querySelector(".analysis-chart-empty");
      if (geographyPlaceholder && (geography.inferenceDeferred || geography.status === "not_requested")) {
        setText(geographyPlaceholder, result.geographyProjection && result.geographyProjection.loaded
          ? "Country assignments are loaded. Preparing this dashboard's descriptive and adjusted evidence…"
          : "Country assignments are loading. The map and shared filters remain available.");
      }
      const geographyStatus = byId("analysis-geography-status") || panel.querySelector(".analysis-geography-status");
      if (geographyStatus && geographyPlaceholder && (geography.inferenceDeferred || geography.status === "not_requested") && geographyStatus.textContent === "Country geography ready.") {
        setText(geographyStatus, "Country assignments loaded · chart preparation continues.");
      }
    }

    let scheduled = false;
    function scheduleExplanation() {
      if (scheduled) return;
      scheduled = true;
      requestAnimationFrame(() => {
        scheduled = false;
        updateExplanation();
      });
    }
    new MutationObserver(scheduleExplanation).observe(panel, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["hidden", "aria-hidden", "aria-selected", "data-phase"],
    });
    document.addEventListener("change", scheduleExplanation, true);
    document.addEventListener("input", scheduleExplanation, true);
    updateExplanation();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", install, { once: true });
  else install();
})();
