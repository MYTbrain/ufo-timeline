from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.analysis_color import normalize_color


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "campaign/analysis_improvement/waves/wave-007-color-assessment/raw_value_audit.json"
CONTRACT = ROOT / "campaign/analysis_improvement/waves/wave-007-color-assessment/parser_contract.json"


def test_exact_and_compound_categories_are_value_only() -> None:
    single = normalize_color("nuforc", "Bright white")
    compound = normalize_color("nuforc", "Red and white")
    assert single.status == "exact_single"
    assert single.categories == ("white",)
    assert single.role == "role_unspecified"
    assert compound.status == "explicit_compound"
    assert compound.categories == ("white", "red")
    assert compound.compound is True
    assert compound.multicolor is True


def test_light_and_object_roles_require_explicit_value_cues() -> None:
    unspecified = normalize_color("nuforc", "White")
    emitted = normalize_color("nuforc", "White lights")
    surface = normalize_color("nuforc", "Black object")
    both = normalize_color("nuforc", "White light on object")
    assert unspecified.role == "role_unspecified"
    assert emitted.role == "emitted_light_explicit"
    assert surface.role == "object_surface_explicit"
    assert both.role == "both_role_cues_ambiguous"


def test_descriptors_do_not_become_color_or_role_claims() -> None:
    for raw in ("Luminous", "Metallic", "Fiery", "Shiny", "Transparent", "Bright", "Dark"):
        value = normalize_color("ufocat", raw)
        assert value.status == "non_color_descriptor"
        assert value.categories == ()
        assert value.role == "role_unspecified"
        assert value.normalized is False


def test_changing_and_unspecified_multicolor_remain_distinct() -> None:
    changing = normalize_color("ufocat", "Changed")
    changing_known = normalize_color("nuforc", "Changing red and blue")
    multi = normalize_color("ufocat", "Multi")
    assert changing.status == "changing_unspecified"
    assert changing.changing is True
    assert changing.categories == ()
    assert changing_known.status == "changing_known"
    assert changing_known.categories == ("red", "blue")
    assert multi.status == "multicolor_unspecified"
    assert multi.multicolor is True


def test_registered_ufocat_packed_values_require_complete_segmentation() -> None:
    compound = normalize_color("ufocat", "RedOrang")
    modified = normalize_color("ufocat", "DarkGray")
    unsupported = normalize_color("ufocat", "BluMetal")
    ordinary_text = normalize_color("nuforc", "RedOrang")
    assert compound.status == "explicit_compound"
    assert compound.categories == ("red", "orange")
    assert modified.status == "exact_single"
    assert modified.categories == ("gray",)
    assert unsupported.status == "unparsed"
    assert ordinary_text.status == "unparsed"


def test_missing_sentinels_and_unparsed_text_fail_closed() -> None:
    assert normalize_color("nuforc", "").status == "missing"
    for raw in ("Unknown", "Unk", "N/A", "NA", "None", "null"):
        assert normalize_color("nuforc", raw).status == "source_sentinel"
    assert normalize_color("ufocat", "Metal").status == "unparsed"
    assert normalize_color("ufocat", "Observed").status == "unparsed"


def test_original_value_hash_and_normalization_are_exact_and_idempotent() -> None:
    raw = "  White/Blue  "
    first = normalize_color("nuforc", raw)
    second = normalize_color("nuforc", raw)
    assert first == second
    assert first.raw_value == raw
    assert first.raw_value_sha256 == hashlib.sha256(raw.encode("utf-8")).hexdigest()


def test_raw_audit_and_parser_contract_are_pinned_before_build() -> None:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert audit["auditBoundary"]["normalizationDecisionMade"] is False
    assert audit["coverage"]["eligibleRawColorRows"] == 79_215
    assert audit["coverage"]["sourceEligibleRows"] == {"nuforc": 11_686, "ufocat": 67_529}
    assert audit["semanticAuditAnchors"]["roleAnchorRows"]["no_explicit_role_cue"] == 77_994
    assert contract["governingAudit"]["sha256"] == hashlib.sha256(AUDIT.read_bytes()).hexdigest()
    assert contract["roleRules"]["default"] == "role_unspecified"
    assert contract["releaseAccounting"]["minimumNormalizedRows"] == 63_372
    assert contract["releaseAccounting"]["patternFinderEligible"] is False
