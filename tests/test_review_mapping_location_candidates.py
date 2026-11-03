import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest

from scripts.review_mapping_location_candidates import (
    EXACT_SCREEN, MISSING_ADMIN, authority_name_index, geographic_reference,
    narrative_risks, review, run,
)
from scripts.recover_mapping_locations import GUARD_FIELDS


def feature(identity="2655603", name="Birmingham", lat=52.48142, lon=-1.89983, country="GB", admin="ENG"):
    return {"geonameId":identity,"name":name,"asciiName":name,"lat":lat,"lon":lon,
            "country":country,"admin1":admin,"featureClass":"P","featureCode":"PPLA2",
            "authorityUrl":"https://www.geonames.org/"+identity,
            "sourceLineSha256":"a"*64,"nameMatches":[{"key":name.lower(),"kind":"primary_or_ascii"}]}


def fixture(source="nuforc", country="GB", admin="ENG", label="Birmingham (UK/Birmingham), , United Kingdom"):
    summary = {"event_id":123,"source":source,"sort_date_iso":"2014-03-08","location_raw":label,
               "lat":None,"lon":None,"coordinate_source":"unresolved","location_precision":"city",
               "has_coordinates":False,"chunk_id":"chunk_000000","detail_index":4}
    location_field = "Location of Event" if source == "mufon" else "Location"
    narrative = "I was at home when I saw three unusual lights crossing the sky. They slowly disappeared behind the clouds."
    detail = {**summary,"description":narrative,"raw_fields":{location_field:label,"Description":narrative},
              "duplicate_record_count":1,"source_provenance_count":1}
    query = {"queryId":"place-1","locality":"Birmingham","country":country,"admin1":admin,
             "features":[feature(country=country,admin=admin)],"screen":EXACT_SCREEN}
    candidate = {"eventId":123,"chunkId":"chunk_000000","detailIndex":4,
                 "guards":{key:summary.get(key) for key in GUARD_FIELDS},
                 "parsedLocation":{"country":country,"admin1":admin,"holds":[],
                    "queryRefs":[{"queryId":"place-1","scope":"whole_label","locality":"Birmingham"}]},
                 "previousReview":{},"reviewLane":"new_qualified_locality_review",
                 "approximateAreaCandidate":None}
    snapshot = {"summary":summary,"source_detail":detail,
                "provenance":{"detail_index":4,"sha256":"b"*64,"source_detail_is_immutable_original":True,
                              "summary_is_current_effective_view":True}}
    return candidate,snapshot,{"place-1":query}


