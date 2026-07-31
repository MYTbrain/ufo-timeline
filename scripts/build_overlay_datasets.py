"""Fetch and preprocess optional static map overlays for the public bundle."""

from __future__ import annotations

from datetime import datetime, timezone
import argparse
import json
import math
from pathlib import Path
import re
import time
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import zipfile


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIRS = [
    ROOT / "webapp" / "static_public" / "data" / "map_overlays",
    ROOT / "static_bundle" / "data" / "map_overlays",
]
CACHE_DIR = ROOT / "cache" / "map_overlays"

AIRPORTS_URL = "https://d2ad6b4ur7yvpq.cloudfront.net/naturalearth-3.3.0/ne_10m_airports.geojson"
HIGHWAYS_QUERY_URL = "https://services.arcgis.com/P3ePLMYs2RVChkJx/ArcGIS/rest/services/USA_Freeway_System/FeatureServer/1/query"
GEONAMES_ALL_COUNTRIES_URL = "https://download.geonames.org/export/dump/allCountries.zip"
GEONAMES_COUNTRY_INFO_URL = "https://download.geonames.org/export/dump/countryInfo.txt"

USER_AGENT = "UFO-Timeline-Overlay-Build/3.0"
DOWNLOAD_CHUNK_BYTES = 1024 * 1024
GEONAMES_PROGRESS_INTERVAL = 1_000_000
MILITARY_DEDUPE_DISTANCE_KM = 5.5

MILITARY_BRANCH_RULES = {
    "air": {
        "feature_codes": {"S.AIRB"},
        "name_patterns": [
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"\bair\s*base\b",
                r"\bairfield\b",
                r"\bair\s*station\b",
                r"\bair\s*force\b",
                r"\baviation\b",
                r"\braf\b",
                r"\bafb\b",
                r"\bwing\b",
            )
        ],
    },
    "naval": {
        "feature_codes": {"L.NVB", "S.STNC"},
        "name_patterns": [
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"\bnaval\b",
                r"\bnavy\b",
                r"\bfleet\b",
                r"\bdockyard\b",
                r"\bcoast guard\b",
                r"\bmarine corps\b",
                r"\bsubmarine\b",
                r"\bshipyard\b",
                r"\bsea base\b",
            )
        ],
    },
    "army": {
        "feature_codes": {"S.BRKS"},
        "name_patterns": [
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"\barmy\b",
                r"\bbarracks\b",
                r"\bgarrison\b",
                r"\bcamp\b",
                r"\bfort\b",
                r"\btraining center\b",
                r"\btraining ground\b",
                r"\bkaserne\b",
                r"\bcaserne\b",
            )
        ],
    },
}

MILITARY_FEATURE_LABELS = {
    "S.AIRB": "Air base",
    "L.NVB": "Naval base",
    "S.STNC": "Coast guard station",
    "S.BRKS": "Barracks",
    "L.MILB": "Military base",
}

MILITARY_BRANCH_LABELS = {
    "air": "Air base",
    "naval": "Naval base",
    "army": "Army base",
    "other": "Other / unknown",
}

GEONAMES_MILITARY_FEATURE_CODES = frozenset(MILITARY_FEATURE_LABELS)


def fetch_json(url: str):
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    with urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def attribute_value(properties: dict, *names: str):
    for name in names:
        if name in properties and properties[name] not in (None, ""):
            return properties[name]
        upper = name.upper()
        if upper in properties and properties[upper] not in (None, ""):
            return properties[upper]
        lower = name.lower()
        if lower in properties and properties[lower] not in (None, ""):
            return properties[lower]
    return None


def simplify_line(coords: list, max_points: int = 64) -> list:
    if len(coords) <= max_points:
        return coords
    step = max(2, math.ceil(len(coords) / max_points))
    simplified = [coords[0]]
    simplified.extend(coords[index] for index in range(step, len(coords) - 1, step))
    if simplified[-1] != coords[-1]:
        simplified.append(coords[-1])
    return simplified


def arcgis_count(query_url: str) -> int:
    params = urlencode(
        {
            "where": "1=1",
            "returnCountOnly": "true",
            "f": "json",
        }
    )
    payload = fetch_json(f"{query_url}?{params}")
    if payload.get("error"):
        print(f"ArcGIS count error for {query_url}: {payload['error']}")
    return int(payload.get("count") or 0)


