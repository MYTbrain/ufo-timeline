from __future__ import annotations

import gzip
import importlib.util
import json
import struct
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "webapp/static_public/data/analysis_v2/ufo_geography_v1.json"
BINARY = ROOT / "webapp/static_public/data/analysis_v2/ufo_geography_v1.bin"
GZIP_BINARY = ROOT / "webapp/static_public/data/analysis_v2/ufo_geography_v1.bin.gz"
MANIFEST = ROOT / "webapp/static_public/data/analysis_v2/manifest.json"
RECEIPT = ROOT / "campaign/analysis_improvement/waves/wave-006-analysis-projection-encoding/encoding_build_receipt.json"


def load_builder():
    path = ROOT / "scripts/build_analysis_geography_binary_v1.py"
    spec = importlib.util.spec_from_file_location("analysis_geography_binary_builder", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER = load_builder()


def test_geography_binary_manifest_and_receipt_are_exact() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    geography = manifest["artifacts"]["ufoGeography"]
    binary = geography["binary"]
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert binary["format"] == "ufo_geography_columnar_v1"
    assert binary["version"] == 1
    assert binary["decodedJsonSha256"] == geography["sha256"]
    assert binary["bytes"] == BINARY.stat().st_size == 8_130_994
    assert binary["gzipBytes"] == GZIP_BINARY.stat().st_size == 4_509_528
    assert binary["sha256"] == BUILDER.sha256_file(BINARY)
    assert binary["gzipSha256"] == BUILDER.sha256_file(GZIP_BINARY)
    assert receipt["parity"]["decodedParityPct"] == 100.0
    assert receipt["parity"]["decodedRowCount"] == geography["rowCount"] == 580_783
    assert receipt["output"]["gzipByteReductionPct"] >= 10
    receipt_entry = receipt["manifest"]["artifactEntry"]
    path_fields = {"file", "gzipFile"}
    assert {
        key: value for key, value in receipt_entry.items() if key not in path_fields
    } == {
        key: value for key, value in binary.items() if key not in path_fields
    }

    asset_base_url = manifest["assetBaseUrl"].rstrip("/")
    parsed_base = urlparse(asset_base_url)
    assert parsed_base.scheme == "https"
    assert parsed_base.netloc
    assert parsed_base.path.rstrip("/").endswith(
        f"/releases/{manifest['releaseId']}"
    )
    for field in sorted(path_fields):
        runtime_url = binary[field]
        parsed_runtime = urlparse(runtime_url)
        assert parsed_runtime.scheme == "https"
        assert parsed_runtime.netloc == parsed_base.netloc
        assert runtime_url.startswith(asset_base_url + "/")
        assert not urlparse(receipt_entry[field]).scheme
        assert Path(parsed_runtime.path).name == Path(receipt_entry[field]).name


def test_geography_binary_rebuild_is_deterministic_and_value_exact() -> None:
    rows = BUILDER.load_rows(SOURCE)
    rebuilt = BUILDER.encode_rows(rows)
    parity = BUILDER.parity_receipt(SOURCE, rows, rebuilt)
    rebuilt_gzip = BUILDER.deterministic_gzip(rebuilt)

    assert bytes(rebuilt) == BINARY.read_bytes()
    assert gzip.decompress(GZIP_BINARY.read_bytes()) == bytes(rebuilt)
    assert parity["decodedParityPct"] == 100.0
    assert parity["sourceJsonSha256"] == "f87c7747cd2143ed75cf8cc87c53603774651a17c66f5333df3b6d3f7cf17871"
    assert parity["sourceCanonicalJsonSha256"] == parity["decodedCanonicalJsonSha256"]

    magic, version, row_count, point_row_base, logical_columns, code_columns, header_bytes = struct.unpack_from(
        "<8sIIIIII", rebuilt, 0
    )
    assert magic == b"UFOGEO1\0"
    assert (version, row_count, point_row_base, logical_columns, code_columns, header_bytes) == (
        1,
        580_783,
        0,
        8,
        6,
        32,
    )
    assert gzip.decompress(rebuilt_gzip) == bytes(rebuilt)
