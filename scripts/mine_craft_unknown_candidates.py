"""Mine read-only candidate rules for unresolved craft-type Unknown rows.

This script intentionally does not change parser rules or rebuild deployable
artifacts. It uses the current craft inference to find rows that still resolve
to ``unknown``, then groups conservative candidate evidence for review.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser.craft_types import infer_event_craft_type, is_unknownish, normalize_text
from parser.taxonomy import display_type_for_web_event, visual_type_group_for_web_event


DEFAULT_INPUT = Path("data/canonical_full_maximal_v3_rehydrated_jurisdiction_repair/deduped_events.jsonl")
DEFAULT_MANIFEST = Path("data/canonical_web/canonical_web_manifest.json")
DEFAULT_OUTPUT_JSON = Path("data/reports/craft_unknown_candidate_rules.json")
DEFAULT_OUTPUT_MD = Path("data/reports/craft_unknown_candidate_rules.md")
DEFAULT_TAXONOMY_JSON = Path("data/reports/craft_unknown_remaining_taxonomy.json")

SAMPLE_LIMIT = 5
TOP_MD_LIMIT = 25

ALLOWED_ACTIONS = {
    "accept_rule",
    "review_manually",
    "ignore_noise",
    "source_code_lookup_needed",
    "classify_unknown_reason_only",
}

ALLOWED_UNKNOWN_REASONS = {
    "missing_shape_evidence",
    "light_without_visible_structure",
    "formation_without_object_shape",
    "source_code_needs_decoding",
    "prosaic_or_conventional_cue",
    "entity_or_encounter_only",
    "instrument_or_photo_only",
    "non_sighting_context",
    "candidate_needs_review",
}

BANNED_STANDALONE_ACCEPT_TERMS = {
    "object",
    "thing",
    "craft",
    "metallic",
    "silver",
    "photo",
    "camera",
    "attached",
    "round",
    "line",
    "glow",
    "aura",
    "trail",
    "light",
}


@dataclass(frozen=True)
class CandidateProposal:
    phrase: str
    bucket: str
    confidence: str
    action: str
    risk: str
    unknown_reason: str
    source_rule: str
    object_morphology: str | None = None
    light_pattern: str | None = None
    formation_type: str | None = None
    behavior_tags: tuple[str, ...] = ()
    prosaic_candidate: bool = False
    evidence: str = ""


@dataclass
class CandidateBucket:
    source_name: str
    candidate_phrase_or_source_code: str
    proposed_bucket: str
    proposed_confidence_tier: str
    false_positive_risk_note: str
    recommended_action: str
    unknown_reason: str
    craft_type_source_rule: str
    object_morphology: str | None
    light_pattern: str | None
    formation_type: str | None
    behavior_tags: tuple[str, ...]
    prosaic_candidate: bool
    count: int = 0
    example_canonical_event_ids: list[str] | None = None
    sample_source_text: list[str] | None = None

    def add(self, event: dict[str, Any], sample_text: str) -> None:
        self.count += 1
        if self.example_canonical_event_ids is None:
            self.example_canonical_event_ids = []
        if self.sample_source_text is None:
            self.sample_source_text = []
        event_id = normalize_text(event.get("canonical_event_id"))
        if event_id and len(self.example_canonical_event_ids) < SAMPLE_LIMIT:
            self.example_canonical_event_ids.append(event_id)
        if sample_text and len(self.sample_source_text) < SAMPLE_LIMIT:
            self.sample_source_text.append(sample_text[:360])

    def to_json(self) -> dict[str, Any]:
        return {
            "source_name": self.source_name,
            "candidate_phrase_or_source_code": self.candidate_phrase_or_source_code,
            "proposed_bucket": self.proposed_bucket,
            "proposed_confidence_tier": self.proposed_confidence_tier,
            "count": self.count,
            "example_canonical_event_ids": self.example_canonical_event_ids or [],
            "sample_source_text": self.sample_source_text or [],
            "false_positive_risk_note": self.false_positive_risk_note,
            "recommended_action": self.recommended_action,
            "derived_fields_prepared": {
                "craft_type_inferred": self.proposed_bucket,
                "craft_type_confidence": self.proposed_confidence_tier,
                "craft_type_evidence": self.sample_source_text or [],
                "craft_type_source_rule": self.craft_type_source_rule,
                "object_morphology": self.object_morphology,
                "light_pattern": self.light_pattern,
                "formation_type": self.formation_type,
                "behavior_tags": list(self.behavior_tags),
                "prosaic_candidate": self.prosaic_candidate,
                "unknown_reason": self.unknown_reason,
            },
        }


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path} line {line_number}: invalid JSON: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path} line {line_number}: expected object")
            yield value


def source_key(event: dict[str, Any]) -> str:
    return normalize_text(event.get("source_name")).lower() or "unknown"


def is_app_facing_unknown(event: dict[str, Any]) -> bool:
    if display_type_for_web_event(event) is None:
        return True
    return visual_type_group_for_web_event(event) == "Other / unknown"


def read_manifest_unknown_count(path: Path) -> int | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    candidates = [
        payload.get("craft_type_counts") if isinstance(payload, dict) else None,
        payload.get("counts", {}).get("craft_type_counts") if isinstance(payload.get("counts"), dict) else None,
        payload.get("summary", {}).get("craft_type_counts") if isinstance(payload.get("summary"), dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            value = candidate.get("unknown")
            if isinstance(value, int):
                return value
    return None


def raw_fields(event: dict[str, Any]) -> dict[str, Any]:
    raw = event.get("raw_fields")
    return raw if isinstance(raw, dict) else {}


def text_blob(event: dict[str, Any]) -> str:
    fields = [
        event.get("type_raw"),
        event.get("type_normalized"),
        event.get("shape_raw"),
        event.get("shape_normalized"),
        event.get("description"),
        event.get("summary"),
    ]
    raw = raw_fields(event)
    for key in ("TYPE", "SHAPE", "HYNEK", "VALLEE", "Characteristics", "Description", "NOTES", "Ufonaut", "Uniform"):
        fields.append(raw.get(key))
    return " ".join(normalize_text(value) for value in fields if normalize_text(value))


def sample_text(event: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("type_raw", "shape_raw", "description", "summary"):
        value = normalize_text(event.get(key))
        if value:
            parts.append(f"{key}: {value[:220]}")
    raw = raw_fields(event)
    for key in ("TYPE", "SHAPE", "HYNEK", "VALLEE", "Characteristics", "NOTES", "Description", "Ufonaut", "Uniform"):
        value = normalize_text(raw.get(key))
        if value:
            parts.append(f"raw.{key}: {value[:220]}")
    return " | ".join(parts)[:720]


def normalized_code(value: Any) -> str:
    return re.sub(r"\s+", "", normalize_text(value).upper())


def first_match(patterns: list[tuple[re.Pattern[str], CandidateProposal]], text: str) -> CandidateProposal | None:
    for pattern, proposal in patterns:
        match = pattern.search(text)
        if match:
            if "{match}" in proposal.phrase:
                phrase = proposal.phrase.replace("{match}", normalize_text(match.group(0)).lower())
                return CandidateProposal(
                    phrase=phrase,
                    bucket=proposal.bucket,
                    confidence=proposal.confidence,
                    action=proposal.action,
                    risk=proposal.risk,
                    unknown_reason=proposal.unknown_reason,
                    source_rule=proposal.source_rule,
                    object_morphology=proposal.object_morphology,
                    light_pattern=proposal.light_pattern,
                    formation_type=proposal.formation_type,
                    behavior_tags=proposal.behavior_tags,
                    prosaic_candidate=proposal.prosaic_candidate,
                    evidence=normalize_text(match.group(0)),
                )
            return proposal
    return None


DIRECT_MORPHOLOGY_PATTERNS: list[tuple[re.Pattern[str], CandidateProposal]] = [
    (
        re.compile(r"\b(?:saucer[- ]?shaped|disc[- ]?shaped|disk[- ]?shaped|discoid(?:al)?|lenticular object)\b", re.I),
        CandidateProposal("{match}", "disc_saucer", "high", "accept_rule", "Explicit compound shape phrase; avoid loose disc/disk by itself.", "candidate_needs_review", "direct_morphology_phrase", object_morphology="disc_saucer"),
    ),
    (
        re.compile(r"\b(?:cigar[- ]?shaped|cigar[- ]?like|cylindrical object|cylinder[- ]?shaped|tube[- ]?shaped|rocket[- ]?shaped|fusiform)\b", re.I),
        CandidateProposal("{match}", "cigar_cylinder", "high", "accept_rule", "Explicit compound shape phrase; not based on generic object alone.", "candidate_needs_review", "direct_morphology_phrase", object_morphology="cigar_cylinder"),
    ),
    (
        re.compile(r"\b(?:triangular object|triangle[- ]?shaped|delta[- ]?shaped|black triangle)\b", re.I),
        CandidateProposal("{match}", "triangle", "high", "accept_rule", "Explicit compound shape phrase.", "candidate_needs_review", "direct_morphology_phrase", object_morphology="triangle"),
    ),
    (
        re.compile(r"\b(?:oval[- ]?shaped|egg[- ]?shaped|eggshaped|elliptical object|football[- ]?shaped)\b", re.I),
        CandidateProposal("{match}", "oval_egg", "high", "accept_rule", "Explicit compound shape phrase.", "candidate_needs_review", "direct_morphology_phrase", object_morphology="oval_egg"),
    ),
    (
        re.compile(r"\b(?:sphere[- ]?shaped|spherical object|ball[- ]?shaped|orb[- ]?like|globular object)\b", re.I),
        CandidateProposal("{match}", "sphere_orb", "high", "accept_rule", "Explicit compound shape phrase.", "candidate_needs_review", "direct_morphology_phrase", object_morphology="sphere_orb"),
    ),
    (
        re.compile(r"\b(?:rectangular object|rectangle[- ]?shaped|box[- ]?shaped|cube[- ]?shaped|square[- ]?shaped)\b", re.I),
        CandidateProposal("{match}", "rectangle_box", "high", "accept_rule", "Explicit compound shape phrase.", "candidate_needs_review", "direct_morphology_phrase", object_morphology="rectangle_box"),
    ),
    (
        re.compile(r"\b(?:cone[- ]?shaped|conical object|pyramid[- ]?shaped)\b", re.I),
        CandidateProposal("{match}", "cone", "high", "accept_rule", "Explicit compound shape phrase.", "candidate_needs_review", "direct_morphology_phrase", object_morphology="cone"),
    ),
    (
        re.compile(r"\b(?:diamond[- ]?shaped|diamond object)\b", re.I),
        CandidateProposal("{match}", "diamond", "high", "accept_rule", "Explicit compound shape phrase.", "candidate_needs_review", "direct_morphology_phrase", object_morphology="diamond"),
    ),
]

FORMATION_PATTERNS: list[tuple[re.Pattern[str], CandidateProposal]] = [
    (
        re.compile(r"\b(?:row of lights|line of lights|string of lights|formation of lights|cluster of lights|fleet of lights|multiple lights in formation)\b", re.I),
        CandidateProposal("{match}", "formation", "medium", "review_manually", "Formation evidence may describe light arrangement rather than object shape.", "formation_without_object_shape", "formation_phrase", formation_type="lights_or_objects_in_formation"),
    ),
]

LIGHT_PATTERN_PATTERNS: list[tuple[re.Pattern[str], CandidateProposal]] = [
    (
        re.compile(r"\b(?:bright light|glowing light|pulsating light|flashing light|stationary light|moving light|light in the sky|points? of light)\b", re.I),
        CandidateProposal("{match}", "light", "low", "classify_unknown_reason_only", "Light-only evidence does not prove object morphology.", "light_without_visible_structure", "light_pattern_phrase", light_pattern="light_only"),
    ),
]

PROSAIC_PATTERNS: list[tuple[re.Pattern[str], CandidateProposal]] = [
    (
        re.compile(r"\b(?:aircraft nearby|airplane nearby|helicopter nearby|balloon|weather balloon|drone|satellite|starlink|venus|mars|meteor|camera artifact|lens flare|probably a|identified as|explained as)\b", re.I),
        CandidateProposal("{match}", "conventional_or_explained", "low", "classify_unknown_reason_only", "Prosaic cue is useful for unknown_reason, not for UFO craft morphology.", "prosaic_or_conventional_cue", "prosaic_cue_phrase", prosaic_candidate=True),
    ),
]

INSTRUMENT_PATTERNS: list[tuple[re.Pattern[str], CandidateProposal]] = [
    (
        re.compile(r"\b(?:madar|webcam|camera|photograph|photo only|attached photo|attached report|video artifact|node detected)\b", re.I),
        CandidateProposal("{match}", "unknown", "none", "classify_unknown_reason_only", "Instrument/photo wording does not establish craft shape.", "instrument_or_photo_only", "instrument_or_photo_phrase"),
    ),
]

ENTITY_PATTERNS: list[tuple[re.Pattern[str], CandidateProposal]] = [
    (
        re.compile(r"\b(?:abduction|abducted|entity|entities|being|beings|humanoid|occupant|ufonaut|creature|close encounter)\b", re.I),
        CandidateProposal("{match}", "unknown", "none", "classify_unknown_reason_only", "Encounter/entity evidence may lack vehicle morphology.", "entity_or_encounter_only", "entity_or_encounter_phrase"),
    ),
]

NON_SIGHTING_CONTEXT_PATTERNS: list[tuple[re.Pattern[str], CandidateProposal]] = [
    (
        re.compile(r"\b(?:document|memorandum|memo|policy|program|committee|contract|report only|newspaper article|book review|ufo organization|conference)\b", re.I),
        CandidateProposal("{match}", "non_ufo_context", "low", "classify_unknown_reason_only", "Context/document terms require record review before excluding as a sighting.", "non_sighting_context", "non_sighting_context_phrase"),
    ),
]


def ufocat_code_proposals(event: dict[str, Any]) -> list[CandidateProposal]:
    if source_key(event) != "ufocat":
        return []
    raw = raw_fields(event)
    proposals: list[CandidateProposal] = []
    seen: set[str] = set()
    for field_name in ("TYPE", "SHAPE", "HYNEK", "VALLEE"):
        value = raw.get(field_name)
        if field_name == "TYPE":
            value = value or event.get("type_raw") or event.get("type_normalized")
        text = normalized_code(value) if field_name == "TYPE" else normalize_text(value)
        if not text or is_unknownish(text):
            continue
        key = f"UFOCAT {field_name}:{text}"
        if key in seen:
            continue
        seen.add(key)
        if field_name == "TYPE":
            proposals.append(
                CandidateProposal(
                    key,
                    "source_code_unmapped",
                    "none",
                    "source_code_lookup_needed",
                    "UFOCAT TYPE is source-native code; decode from codebook before accepting.",
                    "source_code_needs_decoding",
                    "ufocat_source_code",
                )
            )
        elif field_name in {"HYNEK", "VALLEE"} and re.search(r"\bCE[2345]\b", text, re.I):
            proposals.append(
                CandidateProposal(
                    key,
                    "unknown",
                    "none",
                    "classify_unknown_reason_only",
                    "Encounter classification is not vehicle morphology by itself.",
                    "entity_or_encounter_only",
                    "ufocat_encounter_code",
                )
            )
        elif field_name == "SHAPE":
            proposals.append(
                CandidateProposal(
                    key,
                    "source_shape_unmapped",
                    "medium",
                    "source_code_lookup_needed",
                    "UFOCAT SHAPE needs source-code or value lookup before accepting.",
                    "source_code_needs_decoding",
                    "ufocat_shape_code",
                    object_morphology=text.lower(),
                )
            )
    return proposals


def source_specific_candidates(event: dict[str, Any]) -> list[CandidateProposal]:
    source = source_key(event)
    text = text_blob(event)
    proposals: list[CandidateProposal] = []
    if source == "ufocat":
        proposals.extend(ufocat_code_proposals(event))

    for pattern_group in (
        DIRECT_MORPHOLOGY_PATTERNS,
        FORMATION_PATTERNS,
        LIGHT_PATTERN_PATTERNS,
        PROSAIC_PATTERNS,
        INSTRUMENT_PATTERNS,
        ENTITY_PATTERNS,
        NON_SIGHTING_CONTEXT_PATTERNS,
    ):
        proposal = first_match(pattern_group, text)
        if proposal:
            proposals.append(proposal)

    if source == "nuforc":
        raw = raw_fields(event)
        characteristics = normalize_text(raw.get("Characteristics") or event.get("type_raw"))
        if characteristics and not is_unknownish(characteristics):
            proposals.append(
                CandidateProposal(
                    f"NUFORC Characteristics:{characteristics[:80]}",
                    "source_characteristics",
                    "low",
                    "classify_unknown_reason_only",
                    "NUFORC characteristics often describe effects, not craft shape.",
                    "candidate_needs_review",
                    "nuforc_characteristics",
                )
            )
    return proposals


def unknown_reason_for_event(event: dict[str, Any], proposals: list[CandidateProposal]) -> str:
    if proposals:
        reason_counts = Counter(proposal.unknown_reason for proposal in proposals)
        return reason_counts.most_common(1)[0][0]
    text = text_blob(event)
    for pattern_group in (
        NON_SIGHTING_CONTEXT_PATTERNS,
        INSTRUMENT_PATTERNS,
        PROSAIC_PATTERNS,
        ENTITY_PATTERNS,
        FORMATION_PATTERNS,
        LIGHT_PATTERN_PATTERNS,
    ):
        proposal = first_match(pattern_group, text)
        if proposal:
            return proposal.unknown_reason
    return "missing_shape_evidence"


def candidate_key(source: str, proposal: CandidateProposal) -> tuple[Any, ...]:
    return (
        source,
        proposal.phrase,
        proposal.bucket,
        proposal.confidence,
        proposal.action,
        proposal.risk,
        proposal.unknown_reason,
        proposal.source_rule,
        proposal.object_morphology,
        proposal.light_pattern,
        proposal.formation_type,
        proposal.behavior_tags,
        proposal.prosaic_candidate,
    )


def build_reports(input_path: Path, manifest_path: Path, *, limit: int | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_unknown_count = read_manifest_unknown_count(manifest_path)
    totals: Counter[str] = Counter()
    unresolved_by_source: Counter[str] = Counter()
    app_unknown_by_source: Counter[str] = Counter()
    derived_unknown_by_source: Counter[str] = Counter()
    candidate_buckets: dict[tuple[Any, ...], CandidateBucket] = {}
    taxonomy_counts: Counter[str] = Counter()
    taxonomy_by_source: dict[str, Counter[str]] = defaultdict(Counter)
    taxonomy_samples: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    no_candidate_by_source: Counter[str] = Counter()

    for index, event in enumerate(iter_jsonl(input_path), start=1):
        if limit is not None and index > limit:
            break
        totals["events_scanned"] += 1
        source = source_key(event)
        inference = infer_event_craft_type(event)
        derived_unknown = inference.get("craft_type_inferred") == "unknown"
        app_unknown = is_app_facing_unknown(event)

        if app_unknown:
            totals["app_facing_unknown_count"] += 1
            app_unknown_by_source[source] += 1
        if derived_unknown:
            totals["derived_unknown_count"] += 1
            derived_unknown_by_source[source] += 1
        if app_unknown and derived_unknown:
            totals["app_facing_unresolved_unknown_count"] += 1
            unresolved_by_source[source] += 1
            proposals = source_specific_candidates(event)
            if not proposals:
                no_candidate_by_source[source] += 1
            reason = unknown_reason_for_event(event, proposals)
            taxonomy_counts[reason] += 1
            taxonomy_by_source[source][reason] += 1
            sample_key = (source, reason)
            if len(taxonomy_samples[sample_key]) < SAMPLE_LIMIT:
                taxonomy_samples[sample_key].append(
                    {
                        "canonical_event_id": event.get("canonical_event_id"),
                        "date_iso": event.get("date_iso"),
                        "location_raw": event.get("location_raw"),
                        "source_text": sample_text(event),
                    }
                )

            for proposal in proposals:
                key = candidate_key(source, proposal)
                if key not in candidate_buckets:
                    candidate_buckets[key] = CandidateBucket(
                        source_name=source,
                        candidate_phrase_or_source_code=proposal.phrase,
                        proposed_bucket=proposal.bucket,
                        proposed_confidence_tier=proposal.confidence,
                        false_positive_risk_note=proposal.risk,
                        recommended_action=proposal.action,
                        unknown_reason=proposal.unknown_reason,
                        craft_type_source_rule=proposal.source_rule,
                        object_morphology=proposal.object_morphology,
                        light_pattern=proposal.light_pattern,
                        formation_type=proposal.formation_type,
                        behavior_tags=proposal.behavior_tags,
                        prosaic_candidate=proposal.prosaic_candidate,
                    )
                candidate_buckets[key].add(event, sample_text(event))

    candidate_rows = sorted(
        (bucket.to_json() for bucket in candidate_buckets.values()),
        key=lambda row: (-int(row["count"]), str(row["source_name"]), str(row["candidate_phrase_or_source_code"])),
    )

    high_conf = sum(row["count"] for row in candidate_rows if row["recommended_action"] == "accept_rule" and row["proposed_confidence_tier"] == "high")
    medium_conf = sum(row["count"] for row in candidate_rows if row["recommended_action"] in {"accept_rule", "review_manually"} and row["proposed_confidence_tier"] == "medium")
    low_display = sum(row["count"] for row in candidate_rows if row["proposed_confidence_tier"] in {"low", "none"} and row["recommended_action"] != "ignore_noise")
    recoverable_by_source = Counter()
    for row in candidate_rows:
        if row["recommended_action"] in {"accept_rule", "review_manually", "source_code_lookup_needed"}:
            recoverable_by_source[row["source_name"]] += int(row["count"])

    counting_basis_note = (
        "manifest_unknown_count is the current shipped/web artifact craft_type_counts.unknown. "
        "app_facing_unresolved_unknown_count is computed from source/UI unknown rows that still infer to derived unknown in this input. "
        "The two counts are not equivalent unless the same artifact build, source rows, and display/inference logic are being compared."
    )

    summary = {
        "events_scanned": int(totals["events_scanned"]),
        "manifest_unknown_count": manifest_unknown_count,
        "app_facing_unknown_count": int(totals["app_facing_unknown_count"]),
        "app_facing_unresolved_unknown_count": int(totals["app_facing_unresolved_unknown_count"]),
        "derived_unknown_count": int(totals["derived_unknown_count"]),
        "counting_basis_note": counting_basis_note,
        "remaining_unknown_count_by_source": dict(sorted(unresolved_by_source.items(), key=lambda item: (-item[1], item[0]))),
        "app_facing_unknown_count_by_source": dict(sorted(app_unknown_by_source.items(), key=lambda item: (-item[1], item[0]))),
        "derived_unknown_count_by_source": dict(sorted(derived_unknown_by_source.items(), key=lambda item: (-item[1], item[0]))),
        "recoverable_candidate_count_by_source": dict(sorted(recoverable_by_source.items(), key=lambda item: (-item[1], item[0]))),
        "likely_high_confidence_recoveries": int(high_conf),
        "likely_medium_confidence_recoveries": int(medium_conf),
        "low_confidence_display_only_candidates": int(low_display),
        "irreducible_unknowns_without_candidate": int(sum(no_candidate_by_source.values())),
        "candidate_group_count": len(candidate_rows),
    }

    false_positive_traps = [
        row
        for row in candidate_rows
        if row["recommended_action"] != "accept_rule"
        or normalize_text(row["candidate_phrase_or_source_code"]).lower() in BANNED_STANDALONE_ACCEPT_TERMS
    ][:TOP_MD_LIMIT]

    candidate_report = {
        "schema_version": 1,
        "analysis_policy": "read_only_candidate_mining_no_parser_changes",
        "canonical_outputs_mutated": False,
        "inputs": {
            "events_jsonl": str(input_path),
            "manifest": str(manifest_path),
        },
        "allowed_actions": sorted(ALLOWED_ACTIONS),
        "banned_standalone_accept_terms": sorted(BANNED_STANDALONE_ACCEPT_TERMS),
        "summary": summary,
        "top_25_candidate_rules_by_expected_impact": candidate_rows[:TOP_MD_LIMIT],
        "top_25_false_positive_traps": false_positive_traps,
        "candidate_rules": candidate_rows,
    }

    taxonomy_rows = []
    for source, source_counter in sorted(taxonomy_by_source.items()):
        for reason, count in source_counter.most_common():
            taxonomy_rows.append(
                {
                    "source_name": source,
                    "unknown_reason": reason,
                    "count": int(count),
                    "example_events": taxonomy_samples.get((source, reason), []),
                }
            )

    taxonomy_report = {
        "schema_version": 1,
        "analysis_policy": "read_only_unknown_taxonomy_no_parser_changes",
        "canonical_outputs_mutated": False,
        "inputs": {
            "events_jsonl": str(input_path),
            "manifest": str(manifest_path),
        },
        "allowed_unknown_reasons": sorted(ALLOWED_UNKNOWN_REASONS),
        "summary": {
            **summary,
            "unknown_reason_counts": dict(taxonomy_counts.most_common()),
            "unknown_reason_counts_by_source": {
                source: dict(counter.most_common())
                for source, counter in sorted(taxonomy_by_source.items())
            },
        },
        "taxonomy_rows": taxonomy_rows,
    }
    validate_reports(candidate_report, taxonomy_report)
    return candidate_report, taxonomy_report


def validate_reports(candidate_report: dict[str, Any], taxonomy_report: dict[str, Any]) -> None:
    for row in candidate_report.get("candidate_rules", []):
        action = row.get("recommended_action")
        if action not in ALLOWED_ACTIONS:
            raise ValueError(f"Disallowed candidate action: {action}")
        phrase = normalize_text(row.get("candidate_phrase_or_source_code")).lower()
        if action == "accept_rule" and phrase in BANNED_STANDALONE_ACCEPT_TERMS:
            raise ValueError(f"Banned vague standalone accept_rule emitted: {phrase}")
        unknown_reason = row.get("derived_fields_prepared", {}).get("unknown_reason")
        if unknown_reason not in ALLOWED_UNKNOWN_REASONS:
            raise ValueError(f"Disallowed candidate unknown_reason: {unknown_reason}")
    for row in taxonomy_report.get("taxonomy_rows", []):
        reason = row.get("unknown_reason")
        if reason not in ALLOWED_UNKNOWN_REASONS:
            raise ValueError(f"Disallowed taxonomy reason: {reason}")


def write_markdown(path: Path, candidate_report: dict[str, Any], taxonomy_report: dict[str, Any]) -> None:
    summary = candidate_report["summary"]
    lines: list[str] = []
    lines.append("# Craft Unknown Candidate Rules Audit")
    lines.append("")
    lines.append("Read-only audit. No parser, canonical web, static bundle, Cloudflare bundle, or deployment artifacts were changed.")
    lines.append("")
    lines.append("## Counting Basis")
    lines.append("")
    lines.append(f"- Manifest unknown count: `{summary.get('manifest_unknown_count')}`")
    lines.append(f"- App-facing unresolved unknown count: `{summary.get('app_facing_unresolved_unknown_count')}`")
    lines.append(f"- Note: {summary.get('counting_basis_note')}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    for key in (
        "events_scanned",
        "app_facing_unknown_count",
        "derived_unknown_count",
        "candidate_group_count",
        "likely_high_confidence_recoveries",
        "likely_medium_confidence_recoveries",
        "low_confidence_display_only_candidates",
        "irreducible_unknowns_without_candidate",
    ):
        lines.append(f"- {key}: `{summary.get(key)}`")
    lines.append("")
    lines.append("## Remaining Unknown Count By Source")
    lines.append("")
    for source, count in summary.get("remaining_unknown_count_by_source", {}).items():
        lines.append(f"- `{source}`: `{count}`")
    lines.append("")
    lines.append("## Recoverable Candidate Count By Source")
    lines.append("")
    for source, count in summary.get("recoverable_candidate_count_by_source", {}).items():
        lines.append(f"- `{source}`: `{count}`")
    lines.append("")
    lines.append("## Unknown Reason Taxonomy")
    lines.append("")
    for reason, count in taxonomy_report["summary"].get("unknown_reason_counts", {}).items():
        lines.append(f"- `{reason}`: `{count}`")
    lines.append("")
    lines.append("## Top 25 Candidate Rules By Expected Impact")
    lines.append("")
    lines.append("| Count | Source | Candidate | Proposed Bucket | Confidence | Action | Risk |")
    lines.append("|---:|---|---|---|---|---|---|")
    for row in candidate_report.get("top_25_candidate_rules_by_expected_impact", []):
        lines.append(
            "| {count} | `{source}` | `{candidate}` | `{bucket}` | `{confidence}` | `{action}` | {risk} |".format(
                count=row["count"],
                source=row["source_name"],
                candidate=str(row["candidate_phrase_or_source_code"]).replace("|", "\\|")[:120],
                bucket=row["proposed_bucket"],
                confidence=row["proposed_confidence_tier"],
                action=row["recommended_action"],
                risk=str(row["false_positive_risk_note"]).replace("|", "\\|")[:180],
            )
        )
    lines.append("")
    lines.append("## Top 25 False-Positive Traps")
    lines.append("")
    lines.append("| Count | Source | Candidate | Action | Risk |")
    lines.append("|---:|---|---|---|---|")
    for row in candidate_report.get("top_25_false_positive_traps", []):
        lines.append(
            "| {count} | `{source}` | `{candidate}` | `{action}` | {risk} |".format(
                count=row["count"],
                source=row["source_name"],
                candidate=str(row["candidate_phrase_or_source_code"]).replace("|", "\\|")[:120],
                action=row["recommended_action"],
                risk=str(row["false_positive_risk_note"]).replace("|", "\\|")[:180],
            )
        )
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--taxonomy-json", type=Path, default=DEFAULT_TAXONOMY_JSON)
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    candidate_report, taxonomy_report = build_reports(args.input, args.manifest, limit=args.limit)
    write_json(args.output_json, candidate_report)
    write_json(args.taxonomy_json, taxonomy_report)
    write_markdown(args.output_md, candidate_report, taxonomy_report)
    print(
        json.dumps(
            {
                "ok": True,
                "candidate_rules": len(candidate_report.get("candidate_rules", [])),
                "summary": candidate_report.get("summary", {}),
                "outputs": {
                    "candidate_rules_json": str(args.output_json),
                    "candidate_rules_md": str(args.output_md),
                    "taxonomy_json": str(args.taxonomy_json),
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