def arcgis_query_features(
    query_url: str,
    *,
    out_fields: list[str],
    batch_size: int = 1000,
) -> list[dict]:
    total = arcgis_count(query_url)
    features: list[dict] = []
    offset = 0
    while True:
        params_dict = {
            "where": "1=1",
            "outFields": ",".join(out_fields),
            "returnGeometry": "true",
            "f": "json",
            "outSR": "4326",
        }
        if total > batch_size:
            params_dict["resultOffset"] = str(offset)
            params_dict["resultRecordCount"] = str(batch_size)
        params = urlencode(params_dict)
        payload = fetch_json(f"{query_url}?{params}")
        if payload.get("error"):
            print(f"ArcGIS query error for {query_url}: {payload['error']}")
            break
        batch = payload.get("features") or []
        if not batch:
            if offset == 0:
                print(f"No ArcGIS features returned from {query_url}. Payload keys: {sorted(payload.keys())}")
            break
        features.extend(batch)
        print(f"Fetched {len(features):,} / {total or len(features):,} features from {query_url}")
        if len(batch) < batch_size:
            break
        offset += len(batch)
        time.sleep(0.2)
    return features


def arcgis_polyline_to_geojson(geometry: dict | None) -> dict | None:
    if not geometry:
        return None
    paths = geometry.get("paths") or []
    if not paths:
        return None
    simplified_paths = [simplify_line(path) for path in paths if isinstance(path, list) and path]
    if not simplified_paths:
        return None
    if len(simplified_paths) == 1:
        return {"type": "LineString", "coordinates": simplified_paths[0]}
    return {"type": "MultiLineString", "coordinates": simplified_paths}


def build_airports() -> dict:
    payload = fetch_json(AIRPORTS_URL)
    features = []
    for feature in payload.get("features") or []:
        properties = feature.get("properties") or {}
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "name": properties.get("name") or properties.get("NAME") or "Unnamed airport",
                    "scalerank": properties.get("scalerank"),
                    "iata": properties.get("iata_code") or properties.get("iata"),
                },
                "geometry": feature.get("geometry"),
            }
        )
    return {"type": "FeatureCollection", "features": features}


def build_highways() -> dict:
    raw_features = arcgis_query_features(
        HIGHWAYS_QUERY_URL,
        out_fields=["*"],
        batch_size=900,
    )
    features = []
    for feature in raw_features:
        geometry = arcgis_polyline_to_geojson(feature.get("geometry"))
        if not geometry:
            continue
        properties = feature.get("attributes") or {}
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "route_num": attribute_value(properties, "route_num", "sign1", "sign", "number"),
                    "route_name": attribute_value(properties, "route_name", "name", "streetname", "route"),
                },
                "geometry": geometry,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def download_to_cache(url: str, destination: Path, label: str) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        print(f"Using cached {label}: {destination.name} ({destination.stat().st_size:,} bytes)")
        return destination

    attempt = 0
    while attempt < 3:
        attempt += 1
        try:
            temp_path = destination.with_suffix(destination.suffix + ".part")
            if temp_path.exists():
                temp_path.unlink()

            print(f"Downloading {label} (attempt {attempt}/3): {url}")
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=900) as response, temp_path.open("wb") as handle:
                while True:
                    chunk = response.read(DOWNLOAD_CHUNK_BYTES)
                    if not chunk:
                        break
                    handle.write(chunk)
            temp_path.replace(destination)
            print(f"Saved {label}: {destination.name} ({destination.stat().st_size:,} bytes)")
            return destination
        except (HTTPError, URLError, TimeoutError) as error:
            print(f"Download failed for {label}: {error}")
            time.sleep(2.0 * attempt)

    raise RuntimeError(f"Unable to download {label}: {url}")


def load_country_names(country_info_path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for raw_line in country_info_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = raw_line.split("\t")
        if len(parts) < 5:
            continue
        iso_code = parts[0].strip().upper()
        country_name = parts[4].strip()
        if iso_code and country_name:
            mapping[iso_code] = country_name
    return mapping


def iter_geonames_rows(archive_path: Path) -> Iterable[list[str]]:
    with zipfile.ZipFile(archive_path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".txt")]
        if not members:
            raise FileNotFoundError(f"No .txt member found in {archive_path}")
        with archive.open(members[0]) as handle:
            for raw_line in handle:
                yield raw_line.decode("utf-8", errors="replace").rstrip("\n").split("\t")


