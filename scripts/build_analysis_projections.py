"""Build compact, deterministic, descriptive-only analysis projections.

The projections deliberately omit narrative text, source references, coordinates,
and cross-domain identifiers.  They support aggregate catalog analysis without
encoding UFO relationships, traces, proximity, travel, cause, or authenticity.
"""

from __future__ import annotations

import argparse
import calendar
from datetime import date
from io import BytesIO
import gzip
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_ROOT = REPO_ROOT / "webapp" / "static_public" / "data"
DEFAULT_OUTPUT_ROOT = DEFAULT_SOURCE_ROOT / "analysis_v1"
DEFAULT_CATALOG_SOURCE = (
    REPO_ROOT
    / "data"
    / "canonical_full_maximal_v3_rehydrated_jurisdiction_repair"
    / "deduped_events.jsonl"
)
DEFAULT_CANONICAL_WEB_MANIFEST = REPO_ROOT / "data" / "canonical_web" / "canonical_web_manifest.json"
DEFAULT_RELEASE_SEAL = REPO_ROOT / "reproduction" / "release.json"
DEFAULT_RELEASE_ID = "analysis-projections-v1-20260803"
DEFAULT_BROWSER_BASE_PATH = "data/analysis_v1"
SCHEMA_ID = "ufo-timeline-analysis-projections-v1.1.0"

DATE_PRECISION_CODES = {
    "exact_day": 0,
    "month": 1,
    "year": 2,
    "range": 3,
    "approximate": 4,
    "unknown": 5,
}
DATE_PRECISION_ALIASES = {"day": "exact_day"}
COORDINATE_CLASS_CODES = {
    "exact": 0,
    "candidate": 1,
    "locality": 2,
    "unmapped": 3,
}
COMPLEXITY_TIER_CODES = {
    "simple": 0,
    "moderate": 1,
    "complex": 2,
    "very_complex": 3,
    "not_applicable": 4,
}
ANIMAL_STATUS_CODES = {"reported_unreviewed": 0}
YEAR_RE = re.compile(r"^(\d{4})(?:-|$)")
ISO_DATE_RE = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?")
SAFE_RELEASE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

CROP_ROW_SCHEMA = [
    "id",
    "startYear",
    "endYear",
    "datePrecisionCode",
    "countryCode",
    "cropTypeCode",
    "morphologyCodes",
    "complexityTierCodes",
    "coordinateClassCode",
    "mapped",
    "hasNarrative",
    "hasSize",
    "startOrdinal",
    "endOrdinal",
]
ANIMAL_ROW_SCHEMA = [
    "id",
    "startYear",
    "endYear",
    "datePrecisionCode",
    "speciesGroupCodes",
    "mapped",
    "statusCode",
    "startOrdinal",
    "endOrdinal",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--catalog-source", type=Path, default=DEFAULT_CATALOG_SOURCE)
    parser.add_argument(
        "--canonical-web-manifest",
        type=Path,
        default=DEFAULT_CANONICAL_WEB_MANIFEST,
    )
    parser.add_argument("--release-seal", type=Path, default=DEFAULT_RELEASE_SEAL)
    parser.add_argument("--release-id", default=DEFAULT_RELEASE_ID)
    parser.add_argument("--browser-base-path", default=DEFAULT_BROWSER_BASE_PATH)
    return parser.parse_args()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_json_document(value: Any) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def deterministic_gzip(raw: bytes) -> bytes:
    buffer = BytesIO()
    with gzip.GzipFile(
        filename="",
        mode="wb",
        compresslevel=9,
        fileobj=buffer,
        mtime=0,
    ) as stream:
        stream.write(raw)
    return buffer.getvalue()


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_jsonl(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    row_count = 0
    final_byte: int | None = None
    with path.open("rb") as stream:
        while block := stream.read(8 * 1024 * 1024):
            digest.update(block)
            row_count += block.count(b"\n")
            final_byte = block[-1]
    if final_byte is not None and final_byte != 0x0A:
        row_count += 1
    return digest.hexdigest(), row_count


def repository_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"Published source path is outside the repository: {path}") from exc


def safe_relative_path(root: Path, value: Any) -> Path:
    relative = Path(str(value or ""))
    if not str(relative) or relative.is_absolute():
        raise ValueError(f"Expected a relative artifact path, got {value!r}")
    target = (root / relative).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"Artifact path escapes its source root: {value!r}") from exc
    return target


