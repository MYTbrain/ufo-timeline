"""Read-only evidence-preservation audit for unresolved craft-type unknowns."""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import re
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser.craft_types import infer_event_craft_type, normalize_text
from parser.taxonomy import display_type_for_web_event, visual_type_group_for_web_event


INPUT = Path("data/canonical_full_maximal_v3_rehydrated_jurisdiction_repair/deduped_events.jsonl")
OUT_JSON = Path("data/reports/craft_unknown_evidence_preservation_audit.json")
OUT_MD = Path("data/reports/craft_unknown_evidence_preservation_audit.md")
RAW_DIR = Path("UFO Databases")
TOP_LIMIT = 25
SAMPLE_LIMIT = 8

MORPHOLOGY_PATTERNS = {
    "disc_saucer": re.compile(r"\b(dis[ck]s?|saucers?|flying saucers?|discoid(?:al)?|lenticular|domes?|domed|saturn|ring|wheel|top[- ]?shaped|bowl[- ]?shaped)\b", re.I),
    "sphere_orb": re.compile(r"\b(spheres?|spherical|orbs?|ball(?: of light)?|globes?|globular|round(?:ish)?\s+(?:object|craft|ufo)|circular\s+(?:object|craft|ufo))\b", re.I),
    "triangle": re.compile(r"\b(triangular|triangles?|delta[- ]?shaped|black triangle)\b", re.I),
    "chevron_boomerang": re.compile(r"\b(chevrons?|boomerangs?|v[- ]?shaped|vee[- ]?shaped|arrowhead|crescent[- ]?shaped)\b", re.I),
    "cigar_cylinder": re.compile(r"\b(cigars?|cylind\w*|tube[- ]?shaped|rocket[- ]?shaped|oblong|elongat(?:e|ed)|bullet[- ]?shaped|airship|capsul(?:e|ar)?|tic[- ]?tac|tictac)\b", re.I),
    "oval_egg": re.compile(r"\b(oval\w*|egg[- ]?shape(?:d)?|eggshaped|elliptic(?:al)?|ellipse|ellipsoid|football[- ]?shaped|almond[- ]?shaped)\b", re.I),
    "rectangle_box": re.compile(r"\b(rectang\w*|box(?:es|[- ]?shaped)?|cubes?|cubical|square[- ]?shaped)\b", re.I),
    "diamond": re.compile(r"\b(diamond[- ]?shaped|diamonds?)\b", re.I),
    "cone": re.compile(r"\b(cones?|conical|pyramids?)\b", re.I),
    "teardrop": re.compile(r"\b(tear[- ]?drops?|teardrops?)\b", re.I),
    "dumbbell_barbell": re.compile(r"\b(dumbbell|barbell)\b", re.I),
}

LIGHT_RE = re.compile(r"\b(light(?:s)?|luminous|glow(?:ing)?|flash(?:es|ing)?|pulse|pulsing|star[- ]?like|bright|aura|trail|streak)\b", re.I)
FORMATION_RE = re.compile(r"\b(formation|fleet|cluster|row of lights|line of lights|string of lights|multiple lights|several lights)\b", re.I)
BEHAVIOR_RE = re.compile(r"\b(hover(?:ing)?|silent|rapid acceleration|accelerat(?:e|ed|ing)|zig[- ]?zag|puls(?:e|ing)|trail|chasing|radar|em effect|electromagnetic|landed|takeoff|maneuver|stationary)\b", re.I)
PROSAIC_RE = re.compile(r"\b(aircraft|airplane|aeroplane|plane|helicopter|balloon|weather balloon|kite|bird|drone|satellite|starlink|venus|mars|moon|meteor|bolide|rocket launch|flare|hoax|misidentification|identified as|explained as|probably a)\b", re.I)
ENTITY_RE = re.compile(r"\b(entity|entities|being|beings|occupant|occupants|abduction|abducted|close encounter|ce[2345])\b", re.I)
INSTRUMENT_RE = re.compile(r"\b(photo|photograph|camera|video|film|radar|instrument|sensor|image|picture)\b", re.I)
RAW_FILE_RE = re.compile(r"(ufocat|mufon|nuforc|majestic|updb|phenomen)", re.I)

