from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import re


SOURCE_ROOT = Path("webapp/static_public")


class ShellParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: Counter[str] = Counter()
        self.elements: dict[str, tuple[str, dict[str, str | None]]] = {}
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.ids[element_id] += 1
            self.elements[element_id] = (tag, attributes)
        if tag == "script" and attributes.get("src"):
            self.scripts.append(str(attributes["src"]))

    handle_startendtag = handle_starttag


def load_shell() -> tuple[str, str, str, ShellParser]:
    index_html = (SOURCE_ROOT / "index.html").read_text(encoding="utf-8")
    styles_css = (SOURCE_ROOT / "styles.css").read_text(encoding="utf-8")
    analysis_js = (SOURCE_ROOT / "analysis_view.js").read_text(encoding="utf-8")
    parser = ShellParser()
    parser.feed(index_html)
    return index_html, styles_css, analysis_js, parser


def test_analysis_tabs_and_panels_have_complete_accessible_shell_contract() -> None:
    index_html, _styles_css, _analysis_js, parser = load_shell()
    assert not [element_id for element_id, count in parser.ids.items() if count != 1]

    tablist = parser.elements["analysis-view-tablist"]
    map_tab = parser.elements["view-tab-map"]
    analysis_tab = parser.elements["view-tab-analysis"]
    map_panel = parser.elements["map-explorer-panel"]
    analysis_panel = parser.elements["analysis-panel"]

    assert tablist[1]["role"] == "tablist"
    assert tablist[1]["aria-label"] == "Primary data view"
    assert map_tab[0] == analysis_tab[0] == "button"
    assert map_tab[1]["role"] == analysis_tab[1]["role"] == "tab"
    assert map_tab[1]["aria-selected"] == "true"
    assert map_tab[1]["aria-controls"] == "map-explorer-panel"
    assert analysis_tab[1]["aria-selected"] == "false"
    assert analysis_tab[1]["aria-controls"] == "analysis-panel"
    assert analysis_tab[1]["aria-disabled"] == "true"
    assert "disabled" in analysis_tab[1]

    assert map_panel[1]["role"] == analysis_panel[1]["role"] == "tabpanel"
    assert map_panel[1]["aria-labelledby"] == "view-tab-map"
    assert analysis_panel[1]["aria-labelledby"] == "view-tab-analysis"
    assert "hidden" in analysis_panel[1]
    assert "inert" in analysis_panel[1]

    map_panel_start = index_html.index('id="map-explorer-panel"')
    analysis_panel_start = index_html.index('id="analysis-panel"')
    timeline_dock_start = index_html.index('id="map-timeline-dock"')
    assert map_panel_start < analysis_panel_start < timeline_dock_start
    assert 'id="map-height-resize-rail"' in index_html[map_panel_start:analysis_panel_start]
    assert 'id="map-timeline-dock"' not in index_html[map_panel_start:analysis_panel_start]


