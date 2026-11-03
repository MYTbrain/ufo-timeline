"""Propose explicitly labelled area references for unresolved source locations.

This is a read-only recovery lane. It never fills a missing city with a country
point: every non-placeholder source location component must describe the same
country/admin1 area. It consumes a small shared GeoNames administrative-feature
extract, not another copy of the complete gazetteer. Outputs are candidates and
holds for review; no runtime/canonical artifact is changed.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import re
from pathlib import Path
import unicodedata

from scripts.summarize_structured_city_alias_geonames_mapping_candidates import ADMIN1_ALIASES
from scripts.apply_coordinate_sanity_preview import point_in_geometry


COUNTRY_FEATURES = {"PCLI", "PCLD", "PCLF", "PCLS", "PCL"}
CONTINENTS = {"AA", "AF", "AN", "AS", "AU", "EU", "NA", "OC", "P", "SA"}
PLACEHOLDERS = {"", "0", "?", "unknown", "unk", "none", "n/a", "na", "unspecified", "[data missing]", "not specified"}
HISTORICAL = {"ussr", "soviet union", "czechoslovakia", "yugoslavia", "east germany", "west germany", "gdr", "ddr"}
AMBIGUOUS_BARE_COUNTRIES = {"georgia", "jordan", "jersey", "congo"}
BLOCKED_LOCATION = re.compile(r"\b(?:moon|mars|venus|jupiter|saturn|lunar|orbit|space|spacecraft|sea|ocean|ocn|offshore|off coast|international waters|between|aboard|route|flight|airport|airbase|base|headquarters|publisher|address)\b", re.I)
NON_TERRESTRIAL = re.compile(r"\b(?:on (?:the )?(?:moon|lunar surface|mars)|in (?:earth |lunar |space )?orbit|during (?:a )?spacewalk|aboard (?:apollo|gemini|soyuz|the space shuttle|the international space station))\b", re.I)
DOCUMENTARY = re.compile(r"\b(?:editorial|book review|press conference|conference proceedings|memorandum|press release|scientific paper|research paper|publication of|publishes (?:a |the )?(?:book|article)|published (?:a |the )?(?:book|article))\b", re.I)


def norm(value):
    value = unicodedata.normalize("NFKD", str(value or "").replace("\\,", ",").replace("\\n", " "))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", value).strip().lower()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def json_lines(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def load_country_info(path):
    result = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        row = line.split("\t")
        if len(row) >= 5:
            result[row[0]] = {"iso2": row[0], "iso3": row[1], "name": row[4]}
    return result


def geometry_bounds(geometry):
    points = []
    def visit(value):
        if isinstance(value, (list, tuple)) and len(value) >= 2 and isinstance(value[0], (int, float)):
            points.append(value)
        elif isinstance(value, (list, tuple)):
            for item in value:
                visit(item)
    visit(geometry.get("coordinates", []))
    return [min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points)] if points else None


def build_authority_index(features, countries, boundaries=None):
    country_aliases = {}
    for code, row in countries.items():
        for alias in (code, row["iso3"], row["name"]):
            country_aliases[norm(alias)] = code
    country_aliases.update({"uk": "GB", "u.k.": "GB", "great britain": "GB", "u.s.": "US", "u.s.a.": "US", "united states of america": "US", "south korea": "KR", "north korea": "KP"})
    country_features = defaultdict(list)
    admin_features = defaultdict(list)
    admin_aliases = defaultdict(set)
    for f in features:
        code = f.get("country") or f.get("countryCode")
        kind = f.get("featureCode")
        if kind in COUNTRY_FEATURES:
            country_features[code].append(f)
        elif kind == "ADM1" and f.get("admin1"):
            key = (code, f["admin1"])
            admin_features[key].append(f)
            for name in (f.get("name"), f.get("asciiName")):
                if name:
                    admin_aliases[(code, norm(name))].add(f["admin1"])
            # Numeric GeoNames admin codes are not ordinary place names.
            if not str(f["admin1"]).isdigit():
                admin_aliases[(code, norm(f["admin1"]))].add(f["admin1"])
    for code, aliases in ADMIN1_ALIASES.items():
        for alias, admin in aliases.items():
            if (code, admin) in admin_features:
                admin_aliases[(code, norm(alias))].add(admin)
    country_boundaries = {f.get("id"): f for f in (boundaries or {}).get("features", [])}
    return {"countries": countries, "country_aliases": country_aliases, "country_features": country_features,
            "admin_features": admin_features, "admin_aliases": admin_aliases, "boundaries": country_boundaries}


def original_location_fields(detail):
    """Read only the source's explicit event-location fields, never prose guesses."""
    fields = detail.get("raw_fields") or detail.get("raw_source_row") or {}
    source = detail.get("source")
    selected = []
    if source == "phenomenainon_updb":
        for key in ("city", "country"):
            if fields.get(key) is not None:
                selected.append((key, fields[key]))
    elif source == "ufocat":
        for key in ("LOCATION", "COUNTY", "STATE", "REGION"):
            if fields.get(key) is not None:
                selected.append((key, fields[key]))
    elif source == "nuforc":
        selected = [("Location", fields["Location"])] if "Location" in fields else []
    elif source == "mufon":
        selected = [("Location of Event", fields["Location of Event"])] if "Location of Event" in fields else []
    elif source == "majestic":
        selected = sorted((k, v) for k, v in fields.items() if re.fullmatch(r"location/\d+", k) and v)
    return [(str(k), str(v)) for k, v in selected if v is not None and str(v).strip()]