PARSER_EXPLICIT_FIELDS = {
    "shape_normalized",
    "shape_raw",
    "type_normalized",
    "type_raw",
    "description",
    "summary",
    "raw_fields.SHAPE",
    "raw_fields.TYPE",
    "raw_fields.HYNEK",
    "raw_fields.VALLEE",
}
PARSER_GENERIC_NOTE = (
    "all raw_fields values are stringified and scanned generically after standard "
    "fields; most source-specific fields are not explicitly decoded."
)


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"{path} line {line_number}: {exc}") from exc
            if isinstance(payload, dict):
                yield payload


def clean(value: Any, limit: int | None = None) -> str:
    text = normalize_text(value)
    if limit and len(text) > limit:
        return text[:limit].rstrip() + "..."
    return text


def source_key(event: dict[str, Any]) -> str:
    return clean(event.get("source_name")).lower() or "unknown"


def is_app_unknown(event: dict[str, Any]) -> bool:
    if display_type_for_web_event(event) is None:
        return True
    return visual_type_group_for_web_event(event) == "Other / unknown"


def add_sample(items: list[Any], item: Any, limit: int = SAMPLE_LIMIT) -> None:
    if len(items) < limit and item not in items:
        items.append(item)


def morphology_hits(text: str) -> set[str]:
    return {name for name, pattern in MORPHOLOGY_PATTERNS.items() if text and pattern.search(text)}


def metadata_hits(text: str) -> set[str]:
    hits = set()
    if LIGHT_RE.search(text):
        hits.add("light_pattern")
    if FORMATION_RE.search(text):
        hits.add("formation_type")
    if BEHAVIOR_RE.search(text):
        hits.add("behavior_tags")
    if PROSAIC_RE.search(text):
        hits.add("prosaic_candidate")
    if ENTITY_RE.search(text):
        hits.add("entity_or_encounter_context")
    if INSTRUMENT_RE.search(text):
        hits.add("evidence_type_instrument_photo")
    return hits


def sample_event(event: dict[str, Any], include_raw_source: bool = True) -> dict[str, Any]:
    raw_fields = event.get("raw_fields") if isinstance(event.get("raw_fields"), dict) else {}
    raw_source_row = event.get("raw_source_row") if isinstance(event.get("raw_source_row"), dict) else {}
    raw_excerpt = {
        str(key): clean(value, 160)
        for key, value in list(raw_fields.items())[:10]
        if clean(value)
    }
    source_excerpt = {}
    if include_raw_source:
        source_excerpt = {
            str(key): clean(value, 160)
            for key, value in list(raw_source_row.items())[:12]
            if clean(value)
        }
    return {
        "canonical_event_id": event.get("canonical_event_id"),
        "source_name": event.get("source_name"),
        "source_file": event.get("source_file"),
        "source_row_number": event.get("source_row_number"),
        "date_iso": event.get("date_iso"),
        "location_raw": event.get("location_raw"),
        "shape_raw": event.get("shape_raw"),
        "shape_normalized": event.get("shape_normalized"),
        "type_raw": event.get("type_raw"),
        "type_normalized": event.get("type_normalized"),
        "description_excerpt": clean(event.get("description"), 220),
        "summary_excerpt": clean(event.get("summary"), 160),
        "raw_fields_excerpt": raw_excerpt,
        "raw_source_row_excerpt": source_excerpt,
    }


def counter_rows(counter: Counter, limit: int = TOP_LIMIT) -> list[dict[str, Any]]:
    return [{"value": key, "count": int(value)} for key, value in counter.most_common(limit)]


def source_file_candidates() -> list[dict[str, Any]]:
    rows = []
    for base in (Path("UFO Databases"), Path("data"), Path("parser"), Path("scripts")):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or not RAW_FILE_RE.search(path.name):
                continue
            if path.suffix.lower() not in {".csv", ".json", ".jsonl", ".txt", ".md"}:
                continue
            try:
                rows.append({"path": str(path), "bytes": path.stat().st_size})
            except OSError:
                pass
    return sorted(rows, key=lambda item: item["bytes"], reverse=True)[:80]


def raw_path_for(source_file: str | None) -> Path | None:
    if not source_file:
        return None
    candidates = [RAW_DIR / source_file, PROJECT_ROOT / source_file, RAW_DIR / "sources" / source_file]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    target = Path(source_file).name.lower()
    for base in (RAW_DIR, RAW_DIR / "sources"):
        if base.exists():
            for path in base.glob("*"):
                if path.name.lower() == target:
                    return path
    return None


