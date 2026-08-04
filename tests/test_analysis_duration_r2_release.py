from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts import publish_analysis_duration_r2_release as duration_release
from scripts import publish_optional_layer_r2_release as optional_r2


MANIFEST_PATH = Path("webapp/static_public/data/analysis_duration_v1/manifest.json")


def manifest_and_payloads() -> tuple[dict, list[dict]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payloads = optional_r2.declared_payloads(manifest, MANIFEST_PATH.resolve())
    return manifest, payloads


def test_locked_duration_release_validates_locally() -> None:
    manifest, payloads = manifest_and_payloads()
    duration_release.validate_duration_manifest(manifest, payloads)
    report = optional_r2.publish_release(
        manifest_path=MANIFEST_PATH,
        bucket="ufo-timeline-data",
        wrangler=Path("node_modules/.bin/wrangler"),
        timeout=1,
        validate_only=True,
        validate_manifest=duration_release.validate_duration_manifest,
        upload_label="analysis-duration-test",
    )
    assert report == {
        "releaseId": "analysis-duration-v1-20260804",
        "bucket": "ufo-timeline-data",
        "payloadCount": 4,
        "payloadBytes": 16401833,
        "r2Prefix": "releases/analysis-duration-v1-20260804",
        "assetBaseUrl": "https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev/releases/analysis-duration-v1-20260804",
        "validated": True,
    }


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda manifest: manifest["counts"].__setitem__("normalizedRows", 246039), "counts"),
        (lambda manifest: manifest["policy"].__setitem__("patternFinderPromotion", True), "policy"),
        (lambda manifest: manifest["readiness"]["materialGates"].__setitem__("projectionParity", False), "gates"),
    ],
)
def test_duration_release_rejects_changed_scientific_contract(mutation, message: str) -> None:
    manifest, payloads = manifest_and_payloads()
    changed = deepcopy(manifest)
    mutation(changed)
    with pytest.raises(optional_r2.ReleaseError, match=message):
        duration_release.validate_duration_manifest(changed, payloads)
