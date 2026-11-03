"""Admit conservative area-reference decisions without changing source/runtime.

The input candidate ledger remains review evidence. Every admitted decision is
guarded against the currently served summary and immutable original identity.
The GeoNames administrative feature is identity evidence. The retained coarse
country polygon is only a contradiction check, not independent authority.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import re

from scripts.recover_mapping_area_references import (
    DOCUMENTARY, NON_TERRESTRIAL, digest, json_lines, load_country_info, norm,
)


GUARD_FIELDS = ("source", "sort_date_iso", "location_raw", "lat", "lon",
                "coordinate_source", "location_precision", "has_coordinates")
IDENTITY_FIELDS = ("event_id", "canonical_event_id", "source_id", "chunk_id", "detail_index")
TRANSIT_OR_OFFSHORE = re.compile(
    r"\b(?:offshore|off[- ]shore|off (?:the )?coast|at sea|on (?:the )?(?:ocean|sea)|"
    r"aboard|on board|in[- ]flight|during (?:a |the )?flight|"
    r"(?:flying|flight|cruise|sailing|traveling|travelling|driving) from|"
    r"(?:aboard|on|in) (?:a |an |the )?(?:ship|boat|aircraft|airplane|aeroplane|jetliner)|"
    r"international waters|en route|enroute|flying over|sailors?|aircrew|"
    r"over (?:the )?(?:atlantic|pacific|indian ocean))\b", re.I)
DOCUMENTARY_EXTRA = re.compile(
    r"\b(?:newspaper office|publisher|press office|publishing house|witness address|"
    r"interview (?:with|at)|correspondence|letter (?:to|from)|"
    r"(?:radio|television|tv) interview|documentary film|fictional|novel entitled)\b", re.I)
PLACEHOLDER_SUBMISSION = re.compile(
    r"\b(?:test only|test report|dummy report|test submission|please disregard|"
    r"testing (?:this|the) (?:form|system|website))\b", re.I)
OBSERVATION_CONTEXT = re.compile(
    r"\b(?:ufos?|uaps?|sightings?|sighted|saw|seen|observed|observation|witness(?:es)?|"
    r"objects?|lights?|dis[ck]s?|flying|craft|abduct(?:ion|ed)?|encounter(?:ed)?|"
    r"humanoids?|unidentified|aliens?|landed|landing|beings?|nocturnal|fireballs?|"
    r"orbs?|spheres?|triangles?|cigar|faded|vanished|hover(?:ed|ing)?|levitat(?:ed|ing))\b", re.I)


def load_place_checks(path):
    """Only unqualified country-wide queries prove a populated-place collision check."""
    checks = {}
    for query in json_lines(path):
        if query.get("admin1"):
            continue
        key = (query.get("country"), norm(query.get("locality")))
        collisions = [str(f["geonameId"]) for f in query.get("features", [])
                      if f.get("featureClass") == "P"]
        checks.setdefault(key, set()).update(collisions)
    return checks


def explicit_admin_slot(detail, candidate):
    """Retain source schema's state/province slot, not a city with the same name."""
    fields = candidate["source_location_fields"]
    source = detail.get("source")
    admin = str(candidate.get("admin1") or "").lower()
    label = candidate["display_label"].split(": ", 1)[-1].rsplit(", ", 1)[0]
    if source == "ufocat":
        return norm(fields.get("STATE")) in {admin, norm(label)} or (
            candidate["country_code"] == "CA" and norm(fields.get("REGION")) == "cn" and bool(fields.get("STATE")))
    key = "Location" if source == "nuforc" else "Location of Event" if source == "mufon" else None
    if key and key in fields:
        parts = fields[key].replace("\\,", ",").split(",")
        # These retained source fields use city, state/province, country.
        return len(parts) == 3 and bool(norm(parts[1]))
    return False


