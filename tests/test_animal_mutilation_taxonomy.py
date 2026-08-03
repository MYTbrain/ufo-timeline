from __future__ import annotations

import pytest

from scripts import animal_mutilation_taxonomy as taxonomy
from scripts import cattle_mutilation_seed as seed


def source_record(description: str) -> dict[str, object]:
    return {
        "canonical_input_id": "cin_animal_fixture",
        "source_name": "fixture",
        "source_native_id": "animal_fixture_1",
        "source_row_hash": "a" * 40,
        "date_raw": "1975-03-10",
        "date_iso": "1975-03-10",
        "end_date_iso": "1975-03-10",
        "date_precision": "day",
        "location_raw": "Fixture County, United States",
        "city": None,
        "state_province": None,
        "country": "United States",
        "lat": None,
        "lon": None,
        "coordinate_source": None,
        "location_precision": "unknown",
        "description": description,
        "summary": description,
        "type_raw": "report",
        "type_normalized": "report",
        "source_url": None,
        "raw_fields": {"Long Description": description},
    }


@pytest.mark.parametrize(
    ("text", "label", "group"),
    [
        ("A farmer found a mutilated pig in the field.", "pig", "porcine"),
        ("Ten llamas were found drained of blood.", "camelid", "camelid"),
        ("A gutted deer was discovered beside the road.", "deer", "cervid"),
        ("A mutilated cat was reported near the farm.", "cat", "felid"),
        ("Several chickens were found mutilated.", "poultry", "avian"),
        ("A bloodless bison carcass was discovered.", "bison", "bovine"),
        ("A rabbit was found with its organs removed.", "rabbit_hare", "lagomorph"),
        ("A fish was recovered with precise circular incisions.", "fish", "fish"),
        ("A dolphin was found mutilated on the shore.", "marine_mammal", "marine_mammal"),
        ("A snake was found with its organs removed.", "reptile", "reptile"),
        ("A bear was found mutilated in the forest.", "other_named", "other_mammal"),
        ("A mutilated elephant was reported.", "other_named", "other_mammal"),
        ("A lion was found with its organs removed.", "wild_felid", "felid"),
        ("A mutilated zebra was discovered.", "other_ungulate", "other_ungulate"),
        ("An octopus was found mutilated.", "invertebrate", "invertebrate"),
    ],
)
def test_inclusive_non_bovine_victims_are_first_class(text, label, group):
    analysis = taxonomy.analyze_incident_animals(text)
    assert [row.normalized_common_name for row in analysis.victim_assertions] == [label]
    assert analysis.victim_assertions[0].species_group == group
    assert seed.analyze_source_record(source_record(text)).record_type == "mutilation_case"


@pytest.mark.parametrize(
    ("text", "taxon_key", "label", "group"),
    [
        ("A penguin was found mutilated.", "penguin", "wild_bird", "avian"),
        ("An ostrich was found mutilated.", "ostrich", "wild_bird", "avian"),
        ("A parrot was found mutilated.", "parrot", "wild_bird", "avian"),
        ("A platypus was found mutilated.", "platypus", "other_named", "other_mammal"),
        ("A walrus was found mutilated.", "walrus", "marine_mammal", "marine_mammal"),
        ("A manatee was found mutilated.", "manatee", "marine_mammal", "marine_mammal"),
        ("An iguana was found mutilated.", "iguana", "reptile", "reptile"),
        ("A gecko was found mutilated.", "gecko", "reptile", "reptile"),
        ("A newt was found mutilated.", "newt", "amphibian", "amphibian"),
        ("An eel was found mutilated.", "eel", "fish", "fish"),
        ("An orca was found mutilated.", "orca", "marine_mammal", "marine_mammal"),
    ],
)
def test_controlled_common_animal_vocabulary_creates_distinct_victims(
    text, taxon_key, label, group
):
    analysis = taxonomy.analyze_incident_animals(text)
    assert [row.reported_taxon_key for row in analysis.victim_assertions] == [taxon_key]
    assert analysis.victim_assertions[0].normalized_common_name == label
    assert analysis.victim_assertions[0].species_group == group
    assert seed.analyze_source_record(source_record(text)).record_type == "mutilation_case"