def row_morphology(row: dict[str, Any]) -> tuple[set[str], dict[str, str]]:
    hits = set()
    fields = {}
    for key, value in row.items():
        text = clean(value)
        if not text:
            continue
        found = morphology_hits(text)
        if found:
            hits.update(found)
            fields[str(key)] = clean(value, 220)
    return hits, fields


def finalize_field_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "field": entry["field"],
        "non_empty_count": int(entry["non_empty_count"]),
        "sources": dict(entry["sources"].most_common()),
        "sample_values": entry["sample_values"],
        "morphology_hit_count": int(entry["morphology_hit_count"]),
        "morphology_buckets": dict(entry["morphology_buckets"].most_common()),
        "metadata_hit_count": int(entry["metadata_hit_count"]),
        "metadata_targets": dict(entry["metadata_targets"].most_common()),
        "parser_handling": entry["parser_handling"],
    }


def main() -> None:
    totals = Counter()
    source_counts: dict[str, Counter] = defaultdict(Counter)
    source_samples: dict[str, list[Any]] = defaultdict(list)
    source_field_stats: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    raw_field_inventory: dict[str, dict[str, Any]] = {}
    raw_source_only_inventory: dict[str, dict[str, Any]] = {}
    raw_source_missing = Counter()
    raw_source_morph_missing = Counter()
    raw_source_meta_missing = Counter()
    craft_field_scores = Counter()
    metadata_field_scores = Counter()
    craft_field_examples: dict[str, list[Any]] = defaultdict(list)
    metadata_field_examples: dict[str, list[Any]] = defaultdict(list)
    morphology_locations = Counter()
    metadata_locations = Counter()
    source_code_values = Counter()
    source_code_examples: dict[str, list[Any]] = defaultdict(list)
    dedupe_targets_by_file: dict[str, set[int]] = defaultdict(set)
    dedupe_events: dict[str, dict[str, Any]] = {}
    provenance_by_file_row: dict[tuple[str, int], list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    provenance_member_total = 0

    def field_entry(table: dict[str, dict[str, Any]], field: str, handling: str) -> dict[str, Any]:
        return table.setdefault(field, {
            "field": field,
            "non_empty_count": 0,
            "sources": Counter(),
            "sample_values": [],
            "morphology_hit_count": 0,
            "morphology_buckets": Counter(),
            "metadata_hit_count": 0,
            "metadata_targets": Counter(),
            "parser_handling": handling,
        })

    for event in iter_jsonl(INPUT):
        totals["events_scanned"] += 1
        inference = infer_event_craft_type(event)
        if not (is_app_unknown(event) and inference.get("craft_type_inferred") == "unknown"):
            continue

        totals["unresolved_unknowns"] += 1
        source = source_key(event)
        source_counts[source]["unresolved_unknowns"] += 1
        add_sample(source_samples[source], sample_event(event), 5)
        raw_fields = event.get("raw_fields") if isinstance(event.get("raw_fields"), dict) else {}
        raw_source_row = event.get("raw_source_row") if isinstance(event.get("raw_source_row"), dict) else {}

        for base_field in ("shape_normalized", "shape_raw", "type_normalized", "type_raw", "description", "summary"):
            text = clean(event.get(base_field))
            if text:
                source_field_stats[source][base_field]["non_empty"] += 1
                morph = morphology_hits(text)
                meta = metadata_hits(text)
                if morph:
                    source_field_stats[source][base_field]["morphology_hits"] += 1
                    craft_field_scores[f"{source}.{base_field}"] += 1
                    for bucket in morph:
                        morphology_locations[f"{bucket} in {source}.{base_field}"] += 1
                    add_sample(craft_field_examples[f"{source}.{base_field}"], {"event_id": event.get("canonical_event_id"), "value": clean(text, 220), "morphology": sorted(morph)})
                if meta:
                    source_field_stats[source][base_field]["metadata_hits"] += 1
                    metadata_field_scores[f"{source}.{base_field}"] += len(meta)
                    for target in meta:
                        metadata_locations[f"{target} in {source}.{base_field}"] += 1
                    add_sample(metadata_field_examples[f"{source}.{base_field}"], {"event_id": event.get("canonical_event_id"), "value": clean(text, 220), "metadata_targets": sorted(meta)})
            else:
                source_field_stats[source][base_field]["empty"] += 1

        for key, value in raw_fields.items():
            key_s = str(key)
            text = clean(value)
            field = f"raw_fields.{key_s}"
            if not text:
                source_field_stats[source][field]["empty"] += 1
                continue
            handling = "explicitly_decoded" if field in PARSER_EXPLICIT_FIELDS else "generic_raw_fields_text_scan_only"
            entry = field_entry(raw_field_inventory, field, handling)
            entry["non_empty_count"] += 1
            entry["sources"][source] += 1
            add_sample(entry["sample_values"], clean(text, 180))
            source_field_stats[source][field]["non_empty"] += 1
            morph = morphology_hits(text)
            meta = metadata_hits(text)
            if morph:
                entry["morphology_hit_count"] += 1
                source_field_stats[source][field]["morphology_hits"] += 1
                craft_field_scores[f"{source}.{field}"] += 1
                for bucket in morph:
                    entry["morphology_buckets"][bucket] += 1
                    morphology_locations[f"{bucket} in {source}.{field}"] += 1
                add_sample(craft_field_examples[f"{source}.{field}"], {"event_id": event.get("canonical_event_id"), "value": clean(text, 220), "morphology": sorted(morph)})
            if meta:
                entry["metadata_hit_count"] += 1
                source_field_stats[source][field]["metadata_hits"] += 1
                metadata_field_scores[f"{source}.{field}"] += len(meta)
                for target in meta:
                    entry["metadata_targets"][target] += 1
                    metadata_locations[f"{target} in {source}.{field}"] += 1
                add_sample(metadata_field_examples[f"{source}.{field}"], {"event_id": event.get("canonical_event_id"), "value": clean(text, 220), "metadata_targets": sorted(meta)})
            if source == "ufocat" and key_s.upper() in {"TYPE", "SHAPE", "HYNEK", "VALLEE"}:
                code_key = f"ufocat.raw_fields.{key_s}:{text}"
                source_code_values[code_key] += 1
                add_sample(source_code_examples[code_key], sample_event(event, include_raw_source=False), 3)

        raw_keys_lower = {str(key).lower() for key in raw_fields.keys()}
        for key, value in raw_source_row.items():
            key_s = str(key)
            text = clean(value)
            if not text:
                continue
            field = f"raw_source_row.{key_s}"
            source_field_stats[source][field]["non_empty"] += 1
            if key_s.lower() in raw_keys_lower:
                continue
            raw_source_missing[field] += 1
            entry = field_entry(raw_source_only_inventory, field, "preserved_in_raw_source_row_only_not_parser_scanned")
            entry["non_empty_count"] += 1
            entry["sources"][source] += 1
            add_sample(entry["sample_values"], clean(text, 180))
            morph = morphology_hits(text)
            meta = metadata_hits(text)
            if morph:
                raw_source_morph_missing[f"{source}.{field}"] += 1
                entry["morphology_hit_count"] += 1
                craft_field_scores[f"{source}.{field}"] += 1
                for bucket in morph:
                    entry["morphology_buckets"][bucket] += 1
                    morphology_locations[f"{bucket} in {source}.{field}"] += 1
                add_sample(craft_field_examples[f"{source}.{field}"], {"event_id": event.get("canonical_event_id"), "value": clean(text, 220), "morphology": sorted(morph)})
            if meta:
                raw_source_meta_missing[f"{source}.{field}"] += 1
                entry["metadata_hit_count"] += 1
                metadata_field_scores[f"{source}.{field}"] += len(meta)
                for target in meta:
                    entry["metadata_targets"][target] += 1
                    metadata_locations[f"{target} in {source}.{field}"] += 1
                add_sample(metadata_field_examples[f"{source}.{field}"], {"event_id": event.get("canonical_event_id"), "value": clean(text, 220), "metadata_targets": sorted(meta)})

        dup_count = int(event.get("duplicate_record_count") or 0)
        if dup_count > 1:
            totals["unresolved_unknowns_with_duplicate_member_metadata"] += 1
            event_id = str(event.get("canonical_event_id"))
            prov = event.get("source_provenance") if isinstance(event.get("source_provenance"), list) else []
            provenance_member_total += len(prov)
            dedupe_events[event_id] = {"event": sample_event(event, include_raw_source=False), "duplicate_record_count": dup_count, "source_provenance": prov}
            for member in prov:
                if not isinstance(member, dict):
                    continue
                source_file = member.get("source_file")
                row_number = member.get("source_row_number")
                if source_file and row_number:
                    row_number = int(row_number)
                    dedupe_targets_by_file[str(source_file)].add(row_number)
                    provenance_by_file_row[(str(source_file), row_number)].append((event_id, member))

    member_evidence_by_event: dict[str, list[Any]] = defaultdict(list)
    raw_member_scan_summary = {}
    for source_file, row_numbers in dedupe_targets_by_file.items():
        path = raw_path_for(source_file)
        summary = {"source_file": source_file, "path": str(path) if path else None, "targets": len(row_numbers), "rows_found": 0, "rows_with_morphology": 0, "status": "missing_file" if path is None else "scanned"}
        if path is None or path.suffix.lower() != ".csv":
            raw_member_scan_summary[source_file] = summary
            continue
        try:
            with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as handle:
                reader = csv.DictReader(handle)
                for row_index, row in enumerate(reader, start=1):
                    if row_index not in row_numbers:
                        continue
                    summary["rows_found"] += 1
                    morph, fields = row_morphology(row)
                    if morph:
                        summary["rows_with_morphology"] += 1
                        for event_id, member in provenance_by_file_row.get((source_file, row_index), []):
                            member_evidence_by_event[event_id].append({
                                "canonical_input_id": member.get("canonical_input_id"),
                                "source_file": source_file,
                                "source_row_number": row_index,
                                "morphology_buckets": sorted(morph),
                                "evidence_fields": fields,
                            })
                    if summary["rows_found"] >= len(row_numbers):
                        break
        except Exception as exc:
            summary["status"] = f"error: {exc}"
        raw_member_scan_summary[source_file] = summary

    duplicate_examples = []
    for event_id, evidences in member_evidence_by_event.items():
        if not evidences:
            continue
        totals["unresolved_unknowns_with_duplicate_member_direct_morphology"] += 1
        if len(duplicate_examples) < 25:
            duplicate_examples.append({
                "canonical_event_id": event_id,
                "canonical_event": dedupe_events.get(event_id, {}).get("event"),
                "duplicate_record_count": dedupe_events.get(event_id, {}).get("duplicate_record_count"),
                "member_evidence": evidences[:5],
            })

    raw_field_rows = sorted((finalize_field_entry(entry) for entry in raw_field_inventory.values()), key=lambda item: item["non_empty_count"], reverse=True)
    raw_source_only_rows = sorted((finalize_field_entry(entry) for entry in raw_source_only_inventory.values()), key=lambda item: item["non_empty_count"], reverse=True)

    source_specific = {}
    for source in sorted(source_counts):
        field_rows = []
        for field, counter in source_field_stats[source].items():
            non_empty = int(counter.get("non_empty", 0))
            if non_empty <= 0:
                continue
            if field in PARSER_EXPLICIT_FIELDS:
                handling = "explicitly_decoded"
            elif field.startswith("raw_fields."):
                handling = "generic_raw_fields_text_scan_only"
            elif field.startswith("raw_source_row."):
                handling = "raw_source_row_only_not_parser_scanned"
            else:
                handling = "standard_parser_field"
            field_rows.append({
                "field": field,
                "non_empty_count": non_empty,
                "empty_count": int(counter.get("empty", 0)),
                "morphology_hit_count": int(counter.get("morphology_hits", 0)),
                "metadata_hit_count": int(counter.get("metadata_hits", 0)),
                "parser_handling": handling,
            })
        source_specific[source] = {
            "counts": dict(source_counts[source]),
            "available_fields_ranked": sorted(field_rows, key=lambda item: item["non_empty_count"], reverse=True)[:120],
            "ignored_or_generic_fields_with_possible_morphology": [
                {"field": key, "count": int(count), "examples": craft_field_examples.get(key, [])}
                for key, count in craft_field_scores.most_common(120)
                if key.startswith(f"{source}.")
            ][:50],
            "ignored_or_generic_fields_with_metadata_value": [
                {"field": key, "count": int(count), "examples": metadata_field_examples.get(key, [])}
                for key, count in metadata_field_scores.most_common(120)
                if key.startswith(f"{source}.")
            ][:50],
            "samples": source_samples[source],
        }

    ignored_hit_upper = sum(craft_field_scores.values())
    metadata_hit_upper = sum(metadata_field_scores.values())
    source_code_upper = sum(source_code_values.values())
    unresolved = int(totals["unresolved_unknowns"])
    dedupe_direct = int(totals["unresolved_unknowns_with_duplicate_member_direct_morphology"])
    recovery_estimate = {
        "craft_type_recovery_possible_by_using_ignored_or_generic_fields_upper_bound_hits": int(ignored_hit_upper),
        "craft_type_recovery_possible_by_improving_dedupe_evidence_preservation": dedupe_direct,
        "craft_type_recovery_possible_only_with_external_source_codebooks_upper_bound": int(source_code_upper),
        "metadata_only_gain_possible_from_ignored_fields_upper_bound_hits": int(metadata_hit_upper),
        "genuinely_unclassifiable_lower_bound_after_available_evidence": int(max(0, unresolved - ignored_hit_upper - dedupe_direct)),
        "note": "Upper-bound hit counts can double-count events across fields; use as opportunity sizing, not exact recoverable-event counts.",
    }

    report = {
        "schema_version": 1,
        "read_only": True,
        "guardrails": {
            "parser_code_modified": False,
            "canonical_web_rebuilt": False,
            "static_bundle_restaged": False,
            "cloudflare_or_r2_touched": False,
            "git_used": False,
            "direct_craft_type_inferred_changed": False,
        },
        "input": str(INPUT),
        "method": {
            "unknown_basis": "app-facing unknown via parser.taxonomy plus current parser craft_type_inferred == unknown",
            "parser_explicit_fields": sorted(PARSER_EXPLICIT_FIELDS),
            "parser_generic_scan_note": PARSER_GENERIC_NOTE,
            "weak_terms_policy": "vague words alone were not counted as direct craft-shape recovery evidence",
        },
        "summary": {
            "events_scanned": int(totals["events_scanned"]),
            "unresolved_unknowns_audited": unresolved,
            "unresolved_unknowns_with_duplicate_member_metadata": int(totals["unresolved_unknowns_with_duplicate_member_metadata"]),
            "unresolved_unknowns_with_duplicate_member_direct_morphology": dedupe_direct,
            "raw_fields_unique_keys": len(raw_field_rows),
            "raw_source_row_only_unique_keys": len(raw_source_only_rows),
            "raw_source_row_morphology_hits_not_in_raw_fields": int(sum(raw_source_morph_missing.values())),
            "raw_source_row_metadata_hits_not_in_raw_fields": int(sum(raw_source_meta_missing.values())),
        },
        "counts_by_source": {source: dict(counter) for source, counter in sorted(source_counts.items())},
        "raw_field_inventory": raw_field_rows,
        "raw_source_row_only_inventory": raw_source_only_rows,
        "source_specific_field_coverage": source_specific,
        "upstream_source_artifact_comparison": {
            "source_files_found": source_file_candidates(),
            "raw_source_row_preservation_note": "Canonical rows preserve source-row content in raw_source_row. Fields absent from raw_fields are preserved but not included in the parser raw_fields generic scan unless copied or explicitly scanned.",
            "top_raw_source_row_fields_not_in_raw_fields": counter_rows(raw_source_missing, 50),
            "top_morphology_fields_preserved_only_in_raw_source_row": counter_rows(raw_source_morph_missing, 50),
            "top_metadata_fields_preserved_only_in_raw_source_row": counter_rows(raw_source_meta_missing, 50),
        },
        "deduplication_evidence_preservation": {
            "unresolved_unknowns_with_duplicate_member_metadata": int(totals["unresolved_unknowns_with_duplicate_member_metadata"]),
            "source_provenance_members_for_those_events": int(provenance_member_total),
            "raw_member_scan_summary": raw_member_scan_summary,
            "unresolved_unknowns_where_raw_duplicate_member_has_direct_morphology": dedupe_direct,
            "examples_canonical_unknown_but_member_has_shape_evidence": duplicate_examples,
            "limitation": "Duplicate groups preserve provenance IDs, not full member raw rows. Raw CSV row-number scan was used where source files were available.",
            "recommended_merge_improvements": [
                "Preserve compact merged_evidence_summary on canonical events with member shape/type/description evidence.",
                "Retain member morphology as review metadata when canonical representative is unknown.",
                "Keep per-member source snippets for source-native shape/code columns.",
            ],
        },
        "ignored_morphology_evidence": {
            "top_ignored_or_generic_fields_likely_to_improve_craft_type": [
                {"field": key, "hit_count": int(count), "examples": craft_field_examples.get(key, [])}
                for key, count in craft_field_scores.most_common(TOP_LIMIT)
            ],
            "top_candidate_morphology_phrase_locations": counter_rows(morphology_locations, TOP_LIMIT),
        },
        "non_morphology_usefulness": {
            "top_ignored_fields_likely_to_improve_metadata_unknown_reason": [
                {"field": key, "hit_count": int(count), "examples": metadata_field_examples.get(key, [])}
                for key, count in metadata_field_scores.most_common(TOP_LIMIT)
            ],
            "top_metadata_target_locations": counter_rows(metadata_locations, TOP_LIMIT),
        },
        "source_code_evidence_opportunities": {
            "top_source_code_values": [
                {"code": key, "count": int(count), "examples": source_code_examples.get(key, [])}
                for key, count in source_code_values.most_common(TOP_LIMIT)
            ],
            "external_codebooks_needed": [
                "UFOCAT full TYPE codebook and subcode semantics",
                "UFOCAT SHAPE value definitions beyond direct morphology labels",
                "UFOCAT HYNEK and VALLEE classification documentation",
                "UPDB/phenomenAInon source template/code definitions",
                "MUFON historical shape/category export definitions",
                "NUFORC shape and characteristics taxonomy notes",
                "Majestic collection field/code documentation",
            ],
        },
        "recovery_estimate": recovery_estimate,
        "ranked_recommendations": {
            "top_25_ignored_fields_likely_to_improve_craft_type": [
                {"field": key, "hit_count": int(count), "examples": craft_field_examples.get(key, [])}
                for key, count in craft_field_scores.most_common(TOP_LIMIT)
            ],
            "top_25_ignored_fields_likely_to_improve_metadata_unknown_reason": [
                {"field": key, "hit_count": int(count), "examples": metadata_field_examples.get(key, [])}
                for key, count in metadata_field_scores.most_common(TOP_LIMIT)
            ],
            "top_25_dedupe_evidence_preservation_opportunities": duplicate_examples[:TOP_LIMIT],
            "top_10_external_source_files_or_codebooks_needed": [
                "data/reports/ufocat_codebook_extract/UFOCAT Codebook 2023.txt",
                "UFOCAT original codebook/source notes for TYPE/SHAPE/HYNEK/VALLEE",
                "UFO Databases/phenomenAInon_UPDB.csv source schema notes",
                "UFO Databases/mufon.csv and mufonpy.csv shape/category schema notes",
                "UFO Databases/nuforc.csv and nuforcpy.csv NUFORC taxonomy notes",
                "UFO Databases/majestic.csv and sources/majestic.json schema notes",
                "Any UPDB imported-source mapping table",
                "Any MUFON multilingual shape dictionary",
                "Any UFOCAT source-native morphology-value list",
                "Any prior dedupe member-evidence audit output",
            ],
            "recommended_next_implementation_slice": [
                "Add a canonical merged_evidence_summary field/report in a controlled rebuild slice, not a broad parser-regex slice.",
                "Review raw_source_row-only morphology fields and decide whether to copy them into raw_fields or explicitly scan them.",
                "Prioritize duplicate member morphology preservation because that is real representative-selection evidence loss, not missing source evidence.",
            ],
        },
        "blunt_assessment": "The remaining unknowns are mostly genuinely missing direct craft-shape evidence, but there is measurable preserved-only/ignored evidence and dedupe representative loss. The biggest safe gains are metadata/unknown_reason enrichment and dedupe evidence preservation, not broad new craft-type regexes.",
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(report)
    print(json.dumps({
        "ok": True,
        "outputs": {"markdown": str(OUT_MD), "json": str(OUT_JSON)},
        "summary": report["summary"],
        "recovery_estimate": report["recovery_estimate"],
        "top_craft_fields": report["ranked_recommendations"]["top_25_ignored_fields_likely_to_improve_craft_type"][:5],
        "top_metadata_fields": report["ranked_recommendations"]["top_25_ignored_fields_likely_to_improve_metadata_unknown_reason"][:5],
    }, indent=2))


def write_markdown(report: dict[str, Any]) -> None:
    lines = [
        "# Craft Unknown Evidence Preservation Audit",
        "",
        "Read-only audit. No parser code, canonical web artifacts, static bundles, Cloudflare/R2 artifacts, preview, deployment, or direct craft type values were changed.",
        "",
        "## Summary",
        "",
    ]
    s = report["summary"]
    lines.extend([
        f"- Events scanned: `{s['events_scanned']:,}`",
        f"- App-facing unresolved craft-type unknowns audited: `{s['unresolved_unknowns_audited']:,}`",
        f"- Unique raw_fields keys present: `{s['raw_fields_unique_keys']:,}`",
        f"- Unique raw_source_row-only keys present: `{s['raw_source_row_only_unique_keys']:,}`",
        f"- Unresolved unknowns with duplicate/source-member metadata: `{s['unresolved_unknowns_with_duplicate_member_metadata']:,}`",
        f"- Unresolved unknowns where a raw duplicate member has direct morphology evidence: `{s['unresolved_unknowns_with_duplicate_member_direct_morphology']:,}`",
        f"- Raw-source-row-only morphology hits not in raw_fields: `{s['raw_source_row_morphology_hits_not_in_raw_fields']:,}`",
        f"- Raw-source-row-only metadata hits not in raw_fields: `{s['raw_source_row_metadata_hits_not_in_raw_fields']:,}`",
        "",
        "## Counts By Source",
        "",
    ])
    for source, counter in sorted(report["counts_by_source"].items(), key=lambda item: item[1].get("unresolved_unknowns", 0), reverse=True):
        lines.append(f"- `{source}`: `{counter.get('unresolved_unknowns', 0):,}` unresolved unknowns")
    lines.extend([
        "",
        "## Parser Field Handling",
        "",
        "- Explicit parser fields: `" + "`, `".join(report["method"]["parser_explicit_fields"]) + "`.",
        f"- Generic raw field behavior: {report['method']['parser_generic_scan_note']}",
        "- Fields present only in `raw_source_row` are preserved in canonical rows but are not included in the parser generic `raw_fields` scan.",
        "",
        "## Top Ignored / Generic Fields Likely To Improve Craft Type",
        "",
        "| Rank | Field | Hit Count | Example |",
        "|---:|---|---:|---|",
    ])
    for index, item in enumerate(report["ranked_recommendations"]["top_25_ignored_fields_likely_to_improve_craft_type"], start=1):
        examples = item.get("examples") or []
        example = (examples[0].get("value") or "").replace("|", "\\|")[:140] if examples else ""
        lines.append(f"| {index} | `{item['field']}` | `{item['hit_count']:,}` | {example} |")
    lines.extend([
        "",
        "## Top Ignored / Generic Fields Likely To Improve Metadata",
        "",
        "| Rank | Field | Hit Count | Example Targets |",
        "|---:|---|---:|---|",
    ])
    for index, item in enumerate(report["ranked_recommendations"]["top_25_ignored_fields_likely_to_improve_metadata_unknown_reason"], start=1):
        examples = item.get("examples") or []
        targets = ", ".join(examples[0].get("metadata_targets", [])) if examples else ""
        lines.append(f"| {index} | `{item['field']}` | `{item['hit_count']:,}` | {targets} |")
    d = report["deduplication_evidence_preservation"]
    lines.extend([
        "",
        "## Dedupe / Evidence Preservation",
        "",
        f"- Unresolved unknowns with duplicate/source-member metadata: `{d['unresolved_unknowns_with_duplicate_member_metadata']:,}`",
        f"- Source provenance members for those events: `{d['source_provenance_members_for_those_events']:,}`",
        f"- Canonical unknowns where a raw duplicate member has direct morphology evidence: `{d['unresolved_unknowns_where_raw_duplicate_member_has_direct_morphology']:,}`",
        "",
        "### Example Canonical Unknown But Member Has Shape Evidence",
        "",
    ])
    for ex in d["examples_canonical_unknown_but_member_has_shape_evidence"][:8]:
        member = (ex.get("member_evidence") or [{}])[0]
        lines.append(f"- `{ex.get('canonical_event_id')}` member `{member.get('canonical_input_id')}` row `{member.get('source_file')}:{member.get('source_row_number')}` -> `{', '.join(member.get('morphology_buckets', []))}`")
    lines.extend(["", "## Recovery Estimate", ""])
    for key, value in report["recovery_estimate"].items():
        if key == "note":
            lines.append(f"- Note: {value}")
        else:
            lines.append(f"- `{key}`: `{value:,}`")
    lines.extend(["", "## External Codebooks / Source Files Needed", ""])
    for item in report["ranked_recommendations"]["top_10_external_source_files_or_codebooks_needed"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Recommended Next Implementation Slice", ""])
    for item in report["ranked_recommendations"]["recommended_next_implementation_slice"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Blunt Assessment", "", report["blunt_assessment"], "", "More detail is available in the JSON report, especially `raw_field_inventory`, `source_specific_field_coverage`, `upstream_source_artifact_comparison`, and `deduplication_evidence_preservation`."])
    OUT_MD.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