def load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value, raw


def read_declared_gzip(root: Path, declaration: dict[str, Any]) -> Any:
    path = safe_relative_path(root, declaration.get("path"))
    compressed = path.read_bytes()
    expected_bytes = declaration.get("bytes")
    if expected_bytes is not None and len(compressed) != expected_bytes:
        raise ValueError(f"Declared byte count does not match {path}")
    if sha256_bytes(compressed) != declaration.get("sha256"):
        raise ValueError(f"Declared SHA-256 does not match {path}")
    decoded = gzip.decompress(compressed)
    expected_decoded = declaration.get("decodedBytes", declaration.get("decoded_bytes"))
    if expected_decoded is not None and len(decoded) != expected_decoded:
        raise ValueError(f"Declared decoded byte count does not match {path}")
    return json.loads(decoded)


def normalized_date_precision(value: Any) -> str:
    label = DATE_PRECISION_ALIASES.get(str(value or "unknown"), str(value or "unknown"))
    if label not in DATE_PRECISION_CODES:
        raise ValueError(f"Unsupported date precision: {value!r}")
    return label


def date_year(value: Any) -> int | None:
    if not value:
        return None
    match = YEAR_RE.match(str(value))
    if not match:
        raise ValueError(f"Unsupported date value: {value!r}")
    return int(match.group(1))


def date_ordinal_bounds(value: Any) -> tuple[int | None, int | None]:
    """Return the inclusive ordinal interval represented by an ISO-like date."""
    if not value:
        return None, None
    match = ISO_DATE_RE.match(str(value))
    if not match:
        raise ValueError(f"Unsupported date value: {value!r}")
    year = int(match.group(1))
    month = int(match.group(2)) if match.group(2) else None
    day = int(match.group(3)) if match.group(3) else None
    if day is not None and month is None:
        raise ValueError(f"Unsupported date value: {value!r}")
    try:
        start = date(year, month or 1, day or 1)
        if day is not None:
            end = start
        elif month is not None:
            end = date(year, month, calendar.monthrange(year, month)[1])
        else:
            end = date(year, 12, 31)
    except ValueError as exc:
        raise ValueError(f"Unsupported date value: {value!r}") from exc
    return start.toordinal(), end.toordinal()


def date_interval_ordinals(start_value: Any, end_value: Any = None) -> tuple[int | None, int | None]:
    start_lower, start_upper = date_ordinal_bounds(start_value)
    end_lower, end_upper = date_ordinal_bounds(end_value)
    if start_lower is None and end_lower is None:
        return None, None
    lower = start_lower if start_lower is not None else end_lower
    upper = end_upper if end_upper is not None else start_upper
    if lower is None or upper is None:
        return None, None
    return min(lower, upper), max(lower, upper)


def text_or_none(value: Any) -> str | None:
    text = " ".join(str(value or "").split()).strip()
    return text or None


def codebook(values: set[str]) -> tuple[list[str], dict[str, int]]:
    labels = sorted(values, key=lambda value: (value.casefold(), value))
    return labels, {label: index for index, label in enumerate(labels)}


def normalized_code_map(value: Any, *, label: str) -> dict[str, int]:
    if not isinstance(value, dict) or not value:
        raise ValueError(f"Missing {label} code table")
    result = {str(key): int(code) for key, code in value.items()}
    if len(set(result.values())) != len(result):
        raise ValueError(f"Duplicate values in {label} code table")
    return dict(sorted(result.items()))


def ordered_code_labels(code_map: dict[str, int], *, label: str) -> list[str]:
    expected = set(range(len(code_map)))
    if set(code_map.values()) != expected:
        raise ValueError(f"{label} codes must be contiguous from zero")
    labels = [""] * len(code_map)
    for value, code in code_map.items():
        labels[code] = value
    return labels


def unique_morphology_codes(
    morphology: Any,
    morphology_codes: dict[str, int],
) -> tuple[list[int], list[int]]:
    if not isinstance(morphology, list):
        raise ValueError("Crop-circle morphology must be a list")
    families: set[int] = set()
    tiers: set[int] = set()
    for item in morphology:
        if not isinstance(item, dict):
            raise ValueError("Crop-circle morphology entries must be objects")
        family = item.get("family")
        if family not in morphology_codes:
            raise ValueError(f"Unsupported morphology family: {family!r}")
        families.add(morphology_codes[family])
        tier = item.get("complexityTier")
        if tier not in COMPLEXITY_TIER_CODES:
            raise ValueError(f"Unsupported complexity tier: {tier!r}")
        tiers.add(COMPLEXITY_TIER_CODES[tier])
    return sorted(families), sorted(tiers)


