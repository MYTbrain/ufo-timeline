from pathlib import Path


ATTRIBUTION_HTML = (
    '<p class="hero-attribution">Sightings datasets generously provided by '
    '<a href="https://ufosint.com/" target="_blank" '
    'rel="noopener noreferrer external">UFOSINT</a>.</p>'
)


def test_ufosint_attribution_is_beneath_hero_text_and_safe():
    for path in (
        Path("webapp/static_public/index.html"),
        Path("static_bundle/index.html"),
    ):
        html = path.read_text(encoding="utf-8")
        hero_text_index = html.index('<p class="hero-subtext">')
        attribution_index = html.index(ATTRIBUTION_HTML)

        assert attribution_index > hero_text_index
        assert attribution_index < html.index('</div>', attribution_index)


def test_ufosint_attribution_is_visible_and_keyboard_focusable_on_mobile():
    required_fragments = (
        ".hero-attribution {",
        "display: block;",
        ".hero-attribution a:focus-visible {",
        "outline: 3px solid var(--accent);",
        "@media (max-width: 1080px)",
        "font-size: clamp(0.82rem, 2.8vw, 0.9rem);",
    )
    for path in (
        Path("webapp/static_public/styles.css"),
        Path("static_bundle/styles.css"),
    ):
        css = path.read_text(encoding="utf-8")
        for fragment in required_fragments:
            assert fragment in css
