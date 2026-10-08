"""Read-only audit of served source clocks and narrative timing opportunities.

No corpus is copied or mutated. Existing corrected clock dictionary and small
catalog summary shards are joined in memory. Full details are read one protected
chunk at a time. Narrative candidates are review leads, never accepted clocks.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re
import time


DEFAULT_ROOT = Path(r"C:/Users/jarod/Desktop/UFO Timeline map tool")
CLOCK_TEXT = r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<ampm>[ap])\.?\s*m\.?"
MENTION = re.compile(r"(?<![\d:])" + CLOCK_TEXT + r"(?!\w)", re.I)
LEADING = re.compile(r"^\s*(?:(?P<qualifier>at|about|around|approximately|approx\.?)\s+)?" + CLOCK_TEXT, re.I)
EVENT_VERBS = re.compile(r"\b(?:saw|see|sees|seen|observed|observe|observes|sighted|spotted|watched|watching|noticed|encountered|appeared|appears|landed|landing|hovered|hovering|witnessed)\b", re.I)
REPORT_VERBS = re.compile(r"\b(?:reported|reporting|telephoned|called|interviewed|interview|received|submitted|submission|posted|published|publication)\b", re.I)
MULTI_EVENT = re.compile(r"\b(?:another account|parallel incident|another incident|different incident|previous day|next day|following day|days earlier|days later)\b", re.I)
APPROXIMATE = re.compile(r"\b(?:about|around|approximately|approx|roughly|circa|estimated)\b|[?~]", re.I)


def read_json(path: Path):
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def pin(path: Path) -> dict:
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha(path)}


def clocks(text: str):
    return [m for m in MENTION.finditer(text) if 1 <= int(m.group("hour")) <= 12 and int(m.group("minute") or 0) <= 59]


def compact_example(event: dict, *, narrative: bool = False) -> dict:
    keys = ["event_id", "canonical_event_id", "source", "source_id", "source_row_number", "time_raw", "sort_date_iso", "date_iso", "date_precision", "location_raw", "chunk_id", "detail_index"]
    value = {k: event.get(k) for k in keys if k in event}
    if narrative:
        text = str(event.get("description") or event.get("summary") or "")
        match = LEADING.match(text)
        value["narrative_leading_clock"] = match.group(0).strip() if match else ""
        value["description_excerpt"] = text[:700]
        value["evidence_status"] = "review_lead_only_not_an_accepted_clock"
    return value


def audit(root: Path, skip_narrative: bool = False) -> dict:
    started = time.monotonic()
    repairs = root / "data/research/analysis-repairs-20261007"
    attribute = repairs / "attributes/analysis_time_of_day_v1"
    manifest_path = attribute / "manifest.json"
    dictionary_path = attribute / "time_of_day_value_dictionary_v1.json.gz"
    manifest = read_json(manifest_path)
    values = read_json(dictionary_path)
    dictionary = {(manifest["codes"]["source"][v[0]], v[2]): v for v in values}
    totals, kinds, forms = Counter(), Counter(), Counter()
    sources = defaultdict(Counter)
    examples = {}
    summaries = sorted((repairs / "catalog/summary_shards").glob("*.gz"))
    summary_pins = []
    for path in summaries:
        summary_pins.append(pin(path))
        for event in read_json(path):
            totals["catalog_rows"] += 1
            source, raw = event.get("source", "unknown"), event.get("time_raw", "")
            kind = event.get("time_sort_kind", "unknown")
            kinds[kind] += 1
            value = dictionary.get((source, raw))
            status = manifest["codes"]["status"][value[3]] if value else "empty_or_not_in_dictionary"
            sources[source][status] += 1
            if status == "exact_clock":
                totals["typed_exact_rows"] += 1
                if kind == "unknown":
                    totals["typed_exact_legacy_unknown_rows"] += 1
                    sources[source]["typed_exact_legacy_unknown_rows"] += 1
                    exact_day, mapped = event.get("date_precision") == "exact_day", bool(event.get("has_coordinates"))
                    if exact_day:
                        totals["typed_exact_legacy_unknown_exact_day_rows"] += 1
                    if mapped:
                        totals["typed_exact_legacy_unknown_mapped_rows"] += 1
                    if exact_day and mapped:
                        totals["typed_exact_legacy_unknown_exact_day_mapped_rows"] += 1
                    form = "bare_HHMM" if re.fullmatch(r"\d{4}", raw) else "seconds_colon" if re.fullmatch(r"\d{1,2}:\d{2}:\d{2}(?:\.\d+)?", raw) else "local_label" if re.search(r"local", raw, re.I) else "other"
                    forms[form] += 1
                    examples.setdefault(form, compact_example(event))
            if status == "sentinel_ambiguous" and kind in {"exact", "approximate"}:
                totals["sentinel_rows_with_legacy_exact_or_approximate_status"] += 1
                sources[source]["sentinel_rows_with_legacy_exact_or_approximate_status"] += 1

    narrative_counts, narrative_sources = Counter(), defaultdict(Counter)
    narrative_examples = defaultdict(list)
    requested_ids = {1365098095637797, 1548188833291382, 1527598470028955, 3478209486003715, 3972295816637808, 3225459898478069, 1880247488343365, 3448855352240391}
    case_evidence = []
    details = sorted((root / "data/canonical_web/event_chunks").glob("*.json"))
    if not skip_narrative:
        for path in details:
            for event in read_json(path):
                narrative_counts["detail_rows_read"] += 1
                if event.get("event_id") in requested_ids:
                    row = compact_example(event)
                    row["description"] = event.get("description")
                    row["legacy_time_evidence"] = {k: event.get(k) for k in ["time_sort_kind", "time_sort_confidence", "timezone_source", "parsed_time_local_minutes", "parsed_time_utc_epoch_ms"]}
                    case_evidence.append(row)
                raw = str(event.get("time_raw") or "").strip()
                if raw:
                    continue
                narrative_counts["missing_structured_clock_rows"] += 1
                text = str(event.get("description") or event.get("summary") or "")
                mentions = clocks(text)
                if not mentions:
                    continue
                narrative_counts["missing_structured_clock_with_ampm_mention_anywhere"] += 1
                leading = LEADING.match(text)
                if not leading or not 1 <= int(leading.group("hour")) <= 12 or int(leading.group("minute") or 0) > 59:
                    continue
                narrative_counts["missing_structured_clock_with_leading_ampm"] += 1
                tail = text[leading.end():]
                flags = []
                if len(mentions) > 1:
                    flags.append("multiple_clock_mentions")
                if MULTI_EVENT.search(text):
                    flags.append("multiple_event_or_relative_day_context")
                if REPORT_VERBS.search(tail[:150]):
                    flags.append("report_or_submission_context_near_clock")
                if APPROXIMATE.search(leading.group(0)):
                    flags.append("approximation_qualifier")
                if not EVENT_VERBS.search(tail[:250]):
                    flags.append("no_occurrence_verb_near_clock")
                if flags:
                    for flag in flags:
                        narrative_counts["leading_ampm_exclusion_" + flag] += 1
                    lane = "requires_context_review"
                else:
                    lane = "strong_leading_occurrence_clock_review_candidate"
                    narrative_counts[lane] += 1
                    if event.get("date_precision") == "exact_day":
                        narrative_counts[lane + "_exact_day"] += 1
                    if event.get("has_coordinates"):
                        narrative_counts[lane + "_mapped_original_detail"] += 1
                source = event.get("source", "unknown")
                narrative_sources[source][lane] += 1
                if len(narrative_examples[lane]) < 8:
                    row = compact_example(event, narrative=True)
                    row["exclusion_flags"] = flags
                    narrative_examples[lane].append(row)

    return {
        "audit_id": "trace-chronology-coverage-20261008-v1",
        "policy": {
            "raw_and_canonical_data_mutated": False,
            "full_corpus_copied": False,
            "typed_clock_status_is_source_clock_evidence_not_a_timezone": True,
            "typed_exact_counts_are_not_proven_utc_order_counts": True,
            "narrative_candidates_accepted_automatically": False,
            "noon_and_midnight_sentinels_excluded_from_exact_evidence": True,
            "summary_year_overrides_do_not_change_time_fields": True,
        },
        "inputs": {"typed_manifest": pin(manifest_path), "typed_dictionary": pin(dictionary_path), "summary_collection": summary_pins, "full_details": {"path": str((root / "data/canonical_web/event_chunks").resolve()), "files": len(details), "bytes_read_if_full_scan": sum(p.stat().st_size for p in details), "canonical_manifest": pin(root / "data/canonical_web/canonical_web_manifest.json"), "scope": "one shared protected chunk at a time; no rewritten or copied corpus"}},
        "clock_coverage": {"totals": dict(totals), "legacy_time_sort_kind_counts": dict(kinds), "ignored_exact_clock_forms": dict(forms), "by_source": {k: dict(v) for k, v in sources.items()}, "examples": examples},
        "narrative_review_leads": {"skipped": skip_narrative, "counts": dict(narrative_counts), "by_source": {k: dict(v) for k, v in narrative_sources.items()}, "examples": dict(narrative_examples), "criteria": "Missing structured clock, leading AM/PM time, one clock mention, occurrence verb nearby, no approximate prefix, nearby report/submission verb, or explicit cross-event/relative-day context. These remain manual-review leads; they are not certified event times."},
        "ariel_and_washington_source_evidence": case_evidence,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "storage": {"new_corpus_bytes": 0, "retained_inputs": "Existing canonical datasets and corrected clock dictionary; this small audit report is the canonical coverage evidence for this task."},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--skip-narrative", action="store_true")
    args = parser.parse_args()
    result = audit(args.root, args.skip_narrative)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(args.output), "bytes": args.output.stat().st_size, "elapsed_seconds": result["elapsed_seconds"], "clock_totals": result["clock_coverage"]["totals"], "narrative_counts": result["narrative_review_leads"]["counts"]}, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
