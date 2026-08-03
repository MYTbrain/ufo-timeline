from __future__ import annotations

import csv
import json
import os
import shutil
from argparse import Namespace
from pathlib import Path

import pytest

from scripts import cattle_mutilation_seed as seed


def source_record(description: str, **overrides):
    row = {
        "canonical_input_id": "cin_fixture",
        "source_name": "fixture",
        "source_native_id": "fixture_1",
        "source_row_hash": "a" * 40,
        "date_raw": "1975-03-10",
        "date_iso": "1975-03-10",
        "end_date_iso": "1975-03-10",
        "date_precision": "day",
        "location_raw": "Whiteface, Texas, United States",
        "city": "Whiteface",
        "state_province": "TX",
        "country": "United States",
        "lat": 33.6,
        "lon": -102.6,
        "coordinate_source": "locality centroid",
        "location_precision": "city",
        "description": description,
        "summary": description,
        "type_raw": "report",
        "type_normalized": "report",
        "source_url": "https://example.invalid/fixture",
        "raw_fields": {"Long Description": description},
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize(
    ("label", "description", "species", "crop"),
    [
        ("whiteface", "A mutilated cow was found inside a 30-foot crop circle.", "cattle", True),
        ("pelotas", "Investigators reported 300 mutilated sheep; one was found beside a crop circle.", "sheep", True),
        ("eagle", "Several mutilated animals were discovered near a circular landing impression in crops.", "animal", False),
        ("gallipolis", "A dog was found crushed and bloodless in a crop circle.", "dog", True),
        ("westport", "A sheep was reportedly found gutted beside crop circles.", "sheep", True),
        ("netherlands", "Witnesses reported crop circles and cows that were badly mashed up.", "cattle", True),
    ],
)
def test_known_cross_domain_story_fixtures_are_direct_cases(label, description, species, crop):
    analysis = seed.analyze_source_record(source_record(description))
    assert analysis.record_type == "mutilation_case", label
    assert species in analysis.animal_terms, label
    assert analysis.explicit_crop_mutilation_link is crop, label
    assert analysis.needs_human_review is True


def test_oregon_nonclassic_deaths_remain_negative_context():
    analysis = seed.analyze_source_record(
        source_record(
            "The area had prior cattle mutilations and a crop circle. The current cows died, "
            "but did not have classic mutilation features."
        )
    )
    assert analysis.explicit_negative is True
    assert analysis.negative_only is True
    assert analysis.record_type != "mutilation_case"
    assert analysis.disposition == "explicit_negative_context"
    assert analysis.incident_likelihood <= 0.2


def test_positive_incident_survives_a_separate_negative_statement():
    analysis = seed.analyze_source_record(
        source_record("A cow was mutilated. Another cow was not mutilated.")
    )
    assert analysis.explicit_negative is True
    assert analysis.negative_only is False
    assert analysis.record_type == "mutilation_case"
    assert analysis.disposition == "candidate"


@pytest.mark.parametrize(
    "description",
    [
        "A cow was mutilated, but another cow was not mutilated.",
        "Calf found mutilated Chama Canyon, another 2 cows found dead, not mutilated E.",
    ],
)
def test_positive_incident_survives_same_sentence_negative_clause(description):
    analysis = seed.analyze_source_record(source_record(description))
    assert analysis.explicit_negative is True
    assert analysis.negative_only is False
    assert analysis.record_type == "mutilation_case"


@pytest.mark.parametrize(
    "description",
    [
        "No mutilation connection in this particular incident (although animal "
        "mutilations have been reported consistently for well over a decade in the area).",
        "This region is historically a mutilation-prone area (the Snippy the Horse "
        "event occurred here in 1967).",
    ],
)
def test_negative_or_historical_topical_context_is_not_a_discrete_case(description):
    analysis = seed.analyze_source_record(source_record(description))
    assert analysis.record_type != "mutilation_case"
    assert analysis.disposition in {
        "explicit_negative_context",
        "context_or_noise_candidate",
    }


@pytest.mark.parametrize(
    ("native_id", "description"),
    [
        (
            "live_weeks_before_news",
            "Week(s) before the incident I watched a local news broadcast about a "
            "farmers animals being mutilated in a county south of El Paso County.",
        ),
        (
            "live_period_background",
            "It should be noted that this Montana flap occurred during a period in "
            "which livestock mutilations were being consistently reported.",
        ),
        (
            "live_next_morning",
            "One of Irey's calves was found mutilated the next morning.",
        ),
        (
            "live_past_three_years",
            "In the past three years, we have lost two cows with missing parts.",
        ),
        (
            "live_previous_deaths",
            "There were strange cattle deaths in close timing to seeing these things "
            "previously, with the cattle missing eyes.",
        ),
        (
            "live_years_later",
            "Several years later there were numerous cow mutilations on local farms.",
        ),
        (
            "live_few_days_later_news",
            "A few days later I read about cow mutilations in the counties nearby.",
        ),
        (
            "live_mid_sentence_few_days_later",
            "It asked me to report this and a few days later my prize bull was dead "
            "with no blood and a perfect cut.",
        ),
        (
            "live_mid_sentence_year_later",
            "Then about a year later I saw an orange ball, then there was a cattle "
            "mutilation happen about that time.",
        ),
        (
            "live_news_day_before",
            "We remembered having heard about cattle mutilations on the news the day before.",
        ),
        ("Hatch_UDB_16884", "Cattle mutilated / day before."),
        (
            "live_days_prior",
            "Several reports of missing and mutilated cats were in the news in the "
            "days prior to this event.",
        ),
        ("live_back_in_the_day", "Cattle mutilation happened back in the day."),
    ],
)
def test_relative_or_historical_animal_mentions_do_not_inherit_ufo_event_date(
    native_id, description
):
    analysis = seed.analyze_source_record(
        source_record(description, source_native_id=native_id)
    )
    assert analysis.record_type != "mutilation_case"
    if analysis.candidate_reasons:
        assert "historical_or_background_context_only" in analysis.candidate_reasons


def test_source_dated_direct_incident_remains_canonicalizable():
    analysis = seed.analyze_source_record(
        source_record(
            "A cow was found mutilated on the reported date. Several days later, "
            "investigators arrived."
        )
    )
    assert analysis.record_type == "mutilation_case"
    assert "historical_or_background_context_only" not in analysis.candidate_reasons


def test_relative_cue_for_ufo_clause_does_not_demote_current_animal_discovery():
    analysis = seed.analyze_source_record(
        source_record(
            "Helicopters flew over the ranch the day before a mutilated cow was discovered."
        )
    )
    assert analysis.record_type == "mutilation_case"
    assert "historical_or_background_context_only" not in analysis.candidate_reasons


def test_plain_animal_death_without_mutilation_or_distinctive_findings_is_not_case():
    analysis = seed.analyze_source_record(source_record("A farmer found a dead cow in a field."))
    assert analysis.disposition == "not_candidate"
    assert analysis.record_type != "mutilation_case"


@pytest.mark.parametrize(
    ("text", "relationship_type"),
    [
        ("Una vaca mutilada fue encontrada dentro de un círculo de cultivo.", "same_scene"),
        ("Eine verstümmelte Kuh wurde in einem Kornkreis gefunden.", "same_scene"),
        ("Een verminkte koe werd in een graancirkel gevonden.", "same_scene"),
        ("Uma vaca mutilada foi encontrada dentro de um agroglifo.", "same_scene"),
    ],
)
def test_multilingual_crop_linked_animal_incidents(text, relationship_type):
    analysis = seed.analyze_source_record(source_record(text))
    assert analysis.record_type == "mutilation_case"
    assert analysis.crop_relationship_type == relationship_type


def test_unrelated_crop_cooccurrence_is_not_a_source_explicit_relationship():
    analysis = seed.analyze_source_record(
        source_record(
            "A mutilated cow was found in Colorado. Decades later, a book discusses a crop circle in England."
        )
    )
    assert analysis.record_type == "mutilation_case"
    assert analysis.crop_signal is True
    assert analysis.explicit_crop_mutilation_link is False
    assert analysis.crop_relationship_type is None


def test_researcher_and_skeptic_background_statements_are_not_cases():
    for text in (
        "A researcher investigated cattle mutilations for a book.",
        "Skeptics reported that cattle mutilation claims were a hoax.",
    ):
        analysis = seed.analyze_source_record(source_record(text))
        assert analysis.record_type != "mutilation_case"


def test_precision_limited_singleton_date_is_never_exact_day():
    comparison, score, offset = seed.compare_intervals(
        {"start": "2013-01-01", "end": "2013-01-01", "precision": "year"},
        {"start": "2013-01-01", "end": "2013-01-01", "precision": "exact_day"},
    )
    assert comparison == "precision_limited_overlap"
    assert score == 0.4
    assert offset == 0.0


def test_global_country_name_conflict_fails_closed():
    case = seed.build_candidate_record(
        source_record(
            "A mutilated cow was found.",
            city="San Martin",
            state_province=None,
            country="Argentina",
            location_raw="San Martin, Argentina",
            lat=None,
            lon=None,
        ),
        seed.analyze_source_record(
            source_record(
                "A mutilated cow was found.",
                city="San Martin",
                state_province=None,
                country="Argentina",
                location_raw="San Martin, Argentina",
                lat=None,
                lon=None,
            )
        ),
        1,
    )
    crop = {
        "lat": None,
        "lon": None,
        "location_precision": "city",
        "coordinate_uncertainty_km": 15,
        "crop_circle": {
            "place": "San Martin",
            "region": None,
            "country": "Chile",
            "country_code": None,
            "county": None,
        },
    }
    assert seed.compare_locations(case, crop)[0] == "incompatible"


def test_private_internal_coordinates_cannot_select_or_quantify_crop_match():
    record = source_record(
        "A mutilated horse was found at Smith Ranch.",
        date_raw="1975",
        date_iso="1975-01-01",
        end_date_iso="1975-12-31",
        date_precision="year",
        location_raw="Smith Ranch",
        city=None,
        state_province=None,
        country="US",
        lat=39.7392,
        lon=-104.9903,
        location_precision="unknown",
    )
    case = seed.build_candidate_record(record, seed.analyze_source_record(record), 1)
    crop = {
        "lat": 39.7392,
        "lon": -104.9903,
        "location_precision": "exact_site",
        "coordinate_uncertainty_km": 1,
        "crop_circle": {
            "place": None,
            "region": None,
            "country": "US",
            "country_code": "US",
            "county": None,
        },
    }

    assert case["location"]["privacy_level"] == "internal_only"
    assert case["location"]["latitude_internal"] == 39.7392
    assert case["location"]["latitude_public"] is None
    comparison, score, distance, _uncertainty, _warnings = seed.compare_locations(
        case,
        crop,
    )
    assert comparison == "same_country"
    assert score == 0.20
    assert distance is None


def test_anatomical_term_without_animal_context_is_not_candidate():
    analysis = seed.analyze_source_record(source_record("The witness injured an eye and jaw."))
    assert analysis.disposition == "not_candidate"


def test_research_and_aggregate_contexts_are_separate_record_types():
    research = seed.analyze_source_record(
        source_record("A researcher published a book reviewing cattle mutilation theories.")
    )
    aggregate = seed.analyze_source_record(
        source_record("An overview reported 30 cattle mutilation cases across Colorado.")
    )
    assert research.record_type == "publication_event"
    assert aggregate.record_type == "aggregate_report"
    assert research.needs_human_review and aggregate.needs_human_review


def test_quantified_aggregate_with_crop_context_never_promotes_to_incident():
    text = "There were 30 cattle mutilations across Colorado. Crop circles were also discussed."
    analysis = seed.analyze_source_record(source_record(text))
    assert analysis.record_type == "aggregate_report"
    assert analysis.explicit_crop_mutilation_link is False

    crop_source = seed._crop_source_candidate(
        source_kind="crop_assertion_packaged_narrative",
        source_id="aggregate_fixture",
        formation_ids=["cc_aggregate"],
        source_url=None,
        source_hash=seed.sha256_bytes(text.encode("utf-8")),
        text=text,
        analysis=analysis,
        provenance_locator="fixture",
    )
    assert seed.promote_crop_source_cases(
        [crop_source],
        [{"external_id": "cc_aggregate"}],
    ) == []


def test_mystery_helicopter_taxonomy_without_carcass_is_related_not_case():
    record = source_record(
        "A mystery helicopter was reported over the county.",
        type_raw="mystery helicopter/mutilation related",
        type_normalized="mystery_helicopter_mutilation_related",
    )
    analysis = seed.analyze_source_record(record)
    assert analysis.record_type == "related_aerial_event"
    assert "mutilation_related_source_type" in analysis.candidate_reasons


def test_structured_glossary_never_becomes_narrative_case():
    record = source_record("Unrelated light report")
    record["raw_fields"] = {
        "attributes/0": "ANI: Animals affected or sampled",
        "attributes/1": "INJ: Injuries illness death mutilations",
        "attributes/2": "VEG: Plants affected or sampled crop circles",
    }
    analysis = seed.analyze_source_record(record)
    assert analysis.disposition == "structured_code_review"
    assert analysis.record_type != "mutilation_case"
    assert analysis.explicit_crop_mutilation_link is False


def test_crop_source_candidate_scrubs_nested_animal_evidence():
    text = (
        "A mutilated pig was found at 1234 Ranch Road; contact "
        "rancher@example.com or 303-555-1212 near 39.7392, -104.9903."
    )
    analysis = seed.analyze_source_record(source_record(text))
    candidate = seed._crop_source_candidate(
        source_kind="crop_linked_source_page",
        source_id="https://example.invalid/private-evidence",
        formation_ids=["cc_private_fixture"],
        source_url="https://example.invalid/private-evidence",
        source_hash=seed.sha256_bytes(text.encode("utf-8")),
        text=text,
        analysis=analysis,
        provenance_locator="fixture",
    )
    public_text = json.dumps(candidate, ensure_ascii=False)
    assert "1234 Ranch Road" not in public_text
    assert "rancher@example.com" not in public_text
    assert "303-555-1212" not in public_text
    assert "39.7392" not in public_text
    assert "[street address withheld]" in public_text


def test_crop_source_deliberate_staging_is_contested_without_assigning_injury_cause():
    text = (
        "They planted a mutilated bird near the circle to create an eerie touch and "
        "to evoke memories of cattle mutilations."
    )
    analysis = seed.analyze_source_record(source_record(text))
    ufo_case = seed.build_candidate_record(source_record(text), analysis, 1)
    assert ufo_case["status"] == "contested"
    assert ufo_case["investigation"]["disposition"] == (
        "source_explicit_deliberate_placement_of_mutilated_animal"
    )
    candidate = seed._crop_source_candidate(
        source_kind="crop_linked_source_page",
        source_id="https://example.invalid/staged-bird",
        formation_ids=[],
        source_url="https://example.invalid/staged-bird",
        source_hash=seed.sha256_bytes(text.encode("utf-8")),
        text=text,
        analysis=analysis,
        provenance_locator="fixture",
    )
    assert candidate["source_explicit_human_staging"] is True
    assert "source_explicit_deliberate_human_staging" in candidate["candidate_reasons"]
    case = seed.build_crop_cattle_candidate(candidate, {})
    assert case["record_type"] == "mutilation_case"
    assert case["status"] == "contested"
    assert case["investigation"]["disposition"] == (
        "source_explicit_deliberate_placement_of_mutilated_animal"
    )
    assert [row["reported_taxon_key"] for row in case["animals"]] == ["bird"]
    assert [row["reported_taxon_key"] for row in case["animal_context"]] == ["cattle"]


@pytest.mark.parametrize(
    "description",
    [
        "A crop circle was cataloged at Cow Down.",
        "A formation was listed near Cow Drove Hill.",
        "The index names Fort Keogh Livestock Laboratory.",
        "The place label is Dead Man's Island.",
    ],
)
def test_animal_place_name_controls_are_not_candidates(description):
    assert seed.analyze_source_record(source_record(description)).disposition == "not_candidate"


def test_approximate_date_and_private_location_are_not_inflated():
    record = source_record(
        "A mutilated cow was discovered on a private ranch.",
        date_raw="about 2013",
        date_iso="2013-01-01",
        end_date_iso="2013-12-31",
        date_precision="year",
        location_raw="123 Ranch Road, Westport, New York",
        city="Westport",
        state_province="NY",
        country="US",
        location_precision="exact_site",
    )
    analysis = seed.analyze_source_record(record)
    candidate = seed.build_candidate_record(record, analysis, 7)
    assert candidate["dates"]["precision"] == "year"
    assert candidate["dates"]["event_start"] == "2013-01-01"
    assert candidate["dates"]["event_end"] == "2013-12-31"
    assert candidate["location"]["privacy_level"] == "internal_only"
    assert candidate["location"]["latitude_public"] is None
    assert candidate["location"]["longitude_public"] is None
    assert candidate["location"]["raw_text"] == "Westport, NY, US"
    assert candidate["location"]["locality"] == "Westport"


def test_named_private_property_is_removed_from_all_public_case_evidence():
    text = "A mutilated cow was found at smith ranch after a light was reported."
    record = source_record(
        text,
        date_raw="2013-08-01",
        date_iso="2013-08-01",
        end_date_iso="2013-08-01",
        location_raw="smith ranch, Westport, New York",
        city="Westport",
        state_province="NY",
        country="US",
        location_precision="exact_site",
    )
    case = seed.build_candidate_record(record, seed.analyze_source_record(record), 1)
    public_text = json.dumps(case, ensure_ascii=False)
    assert case["location"]["privacy_level"] == "internal_only"
    assert "smith ranch" not in public_text.casefold()
    assert "[private property withheld]" in public_text
    assert "smith ranch" not in (case["summary"] or "").casefold()
    assert all(
        "smith ranch" not in (animal.get("evidence_excerpt") or "").casefold()
        for animal in [*case["animals"], *case["animal_context"]]
    )
    assert all(
        "smith ranch" not in sentence.casefold()
        for sentence in case["extraction"]["incident_evidence_sentences"]
    )


def test_named_private_property_is_removed_from_crop_candidate_and_promoted_case():
    text = (
        "A mutilated sheep was found at jesse and frank ranch beside the crop "
        "formation."
    )
    analysis = seed.analyze_source_record(source_record(text))
    candidate = seed._crop_source_candidate(
        source_kind="crop_linked_source_page",
        source_id="https://example.invalid/private-crop-case",
        formation_ids=[],
        source_url="https://example.invalid/private-crop-case",
        source_hash=seed.sha256_bytes(text.encode("utf-8")),
        text=text,
        analysis=analysis,
        provenance_locator="fixture",
        location={
            "raw_text": "jesse and frank ranch, Wiltshire",
            "place": "jesse and frank ranch",
            "region": "Wiltshire",
            "country_code": "GB",
        },
    )
    promoted = seed.build_crop_cattle_candidate(candidate, {})
    for row in (candidate, promoted):
        public_text = json.dumps(row, ensure_ascii=False)
        assert "jesse and frank ranch" not in public_text.casefold()
        assert "jesse" not in public_text.casefold()
        assert "frank ranch" not in public_text.casefold()
        assert "[private property withheld]" in public_text


def test_multi_name_private_property_is_redacted_as_one_label():
    excerpt = seed.sanitize_public_excerpt(
        "A mutilated cow was found at Jesse and Frank Ranch.",
        withhold_named_private_property=True,
    )
    assert excerpt == "A mutilated cow was found at [private property withheld]."


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Black calf mutilated John Catalano ranch, 6 miles south of Alamosa.",
            "Black calf mutilated [private property withheld], 6 miles south of Alamosa.",
        ),
        (
            "Black calf mutilated john catalano ranch, 6 miles south of Alamosa.",
            "Black calf mutilated [private property withheld], 6 miles south of Alamosa.",
        ),
        (
            "Calf Mutilated John Catalano Ranch.",
            "Calf Mutilated [private property withheld].",
        ),
        (
            "Steer found mutilated Medano Ranch Classic Ted Carpenter.",
            "Steer found mutilated [private property withheld] Classic Ted Carpenter.",
        ),
        (
            "Horse mutilations reported on the farm that same year.",
            "Horse mutilations reported on the farm that same year.",
        ),
        (
            "2 mutilated dogs were found near 1234 Ranch Road.",
            "2 mutilated dogs were found near [street address withheld].",
        ),
        (
            "Mutilated black calf at Mitchell Ranch.",
            "Mutilated black calf at [private property withheld].",
        ),
        (
            "2 year old steer mutilation at Medano Ranch.",
            "2 year old steer mutilation at [private property withheld].",
        ),
        (
            "Cat Taylor Ranch was found mutilated.",
            "Cat [private property withheld] was found mutilated.",
        ),
        (
            "Horse Gutted Medano Ranch during the incident.",
            "Horse Gutted [private property withheld] during the incident.",
        ),
        (
            "Bird bloodless at Hollenbeck Ranch after discovery.",
            "Bird bloodless at [private property withheld] after discovery.",
        ),
        (
            "Taylor Ranch horse was found mutilated.",
            "[private property withheld] horse was found mutilated.",
        ),
        (
            "john catalano ranch horse was found mutilated.",
            "[private property withheld] horse was found mutilated.",
        ),
        (
            "Two mutilated dogs were recovered at 12-14 Smith Road.",
            "Two mutilated dogs were recovered at [street address withheld].",
        ),
    ],
)
def test_private_locator_redaction_preserves_animal_and_harm_anchors(text, expected):
    assert (
        seed.sanitize_public_excerpt(
            text,
            withhold_named_private_property=True,
        )
        == expected
    )


