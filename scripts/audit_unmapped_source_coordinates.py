"""Screen every unmapped source record for original coordinate evidence.

Consumes the manifest-pinned sparse audit, not historical full-corpus previews.
This is a candidate/abstention ledger: no source or runtime row is modified and
no coordinate is approved automatically. In particular UFOCAT longitude/datum
conventions, composite accounts and observer/object roles require source review.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any


SCHEMA = "ufo-unmapped-source-coordinate-audit-v1"
NUMBER = r"[+-]?\d+(?:\.\d+)?"
DECIMAL = re.compile(r"^([+-]?\d+(?:\.\d+)?)\s*([NSEW])?$", re.I)
DMS = re.compile(
    r"^([+-]?\d+(?:\.\d+)?)\s*[°º]\s*(?:(\d+(?:\.\d+)?)\s*['′]\s*)?"
    r'(?:(\d+(?:\.\d+)?)\s*["″]\s*)?([NSEW])?$', re.I)
COMPONENT = r"[+-]?\d{1,3}(?:\.\d+)?(?:\s*[°º]\s*(?:\d{1,2}(?:\.\d+)?\s*['′]\s*)?(?:\d{1,2}(?:\.\d+)?\s*[\"″]\s*)?)?\s*[NSEW]"
HEMISPHERE_PAIR = re.compile(r"(?<![\w.])(" + COMPONENT + r")\s*[,;/]?\s+(" + COMPONENT + r")(?!\w)", re.I)
LABELLED_PAIR = re.compile(
    r"\blat(?:itude)?\s*[:=]?\s*(" + NUMBER + r")\s*[,;/]?\s*"
    r"(?:lon(?:gitude)?|lng)\s*[:=]?\s*(" + NUMBER + r")\b", re.I)
BARE_PAIR = re.compile(r"^\s*(" + NUMBER + r")(?:\s*[,;]\s*|\s+)(" + NUMBER + r")\s*$")
GPS_PAIR = re.compile(r"\b(?:GPS|coordinates?)\s*(?:are|were|is|was|of|at|[:=])?\s*(" + NUMBER + r")\s*[,;]\s*(" + NUMBER + r")\b", re.I)
PAIR_KEYS = {"coordinates", "coordinate", "gps", "gpscoordinates", "latlong", "latlon", "latitudelongitude", "latlongdms"}
AXIS_RE = re.compile(r"^(.*?)(latitude|longitude|lat|lon|lng)$")
NATIVE_CONTAINERS = ("raw_fields", "raw_source_row")
NON_OBSERVER = re.compile(r"publisher|office|headquarters|homeaddress|postaladdress|mailing|residenceaddress|destination|departure|object|craft|target", re.I)
REMOTE_MEDIA = re.compile(r"\b(?:google earth|google maps|youtube|webcam|live feed|livefeed|television|satellite imagery|iss footage)\b", re.I)
NON_TERRESTRIAL = {"earth orbit or seen from space stations capsules", "mars", "neptune", "pluto", "the moon"}


def key(value: Any) -> str:
    return re.sub(r"[^a-z]", "", str(value).lower())


def present(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def parse_component(value: Any, axis: str) -> tuple[float | None, str]:
    """Parse explicit decimal or unit-marked DMS; never guess compact DDMM."""
    if isinstance(value, bool) or value is None:
        return None, "missing_or_non_numeric"
    text = str(value).strip()
    match = DECIMAL.fullmatch(text)
    notation = "decimal"
    if match:
        degree, hemisphere = float(match[1]), match[2]
        number = degree
    else:
        match = DMS.fullmatch(text)
        if not match:
            return None, "unsupported_or_malformed_notation"
        degree = float(match[1])
        minutes = float(match[2] or 0)
        seconds = float(match[3] or 0)
        hemisphere = match[4]
        if minutes >= 60 or seconds >= 60 or (seconds and match[2] is None):
            return None, "invalid_minutes_or_seconds"
        if degree != math.trunc(degree) and (minutes or seconds):
            return None, "mixed_fractional_degree_notation"
        number = abs(degree) + minutes / 60 + seconds / 3600
        if degree < 0:
            number *= -1
        notation = "explicit_dms"
    if not math.isfinite(number):
        return None, "nonfinite"
    if hemisphere:
        hemisphere = hemisphere.upper()
        if hemisphere not in ({"N", "S"} if axis == "lat" else {"E", "W"}):
            return None, "hemisphere_axis_conflict"
        if degree < 0 and hemisphere in {"N", "E"}:
            return None, "sign_hemisphere_conflict"
        if text.startswith("+") and hemisphere in {"S", "W"}:
            return None, "sign_hemisphere_conflict"
        number = abs(number) * (-1 if hemisphere in {"S", "W"} else 1)
    limit = 90 if axis == "lat" else 180
    if abs(number) > limit:
        return None, "out_of_bounds_or_compact_notation"
    return number, notation


def dictionaries(value: Any, path: str):
    if isinstance(value, dict):
        yield path, value
        for name, child in value.items():
            if isinstance(child, (dict, list)):
                yield from dictionaries(child, path + "." + str(name))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, (dict, list)):
                yield from dictionaries(child, f"{path}[{index}]")


def coordinate_findings(detail: dict) -> list[dict]:
    findings = []
    for root in NATIVE_CONTAINERS:
        for path, fields in dictionaries(detail.get(root), root):
            axes = defaultdict(dict)
            for name, value in fields.items():
                normalized = key(name)
                match = AXIS_RE.fullmatch(normalized)
                if match and present(value) and not isinstance(value, (dict, list)):
                    axis = "lat" if match[2] in {"latitude", "lat"} else "lon"
                    axes[match[1]][axis] = (name, value)
                native_pair = normalized in PAIR_KEYS or normalized in {"keyvals" + name for name in PAIR_KEYS}
                if native_pair and isinstance(value, str) and present(value):
                    pair = BARE_PAIR.fullmatch(value)
                    if pair:
                        findings.append({"kind": "native_pair_field", "field_paths": [path + "." + name],
                                         "raw_values": [value], "latitude_raw": pair[1], "longitude_raw": pair[2],
                                         "role": "unverified_native_pair_axis_order"})
                    elif not HEMISPHERE_PAIR.search(value) and not LABELLED_PAIR.search(value):
                        findings.append({"kind": "unparsed_native_pair_field", "field_paths": [path + "." + name],
                                         "raw_values": [value], "role": "unverified_native_coordinate_field"})
            for prefix, pair in axes.items():
                finding = {"kind": "native_axis_fields", "field_paths": [path + "." + pair[a][0] for a in ("lat", "lon") if a in pair],
                           "raw_values": [pair[a][1] for a in ("lat", "lon") if a in pair],
                           "role": prefix or "unspecified_native_coordinate_role"}
                for axis, label in (("lat", "latitude_raw"), ("lon", "longitude_raw")):
                    if axis in pair:
                        finding[label] = pair[axis][1]
                findings.append(finding)
    # Explicit labels and hemisphere notation in retained native text only.
    seen_text = set()
    for root in NATIVE_CONTAINERS:
        for path, fields in dictionaries(detail.get(root), root):
            for name, value in fields.items():
                # Majestic's stemmed search field strips punctuation and can
                # turn ambiguous minute notation into apparent decimals.
                if key(name) == "search" or not isinstance(value, str) or value in seen_text:
                    continue
                seen_text.add(value)
                for pattern, kind in ((HEMISPHERE_PAIR, "hemisphere_text"), (LABELLED_PAIR, "labelled_text"), (GPS_PAIR, "gps_labelled_text")):
                    for match in pattern.finditer(value):
                        latitude, longitude = match[1], match[2]
                        if kind == "hemisphere_text":
                            if latitude.rstrip()[-1].upper() in "EW":
                                latitude, longitude = longitude, latitude
                        findings.append({"kind": kind, "field_paths": [path + "." + name],
                                         "raw_values": [match.group()], "latitude_raw": latitude,
                                         "longitude_raw": longitude, "role": "unverified_text_coordinate_role",
                                         "excerpt": value[max(0, match.start()-180):match.end()+180]})
    return findings


def screen_record(record: dict) -> dict:
    summary, detail = record["summary"], record["source_detail"]
    if str(summary["event_id"]) != str(detail["event_id"]):
        raise ValueError("Summary/detail identity mismatch")
    if summary.get("has_coordinates"):
        raise ValueError("Mapped record entered unmapped-coordinate audit")
    source = str(summary.get("source", "unknown"))
    findings = coordinate_findings(detail)
    flags = []
    meta = " ".join(str(summary.get(k, "")) for k in ("coordinate_source", "quality_view_changes", "coordinate_quarantine", "coordinate_review"))
    if re.search("quarantin|reject|invalid|non.terrestrial", meta, re.I):
        flags.append("existing_coordinate_review_or_quarantine")
    labels = [summary.get("location_raw"), detail.get("country")]
    raw = detail.get("raw_fields") or {}
    if isinstance(raw, dict):
        labels.extend(raw.get(k) for k in ("COUNTRY", "Country", "country", "LOCATION", "Location", "key_vals/Country"))
    if any(re.sub(r"[^a-z0-9]+", " ", str(v or "").lower()).strip() in NON_TERRESTRIAL for v in labels):
        flags.append("non_terrestrial_context")
    if int(detail.get("duplicate_record_count") or 1) > 1 or int(detail.get("source_provenance_count") or 1) > 1:
        flags.append("composite_requires_member_review")
    narrative = str(detail.get("description") or detail.get("raw_event_block") or "")
    if REMOTE_MEDIA.search(narrative):
        flags.append("remote_media_role_requires_review")
    if source == "ufocat" and findings:
        flags.append("ufocat_codebook_sign_datum_and_grid_review")
    for finding in findings:
        lat, lat_kind = parse_component(finding.get("latitude_raw"), "lat")
        lon, lon_kind = parse_component(finding.get("longitude_raw"), "lon")
        finding["latitude_parse"] = lat_kind
        finding["longitude_parse"] = lon_kind
        reasons = list(flags)
        if lat is None or lon is None:
            reasons.append("incomplete_or_unparsed_coordinate_pair")
        elif abs(lat) < 1e-9 and abs(lon) < 1e-9:
            reasons.append("zero_pair_requires_independent_evidence")
        else:
            finding["parsed_lat"] = lat
            finding["parsed_lon"] = lon
        if NON_OBSERVER.search(finding["role"]):
            reasons.append("non_observer_coordinate_role")
        finding["decision"] = "hold" if reasons else "review_candidate"
        finding["hold_reasons"] = sorted(set(reasons))
        finding["required_review"] = ["verify_source_coordinate_semantics", "verify_observer_role", "verify_declared_locality_and_jurisdiction", "preserve_original_precision_and_datum_uncertainty"]
    disposition = "no_explicit_source_coordinates"
    if findings:
        disposition = "review_candidate" if any(v["decision"] == "review_candidate" for v in findings) else "hold"
    return {"event_id": summary["event_id"], "source": source,
            "location_raw": summary.get("location_raw"), "sort_date_iso": summary.get("sort_date_iso"),
            "chunk_id": summary.get("chunk_id"), "detail_index": summary.get("detail_index"),
            "disposition": disposition, "record_flags": flags, "coordinate_findings": findings,
            "source_provenance": record.get("provenance"), "accepted": False}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit(input_path: Path, output_dir: Path, max_output_mib: int = 64) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = output_dir / "coordinate-ledger.jsonl.gz"
    evidence_path = output_dir / "coordinate-evidence.jsonl.gz"
    report_path = output_dir / "coordinate-census.json"
    if any(p.exists() for p in (ledger_path, evidence_path, report_path)):
        raise FileExistsError("Refusing to replace retained coordinate audit outputs")
    counts, sources, flags, fields = Counter(), defaultdict(Counter), Counter(), Counter()
    samples = defaultdict(list)
    with gzip.open(input_path, "rt", encoding="utf8") as source, gzip.open(ledger_path, "wt", encoding="utf8") as ledger, gzip.open(evidence_path, "wt", encoding="utf8") as evidence:
        for line in source:
            record = json.loads(line)
            result = screen_record(record)
            disposition = result["disposition"]
            counts["records_scanned"] += 1
            counts[disposition] += 1
            sources[result["source"]][disposition] += 1
            flags.update(result["record_flags"])
            brief = {k: result[k] for k in ("event_id", "source", "disposition", "record_flags")}
            brief["coordinate_finding_count"] = len(result["coordinate_findings"])
            ledger.write(json.dumps(brief, ensure_ascii=False, separators=(",", ":")) + "\n")
            if result["coordinate_findings"]:
                evidence.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
                for finding in result["coordinate_findings"]:
                    fields.update(finding["field_paths"])
                if len(samples[disposition]) < 12:
                    samples[disposition].append({k: result[k] for k in ("event_id", "source", "location_raw", "record_flags")})
            if counts["records_scanned"] % 10000 == 0:
                ledger.flush(); evidence.flush()
                if ledger_path.stat().st_size + evidence_path.stat().st_size > max_output_mib*1024**2:
                    raise RuntimeError("Coordinate audit exceeded its bounded output budget")
    report = {"schema_id": SCHEMA, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "input": {"path": str(input_path), "bytes": input_path.stat().st_size, "sha256": sha256(input_path)},
              "counts": dict(counts), "by_source": dict(sources), "record_flag_counts": dict(flags),
              "coordinate_field_counts": dict(fields.most_common()), "samples": dict(samples),
              "accepted_coordinates": 0, "runtime_mutated": False,
              "policy": "Original source evidence screen only. All candidates require independent source-role, jurisdiction, precision and convention review; no mapped-copy coordinate transfer or guessed numeric repair.",
              "outputs": [{"path": str(p), "bytes": p.stat().st_size, "sha256": sha256(p)} for p in (ledger_path, evidence_path)]}
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--max-output-mib", type=int, default=64)
    args = parser.parse_args()
    result = audit(args.input, args.output_dir, args.max_output_mib)
    print(json.dumps({"counts": result["counts"], "by_source": result["by_source"], "outputs": result["outputs"]}, indent=2))