def test_analysis_shell_exposes_all_sections_states_and_preview_actions() -> None:
    _index_html, _styles_css, _analysis_js, parser = load_shell()
    required_ids = {
        "analysis-baseline",
        "analysis-computation-status",
        "analysis-loading",
        "analysis-empty",
        "analysis-error",
        "analysis-error-retry",
        "analysis-content",
        "analysis-section-overview",
        "analysis-section-time",
        "analysis-section-craft",
        "analysis-section-geography",
        "analysis-section-spatial",
        "analysis-section-crops",
        "analysis-section-animals",
        "analysis-section-facilities",
        "analysis-section-sources-quality",
        "analysis-section-context",
        "analysis-context-status",
        "analysis-section-nav",
        "analysis-workspace-toolbar",
        "analysis-start-date",
        "analysis-end-date",
        "analysis-all-time",
        "analysis-apply-date-range",
        "analysis-date-range-chip",
        "analysis-date-popover",
        "analysis-mode-label",
        "analysis-cohort-banner",
        "analysis-methodology",
        "analysis-summary-grid",
        "analysis-pattern-list",
        "analysis-relationship-readiness-chart",
        "analysis-relationship-context",
        "analysis-crop-context",
        "analysis-animal-context",
        "analysis-include-crop-circles",
        "analysis-include-animal-reports",
        "analysis-view-crop-analysis",
        "analysis-view-animal-analysis",
        "analysis-crop-excluded",
        "analysis-animal-excluded",
        "analysis-export-json",
        "analysis-export-csv",
        "analysis-preview-drawer",
        "analysis-preview-apply-filters",
        "analysis-preview-apply-area",
        "analysis-preview-cancel",
    }
    chart_ids = {
        "analysis-coverage-chart",
        "analysis-overview-coverage-visual",
        "analysis-overview-craft-mosaic",
        "analysis-overview-context-visual",
        "analysis-comparison-chart",
        "analysis-time-series-chart",
        "analysis-month-year-chart",
        "analysis-craft-distribution-chart",
        "analysis-report-type-chart",
        "analysis-craft-confidence-chart",
        "analysis-craft-residual-chart",
        "analysis-craft-era-chart",
        "analysis-geography-grid-chart",
        "analysis-geography-sensitivity-chart",
        "analysis-geography-time-chart",
        "analysis-spatial-eligibility-chart",
        "analysis-cooccurrence-chart",
        "analysis-context-neighborhood-chart",
        "analysis-context-category-chart",
        "analysis-facility-context-chart",
        "analysis-cross-domain-readiness-chart",
        "analysis-crop-readiness-chart",
        "analysis-animal-readiness-chart",
        "analysis-relationship-readiness-chart",
        "analysis-source-composition-chart",
        "analysis-source-time-chart",
        "analysis-quality-missingness-chart",
        "analysis-quality-audit-chart",
        "analysis-crop-time-chart",
        "analysis-crop-morphology-chart",
        "analysis-crop-type-chart",
        "analysis-crop-coordinate-chart",
        "analysis-crop-coverage-chart",
        "analysis-crop-spatial-chart",
        "analysis-crop-craft-context-chart",
        "analysis-animal-time-chart",
        "analysis-animal-species-chart",
        "analysis-animal-status-chart",
        "analysis-animal-date-precision-chart",
        "analysis-animal-coverage-chart",
        "analysis-animal-spatial-chart",
        "analysis-animal-craft-context-chart",
    }
    assert required_ids | chart_ids <= set(parser.elements)
    for chart_id in chart_ids:
        assert parser.elements[chart_id][1]["data-analysis-chart"]

    baseline_options = (SOURCE_ROOT / "index.html").read_text(encoding="utf-8")
    assert '<option value="other_dates_balanced" selected>' in baseline_options
    assert '<option value="previous_equal_duration">' in baseline_options
    assert '<option value="full_catalog">' in baseline_options
    assert "Other dates, balanced" in baseline_options
    assert "Report-marker associations only. Chronology connectors are never analyzed." in baseline_options
    assert 'role="switch" aria-checked="true"' in baseline_options
    assert "proximity does not establish a relationship or cause" in baseline_options
    assert "They do not establish travel, causation, authenticity, or phenomenon incidence." in baseline_options
    section_tab_ids = [
        "analysis-section-tab-overview",
        "analysis-section-tab-time",
        "analysis-section-tab-craft",
        "analysis-section-tab-geography",
        "analysis-section-tab-spatial",
        "analysis-section-tab-crops",
        "analysis-section-tab-animals",
        "analysis-section-tab-facilities",
        "analysis-section-tab-context",
        "analysis-section-tab-sources-quality",
    ]
    assert parser.elements["analysis-section-nav"][1]["role"] == "tablist"
    assert [parser.elements[tab_id][1]["aria-controls"] for tab_id in section_tab_ids] == [
        "analysis-section-overview",
        "analysis-section-time",
        "analysis-section-craft",
        "analysis-section-geography",
        "analysis-section-spatial",
        "analysis-section-crops",
        "analysis-section-animals",
        "analysis-section-facilities",
        "analysis-section-context",
        "analysis-section-sources-quality",
    ]
    assert sum(parser.elements[tab_id][1]["aria-selected"] == "true" for tab_id in section_tab_ids) == 1
    assert all(parser.elements[tab_id][0] == "button" for tab_id in section_tab_ids)
    for index, tab_id in enumerate(section_tab_ids):
        panel_id = parser.elements[tab_id][1]["aria-controls"]
        panel = parser.elements[panel_id]
        assert panel[1]["role"] == "tabpanel"
        assert panel[1]["aria-labelledby"] == tab_id
        if index:
            assert "hidden" in panel[1]
            assert "inert" in panel[1]
            assert panel[1]["aria-hidden"] == "true"
        else:
            assert "hidden" not in panel[1]
            assert "inert" not in panel[1]
            assert panel[1]["aria-hidden"] == "false"

