import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import rebuild_static_bundle_from_existing_data as rebuild_module


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _fake_config(tmp_path: Path) -> SimpleNamespace:
    data_dir = tmp_path / "data"
    return SimpleNamespace(
        normalized_events_path=data_dir / "normalized_events.json",
        map_events_path=data_dir / "map_events.json",
        unresolved_locations_json_path=data_dir / "unresolved.json",
        ranked_unresolved_locations_json_path=data_dir / "ranked_unresolved.json",
        static_bundle_dir=tmp_path / "static_bundle",
    )


def test_rebuild_refuses_to_regress_an_existing_canonical_bundle(tmp_path, monkeypatch):
    config = _fake_config(tmp_path)
    _write_json(config.normalized_events_path, [{"id": 1}, {"id": 2}])
    _write_json(config.map_events_path, [{"id": 1}])
    _write_json(
        config.static_bundle_dir / "data" / "canonical_web" / "canonical_web_manifest.json",
        {"counts": {"events": 5, "mapped_events": 3}},
    )
    monkeypatch.setattr(rebuild_module, "load_config", lambda _path: config)
    monkeypatch.setattr(
        rebuild_module,
        "build_static_bundle",
        lambda *_args, **_kwargs: pytest.fail("guard must run before the bundle is rebuilt"),
    )

    with pytest.raises(RuntimeError, match=r"5 events.*2 events"):
        rebuild_module.rebuild_static_bundle_from_existing_data("ignored.yaml")


def test_rebuild_requires_explicit_override_for_an_intentional_regression(tmp_path, monkeypatch):
    config = _fake_config(tmp_path)
    _write_json(config.normalized_events_path, [{"id": 1}, {"id": 2}])
    _write_json(config.map_events_path, [{"id": 1}])
    _write_json(
        config.static_bundle_dir / "data" / "canonical_web" / "canonical_web_manifest.json",
        {"counts": {"events": 5, "mapped_events": 3}},
    )
    monkeypatch.setattr(rebuild_module, "load_config", lambda _path: config)
    monkeypatch.setattr(
        rebuild_module,
        "build_static_bundle",
        lambda *_args, **_kwargs: config.static_bundle_dir,
    )

    summary = rebuild_module.rebuild_static_bundle_from_existing_data(
        "ignored.yaml",
        allow_canonical_regression=True,
    )

    assert summary["normalized_events"] == 2
    assert summary["map_events"] == 1
    assert summary["static_bundle_dir"] == str(config.static_bundle_dir)


def test_rebuild_cli_exposes_the_canonical_regression_override():
    args = rebuild_module.build_argument_parser().parse_args(["--allow-canonical-regression"])

    assert args.allow_canonical_regression is True
