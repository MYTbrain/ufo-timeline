import json

from parser.canonical_schema import CanonicalInputRecord
from parser.dedupe import (
    DEDUPE_STRATEGY_MAXIMAL_V3,
    build_deduped_events,
)
from scripts.build_canonical_web_artifacts import build_canonical_web_artifacts


def test_merged_member_evidence_preserves_candidate_without_promoting_canonical_type():
    primary = _record(
        "cin_z_primary",
        source_name="ufocat",
        source_file="ufocat2023.csv",
        source_row_number=1,
        shape_raw="Unknown",
        type_raw="Unknown",
        description="Same duplicated report text.",
    )
    member = _record(
        "cin_member",
        source_name="majestic",
        source_file="majestic.csv",
        source_row_number=2,
        shape_raw="Disc",
        type_raw="sighting",
        description="Same duplicated report text.",
    )

    deduped_events, _ = build_deduped_events([primary, member])

    event = deduped_events[0]
    assert event.get("craft_type_inferred") is None
    assert event["merged_member_craft_type_candidate"] == "disc_saucer"
    assert event["merged_member_craft_type_status"] == "promotable"
    assert event["merged_member_craft_type_confidence"] == "high"
    assert event["merged_member_craft_type_member_ids"] == ["cin_member"]
    assert event["merged_member_craft_type_evidence"][0]["shape_raw"] == "Disc"


def test_direct_canonical_evidence_blocks_member_candidate_promotion_status():
    primary = _record(
        "cin_z_primary",
        shape_raw="Triangle",
        description="Same duplicated report text.",
    )
    member = _record(
        "cin_member",
        source_name="majestic",
        source_file="majestic.csv",
        source_row_number=2,
        shape_raw="Disc",
        description="Same duplicated report text.",
    )

    deduped_events, _ = build_deduped_events([primary, member])

    event = deduped_events[0]
    assert event["shape_raw"] == "Triangle"
    assert event["merged_member_craft_type_candidate"] == "disc_saucer"
    assert event["merged_member_craft_type_status"] == "blocked_direct_canonical_evidence_exists"
    assert event["merged_member_craft_type_basis"]["primary_craft_type_inferred"] == "triangle"


def test_conflicting_high_quality_member_evidence_does_not_become_promotable():
    primary = _record(
        "cin_z_primary",
        shape_raw="Unknown",
        description="Same duplicated report text.",
    )
    disc_member = _record(
        "cin_disc",
        source_name="majestic",
        source_file="majestic.csv",
        source_row_number=2,
        shape_raw="Disc",
        description="Same duplicated report text.",
    )
    triangle_member = _record(
        "cin_triangle",
        source_name="nuforc",
        source_file="nuforcpy.csv",
        source_row_number=3,
        shape_raw="Triangle",
        description="Same duplicated report text.",
    )

    deduped_events, _ = build_deduped_events([primary, disc_member, triangle_member])

    event = deduped_events[0]
    assert event["merged_member_craft_type_conflict"] is True
    assert event["merged_member_craft_type_status"] == "blocked_conflict"
    assert event["merged_member_craft_type_basis"]["high_confidence_conflict"] is True


def test_light_and_prosaic_member_evidence_are_not_promotable_craft_types():
    primary = _record(
        "cin_z_primary",
        shape_raw="Unknown",
        description="Same duplicated report text.",
    )
    light_member = _record(
        "cin_light",
        source_name="nuforc",
        source_file="nuforcpy.csv",
        source_row_number=2,
        shape_raw="Light",
        description="Same duplicated report text.",
    )
    aircraft_member = _record(
        "cin_aircraft",
        source_name="ufocat",
        source_file="ufocat2023.csv",
        source_row_number=3,
        shape_raw="Aircraft",
        description="Same duplicated report text.",
        raw_fields={"SHAPE": "Aircraft"},
    )

    light_event, _ = build_deduped_events([primary, light_member])
    prosaic_event, _ = build_deduped_events([primary, aircraft_member])

    assert light_event[0]["merged_member_craft_type_candidate"] == "light"
    assert light_event[0]["merged_member_craft_type_status"] == "blocked_weak_evidence"
    assert "merged_member_craft_type_candidate" not in prosaic_event[0]