def crop_coordinate_class(record: dict[str, Any]) -> tuple[int, bool]:
    has_lat = record.get("lat") is not None
    has_lon = record.get("lon") is not None
    if has_lat is not has_lon:
        raise ValueError(f"Partial crop-circle coordinates: {record.get('id')}")
    if not has_lat:
        return COORDINATE_CLASS_CODES["unmapped"], False
    if record.get("exactCoordinate") is True:
        return COORDINATE_CLASS_CODES["exact"], True
    if record.get("markerConfidence") == "provisional":
        return COORDINATE_CLASS_CODES["candidate"], True
    return COORDINATE_CLASS_CODES["locality"], True


def build_crop_projection(
    source_root: Path,
) -> tuple[list[list[Any]], list[str], list[str], dict[str, Any], dict[str, int]]:
    layer_root = source_root / "crop_circles"
    manifest, manifest_bytes = load_json(layer_root / "manifest.json")
    morphology_codes = normalized_code_map(
        (manifest.get("codes") or {}).get("morphology"),
        label="crop-circle morphology",
    )
    declarations = (manifest.get("details") or {}).get("files")
    if not isinstance(declarations, list) or not declarations:
        raise ValueError("Crop-circle manifest has no detail declarations")

    records: dict[str, dict[str, Any]] = {}
    for declaration in declarations:
        payload = read_declared_gzip(layer_root, declaration)
        if not isinstance(payload, dict):
            raise ValueError("Crop-circle detail chunks must be objects")
        for record_id, record in payload.items():
            if not isinstance(record, dict) or record.get("id") != record_id:
                raise ValueError(f"Crop-circle detail identity mismatch: {record_id}")
            if record_id in records:
                raise ValueError(f"Duplicate crop-circle ID: {record_id}")
            records[record_id] = record

    expected_count = int((manifest.get("counts") or {}).get("events", -1))
    if len(records) != expected_count:
        raise ValueError("Crop-circle detail count does not match its manifest")

    country_values = {
        country
        for record in records.values()
        if (country := text_or_none(record.get("country"))) is not None
    }
    crop_values = {
        crop
        for record in records.values()
        if (crop := text_or_none(record.get("crop"))) is not None
    }
    country_labels, country_codes = codebook(country_values)
    crop_labels, crop_codes = codebook(crop_values)

    rows: list[list[Any]] = []
    for record_id in sorted(records):
        record = records[record_id]
        family_codes, tier_codes = unique_morphology_codes(
            record.get("morphology"),
            morphology_codes,
        )
        coordinate_code, mapped = crop_coordinate_class(record)
        country = text_or_none(record.get("country"))
        crop = text_or_none(record.get("crop"))
        start_year = date_year(record.get("dateIso"))
        end_year = date_year(record.get("endDateIso"))
        if end_year is None:
            end_year = start_year
        start_ordinal, end_ordinal = date_interval_ordinals(
            record.get("dateIso"),
            record.get("endDateIso"),
        )
        rows.append([
            record_id,
            start_year,
            end_year,
            DATE_PRECISION_CODES[normalized_date_precision(record.get("datePrecision"))],
            country_codes.get(country) if country is not None else None,
            crop_codes.get(crop) if crop is not None else None,
            family_codes,
            tier_codes,
            coordinate_code,
            mapped,
            bool(text_or_none(record.get("sourceDescription")) or record.get("sourceDescriptions")),
            bool(record.get("reportedSizeM") is not None or text_or_none(record.get("sizeText"))),
            start_ordinal,
            end_ordinal,
        ])

    expected_mapped = int((manifest.get("counts") or {}).get("mapped", -1))
    if sum(row[9] for row in rows) != expected_mapped:
        raise ValueError("Crop-circle mapped count does not match its manifest")
    source = {
        "manifest": "webapp/static_public/data/crop_circles/manifest.json",
        "manifestSha256": sha256_bytes(manifest_bytes),
        "releaseId": manifest.get("releaseId"),
        "rowCount": len(rows),
        "sourceCommit": manifest.get("sourceCommit"),
        "sourceSchema": manifest.get("sourceSchema"),
    }
    return rows, country_labels, crop_labels, source, morphology_codes


