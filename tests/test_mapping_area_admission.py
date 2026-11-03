"""Conservative admission prevents area points becoming false site evidence."""
import unittest

from scripts.admit_mapping_area_references import admission, make_country_patterns


class AreaAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.record = {"summary": {"event_id": 1, "source": "nuforc", "has_coordinates": False,
            "coordinate_source": "unresolved", "location_raw": "United States", "location_precision": "country"},
            "source_detail": {"event_id": 1, "canonical_event_id": "evt_fixture", "source_id": "123",
                "source": "nuforc", "chunk_id": "chunk_fixture", "detail_index": 2,
                "duplicate_record_count": 1, "source_provenance_count": 1,
                "description": "I saw unusual lights overhead."}}
        self.candidate = {"event_id": 1, "country_code": "US", "admin1": None,
            "location_precision": "country", "display_label": "Approximate area reference: United States",
            "lat": 40, "lon": -100, "geoname_id": "6252001", "source_location_fields": {"Location": "United States"},
            "boundary_context": {"point_in_coarse_country_boundary": True, "bbox": [-125, 24, -66, 49]}}
        self.patterns = make_country_patterns({"US": {"name": "United States"}, "FR": {"name": "France"}})

    def admit(self, checks=None):
        return admission(self.record, self.candidate, checks or {}, self.patterns)

    def test_decision_has_current_summary_guards_and_immutable_identity(self):
        row, reason = self.admit()
        self.assertIsNone(reason)
        self.assertEqual(row["guard"]["coordinate_source"], "unresolved")
        self.assertIsNone(row["guard"]["lat"])
        self.assertEqual(row["source_identity"]["canonical_event_id"], "evt_fixture")
        reference = row["set_fields"]["location_reference"]
        self.assertEqual(reference["kind"], "country")
        self.assertIn("position unknown", reference["note"])
        self.assertIn("not historical", reference["note"])

    def test_merged_records_require_all_members_to_be_verified(self):
        for key in ["duplicate_record_count", "source_provenance_count"]:
            self.record["source_detail"][key] = 2
            row, reason = self.admit()
            self.assertIsNone(row)
            self.assertEqual(reason, "composite_members_not_independently_verified")
            self.record["source_detail"][key] = 1

    def test_missing_or_outside_coarse_boundary_held(self):
        self.candidate["boundary_context"] = None
        self.assertEqual(self.admit()[1], "country_boundary_unavailable")
        self.candidate["boundary_context"] = {"point_in_coarse_country_boundary": False}
        self.assertEqual(self.admit()[1], "area_point_outside_coarse_country_boundary")

    def test_existing_quarantine_is_not_bypassed(self):
        self.record["summary"]["coordinate_source"] = "quarantined"
        self.assertEqual(self.admit()[1], "prior_coordinate_review_or_quarantine")

    def test_original_coordinates_removed_from_current_view_are_held(self):
        self.record["source_detail"].update(lat=38, lon=-120, has_coordinates=True)
        self.assertEqual(self.admit()[1], "original_coordinates_removed_from_current_view")

    def test_administrative_city_homonym_requires_explicit_slot(self):
        self.candidate.update(country_code="US", admin1="WA", location_precision="state",
            display_label="Approximate area reference: Washington, United States",
            source_location_fields={"Location": "Washington, United States"})
        self.assertEqual(self.admit()[1], "generic_admin_name_not_checked_against_cities")
        self.assertEqual(self.admit({("US", "washington"): {"4140963"}})[1], "city_admin_name_collision")
        self.candidate["source_location_fields"] = {"Location": "unknown, WA, United States"}
        row, reason = self.admit({("US", "washington"): {"4140963"}})
        self.assertIsNone(reason)
        self.assertNotIn("bounds", row["set_fields"]["location_reference"])

    def test_full_raw_narrative_can_disqualify_clean_summary(self):
        for text, expected in [
            ("We were aboard a ship.", "route_or_offshore_context_requires_review"),
            ("The sighting happened in France.", "other_country_in_full_source_context"),
            ("I was on the moon.", "non_terrestrial_context"),
            ("This is a book review.", "documentary_publisher_or_address_context"),
        ]:
            self.record["source_detail"]["raw_source_row"] = {"description": text}
            self.assertEqual(self.admit()[1], expected)

    def test_existing_coordinates_are_never_replaced(self):
        self.record["summary"].update(lat=35, lon=-100)
        self.assertEqual(self.admit()[1], "current_view_already_mapped")

    def test_test_submissions_and_non_observation_timeline_entries_are_held(self):
        for text, reason in [("TEST ONLY TEST ONLY", "test_or_placeholder_submission"),
                             ("Operation Desert Storm", "observation_context_not_established")]:
            self.record["source_detail"]["description"] = text
            self.assertEqual(self.admit()[1], reason)


if __name__ == "__main__":
    unittest.main()
