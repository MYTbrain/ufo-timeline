"""Audit raw color evidence before any Wave 7 normalization rules are written."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DETAIL_ROOT = REPO_ROOT / "static_bundle" / "data" / "canonical_web" / "event_chunks"
DEFAULT_CHUNK_MANIFEST = REPO_ROOT / "static_bundle" / "data" / "canonical_web" / "event_chunk_manifest.json"
DEFAULT_OUTPUT = (
    REPO_ROOT / "campaign" / "analysis_improvement" / "waves" /
    "wave-007-color-assessment" / "raw_value_audit.json"
)
SCHEMA_ID = "ufo-timeline-analysis-color-raw-audit-v1.0.0"
EXPECTED_CATALOG_ROWS = 702_893
EXPECTED_ELIGIBLE_ROWS = 79_215
EXPECTED_SOURCES = {"nuforc": 11_686, "ufocat": 67_529}
SOURCE_COLOR_KEYS = {"nuforc": "Color", "ufocat": "COLOR"}
EXCLUDED_SENTINELS = {"unknown", "unk", "n/a", "na", "none", "null"}
KEY_NORMALIZER = re.compile(r"[^a-z0-9]+")
LIGHT_ROLE_CUE = re.compile(r"\b(?:light|lights|glow|glowing|illumination|illuminated)\b", re.I)
OBJECT_ROLE_CUE = re.compile(r"\b(?:object|craft|body|hull|surface|exterior|fuselage)\b", re.I)
CHANGING_CUE = re.compile(r"\b(?:change|changed|changing|flashing|flashes|pulsing|cycling|alternating)\b", re.I)
MULTICOLOR_CUE = re.compile(r"\b(?:multi(?:colou?red)?|multiple|various|rainbow|different colou?rs?)\b", re.I)
DESCRIPTOR_CUE = re.compile(
    r"\b(?:luminous|metallic|shiny|bright|fiery|transparent|translucent|reflective|clear|dark)\b",
    re.I,
)
COMPOUND_SEPARATOR_CUE = re.compile(r"[/,&+]|\b(?:and|or)\b", re.I)
COLOR_ANCHORS = (
    "white", "black", "gray", "grey", "red", "orange", "yellow", "amber", "green", "blue",
    "aqua", "cyan", "teal", "purple", "violet", "pink", "magenta", "brown", "tan", "beige",
    "cream", "gold", "golden", "silver", "crimson", "scarlet", "maroon", "burgundy", "indigo",
    "lavender", "peach", "ivory", "copper", "bronze",
)
COLOR_ANCHOR_CUE = re.compile(r"\b(?:" + "|".join(COLOR_ANCHORS) + r")\b", re.I)


def compact_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_key(value: Any) -> str:
    return KEY_NORMALIZER.sub("", str(value).lower())


def eligible_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in EXCLUDED_SENTINELS:
        return None
    return text


def matching_color_fields(raw_fields: Any) -> list[tuple[str, str]]:
    if not isinstance(raw_fields, dict):
        return []
    matches = []
    for key, value in raw_fields.items():
        if "color" not in normalized_key(key) and "colour" not in normalized_key(key):
            continue
        raw_text = "" if value is None else str(value)
        if eligible_text(raw_text) is not None:
            matches.append((str(key), raw_text))
    return matches


def counter_rows(counter: Counter[str], *, limit: int | None = None) -> list[dict[str, Any]]:
    ordered = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    if limit is not None:
        ordered = ordered[:limit]
    return [{"value": value, "rows": rows} for value, rows in ordered]


def role_anchor(value: str) -> str:
    light = bool(LIGHT_ROLE_CUE.search(value))
    object_ = bool(OBJECT_ROLE_CUE.search(value))
    if light and object_:
        return "both_explicit_role_cues"
    if light:
        return "explicit_light_role_cue"
    if object_:
        return "explicit_object_role_cue"
    return "no_explicit_role_cue"


def structural_anchors(value: str) -> Iterable[str]:
    if COLOR_ANCHOR_CUE.search(value):
        yield "named_color_word"
    if CHANGING_CUE.search(value):
        yield "changing_color_word"
    if MULTICOLOR_CUE.search(value):
        yield "multicolor_word"
    if DESCRIPTOR_CUE.search(value):
        yield "appearance_or_luminosity_descriptor"
    if COMPOUND_SEPARATOR_CUE.search(value):
        yield "compound_separator_or_conjunction"


def build_audit(detail_root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, list):
        raise ValueError("Canonical event chunk manifest must be an array")
    expected_files = [str(item["file"]) for item in manifest]
    chunk_paths = [detail_root / filename for filename in expected_files]
    if not chunk_paths or any(not path.is_file() for path in chunk_paths):
        raise ValueError("One or more canonical event chunks are missing")

    catalog_rows = 0
    eligible_rows = 0
    multiple_field_rows = 0
    source_catalog_rows: Counter[str] = Counter()
    source_eligible_rows: Counter[str] = Counter()
    canonical_field_keys: Counter[str] = Counter()
    raw_value_counts: Counter[tuple[str, str]] = Counter()
    global_value_counts: Counter[str] = Counter()
    schema_field_rows: Counter[str] = Counter()
    raw_source_blank_rows: Counter[str] = Counter()
    raw_source_sentinel_rows: dict[str, Counter[str]] = defaultdict(Counter)
    raw_source_eligible_rows: Counter[str] = Counter()
    canonical_source_parity_rows: Counter[str] = Counter()
    parity_mismatches: Counter[str] = Counter()
    role_anchor_rows: Counter[str] = Counter()
    source_role_anchor_rows: dict[str, Counter[str]] = defaultdict(Counter)
    structural_anchor_rows: Counter[str] = Counter()
    chunk_inventory = []

    for chunk_path in chunk_paths:
        raw_bytes = chunk_path.read_bytes()
        chunk_inventory.append([
            chunk_path.name,
            len(raw_bytes),
            sha256_bytes(raw_bytes),
        ])
        rows = json.loads(raw_bytes)
        if not isinstance(rows, list):
            raise ValueError(f"Canonical detail chunk is not an array: {chunk_path}")
        for event in rows:
            catalog_rows += 1
            source = str(event.get("source") or "unknown").strip().lower() or "unknown"
            source_catalog_rows[source] += 1
            source_key = SOURCE_COLOR_KEYS.get(source)
            raw_source_row = event.get("raw_source_row")
            source_text: str | None = None
            if source_key and isinstance(raw_source_row, dict) and source_key in raw_source_row:
                schema_field_rows[source] += 1
                source_raw = raw_source_row.get(source_key)
                source_text = "" if source_raw is None else str(source_raw).strip()
                if not source_text:
                    raw_source_blank_rows[source] += 1
                elif source_text.lower() in EXCLUDED_SENTINELS:
                    raw_source_sentinel_rows[source][source_text.lower()] += 1
                else:
                    raw_source_eligible_rows[source] += 1

            matches = matching_color_fields(event.get("raw_fields"))
            if not matches:
                if source_text and source_text.lower() not in EXCLUDED_SENTINELS:
                    parity_mismatches[f"{source}:eligible_raw_source_missing_canonical_field"] += 1
                continue
            eligible_rows += 1
            source_eligible_rows[source] += 1
            if len(matches) > 1:
                multiple_field_rows += 1
            for key, value in matches:
                canonical_field_keys[key] += 1
                raw_value_counts[(source, value)] += 1
                global_value_counts[value] += 1
                anchor = role_anchor(value)
                role_anchor_rows[anchor] += 1
                source_role_anchor_rows[source][anchor] += 1
                for structural_anchor in structural_anchors(value):
                    structural_anchor_rows[structural_anchor] += 1
                if source_text == value.strip():
                    canonical_source_parity_rows[source] += 1
                else:
                    parity_mismatches[f"{source}:trimmed_value_mismatch"] += 1

    if catalog_rows != EXPECTED_CATALOG_ROWS:
        raise ValueError(f"Served catalog row count changed: {catalog_rows}/{EXPECTED_CATALOG_ROWS}")
    if eligible_rows != EXPECTED_ELIGIBLE_ROWS:
        raise ValueError(f"Eligible raw color row count changed: {eligible_rows}/{EXPECTED_ELIGIBLE_ROWS}")
    if dict(source_eligible_rows) != EXPECTED_SOURCES:
        raise ValueError(f"Eligible color source counts changed: {dict(source_eligible_rows)}/{EXPECTED_SOURCES}")
    if multiple_field_rows:
        raise ValueError(f"Color-bearing events contain multiple matching canonical fields: {multiple_field_rows}")
    if parity_mismatches:
        raise ValueError(f"Canonical/source color parity failed: {dict(parity_mismatches)}")

    ordered_inventory = sorted(
        ([source, sha256_bytes(value.encode("utf-8")), value, count] for (source, value), count in raw_value_counts.items()),
        key=lambda row: (row[0], row[1], row[2]),
    )
    source_profiles = {}
    for source in sorted(source_eligible_rows):
        source_values = Counter({value: count for (item_source, value), count in raw_value_counts.items() if item_source == source})
        top_limit = None if source == "ufocat" else 250
        top_values = counter_rows(source_values, limit=top_limit)
        top_rows = sum(item["rows"] for item in top_values)
        source_profiles[source] = {
            "catalogRows": source_catalog_rows[source],
            "schemaFieldRows": schema_field_rows[source],
            "rawSourceBlankRows": raw_source_blank_rows[source],
            "rawSourceSentinelRows": dict(sorted(raw_source_sentinel_rows[source].items())),
            "eligibleRawRows": source_eligible_rows[source],
            "canonicalSourceValueParityRows": canonical_source_parity_rows[source],
            "distinctEligibleRawValues": len(source_values),
            "roleAnchorRows": dict(sorted(source_role_anchor_rows[source].items())),
            "auditedTopValues": top_values,
            "auditedTopValueRows": top_rows,
            "auditedTopValueCoveragePct": round(100 * top_rows / source_eligible_rows[source], 6),
        }

    top_global = counter_rows(global_value_counts, limit=200)
    top_global_rows = sum(item["rows"] for item in top_global)
    return {
        "schemaId": SCHEMA_ID,
        "campaignId": "analysis-improvement-campaign-20260804",
        "waveId": "wave-007-color-assessment",
        "auditBoundary": {
            "stage": "raw_value_audit_before_normalization_rules",
            "descriptionMiningUsed": False,
            "neighboringFieldInferenceUsed": False,
            "normalizationDecisionMade": False,
            "roleAnchorCountsAreParserRules": False,
        },
        "inputs": {
            "eventChunkManifest": manifest_path.relative_to(REPO_ROOT).as_posix(),
            "eventChunkManifestSha256": sha256_file(manifest_path),
            "chunkCount": len(chunk_paths),
            "chunkTreeSha256": sha256_bytes(compact_json_bytes(chunk_inventory)),
        },
        "coverage": {
            "catalogRows": catalog_rows,
            "eligibleRawColorRows": eligible_rows,
            "eligibleCatalogCoveragePct": round(100 * eligible_rows / catalog_rows, 6),
            "eventsWithMultipleMatchingColorFields": multiple_field_rows,
            "canonicalFieldKeys": counter_rows(canonical_field_keys),
            "sourceEligibleRows": dict(sorted(source_eligible_rows.items())),
        },
        "valueInventory": {
            "distinctEligibleRawValuesAcrossSources": len(global_value_counts),
            "distinctSourceValuePairs": len(ordered_inventory),
            "sourceValueInventorySha256": sha256_bytes(compact_json_bytes(ordered_inventory)),
            "topGlobalValues": top_global,
            "topGlobalValueRows": top_global_rows,
            "topGlobalValueCoveragePct": round(100 * top_global_rows / eligible_rows, 6),
        },
        "sourceProfiles": source_profiles,
        "semanticAuditAnchors": {
            "roleAnchorRows": dict(sorted(role_anchor_rows.items())),
            "structuralAnchorRows": dict(sorted(structural_anchor_rows.items())),
            "interpretation": "Vocabulary audit only. No role or color category may be assigned from these counts alone.",
        },
        "preRuleDecision": {
            "minimumNormalizedRows": 63_372,
            "minimumIndependentSources": 2,
            "minimumRowsPerSupportedSource": 1_000,
            "rawVolumeGatePlausible": eligible_rows >= 63_372,
            "crossSourceVolumeGatePlausible": all(source_eligible_rows[source] >= 1_000 for source in EXPECTED_SOURCES),
            "roleAmbiguityIsMaterial": role_anchor_rows["no_explicit_role_cue"] > eligible_rows / 2,
            "nextAuthorizedStep": "write_and_test_conservative_value_only_parser_rules_with_unknown_role_as_default",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detail-root", type=Path, default=DEFAULT_DETAIL_ROOT)
    parser.add_argument("--chunk-manifest", type=Path, default=DEFAULT_CHUNK_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build_audit(args.detail_root.resolve(), args.chunk_manifest.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
    print(json.dumps({
        "output": str(args.output.resolve()),
        "bytes": args.output.stat().st_size,
        "sha256": sha256_file(args.output),
        "eligibleRawColorRows": result["coverage"]["eligibleRawColorRows"],
        "distinctSourceValuePairs": result["valueInventory"]["distinctSourceValuePairs"],
        "roleAnchorRows": result["semanticAuditAnchors"]["roleAnchorRows"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