def schema_indices(declaration: dict[str, Any], required: set[str]) -> dict[str, int]:
    schema = declaration.get("rowSchema")
    if not isinstance(schema, list) or len(schema) != len(set(schema)):
        raise ValueError("Invalid source row schema")
    missing = required - set(schema)
    if missing:
        raise ValueError(f"Source row schema is missing: {sorted(missing)}")
    return {name: index for index, name in enumerate(schema)}


def build_animal_projection(
    source_root: Path,
) -> tuple[list[list[Any]], dict[str, Any], dict[str, int]]:
    layer_root = source_root / "animal_mutilations"
    manifest, manifest_bytes = load_json(layer_root / "manifest.json")
    catalog_declaration = manifest.get("catalog")
    if not isinstance(catalog_declaration, dict):
        raise ValueError("Animal-report manifest has no catalog declaration")
    catalog = read_declared_gzip(layer_root, catalog_declaration)
    if not isinstance(catalog, list):
        raise ValueError("Animal-report catalog must be an array")
    indices = schema_indices(
        catalog_declaration,
        {"id", "dateStart", "dateEnd", "datePrecisionCode", "speciesGroupCodes", "mapped", "status"},
    )
    species_codes = normalized_code_map(
        (manifest.get("codes") or {}).get("speciesGroup"),
        label="animal species-group",
    )
    valid_species_codes = set(species_codes.values())
    source_date_codes = normalized_code_map(
        (manifest.get("codes") or {}).get("datePrecision"),
        label="animal date-precision",
    )
    date_labels_by_code = {code: label for label, code in source_date_codes.items()}

    rows: list[list[Any]] = []
    seen_ids: set[str] = set()
    for source_row in catalog:
        if not isinstance(source_row, list) or len(source_row) != len(catalog_declaration["rowSchema"]):
            raise ValueError("Animal-report catalog row does not match its schema")
        record_id = str(source_row[indices["id"]])
        if record_id in seen_ids:
            raise ValueError(f"Duplicate animal-report ID: {record_id}")
        seen_ids.add(record_id)
        raw_species_codes = source_row[indices["speciesGroupCodes"]]
        if not isinstance(raw_species_codes, list):
            raise ValueError(f"Animal-report species groups must be an array: {record_id}")
        row_species_codes = sorted({int(code) for code in raw_species_codes})
        if not set(row_species_codes) <= valid_species_codes:
            raise ValueError(f"Unknown animal-report species-group code: {record_id}")
        raw_date_code = int(source_row[indices["datePrecisionCode"]])
        if raw_date_code not in date_labels_by_code:
            raise ValueError(f"Unknown animal-report date-precision code: {record_id}")
        status = str(source_row[indices["status"]])
        if status not in ANIMAL_STATUS_CODES:
            raise ValueError(f"Unsupported animal-report status: {status!r}")
        start_year = date_year(source_row[indices["dateStart"]])
        end_year = date_year(source_row[indices["dateEnd"]])
        if end_year is None:
            end_year = start_year
        start_ordinal, end_ordinal = date_interval_ordinals(
            source_row[indices["dateStart"]],
            source_row[indices["dateEnd"]],
        )
        rows.append([
            record_id,
            start_year,
            end_year,
            DATE_PRECISION_CODES[
                normalized_date_precision(date_labels_by_code[raw_date_code])
            ],
            row_species_codes,
            bool(source_row[indices["mapped"]]),
            ANIMAL_STATUS_CODES[status],
            start_ordinal,
            end_ordinal,
        ])
    rows.sort(key=lambda row: row[0])

    expected_count = int((manifest.get("counts") or {}).get("records", -1))
    expected_mapped = int((manifest.get("counts") or {}).get("mapped", -1))
    if len(rows) != expected_count:
        raise ValueError("Animal-report row count does not match its manifest")
    if sum(row[5] for row in rows) != expected_mapped:
        raise ValueError("Animal-report mapped count does not match its manifest")
    source = {
        "manifest": "webapp/static_public/data/animal_mutilations/manifest.json",
        "manifestSha256": sha256_bytes(manifest_bytes),
        "releaseId": manifest.get("releaseId"),
        "rowCount": len(rows),
        "sourceSchema": manifest.get("sourceSchema"),
    }
    return rows, source, species_codes