@pytest.mark.parametrize(
    "text",
    [
        "A table was found mutilated.",
        "Newt Gingrich was found mutilated.",
        "The mutilated pilot was reported in Manatee County.",
        "The mutilated witness was found on Orcas Island.",
    ],
)
def test_expanded_vocabulary_does_not_convert_objects_people_or_places(text):
    assert taxonomy.analyze_incident_animals(text).victim_assertions == ()
    assert seed.analyze_source_record(source_record(text)).record_type != "mutilation_case"


@pytest.mark.parametrize(
    "text",
    [
        "Penguin published a book on cattle mutilations.",
        "The Penguin edition described cattle mutilations.",
    ],
)
def test_penguin_publishing_context_does_not_create_penguin_victim(text):
    analysis = taxonomy.analyze_incident_animals(text)
    assert all(row.reported_taxon_key != "penguin" for row in analysis.victim_assertions)
    assert seed.analyze_source_record(source_record(text)).record_type != "mutilation_case"


def test_ostrich_algorithm_is_not_an_animal_assertion():
    text = "The ostrich algorithm was discussed in an article about mutilated cattle."
    analysis = taxonomy.analyze_incident_animals(text)
    assert [row.reported_taxon_key for row in analysis.victim_assertions] == ["cattle"]
    assert seed.analyze_source_record(source_record(text)).record_type != "mutilation_case"


def test_mixed_species_incident_preserves_each_victim():
    text = "A cow, two horses, and three sheep were found mutilated."
    analysis = taxonomy.analyze_incident_animals(text)
    assert {row.normalized_common_name for row in analysis.victim_assertions} == {
        "cattle",
        "horse",
        "sheep",
    }
    assert seed.analyze_source_record(source_record(text)).record_type == "mutilation_case"


def test_broad_named_species_remain_distinct_victims():
    text = "A bear and an elephant were found mutilated."
    analysis = taxonomy.analyze_incident_animals(text)
    assert [row.normalized_common_name for row in analysis.victim_assertions] == [
        "other_named",
        "other_named",
    ]
    assert [row.reported_taxon_key for row in analysis.victim_assertions] == [
        "bear",
        "elephant",
    ]
    source_analysis = seed.analyze_source_record(source_record(text))
    assert source_analysis.record_type == "mutilation_case"
    public_rows = [
        taxonomy.assertion_to_public_row(row, "source:fixture")
        for row in source_analysis.animal_assertions
    ]
    assert [row["reported_taxon_key"] for row in seed._merge_animal_rows(public_rows)] == [
        "bear",
        "elephant",
    ]


def test_broad_named_victim_does_not_remove_distinct_context_taxon():
    analysis = taxonomy.analyze_incident_animals(
        "A bear was found mutilated. An elephant stood nearby."
    )
    assert [row.reported_taxon_key for row in analysis.victim_assertions] == ["bear"]
    assert [row.reported_taxon_key for row in analysis.context_assertions] == ["elephant"]


def test_live_missing_dog_return_story_is_not_an_anatomical_injury():
    text = (
        "I only had one dog and I got home and the dog that was missing somehow "
        "beat me home then a few months later I head the same noise above my house."
    )
    analysis = taxonomy.analyze_incident_animals(text)
    assert analysis.victim_assertions == ()
    assert seed.analyze_source_record(source_record(text)).record_type != "mutilation_case"


@pytest.mark.parametrize(
    "text",
    [
        "Cattle had gone missing from 2 owners, who lost 2 head each.",
        "3 to 4 days later, 35 head of cattle turned up missing.",
        "2 head cattle were missing.",
    ],
)
def test_live_missing_livestock_counts_are_not_missing_anatomy(text):
    analysis = taxonomy.analyze_incident_animals(text)
    assert analysis.victim_assertions == ()
    assert seed.analyze_source_record(source_record(text)).record_type != "mutilation_case"


