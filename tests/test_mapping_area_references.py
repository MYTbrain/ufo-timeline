"""Evidence/precision boundaries for approximate administrative references."""
import unittest

from scripts.recover_mapping_area_references import build_authority_index, evaluate


def feature(ident, name, country, admin="", kind="PCLI"):
    return {"geonameId": str(ident), "name": name, "asciiName": name,
            "country": country, "admin1": admin, "featureCode": kind,
            "lat": 40.0, "lon": -100.0, "sourceLineSha256": "fixture"}


class AreaReferenceTests(unittest.TestCase):
    def setUp(self):
        countries = {c: {"iso2": c, "iso3": a, "name": n} for c, a, n in [
            ("US", "USA", "United States"), ("CA", "CAN", "Canada"),
            ("CN", "CHN", "China"), ("GB", "GBR", "United Kingdom"),
            ("FR", "FRA", "France"), ("GE", "GEO", "Georgia"),
        ]}
        features = [feature(i, v["name"], k) for i, (k, v) in enumerate(countries.items(), 1)]
        features += [feature(10, "California", "US", "CA", "ADM1"),
                     feature(11, "Indiana", "US", "IN", "ADM1"),
                     feature(12, "Ontario", "CA", "08", "ADM1"),
                     feature(13, "England", "GB", "ENG", "ADM1"),
                     feature(14, "Georgia", "US", "GA", "ADM1")]
        self.index = build_authority_index(features, countries)

    def run_record(self, fields, source="phenomenainon_updb", text="A witness saw unusual lights."):
        return evaluate({"summary": {"event_id": 123, "has_coordinates": False, "source": source,
                                      "location_raw": "preserved original label"},
                         "source_detail": {"event_id": 123, "source": source, "raw_fields": fields,
                                           "description": text}}, self.index)

    def test_explicit_country_field_is_area_not_observer_point(self):
        row, hold = self.run_record({"city": "", "country": "US", "location": "1234"})
        self.assertIsNone(hold)
        self.assertEqual(row["location_precision"], "country")
        self.assertEqual(row["coordinate_role"], "administrative_area_reference_not_observer_position")
        self.assertIn("Approximate area reference", row["display_label"])
        self.assertNotIn("location", row["source_location_fields"], "UPDB numeric location id is not place evidence")

    def test_country_code_in_typed_country_field_is_unambiguous(self):
        row, hold = self.run_record({"country": "CA"})
        self.assertIsNone(hold)
        self.assertEqual(row["country_code"], "CA")
        self.assertEqual(row["location_precision"], "country")

    def test_bare_country_or_admin_code_in_generic_location_is_held(self):
        for value in ["CA", "IN", "Georgia", "Congo"]:
            row, hold = self.run_record({"Location": value}, "nuforc")
            self.assertIsNone(row, value)
            self.assertIsNotNone(hold)

    def test_qualified_admin_code_wins_iso_country_collision(self):
        for value, admin in [("CA, US", "CA"), ("IN, US", "IN"), ("Georgia, US", "GA")]:
            row, hold = self.run_record({"Location": value}, "nuforc")
            self.assertIsNone(hold, value)
            self.assertEqual((row["country_code"], row["admin1"], row["location_precision"]), ("US", admin, "state"))

    def test_mufon_escaped_separators_retain_admin_evidence(self):
        row, hold = self.run_record({"Location of Event": r"unknown\, CA\, US"}, "mufon")
        self.assertIsNone(hold)
        self.assertEqual((row["country_code"], row["admin1"]), ("US", "CA"))

    def test_ufocat_cn_is_canada_but_updb_cn_is_china(self):
        row, hold = self.run_record({"STATE": "ON", "REGION": "CN"}, "ufocat")
        self.assertIsNone(hold)
        self.assertEqual((row["country_code"], row["admin1"], row["location_precision"]), ("CA", "08", "province"))
        row, hold = self.run_record({"country": "CN"})
        self.assertIsNone(hold)
        self.assertEqual(row["country_code"], "CN")

    def test_legacy_country_and_continent_are_source_specific(self):
        row, hold = self.run_record({"STATE": "FRA", "REGION": "EU"}, "ufocat")
        self.assertIsNone(hold)
        self.assertEqual(row["country_code"], "FR")
        row, hold = self.run_record({"city": "FRA", "country": "EU"})
        self.assertIsNone(row)

    def test_more_specific_unresolved_city_never_falls_back_to_country(self):
        row, hold = self.run_record({"city": "Unmatched Town", "country": "US"})
        self.assertIsNone(row)
        self.assertEqual(hold["reason"], "more_specific_location_not_resolved")

    def test_original_multi_location_fields_are_not_truncated(self):
        row, hold = self.run_record({"location/0": "France", "location/1": "United Kingdom"}, "majestic")
        self.assertIsNone(row)
        self.assertEqual(hold["reason"], "conflicting_country_evidence")

    def test_route_and_object_location_are_held(self):
        for value in ["Between California and Ontario", "Atlantic Ocean", "Lunar surface", "Headquarters, US"]:
            row, hold = self.run_record({"Location": value}, "nuforc")
            self.assertIsNone(row, value)

    def test_documentary_and_nonterrestrial_context_are_held(self):
        for text in ["Editorial on flying saucers.", "Objects seen aboard Apollo 11."]:
            row, hold = self.run_record({"country": "US"}, text=text)
            self.assertIsNone(row)
            self.assertIn(hold["reason"], {"documentary_or_publisher_context", "non_terrestrial_context"})

    def test_witness_address_is_not_an_event_location_field(self):
        row, hold = self.run_record({"witness_address": "California, US"}, "nuforc")
        self.assertIsNone(row)
        self.assertEqual(hold["reason"], "missing_original_location_fields")

    def test_uk_subdivision_is_not_collapsed_to_country(self):
        row, hold = self.run_record({"city": "UK/England", "country": "GB"})
        self.assertIsNone(hold)
        self.assertEqual((row["country_code"], row["admin1"], row["location_precision"]), ("GB", "ENG", "province"))

    def test_historical_country_never_silently_becomes_modern_country(self):
        row, hold = self.run_record({"city": "Soviet Union", "country": "US"})
        self.assertIsNone(row)
        self.assertEqual(hold["reason"], "historical_jurisdiction_requires_review")


if __name__ == "__main__":
    unittest.main()
