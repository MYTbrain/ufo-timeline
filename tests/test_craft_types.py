from parser.craft_types import infer_event_craft_type, is_unknownish


def test_unknownish_tokens_cover_common_empty_values():
    assert is_unknownish("Unknown")
    assert is_unknownish("not reported")
    assert is_unknownish("")
    assert not is_unknownish("Triangle")


def test_explicit_shape_is_high_confidence():
    result = infer_event_craft_type({
        "shape_normalized": "Triangle",
        "type_normalized": "Unknown",
        "description": "A bright object was seen.",
    })

    assert result["craft_type_inferred"] == "triangle"
    assert result["craft_type_confidence"] == "high"
    assert result["craft_type_source"] == "shape_normalized"
    assert result["same_day_match_strength"] == "strong"


def test_description_can_recover_unknown_shape_without_rewriting_source():
    result = infer_event_craft_type({
        "shape_normalized": "Unknown",
        "type_normalized": "Unknown",
        "description": "Witness reported a rectangular object with rounded edges.",
    })

    assert result["craft_type_inferred"] == "rectangle_box"
    assert result["craft_type_confidence"] == "medium"
    assert result["craft_type_source"] == "description"
    assert result["same_day_match_strength"] == "strong"


def test_plural_oval_and_arrow_terms_are_recovered():
    ovals = infer_event_craft_type({
        "shape_normalized": "Unknown",
        "type_normalized": "Unknown",
        "description": "Three gun metal grey ovals blinked in and out.",
    })
    arrows = infer_event_craft_type({
        "shape_normalized": "Unknown",
        "type_normalized": "Unknown",
        "description": "Witness briefly saw three fleches moving quickly.",
    })

    assert ovals["craft_type_inferred"] == "oval_egg"
    assert arrows["craft_type_inferred"] == "chevron_boomerang"


def test_plural_and_source_spelling_shape_terms_are_recovered():
    cases = [
        ("Three gray discs hovered above the town.", "disc_saucer"),
        ("Two classic-shaped discoid objects flew over the lake.", "disc_saucer"),
        ("Three saucers stacked vertically.", "disc_saucer"),
        ("A dull metallic bowl-shaped flying object descended.", "disc_saucer"),
        ("A large orange globe moved over the ridge.", "sphere_orb"),
        ("An oblate spheroid moved rapidly.", "sphere_orb"),
        ("A bright white roundish object changed shape.", "sphere_orb"),
        ("Two cylinders hung vertically in the sky.", "cigar_cylinder"),
        ("A huge silver cylindrical object glided overhead.", "cigar_cylinder"),
        ("Four cubes connected in a stack.", "rectangle_box"),
        ("Several rectangles moved together.", "rectangle_box"),
        ("A stack of cigars flew toward Montpellier.", "cigar_cylinder"),
        ("Two boomerangs joined at the center.", "chevron_boomerang"),
        ("A vshaped object crossed the moon.", "chevron_boomerang"),
        ("Three pyramids hovered silently.", "cone"),
        ("Two cones rotated above the house.", "cone"),
        ("Three diamonds moved east.", "diamond"),
    ]

    for description, expected_type in cases:
        result = infer_event_craft_type({
            "shape_normalized": "Unknown",
            "type_normalized": "Unknown",
            "description": description,
        })
        assert result["craft_type_inferred"] == expected_type
        assert result["craft_type_confidence"] == "medium"


def test_multilingual_direct_shape_terms_are_recovered():
    cases = [
        ("Objeto en forma de disco brillante.", "disc_saucer"),
        ("Observation d'un disque au-dessus des arbres.", "disc_saucer"),
        ("Pulsierende Scheibe am Himmel.", "disc_saucer"),
        ("Dos esferas de luz paralelas.", "sphere_orb"),
        ("Deux boules lumineuses ont traversé le ciel.", "sphere_orb"),
        ("Weiße Kugel die Farbe ändert.", "sphere_orb"),
        ("Un cilindro estacionado en el horizonte.", "cigar_cylinder"),
        ("Un objet triangulaire stationnaire.", "triangle"),
        ("Tres luces formando un triángulo.", "triangle"),
        ("Cubo negro en la patagonia.", "rectangle_box"),
        ("Objet rectangulaire très lumineux.", "rectangle_box"),
        ("Objeto ovalado blanco.", "oval_egg"),
        ("Objeto en forma de diamante.", "diamond"),
        ("Masse noire accompagnee du losange brillant.", "diamond"),
        ("Aparentemente con forma de cono.", "cone"),
        ("Plusieurs lumières blanches.", "light"),
        ("Dos luces alargadas.", "light"),
    ]

    for description, expected_type in cases:
        result = infer_event_craft_type({
            "shape_normalized": "Unknown",
            "type_normalized": "Unknown",
            "description": description,
        })
        assert result["craft_type_inferred"] == expected_type