@pytest.mark.parametrize(
    "text",
    [
        "A calf was found missing its head.",
        "A calf was found with its head missing.",
        "The cow's head was missing.",
    ],
)
def test_grammatical_missing_anatomy_remains_a_distinctive_injury(text):
    analysis = taxonomy.analyze_incident_animals(text)
    assert [row.reported_taxon_key for row in analysis.victim_assertions] == ["cattle"]
    assert seed.analyze_source_record(source_record(text)).record_type == "mutilation_case"


@pytest.mark.parametrize(
    ("singular", "plural", "expected"),
    [
        ("fish", "fishes", "fish"),
        ("rhinoceros", "rhinoceroses", "rhinoceros"),
        ("hippopotamus", "hippopotamuses", "hippopotamus"),
        ("ostrich", "ostriches", "ostrich"),
        ("platypus", "platypuses", "platypus"),
        ("walrus", "walruses", "walrus"),
    ],
)
def test_reported_taxon_key_normalizes_singular_and_plural(singular, plural, expected):
    analysis = taxonomy.analyze_incident_animals(
        f"A {singular} and two {plural} were found mutilated."
    )
    assert {row.reported_taxon_key for row in analysis.victim_assertions} == {expected}


@pytest.mark.parametrize(
    ("text", "taxon_key"),
    [
        ("A mutilated cow was found near the road.", "cattle"),
        ("A mutilated horse was found beside County Road.", "horse"),
    ],
)
def test_real_victims_are_not_suppressed_by_nearby_road_words(text, taxon_key):
    analysis = taxonomy.analyze_incident_animals(text)
    assert [row.reported_taxon_key for row in analysis.victim_assertions] == [taxon_key]
    assert seed.analyze_source_record(source_record(text)).record_type == "mutilation_case"


@pytest.mark.parametrize(
    "text",
    [
        "Two dead hogs were found on return, one mutilated.",
        "Thirty-five chickens, three sheep, and a dog were mutilated in one event.",
    ],
)
def test_multi_animal_event_is_not_misclassified_as_aggregate(text):
    analysis = seed.analyze_source_record(source_record(text))
    assert analysis.record_type == "mutilation_case"


def test_unrelated_page_level_aggregate_language_does_not_demote_discrete_incident():
    text = (
        "The introduction gives a nationwide overview and total number of UFO reports. "
        "Later, a deer was found with its torso missing."
    )
    analysis = seed.analyze_source_record(source_record(text))
    assert analysis.record_type == "mutilation_case"
    assert [row.normalized_common_name for row in analysis.animal_assertions] == ["deer"]


def test_generic_animal_incident_is_preserved_as_unknown_not_discarded():
    analysis = taxonomy.analyze_incident_animals(
        "An unidentified animal was discovered mutilated near the road."
    )
    assert len(analysis.victim_assertions) == 1
    assertion = analysis.victim_assertions[0]
    assert assertion.normalized_common_name == "unknown_animal"
    assert assertion.species_group == "unknown"


@pytest.mark.parametrize(
    ("category", "text"),
    [
        (
            "entity_or_agent",
            "4' creatures with pointed ears, then 3 hours missing time.",
        ),
        (
            "entity_or_agent",
            "Man attacked by 'dog-sized creature covered w black hair.' "
            "Animal mutilations reported in area.",
        ),
        (
            "negation_or_speculation",
            "Did not witness animal mutilation, only animal adoption.",
        ),
        (
            "negation_or_speculation",
            "I can only assume the strange noise was an animal being mutilated, "
            "but I really do not know as I did not see anything happen.",
        ),
        (
            "negation_or_speculation",
            "This is not at all a case of animal mutilation.",
        ),
        ("metaphor_or_hypothetical", "It let off an aura of animal mutilation."),
        (
            "metaphor_or_hypothetical",
            "When there is an animal mutilation, what can you hear?",
        ),
        (
            "citation_or_background",
            "Sources: 'The Mysterious Link Between UFOs and Animal Mutilations'.",
        ),
        (
            "citation_or_background",
            "In my classmate's term paper he did talk about livestock mutilations.",
        ),
        (
            "citation_or_background",
            "Catalog Entry: These sightings often followed by a mutilation or "
            "disappearance of an animal.",
        ),
        (
            "perpetrator_or_theory",
            "They are responsible for abductions and animal mutilations.",
        ),
        (
            "perpetrator_or_theory",
            "My guess is the crop circles and animal mutilations were done by aliens.",
        ),
        (
            "perpetrator_or_theory",
            "A more aggressive extraterrestrial race would be mostly responsible "
            "to forced abductions and animal mutilations.",
        ),
        (
            "investigation_future_or_reaction",
            "Cop at stakeout for animal mutilators.",
        ),
        (
            "investigation_future_or_reaction",
            "We look forward to future animal mutilations that may come within "
            "the next few months.",
        ),
        (
            "investigation_future_or_reaction",
            "The animal mutilation disgusts me.",
        ),
    ],
)
def test_generic_nonincident_contexts_do_not_create_unknown_victims(category, text):
    assert category in {
        "entity_or_agent",
        "negation_or_speculation",
        "metaphor_or_hypothetical",
        "citation_or_background",
        "perpetrator_or_theory",
        "investigation_future_or_reaction",
    }
    assert taxonomy.analyze_incident_animals(text).victim_assertions == ()


