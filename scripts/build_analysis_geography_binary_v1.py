#!/usr/bin/env python3
"""Build the deterministic, value-exact Analysis geography binary projection."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


MAGIC = b"UFOGEO1\0"
VERSION = 1
HEADER = struct.Struct("<8sIIIIII")
HEADER_BYTES = HEADER.size
LOGICAL_COLUMN_COUNT = 8
CODE_COLUMN_COUNT = 6
MAX_SAFE_EVENT_ID = (1 << 53) - 1


def sha256_bytes(value: bytes | bytearray | memoryview) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_rows(path: Path) -> list[list[int]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    rows = value if isinstance(value, list) else value.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("The geography source must contain a non-empty row array.")
    return rows


def validate_row(row: Any, index: int) -> list[int]:
    if not isinstance(row, list) or len(row) != LOGICAL_COLUMN_COUNT:
        raise ValueError(f"Geography row {index} does not have {LOGICAL_COLUMN_COUNT} columns.")
    if row[0] != index:
        raise ValueError(f"Geography row {index} has non-canonical pointRowIndex {row[0]!r}.")
    event_id = row[1]
    if not isinstance(event_id, int) or isinstance(event_id, bool) or not 0 <= event_id <= MAX_SAFE_EVENT_ID:
        raise ValueError(f"Geography row {index} has an unsafe eventId {event_id!r}.")
    for column_index, code in enumerate(row[2:], start=2):
        if not isinstance(code, int) or isinstance(code, bool) or not 0 <= code <= 255:
            raise ValueError(
                f"Geography row {index} column {column_index} is not an unsigned byte code: {code!r}."
            )
    return row


def encode_rows(rows: list[list[int]]) -> bytearray:
    row_count = len(rows)
    total_bytes = HEADER_BYTES + row_count * 8 + row_count * CODE_COLUMN_COUNT
    encoded = bytearray(total_bytes)
    HEADER.pack_into(
        encoded,
        0,
        MAGIC,
        VERSION,
        row_count,
        0,
        LOGICAL_COLUMN_COUNT,
        CODE_COLUMN_COUNT,
        HEADER_BYTES,
    )
    low_offset = HEADER_BYTES
    high_offset = low_offset + row_count * 4
    code_base = high_offset + row_count * 4
    for index, row_value in enumerate(rows):
        row = validate_row(row_value, index)
        event_id = row[1]
        struct.pack_into("<I", encoded, low_offset + index * 4, event_id & 0xFFFFFFFF)
        struct.pack_into("<I", encoded, high_offset + index * 4, event_id >> 32)
        for code_index, code in enumerate(row[2:]):
            encoded[code_base + code_index * row_count + index] = code
    return encoded


def decoded_row(encoded: memoryview, index: int, row_count: int) -> list[int]:
    low_offset = HEADER_BYTES
    high_offset = low_offset + row_count * 4
    code_base = high_offset + row_count * 4
    event_low = struct.unpack_from("<I", encoded, low_offset + index * 4)[0]
    event_high = struct.unpack_from("<I", encoded, high_offset + index * 4)[0]
    return [
        index,
        event_high * (1 << 32) + event_low,
        *[encoded[code_base + code_index * row_count + index] for code_index in range(CODE_COLUMN_COUNT)],
    ]


def parity_receipt(source_path: Path, rows: list[list[int]], encoded: bytearray) -> dict[str, Any]:
    view = memoryview(encoded)
    magic, version, row_count, point_row_base, logical_columns, code_columns, header_bytes = HEADER.unpack_from(view, 0)
    if (
        magic != MAGIC
        or version != VERSION
        or row_count != len(rows)
        or point_row_base != 0
        or logical_columns != LOGICAL_COLUMN_COUNT
        or code_columns != CODE_COLUMN_COUNT
        or header_bytes != HEADER_BYTES
    ):
        raise ValueError("The encoded geography header did not round-trip its contract fields.")

    canonical_digest = hashlib.sha256()
    canonical_digest.update(b"[")
    extreme_event_ids = {"minimum": None, "maximum": None}
    code_minimums = [None] * CODE_COLUMN_COUNT
    code_maximums = [None] * CODE_COLUMN_COUNT
    for index, source_row in enumerate(rows):
        decoded = decoded_row(view, index, row_count)
        if decoded != source_row:
            raise ValueError(f"Decoded geography parity failed at row {index}.")
        if index:
            canonical_digest.update(b",")
        canonical_digest.update(json.dumps(decoded, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
        event_id = decoded[1]
        extreme_event_ids["minimum"] = event_id if extreme_event_ids["minimum"] is None else min(extreme_event_ids["minimum"], event_id)
        extreme_event_ids["maximum"] = event_id if extreme_event_ids["maximum"] is None else max(extreme_event_ids["maximum"], event_id)
        for code_index, code in enumerate(decoded[2:]):
            code_minimums[code_index] = code if code_minimums[code_index] is None else min(code_minimums[code_index], code)
            code_maximums[code_index] = code if code_maximums[code_index] is None else max(code_maximums[code_index], code)
    canonical_digest.update(b"]")
    decoded_sha256 = canonical_digest.hexdigest()
    source_sha256 = sha256_file(source_path)
    return {
        "decodedParityPct": 100.0,
        "decodedRowCount": row_count,
        "sourceJsonSha256": source_sha256,
        "sourceCanonicalJsonSha256": decoded_sha256,
        "decodedCanonicalJsonSha256": decoded_sha256,
        "pointRowIndex": {"implicit": True, "base": 0, "maximum": row_count - 1},
        "eventId": extreme_event_ids,
        "codeMinimums": code_minimums,
        "codeMaximums": code_maximums,
        "nullCount": 0,
        "sentinelSemantics": "All six integer code columns are retained byte-exact; their codebooks remain in the signed manifest.",
    }


def deterministic_gzip(value: bytes | bytearray) -> bytes:
    return gzip.compress(value, compresslevel=9, mtime=0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gzip-output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    rows = load_rows(args.source)
    encoded = encode_rows(rows)
    parity = parity_receipt(args.source, rows, encoded)
    compressed = deterministic_gzip(encoded)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.gzip_output.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    args.gzip_output.write_bytes(compressed)

    source_bytes = args.source.stat().st_size
    source_gzip_path = args.source.with_suffix(args.source.suffix + ".gz")
    source_gzip_bytes = source_gzip_path.stat().st_size if source_gzip_path.exists() else None
    binary_entry = {
        "format": "ufo_geography_columnar_v1",
        "version": VERSION,
        "bytes": len(encoded),
        "sha256": sha256_bytes(encoded),
        "gzipBytes": len(compressed),
        "gzipSha256": sha256_bytes(compressed),
        "decodedJsonSha256": parity["sourceJsonSha256"],
        "decodedCanonicalJsonSha256": parity["decodedCanonicalJsonSha256"],
    }
    if args.manifest:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        artifact = manifest.get("artifacts", {}).get("ufoGeography")
        if not isinstance(artifact, dict) or artifact.get("sha256") != parity["sourceJsonSha256"]:
            raise ValueError("The target manifest does not describe the frozen geography source.")
        public_root = args.manifest.parents[2]
        binary_entry["file"] = args.output.relative_to(public_root).as_posix()
        binary_entry["gzipFile"] = args.gzip_output.relative_to(public_root).as_posix()
        artifact["binary"] = dict(binary_entry)
        args.manifest.write_bytes(
            (
                json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                + "\n"
            ).encode("utf-8")
        )

    receipt = {
        "schemaId": "ufo-timeline-analysis-geography-binary-build-v1.0.0",
        "format": {
            "magicHex": MAGIC.hex(),
            "version": VERSION,
            "headerBytes": HEADER_BYTES,
            "endianness": "little",
            "logicalRowSchema": [
                "pointRowIndex",
                "eventId",
                "countryCode",
                "macroregionCode",
                "assignmentSourceCode",
                "assignmentConfidenceCode",
                "boundaryStatusCode",
                "coordinateEvidenceCode",
            ],
            "storedColumns": [
                "eventIdLowUint32",
                "eventIdHighUint32",
                "countryCodeUint8",
                "macroregionCodeUint8",
                "assignmentSourceCodeUint8",
                "assignmentConfidenceCodeUint8",
                "boundaryStatusCodeUint8",
                "coordinateEvidenceCodeUint8",
            ],
        },
        "source": {
            "path": args.source.as_posix(),
            "bytes": source_bytes,
            "gzipBytes": source_gzip_bytes,
            "sha256": parity["sourceJsonSha256"],
        },
        "output": {
            "path": args.output.as_posix(),
            "bytes": len(encoded),
            "sha256": sha256_bytes(encoded),
            "gzipPath": args.gzip_output.as_posix(),
            "gzipBytes": len(compressed),
            "gzipSha256": sha256_bytes(compressed),
            "rawByteReductionPct": round((source_bytes - len(encoded)) * 100 / source_bytes, 6),
            "gzipByteReductionPct": (
                round((source_gzip_bytes - len(compressed)) * 100 / source_gzip_bytes, 6)
                if source_gzip_bytes
                else None
            ),
        },
        "parity": parity,
    }
    if args.manifest:
        receipt["manifest"] = {
            "path": args.manifest.as_posix(),
            "sha256": sha256_file(args.manifest),
            "artifactEntry": binary_entry,
        }
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
