"""Build a read-only UFOCAT codebook decode review report.

This script reads the existing unknown-craft candidate audit and the local
UFOCAT codebook extract, then writes review-only JSON/Markdown reports. It
does not modify parser rules or rebuild deployable artifacts.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "data" / "reports"
CANDIDATE_PATH = REPORT_DIR / "craft_unknown_candidate_rules.json"
CODEBOOK_PATH = REPORT_DIR / "ufocat_codebook_extract" / "UFOCAT Codebook 2023.txt"
OUT_JSON = REPORT_DIR / "ufocat_codebook_decode_review.json"
OUT_MD = REPORT_DIR / "ufocat_codebook_decode_review.md"

PRIORITY = [
    ("TYPE", "2"),
    ("TYPE", "DD"),
    ("TYPE", "5"),
    ("TYPE", "2A"),
    ("TYPE", "3"),
    ("TYPE", "4"),
    ("TYPE", "3H"),
    ("TYPE", "5S"),
    ("TYPE", "1"),
    ("TYPE", "6"),
    ("TYPE", "7"),
    ("TYPE", "5R"),
    ("TYPE", "9M"),
    ("TYPE", "9B"),
    ("TYPE", "5E"),
    ("TYPE", "IFO"),
    ("TYPE", "5C"),
    ("TYPE", "2W"),
    ("TYPE", "8"),
    ("SHAPE", "Copter"),
    ("SHAPE", "Cloud"),
    ("SHAPE", "Aircraft"),
]

ALLOWED_TARGETS = {
    "craft_type_inferred",
    "object_morphology",
    "light_pattern",
    "formation_type",
    "behavior_tags",
    "prosaic_candidate",
    "unknown_reason",
    "ignore/no_rule",
}

TYPE_MAJOR = {
    "0": (
        "Not properly regarded as a UFO report by direct source; may have ufological interest.",
        "unknown_reason",
        "Classify as non_sighting_context or ignore/no_rule only when supported by source context; do not infer craft type from TYPE 0.",
    ),
    "1": (
        "UFO essentially stationary during observation.",
        "behavior_tags",
        "Add stationary behavior tag only; no craft_type rule.",
    ),
    "2": (
        "UFO moved in a continuous trajectory faster than apparent motion of heavenly bodies.",
        "behavior_tags",
        "Add continuous_trajectory / moving behavior tag only; no craft_type rule.",
    ),
    "3": (
        "UFO moved in a non-continuous trajectory with a single discontinuity, e.g. sharp turn or hover pause.",
        "behavior_tags",
        "Add discontinuous_trajectory / maneuver behavior tag only; no craft_type rule.",
    ),
    "4": (
        "UFO moved in a non-continuous trajectory with more than one discontinuity; complex trajectories.",
        "behavior_tags",
        "Add complex_trajectory / maneuver behavior tag only; no craft_type rule.",
    ),
    "5": (
        "Encounter report without landing: UFO entered witness frame of reference; includes photo, radar, EM, investigated cases.",
        "behavior_tags",
        "Add encounter_without_landing / close_encounter_class_only metadata; no craft_type rule from major TYPE alone.",
    ),
    "6": (
        "Landing report without outside occupants; object minimum separation from ground <= object major dimension.",
        "behavior_tags",
        "Add landing_report metadata; no craft_type rule from major TYPE alone.",
    ),
    "7": (
        "Outside occupant report without contact; occupant-only reports can also be Type 7.",
        "unknown_reason",
        "Classify as encounter_class_only / close_encounter_class_only unless separate shape evidence exists.",
    ),
    "8": (
        "Contact report with intelligent communication, including telepathic communication.",
        "unknown_reason",
        "Classify as encounter_class_only / close_encounter_class_only unless separate shape evidence exists.",
    ),
    "9": (
        "Interference where UFO changes something living; includes abduction, missing time, cattle mutilation.",
        "unknown_reason",
        "Classify as encounter_class_only / biological_effect_or_abduction_context; no craft_type rule.",
    ),
}

TYPE_SUB = {
    "2A": ("Aircraft-like behavior.", "prosaic_candidate", "Mark aircraft_like_behavior/conventional cue; do not infer craft morphology."),
    "2B": ("Balloon-like behavior, hot-air or weather.", "prosaic_candidate", "Mark balloon_like_behavior/conventional cue; no craft_type rule."),
    "2C": ("Cloud-cigar shaped object(s).", "object_morphology", "Candidate object_morphology=cigar_or_cloud_cigar; craft_type only after review because phrase mixes cloud/cigar."),
    "2D": ("Disc-shaped object(s).", "craft_type_inferred", "Safe high-confidence craft_type_inferred=disc_saucer from documented TYPE subtype."),
    "2E": ("Echo satellite.", "prosaic_candidate", "Mark satellite/conventional cue; no craft_type rule."),
    "2F": ("Fireball.", "light_pattern", "Mark fireball/meteor_like light pattern; do not force craft_type."),
    "2G": ("Green fireball.", "light_pattern", "Mark green_fireball/meteor_like light pattern; do not force craft_type."),
    "2I": ("Instrumented observation.", "behavior_tags", "Mark instrumented_observation; no craft_type rule."),
    "2L": ("Ghost Lights.", "light_pattern", "Mark ghost_lights/light_pattern; no craft_type rule."),
    "2M": ("Meteor-like behavior.", "prosaic_candidate", "Mark meteor_like_behavior/conventional cue; no craft_type rule."),
    "2P": ("Procession of objects, possibly seen singly.", "formation_type", "Mark procession/formation_type; no craft_type rule."),
    "2S": ("Sputnik satellite.", "prosaic_candidate", "Mark satellite/conventional cue; no craft_type rule."),
    "2X": ("Bolide.", "prosaic_candidate", "Mark bolide/meteor_like conventional cue; no craft_type rule."),
    "2Z": ("Crescent-shaped object.", "craft_type_inferred", "Safe craft_type_inferred=chevron_or_crescent only if taxonomy supports crescent; otherwise object_morphology."),
    "3C": ("Cloud-cigar shaped object(s).", "object_morphology", "Candidate object_morphology=cigar_or_cloud_cigar; review before craft_type."),
    "3D": ("Disc-shaped object(s).", "craft_type_inferred", "Safe high-confidence craft_type_inferred=disc_saucer from documented TYPE subtype."),
    "3H": ("Hovered.", "behavior_tags", "Mark hovered; no craft_type rule."),
    "3L": ("Landed remotely.", "behavior_tags", "Mark remote_landing; no craft_type rule."),
    "3TG": ("Angel hair.", "behavior_tags", "Mark trace_residue/angel_hair; no craft_type rule."),
    "3W": ("Independent witnesses.", "behavior_tags", "Mark independent_witnesses; no craft_type rule."),
    "3X": ("Exploded.", "behavior_tags", "Mark exploded; no craft_type rule."),
    "3Z": ("Crescent-shaped object.", "craft_type_inferred", "Safe craft_type_inferred=chevron_or_crescent only if taxonomy supports crescent; otherwise object_morphology."),
    "4C": ("Cloud-cigar with satellite object(s).", "object_morphology", "Candidate object_morphology=cigar_or_cloud_cigar plus satellite_object tag; review before craft_type."),
    "4D": ("Disc-shaped object(s).", "craft_type_inferred", "Safe high-confidence craft_type_inferred=disc_saucer from documented TYPE subtype."),
    "4H": ("Multiple hovering.", "behavior_tags", "Mark multiple_hovering; no craft_type rule."),
    "4L": ("Falling leaf maneuver.", "behavior_tags", "Mark falling_leaf_maneuver; no craft_type rule."),
    "4W": ("Independent witnesses.", "behavior_tags", "Mark independent_witnesses; no craft_type rule."),
    "4Y": ("Angel hair residue associated with UFO presence.", "behavior_tags", "Mark trace_residue/angel_hair; no craft_type rule."),
    "4ZZ": ("Zigzag maneuver.", "behavior_tags", "Mark zigzag_maneuver; no craft_type rule."),
    "5A": ("Acrobatics.", "behavior_tags", "Mark acrobatics; no craft_type rule."),
    "5B": ("Buzzing.", "behavior_tags", "Mark buzzing/close_pass; no craft_type rule."),
    "5C": ("Chasing-pacing.", "behavior_tags", "Mark chasing_or_pacing; no craft_type rule."),
    "5D": ("Disc shape.", "craft_type_inferred", "Safe high-confidence craft_type_inferred=disc_saucer from documented TYPE subtype."),
    "5E": ("Electromagnetic effect.", "behavior_tags", "Mark electromagnetic_effect; no craft_type rule."),
    "5H": ("Sketch.", "unknown_reason", "Classify as instrument_or_photo_only/supporting_media_only; no craft_type rule."),
    "5I": ("Instrumented observation.", "behavior_tags", "Mark instrumented_observation; no craft_type rule."),
    "5M": ("Animals present.", "behavior_tags", "Mark animals_present; no craft_type rule."),
    "5N": ("Noise or sound.", "behavior_tags", "Mark sound_reported; no craft_type rule."),
    "5O": ("Inside occupant if O is in second column; ring/circle if O is not in second column.", "unknown_reason", "Context-dependent O code; review position before assigning occupant vs ring/circle."),
    "5P": ("Physiological effects, transient.", "behavior_tags", "Mark physiological_effect; no craft_type rule."),
    "5R": ("Radar observation without visual confirmation.", "behavior_tags", "Mark radar_only/instrumented_observation; no craft_type rule."),
    "5RR": ("Multiple radar.", "behavior_tags", "Mark multiple_radar; no craft_type rule."),
    "5S": ("Still picture.", "unknown_reason", "Classify as instrument_or_photo_only/supporting_media_only unless image text contains shape evidence."),
    "5SD": ("Photo of disc.", "craft_type_inferred", "Candidate craft_type_inferred=disc_saucer; require parser to detect full 5SD, not broad S."),
    "5SL": ("Luminous/transparent photo.", "light_pattern", "Mark luminous_or_transparent_photo; no craft_type rule."),
    "5SM": ("Movies.", "unknown_reason", "Classify as instrument_or_photo_only/supporting_media_only; no craft_type rule."),
    "5SS": ("Structured photo.", "unknown_reason", "Classify as instrument_or_photo_only/structured_photo; no craft_type rule unless separate morphology exists."),
    "5T": ("Physical trace(s) correlated with object(s).", "behavior_tags", "Mark physical_trace; no craft_type rule."),
    "5V": ("Radar/visual confirmation.", "behavior_tags", "Mark radar_visual_confirmation; no craft_type rule."),
    "5W": ("Independent witnesses.", "behavior_tags", "Mark independent_witnesses; no craft_type rule."),
    "5Y": ("Psychic effects/testimony obtained under hypnosis.", "unknown_reason", "Classify as encounter_class_only/testimony_context; no craft_type rule."),
    "5ZZ": ("Zigzag maneuver.", "behavior_tags", "Mark zigzag_maneuver; no craft_type rule."),
    "7M": ("Monster, non-humanoid or giant, with UFO also seen.", "unknown_reason", "Classify as encounter_class_only/entity_context; no craft_type rule."),
    "8K": ("MIB or Men in Black incident, harassment or intimidation.", "unknown_reason", "Classify as non_sighting_context or investigation_interference depending source text; no craft_type rule."),
    "9A": ("Abduction or disappearance.", "unknown_reason", "Classify as close_encounter_class_only/abduction_context; no craft_type rule."),
    "9B": ("Teleportation or abduction and return.", "unknown_reason", "Classify as close_encounter_class_only/abduction_or_teleportation_context; no craft_type rule."),
    "9D": ("Death.", "unknown_reason", "Classify as biological_effect_context; no craft_type rule."),
    "9F": ("Other functional effects.", "behavior_tags", "Mark functional_effects; no craft_type rule."),
    "9H": ("Healing effects of any kind.", "behavior_tags", "Mark healing_effect; no craft_type rule."),
    "9L": ("Lapse of time experienced by witness(es).", "behavior_tags", "Mark missing_time/lapse_of_time; no craft_type rule."),
    "9M": ("Animal mutilations.", "unknown_reason", "Classify as non_sighting_context or biological_effect_context unless UFO/object evidence exists."),
}

HYNEK = {
    "NL": ("Nocturnal Lights.", "light_pattern", "Mark nocturnal_lights; no craft_type unless separate structure evidence exists."),
    "ND": ("Nocturnal Discs.", "craft_type_inferred", "Safe high-confidence craft_type_inferred=disc_saucer if raw field is HYNEK."),
    "NO": ("Nocturnal Objects.", "unknown_reason", "Classify as missing_shape_evidence/nocturnal_object_without_shape; no craft_type."),
    "DD": ("Daylight Discs.", "craft_type_inferred", "Safe high-confidence craft_type_inferred=disc_saucer if raw field is HYNEK."),
    "DL": ("Daylight Light.", "light_pattern", "Mark daylight_light; no craft_type."),
    "DO": ("Daylight Objects.", "unknown_reason", "Classify as missing_shape_evidence/daylight_object_without_shape; no craft_type."),
    "RV": ("Radar-Visual UFO Reports.", "behavior_tags", "Mark radar_visual; no craft_type."),
    "RR": ("Radar UFO Reports.", "behavior_tags", "Mark radar_only; no craft_type."),
    "CE1": ("Close Encounters of the First Kind.", "unknown_reason", "Classify as close_encounter_class_only; no craft_type."),
    "CE2": ("Close Encounters of the Second Kind.", "unknown_reason", "Classify as close_encounter_class_only; no craft_type."),
    "CE3": ("Close Encounters of the Third Kind (Entity Reports).", "unknown_reason", "Classify as close_encounter_class_only/entity_context; no craft_type unless shape evidence exists."),
    "CE4": ("Close Encounters of the Fourth Kind (Abduction Reports).", "unknown_reason", "Classify as close_encounter_class_only/abduction_context; no craft_type unless shape evidence exists."),
    "BH": ("Black or mystery helicopter sightings.", "prosaic_candidate", "Mark mystery_helicopter/prosaic_candidate; no UFO craft_type."),
    "TC": ("Trace reports without UFO, e.g. crop circles.", "unknown_reason", "Classify as non_sighting_context/trace_without_ufo; no craft_type."),
}

VALLEE = {
    "AN1": ("Anomaly with no lasting physical effects such as amorphous lights or unexplained explosions.", "light_pattern", "Mark anomaly_light_or_explosion; no craft_type."),
    "AN2": ("Anomaly with lasting physical effects, e.g. poltergeist, apports, flattened grass.", "behavior_tags", "Mark physical_effect_anomaly; no craft_type."),
    "AN3": ("Anomaly with associated entities such as ghosts, bigfoot, dwarfs.", "unknown_reason", "Classify as encounter_class_only/entity_context; no craft_type."),
    "AN4": ("Personal interaction with entities / out-of-body type experiences.", "unknown_reason", "Classify as encounter_class_only/entity_interaction_context; no craft_type."),
    "FB1": ("Simple sighting of UFO flying by or stationary.", "behavior_tags", "Mark flyby_or_stationary; no craft_type."),
    "FB2": ("Flyby accompanied by physical evidence.", "behavior_tags", "Mark flyby_with_physical_evidence; no craft_type."),
    "FB3": ("Flyby with occupants observed on board.", "unknown_reason", "Classify as encounter_class_only/entity_context; no craft_type."),
    "CE1": ("Close encounter with no physical effects.", "unknown_reason", "Classify as close_encounter_class_only; no craft_type."),
    "CE2": ("Close encounter with physical effects such as EM interference or traces.", "unknown_reason", "Classify as close_encounter_class_only with physical_effect tag; no craft_type."),
    "CE3": ("Close encounter with associated entities near UFO.", "unknown_reason", "Classify as close_encounter_class_only/entity_context; no craft_type unless shape evidence exists."),
    "CE4": ("Close encounter with personal interaction with entities.", "unknown_reason", "Classify as close_encounter_class_only/entity_interaction_context; no craft_type unless shape evidence exists."),
    "CE5": ("Close encounter resulting in permanent injuries or deaths.", "unknown_reason", "Classify as close_encounter_class_only/biological_effect_context; no craft_type."),
    "MA1": ("UFO object with discontinuous trajectory.", "behavior_tags", "Mark maneuvering/discontinuous_trajectory; no craft_type."),
    "MA2": ("Discontinuous trajectory plus physical effects.", "behavior_tags", "Mark maneuvering_with_physical_effects; no craft_type."),
    "MA3": ("Maneuvering object(s) with occupants on board.", "unknown_reason", "Classify as encounter_class_only/entity_context; no craft_type."),
}

SHAPE = {
    "Aircraft": ("Listed in UFOCAT SHAPE table as a principal reported shape.", "prosaic_candidate", "Mark aircraft_like/prosaic_candidate; do not assign UFO craft_type without narrative support."),
    "Copter": ("Listed in UFOCAT SHAPE table as a principal reported shape.", "prosaic_candidate", "Mark helicopter_like/prosaic_candidate; do not assign UFO craft_type without narrative support."),
    "Cloud": ("Listed in UFOCAT SHAPE table as a principal reported shape.", "object_morphology", "Mark object_morphology=cloud_like; do not force craft_type."),
    "Balloon": ("Listed in UFOCAT SHAPE table as a principal reported shape.", "prosaic_candidate", "Mark balloon_like/prosaic_candidate; no UFO craft_type."),
    "Polygon": ("Listed in UFOCAT SHAPE table as a principal reported shape.", "object_morphology", "Mark object_morphology=polygon; possible craft_type only if taxonomy supports polygon."),
}


def load_candidates() -> dict[str, dict]:
    candidate = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
    rows = candidate.get("candidate_rules", [])
    return {
        row.get("candidate_phrase_or_source_code"): row
        for row in rows
        if row.get("source_name") == "ufocat"
    }


def recommended_unknown_reason(raw: str, meaning: str, action: str) -> str:
    lower = f"{raw} {meaning} {action}".lower()
    if "photo" in lower or "sketch" in lower or "picture" in lower:
        return "instrument_or_photo_only"
    if "ce" in raw.lower() or "encounter" in lower or "abduction" in lower or "entity" in lower or "occupant" in lower or "contact" in lower:
        return "close_encounter_class_only"
    if "non-ufo" in lower or "mutilation" in lower or "mib" in lower or "death" in lower:
        return "non_sighting_context"
    return "source_code_needs_decoding"


def infer_review(phrase: str, row: dict) -> dict:
    _, rest = phrase.split(" ", 1)
    field, raw = rest.split(":", 1)
    field_out = field
    meaning = "No supported codebook meaning found in this pass."
    target = "unknown_reason"
    action = "source_code_lookup_needed; keep unresolved until field/value documentation is confirmed."
    evidence_source = ""
    confidence = "unknown"
    false_positive = "Low if field is decoded exactly from the documented UFOCAT field; high if inferred from fallback type_raw without checking raw field."

    if field == "TYPE":
        if raw and raw[0].isdigit():
            if raw in TYPE_SUB:
                meaning, target, action = TYPE_SUB[raw]
                confidence = "high"
                evidence_source = "UFOCAT Codebook 2023.txt, Table 9 KEY TO SUB-TYPE CODES, pages 32-35 / lines about 1523-1672."
            elif len(raw) > 1 and raw[0] in TYPE_MAJOR:
                major_meaning, major_target, major_action = TYPE_MAJOR[raw[0]]
                meaning = f'{major_meaning} Additional subtype sequence "{raw[1:]}" needs position-aware decoding.'
                target = major_target
                action = f"{major_action} For compound code {raw}, implement only after position-aware parser tests."
                confidence = "medium"
                evidence_source = "UFOCAT Codebook 2023.txt, TYPE major definitions and subtype context warning, pages 31-35 / lines about 1448-1672."
                false_positive = "Medium/high: codebook says subtype letters can change meaning by context and position."
            elif raw in TYPE_MAJOR:
                meaning, target, action = TYPE_MAJOR[raw]
                confidence = "high"
                evidence_source = "UFOCAT Codebook 2023.txt, Type of Report definitions, page 31 / lines about 1448-1488."
        elif raw in HYNEK:
            hy_meaning, hy_target, hy_action = HYNEK[raw]
            field_out = "HYNEK (audit surfaced as TYPE/type_raw fallback)"
            meaning = f"Invalid as Saunders TYPE because TYPE first character should be a digit. Matches HYNEK code: {hy_meaning}"
            target = hy_target
            action = f"First fix field disambiguation: apply only when raw.HYNEK == {raw}, not when raw.TYPE == {raw}. {hy_action}"
            confidence = "medium"
            evidence_source = "UFOCAT Codebook 2023.txt: TYPE first character must be digit; HYNEK Table 7 pages 28-29 / lines about 1254-1292."
            false_positive = "High if treated as TYPE. Lower if gated strictly to raw.HYNEK."
        elif raw in VALLEE:
            va_meaning, va_target, va_action = VALLEE[raw]
            field_out = "VALLEE (audit surfaced as TYPE/type_raw fallback)"
            meaning = f"Invalid as Saunders TYPE because TYPE first character should be a digit. Matches VALLEE code: {va_meaning}"
            target = va_target
            action = f"First fix field disambiguation: apply only when raw.VALLEE == {raw}, not when raw.TYPE == {raw}. {va_action}"
            confidence = "medium"
            evidence_source = "UFOCAT Codebook 2023.txt: TYPE first character must be digit; VALLEE Table 8 page 29 / lines about 1313-1438."
            false_positive = "High if treated as TYPE. Lower if gated strictly to raw.VALLEE."
        else:
            meaning = "Not a documented Saunders TYPE value in the local codebook because TYPE should start with digit 0-9."
            evidence_source = "UFOCAT Codebook 2023.txt, TYPE field definition: first character is one digit 0-9; pages 31-35."
            false_positive = "High: likely fallback/misfielded value, e.g. HYNEK, VALLEE, EXPLAN, or imported source code."
    elif field == "HYNEK" and raw in HYNEK:
        meaning, target, action = HYNEK[raw]
        confidence = "high"
        evidence_source = "UFOCAT Codebook 2023.txt, HYNEK Table 7, pages 28-29 / lines about 1254-1292."
        false_positive = "Low if gated to raw.HYNEK and not used as morphology except documented Disc codes."
    elif field == "VALLEE" and raw in VALLEE:
        meaning, target, action = VALLEE[raw]
        confidence = "high"
        evidence_source = "UFOCAT Codebook 2023.txt, VALLEE Table 8, page 29 / lines about 1313-1438."
        false_positive = "Low if treated as encounter/behavior metadata, high if treated as craft morphology."
    elif field == "SHAPE" and raw in SHAPE:
        meaning, target, action = SHAPE[raw]
        confidence = "high" if raw == "Cloud" else "medium"
        evidence_source = "UFOCAT Codebook 2023.txt, SHAPE field and Table 14, page 43 / lines about 2027-2078."
        false_positive = "Medium: SHAPE records reported shape, not certainty that the object was anomalous or craft-like."

    if target not in ALLOWED_TARGETS:
        target = "unknown_reason"

    unknown_reason = recommended_unknown_reason(raw, meaning, action) if target == "unknown_reason" else None
    return {
        "field_name": field_out,
        "raw_value": raw,
        "event_count": row.get("count", 0),
        "candidate_meaning": meaning,
        "evidence_source_for_that_meaning": evidence_source,
        "confidence": confidence,
        "recommended_derived_target": target,
        "recommended_unknown_reason": unknown_reason,
        "recommended_parser_action": action,
        "false_positive_risk": false_positive,
        "example_canonical_event_ids": (row.get("example_canonical_event_ids") or [])[:5],
        "sample_source_text_raw_fields": (row.get("sample_source_text") or [])[:3],
        "source_candidate_key": phrase,
    }


def markdown_cell(value: object) -> str:
    return str(value).replace("|", "/").replace("\n", " ").strip()


def build_reports() -> None:
    by_phrase = load_candidates()
    selected = [f"UFOCAT {field}:{value}" for field, value in PRIORITY]
    for phrase, row in sorted(by_phrase.items(), key=lambda item: item[1].get("count", 0), reverse=True):
        if row.get("count", 0) >= 100 and (
            phrase.startswith("UFOCAT TYPE:")
            or phrase.startswith("UFOCAT HYNEK:")
            or phrase.startswith("UFOCAT VALLEE:")
            or phrase.startswith("UFOCAT SHAPE:")
        ):
            selected.append(phrase)
    selected = list(dict.fromkeys(phrase for phrase in selected if phrase in by_phrase))
    reviews = [infer_review(phrase, by_phrase[phrase]) for phrase in selected]

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "parser_modified": False,
        "artifacts_rebuilt": False,
        "priority_values_requested": [f"{field}:{value}" for field, value in PRIORITY],
        "values_reviewed": len(reviews),
        "reviewed_event_count_sum_not_deduped": sum(row["event_count"] for row in reviews),
        "by_recommended_target": {},
        "by_confidence": {},
        "high_confidence_craft_type_candidates": [],
        "field_disambiguation_required": [],
        "key_findings": [
            "UFOCAT TYPE is a Saunders report/strangeness plus subtype field, not a craft-shape field.",
            "The TYPE first character should be a digit 0-9. Audit values such as TYPE:DD and TYPE:IFO require raw-field disambiguation before parser use.",
            "HYNEK and VALLEE CE2/CE3/CE4 values should be treated as encounter_class_only / close_encounter_class_only metadata unless separate morphology evidence exists.",
            "SHAPE is the principal morphology field. Some SHAPE values are morphology candidates, but Aircraft/Copter are better prosaic/conventional candidates than UFO craft types.",
        ],
    }
    for row in reviews:
        summary["by_recommended_target"][row["recommended_derived_target"]] = summary["by_recommended_target"].get(row["recommended_derived_target"], 0) + row["event_count"]
        summary["by_confidence"][row["confidence"]] = summary["by_confidence"].get(row["confidence"], 0) + row["event_count"]
        if row["recommended_derived_target"] == "craft_type_inferred" and row["confidence"] in {"high", "medium"}:
            summary["high_confidence_craft_type_candidates"].append(
                {
                    "field_name": row["field_name"],
                    "raw_value": row["raw_value"],
                    "event_count": row["event_count"],
                    "meaning": row["candidate_meaning"],
                    "caveat": row["false_positive_risk"],
                }
            )
        if "fallback" in row["field_name"].lower() or row["confidence"] == "unknown" or "position-aware" in row["recommended_parser_action"]:
            summary["field_disambiguation_required"].append(
                {
                    "field_name": row["field_name"],
                    "raw_value": row["raw_value"],
                    "event_count": row["event_count"],
                    "reason": row["false_positive_risk"],
                }
            )

    report = {
        "analysis_policy": "read_only_ufocat_codebook_discovery_no_parser_changes",
        "inputs": {
            "candidate_audit": str(CANDIDATE_PATH),
            "codebook_text": str(CODEBOOK_PATH),
        },
        "codebook_evidence_summary": {
            "type": "TYPE first character is digit 0-9 and represents report/strangeness class; subtype letters are context-dependent.",
            "hynek": "HYNEK codes classify sighting/encounter prototypes; DD/ND are disc morphology, CE values are encounter classes.",
            "vallee": "VALLEE codes classify anomaly/flyby/close-encounter/maneuver classes; CE values are not craft morphology.",
            "shape": "SHAPE contains principal reported shape; values still need prosaic/false-positive guards.",
        },
        "summary": summary,
        "decode_reviews": reviews,
    }
    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")

    lines = [
        "# UFOCAT Codebook Decode Review",
        "",
        "Read-only discovery pass. No parser rules, canonical artifacts, bundles, or deployments were changed.",
        "",
        "## Evidence Sources",
        "",
        f"- Candidate audit: `{CANDIDATE_PATH.as_posix()}`",
        f"- Local codebook text: `{CODEBOOK_PATH.as_posix()}`",
        "- Key codebook findings: `TYPE` is report/strangeness plus context-dependent subtype; `HYNEK` and `VALLEE` are encounter/classification systems; `SHAPE` is the principal morphology field.",
        "",
        "## Summary",
        "",
        f"- Values reviewed: {summary['values_reviewed']}",
        f"- Reviewed event-count sum, not deduped across overlapping candidates: {summary['reviewed_event_count_sum_not_deduped']:,}",
        f"- Recommended targets by count: `{summary['by_recommended_target']}`",
        f"- Confidence by count: `{summary['by_confidence']}`",
        "",
        "## Important Taxonomy Correction",
        "",
        "Do not classify all `HYNEK:CE2/CE3/CE4` or `VALLEE:CE2/CE3/CE4` as `entity_or_encounter_only`. The safer taxonomy is `close_encounter_class_only` or `encounter_class_only`, with entity/abduction/effect tags only when the specific code or narrative supports them.",
        "",
        "## Prioritized Decode Table",
        "",
        "| Field | Raw value | Count | Candidate meaning | Confidence | Target | Parser action | False-positive risk |",
        "|---|---:|---:|---|---|---|---|---|",
    ]
    for row in reviews:
        lines.append(
            f"| {markdown_cell(row['field_name'])} | {markdown_cell(row['raw_value'])} | {row['event_count']:,} | "
            f"{markdown_cell(row['candidate_meaning'])} | {row['confidence']} | {row['recommended_derived_target']} | "
            f"{markdown_cell(row['recommended_parser_action'])} | {markdown_cell(row['false_positive_risk'])} |"
        )

    lines.extend(["", "## High-Confidence Craft-Type Candidates", ""])
    if summary["high_confidence_craft_type_candidates"]:
        for item in summary["high_confidence_craft_type_candidates"][:25]:
            lines.append(f"- `{item['field_name']}:{item['raw_value']}` ({item['event_count']:,}) -> {item['meaning']} Caveat: {item['caveat']}")
    else:
        lines.append("- None from the reviewed high-count values without field-disambiguation caveats.")

    lines.extend(["", "## Field Disambiguation Required", ""])
    for item in summary["field_disambiguation_required"][:40]:
        lines.append(f"- `{item['field_name']}:{item['raw_value']}` ({item['event_count']:,}) - {item['reason']}")

    lines.extend(["", "## Examples", ""])
    for row in reviews[:35]:
        lines.append(f"### {row['source_candidate_key']} ({row['event_count']:,})")
        lines.append(f"- Evidence source: {row['evidence_source_for_that_meaning']}")
        if row.get("recommended_unknown_reason"):
            lines.append(f"- Recommended unknown_reason: `{row['recommended_unknown_reason']}`")
        lines.append(f"- Example IDs: `{', '.join(row['example_canonical_event_ids'])}`")
        if row["sample_source_text_raw_fields"]:
            sample = row["sample_source_text_raw_fields"][0].replace("\n", " ")
            if len(sample) > 500:
                sample = sample[:497] + "..."
            lines.append(f"- Sample raw/source text: `{sample}`")
        lines.append("")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"wrote": [str(OUT_JSON), str(OUT_MD)], "reviews": len(reviews), "summary": summary},
            indent=2,
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    build_reports()
