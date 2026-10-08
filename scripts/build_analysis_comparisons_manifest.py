"""Pin the small comparison candidate; reuse the existing facility artifact."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path


def build(root: Path, shared: Path) -> dict:
    destination = root / "data" / "analysis_comparisons"
    artifacts = {}
    for key, name in (("context", "context_rows.json"), ("nuclear", "nuclear_context_v1.json")):
        plain = destination / name
        compressed = destination / (name + ".gz")
        artifacts[key] = {"file": compressed.name, "sha256": hashlib.sha256(plain.read_bytes()).hexdigest(),
                          "bytes": plain.stat().st_size, "gzipBytes": compressed.stat().st_size,
                          "gzipSha256": hashlib.sha256(compressed.read_bytes()).hexdigest()}
    existing_path = shared / "data/releases/quality-20261007/analysis_delta/analysis_v2/manifest.json"
    existing = json.loads(existing_path.read_text(encoding="utf-8-sig"))
    facility = existing["artifacts"]["facilityAnalysis"]
    artifacts["facilities"] = {"file": "../analysis_v2/facility_analysis_v1.json.gz",
                               "sourceFile": facility["gzipFile"], "sha256": facility["sha256"],
                               "gzipSha256": facility["gzipSha256"], "bytes": facility["bytes"],
                               "gzipBytes": facility["gzipBytes"], "reused": True}
    output = {"schemaId": "ufo-analysis-comparisons-v1", "releaseId": "analysis-comparisons-local-v1-20261007",
              "ordinalEpoch": "unix_day", "artifacts": artifacts,
              "facilityCodebook": existing["codes"].get("facilityAnalysis", {}),
              "sourceManifestSha256": hashlib.sha256(existing_path.read_bytes()).hexdigest(),
              "policy": {"inference": "descriptive_only", "clockTimezoneInferred": False,
                         "formationDateInferred": False, "privateCoordinatesAdded": False,
                         "nuclearCatalogPost1998Coverage": False},
              "rebuild": "py -3 scripts/build_analysis_comparisons_manifest.py --shared-root <canonical root>"}
    atlas_manifest = destination / "ephemeris_atlas_manifest.json"
    if atlas_manifest.exists():
        atlas = json.loads(atlas_manifest.read_text(encoding="utf-8"))
        compressed = destination / atlas["file"]
        if compressed.stat().st_size != atlas["gzipByteLength"] or hashlib.sha256(compressed.read_bytes()).hexdigest() != atlas["gzipSha256"]:
            raise ValueError("The precomputed planetary artifact does not match its validated manifest.")
        output["ephemerisAtlas"] = atlas
        output["releaseId"] = "analysis-comparisons-precomputed-v2-20261007"
    (destination / "manifest.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--shared-root", type=Path, required=True)
    args = parser.parse_args()
    result = build(Path(__file__).resolve().parents[1], args.shared_root)
    print(json.dumps({"releaseId": result["releaseId"], "pinnedArtifacts": list(result["artifacts"])}))