def normalize_text(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").strip().lower()).strip()


def geonames_feature_key(feature_class: str, feature_code: str) -> str:
    return f"{(feature_class or '').strip().upper()}.{(feature_code or '').strip().upper()}"


def classify_military_branch(feature_key: str, name: str) -> str:
    normalized_name = normalize_text(name)
    for branch, rules in MILITARY_BRANCH_RULES.items():
        if feature_key in rules["feature_codes"]:
            return branch
        if any(pattern.search(normalized_name) for pattern in rules["name_patterns"]):
            return branch
    return "other"


def military_feature_score(feature: dict) -> tuple[int, int, int, int]:
    properties = feature.get("properties") or {}
    feature_code = properties.get("feature_code")
    branch = properties.get("branch")
    return (
        0 if branch == "other" else 1,
        1 if feature_code in {"S.AIRB", "L.NVB", "S.BRKS", "S.STNC"} else 0,
        1 if properties.get("country") else 0,
        len(properties.get("name") or ""),
    )


def approx_distance_km(coord_a: list[float], coord_b: list[float]) -> float:
    lon_a, lat_a = coord_a
    lon_b, lat_b = coord_b
    lat_scale = 111.32
    lon_scale = 111.32 * math.cos(math.radians((lat_a + lat_b) / 2))
    return math.hypot((lat_b - lat_a) * lat_scale, (lon_b - lon_a) * lon_scale)


def dedupe_military_features(features: list[dict]) -> list[dict]:
    ordered = sorted(features, key=military_feature_score, reverse=True)
    by_key: dict[tuple[str, str, str], list[list[float]]] = {}
    deduped: list[dict] = []

    for feature in ordered:
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        if len(coordinates) < 2:
            continue
        dedupe_key = (
            normalize_text(properties.get("name")),
            str(properties.get("country_code") or ""),
            str(properties.get("branch") or "other"),
        )
        if not dedupe_key[0]:
            continue
        prior_coords = by_key.setdefault(dedupe_key, [])
        if any(approx_distance_km(coordinates, earlier) <= MILITARY_DEDUPE_DISTANCE_KM for earlier in prior_coords):
            continue
        deduped.append(feature)
        prior_coords.append(coordinates)

    deduped.sort(
        key=lambda feature: (
            str((feature.get("properties") or {}).get("country") or ""),
            str((feature.get("properties") or {}).get("name") or ""),
            str((feature.get("properties") or {}).get("source_id") or ""),
        )
    )
    return deduped


def build_military_bases() -> tuple[dict, dict]:
    geonames_archive = download_to_cache(
        GEONAMES_ALL_COUNTRIES_URL,
        CACHE_DIR / "allCountries.zip",
        "GeoNames allCountries archive",
    )
    country_info_path = download_to_cache(
        GEONAMES_COUNTRY_INFO_URL,
        CACHE_DIR / "countryInfo.txt",
        "GeoNames country info",
    )
    country_names = load_country_names(country_info_path)

    features: list[dict] = []
    kept_feature_codes: dict[str, int] = {}
    scanned_rows = 0
    started = time.monotonic()

    for row in iter_geonames_rows(geonames_archive):
        scanned_rows += 1
        if scanned_rows % GEONAMES_PROGRESS_INTERVAL == 0:
            elapsed = max(time.monotonic() - started, 0.001)
            print(f"Scanned {scanned_rows:,} GeoNames rows in {elapsed:,.1f}s; kept {len(features):,} military records")

        if len(row) < 19:
            continue

        feature_key = geonames_feature_key(row[6], row[7])
        if feature_key not in GEONAMES_MILITARY_FEATURE_CODES:
            continue

        name = (row[1] or row[2] or "").strip()
        if not name:
            continue

        try:
            lat = float(row[4])
            lon = float(row[5])
        except ValueError:
            continue

        country_code = row[8].strip().upper()
        branch = classify_military_branch(feature_key, name)
        feature_type = MILITARY_FEATURE_LABELS.get(feature_key, feature_key)
        country_name = country_names.get(country_code) or country_code or None
        geoname_id = row[0].strip()

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "name": name,
                    "country": country_name,
                    "country_code": country_code or None,
                    "branch": branch,
                    "branch_label": MILITARY_BRANCH_LABELS.get(branch, MILITARY_BRANCH_LABELS["other"]),
                    "type": feature_type,
                    "feature_code": feature_key,
                    "source_id": f"geonames:{geoname_id}" if geoname_id else None,
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat],
                },
            }
        )
        kept_feature_codes[feature_key] = kept_feature_codes.get(feature_key, 0) + 1

    if not features:
        raise RuntimeError("No global military installation points were found in GeoNames.")

    deduped = dedupe_military_features(features)
    branch_counts: dict[str, int] = {}
    for feature in deduped:
        branch = feature.get("properties", {}).get("branch") or "other"
        branch_counts[branch] = branch_counts.get(branch, 0) + 1

    metadata = {
        "source": f"{GEONAMES_ALL_COUNTRIES_URL} + {GEONAMES_COUNTRY_INFO_URL}",
        "rawFeatureCount": len(features),
        "featureCount": len(deduped),
        "featureCodes": kept_feature_codes,
        "branchCounts": branch_counts,
        "notes": (
            "Global military installations are built from GeoNames point records only. "
            "Allowed feature codes are filtered to AIRB, BRKS, STNC, NVB, and MILB; "
            "MILB records are branch-classified from centralized name rules when possible. "
            "Nearby duplicate names within the same country/branch are collapsed conservatively."
        ),
    }
    return {"type": "FeatureCollection", "features": deduped}, metadata


