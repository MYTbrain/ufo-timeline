/* Local preview definitions only. No DOM, state, charts, or data are changed here.
 * Each group owns existing whole cards/disclosures; anchors are not chart copies.
 * Optional rootSelectors correspond to anchorIds and identify a larger native unit.
 * The caller supplies the separate "All charts" choice and skips a view picker
 * for sections with only one group. Crop/animal units must stay within their
 * original #analysis-*-content containers so exclusion states remain effective.
 */
(function () {
  "use strict";

  const groups = {
    overview: [
      {
        key: "cohort",
        label: "Cohort overview",
        anchorIds: ["analysis-overview-coverage-visual", "analysis-cohort-banner"],
        rootSelectors: [".analysis-visual-briefing", "#analysis-cohort-banner"],
      },
      {
        key: "signals",
        label: "Signals & patterns",
        anchorIds: ["analysis-comparison-chart"],
        rootSelectors: [".analysis-overview-evidence-card"],
      },
      {
        key: "methods",
        label: "Methodology & provenance",
        anchorIds: ["analysis-methodology"],
        rootSelectors: ["#analysis-methodology"],
      },
    ],
    time: [
      { key: "activity", label: "Reporting activity", anchorIds: ["analysis-time-series-chart"] },
      { key: "timing", label: "Delay, duration & time of day", anchorIds: ["analysis-reporting-delay-chart"] },
      { key: "seasonal", label: "Seasonal craft patterns", anchorIds: ["analysis-month-year-chart"] },
    ],
    craft: [
      { key: "composition", label: "Craft composition", anchorIds: ["analysis-craft-distribution-chart"] },
      { key: "eras", label: "Craft by era", anchorIds: ["analysis-craft-era-chart"] },
      { key: "classification", label: "Classification & color", anchorIds: ["analysis-craft-confidence-chart"] },
    ],
    geography: [
      { key: "countries", label: "Country evidence", anchorIds: ["analysis-geography-grid-chart"] },
      { key: "eras", label: "Geography by era", anchorIds: ["analysis-geography-time-chart"] },
      { key: "sensitivity", label: "Equal-area sensitivity", anchorIds: ["analysis-geography-sensitivity-chart"] },
    ],
    spatial: [
      {
        key: "cooccurrence",
        label: "Craft co-occurrence",
        anchorIds: ["analysis-spatial-eligibility-chart"],
        rootSelectors: ["#analysis-section-spatial > .analysis-card-grid > article"],
      },
      {
        key: "context",
        label: "Context neighborhoods",
        anchorIds: ["analysis-spatial-context-disclosure"],
        rootSelectors: ["#analysis-spatial-context-disclosure"],
      },
    ],
    crops: [
      { key: "activity", label: "Records over time", anchorIds: ["analysis-crop-time-chart"] },
      { key: "craft", label: "Craft & crop context", anchorIds: ["analysis-crop-craft-context-chart"] },
      { key: "composition", label: "Formation profile", anchorIds: ["analysis-crop-morphology-chart"] },
      { key: "coverage", label: "Coverage & locations", anchorIds: ["analysis-crop-coordinate-chart"] },
    ],
    animals: [
      { key: "activity", label: "Reports over time", anchorIds: ["analysis-animal-time-chart"] },
      { key: "craft", label: "Craft & animal context", anchorIds: ["analysis-animal-craft-context-chart"] },
      { key: "composition", label: "Species & review status", anchorIds: ["analysis-animal-species-chart"] },
      { key: "coverage", label: "Coverage & locations", anchorIds: ["analysis-animal-date-precision-chart"] },
    ],
    facilities: [
      { key: "profile", label: "Facility proximity profile", anchorIds: ["analysis-facility-context-chart"] },
    ],
    context: [
      {
        key: "readiness",
        label: "Cross-domain readiness",
        anchorIds: ["analysis-cross-domain-readiness-chart"],
        rootSelectors: [".analysis-context-readiness-card"],
      },
      {
        key: "relationships",
        label: "Relationship lineage",
        anchorIds: ["analysis-relationship-readiness-chart"],
        rootSelectors: ["#analysis-relationship-context"],
      },
    ],
    "sources-quality": [
      { key: "collection", label: "Source collection", anchorIds: ["analysis-source-composition-chart"] },
      {
        key: "quality",
        label: "Quality & classification",
        anchorIds: ["analysis-quality-missingness-chart", "analysis-quality-audit-chart"],
      },
    ],
  };

  Object.values(groups).forEach((section) => {
    section.forEach((group) => {
      Object.freeze(group.anchorIds);
      if (group.rootSelectors) Object.freeze(group.rootSelectors);
      Object.freeze(group);
    });
    Object.freeze(section);
  });
  window.PreviewAnalysisViewGroups = Object.freeze(groups);
})();