def test_analysis_dashboards_prioritize_the_primary_questions() -> None:
    index_html = (SOURCE_ROOT / "index.html").read_text(encoding="utf-8")
    card_pattern = re.compile(r'<(?:article|details)\b[^>]*class="[^"]*\banalysis-card\b[^"]*"', re.I)

    time_shell = index_html.split('id="analysis-section-time"', 1)[1].split('id="analysis-section-craft"', 1)[0]
    craft_shell = index_html.split('id="analysis-section-craft"', 1)[1].split('id="analysis-section-geography"', 1)[0]
    geography_shell = index_html.split('id="analysis-section-geography"', 1)[1].split('id="analysis-section-spatial"', 1)[0]
    overview_shell = index_html.split('id="analysis-section-overview"', 1)[1].split('id="analysis-section-time"', 1)[0]
    spatial_shell = index_html.split('id="analysis-section-spatial"', 1)[1].split('id="analysis-section-crops"', 1)[0]
    crop_shell = index_html.split('id="analysis-section-crops"', 1)[1].split('id="analysis-section-animals"', 1)[0]
    animal_shell = index_html.split('id="analysis-section-animals"', 1)[1].split('id="analysis-section-facilities"', 1)[0]
    facilities_shell = index_html.split('id="analysis-section-facilities"', 1)[1].split('id="analysis-section-context"', 1)[0]
    context_shell = index_html.split('id="analysis-section-context"', 1)[1].split('id="analysis-section-sources-quality"', 1)[0]
    sources_shell = index_html.split('id="analysis-section-sources-quality"', 1)[1].split('id="analysis-preview-drawer"', 1)[0]

    assert len(card_pattern.findall(time_shell)) == 3
    assert 'id="analysis-duration-status"' in time_shell
    assert 'id="analysis-duration-chart"' in time_shell
    assert 'id="analysis-duration-comparison-chart"' in time_shell
    assert 'analysis-rolling' not in time_shell
    assert 'analysis-decade-chart' not in time_shell
    assert 'analysis-bursts-chart' not in time_shell
    assert len(card_pattern.findall(craft_shell)) == 3
    assert 'id="analysis-craft-geography-chart"' not in craft_shell
    assert 'id="analysis-report-type-chart"' not in craft_shell
    assert 'id="analysis-craft-residual-chart"' not in craft_shell
    assert 'id="analysis-report-type-chart"' in sources_shell
    assert 'id="analysis-craft-residual-chart"' in sources_shell
    assert 'id="analysis-craft-trends-chart"' not in sources_shell
    assert '<h3 id="analysis-geography-title">Country evidence</h3>' in geography_shell
    assert 'id="analysis-geography-sensitivity-chart"' in geography_shell
    assert '<summary>Advanced equal-area sensitivity</summary>' in geography_shell
    assert len(card_pattern.findall(overview_shell)) == 4
    cohort_shell = overview_shell.split('id="analysis-cohort-banner"', 1)[1].split('id="analysis-methodology"', 1)[0]
    assert 'id="analysis-coverage-chart"' in cohort_shell
    assert 'id="analysis-comparison-chart"' in overview_shell
    assert 'id="analysis-pattern-list"' in overview_shell
    assert len(card_pattern.findall(spatial_shell)) == 2
    assert 'id="analysis-cross-domain-readiness-chart"' not in spatial_shell
    assert 'id="analysis-context-category-card" class="analysis-card-subsection' in spatial_shell
    assert 'id="analysis-cross-domain-readiness-chart"' in context_shell
    assert len(card_pattern.findall(crop_shell)) == 4
    assert len(card_pattern.findall(animal_shell)) == 4
    assert len(card_pattern.findall(facilities_shell)) == 1
    assert 'id="analysis-crop-craft-context-chart"' in crop_shell
    assert 'id="analysis-animal-craft-context-chart"' in animal_shell
    assert len(card_pattern.findall(sources_shell)) == 3
    assert 'id="analysis-spatial-eligibility-chart"' in index_html