def build_metadata(airports: dict, highways: dict, military: dict, military_metadata: dict) -> dict:
    return {
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "datasets": {
            "airports": {
                "source": AIRPORTS_URL,
                "featureCount": len(airports.get("features") or []),
                "notes": "Natural Earth airport points with trimmed properties.",
            },
            "highways": {
                "source": HIGHWAYS_QUERY_URL,
                "featureCount": len(highways.get("features") or []),
                "notes": "ArcGIS Interstate Highway System lines with lightweight coordinate decimation.",
            },
            "military_bases": military_metadata | {
                "featureCount": len(military.get("features") or []),
                "branchRules": {
                    branch: {
                        "featureCodes": sorted(rules["feature_codes"]),
                        "namePatterns": [pattern.pattern for pattern in rules["name_patterns"]],
                    }
                    for branch, rules in MILITARY_BRANCH_RULES.items()
                },
            },
        },
    }


def build_overlay_readme(metadata: dict) -> str:
    military = metadata["datasets"]["military_bases"]
    return (
        "Static map overlays for the UFO Timeline World Map.\n\n"
        "Sources\n"
        f"- Airports: {metadata['datasets']['airports']['source']}\n"
        f"- Highways / interstates: {metadata['datasets']['highways']['source']}\n"
        f"- Military bases: {military['source']}\n\n"
        "Notes\n"
        "- Airports are lightweight Natural Earth point features.\n"
        "- Highways are simplified ArcGIS interstate lines.\n"
        "- Military installations are global point records derived from GeoNames and normalized into air / naval / army / other branches.\n"
        "- Runtime uses points and lines only; no large military land polygons are shipped in the public bundle.\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--webapp-only", action="store_true", help="Write only to webapp/static_public and skip static_bundle.")
    args = parser.parse_args()

    output_dirs = OUTPUT_DIRS[:1] if args.webapp_only else OUTPUT_DIRS
    for directory in output_dirs:
        directory.mkdir(parents=True, exist_ok=True)

    airports = build_airports()
    highways = build_highways()
    military, military_metadata = build_military_bases()
    metadata = build_metadata(airports, highways, military, military_metadata)
    readme_text = build_overlay_readme(metadata)

    for directory in output_dirs:
        write_json(directory / "airports.geojson", airports)
        write_json(directory / "highways.geojson", highways)
        write_json(directory / "military_bases.geojson", military)
        write_json(directory / "overlay_sources.json", metadata)
        write_text(directory / "README.txt", readme_text)

    for name, payload in (("airports", airports), ("highways", highways), ("military_bases", military)):
        print(f"{name}: {len(payload.get('features') or []):,} features")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