def admin_ambiguity(detail, candidate, place_checks):
    if not candidate.get("admin1") or explicit_admin_slot(detail, candidate):
        return None
    country = candidate["country_code"]
    label = candidate["display_label"].split(": ", 1)[-1].rsplit(", ", 1)[0]
    key = (country, norm(label))
    if key not in place_checks:
        return "generic_admin_name_not_checked_against_cities"
    if place_checks[key]:
        return "city_admin_name_collision"
    return None


def make_country_patterns(countries):
    aliases = {code: {row["name"]} for code, row in countries.items()}
    aliases.setdefault("GB", set()).update({"United Kingdom", "Great Britain", "England", "Scotland", "Wales", "Northern Ireland", "UK"})
    aliases.setdefault("US", set()).update({"United States", "USA"})
    aliases.setdefault("RU", set()).add("Russia")
    # Match named countries, not two-letter codes/pronouns or nationalities.
    return {code: re.compile(r"(?<!\w)(?:" + "|".join(re.escape(v) for v in names) + r")(?!\w)", re.I)
            for code, names in aliases.items()}


def full_source_text(detail):
    texts = [str(detail.get("description") or ""), str(detail.get("summary") or "")]
    for fields in (detail.get("raw_fields") or {}, detail.get("raw_source_row") or {}):
        texts.extend(str(value) for key, value in fields.items()
                     if re.search(r"description|narrative|comment|summary|report text", key, re.I))
    return "\n".join(dict.fromkeys(texts))


def admission(record, candidate, place_checks, country_patterns):
    summary, detail = record["summary"], record["source_detail"]
    if detail.get("event_id") != summary.get("event_id") or candidate["event_id"] != summary.get("event_id"):
        return None, "source_event_identity_mismatch"
    if summary.get("has_coordinates") or summary.get("lat") is not None or summary.get("lon") is not None:
        return None, "current_view_already_mapped"
    if summary.get("coordinate_source") != "unresolved":
        return None, "prior_coordinate_review_or_quarantine"
    if (detail.get("has_coordinates") or detail.get("lat") is not None or detail.get("lon") is not None
            or detail.get("coordinate_source") not in {None, "", "unresolved"}):
        return None, "original_coordinates_removed_from_current_view"
    for obj in (summary, detail):
        if any(value and re.search(r"quarantin|coordinate_reject|location_reject", key, re.I) for key, value in obj.items()):
            return None, "prior_coordinate_review_or_quarantine"
    if (any(int(detail.get(key) or 1) > 1 for key in ("duplicate_record_count", "source_provenance_count"))
            or len(detail.get("source_provenance") or []) > 1
            or len(detail.get("canonical_input_ids") or []) > 1):
        return None, "composite_members_not_independently_verified"
    boundary = candidate.get("boundary_context")
    if not boundary:
        return None, "country_boundary_unavailable"
    if boundary.get("point_in_coarse_country_boundary") is not True:
        return None, "area_point_outside_coarse_country_boundary"
    ambiguity = admin_ambiguity(detail, candidate, place_checks)
    if ambiguity:
        return None, ambiguity
    text = full_source_text(detail)
    if PLACEHOLDER_SUBMISSION.search(text):
        return None, "test_or_placeholder_submission"
    if NON_TERRESTRIAL.search(text):
        return None, "non_terrestrial_context"
    if TRANSIT_OR_OFFSHORE.search(text):
        return None, "route_or_offshore_context_requires_review"
    if DOCUMENTARY.search(text) or DOCUMENTARY_EXTRA.search(text):
        return None, "documentary_publisher_or_address_context"
    other_countries = [code for code, pattern in country_patterns.items()
                       if code != candidate["country_code"] and pattern.search(text)]
    if other_countries:
        return None, "other_country_in_full_source_context"
    if not OBSERVATION_CONTEXT.search(text):
        return None, "observation_context_not_established"
    label = candidate["display_label"].split(": ", 1)[-1]
    reference = {
        "kind": candidate["location_precision"], "label": label,
        "note": "Approximate area reference; exact sighting/observer position unknown. Present-day geography, not historical date-specific borders. Do not use as a precise trace endpoint.",
        "authority_ids": ["geonames:" + candidate["geoname_id"]],
        "evidence_id": "area-reference:" + str(candidate["event_id"]),
    }
    # Country bounds may illustrate country scope only. No state/province
    # extents or uncertainty radius are guessed from a representative point.
    if reference["kind"] == "country":
        reference["bounds"] = boundary["bbox"]
    assert len(json.dumps(reference, ensure_ascii=False).encode("utf-8")) < 1024
    decision = {
        "event_id": candidate["event_id"], "decision": "accepted",
        "policy": "explicit_reported_area_reference_v1_conservative_admission",
        "guard": {key: summary.get(key) for key in GUARD_FIELDS},
        "source_identity": {key: detail.get(key) for key in IDENTITY_FIELDS},
        "set_fields": {"lat": candidate["lat"], "lon": candidate["lon"], "has_coordinates": True,
                       "coordinate_source": "reviewed_area_reference", "location_precision": candidate["location_precision"],
                       "location_reference": reference},
        "evidence_id": reference["evidence_id"],
    }
    return decision, None