def test_markdown_locator_is_removed_before_named_property_redaction():
    excerpt = seed.sanitize_public_excerpt(
        "A horse at [Harry King](https://example.invalid/memorial/123) Ranch was mutilated.",
        withhold_named_private_property=True,
    )
    assert excerpt == "A horse at [private property withheld] was mutilated."


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "A horse at [Harry King](https://example.invalid/a_(nested)/memorial) Ranch was mutilated.",
            "A horse at [private property withheld] was mutilated.",
        ),
        (
            "A horse at [Harry King][owner] Ranch was mutilated.\n"
            "[owner]: https://example.invalid/a_(nested)/memorial",
            "A horse at [private property withheld] was mutilated.",
        ),
        (
            "A horse at [Harry King][] Ranch was mutilated.",
            "A horse at [private property withheld] was mutilated.",
        ),
        (
            "A horse was mutilated; see <https://example.invalid/a_(nested)> for the report.",
            "A horse was mutilated; see for the report.",
        ),
        (
            "A horse was mutilated; see https://example.invalid/a_(nested) for the report.",
            "A horse was mutilated; see for the report.",
        ),
        (
            "A horse at [Harry King](https://example.invalid/truncated was mutilated.",
            "A horse at Harry King was mutilated.",
        ),
        (
            "A horse ](https://example.invalid/truncated was mutilated.",
            "A horse was mutilated.",
        ),
    ],
)
def test_all_public_link_forms_are_removed_without_losing_incident_anchors(
    text, expected
):
    excerpt = seed.sanitize_public_excerpt(
        text,
        withhold_named_private_property=True,
    )
    assert excerpt == expected
    assert "horse" in excerpt.casefold()
    assert "mutilat" in excerpt.casefold()
    assert not seed.contains_public_link_locator(excerpt)


