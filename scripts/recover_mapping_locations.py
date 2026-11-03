"""Screen every unmapped summary against independent, retained GeoNames evidence.

This is a research queue, never a coordinate repair. Qualified labels and
compound-place components retain their original text and explicit review holds.
All exact and alternate-name matches are retained; population never selects a
winner. Source narratives and geographic roles must be reviewed before any
candidate can become a guarded correction. No mapped-copy inference is used.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import html
import json
import math
from pathlib import Path
import re
import sys
import unicodedata
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.summarize_structured_city_alias_geonames_mapping_candidates import ADMIN1_ALIASES

SHARED = Path(r"C:/Users/jarod/Desktop/UFO Timeline map tool")
PREVIOUS = SHARED / "data/research/database_quality_20261007/gazetteer_recovery"
SCHEMA = "ufo-unmapped-qualified-place-candidates-v1"
GUARD_FIELDS = ("source", "sort_date_iso", "location_raw", "lat", "lon",
                "coordinate_source", "location_precision", "has_coordinates")
SUPPORTED_FEATURES = {"PPL", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLC", "PPLX"}
AREA_FEATURES = {"PCLI", "PCLD", "PCLF", "PCLS", "PCL", "ADM1"}
ROLE_WORDS = re.compile(
    r"\b(?:between|near|outside|offshore|aboard|airport|airbase|afb|military|"
    r"highway|road|route|coast|county|township|vicinity|approx|unknown|unspecified|"
    r"miles?|kilomet(?:er|re)s?|km)\b", re.I)
PLACEHOLDERS = {"", "unknown", "unspecified", "none", "null", "na", "n a", "?", "-", "--"}


def text(value):
    return re.sub(r"\s+", " ", html.unescape(str(value or "")).replace("\\,", ",")).strip()


def name_key(value):
    normalized = unicodedata.normalize("NFKD", text(value).casefold())
    return "".join(c for c in normalized if c.isalnum() and not unicodedata.combining(c))


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def pin(path):
    path = Path(path)
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha_file(path)}


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf8")


def references(country_info, admin1_info):
    countries, admins = {}, defaultdict(dict)
    for line in Path(country_info).read_text(encoding="utf8").splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) >= 5:
            for alias in (fields[0], fields[1], fields[4]):
                countries[name_key(alias)] = fields[0]
    for code, aliases in {
        "US": ["US", "USA", "United States", "United States of America"],
        "GB": ["UK", "United Kingdom", "Great Britain", "England", "Scotland", "Wales", "Northern Ireland"],
        "CA": ["Canada"], "AU": ["Australia"],
    }.items():
        for alias in aliases:
            countries[name_key(alias)] = code
    for country, aliases in ADMIN1_ALIASES.items():
        for alias, code in aliases.items():
            admins[country][name_key(alias)] = code
    for line in Path(admin1_info).read_text(encoding="utf8").splitlines():
        fields = line.split("\t")
        if len(fields) >= 3 and "." in fields[0]:
            country, code = fields[0].split(".", 1)
            for alias in fields[1:3]:
                admins[country][name_key(alias)] = code
            # Alphabetic US and GB codes are unambiguous within their country;
            # numeric GeoNames codes are not assumed to be source abbreviations.
            if country in ("US", "GB") and code.isalpha():
                admins[country][name_key(code)] = code
    return countries, dict(admins)


def locality_variants(label):
    variants = {name_key(label): {"label": label, "kind": "literal_normalization"}}
    expanded = re.sub(r"^(st|ft|mt)\.?\s+", lambda match: {
        "st": "Saint ", "ft": "Fort ", "mt": "Mount "
    }[match[1].lower()], label, flags=re.I)
    if expanded != label:
        variants.setdefault(name_key(expanded), {"label": expanded, "kind": "registered_prefix_expansion"})
    return [{"key": key, **value} for key, value in variants.items() if len(key) >= 3]


def parse_location(value, countries, admins):
    """Return reversible research queries; neither parsing nor a match approves a point."""
    original = str(value or "")
    label = text(original)
    result = {"original": original, "normalized": label, "steps": [], "holds": [], "queries": []}
    if label != original:
        result["steps"].append("whitespace_html_or_escaped_comma_normalized")
    if label.casefold() in PLACEHOLDERS:
        result["holds"].append("missing_location_text")
        return result
    if "\ufffd" in label or re.search(r"[\u2500-\u259f]", label):
        result["holds"].append("damaged_location_text")
        return result
    # A comma inside a parenthesis belongs to its qualifier, not the outer
    # jurisdiction fields. Unbalanced/nested forms need direct source review.
    if label.count("(") != label.count(")") or re.search(r"\([^)]*\(", label):
        result["holds"].append("unbalanced_or_nested_qualifier")
        return result
    parts = [text(part) for part in re.split(r",(?![^()]*\))", label)]
    while len(parts) > 1 and not parts[-1]:
        parts.pop()
        result["steps"].append("empty_trailing_field_retained_in_original")
    if len(parts) < 2:
        result["holds"].append("country_only" if name_key(label) in countries else "explicit_country_missing")
        return result
    country = countries.get(name_key(parts[-1]))
    if not country:
        result["holds"].append("explicit_country_unrecognized")
        return result
    result["country"] = country
    result["countryToken"] = parts[-1]
    city = parts[0]
    admin_tokens = [token for token in parts[1:-1] if token.casefold() not in PLACEHOLDERS]
    explicit_admins = set()
    # Subcountry names such as Scotland narrow the same GB country authority.
    if country == "GB" and name_key(parts[-1]) in admins.get(country, {}):
        explicit_admins.add(admins[country][name_key(parts[-1])])
    for token in admin_tokens:
        token_key = name_key(token)
        if countries.get(token_key) == country:
            if token_key in admins.get(country, {}):
                explicit_admins.add(admins[country][token_key])
            result["steps"].append("repeated_country_field:" + token)
        elif token_key in admins.get(country, {}):
            explicit_admins.add(admins[country][token_key])
        else:
            result["holds"].append("unrecognized_admin_field:" + token)
    qualifier = re.fullmatch(r"(.+?)\s*\(([^()]*)\)", city)
    if qualifier:
        city, qualifier_text = text(qualifier[1]), text(qualifier[2])
        result["qualifier"] = qualifier_text
        tokens = [text(token) for token in re.split(r"[/,]", qualifier_text) if text(token)]
        recognized = []
        for token in tokens:
            token_key = name_key(token)
            if token_key == name_key(city):
                recognized.append("repeated_city")
            elif token_key in countries:
                if countries[token_key] != country:
                    result["holds"].append("conflicting_qualifier_country:" + token)
                else:
                    recognized.append("repeated_country")
                    if token_key in admins.get(country, {}):
                        explicit_admins.add(admins[country][token_key])
            elif token_key in admins.get(country, {}):
                explicit_admins.add(admins[country][token_key])
                recognized.append("explicit_admin")
            else:
                result["holds"].append("unresolved_parenthetical_role:" + token)
        if len(recognized) == len(tokens) and tokens:
            result["steps"].append("qualified_label_resolved:" + "+".join(recognized))
        else:
            result["steps"].append("base_locality_retained_for_research_with_qualifier_hold")
    elif "(" in city or ")" in city:
        result["holds"].append("unsupported_qualifier_structure")
        return result
    if len(explicit_admins) > 1:
        result["holds"].append("conflicting_explicit_admins")
        return result
    if any(reason.startswith("conflicting_qualifier_country:") for reason in result["holds"]):
        return result
    admin = next(iter(explicit_admins), None)
    result["admin1"] = admin
    result["adminTokens"] = admin_tokens
    if country in ("US", "CA", "AU") and not admin:
        result["holds"].append("state_or_province_missing_requires_source_review")
    if not city or len(name_key(city)) < 3 or not any(c.isalpha() for c in city):
        result["holds"].append("missing_or_nonlocality_city")
        return result
    if name_key(city) in countries or name_key(city) in admins.get(country, {}):
        result["holds"].append("country_or_admin_as_city")
        return result
    if any(c in city for c in "?[]0123456789"):
        result["holds"].append("numeric_or_damaged_locality_requires_source_review")
    if ROLE_WORDS.search(city):
        result["holds"].append("route_area_facility_or_observer_role_requires_review")
    def add_query(place, scope):
        variants = locality_variants(place)
        if variants:
            result["queries"].append({"locality": place, "scope": scope,
                                      "country": country, "admin1": admin, "variants": variants})
    add_query(city, "whole_label")
    if "/" in city:
        result["holds"].append("compound_places_require_source_review")
        for part in [text(part) for part in city.split("/")]:
            if part:
                add_query(part, "slash_component")
    elif re.fullmatch(r"[^-]+-[^-]+", city):
        # A hyphen can be part of a real name (Saint-Louis) or a compound region
        # (Keaau-Pahoa). Keep the whole-name query and investigate each component.
        for part in city.split("-"):
            if len(name_key(part)) >= 3:
                add_query(text(part), "hyphen_component")
        if len(result["queries"]) > 1:
            result["steps"].append("hyphen_components_retained_separately_for_review")
    return result


def iter_rows(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or row.get("event_id") is None:
                raise ValueError(f"Invalid summary at line {line_number}")
            yield row


def read_previous(screen_path=None, review_path=None):
    previous = {}
    if screen_path and Path(screen_path).exists():
        screen = json.loads(Path(screen_path).read_bytes())
        for query in screen.get("queries", []):
            for row in query.get("rows", []):
                previous.setdefault(str(row["event_id"]), {})["authorityScreen"] = query["screen"]
    if review_path and Path(review_path).exists():
        review = json.loads(Path(review_path).read_bytes())
        for row in review.get("rejections", []):
            previous.setdefault(str(row["event_id"]), {})["sourceHold"] = row["reason"]
    return previous


def query_id(query):
    identity = {key: query[key] for key in ("locality", "country", "admin1", "variants")}
    return "place-" + hashlib.sha256(json_bytes(identity)).hexdigest()[:24]


def scan_geonames(path, queries, area_authorities=None):
    """One record pass over the cached archive; never use an existing report point."""
    wanted = defaultdict(list)
    for identity, query in queries.items():
        query["features"] = {}
        for variant in query["variants"]:
            wanted[variant["key"]].append(identity)
    wanted_keys = wanted.keys()
    stats = Counter()
    before = Path(path).stat()
    with zipfile.ZipFile(path) as archive, archive.open("allCountries.txt") as handle:
        for raw in handle:
            stats["gazetteerRowsRead"] += 1
            fields = raw.decode("utf8").rstrip("\r\n").split("\t")
            if len(fields) < 19:
                continue
            if area_authorities is not None and fields[6] == "A" and fields[7] in AREA_FEATURES:
                lat, lon = float(fields[4]), float(fields[5])
                if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
                    area_authorities.append({
                        "geonameId": fields[0], "name": fields[1], "asciiName": fields[2],
                        "alternateNames": fields[3].split(",") if fields[3] else [],
                        "lat": lat, "lon": lon, "featureClass": fields[6], "featureCode": fields[7],
                        "country": fields[8], "admin1": fields[10], "admin2": fields[11],
                        "population": int(fields[14] or 0), "modified": fields[18],
                        "authorityUrl": "https://www.geonames.org/" + fields[0] + "/",
                        "sourceLineSha256": hashlib.sha256(raw).hexdigest(),
                        "coordinateRole": "administrative_reference_not_observation_position",
                    })
            if fields[6] != "P":
                continue
            primary = {name_key(fields[1]), name_key(fields[2])}
            alternate = {name_key(name) for name in fields[3].split(",") if name}
            hits = (primary | alternate) & wanted_keys
            if not hits:
                continue
            for hit in hits:
                for identity in wanted[hit]:
                    query = queries[identity]
                    if query["country"] != fields[8] or (query["admin1"] and query["admin1"] != fields[10]):
                        continue
                    try:
                        lat, lon = float(fields[4]), float(fields[5])
                    except ValueError:
                        stats["invalidAuthorityCoordinates"] += 1
                        continue
                    if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
                        stats["invalidAuthorityCoordinates"] += 1
                        continue
                    feature = query["features"].setdefault(fields[0], {
                        "geonameId": fields[0], "name": fields[1], "asciiName": fields[2],
                        "lat": lat, "lon": lon, "featureClass": fields[6], "featureCode": fields[7],
                        "country": fields[8], "admin1": fields[10], "admin2": fields[11],
                        "population": int(fields[14] or 0), "modified": fields[18],
                        "authorityUrl": "https://www.geonames.org/" + fields[0] + "/",
                        "sourceLineSha256": hashlib.sha256(raw).hexdigest(), "nameMatches": [],
                    })
                    match = {"key": hit, "kind": "primary_or_ascii" if hit in primary else "alternate"}
                    if match not in feature["nameMatches"]:
                        feature["nameMatches"].append(match)
    after = Path(path).stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("GeoNames input changed during screening")
    stats["gazetteerRecordPasses"] = 1
    for query in queries.values():
        query["features"] = sorted(query["features"].values(), key=lambda feature: int(feature["geonameId"]))
        classify_query(query)
    return dict(stats)


def distance_km(a, b):
    la, lb = math.radians(a["lat"]), math.radians(b["lat"])
    dl = math.radians(a["lon"] - b["lon"])
    return 12742 * math.asin(min(1, math.sqrt(math.sin((la-lb)/2)**2 + math.cos(la)*math.cos(lb)*math.sin(dl/2)**2)))


def classify_query(query):
    features = query["features"]
    # Every same-name feature, including alternates/unsupported subclasses,
    # participates in ambiguity checks. Never select the biggest city.
    diameter = max((distance_km(a, b) for i, a in enumerate(features) for b in features[i+1:]), default=0)
    supported = [feature for feature in features if feature["featureCode"] in SUPPORTED_FEATURES]
    has_primary = any(match["kind"] == "primary_or_ascii" for feature in supported for match in feature["nameMatches"])
    if not features:
        screen = "no_exact_populated_place_match"
    elif diameter > 4:
        screen = "ambiguous_separate_localities"
    elif not supported:
        screen = "unsupported_populated_place_feature"
    elif not has_primary:
        screen = "alternate_name_cluster_requires_identity_review"
    else:
        screen = "small_primary_name_locality_cluster_requires_source_review"
    query["screen"] = screen
    query["maximumClusterDistanceKm"] = round(diameter, 6)
    query["candidateIds"] = [feature["geonameId"] for feature in features]
    query["accepted"] = False
    query["coordinateRole"] = "gazetteer_locality_reference_candidate_not_observer_or_object_position"
    return query


def compound_area_candidate(parsed, queries, maximum_diameter_km=100, locality_buffer_km=10):
    """Describe a bounded candidate area, never invent a measured midpoint point.

    The explicit buffer is a display/generalization convention, not a surveyed
    city boundary or a statistical confidence interval. Full narrative review
    must establish that the report actually concerns this area.
    """
    if not parsed.get("admin1") or parsed.get("holds") and any(
        not reason.startswith("compound_places_require_source_review") for reason in parsed["holds"]
    ):
        return None
    refs = parsed["queryRefs"]
    whole = [queries[item["queryId"]] for item in refs if item["scope"] == "whole_label"]
    if any(query["features"] for query in whole):
        # A real hyphenated locality takes precedence; do not reinterpret it as
        # an area between names merely because each piece also names a town.
        return None
    components = [queries[item["queryId"]] for item in refs if item["scope"] in ("slash_component", "hyphen_component")]
    if len(components) < 2 or any(not query["screen"].startswith("small_primary_name") for query in components):
        return None
    features = {feature["geonameId"]: feature for query in components for feature in query["features"]}
    if len(features) < 2:
        return None
    anchors = list(features.values())
    diameter = max(distance_km(a,b) for i,a in enumerate(anchors) for b in anchors[i+1:])
    if diameter > maximum_diameter_km:
        return None
    # Spherical mean avoids a bogus Greenwich center for dateline localities.
    vectors = [(math.cos(math.radians(f["lat"]))*math.cos(math.radians(f["lon"])),
                math.cos(math.radians(f["lat"]))*math.sin(math.radians(f["lon"])),
                math.sin(math.radians(f["lat"]))) for f in anchors]
    x,y,z = (sum(vector[i] for vector in vectors)/len(vectors) for i in range(3))
    center = {"lat":math.degrees(math.atan2(z, math.hypot(x,y))), "lon":math.degrees(math.atan2(y,x))}
    anchor_radius = max(distance_km(center, feature) for feature in anchors)
    return {
        "accepted":False,"needsFullSourceReview":True,"locationPrecision":"approximate",
        "coordinateRole":"bounded_named_locality_area_reference_not_observed_position",
        "label":"Approximate area: " + " / ".join(query["locality"] for query in components),
        "center":{"lat":round(center["lat"],3),"lon":round(center["lon"],3)},
        "radiusKm":math.ceil(anchor_radius + locality_buffer_km + 0.2),
        "anchorDiameterKm":round(diameter,3),"maximumAnchorDiameterKm":maximum_diameter_km,
        "localityReferenceBufferKm":locality_buffer_km,"country":parsed["country"],"admin1":parsed["admin1"],
        "componentEvidence":[{"queryId":query["queryId"],"locality":query["locality"],"geonameIds":query["candidateIds"]} for query in components],
        "uncertaintyStatement":"Envelope contains named locality reference anchors plus a stated display buffer; it is not an administrative boundary, measured sighting location, or statistical confidence radius.",
    }


def prioritize(parsed, queries, prior):
    whole = [queries[item["queryId"]] for item in parsed["queryRefs"] if item["scope"] == "whole_label"]
    matching = [query for query in whole if query["features"]]
    components = [queries[item["queryId"]] for item in parsed["queryRefs"] if item["scope"] != "whole_label"]
    if prior.get("sourceHold"):
        return 15, "prior_source_hold_requires_new_evidence"
    if any(reason.startswith(("unresolved_parenthetical_role:", "unrecognized_admin_field:", "route_area_", "numeric_or_")) for reason in parsed["holds"]):
        return (20 if matching or any(query["features"] for query in components) else 0), "qualified_role_requires_source_review"
    if "compound_places_require_source_review" in parsed["holds"] or (not matching and any(query["features"] for query in components)):
        return 30, "compound_place_components_require_source_review"
    if not matching:
        return 0, "no_locality_candidate"
    if any(query["screen"] == "ambiguous_separate_localities" for query in matching):
        return 25, "same_name_locality_ambiguity"
    if any(query["screen"].startswith("alternate_name") for query in matching):
        return 45, "alternate_name_identity_review"
    if all(query["screen"].startswith("small_primary_name") for query in matching):
        if any(reason.startswith("state_or_province_missing") for reason in parsed["holds"]):
            return 50, "missing_admin_context_review"
        qualified = any(step.startswith("qualified_label_resolved:") for step in parsed["steps"])
        return (80 if qualified else 65), ("new_qualified_locality_review" if qualified else "exact_locality_source_review")
    return 10, "unsupported_authority_feature_review"


class EvidenceWriter:
    """Bound all uncompressed emitted evidence, conservatively bounding disk use."""
    def __init__(self, output, maximum_bytes):
        self.output = Path(output)
        self.maximum_bytes = maximum_bytes
        self.raw_bytes = 0
        self.files = []

    def write_lines(self, name, rows):
        path = self.output / name
        with path.open("xb") as sink:
            with gzip.GzipFile(filename="", mode="wb", fileobj=sink, mtime=0, compresslevel=6) as handle:
                for row in rows:
                    data = json_bytes(row)
                    if self.raw_bytes + len(data) > self.maximum_bytes:
                        raise ValueError("Evidence cap exceeded; partial output is incomplete, not an accepted result")
                    self.raw_bytes += len(data)
                    handle.write(data)
        self.files.append(pin(path))


def run(input_path, output, geonames_zip, country_info, admin1_info,
        previous_screen=None, previous_review=None, maximum_bytes=500 * 1024**2):
    input_path, output = Path(input_path).resolve(), Path(output).resolve()
    if output == input_path.parent or output in input_path.parents:
        raise ValueError("Use a dedicated evidence directory, separate from the input")
    if maximum_bytes <= 0 or maximum_bytes > 500 * 1024**2:
        raise ValueError("Evidence cap must be between 1 and 500 MiB")
    names = ("query-evidence.jsonl.gz", "record-review.jsonl.gz", "receipt.json", "area-authorities.jsonl.gz")
    if any((output / name).exists() for name in names):
        raise ValueError("Refusing to overwrite existing recovery evidence")
    countries, admins = references(country_info, admin1_info)
    prior = read_previous(previous_screen, previous_review)
    rows, parsed_labels, queries, identifiers = [], {}, {}, set()
    counts = Counter()
    for row in iter_rows(input_path):
        identity = str(row["event_id"])
        if identity in identifiers:
            raise ValueError("Duplicate event ID in audit input: " + identity)
        identifiers.add(identity)
        counts["inputRows"] += 1
        if row.get("has_coordinates"):
            raise ValueError("Input must contain unresolved rows only; mapped reports are not a location authority")
        raw_label = str(row.get("location_raw") or "")
        if raw_label not in parsed_labels:
            parsed = parse_location(raw_label, countries, admins)
            parsed["queryRefs"] = []
            for query in parsed.pop("queries"):
                identity_key = query_id(query)
                queries.setdefault(identity_key, {"queryId": identity_key, **{k:v for k,v in query.items() if k != "scope"}})
                parsed["queryRefs"].append({"queryId": identity_key, "scope": query["scope"], "locality": query["locality"]})
            parsed_labels[raw_label] = parsed
        rows.append({"eventId": row["event_id"], "chunkId": row.get("chunk_id"), "detailIndex": row.get("detail_index"),
                     "guards": {key: row.get(key) for key in GUARD_FIELDS}, "label": raw_label})
    print(json.dumps({"stage":"queries_prepared","records":len(rows),"labels":len(parsed_labels),"queries":len(queries)}), flush=True)
    inputs = {name: pin(path) for name, path in {
        "unmappedSummaries": input_path, "geonames": geonames_zip,
        "countryInfo": country_info, "admin1Info": admin1_info,
    }.items()}
    for name, path in (("previousAuthorityScreen", previous_screen), ("previousSourceReview", previous_review)):
        if path and Path(path).exists():
            inputs[name] = pin(path)
    area_authorities = []
    scan_counts = scan_geonames(geonames_zip, queries, area_authorities)
    output.mkdir(parents=True, exist_ok=True)
    writer = EvidenceWriter(output, maximum_bytes)
    writer.write_lines(names[0], (queries[key] for key in sorted(queries)))
    writer.write_lines(names[3], sorted(area_authorities, key=lambda row:int(row["geonameId"])))
    by_lane, by_source, by_hold = Counter(), Counter(), Counter()
    def reviewed_rows():
        for row in rows:
            parsed = parsed_labels[row.pop("label")]
            previous = prior.get(str(row["eventId"]), {})
            priority, lane = prioritize(parsed, queries, previous)
            by_lane[lane] += 1
            by_source[row["guards"]["source"] or "unknown"] += 1
            by_hold.update(parsed["holds"])
            has_candidates = any(queries[item["queryId"]]["candidateIds"] for item in parsed["queryRefs"])
            counts["rowsWithAnyIndependentLocalityCandidate" if has_candidates else "rowsWithoutLocalityCandidates"] += 1
            area = compound_area_candidate(parsed, queries)
            if area:
                counts["compoundAreaCandidatesRequiringSourceReview"] += 1
            yield {**row, "parsedLocation": parsed, "previousReview": previous, "reviewPriority": priority,
                   "reviewLane": lane, "accepted": False, "needsFullSourceReview": True,
                   "approximateAreaCandidate":area,
                   "reason": "Candidates are geographic references only; source location and observer role are unverified."}
    writer.write_lines(names[1], reviewed_rows())
    receipt = {"schemaId":SCHEMA,"completedUtc":datetime.now(timezone.utc).isoformat(),"status":"candidate_screen_complete",
               "counts":dict(counts),"scan":scan_counts,"distinctLabels":len(parsed_labels),"distinctQueries":len(queries),
               "reviewLanes":dict(by_lane.most_common()),"sourceCounts":dict(by_source.most_common()),
               "holds":dict(by_hold.most_common()),"inputs":inputs,"outputs":writer.files,
               "acceptedDecisions":0,"sourceCorpusMutated":False,"mappedCopiesUsedAsEvidence":False,
               "priorityPolicy":"Scheduling bands only, not confidence or approval. Prior source holds outrank a new name match. No majority/population winner is selected.",
               "precisionPolicy":"A locality candidate is not an exact observer or craft position. Compound components are separate evidence; any envelope center belongs to an explicitly approximate area, never a measured point.",
               "storage":{"outputBytes":sum(item["bytes"] for item in writer.files),"uncompressedEvidenceBytes":writer.raw_bytes,
                          "maximumUncompressedEvidenceBytes":maximum_bytes,"newFilesAbove100MiB":[item["path"] for item in writer.files if item["bytes"]>100*1024**2],
                          "retention":"Retain this candidate evidence, source pins, and rejects until reviewed decisions and a complete unresolved ledger supersede them; no full corpus copy or deletion."}}
    (output / "receipt.json").write_bytes(json_bytes(receipt))
    print(json.dumps({"status":receipt["status"],"counts":receipt["counts"],"reviewLanes":receipt["reviewLanes"],"outputBytes":receipt["storage"]["outputBytes"]}),flush=True)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Full current unmapped summaries, JSONL or JSONL.gz")
    parser.add_argument("--output", type=Path, required=True, help="Dedicated review directory on D: for this data-heavy task")
    parser.add_argument("--geonames-zip", type=Path, default=SHARED/"cache/map_overlays/allCountries.zip")
    parser.add_argument("--country-info", type=Path, default=SHARED/"cache/map_overlays/countryInfo.txt")
    parser.add_argument("--admin1-info", type=Path, default=PREVIOUS/"admin1CodesASCII.txt")
    parser.add_argument("--previous-screen", type=Path, default=PREVIOUS/"gazetteer_screen.json")
    parser.add_argument("--previous-review", type=Path, default=PREVIOUS/"full_source_review_census.json")
    parser.add_argument("--max-output-mib", type=int, default=500)
    args = parser.parse_args()
    run(args.input,args.output,args.geonames_zip,args.country_info,args.admin1_info,
        args.previous_screen,args.previous_review,args.max_output_mib*1024**2)


if __name__ == "__main__":
    main()