def test_generic_light_stays_low_confidence_and_weak_for_matching():
    result = infer_event_craft_type({
        "shape_normalized": "Light",
        "type_normalized": "Unknown",
        "description": "Light in the sky.",
    })

    assert result["craft_type_inferred"] == "light"
    assert result["craft_type_confidence"] == "low"
    assert result["same_day_match_strength"] == "weak"


def test_raw_fields_can_recover_when_primary_fields_are_unknown():
    result = infer_event_craft_type({
        "shape_normalized": "Unknown",
        "type_normalized": "Unknown",
        "raw_fields": {
            "shape": "unk",
            "notes": "large cigar-shaped craft moved silently",
        },
    })

    assert result["craft_type_inferred"] == "cigar_cylinder"
    assert result["craft_type_confidence"] == "medium"
    assert result["craft_type_source"] == "raw_fields"


def test_common_legacy_shape_terms_are_recovered_conservatively():
    cases = [
        ("Football", "oval_egg", "high", "shape_raw"),
        ("Elliptic", "oval_egg", "high", "shape_raw"),
        ("Dome", "disc_saucer", "high", "shape_raw"),
        ("Ring", "disc_saucer", "high", "shape_raw"),
        ("Top-shaped", "disc_saucer", "high", "shape_raw"),
        ("Oblong", "cigar_cylinder", "high", "shape_raw"),
        ("capsule", "cigar_cylinder", "high", "shape_raw"),
        ("Tic Tac", "cigar_cylinder", "high", "shape_raw"),
        ("Box", "rectangle_box", "high", "shape_raw"),
        ("Almond", "oval_egg", "high", "shape_raw"),
        ("Egg shape", "oval_egg", "high", "shape_raw"),
        ("Crescent", "chevron_boomerang", "high", "shape_raw"),
        ("Orbs", "sphere_orb", "high", "shape_raw"),
        ("Flashes", "light", "low", "shape_raw"),
        ("Linear", "formation", "medium", "shape_raw"),
        ("Top", "disc_saucer", "high", "shape_raw"),
        ("Torpedo", "cigar_cylinder", "high", "shape_raw"),
        ("Fuselage", "cigar_cylinder", "medium", "shape_raw"),
        ("Blimp", "cigar_cylinder", "medium", "shape_raw"),
        ("Arrow", "chevron_boomerang", "high", "shape_raw"),
        ("MantaRay", "chevron_boomerang", "medium", "shape_raw"),
        ("Pyramid", "cone", "high", "shape_raw"),
        ("Pear", "oval_egg", "medium", "shape_raw"),
        ("Glow", "light", "low", "shape_raw"),
        ("Streak", "light", "low", "shape_raw"),
        ("Wedge", "chevron_boomerang", "high", "shape_raw"),
        ("Wing", "chevron_boomerang", "medium", "shape_raw"),
        ("U-Shape", "chevron_boomerang", "medium", "shape_raw"),
        ("Banana", "cigar_cylinder", "medium", "shape_raw"),
        ("Missile", "cigar_cylinder", "medium", "shape_raw"),
        ("Bell", "cone", "medium", "shape_raw"),
        ("Dumbbell", "dumbbell_barbell", "high", "shape_raw"),
        ("Barbell", "dumbbell_barbell", "high", "shape_raw"),
    ]

    for shape_raw, expected_type, expected_confidence, expected_source in cases:
        result = infer_event_craft_type({
            "shape_normalized": "Unknown",
            "shape_raw": shape_raw,
            "type_normalized": "Unknown",
        })
        assert result["craft_type_inferred"] == expected_type
        assert result["craft_type_confidence"] == expected_confidence
        assert result["craft_type_source"] == expected_source


def test_low_signal_light_phrases_are_recovered_as_weak_matches():
    result = infer_event_craft_type({
        "shape_normalized": "Unknown",
        "type_normalized": "Unknown",
        "description": "A bright spot was stationary, then became a moving spot in the sky.",
    })

    assert result["craft_type_inferred"] == "light"
    assert result["craft_type_confidence"] == "low"
    assert result["same_day_match_strength"] == "weak"


def test_vague_or_conventional_shape_terms_stay_unknown():
    for shape_raw in ("Cloud", "Aircraft", "Copter", "Balloon", "Polygon"):
        result = infer_event_craft_type({
            "shape_normalized": "Unknown",
            "shape_raw": shape_raw,
            "type_normalized": "Unknown",
        })
        assert result["craft_type_inferred"] == "unknown"
        assert result["craft_type_confidence"] == "none"