def test_short_evidence_strips_urls_before_truncating_the_evidence_window():
    text = (
        "Background [source](https://example.invalid/" + "x" * 500 + ") "
        "then a horse was found mutilated beside the road."
    )
    excerpt = seed.short_evidence_excerpt(
        text,
        ("horse", "mutilated"),
        max_words=12,
        max_chars=120,
    )
    assert excerpt is not None
    assert "horse" in excerpt.casefold()
    assert "mutilat" in excerpt.casefold()
    assert not seed.contains_public_link_locator(excerpt)


@pytest.mark.parametrize(
    "text",
    [
        "A mutilated cat was found at john catalano ranch.",
        "A horse at [Harry King](https://example.invalid/a_(nested)) Ranch was mutilated.",
        "A bird was found at 12-14 Smith Road; see <https://example.invalid/report>.",
        "A dog ](https://example.invalid/truncated was found mutilated.",
    ],
)
def test_public_excerpt_sanitization_is_idempotent(text):
    once = seed.sanitize_public_excerpt(
        text,
        withhold_named_private_property=True,
    )
    twice = seed.sanitize_public_excerpt(
        once,
        withhold_named_private_property=True,
    )
    assert once == twice


def test_lowercase_multiword_property_is_removed_from_ufo_case_end_to_end():
    text = "A mutilated calf was found at john catalano ranch after a light appeared."
    record = source_record(
        text,
        location_raw="john catalano ranch, Alamosa, Colorado",
        city="Alamosa",
        state_province="CO",
        country="US",
        location_precision="unknown",
        date_iso="1975-01-01",
        date_precision="year",
    )
    case = seed.build_candidate_record(record, seed.analyze_source_record(record), 1)
    public_text = json.dumps(case, ensure_ascii=False).casefold()
    assert "john catalano ranch" not in public_text
    assert "john catalano" not in public_text
    assert "calf" in (case["summary"] or "").casefold()
    assert "mutilat" in (case["summary"] or "").casefold()
    assert case["location"]["privacy_level"] == "internal_only"
    assert case["location"]["latitude_public"] is None
    assert case["location"]["longitude_public"] is None


def test_public_incident_evidence_uses_bounded_victim_assertions_only():
    text = (
        "A horse at [Harry King](https://example.invalid/memorial/123) Ranch was "
        "found mutilated. [Nellie Lewis](https://example.invalid/person/456) later "
        "discussed the report."
    )
    record = source_record(
        text,
        location_raw="Harry King Ranch, Alamosa, Colorado",
        city="Alamosa",
        state_province="CO",
        country="US",
    )
    case = seed.build_candidate_record(record, seed.analyze_source_record(record), 1)
    evidence = case["extraction"]["incident_evidence_sentences"]
    assert evidence
    assert all("horse" in value.casefold() for value in evidence)
    assert all("mutilat" in value.casefold() for value in evidence)
    assert all("http" not in value.casefold() for value in evidence)
    assert all("ranch" not in value.casefold() for value in evidence)


def test_historical_named_property_always_suppresses_public_coordinates():
    record = source_record(
        "A mutilated horse was found at Taylor Ranch.",
        date_raw="1967",
        date_iso="1967-01-01",
        end_date_iso="1967-12-31",
        date_precision="year",
        location_raw="Taylor Ranch, Alamosa, Colorado",
        city="Alamosa",
        state_province="CO",
        country="US",
        location_precision="unknown",
    )
    case = seed.build_candidate_record(record, seed.analyze_source_record(record), 1)
    location = case["location"]
    assert location["privacy_level"] == "internal_only"
    assert location["latitude_public"] is None
    assert location["longitude_public"] is None
    assert location["locality"] == "Alamosa"
    assert location["raw_text"] == "Alamosa, CO, US"
    assert "taylor ranch" not in json.dumps(case, ensure_ascii=False).casefold()


def test_historical_named_property_validation_provenance_requires_suppression():
    record = source_record(
        "A mutilated horse was found at Smith Ranch.",
        date_raw="1975",
        date_iso="1975-01-01",
        end_date_iso="1975-12-31",
        date_precision="year",
        location_raw="Smith Ranch",
        city=None,
        location_precision="unknown",
    )
    case = seed.build_candidate_record(record, seed.analyze_source_record(record), 1)
    decision = seed._build_ufo_validation_decision(record, case)

    assert decision["source_location"]["named_private_signal"] is True
    assert decision["source_location"]["public_suppression_required"] is True
    assert case["location"]["privacy_level"] == "internal_only"
    assert case["location"]["latitude_public"] is None
    assert case["location"]["longitude_public"] is None
    seed._validate_case_decision(case, decision)


