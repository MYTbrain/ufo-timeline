"""Audit description/evidence coverage for remaining unresolved craft Unknowns.

This report is intentionally read-only. It does not change parser rules,
canonical artifacts, static bundles, Cloudflare bundles, or deployment state.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser.craft_types import infer_event_craft_type, is_unknownish, normalize_text
from parser.taxonomy import display_type_for_web_event, visual_type_group_for_web_event


DEFAULT_INPUT = Path("data/canonical_full_maximal_v3_rehydrated_jurisdiction_repair/deduped_events.jsonl")
DEFAULT_OUTPUT_MD = Path("data/reports/remaining_unknown_description_coverage_audit.md")
DEFAULT_OUTPUT_JSON = Path("data/reports/remaining_unknown_description_coverage_audit.json")

SAMPLE_LIMIT = 5
TOP_LIMIT = 25

DESCRIPTION_FIELD_HINT_RE = re.compile(
    r"(description|desc|summary|narrative|comment|comments|note|notes|text|story|account|report|"
    r"statement|testimony|detail|details|observation|sighting|case)",
    re.I,
)
MORPHOLOGY_CODE_FIELD_HINT_RE = re.compile(
    r"(shape|type|hynek|vallee|vall[ée]e|class|classification|category|characteristics|"
    r"object|objects|form|morph|body|appearance|phenomen|color|movement|uniform)",
    re.I,
)
NOISE_FIELD_HINT_RE = re.compile(
    r"(^id$|record|row|hash|source|file|author|date|time|year|month|day|lat|lon|lng|"
    r"location|city|state|country|duration|witness|observer|url|page|volume|prn|urn|level|x2)",
    re.I,
)

POSSIBLE_MORPHOLOGY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("disc/saucer phrase", re.compile(r"\b(?:saucer[- ]?shaped|disc[- ]?shaped|disk[- ]?shaped|lenticular|discoid(?:al)?)\b", re.I)),
    ("cigar/cylinder phrase", re.compile(r"\b(?:cigar[- ]?shaped|cigar[- ]?like|cylindrical|cylinder[- ]?shaped|tube[- ]?shaped|fusiform)\b", re.I)),
    ("triangle phrase", re.compile(r"\b(?:triangular|triangle[- ]?shaped|delta[- ]?shaped|black triangle)\b", re.I)),
    ("sphere/orb phrase", re.compile(r"\b(?:spherical|sphere[- ]?shaped|orb[- ]?like|ball[- ]?shaped|globe[- ]?shaped)\b", re.I)),
    ("oval/egg phrase", re.compile(r"\b(?:oval[- ]?shaped|egg[- ]?shaped|elliptical|football[- ]?shaped)\b", re.I)),
    ("chevron/boomerang phrase", re.compile(r"\b(?:chevron[- ]?shaped|boomerang[- ]?shaped|v[- ]?shaped|vee[- ]?shaped|crescent[- ]?shaped)\b", re.I)),
    ("rectangle/box phrase", re.compile(r"\b(?:rectangular|rectangle[- ]?shaped|box[- ]?shaped|cube[- ]?shaped|square[- ]?shaped)\b", re.I)),
    ("cone/pyramid phrase", re.compile(r"\b(?:cone[- ]?shaped|conical|pyramid[- ]?shaped)\b", re.I)),
    ("diamond phrase", re.compile(r"\b(?:diamond[- ]?shaped|lozenge[- ]?shaped)\b", re.I)),
    ("teardrop phrase", re.compile(r"\b(?:tear[- ]?drop[- ]?shaped|teardrop[- ]?shaped)\b", re.I)),
    ("dumbbell/barbell phrase", re.compile(r"\b(?:dumbbell[- ]?shaped|barbell[- ]?shaped)\b", re.I)),
    ("formation phrase", re.compile(r"\b(?:formation of|line of lights|string of lights|row of lights|fleet of|cluster of)\b", re.I)),
    ("cloud-like phrase", re.compile(r"\b(?:cloud[- ]?like|cloud[- ]?shaped)\b", re.I)),
    ("aircraft/helicopter phrase", re.compile(r"\b(?:aircraft[- ]?like|helicopter[- ]?like|copter[- ]?like|plane[- ]?like)\b", re.I)),
]
PHOTO_CONTEXT_RE = re.compile(
    r"\b(?:photo|photograph|picture|camera|video|film|negative|slide|radar|instrument|sensor|"
    r"telescope|scope|madar|lens|image artifact|camera artifact)\b",
    re.I,
)
ENTITY_CONTEXT_RE = re.compile(
    r"\b(?:entity|entities|being|beings|occupant|occupants|humanoid|creature|abduction|abducted|"
    r"contactee|close encounter|ce[ -]?[2345])\b",
    re.I,
)
PROSAIC_CONTEXT_RE = re.compile(
    r"\b(?:aircraft|airplane|aeroplane|plane|helicopter|balloon|weather balloon|kite|bird|drone|"
    r"satellite|starlink|venus|mars|moon|meteor|bolide|rocket|flare|hoax|misidentification|"
    r"identified as|explained as|probably)\b",
    re.I,
)
VAGUE_ONLY_RE = re.compile(
    r"\b(?:object|objects|thing|things|craft|ufo|uap|light|lights|glow|aura|trail|round|"
    r"metallic|silver|bright|dark|moving|stationary)\b",
    re.I,
)


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path} line {line_number}: invalid JSON: {exc}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number}: expected object")
            yield payload


def source_key(event: dict[str, Any]) -> str:
    return normalize_text(event.get("source_name")).lower() or "unknown"


def event_id(event: dict[str, Any]) -> str:
    return normalize_text(event.get("canonical_event_id") or event.get("event_id"))


def is_app_facing_unknown(event: dict[str, Any]) -> bool:
    if display_type_for_web_event(event) is None:
        return True
    return visual_type_group_for_web_event(event) == "Other / unknown"


def is_remaining_unresolved_unknown(event: dict[str, Any]) -> bool:
    if not is_app_facing_unknown(event):
        return False
    inference = infer_event_craft_type(event)
    return inference.get("craft_type_inferred") == "unknown"


def raw_dict(event: dict[str, Any], key: str) -> dict[str, Any]:
    value = event.get(key)
    return value if isinstance(value, dict) else {}


def raw_field_items(event: dict[str, Any]) -> list[tuple[str, Any]]:
    items: list[tuple[str, Any]] = []
    for parent_key in ("raw_fields", "raw_source_row"):
        raw = raw_dict(event, parent_key)
        for key, value in raw.items():
            items.append((f"{parent_key}.{key}", value))
    return items


def text_value(value: Any) -> str:
    text = normalize_text(value)
    if is_unknownish(text):
        return ""
    return text


def description_fields(event: dict[str, Any]) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    for key in ("description", "summary"):
        value = text_value(event.get(key))
        if value:
            fields.append((key, value))
    for key, value in raw_field_items(event):
        leaf_key = key.split(".", 1)[1]
        if DESCRIPTION_FIELD_HINT_RE.search(leaf_key):
            text = text_value(value)
            if text:
                fields.append((key, text))
    return dedupe_pairs(fields)


def morphology_fields(event: dict[str, Any]) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    for key in ("shape_raw", "shape_normalized", "type_raw", "type_normalized"):
        value = text_value(event.get(key))
        if value:
            fields.append((key, value))
    for key, value in raw_field_items(event):
        leaf_key = key.split(".", 1)[1]
        if MORPHOLOGY_CODE_FIELD_HINT_RE.search(leaf_key) and not NOISE_FIELD_HINT_RE.search(leaf_key):
            text = text_value(value)
            if text:
                fields.append((key, text))
    return dedupe_pairs(fields)


def source_code_fields(event: dict[str, Any]) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    for key, value in raw_field_items(event):
        leaf = key.split(".", 1)[1]
        if re.fullmatch(r"(TYPE|SHAPE|HYNEK|VALLEE|VALL[ÉE]E|Class|Classification|Category|Characteristics)", leaf, re.I):
            text = text_value(value)
            if text:
                fields.append((key, text))
    return dedupe_pairs(fields)


def dedupe_pairs(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    output: list[tuple[str, str]] = []
    for key, value in pairs:
        signature = (key, value)
        if signature in seen:
            continue
        seen.add(signature)
        output.append((key, value))
    return output


def text_blob(pairs: list[tuple[str, str]]) -> str:
    return " ".join(value for _, value in pairs)


def possible_morphology_hits(text: str) -> list[str]:
    hits: list[str] = []
    for label, pattern in POSSIBLE_MORPHOLOGY_PATTERNS:
        for match in pattern.finditer(text):
            phrase = normalize_text(match.group(0)).lower()
            if phrase:
                hits.append(f"{label}: {phrase}")
    return hits


def classify_flags(event: dict[str, Any]) -> dict[str, Any]:
    desc = description_fields(event)
    morph = morphology_fields(event)
    source_codes = source_code_fields(event)
    desc_text = text_blob(desc)
    all_evidence_text = " ".join([desc_text, text_blob(morph)])
    morphology_hits = possible_morphology_hits(all_evidence_text)
    has_vague_only_text = bool(desc_text and VAGUE_ONLY_RE.search(desc_text) and not morphology_hits)
    return {
        "description_fields": desc,
        "morphology_fields": morph,
        "source_code_fields": source_codes,
        "has_description_like_text": bool(desc),
        "description_empty_or_null": not text_value(event.get("description")),
        "summary_empty_or_null": not text_value(event.get("summary")),
        "no_shape_raw_or_normalized": not text_value(event.get("shape_raw")) and not text_value(event.get("shape_normalized")),
        "no_type_raw_or_normalized": not text_value(event.get("type_raw")) and not text_value(event.get("type_normalized")),
        "no_useful_raw_fields_morphology_or_code": not morph and not source_codes,
        "some_description_text_no_morphology_terms": bool(desc_text) and not morphology_hits,
        "some_description_text_with_possible_morphology_terms": bool(desc_text) and bool(morphology_hits),
        "source_code_fields_requiring_decoding": bool(source_codes),
        "only_photo_video_camera_instrument_context": bool(all_evidence_text and PHOTO_CONTEXT_RE.search(all_evidence_text) and not morphology_hits),
        "only_entity_encounter_context": bool(all_evidence_text and ENTITY_CONTEXT_RE.search(all_evidence_text) and not morphology_hits),
        "only_prosaic_conventional_context": bool(all_evidence_text and PROSAIC_CONTEXT_RE.search(all_evidence_text) and not morphology_hits),
        "has_vague_only_text": has_vague_only_text,
        "possible_morphology_hits": morphology_hits,
        "description_text_sample": desc_text[:500],
        "morphology_text_sample": text_blob(morph)[:500],
    }


def add_sample(samples: dict[str, list[dict[str, Any]]], bucket: str, event: dict[str, Any], flags: dict[str, Any]) -> None:
    rows = samples.setdefault(bucket, [])
    if len(rows) >= SAMPLE_LIMIT:
        return
    rows.append({
        "canonical_event_id": event_id(event),
        "source_name": event.get("source_name"),
        "date_iso": event.get("date_iso"),
        "location_raw": event.get("location_raw"),
        "type_raw": event.get("type_raw"),
        "type_normalized": event.get("type_normalized"),
        "shape_raw": event.get("shape_raw"),
        "shape_normalized": event.get("shape_normalized"),
        "description_sample": flags.get("description_text_sample"),
        "morphology_or_code_sample": flags.get("morphology_text_sample"),
        "source_code_fields": flags.get("source_code_fields")[:8],
        "possible_morphology_hits": flags.get("possible_morphology_hits")[:8],
    })


def new_source_bucket() -> dict[str, Any]:
    return {
        "total_unresolved_unknown": 0,
        "flag_counts": Counter(),
        "estimate_counts": Counter(),
        "samples": defaultdict(list),
        "candidate_morphology_phrases": Counter(),
        "useful_raw_field_names": Counter(),
    }


def estimate_categories(flags: dict[str, Any]) -> list[str]:
    categories: list[str] = []
    if (
        not flags["has_description_like_text"]
        and flags["no_shape_raw_or_normalized"]
        and flags["no_type_raw_or_normalized"]
        and flags["no_useful_raw_fields_morphology_or_code"]
    ):
        categories.append("truly_unclassifiable_due_to_missing_text_fields")
    if flags["some_description_text_with_possible_morphology_terms"]:
        categories.append("potentially_classifiable_through_text_mining")
    if flags["source_code_fields_requiring_decoding"]:
        categories.append("potentially_classifiable_through_source_code_decoding")
    if (
        flags["only_photo_video_camera_instrument_context"]
        or flags["only_entity_encounter_context"]
        or flags["only_prosaic_conventional_context"]
        or flags["has_vague_only_text"]
    ):
        categories.append("metadata_only_not_craft_type_classifiable")
    if flags["some_description_text_no_morphology_terms"] and not categories:
        categories.append("manual_review_candidates")
    elif flags["some_description_text_no_morphology_terms"]:
        categories.append("manual_review_candidates")
    if not categories:
        categories.append("manual_review_candidates")
    return categories


def build_report(input_path: Path, *, limit: int | None = None) -> dict[str, Any]:
    totals = Counter()
    sources: dict[str, dict[str, Any]] = defaultdict(new_source_bucket)
    global_samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    global_candidate_phrases: Counter[str] = Counter()
    global_raw_field_names: Counter[str] = Counter()

    for index, event in enumerate(iter_jsonl(input_path), start=1):
        if limit is not None and index > limit:
            break
        totals["events_scanned"] += 1
        if not is_remaining_unresolved_unknown(event):
            continue

        totals["total_unresolved_unknown"] += 1
        source = source_key(event)
        bucket = sources[source]
        bucket["total_unresolved_unknown"] += 1
        flags = classify_flags(event)

        flag_keys = [
            "has_description_like_text",
            "description_empty_or_null",
            "summary_empty_or_null",
            "no_shape_raw_or_normalized",
            "no_type_raw_or_normalized",
            "no_useful_raw_fields_morphology_or_code",
            "some_description_text_no_morphology_terms",
            "some_description_text_with_possible_morphology_terms",
            "source_code_fields_requiring_decoding",
            "only_photo_video_camera_instrument_context",
            "only_entity_encounter_context",
            "only_prosaic_conventional_context",
        ]
        for key in flag_keys:
            if flags[key]:
                totals[key] += 1
                bucket["flag_counts"][key] += 1
                add_sample(bucket["samples"], key, event, flags)
                add_sample(global_samples, key, event, flags)

        for category in estimate_categories(flags):
            totals[category] += 1
            bucket["estimate_counts"][category] += 1
            add_sample(bucket["samples"], category, event, flags)
            add_sample(global_samples, category, event, flags)

        for hit in flags["possible_morphology_hits"]:
            global_candidate_phrases[hit] += 1
            bucket["candidate_morphology_phrases"][hit] += 1

        for key, value in flags["morphology_fields"] + flags["source_code_fields"]:
            if value:
                global_raw_field_names[key] += 1
                bucket["useful_raw_field_names"][key] += 1

    source_rows: list[dict[str, Any]] = []
    for source, bucket in sources.items():
        total = int(bucket["total_unresolved_unknown"])
        if total <= 0:
            continue
        source_rows.append({
            "source_name": source,
            "total_unresolved_unknown": total,
            "counts": {key: int(value) for key, value in bucket["flag_counts"].most_common()},
            "estimates": {key: int(value) for key, value in bucket["estimate_counts"].most_common()},
            "top_candidate_morphology_phrases": dict(bucket["candidate_morphology_phrases"].most_common(TOP_LIMIT)),
            "top_useful_raw_field_names": dict(bucket["useful_raw_field_names"].most_common(TOP_LIMIT)),
            "examples_by_bucket": {key: value for key, value in bucket["samples"].items()},
        })
    source_rows.sort(key=lambda row: row["total_unresolved_unknown"], reverse=True)

    ranked = {
        "sources_with_most_missing_description_unresolved_unknowns": rank_sources(source_rows, "has_description_like_text", invert=True),
        "sources_with_most_text_present_but_no_morphology": rank_sources(source_rows, "some_description_text_no_morphology_terms"),
        "sources_with_most_source_code_decoding_opportunities": rank_sources(source_rows, "source_code_fields_requiring_decoding"),
        "sources_with_most_possible_morphology_phrase_opportunities": rank_sources(source_rows, "some_description_text_with_possible_morphology_terms"),
        "top_25_candidate_morphology_phrases": dict(global_candidate_phrases.most_common(TOP_LIMIT)),
        "top_25_raw_field_names_with_classification_evidence": dict(global_raw_field_names.most_common(TOP_LIMIT)),
    }

    return {
        "schema_version": 1,
        "analysis_policy": "read_only_remaining_unknown_description_coverage_no_parser_changes",
        "canonical_outputs_mutated": False,
        "inputs": {"events_jsonl": str(input_path), "limit": limit},
        "summary": {
            "events_scanned": int(totals["events_scanned"]),
            "total_unresolved_unknown": int(totals["total_unresolved_unknown"]),
            "counts": {
                key: int(totals[key])
                for key in [
                    "has_description_like_text",
                    "description_empty_or_null",
                    "summary_empty_or_null",
                    "no_shape_raw_or_normalized",
                    "no_type_raw_or_normalized",
                    "no_useful_raw_fields_morphology_or_code",
                    "some_description_text_no_morphology_terms",
                    "some_description_text_with_possible_morphology_terms",
                    "source_code_fields_requiring_decoding",
                    "only_photo_video_camera_instrument_context",
                    "only_entity_encounter_context",
                    "only_prosaic_conventional_context",
                ]
            },
            "estimates": {
                key: int(totals[key])
                for key in [
                    "truly_unclassifiable_due_to_missing_text_fields",
                    "potentially_classifiable_through_text_mining",
                    "potentially_classifiable_through_source_code_decoding",
                    "metadata_only_not_craft_type_classifiable",
                    "manual_review_candidates",
                ]
            },
            "note": "Counts are overlapping evidence flags unless explicitly labeled as estimates. Estimate categories can also overlap because a row may have source codes plus narrative text.",
        },
        "count_by_source": {
            row["source_name"]: row["total_unresolved_unknown"] for row in source_rows
        },
        "sources": source_rows,
        "ranked_tables": ranked,
        "global_examples_by_bucket": {key: value for key, value in global_samples.items()},
        "recommended_next_strategy": build_recommendation(totals, source_rows, ranked),
    }


def rank_sources(source_rows: list[dict[str, Any]], key: str, *, invert: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in source_rows:
        if invert:
            count = row["total_unresolved_unknown"] - int(row["counts"].get(key, 0))
        else:
            count = int(row["counts"].get(key, 0))
        if count:
            rows.append({"source_name": row["source_name"], "count": count, "total_unresolved_unknown": row["total_unresolved_unknown"]})
    rows.sort(key=lambda item: item["count"], reverse=True)
    return rows[:TOP_LIMIT]


def build_recommendation(totals: Counter[str], source_rows: list[dict[str, Any]], ranked: dict[str, Any]) -> list[str]:
    recommendations = [
        "Keep parser changes source-specific. The remaining Unknown pool is dominated by rows where evidence is absent, coded, or metadata-only.",
        "Do not add broad regex rules for vague terms; use the phrase/opportunity report only as a review queue.",
    ]
    source_code_rows = ranked.get("sources_with_most_source_code_decoding_opportunities") or []
    if source_code_rows:
        top = source_code_rows[0]
        recommendations.append(
            f"Next highest-leverage parser work is source-code decoding for `{top['source_name']}` "
            f"({top['count']:,} unresolved rows with code/classification fields)."
        )
    morphology_rows = ranked.get("sources_with_most_possible_morphology_phrase_opportunities") or []
    if morphology_rows:
        top = morphology_rows[0]
        recommendations.append(
            f"Second path is a narrow manual-review text-mining slice for `{top['source_name']}` "
            f"({top['count']:,} unresolved rows with possible explicit morphology phrases)."
        )
    missing = int(totals["truly_unclassifiable_due_to_missing_text_fields"])
    if missing:
        recommendations.append(
            f"Treat about {missing:,} rows as data-coverage problems first; parser changes cannot classify them without added source text/codebooks."
        )
    return recommendations


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    summary = report["summary"]
    lines: list[str] = [
        "# Remaining Unknown Description Coverage Audit",
        "",
        "Read-only audit. No parser code, canonical web artifacts, static bundles, Cloudflare/R2 artifacts, or deployment state were changed.",
        "",
        "## Counting Basis",
        "",
        "- Basis: app-facing source/UI Unknown rows that still infer to `craft_type_inferred=unknown` under the current accepted parser state.",
        f"- Events scanned: `{summary['events_scanned']:,}`",
        f"- Total unresolved unknown count: `{summary['total_unresolved_unknown']:,}`",
        f"- Note: {summary['note']}",
        "",
        "## Global Coverage Counts",
        "",
    ]
    for key, count in summary["counts"].items():
        lines.append(f"- `{key}`: `{count:,}`")
    lines.extend(["", "## Global Estimates", ""])
    for key, count in summary["estimates"].items():
        lines.append(f"- `{key}`: `{count:,}`")
    lines.extend(["", "## Count By Source", ""])
    for source, count in report["count_by_source"].items():
        lines.append(f"- `{source}`: `{count:,}`")

    tables = report["ranked_tables"]
    append_ranked_table(lines, "Sources With Most Missing-Description Unresolved Unknowns", tables["sources_with_most_missing_description_unresolved_unknowns"])
    append_ranked_table(lines, "Sources With Most Text Present But No Morphology", tables["sources_with_most_text_present_but_no_morphology"])
    append_ranked_table(lines, "Sources With Most Source-Code-Decoding Opportunities", tables["sources_with_most_source_code_decoding_opportunities"])
    append_ranked_table(lines, "Sources With Most Possible Morphology Phrase Opportunities", tables["sources_with_most_possible_morphology_phrase_opportunities"])

    lines.extend(["", "## Top 25 Candidate Morphology Phrases Still Present", ""])
    for phrase, count in tables["top_25_candidate_morphology_phrases"].items():
        lines.append(f"- `{phrase}`: `{count:,}`")
    lines.extend(["", "## Top 25 Raw Field Names With Classification Evidence", ""])
    for field, count in tables["top_25_raw_field_names_with_classification_evidence"].items():
        lines.append(f"- `{field}`: `{count:,}`")

    lines.extend(["", "## Per-Source Summary", ""])
    for row in report["sources"][:12]:
        lines.extend(["", f"### {row['source_name']}", ""])
        lines.append(f"- Total unresolved unknown: `{row['total_unresolved_unknown']:,}`")
        for key, count in row["counts"].items():
            lines.append(f"- `{key}`: `{count:,}`")
        lines.append("- Estimates: " + ", ".join(f"`{key}` `{value:,}`" for key, value in row["estimates"].items()))
        if row["top_candidate_morphology_phrases"]:
            lines.append("- Top possible morphology phrases: " + ", ".join(
                f"`{key}` (`{value:,}`)" for key, value in list(row["top_candidate_morphology_phrases"].items())[:8]
            ))
        if row["top_useful_raw_field_names"]:
            lines.append("- Top useful raw fields: " + ", ".join(
                f"`{key}` (`{value:,}`)" for key, value in list(row["top_useful_raw_field_names"].items())[:8]
            ))

    lines.extend(["", "## Recommended Next Strategy", ""])
    for item in report["recommended_next_strategy"]:
        lines.append(f"- {item}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def append_ranked_table(lines: list[str], title: str, rows: list[dict[str, Any]]) -> None:
    lines.extend(["", f"## {title}", "", "| Rank | Source | Count | Total Unresolved |", "|---:|---|---:|---:|"])
    for index, row in enumerate(rows[:TOP_LIMIT], start=1):
        lines.append(
            f"| {index} | `{row['source_name']}` | `{row['count']:,}` | `{row['total_unresolved_unknown']:,}` |"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(args.input, limit=args.limit)
    write_json(args.output_json, report)
    write_markdown(args.output_md, report)
    print(json.dumps({
        "ok": True,
        "outputs": {
            "markdown": str(args.output_md),
            "json": str(args.output_json),
        },
        "summary": report["summary"],
        "top_sources": list(report["count_by_source"].items())[:8],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
