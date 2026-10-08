"""Build small shared comparison inputs from retained, pinned context projections.

No event coordinates, occurrence dates, source independence, or strict eligibility
are inferred. Canonical source bytes remain untouched; details are read, not copied.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

PYTHON_UNIX_EPOCH = 719163
SCHEMA = "ufo-analysis-comparison-context-v1"


def read(path: Path):
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == ".gz" else data)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode(rows, declaration, codes):
    result = []
    schema = declaration["rowSchema"]
    for values in rows:
        row = dict(zip(schema, values)) if isinstance(values, list) else dict(values)
        for key, value in list(row.items()):
            if key.endswith("Code") and value is not None:
                lookup = codes.get(key[:-4], [])
                if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < len(lookup):
                    row[key] = lookup[value]
        reasons = codes.get("exclusionReason", [])
        row["exclusionReasonCodes"] = [reasons[v] if isinstance(v, int) and 0 <= v < len(reasons) else str(v)
                                       for v in row.get("exclusionReasonCodes", [])]
        result.append(row)
    return result


def value_at(book, key, code, default="unknown"):
    values = book.get(key, [])
    return values[code] if isinstance(code, int) and 0 <= code < len(values) else default


def project(row, domain, metadata, detail):
    uncertainty = row.get("coordinateUncertaintyKm")
    reasons = list(row.get("exclusionReasonCodes") or [])
    item = {
        "id": row["id"], "domain": domain,
        "startOrdinal": row["startOrdinal"] - PYTHON_UNIX_EPOCH if row.get("startOrdinal") is not None else None,
        "endOrdinal": row["endOrdinal"] - PYTHON_UNIX_EPOCH if row.get("endOrdinal") is not None else None,
        "datePrecision": row.get("datePrecisionCode", "unknown"),
        "dateRole": row.get("dateRoleCode", "unknown"),
        "lat": row.get("lat"), "lon": row.get("lon"), "uncertaintyKm": uncertainty,
        "coordinateEvidenceClass": row.get("coordinateEvidenceClassCode", "unmapped"),
        "country": metadata.get("country", detail.get("country", "unknown")),
        "category": row.get("featureGroupCode", "unknown"),
        "sourceFamilyIds": row.get("sourceFamilyIds", []),
        "lineageHash": row.get("lineageHash"),
        "independenceStatus": row.get("independenceStatusCode", "unreviewed"),
        "dedupStatus": row.get("dedupStatusCode", "canonical_record_unreviewed"),
        "reviewState": row.get("reviewStateCode", "unreviewed"),
        "strictEligible": row.get("kilometerEligible") is True,
        "analysisLane": row.get("analysisLaneCode", "excluded"),
        "exclusionReasons": reasons,
        "clusterId": row.get("locationDateClusterId"),
    }
    # A historical record's role stays attached to that date, even if it is a
    # publication/discovery/catalog date. UTC and private site geometry are not added.
    if domain == "crop":
        item["morphology"] = metadata.get("morphology", [])
        item["classification"] = metadata.get("classification", "unreviewed")
        item["originStatus"] = metadata.get("originStatus", "unreviewed_or_unknown")
    else:
        item["title"] = metadata.get("title", "")
        item["species"] = metadata.get("species", [])
        for field in ("sourceIncidentId", "sourceIncidentSha256", "originInputIds", "originUfoEventIds", "originPublisherCodes"):
            item[field] = row.get(field, [] if field.endswith("Ids") or field.endswith("Codes") else None)
        item["sourceRefs"] = [
            {key: ref[key] for key in ("sourceId", "recordUrl", "hashRole") if ref.get(key)}
            for ref in detail.get("sourceRefs", []) if isinstance(ref, dict)
        ]
    return item


def build(source_root: Path, output: Path):
    base = source_root / "webapp/static_public/data"
    repair = source_root / "data/research/analysis-repairs-20261007/context"
    v2_manifest_path = source_root / "data/releases/quality-20261007/analysis_delta/analysis_v2/manifest.json"
    v2 = read(v2_manifest_path)
    v1_manifest_path = repair / "analysis_v1/manifest.json"
    v1 = read(v1_manifest_path)
    paths = [v2_manifest_path, v1_manifest_path]
    crop_path = repair / "analysis_v1/crop_circles.json.gz"
    crop_meta = {}
    paths.append(crop_path)
    for row in read(crop_path):
        crop_meta[row[0]] = {
            "country": value_at(v1.get("dictionaries", {}), "country", row[4]),
            "morphology": [value_at(v1.get("codes", {}), "morphologyFamily", v) for v in row[6]],
            "classification": value_at(v1.get("codes", {}), "classification", row[14]),
            "originStatus": value_at(v1.get("codes", {}), "originStatus", row[15]),
        }
    animal_manifest_path = repair / "animal_mutilations/manifest.json"
    animal_manifest = read(animal_manifest_path)
    animal_catalog_path = repair / "animal_mutilations/catalog.json.gz"
    paths.extend([animal_manifest_path, animal_catalog_path])
    species_codes = animal_manifest.get("codes", {}).get("speciesGroup", {})
    species_names = {value: key for key, value in species_codes.items()}
    animal_meta = {row[0]: {"title": row[1], "species": [species_names.get(v, "unknown") for v in row[7]]}
                   for row in read(animal_catalog_path)}
    details = {}
    for entry in animal_manifest["details"]["files"]:
        local = repair / "animal_mutilations" / entry["path"]
        if not local.exists():
            local = base / "animal_mutilations" / entry["path"]
        paths.append(local)
        details.update(read(local))
    payload = {"schemaId": SCHEMA, "ordinalEpoch": "unix_day", "crops": [], "animals": []}
    for domain, artifact, filename, metadata in (
        ("crop", "cropContextReadiness", "crop_context_readiness.json.gz", crop_meta),
        ("animal", "animalContextReadiness", "animal_context_readiness.json.gz", animal_meta),
    ):
        path = base / "analysis_v2" / filename
        paths.append(path)
        declaration = v2["artifacts"][artifact]
        if sha(path) != declaration["gzipSha256"]:
            raise ValueError(f"Pinned source hash mismatch: {path}")
        values = decode(read(path), declaration, v2["codes"][artifact])
        projected = [project(row, domain, metadata.get(row["id"], {}), details.get(row["id"], {})) for row in values]
        payload["crops" if domain == "crop" else "animals"] = projected
    payload["policy"] = {
        "dateRolesPreserved": True, "sourceIndependenceInferred": False,
        "strictEligibilityChanged": False, "privateCoordinatesAdded": False,
        "utcTimesInferred": False, "traceInputsIncluded": False,
        "animalCountryUnknownPreserved": True,
    }
    output.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
    data_path = output / "context_rows.json"
    gzip_path = output / "context_rows.json.gz"
    data_path.write_bytes(encoded)
    gzip_path.write_bytes(gzip.compress(encoded, compresslevel=9, mtime=0))
    manifest = {
        "schemaId": SCHEMA, "ordinalEpoch": "unix_day",
        "artifacts": {"contextRows": {"file": "context_rows.json", "gzipFile": "context_rows.json.gz",
            "bytes": len(encoded), "gzipBytes": gzip_path.stat().st_size,
            "sha256": sha(data_path), "gzipSha256": sha(gzip_path)}},
        "counts": {"crops": len(payload["crops"]), "animals": len(payload["animals"]),
                   "strictCrops": sum(r["strictEligible"] for r in payload["crops"]),
                   "strictAnimals": sum(r["strictEligible"] for r in payload["animals"])},
        "dateRoleCounts": {name: dict(Counter(r["dateRole"] for r in payload[name])) for name in ("crops", "animals")},
        "sources": [{"path": str(path.relative_to(source_root)).replace("\\", "/"), "bytes": path.stat().st_size, "sha256": sha(path)}
                    for path in paths],
        "policy": payload["policy"], "rebuild": "py -3 scripts/build_analysis_comparison_context.py --source-root <shared canonical root>",
    }
    (output / "context_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    purpose = (
        "Purpose: compact inputs for the local lunar, nuclear and crop-animal comparison preview.\n"
        "Provenance: context_manifest.json pins retained quality-v2 readiness and current repaired context metadata/detail bytes.\n"
        "Rebuild: run scripts/build_analysis_comparison_context.py with --source-root pointing at the shared canonical project.\n"
        "Retention: keep this small local candidate while under review; production and the retained rollback are unchanged.\n"
        "Only these context_rows JSON/gzip and context_manifest files are generated by this builder; no canonical corpus or detail copy is made.\n"
        f"Net new generated size: {len(encoded) + gzip_path.stat().st_size + (output / 'context_manifest.json').stat().st_size:,} bytes. No files over 100 MiB.\n"
    )
    (output / "CONTEXT_PURPOSE.txt").write_text(purpose, encoding="utf-8")
    print(json.dumps({"output": str(output), "counts": manifest["counts"], "bytes": len(encoded), "gzipBytes": gzip_path.stat().st_size,
                      "sha256": manifest["artifacts"]["contextRows"]["sha256"]}, sort_keys=True))
    return payload, manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "data/analysis_comparisons")
    args = parser.parse_args()
    build(args.source_root.resolve(), args.output.resolve())