def test_private_property_name_in_city_field_is_not_republished():
    record = source_record(
        "A mutilated cow was discovered after lights circled overhead.",
        date_iso="1995-06-01",
        date_precision="exact_day",
        location_raw="JESSE PICKUP RANCH, US",
        city="JESSE PICKUP RANCH",
        country="US",
        location_precision="exact_site",
    )
    location = seed.project_location(record)
    assert location["privacy_level"] == "internal_only"
    assert location["raw_text"] == "TX, US"
    assert "RANCH" not in location["raw_text"]
    assert location["locality"] is None
    assert location["precision"] == "unknown"
    assert location["latitude_public"] is None
    assert location["longitude_public"] is None

    legacy_case = {"location": dict(location)}
    legacy_case["location"].update(
        {
            "raw_text": "JESSE PICKUP RANCH, TX, US",
            "locality": "JESSE PICKUP RANCH",
            "precision": "locality",
            "latitude_public": 31.0,
            "longitude_public": -100.0,
        }
    )
    seed._enforce_private_public_location(legacy_case)
    assert legacy_case["location"]["raw_text"] == "TX, US"
    assert legacy_case["location"]["locality"] is None
    assert legacy_case["location"]["precision"] == "unknown"
    assert legacy_case["location"]["latitude_public"] is None
    assert legacy_case["location"]["longitude_public"] is None


def test_start_only_uncertain_dates_are_not_collapsed_to_exact_days():
    approximate = source_record(
        "A mutilated cow was found.",
        date_iso="1994-01-01",
        end_date_iso=None,
        date_precision="approximate",
    )
    candidate = seed.build_candidate_record(
        approximate,
        seed.analyze_source_record(approximate),
        1,
    )
    assert candidate["dates"]["event_start"] == "1994-01-01"
    assert candidate["dates"]["event_end"] is None
    assert candidate["dates"]["precision"] == "approximate"

    assert seed.normalized_date_interval("2013-01-01", None, "year") == {
        "start": "2013-01-01",
        "end": "2013-12-31",
        "precision": "year",
    }
    assert seed.normalized_date_interval("1975-03-01", None, "month") == {
        "start": "1975-03-01",
        "end": "1975-03-31",
        "precision": "month",
    }
    assert seed.normalized_date_interval("1980-01-01", None, "range")["end"] is None
    assert seed._date_interval_from_crop(
        {
            "date_iso": "1994-01-01",
            "end_date_iso": "1994-01-01",
            "date_precision": "approximate",
        }
    )["end"] is None


def test_legacy_html_source_anchor_is_not_promoted_to_a_public_url():
    record = source_record("A mutilated cow was found.", source_url='<a href="timeline.html#ABC">case</a>')
    candidate = seed.build_candidate_record(record, seed.analyze_source_record(record), 1)
    assert candidate["sources"][0]["url"] is None


def test_absolute_url_embedded_in_source_anchor_is_preserved():
    value = '<a href="https://example.invalid/case?a=1&amp;b=2">case</a>'
    assert seed.public_http_url(value) == "https://example.invalid/case?a=1&b=2"


def test_visible_text_honors_legacy_page_charset():
    body = (
        '<html><head><meta charset="windows-1252"></head>'
        "<body>Uma vaca mutilada foi encontrada perto da formação.</body></html>"
    ).encode("cp1252")
    text = seed._extract_visible_text(body, content_type="text/html")
    assert "formação" in text


def test_wrong_state_crop_event_is_incompatible_even_when_locality_matches():
    case_record = source_record("A mutilated dog was found in a crop circle.")
    case_record.update(city="Gallipolis", state_province="OH", location_raw="Gallipolis, Ohio")
    case = seed.build_candidate_record(case_record, seed.analyze_source_record(case_record), 1)
    crop = {
        "lat": None,
        "lon": None,
        "location_precision": "city",
        "coordinate_uncertainty_km": 15,
        "crop_circle": {
            "place": "Gallipolis",
            "region": "Pennsylvania",
            "country": "United States",
            "country_code": "US",
            "county": None,
        },
    }
    comparison, score, _, _, warnings = seed.compare_locations(case, crop)
    assert comparison == "incompatible"
    assert score == 0
    assert "admin1_conflict" in warnings


def test_known_crop_country_assignment_error_is_corrected_for_matching_only():
    code, warning = seed.normalize_country("US", region="Cambridgeshire", place="Fulbourn")
    assert code == "GB"
    assert warning == "country_assignment_corrected_from_US_to_GB"


def test_duplicate_relationship_merge_keeps_coherent_components_and_recomputes_score():
    subject = {
        "domain": "animal_mutilation",
        "dataset": "fixture",
        "external_id": "cmi_fixture",
        "native_event_id": "cmi_fixture",
    }
    object_ref = {
        "domain": "ufo",
        "dataset": "fixture",
        "external_id": "evt_fixture",
        "native_event_id": "evt_fixture",
    }

    def relationship(*, temporal_score, spatial_score, source_score, locator, source_id):
        return seed.make_relationship(
            subject=subject,
            object_ref=object_ref,
            relationship_type="duplicate_lineage",
            assertion_mode="explicit_source",
            match_tier=2,
            temporal={
                "subject_interval": {"start": None, "end": None, "precision": "unknown"},
                "object_interval": {"start": None, "end": None, "precision": "unknown"},
                "comparison": "exact_day" if temporal_score else "unknown",
                "offset_days": 0.0 if temporal_score else None,
                "score": temporal_score,
            },
            spatial={
                "subject_precision": "locality" if spatial_score else "unknown",
                "object_precision": "locality" if spatial_score else "unknown",
                "comparison": "same_locality" if spatial_score else "unknown",
                "distance_km": 0.0 if spatial_score else None,
                "uncertainty_km": 15.0 if spatial_score else None,
                "score": spatial_score,
            },
            source_refs=[
                {
                    "source_id": source_id,
                    "supports": "explicit_relationship",
                    "locator": locator,
                    "source_hash": None,
                }
            ],
            reasons=["native_ufo_event_lineage"],
            source_component=source_score,
            review_state="needs_human_review",
            provenance_locator=locator,
        )

    source_strong = relationship(
        temporal_score=0.0,
        spatial_score=0.0,
        source_score=1.0,
        locator="low-components",
        source_id="source:low",
    )
    component_strong = relationship(
        temporal_score=1.0,
        spatial_score=1.0,
        source_score=0.2,
        locator="high-components",
        source_id="source:high",
    )
    assert source_strong["relationship_id"] == component_strong["relationship_id"]

    forward = seed._merge_relationship_rows([source_strong, component_strong])
    reverse = seed._merge_relationship_rows([component_strong, source_strong])
    assert forward == reverse
    assert len(forward) == 1
    merged = forward[0]
    assert merged["temporal"]["score"] == 1.0
    assert merged["spatial"]["score"] == 1.0
    assert merged["scores"] == {
        "relationship_compatibility": 1.0,
        "temporal_component": 1.0,
        "spatial_component": 1.0,
        "source_component": 1.0,
    }
    assert {row["source_id"] for row in merged["source_refs"]} == {
        "source:high",
        "source:low",
    }


def test_relationship_contract_keeps_explicit_and_computed_lanes_separate():
    case = seed.build_candidate_record(
        source_record("A mutilated cow was found in a crop circle."),
        seed.analyze_source_record(source_record("A mutilated cow was found in a crop circle.")),
        1,
    )
    case["record_id"] = "cmi_fixture"
    case["canonical_incident_id"] = "cmi_fixture"
    explicit = seed.make_relationship(
        subject=seed._case_endpoint(case),
        object_ref={
            "domain": "crop_circle",
            "dataset": "source_story",
            "external_id": "ccsc_fixture",
            "native_event_id": "fixture",
        },
        relationship_type="same_scene",
        assertion_mode="explicit_source",
        match_tier=1,
        temporal=seed._same_event_temporal(case),
        spatial=seed._same_event_spatial(case),
        source_refs=seed._relationship_source_refs(case, "explicit_relationship"),
        reasons=["source_explicit"],
        source_component=1.0,
        review_state="needs_human_review",
        provenance_locator="fixture",
    )
    computed = seed.make_relationship(
        subject=seed._case_endpoint(case),
        object_ref={
            "domain": "crop_circle",
            "dataset": "crop_circle_atlas_export_v1",
            "external_id": "cc_fixture",
            "native_event_id": 1,
        },
        relationship_type="regional_context",
        assertion_mode="deterministic_match",
        match_tier=4,
        temporal=seed._same_event_temporal(case),
        spatial=seed._same_event_spatial(case),
        source_refs=seed._relationship_source_refs(case, "temporal_component"),
        reasons=["computed_candidate_not_source_assertion"],
        source_component=0.5,
        review_state="needs_human_review",
        provenance_locator="fixture-computed",
    )
    assert explicit["assertion_mode"] == "explicit_source"
    assert computed["assertion_mode"] == "deterministic_match"
    assert explicit["causality"] == computed["causality"] == "not_asserted"
    assert explicit["relationship_id"] != computed["relationship_id"]


