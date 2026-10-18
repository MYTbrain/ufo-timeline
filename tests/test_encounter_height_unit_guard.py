"""Keep disputed source heights out of feet statistics without guessing units."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("height_guard_builder", ROOT / "scripts/build_encounter_evidence.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def report(height, text):
    return {"event_id": 123, "source": "ufocat", "source_id": "fixture",
            "raw_source_row": {"Height": height, "Ufonaut": "Grey", "NOTES": text}}


class HeightUnitGuardTests(unittest.TestCase):
    def test_five_audited_native_stature_contexts_withhold_unqualified_feet(self):
        # Native IDs from the source-pinned full height-field audit. Excerpts
        # exercise actual attribution patterns, including a separate sentence.
        cases = [
            ("3645084554199960", "1", "Grandson saw 1m tall ape-like creature, dirty gray in color."),
            ("2838200802129686", "2.5", "Man saw silhouette walking ahead, 2.5m tall, like paper cut out."),
            ("3174520330725298", "0.5", "0.5m tall being with long arms emerged from object."),
            ("4024314512153275", "1.3", "Saw a group of humanoids, 1.3m tall, on side of road."),
            ("4326802475173721", "4.1999998", "Hunter shot Grey humanoid being. 4.2m tall. Was later abducted by 5 Greys."),
        ]
        for event_id, value, text in cases:
            with self.subTest(event_id=event_id):
                original = report(value, text)
                preserved = deepcopy(original)
                row = builder.classify(original)
                self.assertEqual(original, preserved)
                self.assertNotIn("heightFeet", row)
                self.assertIn("ufocat_height_unit_conflict", row["reviewFlags"])
                self.assertIn("grey", row["beingTypes"])
                self.assertNotIn("tall_humanoid", row["beingTypes"])
                self.assertTrue(any(e["field"] == "Height" and e["excerpt"] == value
                                    and e["ruleId"] == "ufocat_reported_height_unit_conflict_v1"
                                    for e in row["evidence"]))

    def test_distances_craft_sizes_and_witness_stature_do_not_contest_entity_height(self):
        texts = [
            "A being stood 1m away from the witness.",
            "The UFO was 1m tall. A being emerged.",
            "A grey being stood beside a UFO 1 metre tall.",
            "The witness was 1 meter tall. A being appeared.",
            "A being watched the 1m tall fence.",
            "A creature was 1m high above the ground.",
        ]
        for text in texts:
            with self.subTest(text=text):
                row = builder.classify(report("1", text))
                self.assertEqual(row["heightFeet"], 1)
                self.assertNotIn("ufocat_height_unit_conflict", row.get("reviewFlags", []))

    def test_other_numbers_and_native_rounding_do_not_invent_a_conversion(self):
        for height, text in [("6.56", "A 2m tall being."), ("4.1999998", "A 4.2ft tall being."),
                             ("4.3", "A 4.2m tall being."), ("1", "A 1cm tall being.")]:
            with self.subTest(height=height, text=text):
                row = builder.classify(report(height, text))
                self.assertEqual(row["heightFeet"], float(height))
                self.assertNotIn("ufocat_height_unit_conflict", row.get("reviewFlags", []))

    def test_multiple_entity_or_unit_context_is_explicitly_held_for_attribution(self):
        texts = [
            "A 1m tall being stood beside another creature.",
            "A 1m tall being stood beside a 3ft tall being.",
            "Hunter saw a being. 1m tall. Then three Greys appeared.",
        ]
        for text in texts:
            with self.subTest(text=text):
                row = builder.classify(report("1", text))
                self.assertNotIn("heightFeet", row)
                self.assertIn("ufocat_height_subject_ambiguous", row["reviewFlags"])

    def test_metres_and_hyphenated_stature_and_numeric_only_source_are_supported(self):
        for phrase in ["a 1 metre tall being", "a 1-meter-tall creature", "a being 1m in height"]:
            with self.subTest(phrase=phrase):
                original = report("1", phrase)
                del original["raw_source_row"]["Ufonaut"]
                row = builder.classify(original)
                self.assertNotIn("heightFeet", row)
                self.assertIn("ufocat_height_unit_conflict", row["reviewFlags"])
                self.assertEqual(row["beingTypes"], ["unspecified"])

    def test_helper_does_not_depend_on_or_mutate_records(self):
        self.assertEqual(builder.metric_height_conflicts(float("nan"), "A 1m tall being."), [])
        self.assertEqual(builder.metric_height_conflicts(0, "A 0m tall being."), [])
        self.assertEqual(builder.metric_height_conflicts(1, ""), [])
        match = builder.metric_height_conflicts(4.1999998, "A 4.2m tall being.")[0]
        self.assertEqual(match["unit"], "m")
        self.assertEqual(match["value"], 4.2)


if __name__ == "__main__":
    unittest.main()