def test_explicit_source_explanation_gets_non_craft_bucket():
    result = infer_event_craft_type({
        "shape_normalized": "Unknown",
        "type_normalized": "Unknown",
        "description": "Result: Meteor",
    })

    assert result["craft_type_inferred"] == "conventional_or_explained"
    assert result["craft_type_confidence"] == "medium"
    assert result["same_day_match_strength"] == "none"


def test_source_conventional_explanation_text_gets_non_craft_bucket():
    result = infer_event_craft_type({
        "shape_normalized": "Unknown",
        "type_normalized": "Unknown",
        "description": "The behavior most likely would have a conventional explanation.",
    })

    assert result["craft_type_inferred"] == "conventional_or_explained"
    assert result["craft_type_confidence"] == "medium"
    assert result["same_day_match_strength"] == "none"


def test_source_result_reflection_gets_non_craft_bucket():
    result = infer_event_craft_type({
        "shape_normalized": "Unknown",
        "type_normalized": "Unknown",
        "description": "Result: Reflection",
    })

    assert result["craft_type_inferred"] == "conventional_or_explained"
    assert result["same_day_match_strength"] == "none"


def test_probable_balloon_gets_non_craft_bucket_without_touching_plain_balloon_shape():
    explained = infer_event_craft_type({
        "shape_normalized": "Unknown",
        "type_raw": "Balloon - Probable",
        "shape_raw": "Unknown",
    })
    plain_shape = infer_event_craft_type({
        "shape_normalized": "Unknown",
        "shape_raw": "Balloon",
        "type_normalized": "Unknown",
    })

    assert explained["craft_type_inferred"] == "conventional_or_explained"
    assert plain_shape["craft_type_inferred"] == "unknown"


def test_ufocat_morphology_subtype_codes_are_source_gated():
    disc = infer_event_craft_type({
        "source_name": "ufocat",
        "shape_normalized": "Unknown",
        "type_raw": "DD",
        "raw_fields": {"TYPE": "2D", "HYNEK": "DD"},
    })
    cloud_cigar = infer_event_craft_type({
        "source_name": "ufocat",
        "shape_normalized": "Unknown",
        "type_raw": "3C",
        "raw_fields": {"TYPE": "3C"},
    })
    crescent = infer_event_craft_type({
        "source_name": "ufocat",
        "shape_normalized": "Unknown",
        "raw_fields": {"TYPE": "2Z"},
    })
    non_ufocat = infer_event_craft_type({
        "source_name": "mufon",
        "shape_normalized": "Unknown",
        "type_raw": "2D",
    })

    assert disc["craft_type_inferred"] == "disc_saucer"
    assert disc["craft_type_source"] == "ufocat_type_code"
    assert cloud_cigar["craft_type_inferred"] == "cigar_cylinder"
    assert crescent["craft_type_inferred"] == "chevron_boomerang"
    assert non_ufocat["craft_type_inferred"] == "unknown"


def test_ufocat_non_ufo_and_conventional_subtype_codes_do_not_become_craft_shapes():
    non_ufo = infer_event_craft_type({
        "source_name": "ufocat",
        "shape_normalized": "Unknown",
        "raw_fields": {"TYPE": "0M"},
    })
    conventional = infer_event_craft_type({
        "source_name": "ufocat",
        "shape_normalized": "Unknown",
        "raw_fields": {"TYPE": "1V"},
    })

    assert non_ufo["craft_type_inferred"] == "non_ufo_context"
    assert non_ufo["same_day_match_strength"] == "none"
    assert conventional["craft_type_inferred"] == "conventional_or_explained"
    assert conventional["same_day_match_strength"] == "none"


def test_ufocat_type_rules_use_raw_type_field_not_type_raw_fallback():
    hynek_dd_only = infer_event_craft_type({
        "source_name": "ufocat",
        "shape_normalized": "Unknown",
        "shape_raw": "Unknown",
        "type_raw": "DD",
        "raw_fields": {"TYPE": "", "HYNEK": "DD", "VALLEE": "FB1"},
    })
    type_raw_only = infer_event_craft_type({
        "source_name": "ufocat",
        "shape_normalized": "Unknown",
        "shape_raw": "Unknown",
        "type_raw": "2D",
        "raw_fields": {"TYPE": "", "HYNEK": "", "VALLEE": ""},
    })
    hynek_disc_not_type_disc = infer_event_craft_type({
        "source_name": "ufocat",
        "shape_normalized": "Unknown",
        "shape_raw": "Unknown",
        "type_raw": "DD",
        "raw_fields": {"HYNEK": "DD"},
    })

    assert hynek_dd_only["craft_type_inferred"] == "disc_saucer"
    assert hynek_dd_only["craft_type_source"] == "ufocat_hynek_daylight_disc"
    assert "TYPE `DD`" not in hynek_dd_only["craft_type_reason"]
    assert type_raw_only["craft_type_inferred"] == "unknown"
    assert hynek_disc_not_type_disc["craft_type_source"] == "ufocat_hynek_daylight_disc"