class SourceAdmissionTests(unittest.TestCase):
    def test_native_field_is_sufficient_without_city_repeated_in_narrative(self):
        candidate,snapshot,queries = fixture()
        decision = review(candidate,snapshot,queries)
        self.assertTrue(decision["accepted"])
        self.assertEqual(decision["set_fields"]["location_precision"],"city")
        self.assertEqual(set(decision["set_fields"]),{"lat","lon","has_coordinates","coordinate_source","location_precision"})
        self.assertEqual(decision["location_reference_evidence"]["originalLocationLabel"],snapshot["summary"]["location_raw"])
        self.assertIn("not_measured",decision["location_reference_evidence"]["locationRole"])
        self.assertFalse(decision["provenance"]["canonicalDataMutated"])

    def test_missing_admin_requires_unique_feature_across_explicit_country(self):
        candidate,snapshot,queries = fixture()
        candidate["parsedLocation"]["admin1"] = None
        candidate["parsedLocation"]["holds"] = [MISSING_ADMIN]
        queries["place-1"]["admin1"] = None
        result = review(candidate,snapshot,queries)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["location_reference_evidence"]["missingAdminResolvedBy"],"unique_primary_named_locality_in_explicit_country")
        queries["place-1"]["features"].append(feature("2",lat=52.482))
        queries["place-1"]["features"][0]["population"] = 1000000
        result = review(candidate,snapshot,queries)
        self.assertFalse(result["accepted"])
        self.assertIn("multiple_same_name_features_not_resolved_by_population",result["reasons"])

    def test_source_disagreement_prior_hold_and_composite_are_never_silently_cleared(self):
        for change,reason in (
            (lambda c,s,q:s["source_detail"]["raw_fields"].update(Location="Another city, UK"),"native_observation_location_missing_or_disagrees"),
            (lambda c,s,q:c["previousReview"].update(sourceHold="international_narrative_locality_not_corroborated"),"prior_source_hold_requires_new_independent_evidence"),
            (lambda c,s,q:s["source_detail"].update(duplicate_record_count=2),"composite_or_duplicate_source_identity_requires_review"),
            (lambda c,s,q:s["summary"].update(location_raw="Changed city, UK"),"current_summary_guard_mismatch"),
            (lambda c,s,q:q["place-1"]["features"][0].update(admin1="SCT"),"authority_jurisdiction_conflict"),
        ):
            candidate,snapshot,queries = fixture()
            change(candidate,snapshot,queries)
            result = review(candidate,snapshot,queries)
            self.assertFalse(result["accepted"])
            self.assertIn(reason,result["reasons"])
            self.assertNotIn("set_fields",result)

    def test_mufon_escaped_commas_and_unconfirmed_archives(self):
        candidate,snapshot,queries = fixture(source="mufon")
        snapshot["source_detail"]["raw_fields"]["Location of Event"] = snapshot["summary"]["location_raw"].replace(",", "\\,")
        self.assertTrue(review(candidate,snapshot,queries)["accepted"])
        candidate,snapshot,queries = fixture(source="majestic")
        result = review(candidate,snapshot,queries)
        self.assertIn("archive_location_field_semantics_not_independently_confirmed",result["reasons"])

    def test_full_narrative_including_remote_tail_blocks_wrong_roles(self):
        for ending,reason in (
            ("We were driving from London.","observer_travel_or_route"),
            ("I was the Captain of a commercial airliner.","observer_travel_or_route"),
            ("On my way to work I saw a light.","observer_travel_or_route"),
            ("I was watching a video of an object.","remote_media_or_republication"),
            ("This sighting was detected on photos I took.","remote_media_or_republication"),
            ("On three occasions I saw this object.","multiple_event_or_observer_locations"),
            ("We were twenty miles north of Birmingham.","distance_or_remote_locality"),
            ("I was on guard duty at the military base.","facility_or_noncity_observer_role"),
            ("This is not my sighting.","nonobservational_or_disputed_account"),
            ("The location was wrong.","explicit_location_qualification_or_conflict"),
        ):
            candidate,snapshot,queries = fixture()
            snapshot["source_detail"]["description_full"] = ("Ordinary account words "*300)+ending
            result = review(candidate,snapshot,queries)
            self.assertFalse(result["accepted"])
            self.assertIn(reason,result["reasons"])

    def test_independently_named_distant_observer_locality_is_held(self):
        anchors = [feature()]
        far = feature("9","Mumbai",19.07,72.87,"IN","16")
        index = authority_name_index({"q":{"features":anchors+[far]}})
        reasons,_ = narrative_risks("I was in Mumbai when I saw lights.",anchors,index)
        self.assertIn("different_named_observer_locality",reasons)
        reasons,_ = narrative_risks("I was in my backyard when I saw lights.",anchors,index)
        self.assertNotIn("different_named_observer_locality",reasons)

    def test_approximate_compound_references_require_unique_bounded_components(self):
        candidate,snapshot,queries = fixture(country="US",admin="WA",label="Everett/Snohomish, WA, USA")
        queries["place-1"]["features"] = []
        for identity,name,lat,lon in (("a","Everett",47.97898,-122.20208),("b","Snohomish",47.91288,-122.09818)):
            queries[identity] = {"queryId":identity,"features":[feature(identity,name,lat,lon,"US","WA")],"screen":EXACT_SCREEN}
        candidate["parsedLocation"]["holds"] = ["compound_places_require_source_review"]
        candidate["approximateAreaCandidate"] = {"country":"US","admin1":"WA","center":{"lat":47.946,"lon":-122.150},
            "radiusKm":16,"label":"Approximate area: Everett / Snohomish","uncertaintyStatement":"Named anchors plus display buffer, not exact observation.",
            "componentEvidence":[{"queryId":"a"},{"queryId":"b"}]}
        result = review(candidate,snapshot,queries)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["set_fields"]["location_precision"],"approximate")
        self.assertEqual(result["location_reference_evidence"]["radiusKm"],16)
        queries["b"]["features"][0]["lat"] = 40
        reference,_,reason = geographic_reference(candidate,queries)
        self.assertIsNone(reference)
        self.assertEqual(reason,"compound_component_diameter_above_100km")

    def test_complete_run_retains_every_hold_and_pins_inputs_without_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="mapping-source-review-test-") as folder:
            root = Path(folder)
            candidate,snapshot,queries = fixture()
            held_c = copy.deepcopy(candidate)
            held_s = copy.deepcopy(snapshot)
            held_c["eventId"] = 124
            held_c["previousReview"]["sourceHold"] = "manual_conflicting_observer_role"
            held_s["summary"]["event_id"] = held_s["source_detail"]["event_id"] = 124
            inputs = {"details":[snapshot,held_s],"candidates":[candidate,held_c],"queries":list(queries.values())}
            for key,rows in inputs.items():
                (root/(key+".jsonl")).write_text("".join(json.dumps(row)+"\n" for row in rows),encoding="utf8")
            args = (root/"details.jsonl",root/"candidates.jsonl",root/"queries.jsonl",root/"review")
            receipt = run(*args)
            self.assertEqual(receipt["counts"],{"sourceDetailsRead":2,"candidateRecords":2,"accepted":1,"held":1})
            self.assertTrue(receipt["inputs"]["sourceDetails"]["sha256"])
            with gzip.open(root/"review/held-decisions.jsonl.gz","rt",encoding="utf8") as handle:
                held = json.loads(next(handle))
            self.assertEqual(held["event_id"],124)
            self.assertIn("prior_source_hold_requires_new_independent_evidence",held["reasons"])
            self.assertLess(receipt["storage"]["uncompressedEvidenceBytes"],100*1024**2)
            with self.assertRaisesRegex(ValueError,"overwrite"):
                run(*args)
            (root/"details.jsonl").write_text(json.dumps(snapshot)+"\n",encoding="utf8")
            with self.assertRaisesRegex(ValueError,"Incomplete source snapshot"):
                run(*args[:3],root/"incomplete")


if __name__ == "__main__":
    unittest.main()