def test_generic_animal_agent_remains_context_beside_supported_cat_victim():
    analysis = taxonomy.analyze_incident_animals(
        "My cat was missing his left ear and it looked cleanly severed. I would "
        "not think any further than it being a wild animal attack."
    )
    assert [row.reported_taxon_key for row in analysis.victim_assertions] == ["cat"]
    assert all(
        row.reported_taxon_key != "unknown_animal"
        for row in analysis.victim_assertions
    )


@pytest.mark.parametrize(
    "text",
    [
        "Animal was missing it's udder from smooth, exact 'incisions.'",
        "Each animal had genitals removed, no other marks found on bodies.",
        "An animal mutilation was observed by more than two male witnesses at a lake.",
        "Several mutilated animals were discovered beside the road.",
    ],
)
def test_generic_actual_incident_predicates_remain_unknown_victims(text):
    analysis = taxonomy.analyze_incident_animals(text)
    assert [row.reported_taxon_key for row in analysis.victim_assertions] == [
        "unknown_animal"
    ]
    assert analysis.victim_assertions[0].incident_role == "reported_victim"


def test_researcher_can_report_a_direct_generic_animal_incident():
    analysis = taxonomy.analyze_incident_animals(
        "The researcher found a mutilated animal at the scene."
    )
    assert [row.reported_taxon_key for row in analysis.victim_assertions] == [
        "unknown_animal"
    ]


def test_researcher_publication_background_remains_context_only():
    analysis = taxonomy.analyze_incident_animals(
        "The researcher published a paper about animal mutilations."
    )
    assert analysis.victim_assertions == ()


def test_generic_background_statement_does_not_add_a_second_unknown_victim():
    analysis = taxonomy.analyze_incident_animals(
        "I found a mutilated fish. Having heard in the past that this was common to "
        "mutilated animal cases."
    )
    assert [row.normalized_common_name for row in analysis.victim_assertions] == ["fish"]
    assert [(row.normalized_common_name, row.incident_role) for row in analysis.context_assertions] == [
        ("unknown_animal", "context_only")
    ]


def test_witness_dog_is_context_and_gutted_deer_is_victim():
    analysis = taxonomy.analyze_incident_animals("My dogs discovered a gutted deer.")
    assert [row.normalized_common_name for row in analysis.victim_assertions] == ["deer"]
    assert [(row.normalized_common_name, row.incident_role) for row in analysis.context_assertions] == [
        ("dog", "witness_companion")
    ]


def test_actual_dog_victim_is_not_suppressed_as_companion():
    analysis = taxonomy.analyze_incident_animals("Two dogs were found gutted.")
    assert [row.normalized_common_name for row in analysis.victim_assertions] == ["dog"]


