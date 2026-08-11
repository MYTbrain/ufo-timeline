from __future__ import annotations

import copy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ENRICH = load_script(
    "crop_circle_description_enrichment",
    REPO_ROOT / "scripts" / "build_crop_circle_description_enrichment.py",
)
BUILDER = load_script(
    "crop_circle_web_artifact_builder",
    REPO_ROOT / "scripts" / "build_crop_circle_web_artifacts.py",
)


def builder_fixture() -> tuple[dict, dict]:
    record_url = "https://iccra.org/example-1996.html"
    collection_url = "https://iccra.org/index.html"
    export = {
        "schema_version": "crop-circle-timeline-export-v1.0.0",
        "source": {"source_commit": "atlas-source-commit"},
        "events": [{
            "event_id": 8742839877850,
            "event_hash": "cc_6e836743a510",
            "external_id": "cc_6e836743a510",
            "date_raw": "1996-09-23",
            "date_iso": "1996-09-23",
            "end_date_iso": None,
            "date_precision": "exact_day",
            "location_raw": "Antonito, Colorado, United States",
            "lat": 37.07918,
            "lon": -106.00863,
            "has_coordinates": True,
            "marker_confidence": "locality_only",
            "exact_coordinate_eligible": False,
            "coordinate_uncertainty_km": 30.0,
            "mapping_notes": "Locality centroid only.",
            "description": "Reported crop formation: Antonito. Maker not established.",
            "links": [record_url],
            "crop_circle": {
                "formation_id": "cc_6e836743a510",
                "place": "Antonito",
                "region": "Colorado",
                "country": "United States",
                "crop": None,
                "crop_normalized": "unknown",
                "classification": "unreviewed",
                "origin_status": "unreviewed_or_unknown",
                "source_family_names": ["ICCRA"],
                "assertion_count": 1,
                "multi_archive_coverage": False,
                "possible_multiple_formations_same_entity": False,
                "modal_morphology_family": None,
            },
        }],
        "morphology_occurrences": [],
        "source_assertions": [{
            "assertion_id": "iccra_case",
            "formation_id": "cc_6e836743a510",
            "source_name": "ICCRA",
            "source_record_url": record_url,
            "source_url": collection_url,
            "source_page": None,
            "source_listing_text": None,
            "notes": "This contaminated internal note must not ship.",
            "date_iso": "1996-09-23",
            "date_precision": "day",
        }],
        "image_links": [],
    }
    excerpt = "Twelve circles in pasture grass discovered near a cattle mutilation."
    description = {
        "formationId": "cc_6e836743a510",
        "assertionId": "iccra_case",
        "sourceName": "ICCRA",
        "sourceRecordUrl": record_url,
        "sourceCollectionUrl": collection_url,
        "sourceDate": "1996-09-23",
        "sourceDatePrecision": "day",
        "dateRole": "catalog_unspecified",
        "displayPolicy": "short_source_excerpt",
        "parserVersion": "iccra-primary-report-v2",
        "pageSha256": "0" * 64,
        "retrieval": "cache",
        "dateValidation": {
            "status": "matched_all",
            "assertionYear": 1996,
            "sourceRecordUrlYear": 1996,
            "pageHeadingYear": 1996,
        },
        "pageHeading": "Reported Crop Circles for the State of Colorado - Antonito (September 23, 1996)",
        "sourceExcerpt": excerpt,
        "sourceExcerptWordCount": len(excerpt.split()),
        "sourceExcerptTruncated": False,
        "sourceNarrativeDetected": True,
        "sourceNarrativeWordCount": len(excerpt.split()),
        "crop": "grass",
        "cropRaw": "grass",
        "sourceCredit": "Jeffrey Wilson",
        "sourceCreditDisplay": "Jeffrey Wilson",
        "sourceCreditRaw": "Jeffrey Wilson",
        "sourceAttributionRaw": ["Jeffrey Wilson"],
        "sourceAttributionAvailable": True,
    }
    envelope = {
        **description,
        "primaryAssertionId": "iccra_case",
        "sourceDescriptions": [description],
    }
    enrichment = {
        "schemaVersion": 1,
        "sourceExportSchema": export["schema_version"],
        "sourceCommit": "atlas-source-commit",
        "policy": {
            "maxSourceWords": 25,
            "rawHtmlPackaged": False,
            "fullArticleTextPackaged": False,
            "displayPolicy": "short_source_excerpt",
            "dateRole": "catalog_unspecified",
        },
        "counts": {
            "candidateAssertions": 1,
            "indexOnlyAssertionsSkipped": 0,
            "records": 1,
            "withSourceExcerpt": 1,
            "withCrop": 1,
            "withSourceCredit": 1,
            "withSourceAttribution": 1,
            "descriptionAssertions": 1,
            "sourceExcerptAssertions": 1,
            "duplicateFormationRecords": 0,
            "quarantinedDateMismatches": 0,
            "failures": 0,
        },
        "records": {"cc_6e836743a510": envelope},
        "failures": [],
    }
    return export, enrichment