def test_aerial_relationship_requires_local_animal_incident_link():
    def relationship_modes(description):
        record = source_record(description)
        candidate = seed.build_candidate_record(record, seed.analyze_source_record(record), 1)
        wrapper = {
            "candidate": candidate,
            "ufo_event_id": "evt_fixture",
            "ufo_event_native_id": "fixture-native",
        }
        incidents, _, _ = seed.cluster_candidates([wrapper])
        relationships, _ = seed.build_relationships([wrapper], incidents, [], [])
        return candidate, relationships

    remote, remote_relationships = relationship_modes(
        "A mutilated cow was found on the ranch. Years earlier, a UFO conference was held in another state."
    )
    assert "ufo" in remote["association_terms"]
    assert remote["explicit_aerial_association_terms"] == []
    assert [row["assertion_mode"] for row in remote_relationships] == ["deterministic_match"]

    local, local_relationships = relationship_modes(
        "A mutilated cow was found while an unmarked helicopter hovered nearby."
    )
    assert any("helicopter" in term for term in local["explicit_aerial_association_terms"])
    explicit = [row for row in local_relationships if row["assertion_mode"] == "explicit_source"]
    assert len(explicit) == 1
    assert explicit[0]["relationship_type"] == "reported_nearby"


def test_computed_matching_scans_full_multi_decade_interval():
    record = source_record(
        "A mutilated cow was found.",
        date_iso="1980-01-01",
        end_date_iso="2000-12-31",
        date_precision="range",
    )
    candidate = seed.build_candidate_record(record, seed.analyze_source_record(record), 1)
    candidate["record_id"] = "cmi_multi_decade"
    candidate["canonical_incident_id"] = "cmi_multi_decade"
    crop = {
        "external_id": "cc_1998",
        "event_id": 1998,
        "date_iso": "1998-06-15",
        "end_date_iso": "1998-06-15",
        "date_precision": "exact_day",
        "location_precision": "city",
        "coordinate_uncertainty_km": 15,
        "lat": 33.6,
        "lon": -102.6,
        "original_entry_url": "https://example.invalid/crop/1998",
        "crop_circle": {
            "place": "Whiteface",
            "region": "Texas",
            "country": "United States",
            "country_code": "US",
            "county": None,
        },
    }
    relationships, _ = seed.build_relationships([], [candidate], [crop], [])
    computed = [row for row in relationships if row["assertion_mode"] == "deterministic_match"]
    assert len(computed) == 1
    assert computed[0]["object"]["external_id"] == "cc_1998"
    assert computed[0]["temporal"]["comparison"] == "overlapping_interval"


def test_crop_linked_source_incident_is_promoted_and_linked_to_formation():
    source_candidate = {
        "crop_source_candidate_id": "ccsc_fixture",
        "source_kind": "crop_linked_source_page",
        "source_id": "https://example.invalid/crop-case",
        "formation_ids": ["cc_fixture"],
        "source_url": "https://example.invalid/crop-case",
        "source_hash": "b" * 64,
        "provenance_locator": "https://example.invalid/crop-case",
        "dates": {},
        "location": {},
        "classification": "candidate",
        "record_type": "mutilation_case",
        "crop_relationship_type": "same_scene",
        "candidate_score": 0.8,
        "candidate_reasons": ["explicit_animal_mutilation_phrase"],
        "direct_animal_terms": ["cattle"],
        "finding_terms": ["mutilated"],
        "explicit_negative": False,
        "evidence_excerpt": "A mutilated cow was found inside the crop formation.",
    }
    crop_event = {
        "external_id": "cc_fixture",
        "event_id": 77,
        "date_iso": "2001-07-10",
        "end_date_iso": "2001-07-10",
        "date_precision": "exact_day",
        "location_precision": "city",
        "coordinate_uncertainty_km": 15,
        "lat": 51.0,
        "lon": -1.0,
        "original_entry_url": "https://example.invalid/atlas/cc_fixture",
        "crop_circle": {
            "place": "Fixtureton",
            "region": "Wiltshire",
            "country": "United Kingdom",
            "country_code": "GB",
            "county": None,
        },
    }
    wrappers = seed.promote_crop_source_cases([source_candidate], [crop_event])
    assert len(wrappers) == 1
    case = wrappers[0]["candidate"]
    assert case["record_type"] == "mutilation_case"
    assert case["location"]["precision"] == "approximate"
    assert case["location"]["latitude_public"] is None
    incidents, _, _ = seed.cluster_candidates(wrappers)
    relationships, _ = seed.build_relationships(wrappers, incidents, [crop_event], [source_candidate])
    explicit = [row for row in relationships if row["assertion_mode"] == "explicit_source"]
    assert len(explicit) == 1
    assert explicit[0]["relationship_type"] == "same_scene"
    assert explicit[0]["object"]["external_id"] == "cc_fixture"
    assert explicit[0]["causality"] == "not_asserted"
    assert case["external_event_refs"][0]["relationship_id"] == explicit[0]["relationship_id"]


@pytest.mark.parametrize(
    ("native_id", "date_iso", "precision", "city", "region", "country", "description", "relationship_type"),
    [
        ("Hatch_UDB_11636", "1975-03-10", "exact_day", "WHITEFACE, TX", "Texas", "USA", "Surgically mutilated cow was found in a 30-foot crop circle.", "same_scene"),
        ("Hatch_UDB_9996", "1972-06-01", "month", "WEST / PELOTAS, BRZ", "RGS", "Brazil", "300 sheep mutilated. Blood drained. One was found in a crop circle.", "same_scene"),
        ("130482", "1994-05-10", "exact_day", "EAGLE NEST", "NM", "US", "Two cows were found mutilated near Eagle Nest; cauterized incisions were reported.", None),
        ("88403", "1966-11-15", "exact_day", "GALLIPOLIS", "OH", "US", "A dog was found crushed and bloodless in a crop circle.", "same_scene"),
        ("5474244", "2013-08-01", "exact_day", "WESTPORT", "NY", "US", "Crop circles had been found in the same area. A farmer also discovered his sheep gutted and turned inside out.", "topical_context"),
        ("48962", "1994-01-01", "approximate", "Het Twiske", None, "Netherlands", "In this area there were crop circles and some very mashed up cows.", "topical_context"),
    ],
)
def test_named_case_regressions_preserve_native_date_and_place(
    native_id, date_iso, precision, city, region, country, description, relationship_type
):
    end_date = "1972-06-30" if precision == "month" else date_iso
    record = source_record(
        description,
        source_native_id=native_id,
        date_raw=date_iso,
        date_iso=date_iso,
        end_date_iso=end_date,
        date_precision=precision,
        city=city,
        state_province=region,
        country=country,
        location_raw=", ".join(str(value) for value in (city, region, country) if value),
    )
    analysis = seed.analyze_source_record(record)
    assert analysis.record_type == "mutilation_case"
    assert analysis.crop_relationship_type == relationship_type
    candidate = seed.build_candidate_record(record, analysis, 1)
    assert candidate["provenance"]["source_native_id"] == native_id
    assert candidate["dates"]["event_start"] == date_iso
    assert candidate["dates"]["precision"] == precision
    assert candidate["location"]["locality"] == city


def test_oregon_nonclassic_death_source_is_negative_context():
    analysis = seed.analyze_source_record(
        source_record(
            "A healthy steer was found dead. No marks or injuries were visible on the initial find; "
            "coyotes possibly disturbed the carcass later. The region had cattle mutilations and a crop circle in the 1990s.",
            source_native_id="183024",
            date_iso="2023-01-19",
            end_date_iso="2023-01-19",
            date_precision="exact_day",
            city="Sprague River",
            state_province="OR",
            country="US",
        )
    )
    assert analysis.explicit_negative is True
    assert analysis.negative_only is True
    assert analysis.record_type != "mutilation_case"
    assert analysis.explicit_crop_mutilation_link is False


def test_crop_image_alt_and_title_narratives_each_receive_a_disposition(monkeypatch, tmp_path):
    monkeypatch.setattr(
        seed,
        "scan_catalog_pdf",
        lambda _path: {
            "counts": {
                "pages": 0,
                "slots": 0,
                "index_only_pages": 0,
                "narrative_present_pages": 0,
            },
            "pages": [],
            "slots": [],
        },
    )
    crop_event = {
        "external_id": "cc_image_fixture",
        "event_id": 1,
        "date_iso": "2001-07-10",
        "end_date_iso": "2001-07-10",
        "date_precision": "exact_day",
        "location_precision": "city",
        "crop_circle": {
            "place": "Fixtureton",
            "region": "Wiltshire",
            "country": "United Kingdom",
            "country_code": "GB",
        },
    }
    image_links = [
        {
            "image_link_id": "image_story",
            "formation_id": "cc_image_fixture",
            "source_record_url": "https://example.invalid/source-story",
            "image_url": "https://images.invalid/ordinary.jpg",
            "image_kind": "formation_photo",
            "alt_text": "A mutilated cow was found inside the crop circle.",
            "title_text": "Detail view",
            "rights_status": "metadata_only",
        },
        {
            "image_link_id": "image_taxonomy_bait",
            "formation_id": "cc_image_fixture",
            "source_record_url": "https://example.invalid/no-signal",
            "image_url": "https://images.invalid/mutilated-cow-crop-circle.jpg",
            "image_kind": "cattle_mutilation",
            "alt_text": "Landscape photograph",
            "title_text": "",
            "rights_status": "metadata_only",
        },
    ]
    candidates, audit, summary = seed.scan_crop_sources(
        {
            "events": [crop_event],
            "assertions": [],
            "image_links": image_links,
            "targets": [],
            "assertion_url_count": 0,
            "listing_source_urls": [],
        },
        catalog_pdf_path=tmp_path / "catalog.pdf",
        acquisition_audit_path=None,
        private_cache_dir=None,
        allow_partial=True,
    )

    image_audit = [row for row in audit if row["item_kind"].startswith("crop_image_")]
    assert len(image_audit) == 3
    assert len({row["item_id"] for row in image_audit}) == 3
    assert summary["crop_image_alt_text_narratives_scanned"] == 2
    assert summary["crop_image_title_text_narratives_scanned"] == 1
    assert summary["crop_image_narrative_candidates"] == 1
    image_candidates = [
        row for row in candidates if row["source_kind"] == "crop_image_packaged_narrative"
    ]
    assert len(image_candidates) == 1
    assert image_candidates[0]["record_type"] == "mutilation_case"
    assert image_candidates[0]["source_url"] == "https://example.invalid/source-story"
    assert "images.invalid" not in (image_candidates[0]["evidence_excerpt"] or "")
    bait_audit = [
        row for row in image_audit if row["source_record_url"] == "https://example.invalid/no-signal"
    ]
    assert [row["disposition"] for row in bait_audit] == ["packaged_narrative_no_signal"]


