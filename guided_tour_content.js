/* Guided exploration copy and DOM targets. This module never changes app state. */
(function (root, factory) {
  "use strict";
  const content = factory();
  if (typeof module === "object" && module.exports) module.exports = content;
  if (root) root.UfoGuidedTourContent = content;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function steps(items) {
    return Object.freeze(items.map(function (item) { return Object.freeze(item); }));
  }

  return Object.freeze({
    essentials: steps([
      {
        id: "workspace",
        title: "Start with the map",
        body: "Filters choose the reports, the legend explains what you see, and Results lets you inspect the records. You can pan and zoom the map at any time.",
        target: "#map-explorer-panel",
        context: "map",
      },
      {
        id: "famous-cases",
        title: "Find a familiar case",
        body: "Search famous cases by name, place, or year. Selecting one centers its vicinity and sets a nearby date window. Results shows its database coverage. The case stays selected until you choose Clear.",
        target: ".famous-case-picker",
        context: "cases",
      },
      {
        id: "filters",
        title: "Choose the reports",
        body: "Adjust dates or search report text here. Categories below let you choose sources, reported types, and location precision. These report filters also carry into Analysis.",
        target: "#primary-filters-body",
        context: "filters",
      },
      {
        id: "results",
        title: "Read the evidence",
        body: "Select a mapped result to locate it. Description opens its account; Full Details shows the preserved record. Case-result labels distinguish reports inside the selected area from connected reports outside.",
        target: "#results-pane-shell",
        context: "results",
      },
      {
        id: "legend",
        title: "Use the interactive legend",
        body: "Colors and symbols identify categories. Click a colored dot to show or hide a craft category; click its name to focus on it. Click that name again to restore the previous mix. Counts describe this map view, rather than the full Results total.",
        target: "#map-legend-panel",
        context: "legend",
      },
      {
        id: "map-view",
        title: "Choose your map view",
        body: "Map tools keep detailed controls nearby. Points shows individual reports, Clusters groups crowded markers, and Heatmap shows concentration. Fit Map To Filtered Results brings matching locations into view.",
        target: "#map-mode",
        context: "view",
      },
      {
        id: "traces",
        title: "Understand the connections",
        body: "Choose Static for report connections, or Playback for the playback trail. Single arrows show supported report order; double arrows show unresolved order. Click a static arrow for timing evidence. These connections do not establish a flight path.",
        target: "#trace-mode",
        context: "traces",
      },
      {
        id: "chronology",
        title: "Explore through time",
        body: "The Chronology Explorer shares the report date window. Resize its selection or enter dates, then use Play to step through mapped reports. Famous Flaps offers ready-made historical windows.",
        target: "#timeline-canvas-wrap",
        context: "timeline",
      },
      {
        id: "analysis",
        title: "Explore Analysis",
        body: "Choose a Topic, then a View, to compare the selected reports. Start with Overview to see coverage and missing data before interpreting a pattern. The shorter Analysis tour explains the comparison controls.",
        target: "#analysis-section-nav",
        context: "analysis-topic",
      },
    ]),
    analysis: steps([
      {
        id: "analysis-topics",
        title: "Choose one question",
        body: "Topics organize reporting patterns, context catalogs, and evidence quality. You can move between them without losing the current report filters.",
        target: "#analysis-section-nav",
        context: "analysis-topic",
      },
      {
        id: "analysis-dates",
        title: "Set the comparison window",
        body: "Open Date range to choose report dates and a reference baseline. All Time shows internal structure; a selected date window can be compared with reference reports.",
        target: "#analysis-date-range-chip",
        context: "analysis-topic",
      },
      {
        id: "analysis-coverage",
        title: "Check what is available",
        body: "Overview shows active, reference, mapped, unmapped, and missing-field counts. Available evidence determines which comparisons can be supported.",
        target: "#analysis-cohort-banner",
        context: "analysis-coverage",
      },
      {
        id: "analysis-views",
        title: "Explore one view at a time",
        body: "Views keep each topic manageable. Choose the question you need, or All charts to expand the topic. Supporting details hold exact values and methodology.",
        target: "#analysis-section-overview .preview-analysis-view-nav",
        context: "analysis-view",
      },
      {
        id: "analysis-comparisons",
        title: "Compare the wider context",
        body: "Comparisons includes Moon, planets, nuclear activity, and report context. Follow the coverage and uncertainty labels: these show associations in recorded reports, not causes.",
        target: "#analysis-comparisons-chart",
        context: "analysis-comparisons",
      },
    ]),
  });
});
