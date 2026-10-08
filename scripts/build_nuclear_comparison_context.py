"""Build a small, source-pinned nuclear comparison catalog without reading the UFO corpus.

The CSV is a separately licensed transcription of the FOA/SIPRI primary report.
No missing coordinates, yields, dates, event purposes, or positional errors are filled.
Run with a Python environment containing pypdf to reproduce the primary-table audit.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import re
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "analysis_comparisons"
SOURCES = DEST / "nuclear_sources"
COMMIT = "056ac3db13b392cb69be9f787e235738167e7fb1"
PRIMARY_URL = "https://www.iaea.org/inis/collection/NCLCollectionStore/_Public/31/060/31060372.pdf"
MIRROR_BASE = f"https://raw.githubusercontent.com/data-is-plural/nuclear-explosions/{COMMIT}/"
OFFICIAL_SOURCES = {
    "nnsa_locations": "https://www.energy.gov/nnsa/locations",
    "llnl_history": "https://www.llnl.gov/purpose/history",
    "awe_history": "https://www.awe.co.uk/about-us/our-history/",
    "oak_ridge_history": "https://www.energy.gov/orem/history",
    "lanl_history": "https://www.energy.gov/nnsa/articles/army-and-origins-nuclear-security-enterprise",
}
DOWNLOADS = {
    "sipri-report-original.pdf": MIRROR_BASE + "documents/sipri-report-original.pdf",
    "sipri-report-explosions.csv": MIRROR_BASE + "data/sipri-report-explosions.csv",
    "transcription-readme.md": MIRROR_BASE + "README.md",
    "transcription-license.txt": MIRROR_BASE + "LICENSE.txt",
    **{key + ".html": url for key, url in OFFICIAL_SOURCES.items()},
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value: str):
    try:
        return float(value) if value.strip() else None
    except (ValueError, AttributeError):
        return None


def event_role(purpose: str) -> str:
    tokens = purpose.split("/")
    if "COMBAT" in tokens:
        return "combat"
    # Mixed weapons/safety purposes are retained as mixed rather than silently
    # promoted to weapons; default comparison excludes them along with safety.
    if any(token in {"SE", "SAM", "SB", "SA", "S", "TRANSP"} for token in tokens):
        return "safety_or_mixed_safety"
    if any(token.startswith("PNE") or token == "P" for token in tokens):
        return "peaceful"
    if any(token in {"WR", "WE", "FMS", "ME", "F"} for token in tokens):
        return "weapons"
    return "unknown"


def verify_primary_table(csv_rows: list[dict]) -> dict:
    from pypdf import PdfReader
    reader = PdfReader(SOURCES / "sipri-report-original.pdf")
    by_key = {(r["date"], r["id_no"], r["country"]): r for r in csv_rows}
    # Layout extraction is important: the scanned report has column-first text
    # ordering under default extraction. The original page remains the evidence.
    pattern = re.compile(
        r"(\d{6})\s+(\d+(?:\.\d+)?)\s+(\d{5})\s+"
        r"(USA|USSR|FRANCE|UK|CHINA|INDIA|PAKIST)\s+(.*?)\s+"
        r"(DOE|MTM|HFS|WTN|NOA|NRD|ZAR|DIS|BKY|IDC|ISC|UGS|SPA)\s+"
        r"(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+\.\d+)\s+"
        r"(\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+([A-Z:/]+)"
    )
    checked, differences = {}, []
    for page_index in range(22, 40):
        content = reader.pages[page_index].extract_text(extraction_mode="layout")
        for match in pattern.finditer(content):
            key = (match[1], match[3], match[4])
            row = by_key.get(key)
            if not row:
                continue
            fields = {"origin_t": match[2], "latitude": match[7], "longitude": match[8],
                      "yield_1": match[12], "yield_u": match[13], "purpose": match[14]}
            errors = []
            for field, primary in fields.items():
                equal = row[field] == primary if field == "purpose" else number(row[field]) == number(primary)
                if not equal:
                    errors.append({"field": field, "transcription": row[field], "primary": primary})
            identity = "foa:" + row["country"] + ":" + row["date_long"] + ":" + row["id_no"]
            if errors:
                differences.append({"id": identity, "pdfPage": page_index + 1, "differences": errors})
            else:
                checked[identity] = page_index + 1
    return {"method": "pypdf_layout_exact_numeric_and_purpose_row_comparison",
            "fields": ["GMT_date", "country", "id_no", "origin_t", "latitude", "longitude", "yield_1", "yield_u", "purpose"],
            "verifiedRows": len(checked), "unverifiedRows": len(csv_rows) - len(checked),
            "differences": differences, "verifiedPdfPagesById": checked,
            "dateConventionPdfPage": 19, "coordinateAndPurposeConventionPdfPage": 20,
            "primaryTablePdfPages": [23, 40],
            "note": "Unparsed and differing OCR lines remain unverified; no source corrections are invented."}


def build(shared_root: Path, fetch: bool) -> dict:
    SOURCES.mkdir(parents=True, exist_ok=True)
    if fetch:
        for filename, url in DOWNLOADS.items():
            target = SOURCES / filename
            if target.exists():
                continue
            req = urllib.request.Request(url, headers={"User-Agent": "UFO-Timeline-source-review/1.0"})
            target.write_bytes(urllib.request.urlopen(req, timeout=45).read())
    with (SOURCES / "sipri-report-explosions.csv").open(encoding="utf-8", newline="") as stream:
        csv_rows = list(csv.DictReader(stream))
    audit = verify_primary_table(csv_rows)
    (SOURCES / "primary_table_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    checked = audit["verifiedPdfPagesById"]
    tests = []
    for source_row, r in enumerate(csv_rows, start=2):
        date = dt.datetime.strptime(r["date_long"], "%Y%m%d").date()
        lat, lon = number(r["latitude"]), number(r["longitude"])
        # Section 3.2 states zero/blank means unavailable, nil, or negligible.
        # The pair (0,0) is not interpreted as an explosion in the Gulf of Guinea.
        if lat == 0 and lon == 0:
            lat = lon = None
        identity = "foa:" + r["country"] + ":" + r["date_long"] + ":" + r["id_no"]
        low, high = number(r["yield_1"]), number(r["yield_u"])
        tests.append({"id": identity, "name": r["name"] or r["id_no"], "country": r["country"],
            "region": r["region"], "ordinal": (date - dt.date(1970, 1, 1)).days,
            "date": date.isoformat(), "datePrecision": "exact_day", "dateRole": "explosion_GMT_day",
            "originTimeGmtRaw": r["origin_t"], "lat": lat, "lon": lon,
            "coordinateEvidenceClass": "source_report_approximate", "uncertaintyKm": None,
            "yieldLowerKt": low if low and low > 0 else None, "yieldUpperKt": high if high and high > 0 else None,
            "yieldZeroMeaning": "unavailable_nil_or_negligible_not_imputed",
            "purposeRaw": r["purpose"], "role": event_role(r["purpose"]), "deployment": r["type"],
            "sourceCode": r["source"], "sourceCsvLine": source_row,
            "primaryTableVerified": identity in checked, "primaryPdfPage": checked.get(identity),
            "strictSpatialEligible": False,
            "strictExclusionReasons": ["source_position_is_often_approximate", "source_position_error_not_quantified"]
                + ([] if identity in checked else ["transcription_not_verified_against_primary_line"]),
            "unit": "published_test_or_group_explosion_record_not_individual_device"})
    # Match reviewed identities, not name keywords. Alternate markers are excluded
    # from the broad comparator so one institution cannot appear in both groups.
    existing_path = shared_root / "webapp" / "static_public" / "data" / "analysis_v2" / "facility_analysis_v1.json"
    existing = json.loads(existing_path.read_text(encoding="utf-8"))
    by_id = {r[0]: r for r in existing}
    reviews = [
        {"id": "facility:dfd76fba1347f76f32b3", "institutionId": "LANL", "aliases": ["facility:f0a28a98b8147660ef51"],
         "role": "nuclear_weapon_design", "startYear": 1943, "sources": ["nnsa_locations", "lanl_history"]},
        {"id": "facility:622bb756286c7167283e", "institutionId": "LLNL", "aliases": [],
         "role": "nuclear_weapon_design", "startYear": 1952, "sources": ["nnsa_locations", "llnl_history"]},
        {"id": "facility:946b08af4403614992e5", "institutionId": "ORNL", "aliases": [],
         "role": "nuclear_research", "startYear": 1943, "sources": ["oak_ridge_history"]},
        {"id": "facility:247c2ae0e6957534205b", "institutionId": "AWE_ALDERMASTON", "aliases": ["facility:a6ad33f65752222d9125"],
         "role": "nuclear_weapon_design_and_materials", "startYear": 1950, "sources": ["awe_history"]},
    ]
    nuclear_facilities = []
    for review in reviews:
        row = by_id[review["id"]]
        links = [{"url": OFFICIAL_SOURCES[key], "capturedFile": "nuclear_sources/" + key + ".html",
                  "sha256": digest(SOURCES / (key + ".html"))} for key in review["sources"]]
        nuclear_facilities.append({"id": row[0], "name": row[2], "lat": row[3], "lon": row[4],
            "institutionId": review["institutionId"], "linkedFacilityIds": [row[0], *review["aliases"]],
            "nuclearRole": review["role"], "nuclearRoleSourceVerified": True, "sources": links,
            "coordinateEvidenceClass": "retained_existing_campus_marker", "uncertaintyKm": None,
            "activeIntervals": [{"startYear": review["startYear"], "endYear": 2026,
                                 "boundaryUncertaintyYears": 1}],
            "activityRole": "institution_nuclear_program_history_years_not_daily_operation",
            "strictSpatialEligible": False,
            "strictExclusionReasons": ["campus_marker_not_operating_unit_boundary", "coordinate_error_not_quantified", "year_only_operational_boundaries"]})
    sources = [{"id": filename, "url": url, "sha256": digest(SOURCES / filename),
                "bytes": (SOURCES / filename).stat().st_size,
                "role": "primary_report" if filename.endswith(".pdf") else "transcription" if filename.endswith(".csv") else "source_provenance"}
               for filename, url in DOWNLOADS.items()]
    roles = Counter(t["role"] for t in tests)
    payload = {"schemaVersion": 1, "schemaId": "ufo_analysis_nuclear_context_v1", "ordinalEpoch": "unix_day",
        "estimatorVersion": "ufo-analysis-nuclear-v1.0.0", "tests": sorted(tests, key=lambda x: (x["ordinal"], x["id"])),
        "nuclearFacilities": nuclear_facilities, "sources": sources,
        "coverage": {"catalogRows": len(tests), "countries": dict(Counter(t["country"] for t in tests)),
            "roles": dict(roles), "locatedRows": sum(t["lat"] is not None for t in tests),
            "firstDate": min(t["date"] for t in tests), "lastDate": max(t["date"] for t in tests),
            "firstOrdinal": min(t["ordinal"] for t in tests), "lastOrdinal": max(t["ordinal"] for t in tests),
            "primaryTableVerifiedRows": audit["verifiedRows"], "primaryTableUnverifiedRows": audit["unverifiedRows"],
            "primarySummaryTotal": 2052, "primarySummarySovietTotal": 715, "transcribedSovietTotal": 714,
            "summaryDiscrepancy": "One Soviet record in the report's stated total is absent from this transcription; no invented replacement.",
            "excludedPost1998": "No North Korean or other post-1998 chronology is included.",
            "facilityInventory": "Four reviewed existing nuclear-program institutions in US/UK; partial coverage, excludes power-reactor inventory."},
        "policy": {"independentOfUfoCatalog": True, "testDayConvention": "GMT",
            "reportDayConvention": "source_civil_date_not_harmonized_to_GMT",
            "zeroZeroCoordinates": "excluded_as_missing", "unquantifiedPositionError": "not_imputed",
            "defaultTestRoles": ["weapons", "peaceful", "combat"],
            "safetyAndMixedSafety": "separate_excluded_default", "duplicateTestIdentity": "country_GMT_date_source_ID",
            "facilityClassification": "reviewed_source_identity_allowlist_not_name_keyword",
            "facilityComparator": "broader_military_research_catalog_nuclear_status_unreviewed",
            "causalityOrIncidenceClaim": False},
        "inputFacilityCatalog": {"path": str(existing_path), "sha256": digest(existing_path), "rows": len(existing)},
        "transcriptionCommit": COMMIT, "primaryReport": {"title": "Nuclear Explosions 1945-1998",
            "authors": ["Nils-Olov Bergkvist", "Ragnhild Ferm"], "issuer": "FOA/SIPRI", "issued": "2000-07",
            "reportId": "FOA-R--00-01572-180--SE", "officialRecordUrl": PRIMARY_URL,
            "primaryPdfSha256": digest(SOURCES / "sipri-report-original.pdf")}}
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    (DEST / "nuclear_context_v1.json").write_bytes(encoded)
    (DEST / "nuclear_context_v1.json.gz").write_bytes(gzip.compress(encoded, mtime=0))
    lifecycle = {"purpose": "Independent nuclear-test chronology and source-confirmed facility-role comparison inputs; local candidate only.",
        "canonicalArtifact": "data/analysis_comparisons/nuclear_context_v1.json", "retention": "Protect sources, review receipt and runtime input until candidate accepted; no deployment altered.",
        "rollback": "Existing deployed release remains rollback; no bundle/corpus copy.",
        "rebuild": "Run scripts/build_nuclear_comparison_context.py with bundled pypdf Python and --shared-root pointing to existing canonical workspace.",
        "sourceBytes": sum(x["bytes"] for x in sources), "runtimeBytes": len(encoded),
        "runtimeGzipBytes": (DEST / "nuclear_context_v1.json.gz").stat().st_size,
        "sourceVisualChecks": [{"file": name, "role": "bounded_primary_source_convention_and_first_table_visual_review", "sha256": digest(SOURCES / name)}
                               for name in ["primary-conventions-page19.png", "primary-table-page23.png"] if (SOURCES / name).exists()],
        "newFilesOver100MiB": [], "fullCorpusReadOrCopied": False, "runtimeSha256": hashlib.sha256(encoded).hexdigest()}
    (SOURCES / "PURPOSE.json").write_text(json.dumps(lifecycle, indent=2), encoding="utf-8")
    return {"coverage": payload["coverage"], "auditDifferencesN": len(audit["differences"]), "lifecycle": lifecycle}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--shared-root", type=Path, default=Path(r"C:\Users\jarod\Desktop\UFO Timeline map tool"))
    parser.add_argument("--fetch-missing-sources", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(args.shared_root, args.fetch_missing_sources), indent=2))