def test_seed_report_separates_review_lanes_and_required_distributions():
    public_case_record = source_record(
        "A mutilated cow was found in a crop circle.",
        coordinate_source="reported coordinates",
    )
    public_case = seed.build_candidate_record(
        public_case_record,
        seed.analyze_source_record(public_case_record),
        1,
    )
    public_case["canonical_incident_id"] = "cmi_report_fixture"
    public_case["extraction"]["candidate_score"] = 0.85

    private_negative_record = source_record(
        "The cow died, but did not have classic mutilation features.",
        canonical_input_id="cin_private_negative",
        source_native_id="private_negative",
        date_raw="about 2013",
        date_iso="2013-01-01",
        end_date_iso="2013-12-31",
        date_precision="year",
        location_raw="123 Ranch Road, Westport, New York",
        city="Westport",
        state_province="NY",
        location_precision="exact_site",
        coordinate_source="locality centroid",
    )
    private_negative = seed.build_candidate_record(
        private_negative_record,
        seed.analyze_source_record(private_negative_record),
        2,
    )
    private_negative["provenance"]["review_state"] = "rejected_as_noise"
    private_negative["extraction"]["candidate_score"] = 0.15

    report = seed.build_seed_report(
        scan_summary={"scanned": 2, "malformed": 1},
        lineage_summary={
            "deduped_events_scanned": 2,
            "candidate_input_ids_without_lineage": 1,
        },
        crop_summary={
            "crop_events_scanned": 2,
            "crop_assertions_scanned": 3,
            "crop_assertion_unique_source_urls": 2,
            "crop_unique_source_urls_scanned": 3,
            "catalog_pages_scanned": 1,
            "catalog_slots_scanned": 4,
            "crop_source_access_gaps": 7,
        },
        candidates=[public_case, private_negative],
        canonical_incidents=[
            {
                "record_id": "cmi_report_fixture",
                "constituent_record_ids": [
                    public_case["record_id"],
                    private_negative["record_id"],
                ],
            }
        ],
        related_events=[private_negative],
        rejected=[private_negative],
        duplicate_pairs=[{"review_state": "provisional_cluster"}],
        relationships=[
            {
                "assertion_mode": "explicit_source",
                "relationship_type": "same_scene",
                "review_state": "needs_human_review",
                "match_tier": 1,
            },
            {
                "assertion_mode": "deterministic_match",
                "relationship_type": "regional_context",
                "review_state": "rejected",
                "match_tier": 4,
            },
        ],
        crop_source_candidates=[],
    )

    required_sections = (
        "## Explicit source relationships",
        "## Computed review candidates",
        "## Reviewed rejections",
        "## Unresolved source access",
        "## Privacy generalization",
        "## Extraction false-positive and control queue",
        "### Date precision",
        "### Coordinate source",
        "### Location precision",
        "### Mapped / unmapped",
        "### Candidate-score band",
        "### Provisional duplicate-cluster size",
        "## Warnings and unresolved questions",
    )
    assert all(section in report for section in required_sections)
    assert "Total explicit-source relationships: 1" in report
    assert "Total deterministic-match candidates: 1" in report
    assert "Cross-domain relationships explicitly rejected during review: 1" in report
    assert "Candidate records explicitly marked `rejected_as_noise`: 1" in report
    assert "Crop source URLs without usable content: 7" in report
    assert "Candidate records with generalized/suppressed private locations: 1" in report
    assert "Internal coordinates available: 2" in report
    assert "Public coordinates available: 1" in report
    assert "`0.00-0.19`: 1" in report
    assert "`0.80-1.00`: 1" in report
    assert "`2` constituent source records: 1 cluster" in report


def test_stream_scan_records_every_row_and_malformed_input(tmp_path):
    source_path = tmp_path / "source_records.jsonl"
    rows = [
        source_record("A mutilated cow was found."),
        source_record("Ordinary light report", canonical_input_id="cin_other"),
    ]
    source_path.write_text(
        "\n".join([json.dumps(rows[0]), "{malformed", json.dumps(rows[1])]) + "\n",
        encoding="utf-8",
    )
    wrappers, summary = seed.scan_ufo_source_records(source_path, tmp_path / "work", resume=False, limit=None)
    assert summary["scanned"] == 3
    assert summary["malformed"] == 1
    assert len(wrappers) == 1
    with Path(summary["audit_spool"]).open(encoding="utf-8", newline="") as handle:
        audit = list(csv.DictReader(handle))
    assert [row["disposition"] for row in audit] == ["candidate", "malformed", "not_candidate"]


def test_stream_resume_truncates_uncheckpointed_spool_writes(tmp_path):
    source_path = tmp_path / "source_records.jsonl"
    rows = [
        source_record(
            "A mutilated cow was found.",
            canonical_input_id="cin_1",
            source_native_id="one",
            source_row_hash="1" * 40,
        ),
        source_record(
            "Ordinary light report.",
            canonical_input_id="cin_2",
            source_native_id="two",
            source_row_hash="2" * 40,
        ),
        source_record(
            "A sheep was found mutilated.",
            canonical_input_id="cin_3",
            source_native_id="three",
            source_row_hash="3" * 40,
        ),
        source_record(
            "Another ordinary light report.",
            canonical_input_id="cin_4",
            source_native_id="four",
            source_row_hash="4" * 40,
        ),
    ]
    source_path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    work_dir = tmp_path / "work"
    first_wrappers, first_summary = seed.scan_ufo_source_records(
        source_path, work_dir, resume=False, limit=2
    )
    assert len(first_wrappers) == 1
    checkpoint_path = Path(first_summary["checkpoint"])
    first_checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert first_checkpoint["complete"] is False

    candidate_spool = Path(first_summary["candidate_spool"])
    audit_spool = Path(first_summary["audit_spool"])
    candidate_spool.write_bytes(candidate_spool.read_bytes() + candidate_spool.read_bytes())
    with audit_spool.open("ab") as handle:
        handle.write(b"uncheckpointed,audit,row\n")

    wrappers, summary = seed.scan_ufo_source_records(
        source_path, work_dir, resume=True, limit=None
    )
    assert summary["scanned"] == 4
    assert summary["candidates_written"] == 2
    assert len(wrappers) == 2
    assert len({wrapper["candidate"]["record_id"] for wrapper in wrappers}) == 2
    with audit_spool.open(encoding="utf-8", newline="") as handle:
        audit = list(csv.DictReader(handle))
    assert [int(row["source_index"]) for row in audit] == [1, 2, 3, 4]

    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint["checkpoint_schema_version"] == 2
    assert checkpoint["pipeline_version"] == seed.PIPELINE_VERSION
    assert checkpoint["complete"] is True
    assert checkpoint["candidate_spool_size"] == candidate_spool.stat().st_size
    assert checkpoint["audit_spool_size"] == audit_spool.stat().st_size


def test_stream_resume_rejects_pipeline_version_and_truncated_spool(tmp_path):
    source_path = tmp_path / "source_records.jsonl"
    source_path.write_text(
        json.dumps(source_record("A mutilated cow was found.")) + "\n",
        encoding="utf-8",
    )
    work_dir = tmp_path / "work"
    _, summary = seed.scan_ufo_source_records(source_path, work_dir, resume=False, limit=1)
    checkpoint_path = Path(summary["checkpoint"])
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint["pipeline_version"] = "different-pipeline-version"
    checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
    with pytest.raises(seed.SeedPipelineError, match="pipeline version changed"):
        seed.scan_ufo_source_records(source_path, work_dir, resume=True, limit=None)

    checkpoint["pipeline_version"] = seed.PIPELINE_VERSION
    checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
    candidate_spool = Path(summary["candidate_spool"])
    with candidate_spool.open("r+b") as handle:
        handle.truncate(candidate_spool.stat().st_size - 1)
    with pytest.raises(seed.SeedPipelineError, match="shorter than its checkpoint boundary"):
        seed.scan_ufo_source_records(source_path, work_dir, resume=True, limit=None)


