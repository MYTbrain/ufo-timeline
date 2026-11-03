import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.build_mapping_recovery_release import (
    GEO_FIELDS, apply_overlay, apply_summary_decision, build, detail_patch,
    pin, validate_decision,
)
from scripts.build_quality_map_release import GUARD_FIELDS, read_json, write_gzip_json, write_json


def row(identity=1,mapped=False):
    return {"event_id":identity,"canonical_event_id":f"native-{identity}","source_id":str(identity),
            "source":"mufon","chunk_id":"chunk_000000","detail_index":identity-1,
            "date_raw":"March 2014","date_iso":"2014-03-08","sort_date_iso":"2014-03-08",
            "date_precision":"exact_day","time_raw":"20:00","time_sort_kind":"unknown",
            "playback_sort_key":[3,None,None,3,0,str(identity)],"playback_sort_reason":"stable_fallback",
            "location_raw":"Town, WA, US","location_precision":"city",
            "coordinate_source":"geocoded" if mapped else "unresolved","has_coordinates":mapped,
            "lat":47.0 if mapped else None,"lon":-122.0 if mapped else None,
            "type":"Triangle","craft_type_inferred":"triangle","craft_type_confidence":"high",
            "craft_type_source":"shape_normalized","same_day_match_strength":"strong",
            "raw_fields":{"Long Description":"Original narrative remains unchanged."}}


def decision(source):
    guards={key:source.get(key) for key in GUARD_FIELDS}
    guards["source_id"]=source["source_id"]
    return {"event_id":source["event_id"],"decision_id":"test-"+str(source["event_id"]),
            "status":"accepted_source_supported","guards":guards,
            "set_fields":{"lat":48.1,"lon":-122.2,"has_coordinates":True,
                "coordinate_source":"reviewed_locality_reference","location_precision":"city",
                "location_reference":{"kind":"locality","label":"Town","note":"Approximate locality reference, not an observer position.",
                                      "authority_ids":["geonames:123"],"evidence_id":"test-source"}}}