def run(args):
    candidates = {row["event_id"]: row for row in json_lines(args.candidates)}
    checks = load_place_checks(args.place_queries)
    patterns = make_country_patterns(load_country_info(args.country_info))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    paths = {kind: args.output_dir / name for kind, name in {
        "accepted": "accepted-area-decisions.jsonl.gz", "evidence": "accepted-area-evidence.jsonl.gz",
        "holds": "area-admission-holds.jsonl.gz"}.items()}
    counts, holds, precisions, sources = Counter(), Counter(), Counter(), Counter()
    with gzip.open(paths["accepted"], "wt", encoding="utf-8") as out, gzip.open(paths["evidence"], "wt", encoding="utf-8") as evidence, gzip.open(paths["holds"], "wt", encoding="utf-8") as held:
        for record in json_lines(args.details):
            counts["full_source_records_screened"] += 1
            candidate = candidates.get(record["summary"]["event_id"])
            if not candidate:
                continue
            counts["area_candidates"] += 1
            decision, reason = admission(record, candidate, checks, patterns)
            if decision:
                counts["accepted"] += 1
                precisions[candidate["location_precision"]] += 1
                sources[candidate["source"]] += 1
                out.write(json.dumps(decision, ensure_ascii=False, separators=(",", ":")) + "\n")
                evidence.write(json.dumps({"evidence_id": decision["evidence_id"], "candidate": candidate,
                    "source_narrative": full_source_text(record["source_detail"]),
                    "admission_checks": ["unmerged_original", "unresolved_current_summary", "original_location_fields_agree", "country_boundary_contradiction_check_passed", "admin_city_ambiguity_screen", "full_source_context_screen"]}, ensure_ascii=False, separators=(",", ":")) + "\n")
            else:
                counts["held"] += 1; holds[reason] += 1
                held.write(json.dumps({"event_id": candidate["event_id"], "reason": reason}, separators=(",", ":")) + "\n")
    report = {"schema_id": "area-reference-admission-v1", "counts": dict(counts), "by_precision": dict(precisions), "by_source": dict(sources), "holds": dict(holds),
              "inputs": {str(p): {"bytes": p.stat().st_size, "sha256": digest(p)} for p in [args.details, args.candidates, args.place_queries, args.country_info]},
              "outputs": {str(p): {"bytes": p.stat().st_size, "sha256": digest(p)} for p in paths.values()},
              "notes": ["No canonical/runtime/source record changed.", "GeoNames administrative feature and original location fields establish area identity; coarse country polygons are not independent authority.", "Country/state/province reference points are not sighting/observer positions; historical boundaries are not reconstructed.", "All merged records held; no cross-record place transfer.", "Full narratives retained separately; runtime location_reference remains below 1 KiB."]}
    (args.output_dir / "area-admission-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ["counts", "by_precision", "holds"]}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["details", "candidates", "place-queries", "country-info", "output-dir"]:
        parser.add_argument("--" + name, type=Path, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