def test_v22_dashboard_order_visibility_and_dom_budget_are_bounded() -> None:
    index_html, styles_css, _analysis_js, parser = load_shell()
    dashboard_names = [
        "overview",
        "time",
        "craft",
        "geography",
        "spatial",
        "crops",
        "animals",
        "facilities",
        "context",
        "sources-quality",
    ]
    tab_ids = [f"analysis-section-tab-{name}" for name in dashboard_names]
    panel_ids = [f"analysis-section-{name}" for name in dashboard_names]

    assert [parser.elements[tab_id][1]["aria-controls"] for tab_id in tab_ids] == panel_ids
    assert [index_html.index(f'id="{tab_id}"') for tab_id in tab_ids] == sorted(
        index_html.index(f'id="{tab_id}"') for tab_id in tab_ids
    )
    assert [index_html.index(f'id="{panel_id}"') for panel_id in panel_ids] == sorted(
        index_html.index(f'id="{panel_id}"') for panel_id in panel_ids
    )
    assert dashboard_names[-1] == "sources-quality"

    assert parser.elements[panel_ids[0]][1]["aria-hidden"] == "false"
    assert "hidden" not in parser.elements[panel_ids[0]][1]
    assert "inert" not in parser.elements[panel_ids[0]][1]
    for panel_id in panel_ids[1:]:
        attributes = parser.elements[panel_id][1]
        assert attributes["aria-hidden"] == "true"
        assert "hidden" in attributes
        assert "inert" in attributes

    section_bounds = list(zip(dashboard_names[:-1], dashboard_names[1:]))
    section_shells = {
        name: index_html.split(f'id="analysis-section-{name}"', 1)[1].split(
            f'id="analysis-section-{next_name}"', 1
        )[0]
        for name, next_name in section_bounds
    }
    section_shells["sources-quality"] = index_html.split(
        'id="analysis-section-sources-quality"', 1
    )[1].split('id="analysis-preview-drawer"', 1)[0]
    card_pattern = re.compile(r'<(?:article|details)\b[^>]*class="[^"]*\banalysis-card\b[^"]*"', re.I)
    card_counts = {name: len(card_pattern.findall(shell)) for name, shell in section_shells.items()}
    assert card_counts == {
        "overview": 4,
        "time": 3,
        "craft": 3,
        "geography": 3,
        "spatial": 2,
        "crops": 4,
        "animals": 4,
        "facilities": 1,
        "context": 2,
        "sources-quality": 3,
    }
    assert sum(card_counts.values()) == 29
    assert 'id="analysis-context-category-card" class="analysis-card-subsection analysis-context-category-panel" hidden' in section_shells["spatial"]

    relationship_shell = section_shells["context"].split('id="analysis-relationship-context"', 1)[1]
    assert len(card_pattern.findall(relationship_shell)) == 1

    simultaneously_primary = {
        "overview": 4,
        "time": 1,
        "craft": 1,
        "geography": 1,
        "spatial": 1,
        "crops": 2,
        "animals": 2,
        "facilities": 1,
        "context": 2,
        "sources-quality": 1,
    }
    assert sum(simultaneously_primary.values()) == 16
    assert sum(simultaneously_primary.values()) < 20

    toolbar_rule = styles_css.split(".analysis-workspace-toolbar {", 1)[1].split("}", 1)[0]
    assert "position: sticky" in toolbar_rule
    assert "top: max(8px, var(--safe-area-top))" in toolbar_rule
    assert "z-index: 640" in toolbar_rule
    assert "ea6x12" not in index_html


def test_v22_reference_desktop_uses_compact_dashboard_layouts() -> None:
    index_html, styles_css, _analysis_js, _parser = load_shell()

    time_shell = index_html.split('id="analysis-section-time"', 1)[1].split(
        'id="analysis-section-craft"', 1
    )[0]
    craft_shell = index_html.split('id="analysis-section-craft"', 1)[1].split(
        'id="analysis-section-geography"', 1
    )[0]

    assert "analysis-time-series-card" in time_shell
    assert "analysis-reporting-delay-card" in time_shell
    assert "analysis-month-craft-card" in time_shell
    assert "analysis-craft-mosaic-card" in craft_shell
    assert "analysis-craft-era-card" in craft_shell
    assert "analysis-confidence-strip-card" in craft_shell
    assert craft_shell.index("analysis-craft-mosaic-card") < craft_shell.index("analysis-craft-era-card")

    for fragment in (
        ".analysis-time-series-card {\n  grid-column: span 5;",
        ".analysis-reporting-delay-card {\n  grid-column: span 7;",
        ".analysis-month-craft-card {\n  grid-column: span 7;",
        ".analysis-craft-mosaic-card {\n  grid-column: span 5;",
        ".analysis-craft-era-card {\n  grid-column: span 7;",
        ".analysis-confidence-strip-card {\n  grid-column: span 12;",
        ".analysis-confidence-strip-card .analysis-bar-list {\n  grid-template-columns: repeat(3, minmax(0, 1fr));",
        ".analysis-month-craft-card .analysis-heat-cell,\n.analysis-craft-era-card .analysis-heat-cell {\n  width: 38px;",
    ):
        assert fragment in styles_css

    compact_fallback = styles_css.split("@container (max-width: 700px) {", 1)[1].split("@media (max-width: 1180px)", 1)[0]
    for class_name in (
        ".analysis-time-series-card",
        ".analysis-reporting-delay-card",
        ".analysis-month-craft-card",
        ".analysis-craft-mosaic-card",
        ".analysis-craft-era-card",
        ".analysis-confidence-strip-card",
    ):
        assert class_name in compact_fallback