def sealed_ufo_catalog_metadata(
    *,
    catalog_source: Path,
    canonical_web_manifest_path: Path,
    release_seal_path: Path,
) -> dict[str, Any]:
    canonical_manifest, canonical_bytes = load_json(canonical_web_manifest_path)
    release_seal, release_bytes = load_json(release_seal_path)
    sealed_files = (release_seal.get("r2") or {}).get("files")
    if not isinstance(sealed_files, list):
        raise ValueError("Release seal has no R2 file inventory")
    canonical_repo_path = repository_path(canonical_web_manifest_path)
    sealed_canonical = next(
        (item for item in sealed_files if item.get("path") == canonical_repo_path),
        None,
    )
    if not isinstance(sealed_canonical, dict):
        raise ValueError("Release seal does not inventory the canonical web manifest")
    canonical_sha256 = sha256_bytes(canonical_bytes)
    if canonical_sha256 != sealed_canonical.get("sha256"):
        raise ValueError("Canonical web manifest does not match the release seal")

    r2_base_url = str((release_seal.get("r2") or {}).get("base_url") or "").rstrip("/")
    release_id = Path(urlparse(r2_base_url).path).name
    if not SAFE_RELEASE_ID_RE.fullmatch(release_id):
        raise ValueError("Could not derive a safe UFO catalog release ID")
    row_count = int((canonical_manifest.get("counts") or {}).get("events", -1))
    mapped_count = int((canonical_manifest.get("counts") or {}).get("mapped_events", -1))
    sealed_count = int((release_seal.get("release") or {}).get("normalized_count", -1))
    if row_count <= 0 or row_count != sealed_count:
        raise ValueError("UFO catalog count does not match the release seal")
    configured_source = str(
        (canonical_manifest.get("source") or {}).get("input_path") or ""
    ).replace("\\", "/")
    catalog_repo_path = repository_path(catalog_source)
    if not configured_source.casefold().endswith(catalog_repo_path.casefold()):
        raise ValueError("Canonical web manifest points at a different catalog source")
    if not catalog_source.is_file():
        raise ValueError(f"Canonical catalog source is missing: {catalog_source}")

    source_corpus_sha256, source_corpus_row_count = sha256_jsonl(catalog_source)
    reviewed_merge_reduction = source_corpus_row_count - row_count
    if reviewed_merge_reduction < 0:
        raise ValueError("Served UFO catalog has more rows than its canonical source corpus")

    return {
        "canonicalWebManifestBytes": len(canonical_bytes),
        "canonicalWebManifest": canonical_repo_path,
        "canonicalWebManifestSha256": canonical_sha256,
        "hashRole": "served_catalog_manifest",
        "mappedRowCount": mapped_count,
        "releaseId": release_id,
        "releaseSeal": repository_path(release_seal_path),
        "releaseSealSha256": sha256_bytes(release_bytes),
        "reviewedMergedShellReduction": reviewed_merge_reduction,
        "rowCount": row_count,
        "sha256": canonical_sha256,
        "sourceCorpusBytes": catalog_source.stat().st_size,
        "sourceCorpusHashRole": "pre_serving_canonical_source_corpus",
        "sourceCorpusPath": catalog_repo_path,
        "sourceCorpusRowCount": source_corpus_row_count,
        "sourceCorpusSha256": source_corpus_sha256,
    }


def write_projection(
    *,
    output_root: Path,
    filename: str,
    browser_base_path: str,
    rows: list[list[Any]],
    row_schema: list[str],
) -> dict[str, Any]:
    raw = canonical_json_document(rows)
    compressed = deterministic_gzip(raw)
    output_root.mkdir(parents=True, exist_ok=True)
    raw_path = output_root / filename
    gzip_path = output_root / f"{filename}.gz"
    raw_path.write_bytes(raw)
    gzip_path.write_bytes(compressed)
    browser_prefix = browser_base_path.strip("/")
    return {
        "bytes": len(raw),
        "file": f"{browser_prefix}/{filename}",
        "gzipBytes": len(compressed),
        "gzipFile": f"{browser_prefix}/{filename}.gz",
        "gzipSha256": sha256_bytes(compressed),
        "rowCount": len(rows),
        "rowSchema": row_schema,
        "sha256": sha256_bytes(raw),
    }