def test_ufocat_raw_type_does_not_fallback_to_hynek_or_vallee():
    result = infer_event_craft_type({
        "source_name": "ufocat",
        "shape_normalized": "Unknown",
        "shape_raw": "Unknown",
        "type_raw": "2D",
        "raw_fields": {"TYPE": "", "HYNEK": "CE2", "VALLEE": "FB1"},
    })

    assert result["craft_type_inferred"] == "unknown"
    assert result.get("unknown_reason") == "close_encounter_class_only"
    assert result["craft_type_source"] == "ufocat_hynek_code"


def test_ufocat_ce_values_are_encounter_metadata_not_craft_type():
    for field_name in ("HYNEK", "VALLEE"):
        result = infer_event_craft_type({
            "source_name": "ufocat",
            "shape_normalized": "Unknown",
            "shape_raw": "Unknown",
            "raw_fields": {field_name: "CE3"},
        })

        assert result["craft_type_inferred"] == "unknown"
        assert result["craft_type_confidence"] == "none"
        assert result.get("unknown_reason") == "close_encounter_class_only"


def test_ufocat_non_morphology_type_values_do_not_create_craft_type():
    for type_code in ("2", "5", "7", "8", "5S", "IFO", "."):
        result = infer_event_craft_type({
            "source_name": "ufocat",
            "shape_normalized": "Unknown",
            "shape_raw": "Unknown",
            "type_raw": type_code,
            "raw_fields": {"TYPE": type_code},
        })

        assert result["craft_type_inferred"] == "unknown"


def test_ufocat_safe_shape_metadata_mappings_do_not_create_craft_type():
    cloud = infer_event_craft_type({
        "source_name": "ufocat",
        "shape_normalized": "Unknown",
        "shape_raw": "Cloud",
        "raw_fields": {"SHAPE": "Cloud"},
    })
    copter = infer_event_craft_type({
        "source_name": "ufocat",
        "shape_normalized": "Unknown",
        "shape_raw": "Copter",
        "raw_fields": {"SHAPE": "Copter"},
    })
    aircraft = infer_event_craft_type({
        "source_name": "ufocat",
        "shape_normalized": "Unknown",
        "shape_raw": "Aircraft",
        "raw_fields": {"SHAPE": "Aircraft"},
    })

    assert cloud["craft_type_inferred"] == "unknown"
    assert cloud.get("object_morphology") == "cloud_like"
    assert copter["craft_type_inferred"] == "unknown"
    assert copter.get("prosaic_candidate") == "helicopter_like"
    assert aircraft["craft_type_inferred"] == "unknown"
    assert aircraft.get("prosaic_candidate") == "aircraft_like"


def test_ufocat_hynek_dd_is_medium_confidence_and_blocked_by_prosaic_shape():
    daylight_disc = infer_event_craft_type({
        "source_name": "ufocat",
        "shape_normalized": "Unknown",
        "shape_raw": "Unknown",
        "raw_fields": {"HYNEK": "DD"},
    })
    contradicted = infer_event_craft_type({
        "source_name": "ufocat",
        "shape_normalized": "Unknown",
        "shape_raw": "Aircraft",
        "raw_fields": {"SHAPE": "Aircraft", "HYNEK": "DD"},
    })

    assert daylight_disc["craft_type_inferred"] == "disc_saucer"
    assert daylight_disc["craft_type_confidence"] == "medium"
    assert daylight_disc["craft_type_source"] == "ufocat_hynek_daylight_disc"
    assert contradicted["craft_type_inferred"] == "unknown"
    assert contradicted.get("prosaic_candidate") == "aircraft_like"


def test_unknown_fallback_does_not_invent_precision():
    result = infer_event_craft_type({
        "shape_normalized": "Unknown",
        "type_normalized": "Unknown",
        "description": "Witness saw something unusual but gave no shape.",
    })

    assert result["craft_type_inferred"] == "unknown"
    assert result["craft_type_confidence"] == "none"
    assert result["same_day_match_strength"] == "none"
