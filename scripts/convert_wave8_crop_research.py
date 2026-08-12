from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

try:
    from scripts import build_context_evidence_campaign as campaign
    from scripts.context_evidence_attempt_fingerprint import stamp_attempt_fingerprint
except (ImportError, ModuleNotFoundError):  # Direct execution resolves sibling modules from scripts/.
    import build_context_evidence_campaign as campaign
    from context_evidence_attempt_fingerprint import stamp_attempt_fingerprint


WAVE_ID = "wave-008-crop-strict-conversion"
FROZEN_AT = "2026-08-12T01:31:17Z"
ROSTER_MANIFEST_SHA256 = "2fcbbf64cfa34e9368ecf6c61d7a5d7abda724983efe700142c813452ec3b58d"
ROSTER_SHA256 = "40ff8049f7224d3589bcfdbd6c8a5ad3a20ce8cbd9acc88c4f219faea23519a2"
RESEARCH_A_MANIFEST_SHA256 = "1075a382b4ec9ebc3849bb6ac8924b49e8395dfbf69e67806917bf8fb9118246"
RESEARCH_A_PACKET_SHA256 = "4d9145edb60e8fd68285d0a6408d166b566d47a7d302534907909166d88a7d58"
RESEARCH_A_ATTEMPTS_SHA256 = "9548fcb3398f59a92dbd2d1f03f242ec69eae172e7c5f9dd9ccf8a4849bb8555"
RESEARCH_B_MANIFEST_SHA256 = "5d571c191906ee96871f3e8304d506e415ea79e889c653c6c29354765dec935d"
RESEARCH_B_PACKET_SHA256 = "210e674c5eb365dc98c8b00781f0425c0973d57b65b97981e519a5f4133899a7"
RESEARCH_B_ATTEMPTS_SHA256 = "530e61e44e8593aac9be18fd7e88299a0b179d18a7678068f4e0025416c58b17"
WAVE7_SOURCE_LEDGER_SHA256 = "ec0f40e5428dc566faf1739daaa0ae610ff05ef63b9c56c6b8bfc487c09504cf"

MATERIAL_ORDINALS = {2, 3, 4, 6, 9, 11, 14, 15, 16, 17, 19, 20, 21, 23, 24}
EXACT_DAY_ORDINALS = {2, 9}

G0 = [
    "exact_occurrence_day",
    "date_provenance",
    "source_supported_coordinates",
    "location_provenance",
    "review_quorum",
    "qualifying_source",
    "stable_identity",
    "conflict_resolution",
]
G1 = G0 + ["uncertainty_within_1km"]
G2 = [
    "source_supported_coordinates",
    "uncertainty_within_1km",
    "location_provenance",
    "review_quorum",
    "stable_identity",
    "conflict_resolution",
]
G3 = [
    "exact_occurrence_day",
    "date_provenance",
    "source_supported_coordinates",
    "uncertainty_within_1km",
    "location_provenance",
    "review_quorum",
    "stable_identity",
    "conflict_resolution",
]