class MappingReleaseTests(unittest.TestCase):
    def test_summary_missing_source_identity_is_deferred_but_current_geographic_guard_is_checked(self):
        full=row()
        current={key:value for key,value in full.items() if key not in ("source_id","raw_fields","canonical_event_id")}
        approved=decision(full)
        result=apply_summary_decision(current,approved)
        self.assertNotIn("source_id",result)
        self.assertEqual({k:v for k,v in result.items() if k not in GEO_FIELDS},
                         {k:v for k,v in current.items() if k not in GEO_FIELDS})
        approved["guards"]["location_raw"]="Other town"
        with self.assertRaisesRegex(ValueError,"guard"):
            apply_summary_decision(current,approved)

    def test_only_geographic_edits_and_bounded_reference_are_allowed(self):
        approved=decision(row())
        self.assertIs(validate_decision(approved),approved)
        for key,value in (("sort_date_iso","2014-01-01"),("type","Disk"),("raw_fields",{})):
            bad=copy.deepcopy(approved)
            bad["set_fields"][key]=value
            with self.assertRaisesRegex(ValueError,"non-geographic"):
                validate_decision(bad)
        bad=copy.deepcopy(approved)
        bad["set_fields"]["location_reference"]["note"]="x"*1500
        with self.assertRaisesRegex(ValueError,"1 KiB"):
            validate_decision(bad)
        bad=copy.deepcopy(approved)
        bad["set_fields"]["lat"]=float("nan")
        with self.assertRaisesRegex(ValueError,"coordinate"):
            validate_decision(bad)

    def test_overlay_order_nested_presence_and_augmented_identity_guards(self):
        original=row()
        quality={"eventId":1,"guards":{"location_precision":"city"},"setFields":{"quality_review":"retained"}}
        analysis={"eventId":1,"guards":[{"path":["quality_review"],"exists":True,"value":"retained"},
                                           {"path":["absent"],"exists":False,"value":None}],
                  "setFields":{"date_precision":"month","date_iso":"2014-03-01","sort_date_iso":"2014-03-01"}}
        with self.assertRaisesRegex(ValueError,"Prior overlay guard"):
            apply_overlay(original,analysis)
        effective=apply_overlay(apply_overlay(original,quality),analysis)
        approved=decision(effective)
        packet=detail_patch(original,effective,effective,approved)
        self.assertEqual(packet["guards"]["canonical_event_id"],"native-1")
        self.assertEqual(packet["guards"]["source_id"],"1")
        self.assertEqual(packet["guards"]["date_precision"],"month")
        self.assertEqual(set(packet["setFields"]),GEO_FIELDS)
        after=apply_overlay(effective,packet)
        self.assertEqual(after["date_iso"],"2014-03-01")
        self.assertEqual(after["quality_review"],"retained")
        self.assertEqual(after["raw_fields"],original["raw_fields"])
        wrong=copy.deepcopy(approved)
        wrong["guards"]["source_id"]="wrong"
        with self.assertRaisesRegex(ValueError,"effective detail guard"):
            detail_patch(original,effective,effective,wrong)

    def test_full_delta_keeps_date_repairs_and_distinguishes_new_maps_from_corrections(self):
        with tempfile.TemporaryDirectory(prefix="mapping-release-test-") as directory:
            root=Path(directory)
            base=root/"base"
            base.mkdir()
            originals=[row(1),row(2,True),row(3,True)]
            write_gzip_json(base/"event_chunks/chunk_000000.json.gz",originals)
            chunks=[{"id":"chunk_000000","file":"chunk_000000.json","event_count":3,"start_event_id":1,"end_event_id":3}]
            write_json(base/"event_chunk_manifest.json",chunks)
            write_json(base/"canonical_web_manifest.json",{"counts":{"events":3,"mapped_events":2}})
            quality_manifest=root/"quality_manifest.json"
            base_files={name:pin(base/name) for name in ("event_chunks/chunk_000000.json.gz","event_chunk_manifest.json","canonical_web_manifest.json")}
            write_json(quality_manifest,{"base":{"path":str(base),"files":base_files,"manifest_sha256":base_files["canonical_web_manifest.json"]["sha256"]}})
            quality_payload={"schemaVersion":1,"baseManifestSha256":base_files["canonical_web_manifest.json"]["sha256"],
                             "qualityManifestSha256":pin(quality_manifest)["sha256"],"patches":[]}
            quality_path=root/"quality.json.gz"
            write_gzip_json(quality_path,quality_payload)
            repair={"eventId":1,"guards":[{"path":["date_iso"],"exists":True,"value":"2014-03-08"}],
                    "setFields":{"date_iso":"2014-03-01","sort_date_iso":"2014-03-01","date_precision":"month","exact_day_eligible":False}}
            analysis_path=root/"analysis.json.gz"
            write_gzip_json(analysis_path,{"schemaVersion":1,"patches":[repair]})
            analysis_manifest=root/"analysis_manifest.json"
            ap=pin(analysis_path)
            write_json(analysis_manifest,{"gzipBytes":ap["bytes"],"gzipSha256":ap["sha256"],"sourcePins":{"existingQualityOverlayGzipSha256":pin(quality_path)["sha256"]}})
            effective=[apply_overlay(originals[0],repair),originals[1],originals[2]]
            summaries=[{k:v for k,v in r.items() if k not in ("source_id","canonical_event_id","raw_fields","date_iso")} for r in effective]
            current=root/"current"
            write_gzip_json(current/"summary_shards/summary_000000.json.gz",summaries)
            write_json(current/"summary_manifest.json",[{"id":"summary_000000","file":"summary_000000.json","event_count":3,"start_event_id":1,"end_event_id":3}])
            write_json(current/"canonical_web_manifest.json",{"counts":{"events":3,"mapped_events":2},"policy":{},
                "artifacts":{"event_chunks_dir":"https://example.test/shared/event_chunks/",
                             "trace_event_index":"https://example.test/old/trace_event_index.bin"}})
            uploads=[]
            for suffix,path in (("canonical_web/canonical_web_manifest.json",current/"canonical_web_manifest.json"),
                                ("canonical_web/summary_manifest.json",current/"summary_manifest.json"),
                                ("canonical_web/summary_shards/summary_000000.json.gz",current/"summary_shards/summary_000000.json.gz"),
                                ("analysis_repair_detail/patches.json.gz",analysis_path)):
                uploads.append({"key":"releases/current/data/"+suffix,"source":str(path),**{k:v for k,v in pin(path).items() if k!="path"}})
            plan=root/"delivery_plan.json"
            write_json(plan,{"uploads":uploads,"retained_rollback":{"id":"old-release"}})
            decisions=root/"accepted.jsonl"
            decisions.write_text("\n".join(json.dumps(decision(r)) for r in (effective[0],effective[2]))+"\n",encoding="utf8")
            output=root/"map-delta"
            with patch("scripts.build_mapping_recovery_release.verify_storage",return_value=10**10):
                result=build(plan,decisions,quality_manifest,quality_path,analysis_manifest,output)
            self.assertEqual(result["counts"]["mapped_events"],3)
            self.assertEqual(result["newlyMappedRecords"],1)
            self.assertEqual(result["existingMappedCorrections"],1)
            self.assertEqual(result["chronologyRecomputedRecords"],0)
            generated=read_json(output/"summary_shards/summary_000000.json.gz")
            self.assertEqual(generated[0]["date_precision"],"month")
            self.assertEqual(generated[0]["sort_date_iso"],"2014-03-01")
            self.assertEqual(generated[0]["playback_sort_key"],summaries[0]["playback_sort_key"])
            self.assertEqual(generated[1],summaries[1])
            self.assertFalse((output/"event_chunks").exists())
            canonical=read_json(output/"canonical_web_manifest.json")
            self.assertEqual(canonical["artifacts"]["trace_event_index"],"trace_event_index.bin")
            self.assertEqual(canonical["artifacts"]["event_chunks_dir"],"https://example.test/shared/event_chunks/")
            packet=read_json(output/"mapping_recovery_detail/patches.json.gz")
            self.assertEqual(packet["patchCount"],2)
            self.assertEqual(packet["baseManifestSha256"],base_files["canonical_web_manifest.json"]["sha256"])
            self.assertEqual(packet["qualityManifestSha256"],pin(decisions)["sha256"])
            manifest=read_json(output/"mapping_recovery_detail/manifest.json")
            self.assertEqual(manifest["qualityManifestSha256"],packet["qualityManifestSha256"])
            self.assertEqual(packet["patches"][0]["guards"]["date_precision"],"month")
            self.assertEqual(packet["patches"][0]["guards"]["source_id"],"1")
            with self.assertRaisesRegex(ValueError,"absent or empty"):
                build(plan,decisions,quality_manifest,quality_path,analysis_manifest,output)


if __name__ == "__main__":
    unittest.main()