def parse_area(detail, index):
    fields = original_location_fields(detail)
    if not fields:
        return None, "missing_original_location_fields"
    source = detail.get("source")
    raw = " | ".join(v for _, v in fields)
    if BLOCKED_LOCATION.search(raw):
        return None, "non_area_location_or_route"
    parts = [(key, norm(part)) for key, value in fields for part in value.replace("\\,", ",").split(",") if norm(part) not in PLACEHOLDERS]
    if not parts:
        return None, "no_explicit_jurisdiction"
    if any(v in HISTORICAL for _, v in parts):
        return None, "historical_jurisdiction_requires_review"
    explicit_country = None
    if source == "phenomenainon_updb":
        explicit = [index["country_aliases"].get(v) for key, v in parts if key == "country"]
        if len(explicit) != 1 or not explicit[0]:
            return None, "country_field_unrecognized"
        explicit_country = explicit[0]
    elif source == "ufocat":
        original = {key: norm(v) for key, v in fields}
        region = original.get("REGION", "").upper()
        if region == "CN":  # UFODCAT's legacy North American REGION code, not ISO China.
            explicit_country = "CA"
            parts = [(k, v) for k, v in parts if k != "REGION"]
        elif region in CONTINENTS:
            state = original.get("STATE", "")
            legacy_aliases = {"sui": "CH", "ger": "DE", "chi": "CL", "den": "DK", "saf": "ZA"}
            explicit_country = index["country_aliases"].get(state) or legacy_aliases.get(state)
            if not explicit_country:
                return None, "legacy_country_unrecognized"
            parts = [(k, v) for k, v in parts if k not in {"REGION", "STATE"}]
        else:
            explicit_country = index["country_aliases"].get(norm(region))
    # Explicit UK subdivision syntax is a region, not a slash-separated route.
    parts = [(k, re.sub(r"^(?:uk|united kingdom)/", "", v)) for k, v in parts]
    if any("/" in value or ";" in value for _, value in parts):
        return None, "compound_or_multiple_location"
    country_codes = set()
    if explicit_country:
        country_codes.add(explicit_country)
    for key, value in parts:
        code = index["country_aliases"].get(value)
        if code:
            # In a country-qualified location, an admin code wins over an ISO
            # country code collision: CA, US means California; IN, US Indiana.
            if explicit_country and index["admin_aliases"].get((explicit_country, value)) and key != "country":
                continue
            country_codes.add(code)
    if not country_codes:
        if any(value in {"england", "scotland", "wales", "northern ireland"} for _, value in parts):
            country_codes.add("GB")
        else:
            return None, "no_explicit_country"
    if len(country_codes) != 1:
        # Generic location strings can carry state abbreviations before a
        # terminal country: infer only if every preceding token is an admin.
        tail_code = index["country_aliases"].get(parts[-1][1]) if parts else None
        if not explicit_country and tail_code and all(index["admin_aliases"].get((tail_code, value)) or index["country_aliases"].get(value) == tail_code for _, value in parts):
            country_codes = {tail_code}
        else:
            return None, "conflicting_country_evidence"
    country = next(iter(country_codes))
    admins = set()
    leftovers = []
    for key, value in parts:
        if key == "country" and source == "phenomenainon_updb":
            continue
        admin_matches = index["admin_aliases"].get((country, value), set())
        if len(admin_matches) > 1:
            return None, "ambiguous_admin_name"
        if admin_matches:
            admins.update(admin_matches)
        elif index["country_aliases"].get(value) != country:
            leftovers.append(value)
    if leftovers:
        return None, "more_specific_location_not_resolved"
    if len(admins) > 1:
        return None, "multiple_administrative_regions"
    if not explicit_country and len(parts) == 1:
        value = parts[0][1]
        if value in AMBIGUOUS_BARE_COUNTRIES or (len(value) == 2 and value not in {"us", "gb", "uk"}):
            return None, "ambiguous_bare_jurisdiction"
    admin = next(iter(admins), None)
    matches = index["admin_features"].get((country, admin), []) if admin else index["country_features"].get(country, [])
    if len(matches) != 1:
        return None, "missing_or_ambiguous_area_authority"
    feature = matches[0]
    return {"country": country, "admin1": admin, "feature": feature, "fields": dict(fields)}, None