class ConversionError(ValueError):
    pass


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def canonical_line(row: Mapping[str, Any]) -> bytes:
    return campaign.canonical_json_bytes(dict(row))


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_id(prefix: str, value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{prefix}_{digest_text(payload)[:24]}"


def verify_sha(path: Path, expected: str, label: str) -> None:
    actual = campaign.sha256_file(path)
    if actual != expected:
        raise ConversionError(f"{label} SHA-256 mismatch: expected {expected}, got {actual}")


def date_only(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", value)
    return match.group(1) if match else None


def normalize_confidence(value: str) -> str:
    return "medium" if value in {"medium_high", "medium"} else value if value in {"high", "low"} else "low"


def normalize_polarity(value: str) -> str:
    lowered = value.casefold()
    if "contradict" in lowered or "conflict" in lowered:
        return "contradicts"
    if "unknown" in lowered or "unresolved" in lowered or "blocks_" in lowered:
        return "unknown"
    if "report" in lowered or "date_role_only" in lowered or "upper_bound" in lowered or "limits_" in lowered:
        return "reports"
    return "supports"


def source_id(content_sha: str) -> str:
    return f"src_{content_sha[:24]}"


def family_id(label: str) -> str:
    return f"sf_{digest_text(label)[:24]}"


def lead_source(family: str, label: str, title: str, locator: str, accessed_at: str) -> dict[str, Any]:
    return {
        "schemaId": "ufo-timeline-context-evidence-source-v1.0.0",
        "sourceId": f"src_{digest_text('lead-only:' + label)[:24]}",
        "sourceFamilyId": family,
        "title": title,
        "publisher": title,
        "publicationDate": None,
        "authors": [],
        "locator": {"kind": "bibliographic", "value": locator, "accessedAt": accessed_at, "pageOrSection": "Upstream lineage named by the retained downstream source; full text not retained."},
        "accessStatus": "inaccessible",
        "contentSha256": None,
        "sourceTier": "lead_only",
        "rights": {"status": "rights_unknown", "redistributionAllowed": False, "license": None, "notes": "Lineage-only record; no retained content and no evidentiary independence credit."},
        "retention": {"class": "metadata_only", "storageLocation": None, "decision": "Retain only to preserve fail-closed source lineage."},
        "derivation": {"derivedFromSourceIds": [], "relation": "original"},
        "independenceStatus": "lead_only",
        "registeredAt": FROZEN_AT,
    }


def a_source_cards(research_a_root: Path, wave7_source_ledger: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    verify_sha(wave7_source_ledger, WAVE7_SOURCE_LEDGER_SHA256, "Wave 7 proposal source ledger")
    wave7 = {row["contentSha256"]: row for row in jsonl(wave7_source_ledger) if row.get("contentSha256")}
    required_reused = {
        "09539fab6aca623aedf95fa10cf76481615a1c21ce8710be20cfed3437c65117",
        "7429165d86f8b03574907fafb3860b564de44ef940656881a50b83800d4d22ff",
    }
    if not required_reused.issubset(wave7):
        raise ConversionError("Wave 7 source ledger does not contain both frozen Rockville source cards")
    cards = [dict(wave7[item]) for item in sorted(required_reused)]

    # CBS is explicitly a syndication. Preserve that fact with a lineage-only
    # upstream instead of repeating the invalid empty-upstream Wave 7 card.
    for index, card in enumerate(tuple(cards)):
        if str(card.get("contentSha256") or "").startswith("7429165d"):
            upstream = lead_source(
                card["sourceFamilyId"],
                "vacaville-reporter-rockville-2003",
                "Vacaville Reporter Rockville account",
                "Vacaville Reporter account relayed by CBS News on 2003-07-12",
                "2026-08-11",
            )
            cards.append(upstream)
            card = dict(card)
            card["derivation"] = {"derivedFromSourceIds": [upstream["sourceId"]], "relation": "syndication"}
            card["independenceStatus"] = "same_family"
            cards[index] = card

    metadata: dict[str, dict[str, Any]] = {
        "b13f45971ee6cf024f383c59f443ffa112b289976991271d58d840fb65a86bf8": {
            "family": "sf_wave8_osm_nominatim", "title": "Nominatim reverse geocode of the deployed Rockville marker", "publisher": "OpenStreetMap Nominatim", "publication": None, "authors": [], "url": "https://nominatim.openstreetmap.org/reverse?lat=38.2429774&lon=-122.1252947&format=jsonv2&zoom=18&addressdetails=1", "path": "web_extracts/nominatim_rockville_marker_reverse.json", "tier": "official", "independence": "unknown", "rights": "open",
        },
        "3d1d809000a70f5befec407c787a6a08e7e1718ac5300f351847686248fcb1e0": {
            "family": "sf_wave8_revista_ufo_gevaerd_prudentopolis", "title": "Relatorio inicial sobre o Agroglifo de Prudentopolis", "publisher": "Folha da Terra / Revista UFO field report", "publication": "2015-10-09", "authors": ["A. J. Gevaerd"], "url": "https://www.folhadaterraweb.com.br/noticias/geral/capa/2015/10/relatorio-inicial-sobre-o-agroglifo-de-prudentopolis-.html?pagina=455", "path": "web_extracts/turn207_folha_terra_prudentopolis.txt", "tier": "primary", "independence": "independent",
        },
        "f75d884b8356da4b9112bdd01f74b738c65ecd0eb54b605c351f79952be92236": {
            "family": "sf_wave8_gazeta_do_povo", "title": "Circulos em plantacao de trigo em Prudentopolis chamam a atencao", "publisher": "Gazeta do Povo", "publication": "2015-10-09", "authors": ["Diego Ribeiro"], "url": "https://www.gazetadopovo.com.br/vida-e-cidadania/circulos-em-plantacao-de-trigo-em-prudentopolis-chamam-a-atencao-de-ufologos-d0k0hdpqjhr32wsb5p6hv8lri/", "path": "web_extracts/turn207_gazeta_prudentopolis.txt", "tier": "contemporaneous", "independence": "unknown",
        },
        "fd8d1b921ccd0aceadbcce6c725242cf42f0b377296735894951a0ff5c4ebb4d": {
            "family": "sf_wave8_folha_uol", "title": "Circulos em plantacoes assustam moradores do PR e SC", "publisher": "Folha de S.Paulo", "publication": "2015-10-27", "authors": [], "url": "https://brasil.blogfolha.uol.com.br/2015/10/27/circulos-em-plantacoes-assustam-moradores-do-pr-e-sc/", "path": "web_extracts/turn207_folha_uol_prudentopolis.txt", "tier": "secondary", "independence": "independent",
        },
        "eba54a74a057be8df95d473a590e78272826cc55fdc3ca0a1e5aac6b5e1e3f85": {
            "family": "sf_wave8_ihdohll_ipuacu", "title": "Fenomeno dos agroglifos se repete em Ipuacu", "publisher": "Ivo Hugo Dohll", "publication": "2016-11-05", "authors": ["Ivo Hugo Dohl"], "url": "https://ihdohll.blogspot.com/2016/11/", "path": "web_extracts/turn208_ihdohll_ipuacu.txt", "tier": "primary", "independence": "independent",
        },
        "098efd7caedbbdf8379413f9e5ef1a927967f148a632401e2fbde034e09a5c80": {
            "family": "sf_wave8_temporary_temples", "title": "2002 Crop Circles photographic archive", "publisher": "Temporary Temples", "publication": None, "authors": [], "url": "https://temporarytemples.co.uk/crop-circles/2002-crop-circles", "path": "web_extracts/turn209_temporary_temples_waden.txt", "tier": "primary", "independence": "independent",
        },
        "e0769e951394296c67929f85b0b3846382025c1f608be8d550baa5f52cad351d": {
            "family": "sf_wave8_sarraltroff_creator_disclosure", "title": "Le crop circle du mois de juin a Sarraltroff ne vient pas des extra-terrestres", "publisher": "Radio Melodie", "publication": "2018-08-24", "authors": ["Cedric Kempf"], "url": "https://www.radiomelodie.com/actu/10212-le-crop-circle-du-mois-de-juin-a-sarraltroff-ne-vient-pas-des-extra-terrestres.html", "path": "web_extracts/turn209_radio_melodie_sarraltroff.txt", "tier": "contemporaneous", "independence": "same_family",
        },
        "7921288a2d13a45690946b3592fc8981ea11a37d8d8f82e874aeec57a17b3538": {
            "family": "sf_wave8_sarraltroff_creator_disclosure", "title": "Le crop circle de Sarraltroff etait l'oeuvre d'une bande de youtubeurs", "publisher": "Dernieres Nouvelles d'Alsace", "publication": "2018-08-31", "authors": ["Marie Gall"], "url": "https://www.dna.fr/religions/2018/08/31/le-crop-circle-etait-l-oeuvre-d-une-bande-de-youtubeurs", "path": "web_extracts/turn209_dna_sarraltroff.txt", "tier": "contemporaneous", "independence": "same_family",
        },
        "6a94ea77162ccc7c8ed867d685e37fd419a85667023db3884c12d4b59789b4e5": {
            "family": "sf_wave8_wrzesnia_info", "title": "Kregi w zbozu. Tajemnicze zjawisko w gminie Wrzesnia", "publisher": "wrzesnia.info.pl", "publication": "2021-07-16", "authors": [], "url": "https://wrzesnia.info.pl/pl/19_wiadomosci-z-regionu/635_wrzesnia/15781_kregi-w-zbozu-tajemnicze-zjawisko-w-gminie-wrzesnia.html", "path": "web_extracts/turn210_wrzesnia_local.txt", "tier": "contemporaneous", "independence": "unknown",
        },
        "5c9259c76648d24332bfd736be7302e9d6fbceb75e2c45dae1ab79a48b5c30f2": {
            "family": "sf_wave8_topagrar", "title": "Tajemnicze kregi w zbozu, znowu w Wielkopolsce", "publisher": "topagrar.pl", "publication": "2021-07-17", "authors": ["Dorota Kolasinska"], "url": "https://www.topagrar.pl/articles/aktualnosci/tajemnicze-kregi-w-zbozu-znowu-w-wielkopolsce-2459039", "path": "web_extracts/turn210_topagrar_wrzesnia.txt", "tier": "contemporaneous", "independence": "unknown",
        },
    }

    for content_sha, item in metadata.items():
        evidence_path = research_a_root / item["path"]
        verify_sha(evidence_path, content_sha, f"Wave 8 A source {content_sha[:12]}")
        is_open = item.get("rights") == "open"
        cards.append({
            "schemaId": "ufo-timeline-context-evidence-source-v1.0.0",
            "sourceId": source_id(content_sha),
            "sourceFamilyId": family_id(item["family"]),
            "title": item["title"],
            "publisher": item["publisher"],
            "publicationDate": item["publication"],
            "authors": item.get("authors", []),
            "locator": {"kind": "url", "value": item["url"], "accessedAt": "2026-08-11", "pageOrSection": "Frozen attributed extract or exact JSON response retained in the Wave 8 A packet."},
            "accessStatus": "retrieved",
            "contentSha256": content_sha,
            "sourceTier": item["tier"],
            "rights": {"status": "open_license" if is_open else "copyright_link_only", "redistributionAllowed": bool(is_open), "license": "ODbL 1.0" if is_open else None, "notes": "OpenStreetMap attribution required." if is_open else "Copyright retained; frozen extract is restricted to internal research and provenance."},
            "retention": {"class": "canonical_source" if is_open else "restricted", "storageLocation": str(evidence_path), "decision": "Retain on D through adjudication; publish only accepted facts and permitted links."},
            "derivation": {"derivedFromSourceIds": [], "relation": "original"},
            "independenceStatus": item["independence"],
            "registeredAt": FROZEN_AT,
        })
    return cards, {row["contentSha256"]: row["sourceId"] for row in cards if row["contentSha256"]}


def map_b_tier(value: str) -> str:
    lowered = value.casefold()
    if "field_video_description_metadata" in lowered:
        return "secondary"
    if any(token in lowered for token in ("primary", "field_investigator", "photographer")):
        return "primary"
    if "contemporaneous" in lowered:
        return "contemporaneous"
    return "secondary"


def b_source_cards(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    cards: list[dict[str, Any]] = []
    packet_to_canonical: dict[str, str] = {}
    for case in rows:
        for item in case.get("sources", []):
            content_sha = item["rawSha256"]
            raw_path = Path(item["rawPath"])
            verify_sha(raw_path, content_sha, f"Wave 8 B source {item['sourceId']}")
            if raw_path.stat().st_size != item["bytes"]:
                raise ConversionError(f"Wave 8 B source byte mismatch: {raw_path}")
            family = family_id(item["sourceFamilyId"])
            relation = "original"
            upstream_ids: list[str] = []
            independence_text = str(item.get("independenceStatus") or "").casefold()
            if "underlying_iccra_interview_lineage" in independence_text:
                upstream = lead_source(family, "iccra-northwood-2005", "ICCRA Northwood interview lineage", "ICCRA interview lineage named by the retained Earthfiles report", "2026-08-12")
                cards.append(upstream)
                upstream_ids = [upstream["sourceId"]]
                relation = "retelling"
            elif "publisher is a republisher" in independence_text:
                upstream = lead_source(family, "renata-kralova-bohdankov-video", "Renata Kralova field video", "Field video credited by the retained YouTube metadata page", "2026-08-12")
                cards.append(upstream)
                upstream_ids = [upstream["sourceId"]]
                relation = "index"
            elif "sda_syndication" in independence_text:
                upstream = lead_source(family, "sda-buren-2019", "Swiss News Agency (SDA) report", "SDA report republished by 1815.ch", "2026-08-12")
                cards.append(upstream)
                upstream_ids = [upstream["sourceId"]]
                relation = "syndication"
            elif "epa_photo_wire" in independence_text:
                upstream = lead_source(family, "epa-yonhap-buren-2019", "EPA / Yonhap photo-wire record", "EPA/Yonhap record republished by Daum", "2026-08-12")
                cards.append(upstream)
                upstream_ids = [upstream["sourceId"]]
                relation = "syndication"
            independence = (
                "independent"
                if any(token in independence_text for token in ("original", "primary_party", "first_person", "named_field", "photographer_source"))
                else "same_family"
                if any(token in independence_text for token in ("lineage", "republisher", "syndication", "wire_family"))
                else "unknown"
            )
            if upstream_ids:
                independence = "same_family"
            canonical_id = source_id(content_sha)
            packet_to_canonical[item["sourceId"]] = canonical_id
            author = item.get("author")
            authors = [author] if isinstance(author, str) and author.strip() else []
            cards.append({
                "schemaId": "ufo-timeline-context-evidence-source-v1.0.0",
                "sourceId": canonical_id,
                "sourceFamilyId": family,
                "title": item["title"],
                "publisher": item["publisher"],
                "publicationDate": date_only(item.get("publicationDate")),
                "authors": authors,
                "locator": {"kind": "url", "value": item["url"], "accessedAt": date_only(item["accessedAt"]) or "2026-08-12", "pageOrSection": item["locator"]},
                "accessStatus": "retrieved",
                "contentSha256": content_sha,
                "sourceTier": map_b_tier(item["sourceTier"]),
                "rights": {"status": "copyright_link_only", "redistributionAllowed": False, "license": None, "notes": "Copyright retained; raw capture is restricted to internal research and provenance."},
                "retention": {"class": "restricted", "storageLocation": str(raw_path), "decision": "Retain on D through adjudication; do not publish raw bytes."},
                "derivation": {"derivedFromSourceIds": upstream_ids, "relation": relation},
                "independenceStatus": independence,
                "registeredAt": FROZEN_AT,
            })
    return cards, packet_to_canonical


def make_assertion(case_id: str, field: str, value: Any, sources: list[str], locators: list[dict[str, str]], confidence: str, polarity: str, evidence: list[str]) -> dict[str, Any]:
    seed = {"caseId": case_id, "fieldName": field, "value": value, "sourceIds": sorted(sources), "evidenceSha256": sorted(evidence), "waveId": WAVE_ID}
    return {
        "schemaId": "ufo-timeline-context-evidence-assertion-v1.0.0",
        "assertionId": stable_id("cea", seed),
        "caseId": case_id,
        "domain": "crop_circle",
        "fieldName": field,
        "value": value,
        "sourceIds": sorted(sources),
        "sourceLocators": sorted(locators, key=lambda item: item["sourceId"]),
        "confidence": normalize_confidence(confidence),
        "polarity": normalize_polarity(polarity),
        "evidenceSha256": sorted(evidence),
        "waveId": WAVE_ID,
        "assertedAt": FROZEN_AT,
    }


def a_assertions(rows: list[dict[str, Any]], by_hash: Mapping[str, str]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for case in rows:
        for item in case.get("candidateAssertions", []):
            evidence = item["evidenceSha256"]
            if evidence not in by_hash:
                raise ConversionError(f"Wave 8 A assertion references unknown evidence {evidence}")
            source = by_hash[evidence]
            field = item["field"]
            value = item.get("value")
            mapped_field = {
                "formation_date": "formation_date",
                "occurrence_interval": "formation_date",
                "discovery_date": "discovery_date",
                "photography_date": "photography_date",
                "event_site_description": "location_label",
                "classification": "primary_classification",
                "morphology_and_condition": "morphology",
            }.get(field, "associated_claim")
            if field == "occurrence_interval":
                start, end = str(value).split("/", 1)
                value = {"start": start, "end": end, "dateRole": item.get("dateRole", "formation_interval")}
            elif field == "formation_date" and value is None:
                mapped_field = "associated_claim"
                value = {"claimType": "exact_formation_date_unknown", "observedValue": "source explicitly says exact formation time unknown", "conflictsWith": "2021-07-13"}
            elif mapped_field == "associated_claim":
                claim_type = {
                    "identity_cluster": "identity_nonmerge",
                    "coordinate_provenance_check": "coordinate_alignment",
                }.get(field, field)
                value = {"claimType": claim_type, "observedValue": value}
            if mapped_field == "location_label" and case["caseId"] == "cc_f57d09d334a8":
                value = "rural property beside the road linking BR-277 to Prudentopolis, no more than 1 km from town"
            output.append(make_assertion(
                case["caseId"], mapped_field, value, [source],
                [{"sourceId": source, "locator": item["locator"]}],
                item["confidence"], item["polarity"], [evidence],
            ))
    return output


def b_assertions(rows: list[dict[str, Any]], packet_source_ids: Mapping[str, str], source_rows: Mapping[str, dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for case in rows:
        for item in case.get("evidenceFindings", []):
            sources = [packet_source_ids[source] for source in item["sourceIds"]]
            evidence = [source_rows[source]["contentSha256"] for source in sources]
            locators = [{"sourceId": source, "locator": source_rows[source]["locator"]["pageOrSection"]} for source in sources]
            field = item["field"]
            role = item.get("dateRole")
            value = item["observedValue"]
            polarity = item["polarity"]
            if field == "date":
                if role == "discovery":
                    mapped_field = "discovery_date"
                elif role == "publication":
                    mapped_field = "publication_date"
                elif role in {"formation_interval", "reported_formation_interval"}:
                    mapped_field = "formation_date"
                    value = {"start": value["start"], "end": value["end"], "dateRole": role}
                elif role == "field_video":
                    mapped_field = "photography_date"
                else:
                    mapped_field = "associated_claim"
                    value = {"claimType": role or "reported_date", "observedValue": value}
            elif field.startswith("location."):
                mapped_field = "location_label"
            elif field == "classification":
                mapped_field = "primary_classification"
            elif field == "morphology.size":
                mapped_field = "morphology"
            elif field == "coordinates":
                coordinate_claim = {
                    "claimType": "source_coordinate_with_unknown_uncertainty",
                    "observedValue": {"lat": value["lat"], "lon": value["lon"]},
                    "coordinateMethod": item.get("coordinateMethod"),
                    "coordinateUncertaintyM": None,
                }
                output.append(make_assertion(case["caseId"], "associated_claim", coordinate_claim, sources, locators, item["confidence"], polarity, evidence))
                continue
            else:
                mapped_field = "associated_claim"
                value = {"claimType": field, "observedValue": value}
            output.append(make_assertion(case["caseId"], mapped_field, value, sources, locators, item["confidence"], polarity, evidence))
    return output


def attempt_result(text: str, *, status: str | None = None, http_status: int | None = None) -> str:
    lowered = f"{status or ''} {text}".casefold()
    if http_status == 403 or "403" in lowered or "unsafe" in lowered or "access_denied" in lowered:
        return "inaccessible"
    if "tls" in lowered or "failed_nonretryable" in lowered:
        return "failed"
    if "not_same_case" in lowered or "other_yancey" in lowered or "irrelevant" in lowered:
        return "irrelevant"
    if "duplicate empty" in lowered:
        return "duplicate"
    if any(token in lowered for token in ("frozen_substantive", "frozen_primary", "opened_frozen_extract", "opened_raw_json_frozen")):
        return "material_gain"
    if any(token in lowered for token in ("qualified", "found ", "corroborated", "confirmed", "same_lead", "surfaced a july", "surfaced already-frozen")) and not lowered.strip().startswith("no"):
        return "useful_lead"
    return "no_gain"


def queue_attempt(case_id: str, kind: str, target: str, version: str | None, phase: str, result: str, attempted_at: str) -> dict[str, Any]:
    seed = f"{case_id}\0{kind}\0{target}\0{version or ''}"
    return stamp_attempt_fingerprint({
        "attemptId": f"ra_{digest_text(seed)[:24]}",
        "kind": kind,
        "target": target,
        "versionSha256": version,
        "fingerprint": "0" * 64,
        "automatic": False,
        "phase": phase,
        "result": result,
        "attemptedAt": attempted_at,
    })


def a_attempts(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        attempts: list[dict[str, Any]] = []
        for item in row["queries"]:
            phase = "escalation" if item.get("phase") == "coordinate_escalation" else "first_pass"
            attempts.append(queue_attempt(row["caseId"], "query", item["target"], None, phase, attempt_result(item["outcome"]), "2026-08-11T00:00:00Z"))
        for item in row["openings"]:
            opened = item["sourceOpenAttempt"]
            version = item.get("evidenceSha256")
            phase = "escalation" if row["escalationUsed"] else "first_pass"
            attempts.append(queue_attempt(row["caseId"], "source_open", opened["target"], version, phase, attempt_result(item.get("outcome", ""), status=item.get("status")), "2026-08-11T00:00:00Z"))
        output[row["caseId"]] = attempts
    return output


def b_attempts(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        attempts: list[dict[str, Any]] = []
        for item in row["queries"]:
            attempts.append(queue_attempt(row["caseId"], "query", item["target"], None, "first_pass", attempt_result(item["outcome"]), "2026-08-12T01:28:26Z"))
        for item in row["openings"]:
            attempts.append(queue_attempt(row["caseId"], "source_open", item["target"], item.get("rawSha256"), "first_pass", attempt_result(item["outcome"], http_status=item.get("httpStatus")), "2026-08-12T01:28:26Z"))
        output[row["caseId"]] = attempts
    return output


def missing_gates(ordinal: int) -> list[str]:
    if ordinal == 1:
        return G0
    if ordinal == 2:
        return G2
    if ordinal == 9:
        return G2
    if ordinal in MATERIAL_ORDINALS:
        return G3
    return G1


def build_queue(
    roster: list[dict[str, Any]],
    attempts: Mapping[str, list[dict[str, Any]]],
    assertions: list[dict[str, Any]],
    sources: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    assertion_sources: dict[str, set[str]] = {}
    for assertion in assertions:
        assertion_sources.setdefault(assertion["caseId"], set()).update(assertion["sourceIds"])
    rows: list[dict[str, Any]] = []
    for item in roster:
        ordinal = int(item["ordinal"])
        gates = sorted(missing_gates(ordinal))
        status = "materially_upgraded" if ordinal in MATERIAL_ORDINALS else "no_gain"
        independent_families = {
            sources[source_id]["sourceFamilyId"]
            for source_id in assertion_sources.get(item["caseId"], set())
            if sources[source_id]["sourceTier"] != "lead_only"
            and sources[source_id]["independenceStatus"] == "independent"
        }
        query_budget = {
            "firstPassQueries": 2,
            "firstPassSourceOpenings": 4,
            "escalationQueries": 3,
            "escalationSourceOpenings": 4,
            "archiveFallbacks": 1,
            "escalationApproved": ordinal == 2,
            "escalationFocusGate": None,
        }
        if ordinal == 2:
            query_budget["escalationFocusGate"] = "source_supported_coordinates"
        terminal = "materially_upgraded" if ordinal in MATERIAL_ORDINALS else "no_gain"
        blockers = {
            f"roster_ordinal_{ordinal}",
            "sealed_wave8_packets_authoritative",
            "automatic_retry_prohibited",
            "review_and_deduplication_pending",
            f"terminal_{terminal}",
        }
        for attempt in attempts[item["caseId"]]:
            if attempt["result"] in {"failed", "inaccessible"}:
                blockers.add(f"{attempt['result']}_target_recorded_no_retry")
        row = {
            "schemaId": "ufo-timeline-context-evidence-research-queue-v1.0.0",
            "queueId": stable_id("rq", {"wave": WAVE_ID, "caseId": item["caseId"]}),
            "caseId": item["caseId"], "candidateId": None, "domain": "crop_circle", "lane": "case_enrichment",
            "caseClass": "crop_exact_coordinate" if ordinal == 1 else "crop_candidate_field",
            "missingStrictGates": gates,
            "priorityInputs": {"missingStrictGateCount": len(gates), "independentSourceFamilyCount": len(independent_families), "exactOccurrenceDay": ordinal in EXACT_DAY_ORDINALS, "sourceSupportedCoordinate": False},
            "priorityScore": 0, "rank": 0,
            "queryBudget": query_budget,
            "attempts": attempts[item["caseId"]],
            "blockers": sorted(blockers),
            "waveId": WAVE_ID, "status": status, "terminalDisposition": status, "candidateDisposition": None,
            "createdAt": FROZEN_AT, "updatedAt": FROZEN_AT,
        }
        row["priorityScore"] = campaign.queue_priority_score(row)
        rows.append(row)
    rows.sort(key=lambda row: (-row["priorityScore"], row["caseId"], row["queueId"]))
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
    return rows


def file_identity(path: Path, rows: int | None = None) -> dict[str, Any]:
    result = {"path": str(path), "bytes": path.stat().st_size, "sha256": campaign.sha256_file(path)}
    if rows is not None:
        result["rowCount"] = rows
    return result


def validate_package(campaign_root: Path, sources: list[dict[str, Any]], assertions: list[dict[str, Any]], queue: list[dict[str, Any]]) -> None:
    contract_root = campaign_root / "contracts" / "v1"
    schemas = {name: campaign.load_json(contract_root / filename) for name, filename in campaign.CONTRACTS.items()}
    campaign._validate_rows(sources, campaign._validator(schemas["source"], "source"), "source")
    campaign._validate_rows(assertions, campaign._validator(schemas["assertion"], "assertion"), "assertion")
    campaign._validate_rows(queue, campaign._validator(schemas["queue"], "queue"), "queue")
    source_map = campaign.validate_sources(sources)
    campaign.validate_assertions(assertions, source_map)
    for assertion in assertions:
        if assertion["fieldName"] == "formation_date" and isinstance(assertion["value"], Mapping):
            value = assertion["value"]
            if not isinstance(value.get("start"), str) or not isinstance(value.get("end"), str):
                raise ConversionError(f"Date interval is not projection-compatible: {assertion['assertionId']}")
        if assertion["fieldName"] in {"latitude", "longitude"}:
            raise ConversionError("Wave 8 cannot project numeric coordinates without source-stated uncertainty")
    reconciliation = campaign.load_json(campaign_root / "state" / "known_source_reconciliation.json")
    known = campaign.validate_known_source_reconciliation(reconciliation)
    existing_queue = jsonl(campaign_root / "ledgers" / "research_queue.jsonl")
    known.update(attempt["fingerprint"] for row in existing_queue for attempt in row["attempts"])
    campaign.validate_queue(queue, known)

    canonical_ids = {
        "source": {row["sourceId"] for row in jsonl(campaign_root / "ledgers" / "source_ledger.jsonl")},
        "assertion": {row["assertionId"] for row in jsonl(campaign_root / "ledgers" / "case_enrichment.jsonl")},
        "queue": {row["queueId"] for row in existing_queue},
    }
    collisions = {
        "source": canonical_ids["source"].intersection(row["sourceId"] for row in sources),
        "assertion": canonical_ids["assertion"].intersection(row["assertionId"] for row in assertions),
        "queue": canonical_ids["queue"].intersection(row["queueId"] for row in queue),
    }
    if any(collisions.values()):
        raise ConversionError(f"Canonical ID collision: {collisions}")
    attempt_count = sum(len(row["attempts"]) for row in queue)
    if len(sources) != 30 or len(assertions) != 49 or len(queue) != 25 or attempt_count != 84:
        raise ConversionError(
            f"Wave 8 output count mismatch: sources={len(sources)} assertions={len(assertions)} "
            f"queue={len(queue)} attempts={attempt_count}"
        )
    if sum(row["status"] == "materially_upgraded" for row in queue) != 15:
        raise ConversionError("Wave 8 material-upgrade count must remain 15")
    if any(row["status"] == "strict_ready" for row in queue):
        raise ConversionError("Wave 8 conversion cannot confer strict-ready status")
    rockville = next(row for row in queue if row["caseId"] == "cc_ae1b8ee2ae1f")
    if set(rockville["missingStrictGates"]) != set(G2) or rockville["queryBudget"].get("escalationFocusGate") != "source_supported_coordinates":
        raise ConversionError("Rockville must retain every unresolved strict gate and one explicit research focus")


def write_package(args: argparse.Namespace) -> Path:
    roster_root = args.roster_root.resolve()
    research_a_root = args.research_a_root.resolve()
    research_b_root = args.research_b_root.resolve()
    output_root = args.output_root.resolve()
    campaign_root = args.campaign_root.resolve()
    wave7_sources = args.wave7_source_ledger.resolve()

    verify_sha(roster_root / "manifest.json", ROSTER_MANIFEST_SHA256, "Wave 8 roster manifest")
    verify_sha(roster_root / "roster.jsonl", ROSTER_SHA256, "Wave 8 roster")
    verify_sha(research_a_root / "manifest.json", RESEARCH_A_MANIFEST_SHA256, "Wave 8 research A manifest")
    verify_sha(research_a_root / "research_packet.jsonl", RESEARCH_A_PACKET_SHA256, "Wave 8 research A packet")
    verify_sha(research_a_root / "attempts.jsonl", RESEARCH_A_ATTEMPTS_SHA256, "Wave 8 research A attempts")
    verify_sha(research_b_root / "manifest.json", RESEARCH_B_MANIFEST_SHA256, "Wave 8 research B manifest")
    verify_sha(research_b_root / "research_packet.jsonl", RESEARCH_B_PACKET_SHA256, "Wave 8 research B packet")
    verify_sha(research_b_root / "attempts.jsonl", RESEARCH_B_ATTEMPTS_SHA256, "Wave 8 research B attempts")
    roster = jsonl(roster_root / "roster.jsonl")
    a_rows = jsonl(research_a_root / "research_packet.jsonl")
    b_rows = jsonl(research_b_root / "research_packet.jsonl")
    a_receipts = jsonl(research_a_root / "attempts.jsonl")
    b_receipts = jsonl(research_b_root / "attempts.jsonl")
    if [row["ordinal"] for row in roster] != list(range(1, 26)):
        raise ConversionError("Wave 8 roster must contain exact ordinals 1-25")
    if [row["rosterOrdinal"] for row in a_rows] != list(range(1, 13)) or [row["ordinal"] for row in b_rows] != list(range(13, 26)):
        raise ConversionError("Wave 8 research packets do not cover exact frozen roster partitions")

    a_sources, a_by_hash = a_source_cards(research_a_root, wave7_sources)
    b_sources, b_packet_ids = b_source_cards(b_rows)
    sources_by_id = {row["sourceId"]: row for row in a_sources + b_sources}
    if len(sources_by_id) != len(a_sources) + len(b_sources):
        raise ConversionError("Wave 8 source normalization produced duplicate IDs")
    sources = sorted(sources_by_id.values(), key=lambda row: row["sourceId"])
    assertions = a_assertions(a_rows, a_by_hash) + b_assertions(b_rows, b_packet_ids, sources_by_id)
    assertions.sort(key=lambda row: row["assertionId"])
    attempts = a_attempts(a_receipts)
    attempts.update(b_attempts(b_receipts))
    queue = build_queue(roster, attempts, assertions, sources_by_id)
    validate_package(campaign_root, sources, assertions, queue)

    if output_root.exists() and any(output_root.iterdir()):
        raise ConversionError(f"Output directory must be empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    files = {
        "source_ledger.jsonl": sources,
        "case_enrichment.jsonl": assertions,
        "research_queue.jsonl": queue,
    }
    for name, rows in files.items():
        (output_root / name).write_bytes(b"".join(canonical_line(row) for row in rows))
    (output_root / "case_review_decisions.jsonl").write_bytes(b"")
    readme = (
        "# Wave 8 crop ledger proposals\n\n"
        "Deterministic proposal-only conversion of the frozen Wave 8 crop roster and research A/B packets. "
        "No assertion is reviewed or strict-ready. Date intervals, contradictory catalog roles, unknown coordinate uncertainty, "
        "source-family dependence, failed openings, and automatic-retry prohibitions remain explicit.\n"
    )
    (output_root / "README.md").write_text(readme, encoding="utf-8", newline="\n")
    manifest = {
        "schemaId": "context-evidence-wave8-crop-ledger-proposal-manifest-v1.0.0",
        "waveId": WAVE_ID,
        "packetId": "wave-008-crop-ledger-proposals",
        "generatedAt": FROZEN_AT,
        "proposalOnly": True,
        "inputs": [
            file_identity(roster_root / "manifest.json"), file_identity(roster_root / "roster.jsonl", 25),
            file_identity(research_a_root / "manifest.json"), file_identity(research_a_root / "research_packet.jsonl", 12), file_identity(research_a_root / "attempts.jsonl", 12),
            file_identity(research_b_root / "manifest.json"), file_identity(research_b_root / "research_packet.jsonl", 13), file_identity(research_b_root / "attempts.jsonl", 13),
            file_identity(wave7_sources),
        ],
        "scope": {"rosterCases": 25, "materiallyUpgradedCases": 15, "noGainCases": 10, "sourceProposals": len(sources), "fieldAssertionProposals": len(assertions), "terminalQueueRows": 25, "attemptReceipts": 84, "reviewDecisions": 0, "strictReadyPromotions": 0},
        "scientificInvariants": {"ufoProximityUsed": False, "cropOrientationUsed": False, "causality": "not_asserted", "traceEligible": False, "dateIntervalsPreserved": True, "coordinateUncertaintyInvented": False, "reviewIndependentFromAuthenticity": True},
        "outputs": [
            file_identity(output_root / "source_ledger.jsonl", len(sources)),
            file_identity(output_root / "case_enrichment.jsonl", len(assertions)),
            file_identity(output_root / "research_queue.jsonl", len(queue)),
            file_identity(output_root / "case_review_decisions.jsonl", 0),
            file_identity(output_root / "README.md"),
        ],
        "validation": {"status": "pass", "runCount": 1, "correctionPassUsed": False, "validator": "campaign contracts plus canonical no-repeat and ID collision checks"},
    }
    (output_root / "manifest.json").write_bytes(campaign.canonical_json_bytes(manifest))
    return output_root / "manifest.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert frozen Wave 8 crop research into fail-closed proposal ledgers.")
    parser.add_argument("--roster-root", type=Path, required=True)
    parser.add_argument("--research-a-root", type=Path, required=True)
    parser.add_argument("--research-b-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--wave7-source-ledger", type=Path, required=True)
    parser.add_argument("--campaign-root", type=Path, default=campaign.DEFAULT_CAMPAIGN_ROOT)
    return parser.parse_args()


def main() -> int:
    try:
        manifest = write_package(parse_args())
    except (ConversionError, campaign.CampaignValidationError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"Wave 8 crop conversion failed: {exc}")
        return 1
    print(f"Wave 8 crop proposal package: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