@pytest.mark.parametrize(
    "text",
    [
        "A dead cow - not mutilated - was found beside the road.",
        "No cattle were mutilated in this incident.",
        "None of the animals were mutilated.",
        "The cow was not mutilated and no organs were missing.",
        "The cow was not mutilated; its tongue was not missing.",
    ],
)
def test_explicitly_negated_mutilation_is_not_victim_evidence(text):
    analysis = taxonomy.analyze_incident_animals(text)
    assert analysis.victim_assertions == ()
    source_analysis = seed.analyze_source_record(source_record(text))
    assert source_analysis.explicit_negative is True
    assert source_analysis.record_type != "mutilation_case"


@pytest.mark.parametrize(
    "text",
    [
        "The cow had no organs missing.",
        "The cow's tongue was not missing.",
        "The cow was not bloodless and was never gutted.",
    ],
)
def test_negated_distinctive_injuries_do_not_create_cases(text):
    assert taxonomy.analyze_incident_animals(text).victim_assertions == ()
    assert seed.analyze_source_record(source_record(text)).record_type != "mutilation_case"


def test_positive_distinctive_injury_control_remains_a_case():
    text = "The cow had no blood remaining and its tongue was missing."
    analysis = taxonomy.analyze_incident_animals(text)
    assert [row.reported_taxon_key for row in analysis.victim_assertions] == ["cattle"]
    assert seed.analyze_source_record(source_record(text)).record_type == "mutilation_case"


def test_buffalo_place_homonym_is_not_a_bison_victim():
    analysis = taxonomy.analyze_incident_animals(
        "Four calves were mutilated in the Buffalo area."
    )
    assert [row.normalized_common_name for row in analysis.victim_assertions] == [
        "cattle"
    ]
    assert all(
        row.normalized_common_name != "bison"
        for row in analysis.context_assertions
    )


def test_place_only_buffalo_does_not_create_an_animal_case():
    text = "The mutilated body was found in Buffalo, New York."
    assert taxonomy.analyze_incident_animals(text).victim_assertions == ()
    assert seed.analyze_source_record(source_record(text)).record_type != "mutilation_case"


@pytest.mark.parametrize(
    ("text", "victims"),
    [
        ("A robotic slug descended and mutilated my cows.", ["cattle"]),
        ("A decapitated sheep sat rigid like a teddy bear.", ["sheep"]),
        ("Cattle mutilations and panther tracks were reported.", ["cattle"]),
    ],
)
def test_figurative_or_track_terms_are_not_victim_species(text, victims):
    analysis = taxonomy.analyze_incident_animals(text)
    assert [row.normalized_common_name for row in analysis.victim_assertions] == victims


def test_mechanical_animal_metaphor_remains_suppressed_across_sentences():
    text = (
        "A robotic slug descended and mutilated my cows. "
        "The slug then burned my cows, mutilated my cows, and depressed my cows."
    )
    analysis = taxonomy.analyze_incident_animals(text)
    assert [row.normalized_common_name for row in analysis.victim_assertions] == [
        "cattle"
    ]


def test_animal_size_comparison_is_not_an_incident():
    text = (
        "They said it was smaller than a ladybug's leg and bigger than the "
        "biggest elephant. My brains leaked out of my head when she told me that."
    )
    assert taxonomy.analyze_incident_animals(text).victim_assertions == ()
    assert seed.analyze_source_record(source_record(text)).record_type != "mutilation_case"


@pytest.mark.parametrize(
    "text",
    [
        "The mutilated body was found in the Buffalo vicinity.",
        "The mutilated body was reported in Eagle, Southeast Fairbanks Borough.",
        "The mutilated body was reported near Conejos County.",
        "The mutilated body was reported from Bear Mountain.",
        "The mutilated body was found near Fox Run Road.",
        "The mutilated pilot was found near Seal Beach.",
    ],
)
def test_animal_place_names_do_not_create_victims(text):
    assert taxonomy.analyze_incident_animals(text).victim_assertions == ()