def test_stream_resume_rejects_same_size_source_replacement(tmp_path):
    source_path = tmp_path / "source_records.jsonl"
    rows = [
        source_record(
            "A mutilated cow was found.",
            canonical_input_id="cin_1",
            source_native_id="one",
            source_row_hash="1" * 40,
        ),
        source_record(
            "Ordinary light report.",
            canonical_input_id="cin_2",
            source_native_id="two",
            source_row_hash="2" * 40,
        ),
    ]
    source_path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    work_dir = tmp_path / "work"
    seed.scan_ufo_source_records(source_path, work_dir, resume=False, limit=1)
    original_stat = source_path.stat()
    changed = source_path.read_text(encoding="utf-8").replace(
        "Ordinary light report.", "Ordinary night report."
    )
    source_path.write_text(changed, encoding="utf-8")
    assert source_path.stat().st_size == original_stat.st_size
    os.utime(
        source_path,
        ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
    )

    with pytest.raises(seed.SeedPipelineError, match="source corpus identity changed"):
        seed.scan_ufo_source_records(source_path, work_dir, resume=True, limit=None)


def test_cluster_uses_existing_ufo_lineage_and_never_auto_merges_pair():
    first_record = source_record("A mutilated cow was found.", canonical_input_id="cin_1", source_native_id="one")
    second_record = source_record("A cow was found mutilated.", canonical_input_id="cin_2", source_native_id="two")
    wrappers = []
    for index, record in enumerate((first_record, second_record), 1):
        candidate = seed.build_candidate_record(record, seed.analyze_source_record(record), index)
        wrappers.append({"candidate": candidate, "ufo_event_id": "evt_same"})
    incidents, pairs, mapping = seed.cluster_candidates(wrappers)
    assert len(incidents) == 1
    assert len(pairs) == 1
    assert pairs[0]["auto_merge"] == "false"
    assert set(mapping) == {wrappers[0]["candidate"]["record_id"], wrappers[1]["candidate"]["record_id"]}


def test_unclustered_context_row_receives_resolvable_duplicate_lineage_only():
    record = source_record(
        "A mystery helicopter was reported over the county.",
        type_raw="mystery helicopter/mutilation related",
        type_normalized="mystery_helicopter_mutilation_related",
    )
    analysis = seed.analyze_source_record(record)
    candidate = seed.build_candidate_record(record, analysis, 1)
    candidate["external_event_refs"] = [
        {
            "domain": "ufo",
            "dataset": "MYTbrain/ufo-timeline",
            "external_id": "evt_context_fixture",
            "native_event_id": 42,
            "relationship_id": None,
        }
    ]
    wrapper = {
        "candidate": candidate,
        "analysis": {"disposition": analysis.disposition},
        "ufo_event_id": "evt_context_fixture",
        "ufo_event_native_id": 42,
    }

    relationships, _ = seed.build_relationships([wrapper], [], [], [])

    assert len(relationships) == 1
    lineage = relationships[0]
    assert lineage["relationship_type"] == "duplicate_lineage"
    assert lineage["assertion_mode"] == "deterministic_match"
    assert lineage["subject"]["external_id"] == candidate["record_id"]
    assert lineage["object"]["external_id"] == "evt_context_fixture"
    assert lineage["causality"] == "not_asserted"
    assert candidate["external_event_refs"][0]["relationship_id"] == lineage["relationship_id"]
    assert not any(row["assertion_mode"] == "explicit_source" for row in relationships)