def test_shell_cache_keys_track_their_current_source_releases() -> None:
    index_html = (SOURCE_ROOT / "index.html").read_text(encoding="utf-8")
    assert "styles.css?v=2026-08-12-context-evidence-v2" in index_html
    assert "app.js?v=2026-08-12-viewport-legend-area-traces-v1" in index_html
    assert "analysis_view.js?v=2026-08-12-context-evidence-v2" in index_html
    assert "analysis-evidence-lab-v2-1-recovery" not in index_html


def test_analysis_controller_is_loaded_before_app_and_exposes_integration_api() -> None:
    _index_html, _styles_css, analysis_js, parser = load_shell()
    analysis_script_index = next(
        index for index, src in enumerate(parser.scripts) if "analysis_view.js" in src
    )
    app_script_index = next(index for index, src in enumerate(parser.scripts) if "app.js" in src)
    assert analysis_script_index < app_script_index

    for fragment in (
        "root.UfoAnalysisView = api",
        "class AnalysisViewController",
        "setActiveView(view, options)",
        "setAnalysisEnabled(enabled, reason)",
        "setAnalysisState(state, message)",
        "setComputationPhase(phaseValue, messageValue)",
        "renderAnalysisResult(result, metaOverrides)",
        "_renderActiveSectionIfNeeded()",
        "projectedEqualAreaGeometryPath",
        "worldEqualAreaPathCache",
        "showPreview(preview)",
        "hidePreview(options)",
        "renderPatternFindings(findings, patternGroups)",
        "navigateToSection(sectionId, options)",
        "refreshSectionNavigation(options)",
        "setContextControlState(domain, stateValue)",
        "setSectionState(sectionValue, stateValue, messageValue)",
        "onContextLayerChange",
        "onSectionActivate",
        "onExportEvidence",
        "getFilterSnapshot",
        "buildEvidencePackage",
        "evidencePackageToCsv",
        "sourceBalancedDisplay",
        "formatSignedPercent",
        "formatPercentInterval",
        "inferPreviewCriteria",
        "Point-based craft co-occurrence evidence",
        "Equal-area adjusted report enrichment",
        "No supported cells are available",
        "100% stacked source composition",
        "stableMultiSource",
        "previous_equal_duration",
        "onApplyFilterPreview",
        "onApplyAreaPreview",
    ):
        assert fragment in analysis_js


def test_analysis_sticky_date_controls_use_the_shared_date_state_pipeline() -> None:
    index_html = (SOURCE_ROOT / "index.html").read_text(encoding="utf-8")
    app_js = (SOURCE_ROOT / "app.js").read_text(encoding="utf-8")

    for fragment in (
        'id="analysis-start-date"',
        'id="analysis-end-date"',
        'id="analysis-all-time"',
        'id="analysis-apply-date-range"',
        'id="analysis-date-range-chip"',
        'id="analysis-date-popover"',
        'id="analysis-mode-label"',
        'id="analysis-date-feedback" class="date-range-feedback" role="alert" aria-live="assertive"',
    ):
        assert fragment in index_html

    for fragment in (
        "els.analysisStartDateInput",
        "els.analysisEndDateInput",
        "els.analysisStartDatePicker",
        "els.analysisEndDatePicker",
        "els.analysisDateFeedback",
        "syncAnalysisDateRangeSummary(startValue, endValue)",
        "validateDateRangeCandidate(startValue, endValue)",
        "commitAnalysisDateInputs()",
        'feedbackScope: "analysis"',
        "setAnalysisDatePopoverOpen(false, { restoreFocus: true })",
        "applyFullTimeRange();",
        "commitDateInputs()",
        "getWorldReferenceData: function () { return runtime.worldReferenceData; }",
    ):
        assert fragment in app_js

    blur_guard = re.search(
        r'input\.addEventListener\("blur", function \(event\) \{\s*'
        r'if \(isAnalysisDateInputElement\(input\)\) \{\s*'
        r'markDateInputPending\(input\);\s*return;',
        app_js,
    )
    assert blur_guard, "Analysis date drafts must not commit on blur before the pair is validated"

    apply_handler = re.search(
        r'analysisApplyDateButton\.addEventListener\("click", function \(\) \{\s*'
        r'if \(commitAnalysisDateInputs\(\)',
        app_js,
    )
    assert apply_handler, "Analysis Apply must use the atomic draft-pair commit path"