def test_rule_based_dedupe_also_preserves_merged_member_evidence():
    primary = _record(
        "cin_primary",
        source_name="ufocat",
        source_file="ufocat2023.csv",
        source_row_number=1,
        source_native_id="same-native",
        shape_raw="Unknown",
        description="Longer canonical same native id row with no direct shape evidence retained.",
    )
    member = _record(
        "cin_member",
        source_name="ufocat",
        source_file="ufocat2023.csv",
        source_row_number=2,
        source_native_id="same-native",
        shape_raw="Cylinder",
        description="Cylinder evidence.",
    )

    deduped_events, duplicate_groups = build_deduped_events([primary, member], strategy=DEDUPE_STRATEGY_MAXIMAL_V3)

    assert len(deduped_events) == 1
    assert len(duplicate_groups) == 1
    assert deduped_events[0]["canonical_input_id"] == "cin_primary"
    assert deduped_events[0]["merged_member_craft_type_candidate"] == "cigar_cylinder"
    assert deduped_events[0]["merged_member_craft_type_status"] == "promotable"


def test_canonical_web_detail_preserves_member_evidence_without_promoting_summary(tmp_path):
    primary = _record(
        "cin_z_primary",
        source_name="ufocat",
        source_file="ufocat2023.csv",
        source_row_number=1,
        shape_raw="Unknown",
        type_raw="Unknown",
        description="Same duplicated report text.",
    )
    member = _record(
        "cin_member",
        source_name="majestic",
        source_file="majestic.csv",
        source_row_number=2,
        shape_raw="Disc",
        type_raw="sighting",
        description="Same duplicated report text.",
    )
    deduped_events, _ = build_deduped_events([primary, member])
    input_path = tmp_path / "deduped_events.jsonl"
    input_path.write_text(json.dumps(deduped_events[0]) + "\n", encoding="utf-8")
    output_dir = tmp_path / "canonical_web"

    summary = build_canonical_web_artifacts(input_path=input_path, output_dir=output_dir)

    assert summary["events"] == 1
    details = json.loads((output_dir / "event_chunks" / "chunk_000000.json").read_text(encoding="utf-8"))
    detail = details[0]
    assert detail["craft_type_inferred"] == "unknown"
    assert detail["merged_member_craft_type_candidate"] == "disc_saucer"
    assert detail["merged_member_craft_type_status"] == "promotable"
    assert detail["merged_member_craft_type_member_ids"] == ["cin_member"]
    assert detail["merged_member_craft_type_evidence"][0]["shape_raw"] == "Disc"

    summaries = json.loads((output_dir / "summary_shards" / "summary_000000.json").read_text(encoding="utf-8"))
    startup_summary = summaries[0]
    assert startup_summary["craft_type_inferred"] == "unknown"
    assert "merged_member_craft_type_candidate" not in startup_summary


def _record(
    canonical_input_id,
    *,
    source_name="ufocat",
    source_file="ufocat2023.csv",
    source_row_number=1,
    source_native_id=None,
    source_row_hash=None,
    shape_raw=None,
    type_raw="Unknown",
    description="Duplicate group row.",
    raw_fields=None,
):
    return CanonicalInputRecord(
        canonical_input_id=canonical_input_id,
        source_name=source_name,
        source_file=source_file,
        source_row_number=source_row_number,
        source_native_id=source_native_id,
        source_row_hash=source_row_hash or f"hash_{canonical_input_id}",
        date_iso="1954-09-24",
        sort_date_iso="1954-09-24",
        date_precision="exact_day",
        time_raw="21:00",
        location_raw="Hobbs, NM, US",
        shape_raw=shape_raw,
        shape_normalized=shape_raw,
        type_raw=type_raw,
        type_normalized=type_raw,
        description=description,
        raw_fields=raw_fields or {},
    )