class CropCircleDescriptionEnrichmentTest(unittest.TestCase):
    def test_iccra_primary_report_parser_extracts_actual_description(self) -> None:
        source = b"""
        <html><body><table><tr>
          <td valign="top" width="631">
            <p><strong>Reported Crop Circles for the State of Colorado - Antonito (September 23, 1996)</strong></p>
            <p>Twelve circles in pasture grass discovered near a cattle mutilation.</p>
            <p>Eyewitness report only.</p>
            <p>Crop type: grass</p>
            <p>Source: Jeffrey Wilson</p>
          </td>
          <td valign="top" width="238"><p>City / County / Date:</p></td>
        </tr></table></body></html>
        """
        result = ENRICH.parse_report(source, max_source_words=25)
        self.assertEqual(
            result["sourceExcerpt"],
            "Twelve circles in pasture grass discovered near a cattle mutilation. Eyewitness report only.",
        )
        self.assertEqual(result["crop"], "grass")
        self.assertEqual(result["sourceCredit"], "Jeffrey Wilson")
        self.assertFalse(result["sourceExcerptTruncated"])

    def test_source_excerpt_never_exceeds_publication_cap(self) -> None:
        words = " ".join(f"word{index}" for index in range(40))
        source = (
            '<td valign="top" width="631">'
            '<p>Reported Crop Circles for the State of Test - Case</p>'
            f"<p>{words}</p>"
            "</td>"
        ).encode("utf-8")
        result = ENRICH.parse_report(source, max_source_words=25)
        self.assertEqual(len(result["sourceExcerpt"].split()), 25)
        self.assertTrue(result["sourceExcerptTruncated"])

    def test_legacy_charset_and_non_state_heading_are_cleaned(self) -> None:
        source = (
            '<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">'
            '<td valign="top" width="631">'
            '<p>Reported Crop Circles for Puerto Rico - Ajuntas</p>'
            '<p>A witness described a “glowing” light above the field.</p>'
            '<p>Crop type: grass</p>'
            '</td>'
        ).encode("windows-1252")
        result = ENRICH.parse_report(source, max_source_words=25)
        self.assertEqual(result["sourceExcerpt"], 'A witness described a “glowing” light above the field.')
        self.assertNotIn("Reported Crop Circles", result["sourceExcerpt"])
        self.assertFalse(any("\u0080" <= char <= "\u009f" for char in result["sourceExcerpt"]))

    def test_photo_caption_and_inline_case_label_are_not_the_description(self) -> None:
        source = b"""
        <td valign="top" width="631">
          <p>Reported Crop Circles for the State of North Carolina - Charlotte</p>
          <p>Pictured: Eli Springs, Jr. Photo: Dick Van Halsema</p>
          <p>Charlotte, Mecklenburg County (August 8, 1991) Six circles were found after a thunderstorm.</p>
          <p>Crop type: soybeans</p>
        </td>
        """
        result = ENRICH.parse_report(
            source,
            max_source_words=25,
            leading_case_labels=("Charlotte, Mecklenburg County", "Charlotte"),
        )
        self.assertEqual(result["sourceExcerpt"], "Six circles were found after a thunderstorm.")
        self.assertNotIn("Pictured", result["sourceExcerpt"])

        malformed_export_label = ENRICH.strip_leading_case_label(
            "North Long Lake, Crow Wing County (February, 2002) No further details known.",
            ("Febuary 2002 - North Long Lake",),
        )
        self.assertEqual(malformed_export_label, "No further details known.")

    def test_primary_cell_fallback_recovers_legacy_report_and_splits_inline_metadata(self) -> None:
        source = b"""
        <td valign="top" width="631">
          <strong>Reported Crop Circles for the State of Ohio - Patterson's Corner,
          Greene County (July 5, 2005)</strong><br>
          A 44-foot irregular rectangle with a herringbone crop-lay pattern was found while harvesting.<br>
          Crop type: Unknown. Source: BLT, Inc. Photos: landowner
        </td>
        """
        result = ENRICH.parse_report(source, max_source_words=25)
        self.assertEqual(
            result["sourceExcerpt"],
            "A 44-foot irregular rectangle with a herringbone crop-lay pattern was found while harvesting.",
        )
        self.assertIsNone(result["crop"])
        self.assertEqual(result["cropRaw"], "Unknown.")
        self.assertEqual(result["sourceCreditDisplay"], "BLT, Inc.")
        self.assertTrue(result["sourceAttributionAvailable"])

    def test_inline_crop_and_photo_labels_do_not_leak_into_excerpt(self) -> None:
        source = b"""
        <td valign="top" width="631">
          <p>Reported Crop Circles for the State of Test - County (August 1, 1996)</p>
          <p>No further details known. Crop type: grass Photo: field owner</p>
          <p>Source: Jeffrey Wilson</p>
        </td>
        """
        result = ENRICH.parse_report(source, max_source_words=25)
        self.assertEqual(result["sourceExcerpt"], "No further details known.")
        self.assertEqual(result["crop"], "grass")
        self.assertEqual(result["sourceCreditDisplay"], "Jeffrey Wilson")
        self.assertNotRegex(result["sourceExcerpt"], r"(?i)crop type|photo:")

    def test_url_and_byline_preamble_are_skipped(self) -> None:
        source = b"""
        <td valign="top" width="631">
          <p>Reported Crop Circles for the State of Ohio - Chillicothe (September 2012)</p>
          <p>September 20, 2012 - Crop Circle News received a report.</p>
          <p>http://example.invalid/navigation</p>
          <p>Jeffrey Wilson - 9/24/12</p>
          <p>A landowner reported a complex formation near the Hopewell Mound Group.</p>
          <p>Crop type: corn</p>
        </td>
        """
        result = ENRICH.parse_report(source, max_source_words=25)
        self.assertEqual(
            result["sourceExcerpt"],
            "A landowner reported a complex formation near the Hopewell Mound Group.",
        )
        self.assertNotRegex(result["sourceExcerpt"], r"(?i)https?://|Jeffrey Wilson")

    def test_explicit_assertion_url_and_heading_year_mismatch_is_quarantinable(self) -> None:
        source_url = "https://iccra.org/case-(1952).html"
        source = b"""
        <td valign="top" width="631">
          <p>Reported Crop Circles for the State of Kentucky - Ashland (May 1952)</p>
          <p>A circular area of dead plants was reported.</p>
          <p>Crop type: unknown</p>
        </td>
        """
        assertion = {
            "formation_id": "cc_mismatch",
            "assertion_id": "iccra_mismatch",
            "source_name": "ICCRA",
            "source_record_url": source_url,
            "source_url": "https://iccra.org/index.html",
            "date_iso": "1967-05",
            "date_precision": "month",
            "place": "Ashland",
            "county": "Boyd County",
        }
        with tempfile.TemporaryDirectory() as temporary:
            cache_root = Path(temporary)
            ENRICH.cache_path(cache_root, source_url).write_bytes(source)
            with self.assertRaises(ENRICH.SourceDateMismatchError) as raised:
                ENRICH.enrich_assertion(
                    assertion,
                    cache_root=cache_root,
                    refresh=False,
                    offline=True,
                    timeout=1,
                    max_source_words=25,
                )
        self.assertEqual(raised.exception.evidence, {
            "assertionYear": 1967,
            "sourceRecordUrlYear": 1952,
            "pageHeadingYear": 1952,
        })

    def test_builder_separates_source_description_from_catalog_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            export_path = root / "export.json"
            enrichment_path = root / "descriptions.json"
            output = root / "output"
            export, enrichment = builder_fixture()
            export_path.write_text(json.dumps(export), encoding="utf-8")
            enrichment["sourceExportSha256"] = hashlib.sha256(export_path.read_bytes()).hexdigest()
            enrichment_path.write_text(json.dumps(enrichment), encoding="utf-8")

            manifest = BUILDER.build(
                export_path,
                output,
                "test-release",
                50,
                "https://assets.example.test/test-release/",
                enrichment_path,
                context_evidence_root=None,
            )
            self.assertEqual(manifest["sourceCommit"], "atlas-source-commit")
            self.assertEqual(manifest["counts"]["sourceDescriptions"], 1)
            self.assertEqual(manifest["counts"]["recordsWithSourceDescriptions"], 1)
            self.assertEqual(manifest["counts"]["sourceDescriptionAssertions"], 1)
            self.assertEqual(manifest["counts"]["mappedPositions"], 1)
            self.assertFalse(manifest["policy"]["traceEligible"])
            self.assertEqual(manifest["policy"]["cropChronologyRole"], "catalog_date_adjacency_only")

            with gzip.open(output / "details" / "chunk_000.json.gz", "rt", encoding="utf-8") as handle:
                detail = json.load(handle)["cc_6e836743a510"]
            self.assertEqual(
                detail["sourceDescription"],
                "Twelve circles in pasture grass discovered near a cattle mutilation.",
            )
            self.assertEqual(detail["catalogSummary"], export["events"][0]["description"])
            self.assertEqual(detail["crop"], "grass")
            self.assertEqual(detail["sourceDescriptionLabel"], "ICCRA — source narrative")
            self.assertEqual(detail["sourceDescriptionCreditDisplay"], "Jeffrey Wilson")
            self.assertTrue(detail["sourceDescriptionAttributionAvailable"])
            self.assertEqual(detail["sourceDescriptions"], [{
                "assertionId": "iccra_case",
                "text": "Twelve circles in pasture grass discovered near a cattle mutilation.",
                "truncated": False,
                "url": "https://iccra.org/example-1996.html",
                "sourceName": "ICCRA",
                "creditDisplay": "Jeffrey Wilson",
                "attributionAvailable": True,
            }])
            self.assertFalse(detail["traceEligible"])
            self.assertTrue(detail["cropChronologyEligible"])
            self.assertNotIn("notes", detail["sources"][0])
            self.assertNotIn("contaminated", json.dumps(detail))
            self.assertNotIn("sourceCreditRaw", json.dumps(detail))
            self.assertNotIn("sourceAttributionRaw", json.dumps(detail))

    def test_builder_preserves_multiple_assertion_descriptions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            export_path = root / "export.json"
            enrichment_path = root / "descriptions.json"
            output = root / "output"
            export, enrichment = builder_fixture()
            second_assertion = copy.deepcopy(export["source_assertions"][0])
            second_assertion.update({
                "assertion_id": "iccra_case_b",
                "source_record_url": "https://iccra.org/example-secondary-1996.html",
            })
            export["source_assertions"].append(second_assertion)
            export["events"][0]["crop_circle"]["assertion_count"] = 2

            envelope = enrichment["records"]["cc_6e836743a510"]
            second_description = copy.deepcopy(envelope["sourceDescriptions"][0])
            second_excerpt = "A second formation was reported."
            second_description.update({
                "assertionId": "iccra_case_b",
                "sourceRecordUrl": second_assertion["source_record_url"],
                "pageHeading": "Reported Crop Circles for the State of Colorado - Antonito #2 (1996)",
                "pageSha256": "1" * 64,
                "sourceExcerpt": second_excerpt,
                "sourceExcerptWordCount": len(second_excerpt.split()),
                "sourceNarrativeWordCount": len(second_excerpt.split()),
            })
            envelope["sourceDescriptions"].append(second_description)
            enrichment["counts"].update({
                "candidateAssertions": 2,
                "descriptionAssertions": 2,
                "sourceExcerptAssertions": 2,
                "duplicateFormationRecords": 1,
            })
            export_path.write_text(json.dumps(export), encoding="utf-8")
            enrichment["sourceExportSha256"] = hashlib.sha256(export_path.read_bytes()).hexdigest()
            enrichment_path.write_text(json.dumps(enrichment), encoding="utf-8")

            manifest = BUILDER.build(
                export_path,
                output,
                "duplicate-test",
                50,
                description_enrichment_path=enrichment_path,
                context_evidence_root=None,
            )
            self.assertEqual(manifest["counts"]["recordsWithSourceDescriptions"], 1)
            self.assertEqual(manifest["counts"]["sourceDescriptionAssertions"], 2)
            with gzip.open(output / "details" / "chunk_000.json.gz", "rt", encoding="utf-8") as handle:
                detail = json.load(handle)["cc_6e836743a510"]
            self.assertEqual(
                [item["assertionId"] for item in detail["sourceDescriptions"]],
                ["iccra_case", "iccra_case_b"],
            )

    def test_builder_rejects_unsafe_or_internally_inconsistent_enrichment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            export_path = root / "export.json"
            enrichment_path = root / "descriptions.json"
            export, base = builder_fixture()
            export_path.write_text(json.dumps(export), encoding="utf-8")
            base["sourceExportSha256"] = hashlib.sha256(export_path.read_bytes()).hexdigest()

            def unsafe_excerpt(payload: dict) -> None:
                item = payload["records"]["cc_6e836743a510"]["sourceDescriptions"][0]
                item["sourceExcerpt"] = "See https://example.invalid for the description."

            def wrong_date_evidence(payload: dict) -> None:
                item = payload["records"]["cc_6e836743a510"]["sourceDescriptions"][0]
                item["dateValidation"]["pageHeadingYear"] = 1997

            def missing_assertion_array(payload: dict) -> None:
                payload["records"]["cc_6e836743a510"]["sourceDescriptions"] = []

            def incorrect_counts(payload: dict) -> None:
                payload["counts"]["records"] = 2

            for label, mutate in {
                "unsafe excerpt": unsafe_excerpt,
                "wrong date evidence": wrong_date_evidence,
                "missing assertion array": missing_assertion_array,
                "incorrect counts": incorrect_counts,
            }.items():
                with self.subTest(label=label):
                    payload = copy.deepcopy(base)
                    mutate(payload)
                    enrichment_path.write_text(json.dumps(payload), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        BUILDER.load_description_enrichment(enrichment_path, export_path)

    def test_committed_enrichment_has_descriptions_and_quarantines_known_mismatches(self) -> None:
        payload = json.loads(
            (REPO_ROOT / "data" / "crop_circle_description_enrichment_v1.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload["counts"], {
            "candidateAssertions": 572,
            "descriptionAssertions": 566,
            "duplicateFormationRecords": 2,
            "failures": 6,
            "indexOnlyAssertionsSkipped": 35,
            "quarantinedDateMismatches": 5,
            "records": 564,
            "sourceExcerptAssertions": 566,
            "withCrop": 463,
            "withSourceAttribution": 555,
            "withSourceCredit": 431,
            "withSourceExcerpt": 564,
        })
        mismatch_ids = {
            failure["formationId"]
            for failure in payload["failures"]
            if failure.get("errorCode") == "source_record_date_mismatch"
        }
        self.assertEqual(mismatch_ids, {
            "cc_08d19207b2fc",
            "cc_3666f29391b5",
            "cc_57994754a6f2",
            "cc_ab95f1893c86",
            "cc_f70271bbfb6b",
        })
        recovered_ids = {
            "cc_092bbd9b8139", "cc_0bd99b5f01bc", "cc_0fdb69ce93fa", "cc_1249b0533691",
            "cc_13fb594def91", "cc_2152af98e2d7", "cc_24cc5e687d9f", "cc_2de1e38cfbe3",
            "cc_3fb745fb7416", "cc_589cfbecda43", "cc_5a40eb916407", "cc_5df51502813c",
            "cc_611f23bd8a62", "cc_76aa935eca59", "cc_7cdb63cfe429", "cc_8d9594f155d7",
            "cc_95b82c50e0d0", "cc_9e24b20abfd8", "cc_9f5c212449ec", "cc_a7e00ad128b6",
            "cc_ac244ef555fa", "cc_c2aae0e25f71", "cc_c53d381ed8ab", "cc_de15592eedb8",
            "cc_e6129d4180c8", "cc_ea974401cd6f", "cc_eaf79847abda", "cc_f3939cfc9f0e",
            "cc_f6c7487031e4", "cc_fcc20d494b91", "cc_fd8fecec9605",
        }
        self.assertTrue(all(payload["records"][formation_id]["sourceExcerpt"] for formation_id in recovered_ids))
        self.assertEqual(len(payload["records"]["cc_3e5e0b843661"]["sourceDescriptions"]), 2)
        self.assertEqual(len(payload["records"]["cc_7ab13a031edc"]["sourceDescriptions"]), 2)
        self.assertIsNone(payload["records"]["cc_7a7f001002bb"]["crop"])
        self.assertEqual(
            payload["records"]["cc_7a7f001002bb"]["cropRaw"],
            "NO CROP TYPE - Faked photo in newspaper",
        )
        antonito = payload["records"]["cc_6e836743a510"]
        self.assertEqual(
            antonito["sourceExcerpt"],
            "Twelve circles in pasture grass discovered near a cattle mutilation. Eyewitness report only.",
        )
        descriptions = [
            item
            for record in payload["records"].values()
            for item in record["sourceDescriptions"]
        ]
        self.assertTrue(all(item["sourceExcerpt"] for item in descriptions))
        self.assertTrue(all(len(item["sourceExcerpt"].split()) <= 25 for item in descriptions))
        self.assertFalse(any(re.search(r"(?i)https?://|www\.", item["sourceExcerpt"]) for item in descriptions))
        self.assertFalse(any(re.search(
            r"(?i)\b(?:crop\s*type|sources?|photos?|pictured|diagrams?)\s*:",
            item["sourceExcerpt"],
        ) for item in descriptions))


if __name__ == "__main__":
    unittest.main()