@pytest.mark.parametrize(
    "text",
    [
        "My kids found an object with large eyes.",
        "The RAM module failed after a jaw-shaped craft was reported.",
        "The bull market caught the analyst's eye.",
        "The witness reported pain in his calf muscle and ear.",
        "The catalog label was Cat: 4.",
        "A formation was listed at Buffalo, New York.",
        "The report came from Deerfield near Horseheads.",
        "The witness described a tall creature with a dark skinned body and elongated head.",
    ],
)
def test_ambiguous_human_technical_and_place_terms_are_not_incidents(text):
    analysis = taxonomy.analyze_incident_animals(text)
    assert analysis.victim_assertions == ()
    assert seed.analyze_source_record(source_record(text)).record_type != "mutilation_case"


@pytest.mark.parametrize(
    "text",
    [
        "I took my dog outside and saw a being with large eyes.",
        "The witness's dog barked while the craft opened like a jaw.",
        "A cat watched an object with two bright eyes.",
    ],
)
def test_pet_and_anatomy_cooccurrence_is_not_a_case(text):
    assert seed.analyze_source_record(source_record(text)).disposition == "not_candidate"


@pytest.mark.parametrize(
    "text",
    [
        "A dead pig was found in the field.",
        "Several ducks died during the storm.",
        "A farmer reported that a horse was killed by lightning.",
    ],
)
def test_ordinary_animal_death_is_context_not_mutilation_case(text):
    analysis = seed.analyze_source_record(source_record(text))
    assert analysis.record_type != "mutilation_case"
    assert analysis.disposition == "not_candidate"


def test_scavenger_is_not_labeled_as_victim():
    analysis = taxonomy.analyze_incident_animals(
        "Coyotes were feeding near a cow that was found mutilated."
    )
    assert [row.normalized_common_name for row in analysis.victim_assertions] == ["cattle"]
    assert [(row.normalized_common_name, row.incident_role) for row in analysis.context_assertions] == [
        ("wild_canid", "predator_or_scavenger")
    ]


def test_anaphoric_deaths_keep_cattle_as_victim_and_vulture_as_scavenger():
    text = (
        "Strange cattle deaths occurred. The deaths have been blamed on "
        "non-native vultures, but were missing eyes."
    )
    analysis = taxonomy.analyze_incident_animals(text)
    assert [row.reported_taxon_key for row in analysis.victim_assertions] == ["cattle"]
    assert [(row.reported_taxon_key, row.incident_role) for row in analysis.context_assertions] == [
        ("vulture", "predator_or_scavenger")
    ]


def test_alleged_active_animal_agent_is_context_not_victim():
    analysis = taxonomy.analyze_incident_animals("Lizard-types mutilate cows.")
    assert [row.reported_taxon_key for row in analysis.victim_assertions] == ["cattle"]
    assert [(row.reported_taxon_key, row.incident_role) for row in analysis.context_assertions] == [
        ("lizard", "context_only")
    ]


def test_animal_like_footprint_is_trace_context_not_victim():
    analysis = taxonomy.analyze_incident_animals(
        "The footprints looked like a lizard and led to a mutilated cat."
    )
    assert [row.reported_taxon_key for row in analysis.victim_assertions] == ["cat"]
    assert [(row.reported_taxon_key, row.incident_role) for row in analysis.context_assertions] == [
        ("lizard", "context_only")
    ]


def test_real_source_possessive_cat_is_victim_and_lizard_footprint_is_context():
    analysis = taxonomy.analyze_incident_animals(
        "I went into the garden and found footprints going toward a bush and there I "
        "found my cat mutilated and a tube was inserted into his body and his intestines "
        "were pulled out and coiled on a leaf and the footprint were like those of a "
        "lizard type animal"
    )
    assert [row.reported_taxon_key for row in analysis.victim_assertions] == ["cat"]
    assert ("lizard", "context_only") in {
        (row.reported_taxon_key, row.incident_role)
        for row in analysis.context_assertions
    }


def test_real_source_cow_remains_victim_when_vultures_explain_one_missing_eye():
    analysis = taxonomy.analyze_incident_animals(
        "The cow was found with a cut in the front of the body between the front two "
        "legs, and the heart outside the body. All of the teats had been cut off of the "
        "udder, the tongue was cut out, and one eye was missing (the eye may have been "
        "missing due to vultures or maggots, which were already on the cow)."
    )
    assert [row.reported_taxon_key for row in analysis.victim_assertions] == ["cattle"]
    assert ("vulture", "predator_or_scavenger") in {
        (row.reported_taxon_key, row.incident_role)
        for row in analysis.context_assertions
    }