def evaluate(record, index):
    summary = record.get("summary", {})
    detail = record.get("source_detail", {})
    event_id = summary.get("event_id")
    hold = {"event_id": event_id, "location_raw": summary.get("location_raw"), "source": summary.get("source")}
    if summary.get("has_coordinates"):
        return None, dict(hold, reason="already_mapped")
    if detail.get("event_id") != event_id:
        return None, dict(hold, reason="source_event_identity_mismatch")
    area, reason = parse_area(detail, index)
    if reason:
        return None, dict(hold, reason=reason)
    description = str(detail.get("description") or detail.get("summary") or "")
    if NON_TERRESTRIAL.search(description):
        return None, dict(hold, reason="non_terrestrial_context")
    if DOCUMENTARY.search(description):
        return None, dict(hold, reason="documentary_or_publisher_context")
    feature = area["feature"]
    lat, lon = feature.get("lat"), feature.get("lon")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None, dict(hold, reason="invalid_area_authority_point")
    country = area["country"]
    admin = area["admin1"]
    precision = "country" if not admin else ("state" if country in {"US", "AU"} else "province")
    iso3 = index["countries"][country]["iso3"]
    boundary = index["boundaries"].get(iso3)
    boundary_ref = None
    if boundary:
        boundary_ref = {"feature_id": iso3, "scope": "country", "authority_level": "coarse_display_context_not_survey_authority", "bbox": geometry_bounds(boundary["geometry"]), "point_in_coarse_country_boundary": point_in_geometry(lat, lon, boundary["geometry"])}
    # Use the short countryInfo label rather than formal/malformed names in
    # older GeoNames area records; preserve the authority ID and original hash.
    label = index["countries"][country]["name"] if not admin else (feature.get("asciiName") or feature["name"]) + ", " + index["countries"][country]["name"]
    return {"event_id": event_id, "canonical_event_id": detail.get("canonical_event_id"), "source": summary.get("source"), "source_id": detail.get("source_id"), "location_raw": summary.get("location_raw"), "candidate_policy": "explicit_reported_area_reference_v1", "decision": "candidate_for_review", "lat": lat, "lon": lon, "location_precision": precision, "coordinate_source": "reviewed_area_reference", "coordinate_role": "administrative_area_reference_not_observer_position", "display_label": "Approximate area reference: " + label, "country_code": country, "admin1": admin, "geoname_id": str(feature["geonameId"]), "area_feature_code": feature["featureCode"], "authority_url": feature.get("authorityUrl") or "https://www.geonames.org/" + str(feature["geonameId"]), "source_location_fields": area["fields"], "source_location_role": "reported_event_location_fields_only", "source_detail_provenance": record.get("provenance"), "authority_source_line_sha256": feature.get("sourceLineSha256"), "boundary_context": boundary_ref, "admin_boundary_available": False if admin else bool(boundary), "precision_note": "Representative point for the named administrative area, not a recovered observer/site coordinate. Present-day display geography does not establish historical boundaries; never use this point as exact evidence or as a precise trace endpoint."}, None