def test_acquire_cli_passes_bounded_worker_count(monkeypatch, tmp_path, capsys):
    captured = {}

    def fake_acquire(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return {"status": "test"}

    monkeypatch.setattr(seed, "acquire_crop_sources", fake_acquire)
    exit_code = seed.main(
        [
            "acquire",
            "--crop-zip",
            str(tmp_path / "crop.zip"),
            "--audit-output",
            str(tmp_path / "audit.csv"),
            "--private-cache-dir",
            str(tmp_path / "cache"),
            "--workers",
            "4",
        ]
    )

    assert exit_code == 0
    assert captured["kwargs"]["workers"] == 4
    assert json.loads(capsys.readouterr().out) == {"status": "test"}


def test_cli_completion_json_is_ascii_safe(monkeypatch, capsys):
    monkeypatch.setattr(
        seed,
        "run_extract",
        lambda args: {"source_excerpt": "replacement \ufffd character"},
    )
    assert seed.main(["extract"]) == 0
    output = capsys.readouterr().out
    assert "\\ufffd" in output
    assert json.loads(output)["source_excerpt"] == "replacement \ufffd character"


def test_extract_cli_prints_compact_manifest_summary(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        seed,
        "run_extract",
        lambda args: {
            "output_dir": str(tmp_path),
            "manifest": {
                "pipeline_version": "fixture-v1",
                "counts": {"candidate_records": 2},
                "validation_provenance": {"large_registry": ["not printed"]},
            },
            "validation": {"status": "passed"},
        },
    )
    assert seed.main(["extract"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["pipeline_version"] == "fixture-v1"
    assert output["counts"] == {"candidate_records": 2}
    assert output["validation"] == {"status": "passed"}
    assert "validation_provenance" not in output


@pytest.fixture(scope="module")
def validation_output_with_real_pinned_crop_inputs(tmp_path_factory):
    required = (seed.DEFAULT_STARTER_PACK, seed.DEFAULT_CROP_ZIP, seed.DEFAULT_CATALOG_PDF)
    if not all(path.is_file() for path in required):
        pytest.skip("Pinned local research packages are not installed in this environment")

    tmp_path = tmp_path_factory.mktemp("cattle_validation_output")
    source_path = tmp_path / "source_records.jsonl"
    deduped_path = tmp_path / "deduped_events.jsonl"
    record = source_record(
        "A mutilated cow was found inside a crop circle.",
        date_raw="about 2013",
        date_iso="2013-01-01",
        end_date_iso="2013-12-31",
        date_precision="year",
        location_raw="123 Ranch Road, Westport, New York",
        city="Westport",
        state_province="NY",
        country="US",
        lat=44.183,
        lon=-73.436,
        location_precision="exact_site",
    )
    context_record = source_record(
        "A mystery helicopter was reported over the county.",
        canonical_input_id="cin_context_fixture",
        source_native_id="context_fixture_1",
        type_raw="mystery helicopter/mutilation related",
        type_normalized="mystery_helicopter_mutilation_related",
    )
    source_path.write_text(
        json.dumps(record) + "\n" + json.dumps(context_record) + "\n",
        encoding="utf-8",
    )
    deduped_path.write_text(
        "\n".join(
            json.dumps(row)
            for row in (
                {
                    "canonical_event_id": "evt_fixture",
                    "event_id": 1,
                    "canonical_input_ids": [record["canonical_input_id"]],
                    "source_provenance": [],
                },
                {
                    "canonical_event_id": "evt_context_fixture",
                    "event_id": 2,
                    "canonical_input_ids": [context_record["canonical_input_id"]],
                    "source_provenance": [],
                },
            )
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "output"
    result = seed.run_extract(
        Namespace(
            starter_pack=str(seed.DEFAULT_STARTER_PACK),
            crop_zip=str(seed.DEFAULT_CROP_ZIP),
            catalog_pdf=str(seed.DEFAULT_CATALOG_PDF),
            source_records=str(source_path),
            deduped_events=str(deduped_path),
            acquisition_audit="",
            private_cache_dir="",
            output_dir=str(output_dir),
            resume=False,
            allow_partial=True,
            limit=None,
        )
    )
    return output_dir, result


def _copy_validation_output(base_output: Path, destination: Path) -> Path:
    copied = destination / "output"
    shutil.copytree(base_output, copied)
    return copied


def _refresh_manifest_output_identities(output_dir: Path, *names: str) -> None:
    manifest_path = output_dir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name in names:
        path = output_dir / name
        manifest["outputs"][name] = {
            "size_bytes": path.stat().st_size,
            "sha256": seed.sha256_file(path),
        }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _ufo_source_case(rows):
    return next(
        row
        for row in rows
        if row.get("provenance", {}).get("ingestion_adapter")
        == "ufo_timeline_source_records_v1"
        and row.get("record_type") == "mutilation_case"
    )


def test_partial_end_to_end_uses_real_pinned_crop_inputs_when_available(
    validation_output_with_real_pinned_crop_inputs,
):
    output_dir, result = validation_output_with_real_pinned_crop_inputs
    assert result["validation"]["status"] == "passed"
    assert result["manifest"]["counts"]["scanned"] == 2
    assert result["manifest"]["counts"]["crop_events_scanned"] == 7745
    assert result["manifest"]["counts"]["catalog_slots_scanned"] == 5978
    assert all((output_dir / name).is_file() for name in seed.OUTPUT_NAMES)
    with (output_dir / "crop_circle_source_access_audit.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        crop_audit = list(csv.DictReader(handle))
    kind_counts = {}
    for row in crop_audit:
        kind_counts[row["item_kind"]] = kind_counts.get(row["item_kind"], 0) + 1
        assert row["disposition"]
    assert kind_counts["crop_event"] == 7745
    assert kind_counts["crop_assertion"] == 8391
    assert kind_counts["crop_image_alt_text"] == 2858
    assert kind_counts["crop_image_title_text"] == 78
    assert kind_counts["crop_source_url"] == 2371
    assert kind_counts["catalog_pdf_page"] == 309
    assert kind_counts["catalog_pdf_slot"] == 5978
    assert kind_counts["crop_listing_source_url"] > 0
    emitted_cases = list(seed.read_jsonl(output_dir / "candidate_records.jsonl"))
    context_case = next(row for row in emitted_cases if row["record_type"] == "related_aerial_event")
    assert context_case["external_event_refs"]
    assert all(ref["relationship_id"] for ref in context_case["external_event_refs"])
    manifest_text = (output_dir / "run_manifest.json").read_text(encoding="utf-8")
    assert "validation_provenance" in result["manifest"]
    assert result["manifest"]["configuration"]["privacy_policy"] == (
        "redact_all_named_private_properties_and_generalize_"
        "modern_or_precise_unnamed_private_locations"
    )
    assert "123 Ranch Road" not in manifest_text


def test_validate_rejects_fabricated_ufo_endpoint_with_reciprocal_output_refs(
    validation_output_with_real_pinned_crop_inputs, tmp_path
):
    base_output, _ = validation_output_with_real_pinned_crop_inputs
    output_dir = _copy_validation_output(base_output, tmp_path)
    relationships = list(seed.read_jsonl(output_dir / "cross_domain_relationships.jsonl"))
    fabricated_id = "evt_fabricated_not_in_deduplicated_input"
    fabricated_native_id = "999999999"
    ufo_relationship = next(
        row for row in relationships if row.get("object", {}).get("domain") == "ufo"
    )
    ufo_relationship["object"]["external_id"] = fabricated_id
    ufo_relationship["object"]["native_event_id"] = fabricated_native_id
    mutated_relationship_id = ufo_relationship["relationship_id"]
    seed.write_jsonl(output_dir / "cross_domain_relationships.jsonl", relationships)

    for name in ("candidate_records.jsonl", "canonical_incidents.jsonl"):
        rows = list(seed.read_jsonl(output_dir / name))
        for row in rows:
            for external_ref in row.get("external_event_refs", []):
                if external_ref.get("relationship_id") == mutated_relationship_id:
                    external_ref["external_id"] = fabricated_id
                    external_ref["native_event_id"] = fabricated_native_id
        seed.write_jsonl(output_dir / name, rows)
    _refresh_manifest_output_identities(
        output_dir,
        "cross_domain_relationships.jsonl",
        "candidate_records.jsonl",
        "canonical_incidents.jsonl",
    )

    with pytest.raises(seed.SeedPipelineError, match="authoritative lineage"):
        seed.validate_outputs(output_dir, crop_zip_path=seed.DEFAULT_CROP_ZIP)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_hash", "0" * 64),
        ("locator", "fabricated:source-locator"),
    ],
)
def test_validate_rejects_valid_looking_wrong_source_hash_or_locator(
    validation_output_with_real_pinned_crop_inputs, tmp_path, field, value
):
    base_output, _ = validation_output_with_real_pinned_crop_inputs
    output_dir = _copy_validation_output(base_output, tmp_path)
    relationships = list(seed.read_jsonl(output_dir / "cross_domain_relationships.jsonl"))
    source_ref = next(
        source_ref
        for relationship in relationships
        for source_ref in relationship.get("source_refs", [])
        if not str(source_ref.get("source_id", "")).startswith("crop:")
    )
    source_ref[field] = value
    seed.write_jsonl(output_dir / "cross_domain_relationships.jsonl", relationships)
    _refresh_manifest_output_identities(output_dir, "cross_domain_relationships.jsonl")

    with pytest.raises(seed.SeedPipelineError, match="authoritative provenance"):
        seed.validate_outputs(output_dir, crop_zip_path=seed.DEFAULT_CROP_ZIP)


def test_validate_rejects_private_raw_address_and_public_coordinates(
    validation_output_with_real_pinned_crop_inputs, tmp_path
):
    base_output, _ = validation_output_with_real_pinned_crop_inputs
    output_dir = _copy_validation_output(base_output, tmp_path)
    candidates = list(seed.read_jsonl(output_dir / "candidate_records.jsonl"))
    case = _ufo_source_case(candidates)
    case["location"].update(
        {
            "raw_text": "123 Ranch Road, Westport, New York",
            "latitude_public": 44.183,
            "longitude_public": -73.436,
            "privacy_level": "public_generalized",
        }
    )
    seed.write_jsonl(output_dir / "candidate_records.jsonl", candidates)
    _refresh_manifest_output_identities(output_dir, "candidate_records.jsonl")

    with pytest.raises(seed.SeedPipelineError, match="public-location decision"):
        seed.validate_outputs(output_dir, crop_zip_path=seed.DEFAULT_CROP_ZIP)


@pytest.mark.parametrize("field", ["explicit_negative", "negative_only"])
def test_validate_rejects_negative_flag_provenance_mutation(
    validation_output_with_real_pinned_crop_inputs, tmp_path, field
):
    base_output, _ = validation_output_with_real_pinned_crop_inputs
    output_dir = _copy_validation_output(base_output, tmp_path)
    candidates = list(seed.read_jsonl(output_dir / "candidate_records.jsonl"))
    case = _ufo_source_case(candidates)
    case[field] = not bool(case.get(field))
    seed.write_jsonl(output_dir / "candidate_records.jsonl", candidates)
    _refresh_manifest_output_identities(output_dir, "candidate_records.jsonl")

    with pytest.raises(seed.SeedPipelineError, match=field.replace("_", "-")):
        seed.validate_outputs(output_dir, crop_zip_path=seed.DEFAULT_CROP_ZIP)


@pytest.mark.parametrize(
    "residual_locator",
    [
        "A report came from 1234 Ranch Road.",
        "A report came from 12-14 Smith Road.",
        "A cow at john catalano ranch was mutilated.",
        "A [cow](https://example.invalid/a_(nested)) was mutilated.",
        "A [cow][case-source] was mutilated.",
        "[case-source]: https://example.invalid/report",
        "A cow was mutilated; see <https://example.invalid/report>.",
        "A cow was mutilated; see https://example.invalid/report.",
        "A [cow](https://example.invalid/truncated was mutilated.",
    ],
)
def test_validate_rejects_every_residual_private_or_link_locator_form(
    validation_output_with_real_pinned_crop_inputs, tmp_path, residual_locator
):
    base_output, _ = validation_output_with_real_pinned_crop_inputs
    output_dir = _copy_validation_output(base_output, tmp_path)
    crop_candidates = list(
        seed.read_jsonl(output_dir / "crop_circle_source_candidates.jsonl")
    )
    crop_candidates[0].setdefault("animal_assertions", []).append(
        {"evidence_excerpt": residual_locator}
    )
    seed.write_jsonl(
        output_dir / "crop_circle_source_candidates.jsonl", crop_candidates
    )
    _refresh_manifest_output_identities(
        output_dir, "crop_circle_source_candidates.jsonl"
    )

    with pytest.raises(seed.SeedPipelineError, match="Crop source candidate public evidence"):
        seed.validate_outputs(output_dir, crop_zip_path=seed.DEFAULT_CROP_ZIP)


@pytest.mark.parametrize(
    ("target", "residual_locator"),
    [
        ("case_title", "Animal incident at john catalano ranch"),
        ("source_title", "Report from 12-14 Smith Road"),
        ("source_publisher", "Archive <https://example.invalid/private>"),
    ],
)
def test_validate_rejects_locators_in_public_titles_and_source_metadata(
    validation_output_with_real_pinned_crop_inputs,
    tmp_path,
    target,
    residual_locator,
):
    base_output, _ = validation_output_with_real_pinned_crop_inputs
    output_dir = _copy_validation_output(base_output, tmp_path)
    candidates = list(seed.read_jsonl(output_dir / "candidate_records.jsonl"))
    case = _ufo_source_case(candidates)
    if target == "case_title":
        case["title"] = residual_locator
    elif target == "source_title":
        case["sources"][0]["title"] = residual_locator
    else:
        case["sources"][0]["agency_or_publisher"] = residual_locator
    seed.write_jsonl(output_dir / "candidate_records.jsonl", candidates)
    _refresh_manifest_output_identities(output_dir, "candidate_records.jsonl")

    with pytest.raises(seed.SeedPipelineError, match="Public evidence excerpt"):
        seed.validate_outputs(output_dir, crop_zip_path=seed.DEFAULT_CROP_ZIP)


@pytest.mark.parametrize("mutation", ["date_collapse", "location_upgrade"])
def test_validate_rejects_date_or_location_precision_inflation(
    validation_output_with_real_pinned_crop_inputs, tmp_path, mutation
):
    base_output, _ = validation_output_with_real_pinned_crop_inputs
    output_dir = _copy_validation_output(base_output, tmp_path)
    candidates = list(seed.read_jsonl(output_dir / "candidate_records.jsonl"))
    case = _ufo_source_case(candidates)
    if mutation == "date_collapse":
        case["dates"]["event_end"] = case["dates"]["event_start"]
        expected_error = "date decision"
    else:
        case["location"]["precision"] = "exact_site"
        expected_error = "public-location decision"
    seed.write_jsonl(output_dir / "candidate_records.jsonl", candidates)
    _refresh_manifest_output_identities(output_dir, "candidate_records.jsonl")

    with pytest.raises(seed.SeedPipelineError, match=expected_error):
        seed.validate_outputs(output_dir, crop_zip_path=seed.DEFAULT_CROP_ZIP)