def test_real_source_heard_frog_is_context_for_unrelated_humanoid_anatomy():
    analysis = taxonomy.analyze_incident_animals(
        "Type C. Electrician fishing in boat, heard frog croaking, domed disc w "
        "orange+blue lights approachs. 5' humanoid, pointed ears, large eyes, sharp "
        "chin, paralysis, missing time."
    )
    assert analysis.victim_assertions == ()
    assert ("frog", "context_only") in {
        (row.reported_taxon_key, row.incident_role)
        for row in analysis.context_assertions
    }


def test_real_source_anaphoric_cattle_deaths_keep_vultures_as_context():
    analysis = taxonomy.analyze_incident_animals(
        "I don't know if it's connected or not, but there have been strange cattle "
        "deaths in close timing to seeing these things previously. The deaths have been "
        "blamed on some type of non-native vultures, but were missing eyes."
    )
    assert [row.reported_taxon_key for row in analysis.victim_assertions] == ["cattle"]
    assert ("vulture", "predator_or_scavenger") in {
        (row.reported_taxon_key, row.incident_role)
        for row in analysis.context_assertions
    }


def test_real_source_historical_snippy_reference_keeps_horse_as_context():
    analysis = taxonomy.analyze_incident_animals(
        "I was not even sure which year it was until I remembered that the well-known "
        "case of Snippy the horse (mutilation) occurred about 2 to 4 weeks after our "
        "event."
    )
    assert analysis.victim_assertions == ()
    assert ("horse", "context_only") in {
        (row.reported_taxon_key, row.incident_role)
        for row in analysis.context_assertions
    }


def test_staged_bird_is_victim_while_cattle_memory_is_context():
    text = (
        "They planted a mutilated bird near the circle to create an eerie touch and "
        "to evoke memories of cattle mutilations."
    )
    analysis = taxonomy.analyze_incident_animals(text)
    assert [row.reported_taxon_key for row in analysis.victim_assertions] == ["bird"]
    assert ("cattle", "context_only") in {
        (row.reported_taxon_key, row.incident_role)
        for row in analysis.context_assertions
    }


def test_long_narrative_windows_preserve_victim_and_harm_anchors():
    text = ("unrelated observation " * 45) + "a mutilated bird was found."
    animal_analysis = taxonomy.analyze_incident_animals(text)
    assertion = animal_analysis.victim_assertions[0]
    assert len(assertion.evidence_excerpt) <= 320
    assert "bird" in assertion.evidence_excerpt.casefold()
    assert "mutilat" in assertion.evidence_excerpt.casefold()
    assert animal_analysis.evidence_sentences
    assert all(len(value) <= 500 for value in animal_analysis.evidence_sentences)
    assert all("bird" in value.casefold() for value in animal_analysis.evidence_sentences)
    assert all("mutilat" in value.casefold() for value in animal_analysis.evidence_sentences)

    record = source_record(text)
    source_analysis = seed.analyze_source_record(record)
    case = seed.build_candidate_record(record, source_analysis, 1)
    assert "bird" in case["summary"].casefold()
    assert "mutilat" in case["summary"].casefold()


def test_whirly_bird_helicopter_is_not_an_animal():
    analysis = taxonomy.analyze_incident_animals(
        'A bull was found mutilated; a yellow whirly-bird type helicopter was seen.'
    )
    assert [row.reported_taxon_key for row in analysis.victim_assertions] == ["cattle"]
    assert all(row.reported_taxon_key != "bird" for row in analysis.context_assertions)


def test_removed_content_placeholder_is_not_an_anatomical_finding():
    text = "This grey and reptiles been [Removed obscenity] with my head."
    assert taxonomy.analyze_incident_animals(text).victim_assertions == ()
    assert seed.analyze_source_record(source_record(text)).record_type != "mutilation_case"


