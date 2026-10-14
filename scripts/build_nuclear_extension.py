"""Build a bounded additive nuclear context from CTBTO, USGS and Sandia sources.

Existing source captures are reused. This script never rewrites the base nuclear
chronology or reads/copies the UFO corpus. Geophysical estimates and institutional
markers do not become verified device sites, yields or daily operation records.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import gzip
import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "analysis_comparisons"
SOURCE_DIR = DEST / "nuclear_extension_sources"
QA_DIR = ROOT / "docs" / "qa" / "nuclear-extension-20261013"
DATES = ["2006-10-09", "2009-05-25", "2013-02-12", "2016-01-06", "2016-09-09", "2017-09-03"]
CTBTO_URL = "https://www.ctbto.org/our-work/detecting-nuclear-tests"
SANDIA_URL = "https://www.sandia.gov/about/history/"
USGS_FORMAT_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php"
FACILITY_ID = "facility:1a022b4a6b36149071a0"
SOURCE_BUDGET = 2 * 1024 * 1024


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def usgs_query(date: str) -> str:
    end = (dt.date.fromisoformat(date) + dt.timedelta(days=1)).isoformat()
    args = {"format": "geojson", "starttime": date, "endtime": end, "minlatitude": 40,
            "maxlatitude": 42, "minlongitude": 128, "maxlongitude": 130,
            "minmagnitude": 4, "limit": 10, "orderby": "magnitude"}
    return "https://earthquake.usgs.gov/fdsnws/event/1/query?" + urllib.parse.urlencode(args)


def sources() -> dict[str, str]:
    return {"ctbto_detecting_nuclear_tests.html": CTBTO_URL, "sandia_history.html": SANDIA_URL,
            "usgs_geojson_format.html": USGS_FORMAT_URL,
            **{"usgs_" + date.replace("-", "") + ".json": usgs_query(date) for date in DATES}}


def capture(name_url: tuple[str, str]) -> None:
    name, url = name_url
    path = SOURCE_DIR / name
    if path.exists():
        return
    request = urllib.request.Request(url, headers={"User-Agent": "UFO-Timeline-bounded-source-review/1.0"})
    with urllib.request.urlopen(request, timeout=40) as response:
        data = response.read(SOURCE_BUDGET + 1)
        if len(data) > SOURCE_BUDGET:
            raise ValueError("Source response exceeds the complete extension budget: " + name)
    path.write_bytes(data)
    print("Captured " + name + ": " + str(len(data)) + " bytes", flush=True)


def source_record(name: str, url: str, role: str) -> dict:
    data = (SOURCE_DIR / name).read_bytes()
    return {"id": name, "url": url, "capturedFile": "nuclear_extension_sources/" + name,
            "sha256": digest(data), "bytes": len(data), "role": role}


def build(shared_root: Path, fetch: bool) -> dict:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)
    base_path = DEST / "nuclear_context_v1.json"
    base_gzip = DEST / "nuclear_context_v1.json.gz"
    base_pins = {path.name: digest(path.read_bytes()) for path in [base_path, base_gzip]}
    if fetch:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            list(executor.map(capture, sources().items()))
    if sum((SOURCE_DIR / name).stat().st_size for name in sources()) > SOURCE_BUDGET:
        raise ValueError("Captured sources exceed the authorized 2 MiB extension budget")
    ctbto = source_record("ctbto_detecting_nuclear_tests.html", CTBTO_URL, "primary_nuclear_test_identity_and_date")
    sandia = source_record("sandia_history.html", SANDIA_URL, "primary_institution_role_and_history")
    source_pins = [ctbto, sandia, source_record("usgs_geojson_format.html", USGS_FORMAT_URL, "primary_API_field_definition")]
    tests = []
    checks = []
    for date in DATES:
        name = "usgs_" + date.replace("-", "") + ".json"
        source = source_record(name, usgs_query(date), "primary_seismic_event_location_and_origin_time")
        source_pins.append(source)
        data = json.loads((SOURCE_DIR / name).read_text(encoding="utf-8"))
        features = data.get("features", [])
        candidates = [feature for feature in features if feature.get("properties", {}).get("type") == "nuclear explosion"]
        if len(candidates) != 1:
            raise ValueError(f"Expected exactly one USGS nuclear-explosion event for CTBTO date {date}; found {len(candidates)}")
        feature = candidates[0]
        prop = feature["properties"]
        origin = dt.datetime.fromtimestamp(prop["time"] / 1000, tz=dt.timezone.utc)
        if origin.date().isoformat() != date:
            raise ValueError("USGS origin day differs from the CTBTO-listed date")
        lon, lat, depth = feature["geometry"]["coordinates"]
        if not (40 <= lat <= 42 and 128 <= lon <= 130):
            raise ValueError("USGS candidate is outside the bounded primary-source query")
        tests.append({"id": "ctbto:dprk:" + date, "name": "DPRK declared nuclear test " + date, "country": "DPRK",
            "region": prop.get("place"), "date": date,
            "ordinal": (origin.date() - dt.date(1970, 1, 1)).days, "datePrecision": "exact_day",
            "dateRole": "explosion_GMT_day", "originTimeUtc": origin.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "originTimeProvenance": "USGS preferred seismic event origin; not a separately verified device detonation clock",
            "lat": lat, "lon": lon, "coordinateEvidenceClass": "source_seismic_epicenter_estimate", "uncertaintyKm": None,
            "usgsEventId": feature["id"], "usgsEventUrl": prop.get("url"), "usgsEventType": prop["type"],
            "usgsMagnitude": prop.get("mag"), "usgsMagnitudeType": prop.get("magType"), "usgsDepthKm": depth,
            "yieldLowerKt": None, "yieldUpperKt": None, "yieldZeroMeaning": "yield_not_transcribed_or_inferred_from_seismic_magnitude",
            "role": "weapons", "purposeRaw": "CTBTO-listed declared DPRK nuclear weapon test", "deployment": None,
            "primaryDateVerified": True, "primaryIdentityVerified": True,
            "strictSpatialEligible": False, "strictExclusionReasons": ["seismic_epicenter_not_verified_device_position", "position_error_not_quantified"],
            "unit": "declared_nuclear_test_event_not_device_inventory", "sources": [ctbto, source]})
        checks.append({"date": date, "queriedEvents": len(features), "nuclearCandidates": len(candidates), "selectedId": feature["id"],
                       "originTimeUtc": tests[-1]["originTimeUtc"], "lat": lat, "lon": lon})
    facility_path = shared_root / "webapp" / "static_public" / "data" / "analysis_v2" / "facility_analysis_v1.json"
    facility_bytes = facility_path.read_bytes()
    facility_catalog = json.loads(facility_bytes)
    marker = next(row for row in facility_catalog if row[0] == FACILITY_ID)
    if marker[3:5] != [35.05, -106.536]:
        raise ValueError("Retained Sandia marker no longer matches the reviewed identity and coordinates")
    nuclear_facility = {"id": marker[0], "name": marker[2], "lat": marker[3], "lon": marker[4], "institutionId": "SANDIA_ALBUQUERQUE",
        "linkedFacilityIds": [marker[0]], "nuclearRole": "nuclear_weapon_nonnuclear_component_engineering", "nuclearRoleSourceVerified": True,
        "sources": [sandia], "coordinateEvidenceClass": "retained_existing_campus_marker", "uncertaintyKm": None,
        "activeIntervals": [{"startYear": 1945, "endYear": 2026, "boundaryUncertaintyYears": 1}],
        "activityRole": "institution_nuclear_program_history_years_not_daily_operation",
        "activityEndMeaning": "source_capture_horizon_not_shutdown_year", "strictSpatialEligible": False,
        "strictExclusionReasons": ["campus_marker_not_operating_unit_boundary", "coordinate_error_not_quantified", "year_only_operational_boundaries"]}
    payload = {"schemaId": "ufo-nuclear-context-extension-v1", "schemaVersion": 1, "releaseId": "nuclear-extension-20261013-v1",
        "ordinalEpoch": "unix_day", "tests": tests, "nuclearFacilities": [nuclear_facility], "sources": source_pins,
        "baseArtifact": {"file": "nuclear_context_v1.json.gz", "sha256": base_pins[base_path.name], "gzipSha256": base_pins[base_gzip.name]},
        "inputFacilityCatalog": {"path": str(facility_path), "sha256": digest(facility_bytes), "rows": len(facility_catalog)},
        "coverage": {"catalogRows": 6, "locatedRows": 6, "addedNuclearInstitutions": 1, "countries": {"DPRK": 6}, "roles": {"weapons": 6},
            "firstDate": DATES[0], "lastDate": DATES[-1], "firstOrdinal": tests[0]["ordinal"], "lastOrdinal": tests[-1]["ordinal"],
            "post1998Coverage": "six_declared_DPRK_tests_only_not_comprehensive_global_chronology",
            "post2017Coverage": "not_included", "facilityInventory": "One additional reviewed Sandia institution marker; excludes power reactors and unreviewed nuclear-role markers."},
        "policy": {"additiveOnly": True, "baseChronologyUnchanged": True, "independentOfUfoCatalog": True, "testDayConvention": "UTC",
            "reportDayConvention": "source_civil_date_not_harmonized_to_UTC", "seismicLocationIsDeviceSite": False,
            "yieldInferredFromMagnitude": False, "unquantifiedPositionError": "not_imputed", "facilityDailyOperationInferred": False,
            "missingTestsMeanNoTest": False, "causalityOrIncidenceClaim": False}}
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    compressed = gzip.compress(encoded, mtime=0)
    (DEST / "nuclear_extension_v1.json").write_bytes(encoded)
    (DEST / "nuclear_extension_v1.json.gz").write_bytes(compressed)
    manifest_path = DEST / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["nuclearExtension"] = {"schemaId": payload["schemaId"], "releaseId": payload["releaseId"],
        "file": "./nuclear_extension_v1.json.gz", "url": "./data/analysis_comparisons/nuclear_extension_v1.json.gz",
        "sha256": digest(encoded), "bytes": len(encoded), "gzipSha256": digest(compressed), "gzipBytes": len(compressed),
        "additiveOnly": True, "testRows": 6, "nuclearInstitutions": 1, "post1998Coverage": payload["coverage"]["post1998Coverage"]}
    manifest["policy"]["nuclearExtensionPost1998Coverage"] = payload["coverage"]["post1998Coverage"]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    after_pins = {path.name: digest(path.read_bytes()) for path in [base_path, base_gzip]}
    if after_pins != base_pins:
        raise ValueError("Protected base chronology changed during additive build")
    source_size = sum(source["bytes"] for source in source_pins)
    lifecycle = {"canonicalArtifact": "data/analysis_comparisons/nuclear_extension_v1.json.gz", "decodedCompanion": "data/analysis_comparisons/nuclear_extension_v1.json",
        "purpose": "Source-pinned additive DPRK test chronology and Sandia institution review; local candidate inputs only.",
        "retention": "Retain unique source captures, extension inputs and QA; base chronology and deployed/current rollback remain unchanged.",
        "rebuild": "py -3 scripts/build_nuclear_extension.py --shared-root <protected canonical root>; --fetch-missing-sources only for absent captures.",
        "rollback": "Existing base nuclear_context_v1 artifacts and deployed rollback remain protected; no bundle or dataset copies created.",
        "sourceBytes": source_size, "runtimeBytes": len(encoded), "runtimeGzipBytes": len(compressed),
        "newFilesOver100MiB": [], "corpusReadOrCopied": False, "supersededGeneratedArtifacts": []}
    (SOURCE_DIR / "PURPOSE.json").write_text(json.dumps(lifecycle, indent=2) + "\n", encoding="utf-8")
    receipt = {"schemaId": "ufo-nuclear-extension-source-audit-v1", "status": "passed", "tests": checks,
        "facility": {"id": marker[0], "name": marker[2], "lat": marker[3], "lon": marker[4], "primaryRoleAndHistoryUrl": SANDIA_URL,
            "markerCatalogSha256": digest(facility_bytes), "yearBoundariesUncertain": True, "strictSpatialEligible": False},
        "artifact": manifest["artifacts"]["nuclearExtension"], "baseHashesBefore": base_pins, "baseHashesAfter": after_pins,
        "sourceHashes": source_pins, "storage": lifecycle}
    (QA_DIR / "source-runtime.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return {"status": "passed", "coverage": payload["coverage"], "artifact": manifest["artifacts"]["nuclearExtension"],
            "storage": lifecycle}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--shared-root", type=Path, default=Path(r"C:\Users\jarod\Desktop\UFO Timeline map tool"))
    parser.add_argument("--fetch-missing-sources", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(args.shared_root, args.fetch_missing_sources), indent=2))
