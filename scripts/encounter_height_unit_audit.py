"""Source-pin height-unit disagreements; never repair height from magnitude alone."""
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

ROOT = Path(__file__).resolve().parents[1]
SHARED = Path("C:/Users/jarod/Desktop/UFO Timeline map tool")
UNITS = r"(?:centimet(?:er|re)s?|cm|met(?:er|re)s?|m|feet|foot|ft|inches?|inch|in|['\"’′″])"
HEIGHT = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>" + UNITS + r")(?:\s*(?:[-–]\s*)?(?:\d+\s*(?:inches?|inch|in|[\"″])\s*)?)(?:\s*(?:-\s*)?)(?:tall|high|in\s+height)\b", re.I)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def convert_to_feet(value, unit):
    unit = unit.lower()
    if unit in {"m", "meter", "meters", "metre", "metres"}:
        return value / 0.3048, "m"
    if unit in {"cm", "centimeter", "centimeters", "centimetre", "centimetres"}:
        return value / 30.48, "cm"
    if unit in {"in", "inch", "inches", '"', "″"}:
        return value / 12, "in"
    return value, "ft"


def extract_height_assertions(text):
    result = []
    for match in HEIGHT.finditer(text or ""):
        value = float(match["value"])
        feet, unit = convert_to_feet(value, match["unit"])
        context = (text or "")[max(0, match.start() - 65):min(len(text), match.end() + 65)]
        result.append({"raw": match.group(), "value": value, "unit": unit, "convertedFeet": feet, "excerpt": context, "characterStart": match.start(), "characterEnd": match.end(), "scope": "height_assertion_requires_manual_subject_review"})
    return result


def classify_numeric_relation(indexed_feet, assertion):
    """Only identifies disagreement candidates; subject and identity need manual review."""
    val, expected = assertion["value"], assertion["convertedFeet"]
    close = lambda a, b: math.isclose(a, b, rel_tol=0.04, abs_tol=0.03)
    if close(indexed_feet, expected):
        return "agrees_with_unit_conversion_within_rounding"
    if assertion["unit"] in {"m", "cm", "in"} and close(indexed_feet, val):
        return "same_raw_number_different_unit_possible_coding_error"
    return "different_height_or_subject_requires_manual_review"


def run(output, *, root=ROOT, shared=SHARED):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Protected nonempty output exists")
    base_path = root / "data/encounters/evidence.json.gz"
    base_raw = base_path.read_bytes()
    evidence = json.loads(gzip.decompress(base_raw))
    selected = [row for row in evidence["rows"] if row.get("heightFeet") is not None]
    by_chunk = defaultdict(list)
    for row in selected:
        by_chunk[row["sourceRef"]["chunk"]].append(row)
    pins, rows, categories, scanned_bytes = [], [], Counter(), 0
    for number, (chunk, needed) in enumerate(sorted(by_chunk.items()), 1):
        path = shared / "data/canonical_web/event_chunks" / (chunk + ".json")
        payload = path.read_bytes()
        digest = sha(payload)
        scanned_bytes += len(payload)
        if any(digest != row["sourceRef"]["chunkSha256"] for row in needed):
            raise ValueError("Native chunk hash mismatch: " + str(path))
        events = json.loads(payload)
        pins.append({"path": str(path), "bytes": len(payload), "sha256": digest})
        for row in needed:
            native = events[row["sourceRef"]["detailIndex"]]
            if str(native["event_id"]) != row["eventId"] or native["source"] != row["source"]:
                raise ValueError("Native row identity mismatch")
            raw_fields = native.get("raw_source_row") or native.get("raw_fields") or {}
            upper = {str(key).upper(): value for key, value in raw_fields.items()}
            raw_height = upper.get("HEIGHT")
            if not math.isclose(float(raw_height), row["heightFeet"], abs_tol=1e-10):
                raise ValueError("Indexed height differs from original source field")
            text = str(upper.get("NOTES") or native.get("description") or "")
            assertions = extract_height_assertions(text)
            for assertion in assertions:
                assertion["numericRelation"] = classify_numeric_relation(row["heightFeet"], assertion)
                categories[assertion["numericRelation"]] += 1
            rows.append({"eventId": row["eventId"], "source": row["source"], "sourceEventId": row["sourceEventId"], "sourceRef": row["sourceRef"], "dateRaw": native.get("date_raw"), "locationRaw": native.get("location_raw"), "rawHeight": str(raw_height), "indexedHeightFeet": row["heightFeet"], "originalNarrativeSha256": sha(text.encode("utf-8")), "explicitHeightAssertions": assertions, "nativeSource": upper.get("SOURCE"), "nativePageVol": upper.get("PAGEVOL"), "reviewStatus": "candidate_numeric_comparison_not_adjudicated"})
        if number % 70 == 0:
            print(json.dumps({"chunksRead": number, "of": len(by_chunk), "heightRowsInspected": len(rows)}), flush=True)
    candidates = [row for row in rows if any(item["numericRelation"] == "same_raw_number_different_unit_possible_coding_error" for item in row["explicitHeightAssertions"])]
    report = {"schemaId": "ufo-encounter-height-unit-audit-v1", "generatedAtUtc": datetime.now(timezone.utc).isoformat(), "baseline": {"path": str(base_path), "gzipSha256": sha(base_raw), "decodedSha256": sha(gzip.decompress(base_raw))}, "producer": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__).read_bytes())}, "codebook": {"url": "https://cufos.org/PDFs/UFOCAT%20Codebook%202023.pdf", "printedPage": 10, "field": "Height", "declaredUnit": "ft", "verifiedViaOfficialPdf": True}, "scope": {"allEncounterIndexRows": len(evidence["rows"]), "allHeightBearingRows": len(rows), "nativeChunksReadInPlace": len(pins), "nativeBytesReadInPlace": scanned_bytes, "sourceCounts": dict(Counter(row["source"] for row in rows)), "nativeRawHeightEqualToIndexedNumericValue": len(rows)}, "counts": {"withRegexMatchedExplicitHeightUnitAssertion": sum(bool(row["explicitHeightAssertions"]) for row in rows), "sameRawNumberDifferentUnitCandidateRows": len(candidates), "heightAssertionNumericRelations": dict(categories), "under1Foot": sum(row["indexedHeightFeet"] < 1 for row in rows), "under3Feet": sum(row["indexedHeightFeet"] < 3 for row in rows), "over15Feet": sum(row["indexedHeightFeet"] > 15 for row in rows)}, "candidateRows": candidates, "allRows": rows, "nativeInputPins": pins, "policy": {"noRuntimeMutation": True, "nativeRecordsModified": False, "heightMagnitudeAloneEstablishesError": False, "regexCandidatesRequireManualSubjectAndUnitReview": True, "sourceCodebookDefinesFeetButIndividualCodingMayConflictWithNarrative": True, "fullNarrativesIncluded": False, "heightRulesNeverInferBeingType": True}, "recommendation": "Add an explicit reported-height provenance/status layer and hold contested height from unqualified feet display; keep original rawHeight and native source pins. Prefer manually sourced unit-specific facts to blanket metric/imperial guessing.", "rebuild": "python scripts/encounter_height_unit_audit.py --output <new-empty-directory>"}
    encoded = gzip.compress(json.dumps(report, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), mtime=0)
    if len(encoded) > 2 * 1024 * 1024:
        raise ValueError("Audit exceeds 2 MiB allocation")
    output.mkdir(parents=True, exist_ok=True)
    (output / "audit.json.gz").write_bytes(encoded)
    summary = {key: report[key] for key in ("schemaId", "generatedAtUtc", "baseline", "producer", "codebook", "scope", "counts", "candidateRows", "policy", "recommendation", "rebuild")}
    summary_bytes = json.dumps(summary, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    (output / "summary.json").write_bytes(summary_bytes)
    lifecycle = {"purpose": "Canonical read-only full height-field unit safety audit; source excerpts only", "canonical": str(output / "audit.json.gz"), "retention": "Retain source pins, field comparisons and manual review candidates; original corpus and runtime remain unchanged", "rollback": "No runtime or source mutation; current validated runtime retained", "supersededStaging": [], "newFilesOver100MiB": [], "netGrowthBytesExcludingLifecycle": len(encoded) + len(summary_bytes), "cleanup": "No duplicated datasets or staging created", "rebuild": report["rebuild"], "auditSha256": sha(encoded)}
    (output / "lifecycle.json").write_bytes(json.dumps(lifecycle, indent=2).encode() + b"\n")
    print(json.dumps({"output": str(output), "scope": report["scope"], "counts": report["counts"], "bytes": len(encoded)}, indent=2))
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, required=True)
    run(ap.parse_args().output)