def build(
    *,
    source_root: Path = DEFAULT_SOURCE_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    catalog_source: Path = DEFAULT_CATALOG_SOURCE,
    canonical_web_manifest_path: Path = DEFAULT_CANONICAL_WEB_MANIFEST,
    release_seal_path: Path = DEFAULT_RELEASE_SEAL,
    release_id: str = DEFAULT_RELEASE_ID,
    browser_base_path: str = DEFAULT_BROWSER_BASE_PATH,
) -> dict[str, Any]:
    if not SAFE_RELEASE_ID_RE.fullmatch(release_id):
        raise ValueError(f"Invalid analysis release ID: {release_id!r}")
    if not browser_base_path.strip("/") or ".." in Path(browser_base_path).parts:
        raise ValueError("Invalid browser artifact base path")

    crop_rows, countries, crop_types, crop_source, morphology_codes = build_crop_projection(
        source_root,
    )
    animal_rows, animal_source, species_codes = build_animal_projection(source_root)
    ufo_catalog_source = sealed_ufo_catalog_metadata(
        catalog_source=catalog_source,
        canonical_web_manifest_path=canonical_web_manifest_path,
        release_seal_path=release_seal_path,
    )
    crop_artifact = write_projection(
        output_root=output_root,
        filename="crop_circles.json",
        browser_base_path=browser_base_path,
        rows=crop_rows,
        row_schema=CROP_ROW_SCHEMA,
    )
    animal_artifact = write_projection(
        output_root=output_root,
        filename="animal_reports.json",
        browser_base_path=browser_base_path,
        rows=animal_rows,
        row_schema=ANIMAL_ROW_SCHEMA,
    )

    manifest = {
        "artifacts": {
            "animalReports": animal_artifact,
            "cropCircles": crop_artifact,
        },
        "codes": {
            "complexityTier": ordered_code_labels(
                COMPLEXITY_TIER_CODES,
                label="complexity-tier",
            ),
            "coordinateClass": ordered_code_labels(
                COORDINATE_CLASS_CODES,
                label="coordinate-class",
            ),
            "datePrecision": ordered_code_labels(
                DATE_PRECISION_CODES,
                label="date-precision",
            ),
            "morphologyFamily": ordered_code_labels(
                morphology_codes,
                label="morphology-family",
            ),
            "speciesGroup": ordered_code_labels(
                species_codes,
                label="species-group",
            ),
            "status": ordered_code_labels(
                ANIMAL_STATUS_CODES,
                label="animal-status",
            ),
        },
        "counts": {
            "animalReports": len(animal_rows),
            "cropCircles": len(crop_rows),
            "mappedAnimalReports": sum(row[5] for row in animal_rows),
            "ufoCatalog": ufo_catalog_source["rowCount"],
            "unmappedAnimalReports": sum(not row[5] for row in animal_rows),
        },
        "determinism": {
            "canonicalJson": "utf8_sorted_keys_compact_with_lf",
            "gzipMtime": 0,
            "rowOrder": "id_ascending",
        },
        "dictionaries": {
            "country": countries,
            "cropType": crop_types,
        },
        "policy": {
            "authenticityAssessments": False,
            "causalInferences": False,
            "crossDomainJoins": False,
            "proximityMetrics": False,
            "scope": "descriptive_catalog_aggregates_only",
            "speciesGroupsIncluded": True,
            "traceMetrics": False,
            "travelMetrics": False,
            "ufoRelationships": False,
            "unmappedAnimalReportsIncluded": True,
        },
        "releaseId": release_id,
        "schemaId": SCHEMA_ID,
        "schemaVersion": 1,
        "sources": {
            "animalReports": animal_source,
            "cropCircles": crop_source,
            "ufoCatalog": ufo_catalog_source,
        },
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "manifest.json").write_bytes(canonical_json_document(manifest))
    return manifest


def main() -> int:
    args = parse_args()
    manifest = build(
        source_root=args.source_root,
        output_root=args.output,
        catalog_source=args.catalog_source,
        canonical_web_manifest_path=args.canonical_web_manifest,
        release_seal_path=args.release_seal,
        release_id=args.release_id,
        browser_base_path=args.browser_base_path,
    )
    print(json.dumps({
        "artifacts": manifest["artifacts"],
        "counts": manifest["counts"],
        "releaseId": manifest["releaseId"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
