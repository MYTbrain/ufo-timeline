from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]


class CaseShellParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = Counter()
        self.elements = {}
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.ids[element_id] += 1
            self.elements[element_id] = (tag, attributes)
        if tag == "script" and attributes.get("src"):
            self.scripts.append(attributes["src"])


def load_shell():
    markup = (ROOT / "index.html").read_text(encoding="utf-8")
    parser = CaseShellParser()
    parser.feed(markup)
    return markup, parser


def test_case_picker_and_direction_controls_have_accessible_unique_targets():
    markup, parser = load_shell()
    assert not [element_id for element_id, count in parser.ids.items() if count != 1]
    for element_id in (
        "filter-famous-cases", "famous-case-search", "famous-case-search-status",
        "famous-case-details", "area-direction-summary", "area-direction-summary-body",
        "results-famous-case-summary", "results-case-context",
    ):
        assert parser.ids[element_id] == 1
    assert markup.index('id="filter-flap-presets"') < markup.index('id="filter-famous-cases"')
    assert parser.elements["filter-famous-cases"][1]["aria-describedby"] == "famous-case-search-status"
    assert parser.elements["famous-case-search"][1]["aria-controls"] == "filter-famous-cases"
    assert parser.elements["famous-case-search-status"][1]["role"] == "status"
    assert "hidden" in parser.elements["area-direction-summary"][1]


def test_full_case_context_has_a_dedicated_results_location():
    markup, parser = load_shell()
    summary = parser.elements["results-famous-case-summary"]
    assert summary[0] == "section"
    assert summary[1]["aria-label"] == "Selected famous case"
    assert "hidden" in summary[1]
    assert "hidden" in parser.elements["famous-case-details"][1]
    assert (
        markup.index('id="results-pane-shell"')
        < markup.index('id="results-famous-case-summary"')
        < markup.index('id="results-case-context"')
        < markup.index('id="result-list"')
        < markup.index('id="expand-results-pane"')
    )


def test_case_direction_and_legend_dependencies_ship_before_the_app():
    _markup, parser = load_shell()
    script_paths = [urlsplit(src).path.removeprefix("./") for src in parser.scripts]
    expected = {
        "trace_neighborhood.js": "2026-10-06-case-traces-v4",
        "trace_direction_summary.js": "2026-10-06-shared-arrows-v8",
        "legend_controls.js": "2026-10-06-legend-case-labels-v3",
        "famous_case_presets.js": "2026-10-06-case-records-v6",
    }
    for filename, token in expected.items():
        assert (ROOT / filename).is_file()
        assert script_paths.index(filename) < script_paths.index("app.js")
        assert f"./{filename}?v={token}" in parser.scripts
    assert "./app.js?v=2026-10-06-case-coverage-v11" in parser.scripts
