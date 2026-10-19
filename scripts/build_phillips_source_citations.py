"""Build a small citation-only derivative from the reviewed Phillips source index.

Default output stays on D:. This never rebuilds or mutates the UFO corpus. The
browser additionally requires an exact retained source-member identity/hash join.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from parser.canonical_schema import canonical_input_id, source_row_hash

DEFAULT_RESEARCH = Path("D:/UFO-Timeline-Context-Evidence/candidate/eligibility-research-20261019/phillips")
DEFAULT_CSV = Path("C:/Users/jarod/Desktop/UFO Timeline map tool/UFO Databases/ufocat2023.csv")
SCHEMA = "ufo-timeline-phillips-detail-citations-v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build(index_path: Path, csv_path: Path, output: Path) -> dict:
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index.get("schemaId") != "ufo-timeline-phillips-source-index-v1":
        raise ValueError("Unsupported reviewed source index")
    csv_hash = sha256(csv_path)
    if csv_hash != index["source"]["ufocatCsvSha256"]:
        raise ValueError("UFOCAT input differs from the reviewed source-index pin")
    wanted = {row["sourceRowNumber"]: row for row in index["records"]}
    if len(wanted) != len(index["records"]):
        raise ValueError("Duplicate reviewed source-row identity")
    events = {}
    matched = set()
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        for number, raw in enumerate(reader, 2):
            if number not in wanted:
                continue
            reviewed = wanted[number]
            row_hash = source_row_hash(reader.fieldnames, raw)
            input_id = canonical_input_id(source_name="ufocat", source_file="ufocat2023.csv",
                source_row_number=number, source_native_id=raw["PRN"].strip(), row_hash=row_hash)
            if (row_hash, input_id, raw["PRN"].strip()) != (
                    reviewed["sourceRowHash"], reviewed["canonicalInputId"], reviewed["sourceNativeId"]):
                raise ValueError(f"Reviewed source identity/hash mismatch at row {number}")
            member = {"source_name":"ufocat", "source_file":"ufocat2023.csv",
                "source_native_id":reviewed["sourceNativeId"], "source_row_number":number,
                "source_row_hash":row_hash, "canonical_input_id":input_id,
                "raw_fields":{key:raw[key].strip() for key in ("SOURCE","PAGEVOL","ISOURCE","IPAGEVOL") if raw[key].strip()}}
            for joined in reviewed["joinedEvents"]:
                event = events.setdefault(str(joined["eventId"]), {"eventId":joined["eventId"],
                    "canonicalEventId":joined["canonicalEventId"], "chunkId":joined["chunkId"], "sourceRecords":[]})
                if event["canonicalEventId"] != joined["canonicalEventId"]:
                    raise ValueError("Conflicting existing canonical event identity")
                event["sourceRecords"].append(member)
            matched.add(number)
    if matched != set(wanted):
        raise ValueError("Some reviewed source rows were not found")
    policy = {"countingUnit":"existing source representations attached to existing event identities",
        "identityGuard":["eventId","canonicalEventId","canonical_input_id membership","source_row_hash exact match"],
        "newEventsAdded":0,"qualificationsChanged":False,"narrativesIncluded":False,"coordinatesIncluded":False,
        "independentSourceFamiliesAsserted":False,"catalogLocators":"Direct case number; indirect raw ambiguous page-or-case locator"}
    counts = {"eventN":len(events), "sourceRecordN":sum(len(event["sourceRecords"]) for event in events.values())}
    data = {"schemaId":SCHEMA, "sourceIndexSha256":sha256(index_path),
        "sourceRowHashAlgorithm":"sha1_canonical_json_raw_csv_values_v1",
        "familyId":"ted_phillips_physical_trace_lineage", "policy":policy, "counts":counts, "events":events}
    decoded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = gzip.compress(decoded, mtime=0)
    output.mkdir(parents=True, exist_ok=True)
    artifact = output / "phillips.json.gz"
    artifact.write_bytes(compressed)
    manifest = {"schemaId":"ufo-timeline-phillips-detail-citations-manifest-v1",
        "artifact":{"file":"phillips.json.gz", "schemaId":SCHEMA,
            "decodedBytes":len(decoded), "decodedSha256":hashlib.sha256(decoded).hexdigest(),
            "gzipBytes":len(compressed), "gzipSha256":hashlib.sha256(compressed).hexdigest()},
        "counts":counts, "inputPins":{"sourceIndex":{"file":index_path.name,"sha256":sha256(index_path)},
            "ufocatCsv":{"file":"ufocat2023.csv","sha256":csv_hash,"bytes":csv_path.stat().st_size},
            "sourceCodebook":{"file":"UFOCAT 2023 Sources.xlsx","locator":"worksheet1 rows748-751"},
            "canonicalChunkManifestSha256":index["source"]["canonicalChunkManifestSha256"],
            "previewChunkManifestSha256":index["source"].get("currentPreviewChunkManifestSha256"),
            "catalogPdf":{"url":index["source"]["catalogUrl"],"sha256":index["source"]["catalogPdfSha256"]}},
        "policy":policy}
    manifest["inputPins"]["sourceCodebook"].update({
        "sha256":"8b47d701440bae501a4fb6dd823e79ff34bb2fb42fa971e6f8ab2351dd8d8701",
        "container":"UFOCAT 2023 Excel format.zip",
        "containerSha256":"724f02b79736265bede0bbe77043b270a17bfa7a770a85e85c6042c2b0a392ae"})
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-index", type=Path, default=DEFAULT_RESEARCH / "phillips-source-index.json")
    parser.add_argument("--source-csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESEARCH / "runtime")
    args = parser.parse_args()
    print(json.dumps(build(args.source_index, args.source_csv, args.output_dir), indent=2))
