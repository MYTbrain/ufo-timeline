"""Encounter evidence checks target source semantics and extraction traps."""
from copy import deepcopy
import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_encounter_evidence", ROOT / "scripts/build_encounter_evidence.py")
encounter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(encounter)


def event(source="ufocat", **fields):
    return {"event_id": 123, "source": source, "source_id": "source-1", "raw_source_row": fields}


class EncounterEvidenceTests(unittest.TestCase):
    def test_hynek_ce4_is_a_reported_source_class_not_a_verified_claim(self):
        row = encounter.classify(event(HYNEK="CE4", NOTES="Missing time and bright lights"))
        self.assertEqual(row["abductionStatus"], "source_reported")
        self.assertEqual(row["beingTypes"], [])
        self.assertEqual(row["craftAssociation"], "not_established")

    def test_vallee_ce4_and_biological_or_missing_time_major_codes_are_not_abductions(self):
        for fields in [{"VALLEE": "CE4"}, {"TYPE": "9"}, {"TYPE": "9L"}, {"TYPE": "9M"}]:
            self.assertIsNone(encounter.classify(event(**fields)))

    def test_disappearance_teleportation_subtypes_remain_ambiguous(self):
        for code in ["9A", "9B", "9BGW", "9LYB"]:
            row = encounter.classify(event(TYPE=code))
            self.assertEqual(row["abductionStatus"], "ambiguous")
        row = encounter.classify(event(TYPE="9A", NOTES="Car just ahead suddenly vanished when fog lifted."))
        self.assertEqual(row["abductionStatus"], "ambiguous")

    def test_own_narrative_can_narrow_broader_source_class(self):
        row = encounter.classify(event(TYPE="9B", NOTES="Abduction, medical exam. Two grey beings took me aboard a UFO."))
        self.assertEqual(row["abductionStatus"], "narrative_reported")
        self.assertIn("grey", row["beingTypes"])
        self.assertEqual(row["craftAssociation"], "explicit")

    def test_exact_majestic_type_and_nuforc_possible_attribute_stay_distinct(self):
        coded = encounter.classify(event("majestic", **{"type/0": "Mass abduction"}))
        possible = encounter.classify(event("nuforc", Characteristics="Possible abduction, Missing time"))
        self.assertEqual(coded["abductionStatus"], "source_reported")
        self.assertEqual(possible["abductionStatus"], "ambiguous")
        self.assertIsNone(encounter.classify(event("majestic", **{"type/0": "Close encounter / abduction"})))

    def test_all_sources_support_guarded_own_report_narratives(self):
        for source, field in [("mufon", "Long Description"), ("nuforc", "Description"), ("majestic", "desc"), ("phenomenainon_updb", "description")]:
            row = encounter.classify(event(source, **{field: "I was abducted by three grey beings aboard a UFO."}))
            self.assertEqual(row["abductionStatus"], "narrative_reported")
            self.assertIn("grey", row["beingTypes"])

    def test_negation_publication_prior_incident_and_speculation_do_not_become_asserted_reports(self):
        held = [
            "I saw a UFO but was not abducted and never saw aliens.",
            "The book discusses abduction research and grey aliens.",
            "I was abducted by grey aliens years ago.",
            "I read about another abduction by grey beings.",
            "My dream seemed like an abduction by grey aliens.",
            "I read a book. The victim was abducted by grey aliens.",
            "This reminded me of Betty and Barney Hill, who were abducted by grey aliens.",
            "This was another case from years ago. The man was abducted by grey aliens.",
            "I saw a UFO. I have been abducted since age5 and have seen aliens in my room.",
            "I was intently looking at a vacant field and wanting to see the aliens do something.",
            "I saw blobs and everyone said they were aliens and were gonna abduct us.",
        ]
        for text in held:
            self.assertIsNone(encounter.classify(event("mufon", **{"Long Description": text})), text)
        row = encounter.classify(event("mufon", **{"Long Description": "Maybe I was abducted by grey aliens in a UFO."}))
        self.assertEqual(row["abductionStatus"], "ambiguous")
        self.assertEqual(row["beingTypes"], [])
        dream = encounter.classify(event("mufon", **{"Long Description": "In a dream I was abducted by grey aliens."}))
        self.assertEqual(dream["abductionStatus"], "ambiguous")
        self.assertEqual(dream["beingTypes"], [])

    def test_grey_objects_and_ordinary_human_beings_do_not_become_grey_entities(self):
        for text in [
            "I saw a grey triangular craft.", "I saw human beings on a grey airplane.",
            "I saw an alien craft.", "I saw a grey alien triangular craft.",
            "I saw an alien-looking spacecraft.", "I saw a human-made object and a robot aircraft.",
            "I saw a UFO whose light was being reflected in a mirror.",
            "I saw two space alien ships fighting with each other.",
            "I saw nine alien spacecrafts in my lifetime.",
            "I know an alien UFO when I see one.",
            "I saw alien lights and alien UFO's.",
        ]:
            self.assertIsNone(encounter.classify(event("mufon", **{"Long Description": text})))

    def test_occupant_only_and_anomaly_rows_are_not_craft_associations(self):
        row = encounter.classify(event(Ufonaut="Grey", HYNEK="CE3", VALLEE="AN3", TYPE="0H", OBJS="0", NOTES="Two grey beings by a river."))
        self.assertEqual(row["beingTypes"], ["grey"])
        self.assertEqual(row["craftAssociation"], "none_reported")
        other = encounter.classify(event(Ufonaut="Humanoid", TYPE="7", OBJS="0"))
        self.assertEqual(other["craftAssociation"], "none_reported")

    def test_positive_object_count_is_only_coreporting_unless_relationship_is_explicit(self):
        row = encounter.classify(event(Ufonaut="Dwarf", TYPE="7", OBJS="1", SHAPE="Cigar"))
        self.assertEqual(row["craftAssociation"], "co_reported")
        explicit = encounter.classify(event(Ufonaut="Dwarf", TYPE="7", OBJS="1", NOTES="Three small humanoids emerged from a cigar-shaped craft."))
        self.assertEqual(explicit["craftAssociation"], "explicit")
        coded = encounter.classify(event(VALLEE="FB3", OBJS="1"))
        self.assertEqual(coded["craftAssociation"], "explicit")

    def test_explicit_no_craft_text_negates_the_relation_not_the_being(self):
        row = encounter.classify(event("mufon", **{"Long Description": "I saw two grey beings by a river. No UFO was seen."}))
        self.assertIn("grey", row["beingTypes"])
        self.assertEqual(row["craftAssociation"], "none_reported")

    def test_height_and_uniform_preserve_actual_source_fields_without_inventing_a_type(self):
        raw = event(Height="3.5", Uniform="Silver coverall")
        original = deepcopy(raw)
        row = encounter.classify(raw)
        self.assertEqual(raw, original)
        self.assertEqual(row["beingTypes"], ["unspecified"])
        self.assertEqual(row["heightFeet"], 3.5)
        self.assertEqual(row["uniform"], "Silver coverall")
        self.assertNotIn("small_humanoid", row["beingTypes"])
        for value in ["NaN", "Infinity", "-1", "0", ""]:
            row = encounter.classify(event(Ufonaut="Grey", Height=value))
            self.assertNotIn("heightFeet", row)

    def test_original_labels_and_multiple_appearance_groups_are_preserved(self):
        row = encounter.classify(event(Ufonaut="Hairy dwarf", OBJS="0"))
        self.assertEqual(row["beingTypes"], ["small_humanoid", "hairy"])
        self.assertEqual(row["evidence"][0]["excerpt"], "Hairy dwarf")
        self.assertEqual(encounter.source_being_types("Uncatalogued descriptor"), ["other_described"])
        self.assertEqual(encounter.source_being_types("LGM"), ["other_described"])

    def test_numeric_height_tall_is_not_a_qualitative_tall_type(self):
        row = encounter.classify(event("mufon", **{"Long Description": "I saw a UFO. There was a 4' tall humanoid being standing beside it."}))
        self.assertIn("humanoid", row["beingTypes"])
        self.assertNotIn("tall_humanoid", row["beingTypes"])
        other = encounter.classify(event(Ufonaut="Tall", NOTES="I saw a UFO and a 4' tall humanoid beside it."))
        self.assertIn("tall_humanoid", other["beingTypes"])

    def test_held_record_frames_do_not_remove_source_coded_facts(self):
        row = encounter.classify(event(HYNEK="CE4", Ufonaut="Grey", NOTES="I read a book. I have been abducted since age5."))
        self.assertEqual(row["abductionStatus"], "source_reported")
        self.assertEqual(row["beingTypes"], ["grey"])
        self.assertTrue(all(not e["ruleId"].startswith("narrative_") for e in row["evidence"]))

    def test_build_pins_original_source_bytes_and_fails_on_identity_or_count_drift(self):
        with tempfile.TemporaryDirectory(prefix="encounter-evidence-fixture-") as folder:
            root = Path(folder)
            chunks = root / "data/canonical_web/event_chunks"
            chunks.mkdir(parents=True)
            item = event(HYNEK="CE4")
            path = chunks / "chunk_000000.json"
            original = json.dumps([item]).encode()
            path.write_bytes(original)
            output = root / "output"
            manifest = encounter.build(root, output, expected_count=1)
            packed = (output / "evidence.json.gz").read_bytes()
            payload = json.loads(gzip.decompress(packed))
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(payload["rows"][0]["eventId"], "123")
            self.assertEqual(payload["rows"][0]["sourceRef"]["chunkSha256"], encounter.digest(original))
            self.assertEqual(encounter.digest(packed), manifest["artifact"]["gzipSha256"])
            self.assertEqual(encounter.digest(gzip.decompress(packed)), manifest["artifact"]["decodedSha256"])
            self.assertLess(sum(p.stat().st_size for p in output.iterdir()), encounter.MAX_OUTPUT_BYTES)
            with self.assertRaisesRegex(ValueError, "Catalog count drift"):
                encounter.build(root, root / "other", expected_count=2)
            path.write_bytes(json.dumps([item, item]).encode())
            with self.assertRaisesRegex(ValueError, "unsafe, repeated"):
                encounter.build(root, root / "duplicate", expected_count=2)


if __name__ == "__main__":
    unittest.main()
