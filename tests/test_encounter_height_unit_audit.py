"""Conservative unit triage: magnitudes and unrelated distances are not corrections."""
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "scripts/encounter_height_unit_audit.py"
spec = importlib.util.spec_from_file_location("encounter_height_unit_audit", path)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class HeightAuditSemantics(unittest.TestCase):
    def test_metric_height_preserves_unit(self):
        assertion = audit.extract_height_assertions("Being 0.5m tall emerged.")[0]
        self.assertEqual(assertion["unit"], "m")
        self.assertAlmostEqual(assertion["convertedFeet"], 1.6404199475)
        self.assertEqual(audit.classify_numeric_relation(0.5, assertion), "same_raw_number_different_unit_possible_coding_error")

    def test_distance_not_height(self):
        self.assertEqual(audit.extract_height_assertions("Object 0.5m away; being approached."), [])

    def test_reported_giant_not_error_from_magnitude(self):
        assertion = audit.extract_height_assertions("A 25m tall figure.")[0]
        self.assertEqual(audit.classify_numeric_relation(82, assertion), "agrees_with_unit_conversion_within_rounding")

    def test_native_float_rounding_not_false_unit_conflict(self):
        assertion = audit.extract_height_assertions("A 4.2ft tall being.")[0]
        self.assertEqual(audit.classify_numeric_relation(4.1999998, assertion), "agrees_with_unit_conversion_within_rounding")


if __name__ == "__main__":
    unittest.main()
