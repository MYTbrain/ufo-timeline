from collections import Counter
from html.parser import HTMLParser
from pathlib import Path


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
        "analysis-section-sources-quality",
        "analysis-section-context",
        "analysis-section-nav",
        "analysis-cohort-banner",
        "analysis-methodology",
        "analysis-summary-grid",
        "analysis-pattern-list",
        "analysis-rolling-title",
        "analysis-relationship-readiness-chart",
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
        "analysis-comparison-chart",
        "analysis-time-series-chart",
        "analysis-decade-chart",
        "analysis-month-year-chart",
        "analysis-rolling-chart",
        "analysis-bursts-chart",
        "analysis-craft-distribution-chart",
        "analysis-report-type-chart",
        "analysis-craft-confidence-chart",
        "analysis-craft-trends-chart",
        "analysis-craft-residual-chart",
        "analysis-craft-era-chart",
        "analysis-craft-geography-chart",
        "analysis-geography-grid-chart",
        "analysis-geography-time-chart",
        "analysis-cooccurrence-chart",
        "analysis-facility-context-chart",
        "analysis-cross-domain-readiness-chart",
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
        "analysis-animal-time-chart",
        "analysis-animal-species-chart",
        "analysis-animal-status-chart",
        "analysis-animal-date-precision-chart",
        "analysis-animal-coverage-chart",
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
    assert "An association appears only when its preregistered evidence gates pass." in baseline_options
    assert "They do not establish travel, causation, authenticity, or phenomenon incidence." in baseline_options
    assert baseline_options.count('aria-current="location"') == 1
    assert baseline_options.count('href="#analysis-section-') == 7
    assert 'href="#analysis-section-spatial">Spatial Evidence</a>' in baseline_options


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
        "Descriptive rolling report counts",
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


def test_analysis_styles_cover_dark_theme_mobile_keyboard_and_unavailable_map_controls() -> None:
    _index_html, styles_css, _analysis_js, _parser = load_shell()
    for selector_or_token in (
        ".hero-view-tab:focus-visible",
        ".map-explorer-panel[hidden]",
        ".analysis-panel[hidden]",
        ".analysis-section-nav",
        ".analysis-section-nav a[aria-current=\"location\"]",
        ".analysis-computation-status",
        ".analysis-context-switch[aria-checked=\"true\"]",
        ".analysis-forest-row",
        ".analysis-equal-area-svg",
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
    assert 'html[data-active-primary-view="analysis"] .map-timeline-dock' in styles_css
    mobile_rules = styles_css.split("@media (max-width: 760px) {", 1)[1].split("@media (max-width: 480px)", 1)[0]
    assert ".analysis-card" in mobile_rules
    assert "max-width: 100%" in mobile_rules
    assert "overflow: hidden" in mobile_rules
    assert ".analysis-heatmap-scroll" in mobile_rules
    assert "width: 100%" in mobile_rules
