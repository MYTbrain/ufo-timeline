from parser.taxonomy import (
    display_shape_for_web_event,
    display_type_for_web_event,
    normalize_event_type_label,
    normalize_shape_label,
    visual_type_group_for_web_event,
)


def test_source_family_labels_are_not_object_types():
    for label in ("NUFORC", "MUFON", "BLUEBOOK", "UFODNA", "NICAP", "NIDS", "UKTNA"):
        assert normalize_event_type_label(label) is None
        assert display_type_for_web_event({"type_raw": label}) is None
        assert visual_type_group_for_web_event({"type_raw": label}) == "Other / unknown"


def test_shape_synonyms_collapse_to_web_display_labels():
    examples = {
        "disc": ("disk", "Disk"),
        "saucer": ("disk", "Disk"),
        "DomeDisc": ("disk", "Disk"),
        "triangular": ("triangle", "Triangle"),
        "orb": ("sphere", "Sphere / orb"),
        "Rectangl": ("rectangle", "Rectangle"),
        "Formatn": ("formation", "Formation"),
    }
    for raw_value, (normalized, display) in examples.items():
        assert normalize_shape_label(raw_value) == normalized
        assert display_shape_for_web_event({"shape_raw": raw_value}) == display


def test_web_type_prefers_shape_over_generic_sighting_labels():
    event = {
        "type_raw": "ufo sighting",
        "shape_raw": "Triangle",
    }
    assert display_type_for_web_event(event) == "Triangle"
    assert visual_type_group_for_web_event(event) == "UFO/UAP sighting"


def test_web_type_uses_priority_event_classes_when_shape_is_absent():
    assert display_type_for_web_event({"type_raw": "atomic"}) == "Nuclear / atomic event"
    assert visual_type_group_for_web_event({"type_raw": "atomic"}) == "Nuclear / atomic / weapons test"
    assert display_type_for_web_event({"type_raw": "close encounter"}) == "Close encounter / abduction"


def test_sentence_fragments_do_not_become_type_labels():
    assert normalize_event_type_label("the sky") is None
    assert display_type_for_web_event({"type_raw": "the sky"}) is None
    assert display_type_for_web_event({"type_raw": "Lights on object"}) == "Light"
