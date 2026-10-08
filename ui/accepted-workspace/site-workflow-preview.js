/* Local workflow preview. Existing app controls remain the authority for state. */
(function () {
  "use strict";
  if (window.UfoSiteWorkflowPreview) return;

  const byId = function (id) { return document.getElementById(id); };
  let refreshTimer = null;
  let savedPanelLayout = null;
  let restoringPanels = false;
  const panels = [
    { key: "filters", root: "filters-pane-shell", toggle: "toggle-filters-pane", expand: "expand-filters-pane" },
    { key: "results", root: "results-pane-shell", toggle: "toggle-results-pane", expand: "expand-results-pane" },
    { key: "detail", root: "detail-stage", toggle: "toggle-detail-panel" },
  ];

  function setText(element, value) {
    if (element && element.textContent !== value) element.textContent = value;
  }

  function caption(id, parent, before) {
    if (!parent) return null;
    let element = byId(id);
    if (!element) {
      element = document.createElement("p");
      element.id = id;
      element.className = "workflow-scope-caption";
      parent.insertBefore(element, before || null);
    }
    return element;
  }

  function selectedLabel(element, fallback) {
    return element && element.selectedOptions && element.selectedOptions[0]
      ? element.selectedOptions[0].textContent.trim() : fallback;
  }

  function filterSummary(mode, selected, noun) {
    if (mode === "all") return "all " + noun;
    if (mode === "none") return "no " + noun;
    return (Array.isArray(selected) ? selected.length : 0) + " " + noun + " selected";
  }

  function currentSnapshot() {
    try {
      return typeof window.getAnalysisFilterSnapshot === "function"
        ? window.getAnalysisFilterSnapshot() : null;
    } catch (_) { return null; }
  }

  function contextScope(name, buttonId) {
    const button = byId(buttonId);
    if (!button || button.getAttribute("aria-pressed") !== "true") return name + ": off";
    return name + ": " + (button.dataset.state === "all" ? "all time" : "report window");
  }

  function refreshScopeCaptions() {
    const snapshot = currentSnapshot();
    const reportCaption = byId("workflow-report-scope");
    if (snapshot && snapshot.timeRange) {
      const range = snapshot.timeRange;
      const dates = range.mode === "full" ? "All time"
        : (range.startIso || "Start unset") + " – " + (range.endIso || "End unset");
      const filters = snapshot.filters || {};
      const active = [];
      if (filters.keyword) active.push("text search");
      if (filters.sourceMode && filters.sourceMode !== "all") {
        active.push(filterSummary(filters.sourceMode, filters.selectedSources, "sources"));
      }
      if (filters.typeMode && filters.typeMode !== "all") {
        active.push(filterSummary(filters.typeMode, filters.selectedTypes, "recorded types"));
      }
      if (filters.hideNonExactDates) active.push("exact dates");
      if (filters.hideLowPrecision) active.push("low-precision places hidden");
      if (snapshot.areaFilter && snapshot.areaFilter.active) active.push("area selected");
      setText(reportCaption, "Report window: " + dates + (active.length ? " · " + active.join(" · ") : " · all report filters"));
      if (reportCaption) reportCaption.title = [
        "Committed report dates; partial date edits do not change this scope.",
        filterSummary(filters.sourceMode, filters.selectedSources, "sources"),
        filterSummary(filters.typeMode, filters.selectedTypes, "recorded types"),
        filters.hideNonExactDates ? "Exact dates only" : "Non-exact dates included",
        filters.hideLowPrecision ? "Low-precision locations hidden" : "Low-precision locations included",
        snapshot.areaFilter && snapshot.areaFilter.active ? "An area filter is active" : "No area filter",
        filters.keyword ? "Report text search is active" : "No report text search",
      ].join(" · ");
    } else {
      setText(reportCaption, "Report window and current filters apply to report results.");
    }

    setText(byId("workflow-context-scope"),
      contextScope("Crops", "cluster-quick-crop-circles") + " · " +
      contextScope("Animal reports", "cluster-quick-animal-mutilations"));
    const contextCaption = byId("workflow-context-scope");
    if (contextCaption) contextCaption.title =
      "Context layers have their own date scopes. All time leaves the UFO report window unchanged; evidence filters still apply.";

    const convergenceEnabled = Boolean(byId("trace-intersection-enabled") && byId("trace-intersection-enabled").checked);
    const convergence = byId("workflow-convergence-scope");
    if (convergence) {
      convergence.hidden = !convergenceEnabled;
      setText(convergence, "Convergence scope: " + selectedLabel(byId("trace-intersection-time-scope"), "its selected time scope"));
    }
    const stamp = byId("workflow-convergence-stamp");
    if (stamp) {
      stamp.hidden = !convergenceEnabled;
      const scope = byId("trace-intersection-time-scope");
      setText(stamp, scope && scope.value === "all_time" ? "All catalog years" : selectedLabel(scope, "Own time scope"));
    }
    syncFocusButton();
  }

  function scheduleRefresh() {
    if (refreshTimer !== null) return;
    refreshTimer = window.setTimeout(function () {
      refreshTimer = null;
      refreshScopeCaptions();
    }, 120);
  }

  function panelLayout() {
    const layout = {};
    panels.forEach(function (panel) {
      const root = byId(panel.root);
      if (root) layout[panel.key] = root.classList.contains("is-collapsed");
    });
    return layout;
  }

  function setPanelCollapsed(panel, collapsed) {
    const root = byId(panel.root);
    if (!root || root.classList.contains("is-collapsed") === collapsed) return;
    const button = !collapsed && panel.expand ? byId(panel.expand) : byId(panel.toggle);
    if (button) button.click();
  }

  function syncFocusButton() {
    const original = byId("focus-map-toggle");
    const exposed = byId("workflow-focus-map");
    if (!original || !exposed) return;
    const active = original.getAttribute("aria-pressed") === "true";
    exposed.setAttribute("aria-pressed", active ? "true" : "false");
    setText(exposed, active ? "Restore panels" : "Focus map");
    exposed.title = active && savedPanelLayout
      ? "Restore the panel arrangement used before Focus Map."
      : "Give the map more room by collapsing Filters, Results and Full Event View.";
  }

  function installFocusMap() {
    const original = byId("focus-map-toggle");
    const heading = document.querySelector("#map-control-cluster .map-control-cluster-heading");
    if (!original || !heading) return;
    heading.classList.add("workflow-map-tools-heading");
    heading.hidden = false;
    heading.removeAttribute("aria-hidden");
    const exposed = document.createElement("button");
    exposed.id = "workflow-focus-map";
    exposed.type = "button";
    exposed.className = "secondary-button workflow-small-action";
    exposed.setAttribute("aria-controls", "filters-pane-shell results-pane-shell detail-stage");
    exposed.addEventListener("click", function () { original.click(); syncFocusButton(); });
    heading.appendChild(exposed);

    // Capture before the existing handler runs, then restore through its controls.
    original.addEventListener("click", function () {
      if (restoringPanels) return;
      if (original.getAttribute("aria-pressed") !== "true") {
        savedPanelLayout = panelLayout();
        queueMicrotask(syncFocusButton);
      } else if (savedPanelLayout) {
        const previous = savedPanelLayout;
        savedPanelLayout = null;
        queueMicrotask(function () {
          restoringPanels = true;
          try {
            panels.forEach(function (panel) {
              if (Object.prototype.hasOwnProperty.call(previous, panel.key)) {
                setPanelCollapsed(panel, previous[panel.key]);
              }
            });
          } finally { restoringPanels = false; }
          syncFocusButton();
        });
      }
    }, true);
    new MutationObserver(syncFocusButton).observe(original, { attributes: true, attributeFilter: ["aria-pressed"] });
    syncFocusButton();
  }

  function showMap() {
    const tab = byId("view-tab-map");
    if (tab && tab.getAttribute("aria-selected") !== "true") tab.click();
  }

  function focusTarget(target) {
    if (!target) return;
    target.scrollIntoView({ block: "nearest", behavior: "auto" });
    if (typeof target.focus === "function") target.focus({ preventScroll: true });
  }

  function installBackToResults() {
    const actions = document.querySelector("#detail-stage .panel-header-actions");
    if (!actions) return;
    const button = document.createElement("button");
    button.id = "workflow-back-to-results";
    button.type = "button";
    button.className = "secondary-button workflow-small-action";
    button.textContent = "Back to Results";
    button.title = "Keep this record available and return to the Results list.";
    button.addEventListener("click", function () {
      showMap();
      setPanelCollapsed(panels[1], false);
      setPanelCollapsed(panels[2], true);
      window.requestAnimationFrame(function () {
        const target = document.querySelector("#result-list .result-card.is-active .result-card-button") || byId("results-sort");
        focusTarget(target);
      });
    });
    actions.insertBefore(button, actions.firstChild);
  }

  function installHelpShortcuts() {
    const guide = byId("user-guide-body");
    if (!guide) return;
    const shortcuts = document.createElement("nav");
    shortcuts.className = "workflow-help-shortcuts";
    shortcuts.setAttribute("aria-label", "Jump to exploration controls");
    const tasks = [
      { label: "Famous cases", target: "filter-famous-cases", primary: true },
      { label: "Area selection", section: "map-control-section-area", target: "area-selection-tool-circle" },
      { label: "Facility comparison", section: "map-control-section-facility", target: "trace-facility-filter-enabled" },
    ];
    tasks.forEach(function (task) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary-button workflow-small-action";
      button.textContent = task.label;
      button.addEventListener("click", function () {
        showMap();
        if (task.primary) {
          const mobileFilters = byId("preview-mobile-filters");
          if (mobileFilters && window.innerWidth <= 1080) mobileFilters.open = true;
          setPanelCollapsed(panels[0], false);
          const primaryToggle = byId("toggle-primary-filters");
          if (primaryToggle && primaryToggle.getAttribute("aria-expanded") === "false") primaryToggle.click();
        } else {
          const toolboxToggle = byId("toggle-map-control-cluster");
          if (toolboxToggle && toolboxToggle.getAttribute("aria-expanded") === "false") toolboxToggle.click();
          const section = byId(task.section);
          if (section) section.open = true;
        }
        window.requestAnimationFrame(function () { focusTarget(byId(task.target)); });
      });
      shortcuts.appendChild(button);
    });
    guide.appendChild(shortcuts);
  }

  function install() {
    document.documentElement.classList.add("site-workflow-preview");
    const reportBody = byId("primary-filters-body");
    caption("workflow-report-scope", reportBody, reportBody && reportBody.firstChild);
    const legend = byId("map-legend-panel");
    const legendCaption = caption("workflow-legend-scope", legend, byId("map-legend-status"));
    setText(legendCaption, "Counts in this map view");
    if (legendCaption) legendCaption.title = "Viewport legend counts can differ from the full filtered Results total.";
    caption("workflow-context-scope", byId("map-control-overlays-slot"));
    caption("workflow-convergence-scope", byId("map-control-intersections-slot"));
    const convergenceLabel = document.querySelector("#map-control-section-intersections .map-control-summary-label");
    if (convergenceLabel) {
      const stamp = document.createElement("span");
      stamp.id = "workflow-convergence-stamp";
      stamp.className = "workflow-scope-stamp";
      stamp.hidden = true;
      convergenceLabel.appendChild(stamp);
    }
    installFocusMap();
    installBackToResults();
    installHelpShortcuts();

    ["change", "pointerup", "click"].forEach(function (name) {
      document.addEventListener(name, scheduleRefresh, true);
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === "Escape") scheduleRefresh();
    }, true);
    ["ufo:timeline-ready", "ufo:crop-circle-statechange", "ufo:animal-mutilation-statechange"].forEach(function (name) {
      window.addEventListener(name, scheduleRefresh);
    });
    ["source-filter-state", "type-filter-state", "precision-filter-state", "primary-filters-flap-status",
      "map-control-overlays-summary-state", "map-control-intersections-summary-state", "results-case-context"].forEach(function (id) {
      const element = byId(id);
      if (element) new MutationObserver(scheduleRefresh).observe(element, { childList: true, characterData: true, subtree: true });
    });
    refreshScopeCaptions();
  }

  window.UfoSiteWorkflowPreview = Object.freeze({
    refresh: scheduleRefresh,
    getPanelLayout: panelLayout,
  });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", install, { once: true });
  else install();
})();
