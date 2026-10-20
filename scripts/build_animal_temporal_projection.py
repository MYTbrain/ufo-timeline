"""Derive a bounded country extension without changing the frozen animal rows.

Private seed records are read in place and joined only after their canonical
record hashes match the already-public detail provenance. The only new runtime
field is a normalized, explicitly stated country. No coordinates or narratives
are exported from the private seed.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re


SEED_SHA256 = "ba9558107ae1db1e08c53c7d2f36c2a941a50d3b8ed29608e32a876835e183f6"
ROW_SCHEMA = ["id", "startYear", "endYear", "datePrecisionCode", "speciesGroupCodes",
              "mapped", "statusCode", "startOrdinal", "endOrdinal"]
CONTINENTS = frozenset({"SA", "ME", "AS", "EU", "AF", "NA", "OC"})
# Release-specific explicit aliases. Unknown countries are held for review; no
# locality, state, coordinate, language or continent is geocoded into a country.
COUNTRY_ALIASES = {
    "US": "US", "USA": "US", "U.S.": "US", "U.S.A.": "US",
    "UNITED STATES": "US", "UNITED STATES OF AMERICA": "US",
    "CA": "CA", "CAN": "CA", "CANADA": "CA",
    "AU": "AU", "AUS": "AU", "AUSTRALIA": "AU",
    "CN": "CN", "CHN": "CN", "CHINA": "CN",
    "BR": "BR", "BRA": "BR", "BRAZIL": "BR",
    "JP": "JP", "JPN": "JP", "JAPAN": "JP",
    "IQ": "IQ", "IRQ": "IQ", "IRAQ": "IQ",
    "IL": "IL", "ISR": "IL", "ISRAEL": "IL",
    "GB": "GB", "GBR": "GB", "UK": "GB", "UNITED KINGDOM": "GB",
    "AR": "AR", "ARG": "AR", "ARGENTINA": "AR",
    "NL": "NL", "NLD": "NL", "NETHERLANDS": "NL",
    "FR": "FR", "FRA": "FR", "FRANCE": "FR",
    "ZW": "ZW", "ZWE": "ZW", "ZIMBABWE": "ZW",
    "BO": "BO", "BOL": "BO", "BOLIVIA": "BO",
    "CL": "CL", "CHL": "CL", "CHI": "CL", "CHILE": "CL",
    "IT": "IT", "ITA": "IT", "ITALY": "IT",
    "DE": "DE", "DEU": "DE", "GER": "DE", "GERMANY": "DE",
}
AMBIGUOUS_STATE_TOKENS = frozenset({"CA", "AR", "IL", "DE"})


def require(condition, message):
    if not condition:
        raise ValueError(message)


def compact(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def token(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).upper()


def resolve_country(source_country, public_location):
    """Return (country, status) using only explicit country fields/suffixes."""
    source_token = token(source_country)
    source = COUNTRY_ALIASES.get(source_token)
    parts = [token(value) for value in str(public_location or "").split(",")]
    tail = parts[-1] if parts else ""
    public_token = parts[-2] if tail in CONTINENTS and len(parts) > 1 else tail
    public = COUNTRY_ALIASES.get(public_token)
    # A bare terminal CA/AR/IL/DE can be a state abbreviation. It is accepted
    # only when an explicit country field independently agrees, or when a
    # terminal continent token establishes the structured country position.
    if public_token in AMBIGUOUS_STATE_TOKENS and tail not in CONTINENTS and source != public:
        public = None
    if source and public and source != public:
        return "unknown", "country_conflict"
    if source:
        return source, "source_and_public_agree" if public else "source_country"
    if public:
        return public, "continent_suffix_recovered" if source_token in CONTINENTS else "public_country_suffix"
    if source_token in CONTINENTS:
        return "unknown", "unresolved_continent_code"
    return "unknown", "unrecognized_source_country" if source_token else "country_missing"


def build_animal_temporal_projection(frozen_root, seed_path, output_root, *,
                                     expected_seed_sha256=SEED_SHA256,
                                     expected_record_count=1184,
                                     expected_seed_matches=1177,
                                     write_outputs=True):
    """Write only the small derived JSON, gzip and public provenance receipt.

    Returned inputPins include local paths for release tooling; those paths do
    not appear in any written/public artifact. The returned projection metadata
    uses the existing Analysis v1 manifest's file/gzipFile field conventions.
    write_outputs=False validates and calculates identical metadata in memory
    without creating a directory or changing existing generated files.
    """
    frozen_root, seed_path, output_root = map(lambda value: Path(value).resolve(),
                                            (frozen_root, seed_path, output_root))
    require(not output_root.is_relative_to(frozen_root), "Frozen release inputs must remain immutable")
    require(not output_root.is_relative_to(seed_path.parent), "Private source directory is not an output directory")
    pins = []

    def read_pinned(path, role, expected_sha=None, expected_bytes=None):
        data = path.read_bytes()
        checksum = digest(data)
        require(expected_sha is None or checksum == expected_sha, role + " hash mismatch")
        require(expected_bytes is None or len(data) == expected_bytes, role + " byte count mismatch")
        pins.append({"role": role, "path": str(path), "sha256": checksum, "bytes": len(data)})
        return data

    analysis_manifest = json.loads(read_pinned(frozen_root / "public/data/analysis_v1/manifest.json", "analysis_manifest"))
    declaration = analysis_manifest["artifacts"]["animalReports"]
    require(declaration["rowSchema"] == ROW_SCHEMA, "Unexpected frozen animal projection schema")
    projection_bytes = gzip.decompress(read_pinned(
        frozen_root / "projections/analysis_v1/animal_reports.json.gz", "animal_projection_gzip",
        declaration["gzipSha256"], declaration["gzipBytes"]))
    require(digest(projection_bytes) == declaration["sha256"] and len(projection_bytes) == declaration["bytes"],
            "Decoded animal projection pin mismatch")
    rows = json.loads(projection_bytes)
    require(isinstance(rows, list) and len(rows) == expected_record_count == declaration["rowCount"],
            "Animal projection row count drift")
    require(all(isinstance(row, list) and len(row) == len(ROW_SCHEMA) for row in rows),
            "Animal projection fields changed")
    ids = [row[0] for row in rows]
    require(len(set(ids)) == len(ids), "Duplicate animal projection IDs")

    detail_root = frozen_root / "layers/animal_mutilations"
    detail_manifest = json.loads(read_pinned(detail_root / "manifest.json", "animal_detail_manifest"))
    details = {}
    for index, member in enumerate(detail_manifest["details"]["files"]):
        member_path = (detail_root / member["path"]).resolve()
        require(member_path.is_relative_to(detail_root), "Unsafe detail member path")
        chunk = json.loads(gzip.decompress(read_pinned(member_path, "animal_detail_chunk_" + str(index),
                                                      member["sha256"], member["bytes"])))
        require(isinstance(chunk, dict) and len(chunk) == member["recordCount"], "Detail chunk count drift")
        require(not set(details).intersection(chunk), "Duplicate animal detail IDs")
        require(all(isinstance(value, dict) and key == value.get("id") for key, value in chunk.items()),
                "Animal detail ID disagreement")
        details.update(chunk)
    require(set(ids) == set(details), "Animal projection/detail IDs disagree")

    seed_bytes = read_pinned(seed_path, "private_seed_country_source", expected_seed_sha256)
    seed = {}
    for line in seed_bytes.decode("utf-8-sig").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        key = record["canonical_incident_id"]
        require(key and key not in seed, "Missing or duplicate private seed incident ID")
        seed[key] = record
    require(len(seed) == expected_seed_matches, "Private seed record count drift")
    derived, status_counts, country_counts = [], Counter(), Counter()
    joined = 0
    joined_source_ids = set()
    for row in rows:
        detail = details[row[0]]
        source = seed.get(detail.get("sourceIncidentId"))
        if source is not None:
            require(detail["sourceIncidentId"] not in joined_source_ids, "Duplicate public detail/private seed join")
            require(digest(compact(source)) == detail.get("sourceIncidentSha256"),
                    "Public detail/private seed canonical record hash mismatch")
            joined_source_ids.add(detail["sourceIncidentId"])
            joined += 1
        source_country = (source.get("location") or {}).get("country_code") if source is not None else None
        country, status = resolve_country(source_country, detail.get("location"))
        derived.append(row + [country])
        status_counts[status] += 1
        country_counts[country] += 1
    require(joined == expected_seed_matches, "Public detail/private seed join count drift")
    require(joined_source_ids == set(seed), "Private seed join coverage drift")
    require(all(new[:9] == old for new, old in zip(derived, rows)), "Frozen animal fields changed")
    payload = compact(derived)
    compressed = gzip.compress(payload, compresslevel=9, mtime=0)
    logical = "data/analysis_v1/animal_reports_temporal.json"
    projection = {"path": logical, "file": logical, "gzipFile": logical + ".gz",
                  "sha256": digest(payload), "bytes": len(payload),
                  "gzipSha256": digest(compressed), "gzipBytes": len(compressed),
                  "decodedBytes": len(payload), "recordCount": len(derived), "rowCount": len(derived),
                  "rowSchema": ROW_SCHEMA + ["country"]}
    counts = {"recordCount": len(derived), "seedMatched": joined, "seedUnmatched": len(derived) - joined,
              "knownCountry": len(derived) - country_counts["unknown"], "unknownCountry": country_counts["unknown"],
              "countries": dict(sorted(country_counts.items())), "countryResolution": dict(sorted(status_counts.items()))}
    public_provenance = {
        "schemaId": "ufo-animal-temporal-country-projection-v1", "schemaVersion": 1,
        "counts": counts, "rowSchema": projection["rowSchema"],
        "inputs": [{key: pin[key] for key in ("role", "sha256", "bytes")} for pin in pins],
        "outputs": {"json": {"path": logical, "sha256": projection["sha256"], "bytes": len(payload)},
                    "gzip": {"path": logical + ".gz", "sha256": projection["gzipSha256"], "bytes": len(compressed)}},
        "policy": {"firstNineFieldsUnchanged": True, "sourceRecordHashJoinsRequired": True,
                   "sourceCountryField": "location.country_code", "countryAliases": "explicit-release-allowlist-v1",
                   "publicLocationSuffix": "exact last country token, or exact penultimate country token before a continent code",
                   "ambiguousStateTokenRequiresCorroboration": True,
                   "conflictingCountries": "unknown", "missingCountries": "unknown",
                   "geocodingUsed": False, "privateCoordinatesExported": False,
                   "privateNarrativesExported": False, "sourceCountsChanged": False},
    }
    provenance_bytes = compact(public_provenance)
    provenance_path = "data/analysis_v1/animal_temporal_provenance.json"
    require(len(payload) + len(compressed) + len(provenance_bytes) < 1024**2, "Derived output exceeds its 1 MiB budget")
    if write_outputs:
        destination = output_root / "data/analysis_v1"
        destination.mkdir(parents=True, exist_ok=True)
        for name, data in (("animal_reports_temporal.json", payload), ("animal_reports_temporal.json.gz", compressed),
                           ("animal_temporal_provenance.json", provenance_bytes)):
            (destination / name).write_bytes(data)
    return {"projection": projection, "provenance": {"path": provenance_path, "sha256": digest(provenance_bytes),
                                                      "bytes": len(provenance_bytes)},
            "counts": counts, "inputPins": pins, "outputRoot": str(output_root)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-root", required=True, type=Path)
    parser.add_argument("--seed-path", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    result = build_animal_temporal_projection(args.frozen_root, args.seed_path, args.output_root)
    print(json.dumps({"counts": result["counts"], "projection": result["projection"],
                      "provenance": result["provenance"]}, sort_keys=True))


if __name__ == "__main__":
    main()