def run(args):
    countries = load_country_info(args.country_info)
    boundaries = json.loads(args.country_boundaries.read_text(encoding="utf-8")) if args.country_boundaries else None
    index = build_authority_index(json_lines(args.authorities), countries, boundaries)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    by_precision = Counter()
    by_source = Counter()
    by_region = Counter()
    holds = Counter()
    candidate_path = args.output_dir / "area-reference-candidates.jsonl.gz"
    hold_path = args.output_dir / "area-reference-holds.jsonl.gz"
    with gzip.open(candidate_path, "wt", encoding="utf-8", newline="\n") as accepted, gzip.open(hold_path, "wt", encoding="utf-8", newline="\n") as rejected:
        for record in json_lines(args.details):
            counts["screened"] += 1
            candidate, hold = evaluate(record, index)
            if candidate:
                counts["candidates"] += 1
                by_precision[candidate["location_precision"]] += 1
                by_source[candidate["source"]] += 1
                by_region[candidate["display_label"]] += 1
                accepted.write(json.dumps(candidate, ensure_ascii=False, separators=(",", ":")) + "\n")
            else:
                counts["held"] += 1
                holds[hold["reason"]] += 1
                rejected.write(json.dumps(hold, ensure_ascii=False, separators=(",", ":")) + "\n")
    report = {"schema_id": "mapping-area-reference-recovery-v1", "scope": "Every retained unmapped source detail screened; candidates only", "canonical_outputs_mutated": False, "counts": dict(counts), "by_precision": dict(by_precision), "by_source": dict(by_source), "top_regions": by_region.most_common(50), "holds": dict(holds), "inputs": {str(path): {"bytes": path.stat().st_size, "sha256": digest(path)} for path in [args.details, args.authorities, args.country_info] + ([args.country_boundaries] if args.country_boundaries else [])}, "outputs": {str(path): {"bytes": path.stat().st_size, "sha256": digest(path)} for path in [candidate_path, hold_path]}, "notes": ["No more-specific unresolved location is replaced by a country point.", "No administrative reference is a recovered observer coordinate or precise trace endpoint.", "GeoNames area records establish administrative identity; country GeoJSON is coarse display context with derivative provenance, not an authoritative cadastral boundary.", "Admin1 polygon extents are not available in these retained inputs; no uncertainty radius is fabricated."]}
    (args.output_dir / "area-reference-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"counts": dict(counts), "precision": dict(by_precision), "holds": dict(holds)}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--details", type=Path, required=True)
    parser.add_argument("--authorities", type=Path, required=True)
    parser.add_argument("--country-info", type=Path, required=True)
    parser.add_argument("--country-boundaries", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