@pytest.mark.parametrize(
    "text",
    [
        "There was NO blood on the pavement, no animal, no car, nothing!",
        "I have two cats and checked them and there was no blood on them.",
    ],
)
def test_absent_or_checked_unaffected_animals_are_not_victims(text):
    assert taxonomy.analyze_incident_animals(text).victim_assertions == ()
    assert seed.analyze_source_record(source_record(text)).record_type != "mutilation_case"


def test_complete_including_list_keeps_last_named_victim():
    analysis = taxonomy.analyze_incident_animals(
        "Hundreds of mutilated animal carcasses, including moose, grizzly bears, "
        "elk, caribou, and even a killer whale."
    )
    assert {row.reported_taxon_key for row in analysis.victim_assertions} == {
        "moose",
        "bear",
        "elk",
        "caribou",
        "whale",
    }


@pytest.mark.parametrize(
    "text",
    [
        "A lizard with track marks was found mutilated.",
        "The mutilated cat left tracks near the road.",
    ],
)
def test_track_language_does_not_suppress_a_linked_victim(text):
    analysis = taxonomy.analyze_incident_animals(text)
    assert len(analysis.victim_assertions) == 1


@pytest.mark.parametrize(
    "text",
    [
        "I have two cats and checked them and found them mutilated.",
        "I checked my cat and found it mutilated.",
    ],
)
def test_companion_language_does_not_suppress_anaphoric_pet_victim(text):
    analysis = taxonomy.analyze_incident_animals(text)
    assert [row.reported_taxon_key for row in analysis.victim_assertions] == ["cat"]


@pytest.mark.parametrize(
    "text",
    [
        "Hundreds of mutilated animal carcasses, including cows, were found while a horse stood nearby.",
        "Hundreds of mutilated animal carcasses, including cows, were found as a witness rode a horse.",
    ],
)
def test_animals_after_bounded_including_list_remain_context(text):
    analysis = taxonomy.analyze_incident_animals(text)
    assert [row.reported_taxon_key for row in analysis.victim_assertions] == ["cattle"]
    assert [row.reported_taxon_key for row in analysis.context_assertions] == ["horse"]


def test_by_agent_is_not_a_second_victim():
    analysis = taxonomy.analyze_incident_animals("A lizard was mutilated by a cow.")
    assert [row.reported_taxon_key for row in analysis.victim_assertions] == ["lizard"]
    assert [row.reported_taxon_key for row in analysis.context_assertions] == ["cattle"]


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("Un cerdo mutilado fue encontrado en el campo.", "pig"),
        ("Uma vaca mutilada foi encontrada no campo.", "cattle"),
        ("Eine verstummelte Kuh wurde gefunden.", "cattle"),
        ("Een verminkte koe werd gevonden.", "cattle"),
    ],
)
def test_multilingual_explicit_incidents(text, label):
    analysis = taxonomy.analyze_incident_animals(text)
    assert [row.normalized_common_name for row in analysis.victim_assertions] == [label]


def test_public_animal_row_carries_role_and_source_provenance():
    analysis = taxonomy.analyze_incident_animals("A mutilated hog was found.")
    row = taxonomy.assertion_to_public_row(analysis.victim_assertions[0], "source:fixture")
    assert row["normalized_common_name"] == "pig"
    assert row["reported_taxon_key"] == "pig"
    assert row["incident_role"] == "reported_victim"
    assert row["source_ids"] == ["source:fixture"]
    assert row["identification_basis"] == "sentence_local_explicit_mutilation"


def test_public_evidence_scrubs_private_contact_and_location_tokens():
    text = (
        "A mutilated pig was reported at 1234 Ranch Road; "
        "contact rancher@example.com or 303-555-1212 near 39.7392, -104.9903."
    )
    sanitized = seed.sanitize_public_excerpt(text)
    assert "rancher@example.com" not in sanitized
    assert "303-555-1212" not in sanitized
    assert "39.7392" not in sanitized
    assert "1234 Ranch Road" not in sanitized
    assert "[email withheld]" in sanitized
    assert "[coordinates withheld]" in sanitized