def test_analysis_styles_cover_dark_theme_mobile_keyboard_and_unavailable_map_controls() -> None:
    _index_html, styles_css, _analysis_js, _parser = load_shell()
    for selector_or_token in (
        ".hero-view-tab:focus-visible",
        ".map-explorer-panel[hidden]",
            ".analysis-panel[hidden]",
            ".analysis-section[hidden]",
            ".analysis-section-nav",
            ".analysis-section-nav [role=\"tab\"][aria-selected=\"true\"]",
            ".analysis-workspace-toolbar",
            ".analysis-date-popover",
        ".analysis-signal-spectrum",
        ".analysis-eligibility-funnel",
        ".analysis-eligibility-strip",
        ".analysis-overview-evidence-grid",
        ".analysis-craft-mosaic",
        ".analysis-country-choropleth",
        ".analysis-country-shape",
        ".analysis-visual-briefing-grid",
        ".analysis-context-pulse-card",
        ".analysis-mosaic-mode-button",
        'html[data-active-primary-view="analysis"] .timeline-panel',
        ".analysis-context-subchart-grid",
        ".analysis-card-subsection[hidden]",
        ".analysis-context-readiness-card",
        ".analysis-source-composite-card",
        ".analysis-spatial-eligibility",
        ".analysis-heat-cell.is-diagonal",
        ".has-formation-lane",
        ".shows-formation-configuration",
        'data-readiness-status="ready_inferential"',
        'data-readiness-status="data_unavailable"',
        ".analysis-computation-status",
        ".analysis-context-switch[aria-checked=\"true\"]",
        ".analysis-forest-row",
        ".analysis-equal-area-svg",
        ".analysis-equal-area-land",
        ".analysis-equal-area-land-outline",
        ".analysis-equal-area-graticule",
        ".analysis-equal-area-axis-title",
        ".analysis-readiness-grid",
        ".analysis-readiness-metrics",
        ".analysis-context-excluded",
        ".analysis-summary-grid",
        ".analysis-series-svg",
        ".analysis-composition-track",
        ".analysis-pattern-lane",
        ".analysis-heatmap-table",
        ".analysis-data-table",
        ".analysis-preview-drawer",
        '[data-analysis-unavailable="true"]',
        "Available in Map Explorer",
        "@media (max-width: 760px)",
        "@media (prefers-reduced-motion: reduce)",
        "var(--panel-strong)",
        "var(--focus-ring)",
    ):
        assert selector_or_token in styles_css
    analysis_panel_rule = styles_css.split(".analysis-panel {", 1)[1].split("}", 1)[0]
    assert "height: auto" in analysis_panel_rule
    assert "overflow: visible" in analysis_panel_rule
    assert "content-visibility: auto" not in styles_css.split(".analysis-section {", 1)[1].split("}", 1)[0]
    assert "grid-template-columns: repeat(12, minmax(0, 1fr))" in styles_css
    assert 'html[data-active-primary-view="analysis"] .map-timeline-dock' in styles_css
    mobile_rules = styles_css.split("@media (max-width: 760px) {", 1)[1].split("@media (max-width: 480px)", 1)[0]
    assert ".analysis-card" in mobile_rules
    assert "max-width: 100%" in mobile_rules
    assert "overflow: hidden" in mobile_rules
    assert ".analysis-heatmap-scroll" in mobile_rules
    assert "width: 100%" in mobile_rules
