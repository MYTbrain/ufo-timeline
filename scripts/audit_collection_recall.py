"""Complement the pinned soil/plant dossier without rewriting its judgments.

This is a recall queue, never a positive classifier. All full-detail files are
streamed one chunk at a time from their existing pinned locations. Candidate
excerpts are bounded; exact locators allow a reviewer to reopen full narratives.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import hashlib
import html
import json
from pathlib import Path
import re
import time

NARRATIVE_KEY = re.compile(r"description|summary|^desc$|^notes?$|narrative|report_text|^text$", re.I)
TAGS = re.compile(r"<[^>]{1,300}>")
SPACE = re.compile(r"\s+")

# These supplement (rather than simply rerun) the dossier's logged patterns:
# geological/vegetative materials absent from its list; extraction mechanics;
# additional Romance-language sampling verbs; and terse native wording.
NEW_MATERIAL = re.compile(
    r"\b(?:turf|sod|clods?|pebbles?|gravel|loam|clay|mud|sediments?|silt|chalk|"
    r"boulders?|ore|ores|crystals?|quartz|lichen|bark|twigs?|petals?|blossoms?|"
    r"foliage|sprouts?|shoots|saplings?|pollen|pinecones?|cones|berries|tubers?|"
    r"mottes?|cailloux|pousses|feuillage|fango|terriccio|sassi|erba|fiori|"
    r"hojas|hierbas?|arbustos?|piedras|guijarros|barro|grama|folhas|pedras|"
    r"amostras?|campioni|preliev\w*)\b", re.I)
MATERIAL = re.compile(
    r"\b(?:soil\w*|dirt|earth|ground|sand|rocks?|stones?|minerals?|vegetation|"
    r"plants?|flowers?|leaves|leaf|grass|roots?|seeds?|crops?|wheat|corn|maize|"
    r"potatoes|beans?|cabbages?|lavender|alfalfa|mushrooms?|ferns?|trees?|"
    r"branches?|shrubs?|bushes|water|agu[ae]|eau|muestras?|plantas?|flores|"
    r"tierra|rocas?|vegetaci[oó]n|fleurs?|herbe|arbres?|terre|sol|boden|"
    r"pflanzen|blumen|proben|turf|sod|clods?|pebbles?|gravel|loam|clay|mud|"
    r"sediments?|silt|chalk|boulders?|ore|ores|crystals?|quartz|lichen|bark|"
    r"twigs?|petals?|blossoms?|foliage|sprouts?|shoots|saplings?|pollen|"
    r"pinecones?|berries|tubers?|mottes?|cailloux|pousses|feuillage|fango|"
    r"terriccio|sassi|erba|fiori|hojas|hierbas?|arbustos?|piedras|guijarros|"
    r"barro|grama|folhas|pedras|amostras?|campioni)\b", re.I)
NEW_ACTION = re.compile(
    r"\b(?:extract\w*|excavat\w*|siphon\w*|aspirat\w*|levitat\w*|"
    r"hoist\w*|elevat\w*|suction|bor(?:e|es|ed|ing)|core\s+sampl\w*|"
    r"sever\w*|detach\w*|clip(?:s|ped|ping)?|snip\w*|pinch\w*|"
    r"trim(?:s|med|ming)?|stow\w*|load(?:s|ed|ing)?|deposit\w*|"
    r"gouge\w*|nibbl\w*|forag\w*|prelev\w*|pr[eé]lev\w*|r[eé]colt\w*|"
    r"arrach\w*|raccog\w*|cogli\w*|campion\w*|scav\w*|apanh\w*|"
    r"colh\w*|amostr\w*|cog(?:er|iendo|i[oó]|i[ae]n)|tom(?:ar|ando|[aó])|"
    r"arranc\w*|recogi\w*|extrai\w*|extra[eé]\w*|succion\w*|"
    r"suck\w*\s+up|draw\w*\s+(?:up|into)|lift\w*\s+(?:up|into))\b", re.I)
ACTION = re.compile(
    r"\b(?:collect\w*|gather\w*|sampl\w*|examin\w*|inspect\w*|pick\w*|"
    r"pluck\w*|tak(?:e|en|es|ing)|took|carri\w*|carry\w*|dig\w*|dug|"
    r"scoop\w*|scrap\w*|sift\w*|cut(?:s|ting)?|pull\w*|uproot\w*|"
    r"harvest\w*|remov\w*|touch\w*|extract\w*|excavat\w*|siphon\w*|"
    r"aspirat\w*|levitat\w*|hoist\w*|elevat\w*|suction|bor(?:e|es|ed|ing)|"
    r"sever\w*|detach\w*|clip(?:s|ped|ping)?|snip\w*|pinch\w*|"
    r"trim(?:s|med|ming)?|stow\w*|load(?:s|ed|ing)?|deposit\w*|"
    r"gouge\w*|nibbl\w*|forag\w*|pr[eé]lev\w*|prelev\w*|r[eé]colt\w*|"
    r"arrach\w*|raccog\w*|cogli\w*|campion\w*|scav\w*|apanh\w*|colh\w*|"
    r"amostr\w*|cog(?:er|iendo|i[oó]|i[ae]n)|tom(?:ar|ando|[aó])|"
    r"arranc\w*|recogi\w*|extrai\w*|extra[eé]\w*|succion\w*)\b", re.I)
ACTOR = re.compile(r"\b(?:occupant\w*|beings?|entities|entity|humanoid\w*|alien\w*|creature\w*|figures?|dwar\w*|little\s+(?:men|man|people)|robots?|ufonaut\w*|hombres|seres|hommes|personnages|omino|omini|criaturas)\b", re.I)
MECHANICAL = re.compile(r"\b(?:suction|siphon\w*|aspirat\w*|vacuum\w*|hoist\w*|levitat\w*|extract\w*|excavat\w*)\b", re.I)


def read(path):
    data = Path(path).read_bytes()
    return json.loads(gzip.decompress(data) if str(path).endswith(".gz") else data)


def narratives(row):
    stack = [("", row)]
    seen = set()
    while stack:
        prefix, obj = stack.pop()
        for key, value in obj.items():
            field = f"{prefix}/{key}" if prefix else str(key)
            if isinstance(value, str) and NARRATIVE_KEY.search(str(key)):
                text = SPACE.sub(" ", html.unescape(TAGS.sub(" ", value))).strip()
                if text and text not in seen:
                    seen.add(text)
                    yield field, text
            elif isinstance(value, dict):
                stack.append((field, value))
            elif isinstance(value, list):
                stack.extend((f"{field}/{i}", x) for i, x in enumerate(value) if isinstance(x, dict))


def bounded_queue(candidates):
    """Preserve locators while avoiding bulk retention of unrelated text."""
    enriched, compact = [], []
    for candidate in candidates:
        if candidate["score"] >= 5:
            enriched.append(candidate)
        else:
            match = candidate["snippets"][0]
            compact.append({k: candidate[k] for k in ("event_id", "chunk_id", "detail_index", "source", "score")}
                           | {"field": match["field"], "start": match["start"], "action": match["action"],
                              "material": match["material"], "reason": match["reason"],
                              "review_status": "unreviewed_lower_priority"})
    return enriched, compact


def scan(dossier, out):
    started = time.monotonic()
    pins = read(dossier / "input_pins.json")
    old_path = dossier / "reviewed_candidate_dispositions.csv"
    with old_path.open(encoding="utf-8-sig", newline="") as file:
        reviewed_ids = {str(r["event_id"]) for r in csv.DictReader(file)}
    retained_ids = {str(r["event_id"]) for r in read(dossier / "reviewed_report_rows.json")["records"]}
    current_ids = set()
    for pin in pins["summary_shards"]:
        if hashlib.sha256(Path(pin["path"]).read_bytes()).hexdigest() != pin["sha256"]:
            raise ValueError(f"Pinned summary changed: {pin['path']}")
        current_ids.update(str(r["event_id"]) for r in read(pin["path"]))
    counts = collections.Counter()
    source_counts = collections.defaultdict(collections.Counter)
    candidates = []
    metadata = {}
    for number, pin in enumerate(pins["detail_chunks"]):
        data = Path(pin["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != pin["sha256"]:
            raise ValueError(f"Pinned detail changed: {pin['path']}")
        for index, row in enumerate(json.loads(gzip.decompress(data))):
            event_id = str(row["event_id"])
            if event_id not in current_ids:
                counts["noncurrent_physical_rows_excluded"] += 1
                continue
            counts["current_rows_scanned"] += 1
            source_counts[row.get("source")]["scanned"] += 1
            fields = list(narratives(row))
            if event_id in retained_ids:
                metadata[event_id] = {k: row.get(k) for k in ("event_id", "source", "source_id", "date_raw", "date_iso", "sort_date_iso", "end_date_iso", "date_precision", "location_raw", "country", "lat", "lon", "has_coordinates", "location_precision", "coordinate_source", "shape", "type", "craft_type", "craft_category", "source_url")}
                metadata[event_id].update(chunk_id=pin["id"], detail_index=index, detail_chunk_sha256=pin["sha256"], detail_chunk_url=pin["url"])
            counts["rows_with_narrative" if fields else "rows_without_narrative"] += 1
            matched = []
            for field, text in fields:
                # A new verb or a new material is required, avoiding an unlogged
                # rerun of all 41,841 prior lexical candidates.
                novel_actions = list(NEW_ACTION.finditer(text))
                novel_materials = list(NEW_MATERIAL.finditer(text))
                if not novel_actions and not novel_materials:
                    continue
                pairs = []
                for action in novel_actions:
                    lo, hi = max(0, action.start() - 180), action.end() + 180
                    for material in MATERIAL.finditer(text, lo, min(len(text), hi)):
                        pairs.append((action, material, "additional_extraction_or_multilingual_action"))
                for material in novel_materials:
                    lo, hi = max(0, material.start() - 180), material.end() + 180
                    for action in ACTION.finditer(text, lo, min(len(text), hi)):
                        pairs.append((action, material, "additional_material_synonym"))
                for action, material, reason in pairs:
                    lo = max(0, min(action.start(), material.start()) - 180)
                    hi = min(len(text), max(action.end(), material.end()) + 260)
                    local = text[max(0, lo - 400):hi + 400]
                    actor = bool(ACTOR.search(local))
                    mechanical = bool(MECHANICAL.fullmatch(action.group()))
                    # Prioritize meaningful contexts; retain all new candidates.
                    score = 10 * actor + 5 * mechanical + (3 if reason.startswith("additional_material") else 1)
                    matched.append({"field": field, "start": lo, "end": hi,
                                    "snippet": text[lo:hi], "field_chars": len(text),
                                    "action": action.group(), "material": material.group(),
                                    "reason": reason, "actor_context": actor,
                                    "mechanical_action": mechanical, "score": score})
            if not matched:
                continue
            counts["all_matching_rows"] += 1
            if event_id in reviewed_ids:
                counts["previously_reviewed_matches_preserved"] += 1
                continue
            counts["novel_candidate_rows"] += 1
            source_counts[row.get("source")]["novel_candidates"] += 1
            matched.sort(key=lambda m: (-m["score"], m["field"] != "description", m["start"]))
            keep = []
            for match in matched:
                if not any(x["field"] == match["field"] and abs(x["start"] - match["start"]) < 160 for x in keep):
                    keep.append(match)
                if len(keep) == 2:
                    break
            candidate = {k: row.get(k) for k in ("source", "source_id", "date_raw", "date_iso", "sort_date_iso", "date_precision", "location_raw", "country", "lat", "lon", "has_coordinates", "source_url")}
            candidate.update(event_id=event_id, chunk_id=pin["id"], detail_index=index,
                             detail_chunk_url=pin["url"], snippets=keep,
                             score=matched[0]["score"], review_status="unadjudicated_recall_candidate")
            candidates.append(candidate)
        if number % 30 == 0:
            print(json.dumps({"chunks": number + 1, "rows": counts["current_rows_scanned"], "new_candidates": len(candidates), "elapsed_seconds": round(time.monotonic() - started)}), flush=True)
    assert counts["current_rows_scanned"] == len(current_ids) == 702893
    candidates.sort(key=lambda r: (-r["score"], r.get("sort_date_iso") or r.get("date_iso") or "", r["event_id"]))
    # Keep the wide queue's exact locators, enriching only higher-priority
    # contexts. This avoids copying thousands of unrelated long descriptions.
    enriched, compact = bounded_queue(candidates)
    result = {"schema": "collection-complementary-recall-audit-v1", "created_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
              "purpose": "New whole-current-corpus recall queue supplementing, not replacing, 6,690 prior decisions. No keyword hit is accepted automatically.",
              "prior_dossier": str(dossier), "prior_dispositions_sha256": hashlib.sha256(old_path.read_bytes()).hexdigest(),
              "input_pins_sha256": hashlib.sha256((dossier / "input_pins.json").read_bytes()).hexdigest(),
              "prior_reviewed_ids": len(reviewed_ids), "counts": dict(counts),
              "source_counts": {k: dict(v) for k, v in source_counts.items()},
              "search_definition": {"new_material": NEW_MATERIAL.pattern, "material": MATERIAL.pattern,
                                    "new_action": NEW_ACTION.pattern, "action": ACTION.pattern,
                                    "actor": ACTOR.pattern, "mechanical": MECHANICAL.pattern,
                                    "action_material_radius_chars": 180, "not_positive_classifier": True},
              "elapsed_seconds": round(time.monotonic() - started, 2), "records": enriched,
              "lower_priority_queue": compact,
              "retention_note": "Exact locators retained for all new candidates; only priority score>=5 has bounded excerpts. Scores order review and never imply inclusion."}
    out.mkdir(parents=True, exist_ok=True)
    target = out / "collection_recall_audit_candidates.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8")
    (out / "collection_recall_audit_metadata.json").write_text(json.dumps({"schema": "collection-sparse-canonical-metadata-v1", "records": metadata}, ensure_ascii=False, indent=2), encoding="utf8")
    if target.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("Recall output exceeded bounded 10 MiB budget")
    print(json.dumps({"complete": True, "counts": dict(counts), "output_bytes": target.stat().st_size, "elapsed_seconds": result["elapsed_seconds"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dossier", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    scan(args.dossier, args.output)
