from pathlib import Path

from scripts.build_canonical_mutation_contract import build_canonical_mutation_contract


def write_lines(path: Path, count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{{\"id\":{index}}}\n" for index in range(count)), encoding="utf-8")


def test_build_canonical_mutation_contract_stays_report_only(tmp_path):
    canonical = tmp_path / "canonical.jsonl"
    base_preview = tmp_path / "base.jsonl"
    promoted_preview = tmp_path / "promoted.jsonl"
    write_lines(canonical, 10)
    write_lines(base_preview, 8)
    write_lines(promoted_preview, 7)

    report = build_canonical_mutation_contract(
        canonical_events=canonical,
        promoted_preview_events=promoted_preview,
        base_preview_events=base_preview,
        acceptance_report={"accepted_decision_count": 1},
        preview_apply_report={
            "canonical_outputs_mutated": False,
            "effects_applied": 1,
            "effects_blocked": 0,
            "projected_event_reduction": 1,
        },
        runtime_readiness={"ready_for_primary_catalog": True},
        static_payload_readiness={
            "status": "ready",
            "config_state": {"default_app_config_canonical_promoted": True},
        },
        output_json=tmp_path / "report.json",
        output_md=tmp_path / "report.md",
    )

    assert report["contract_valid"] is True
    assert report["canonical_outputs_mutated"] is False
    assert report["ready_for_direct_canonical_overwrite"] is False
    assert report["counts"]["whole_chain_event_reduction_if_promoted"] == 3
    assert report["counts"]["latest_remaining_lower_event_reduction"] == 1


def test_build_canonical_mutation_contract_flags_mismatched_reduction(tmp_path):
    canonical = tmp_path / "canonical.jsonl"
    base_preview = tmp_path / "base.jsonl"
    promoted_preview = tmp_path / "promoted.jsonl"
    write_lines(canonical, 10)
    write_lines(base_preview, 8)
    write_lines(promoted_preview, 7)

    report = build_canonical_mutation_contract(
        canonical_events=canonical,
        promoted_preview_events=promoted_preview,
        base_preview_events=base_preview,
        acceptance_report={"accepted_decision_count": 1},
        preview_apply_report={
            "canonical_outputs_mutated": False,
            "effects_applied": 1,
            "effects_blocked": 0,
            "projected_event_reduction": 2,
        },
        runtime_readiness={"ready_for_primary_catalog": True},
        static_payload_readiness={
            "status": "ready",
            "config_state": {"default_app_config_canonical_promoted": True},
        },
        output_json=tmp_path / "report.json",
        output_md=tmp_path / "report.md",
    )

    assert report["contract_valid"] is False
    assert "base preview to promoted preview reduction must match latest projected reduction" in report["validation_errors"]
