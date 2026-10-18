"""Build a bounded, source-pinned collection-motif sidecar; never modify the corpus.

Inputs are reviewed research units, not validated incidents. Regex rules code only
reviewer-stated targets/actions; they never promote keyword candidates to positives.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import date
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess

SCHEMA = "ufo-collection-evidence-v1"
MAX_BYTES = 5 * 1024 * 1024
MATERIALS = [
 ("soil", "Soil / earth / sand"), ("flowers", "Flowers / buds"),
 ("grass", "Grass / herbs / moss"), ("leaves_wood", "Leaves / twigs / wood"),
 ("crops_fruit", "Crops / fruit"), ("plants_unspecified", "Other / unspecified plants"),
 ("fungi", "Fungi"), ("minerals", "Rocks / minerals"), ("water_ice", "Water / ice / snow"),
 ("other", "Other stated material"), ("unspecified", "Material unspecified")]
ACTIONS = [
 ("taking", "Picking / taking / gathering"), ("extraction", "Extracting / siphoning"), ("digging", "Digging / probing ground"),
 ("examining", "Examining / touching"), ("carrying", "Carrying / loading"),
 ("container", "Putting material in container"), ("transfer", "Transfer from a person"),
 ("interest", "Interest / communication"), ("damage", "Damage / traces only"),
 ("unspecified", "Act unspecified")]
MATERIAL_PATTERNS = {
 "soil": r"\b(?:soil|earth|dirt|sand|mud|substrate)\b",
 "flowers": r"\b(?:flowers?|buds?|hydrangea)\b",
 "grass": r"\b(?:grass|grasses|herbs?|moss(?:es)?|weeds?)\b",
 "leaves_wood": r"\b(?:leaves|leaf|foliage|twigs?|wood|limbs?|branches?|trees?)\b",
 "crops_fruit": r"\b(?:apples?|fruit|tomato(?:es)?|potato(?:es)?|tobacco|sugar[ -]?cane|cane|corn|maize|beans?|cotton|malanga)\b",
 "plants_unspecified": r"\b(?:plants?|vegetation|shrubs?|bush(?:es)?|hedges?|roots?)\b",
 "fungi": r"\b(?:fungi|mushrooms?)\b", "minerals": r"\b(?:stones?|rocks?|boulders?|ore|basalt|pumice|pebbles?|crystals?|gemstones?)\b",
 "water_ice": r"\b(?:water|ice|snow)\b", "other": r"\b(?:oil|air|rat|animal|ammonia|fertilizer)\b"}
ACTION_PATTERNS = {
 "taking": r"\b(?:take|takes|taking|took|taken|collect\w*|pick\w*|gather\w*|pluck\w*|harvest\w*|uproot\w*|cutting|remov\w*)\b",
 "extraction": r"\b(?:extract\w*|siphon\w*|vacuum\w*|suck\w*)\b",
 "digging": r"\b(?:dig|digs|digging|dug|excavat\w*|insert\w*|prob\w*|shovell?\w*|scratching|stab\w*|spade)\b",
 "examining": r"\b(?:examin\w*|inspect\w*|touch\w*|look\w*|study|studying|smell\w*|tast\w*)\b",
 "carrying": r"\b(?:carr\w*|load\w*|holding|held|aboard)\b",
 "container": r"\b(?:put|puts|putting|place|places|placed|fill\w*|bagging|scoop\w*)\b.{0,80}\b(?:box|bag|pail|container|tube|canister)\b",
 "transfer": r"\b(?:from (?:the )?witness|from (?:a )?person|accept\w*|offered|human mushroom bag|transfer)\b",
 "interest": r"\b(?:interest|asks?|request|communicat\w*)\b",
 "damage": r"\b(?:traces?|damage|destroy|destruction|burnt|scorch\w*)\b"}
# These phrases describe the review procedure, not a particular material or act.
BOILERPLATE = re.compile(r"Retrieved narrative explicitly reports occupants/entities taking, collecting or examining named soil/plant material; claim classification only, not confirmation\.?|Existing reviewer retains an uncertainty or adjacent context; not a simple direct environmental sampling positive\.?|Examination/probing claim; do not upgrade it to removed samples\.?", re.I)
NEGATIVE = re.compile(r"\b(?:no|not|never|without|unseen|unobserved)\b", re.I)


def digest(raw): return hashlib.sha256(raw).hexdigest()
def compact(obj): return (json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
def load(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def pin(path, role):
 raw = Path(path).read_bytes()
 return {"file": Path(path).name, "sha256": digest(raw), "bytes": len(raw), "role": role}
def safe_url(value):
 value = str(value or "").strip()
 return value if re.match(r"^https?://[^\s<>]+$", value, re.I) else ""
def strings(value): return [str(x) for x in value if x] if isinstance(value, list) else []
def url_list(values): return sorted(set(filter(None, (safe_url(v) for v in values))))

def codes(row):
 # Target fields and non-generic reviewer summaries are the sole coding surface.
 # Do not scan background botanical mentions in the discovery excerpt.
 target = str(row.get("target") or "")
 action = BOILERPLATE.sub("", str(row.get("action") or row.get("observed_behavior") or ""))
 # Retain affirmative clauses only; negated removal must not become taking.
 clauses = [x.strip() for x in re.split(r"[.;|]", action) if x.strip()]
 positive = " ".join(x for x in clauses if not NEGATIVE.search(x))
 material_text = target if target else positive
 materials = [key for key, pattern in MATERIAL_PATTERNS.items() if re.search(pattern, material_text, re.I)]
 # Generic "soil/plant" in review prose does not establish either specimen.
 if not materials: materials = ["unspecified"]
 actions = [key for key, pattern in ACTION_PATTERNS.items() if re.search(pattern, positive, re.I)] or ["unspecified"]
 return materials, actions, {"materialBasis": "reviewed_target" if target else "reviewed_act_summary", "actionBasis": "affirmative_reviewed_act_clauses", "codedText": action.strip()[:1600]}

def ordinal(iso):
 try: return (date.fromisoformat(str(iso)[:10]) - date(1970, 1, 1)).days
 except (ValueError, TypeError): return None

def date_bounds(record):
 iso = str(record.get("date_iso") or record.get("sort_date_iso") or "")
 precision = str(record.get("date_precision") or "unknown")
 day = ordinal(iso)
 if day is None: return None, None
 year, month = int(iso[:4]), int(iso[5:7])
 if precision in {"year", "year_only"}: return ordinal(f"{year:04}-01-01"), ordinal(f"{year:04}-12-31")
 if precision in {"month", "month_only"}:
  next_month = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
  return ordinal(f"{year:04}-{month:02}-01"), (next_month - date(1970, 1, 1)).days - 1
 if precision not in {"exact_day", "day", "exact"}: return None, None
 end = ordinal(record.get("end_date_iso"))
 return day, end if end is not None else day

COUNTRY_ALIASES = {
 "us": "United States", "usa": "United States", "united states": "United States", "u.s.a.": "United States",
 "uk": "United Kingdom", "gb": "United Kingdom", "gbr": "United Kingdom", "england": "United Kingdom", "scotland": "United Kingdom", "wales": "United Kingdom",
 "fr": "France", "fra": "France", "france": "France", "br": "Brazil", "bra": "Brazil", "brazil": "Brazil", "brasil": "Brazil",
 "ar": "Argentina", "arg": "Argentina", "argentina": "Argentina", "it": "Italy", "ita": "Italy", "italy": "Italy", "italia": "Italy",
 "es": "Spain", "esp": "Spain", "spain": "Spain", "au": "Australia", "aus": "Australia", "australia": "Australia",
 "ca": "Canada", "can": "Canada", "canada": "Canada", "mx": "Mexico", "mex": "Mexico", "mexico": "Mexico",
 "nz": "New Zealand", "nzl": "New Zealand", "new zealand": "New Zealand", "cl": "Chile", "chi": "Chile", "chile": "Chile",
 "ve": "Venezuela", "ven": "Venezuela", "venezuela": "Venezuela", "za": "South Africa", "south africa": "South Africa",
 "ru": "Russia", "rus": "Russia", "russia": "Russia", "ussr": "Soviet Union (source label)", "soviet union": "Soviet Union (source label)",
 "cn": "China", "chn": "China", "china": "China", "do": "Dominican Republic", "dom": "Dominican Republic",
 "pe": "Peru", "per": "Peru", "peru": "Peru", "ph": "Philippines", "phi": "Philippines", "philippines": "Philippines",
 "pr": "Puerto Rico", "pri": "Puerto Rico", "puerto rico": "Puerto Rico", "pt": "Portugal", "por": "Portugal", "portugal": "Portugal",
 "fi": "Finland", "fin": "Finland", "finland": "Finland", "se": "Sweden", "swe": "Sweden", "sweden": "Sweden",
 "zw": "Zimbabwe", "zim": "Zimbabwe", "zimbabwe": "Zimbabwe", "de": "Germany", "deu": "Germany", "germany": "Germany",
}
# Country names are explicit source tokens, never inferred from these polygons.
COUNTRY_NAMES_FILE = Path(__file__).resolve().parents[1] / "data/world_countries.geojson"
if COUNTRY_NAMES_FILE.exists():
 for feature in load(COUNTRY_NAMES_FILE).get("features", []):
  name = feature.get("properties", {}).get("name")
  if name: COUNTRY_ALIASES.setdefault(name.casefold(), name)
def country(record):
 raw = record.get("raw_source_row") or record.get("raw_fields") or {}
 source = str(record.get("source") or "")
 for key in ["country", "Country", "COUNTRY", "key_vals/Country"]:
  value = str(record.get(key) or raw.get(key) or "").strip()
  if value.upper() == "CN" and source == "ufocat": return "Canada", "source_specific_country_code"
  if value.upper() == "CA" and source == "ufocat": continue
  if value.casefold() in COUNTRY_ALIASES: return COUNTRY_ALIASES[value.casefold()], "source_country_field"
 parts = [x.strip() for x in str(record.get("location_raw") or "").split(",")]
 for part in list(reversed(parts))[:3] + parts[:1]:
  if part.upper() == "CN" and source == "ufocat": return "Canada", "source_specific_location_code"
  if part.upper() == "CA" and source == "ufocat": continue
  if part.casefold() in COUNTRY_ALIASES: return COUNTRY_ALIASES[part.casefold()], "explicit_location_token"
 return "Unknown / unresolved", "unknown"

def sanitize_case(row, ids):
 sources = []
 for s in row.get("sources", []):
  if not isinstance(s, dict): continue
  sources.append({k: str(s[k])[:2000] for k in ["source_id", "title", "locator", "primary_status"] if s.get(k)} | {"url": safe_url(s.get("url"))})
 materials, actions, coding = codes(row)
 return {"caseId": str(row["case_id"]), "title": str(row.get("title") or row["case_id"]),
  "dateLabel": str(row.get("date") or row.get("date_iso") or "Unknown"), "datePrecision": str(row.get("date_precision") or "not normalized; see source"),
  "location": str(row.get("place") or row.get("location") or ""), "country": str(row.get("country") or "Unknown / unresolved"),
  "disposition": str(row.get("disposition") or "ambiguous"), "scope": str(row.get("scope") or "review_needed"),
  "observedBehavior": str(row.get("observed_behavior") or ""), "limitations": strings(row.get("limitations")),
  "sources": sources, "earliestSource": row.get("earliest_source") or "", "sourceAccess": str(row.get("source_access") or row.get("provenance_tier") or "qualified"),
  "sourceFamily": str(row.get("source_family") or ""), "aliases": strings(row.get("aliases")),
  "eventIds": strings(row.get("event_ids")), "originalCandidateReportIds": strings(row.get("event_ids")), "indexedReportIds": [x for x in strings(row.get("event_ids")) if x in ids],
  "joinMeaning": "Original dossier associations joined by current report ID only; narrative identity and version disagreements remain.",
  "joinStatus": "linked_reviewed_report" if any(x in ids for x in strings(row.get("event_ids"))) else "not_joined_to_reviewed_report",
  "reportedDate": str(row.get("reported_date") or ""), "postedDate": str(row.get("posted_date") or ""),
  "materials": materials, "actions": actions, "coding": coding, "countUnit": "dossier entry; excluded from catalog report matrices"}

def finalize_runtime_metadata(payload, args):
 """Join pinned browser-effective metadata without changing any canonical record."""
 pins = []
 facet_path = Path(args.facet_reviews)
 if facet_path.exists():
  reviews = load(facet_path).get("records", [])
  by_id = {str(x["eventId"]): x for x in payload["reports"]}
  valid_materials = {x[0] for x in MATERIALS}; valid_actions = {x[0] for x in ACTIONS}
  for review in reviews:
   event_id = str(review["event_id"]); row = by_id.get(event_id)
   if not row or row["source"] != review["source"] or row["sourceId"] != str(review["source_id"]): raise ValueError("Facet review identity mismatch")
   if digest(row["coding"]["codedText"].encode("utf-8")) != review["expected_coded_text_sha256"]: raise ValueError("Facet review text guard mismatch")
   if not review["materials"] or not set(review["materials"]) <= valid_materials or not review["actions"] or not set(review["actions"]) <= valid_actions: raise ValueError("Unknown reviewed facet")
   row["materials"] = review["materials"]; row["actions"] = review["actions"]
   row["coding"]["manualReview"] = {"reason": review["reason"], "reviewFile": facet_path.name, "codedTextSha256": review["expected_coded_text_sha256"]}
  pins.append(pin(facet_path, "guarded semantic facet corrections"))
 helper = Path(__file__).with_name("collection_effective_metadata.cjs")
 result = subprocess.run([args.node, str(helper), str(args.shared_root)], input=json.dumps(payload["reports"]), text=True, encoding="utf-8", capture_output=True, check=True)
 projection = json.loads(result.stdout); indexed = {str(x["eventId"]): x for x in projection["metadata"]}
 for row in payload["reports"]:
  projected = indexed.get(row["eventId"])
  if not projected: continue
  row["effectiveMetadataOverlays"] = projected["applied"]
  effective = projected.get("effective") or {}
  if "analysis_repair_detail" in projected["applied"]:
   row.setdefault("importedDate", {"dateIso": row["dateIso"], "datePrecision": row["datePrecision"], "startOrdinal": row["startOrdinal"], "endOrdinal": row["endOrdinal"]})
   start, end = date_bounds(effective)
   row.update(dateIso=effective.get("date_iso") or effective.get("sort_date_iso") or "",datePrecision=effective.get("date_precision") or "unknown",startOrdinal=start,endOrdinal=end)
   row["dateRecovery"] = {"contract": effective.get("date_recovery_contract"), "intervalSemantics": effective.get("date_interval_semantics"), "exactDayEligible": effective.get("exact_day_eligible") is True}
  if effective.get("country"):
   nation, basis = country({"source": row["source"],"country": effective["country"],"location_raw": row["location"]})
   if nation != "Unknown / unresolved": row.update(country=nation,countryBasis="guarded_runtime_country_field")
  display = projected.get("locationDisplay")
  if display:
   row.setdefault("locationRaw", row["location"]); row["location"] = display
   reviewed = projected.get("reviewedLocation") or {}
   if reviewed.get("country"):
    nation,basis = country({"source":row["source"],"country":reviewed["country"],"location_raw":display})
   else:
    nation,basis = country({"source":row["source"],"location_raw":display})
   if row["country"] == "Unknown / unresolved" and nation != "Unknown / unresolved": row.update(country=nation,countryBasis="runtime_explicit_location_display_token")
 pins.extend(projection["inputPins"])
 audit_path = Path(args.complementary_coverage)
 if audit_path.exists():
  audit = load(audit_path); counts = audit["counts"]; manual = audit["manual_review"]
  payload.setdefault("coverage", {})["complementaryPass"] = {"recordsScreened":counts["current_rows_scanned"], "narratives":counts["rows_with_narrative"], "newLexicalCandidates":counts["novel_candidate_rows"], "manualContextsReviewed":manual["manual_context_reviews"], "retainedRows":manual["retained_additional_report_rows"], "remainingUnreviewed":audit["candidate_queue"]["unreviewed_in_this_agent"], "newDirectSoilPlant":manual["new_direct_soil_or_plant_collection_rows"]}
  pins.append(pin(audit_path,"sanitized complementary full-corpus coverage counts"))
 payload["policy"]["runtimeMetadata"] = "Current pinned date and quality overlays are applied with the same guard implementations as the browser. Month/year intervals are calendar bounds, never observed exact dates; location display labels do not assert coordinates."
 return pins, projection["receipt"]

def refresh_runtime_metadata(args):
 output = Path(args.output); manifest = load(output / "manifest.json")
 packed = (output / "evidence.json.gz").read_bytes(); decoded = gzip.decompress(packed)
 if digest(packed) != manifest["artifact"]["gzipSha256"] or digest(decoded) != manifest["artifact"]["decodedSha256"]: raise ValueError("Existing sparse sidecar integrity mismatch")
 payload = json.loads(decoded); pins, receipt = finalize_runtime_metadata(payload,args)
 decoded = compact(payload); packed = gzip.compress(decoded,compresslevel=9,mtime=0)
 if len(decoded)>MAX_BYTES or re.search(rb"[A-Za-z]:[\\/]Users[\\/]",decoded): raise ValueError("Public output size/privacy guard")
 artifact = manifest["artifact"]; artifact.update(gzipBytes=len(packed),decodedBytes=len(decoded),gzipSha256=digest(packed),decodedSha256=digest(decoded))
 manifest["inputPins"] = list({(x["file"],x["role"]): x for x in manifest["inputPins"]+pins}.values())
 manifest["policy"] = payload["policy"]; manifest["metadataOverlayReceipt"] = receipt; manifest["builderPin"] = pin(Path(__file__),"reproducible sidecar builder")
 (output/"evidence.json.gz").write_bytes(packed); (output/"manifest.json").write_bytes(compact(manifest))
 print(json.dumps({"artifact":artifact,"metadataOverlayReceipt":receipt},indent=2))
 return manifest


def build(args):
 source = Path(args.dossier_dir)
 base = load(source / "reviewed_report_rows.json")["records"]
 case_rows = load(source / "case_dossiers.json")["cases"]
 pins = [pin(COUNTRY_NAMES_FILE, "country names only; no polygon geocoding")] + [pin(source / name, role) for name, role in [("reviewed_report_rows.json", "reviewed report register"), ("case_dossiers.json", "curated dossier including controls"), ("coverage_manifest.json", "original search coverage"), ("source_ledger.json", "source genealogy")]]
 for path in args.additions:
  addition = load(path)
  base.extend(addition.get("records", [])); case_rows.extend(addition.get("cases", []))
  pins.append(pin(path, "additional manual review"))
 source_review = load(args.source_review) if args.source_review else {}
 if args.source_review:
  pins.append(pin(args.source_review, "bounded original-source follow-up and annotations"))
  case_rows.extend(source_review.get("new_web_extensions", []))
  # These dossiers link reviewed representations without adding new catalog reports.
  case_rows.extend(source_review.get("additional_report_candidates", []))
  case_rows.extend(x for x in source_review.get("screening_controls", []) if x.get("case_id"))
 date_annotations = {str(x["event_id"]): x for x in source_review.get("source_precision_annotations", [])}
 actor_annotations = {str(event_id): x for x in source_review.get("actor_annotations", []) for event_id in x.get("event_ids", [])}
 seen = set()
 for row in base:
  key = str(row["event_id"])
  if key in seen: raise ValueError(f"Repeated reviewed event ID: {key}")
  seen.add(key)
 encounter_path = Path(args.encounters)
 raw = encounter_path.read_bytes(); pins.append(pin(encounter_path, "current indexed being and abduction facets"))
 encounters = {str(x["eventId"]): x for x in json.loads(gzip.decompress(raw))["rows"]}
 groups = defaultdict(list)
 for row in base: groups[row["chunk_id"]].append(row)
 reports, chunk_pins = [], []
 for chunk, values in sorted(groups.items()):
  path = Path(args.shared_root) / "data/canonical_web/event_chunks" / f"{chunk}.json.gz"
  chunk_raw = path.read_bytes(); detail = json.loads(gzip.decompress(chunk_raw))
  chunk_pins.append({"chunkId": chunk, "gzipSha256": digest(chunk_raw), "gzipBytes": len(chunk_raw)})
  for row in values:
   index = int(row["detail_index"]); canonical = detail[index]
   expected = (str(row["event_id"]), str(row["source"]), str(row["source_id"]))
   actual = (str(canonical.get("event_id")), str(canonical.get("source")), str(canonical.get("source_id")))
   if actual != expected: raise ValueError(f"Canonical identity mismatch at {chunk}:{index}: {expected} != {actual}")
   annotation = date_annotations.get(expected[0], {})
   if annotation and str(annotation.get("source_id")) != expected[2]: raise ValueError("Source precision annotation identity mismatch")
   actor_note = actor_annotations.get(expected[0], {})
   encounter = encounters.get(expected[0]); enc_join = bool(encounter and str(encounter.get("source")) == expected[1] and str(encounter.get("sourceEventId")) == expected[2])
   material, action, coding = codes(row); start, end = date_bounds(canonical); nation, nation_basis = country(canonical)
   if nation == "Unknown / unresolved" and row.get("review_country") in COUNTRY_ALIASES.values(): nation, nation_basis = str(row["review_country"]), "reviewed_explicit_narrative_country"
   # A report member's matched narrative can differ from the primary row; preserve it.
   reports.append({"eventId": expected[0], "source": expected[1], "sourceId": expected[2],
    "canonicalJoinStatus": "validated_id_source_chunk_index", "chunkId": chunk, "detailIndex": index,
    "dateLabel": str(canonical.get("date_raw") or row.get("date_raw") or ""), "dateIso": str(canonical.get("date_iso") or canonical.get("sort_date_iso") or ""),
    "datePrecision": str(canonical.get("date_precision") or "unknown"), "startOrdinal": start, "endOrdinal": end,
    "sourceDatePrecision": str(annotation.get("source_value") or actor_note.get("date_precision") or ""), "sourceDateNote": str(annotation.get("recommendation") or ""),
    "sourceActor": str(actor_note.get("actor") or ""), "sourceActorNote": str(actor_note.get("note") or ""),
    "location": str(canonical.get("location_raw") or row.get("location") or ""), "country": nation, "countryBasis": nation_basis,
    "craftType": str(canonical.get("craft_type_inferred") or "unknown"), "craftLabel": str(canonical.get("craft_type_label") or "Unknown / unresolved"),
    "beingTypes": strings(encounter.get("beingTypes")) if enc_join else [], "abductionStatus": str(encounter.get("abductionStatus") or "") if enc_join else "",
    "craftAssociation": str(encounter.get("craftAssociation") or "not_established") if enc_join else "not_indexed",
    "encounterJoinStatus": "validated_id_source_native_id" if enc_join else "no_indexed_encounter_facets",
    "disposition": str(row["disposition"]), "scope": str(row.get("scope") or "review_needed"),
    "sourceScope": str(row.get("source_scope") or ""), "sourceFamily": str(row.get("source_family") or ""),
    "provisionalGroup": str(row.get("provisional_group") or ""), "linkedRepresentationCount": int(row.get("linked_representation_count") or 1),
    "title": str(row.get("case_title") or row.get("location") or "Report"),
    "target": str(row.get("target") or ""), "action": str(row.get("action") or ""), "reviewReason": str(row.get("reason") or ""),
    "excerpt": str(row.get("dataset_excerpt") or "")[:4000], "excerptField": str(row.get("field") or ""),
    "canonicalPrimaryDiffers": bool(row.get("canonical_primary_differs")), "contextStatus": str(row.get("context_status") or ""),
    "reviewMethod": str(row.get("review_method") or ""), "reviewScope": str(row.get("review_scope") or ""),
    "curatedIds": strings(row.get("curated_ids")), "materials": material, "actions": action, "coding": coding,
    "sourceUrls": url_list(strings(row.get("source_urls")) + [row.get("source_url")]),
    "sourceReferences": [{"field": str(k), "text": str(v)[:1500]} for k, v in (row.get("native_reference_fields") or {}).items() if v],
    "discoveryPass": str(row.get("discovery_pass") or "original_review")})
 reports.sort(key=lambda x: x["eventId"])
 taxonomy = {"materials": [{"key": k, "label": v} for k, v in MATERIALS], "actions": [{"key": k, "label": v} for k, v in ACTIONS]}
 cases = [sanitize_case(x, seen) for x in case_rows]
 coverage = load(source / "coverage_manifest.json")
 payload = {"schemaId": SCHEMA, "schemaVersion": 1, "taxonomy": taxonomy, "reports": reports, "cases": cases,
  "policy": {"countUnit": "unique canonical catalog reports, never authenticated incidents", "casesExcludedFromReportMatrices": True,
   "defaultDispositions": ["direct_report"], "defaultScopes": ["occupant_soil_plant", "craft_collection"],
   "multiLabel": "A report can describe several materials, actions and being labels; column counts overlap.",
   "notIndexedIsNotAbsent": True, "keywordCandidatesPromoted": False, "canonicalDataMutated": False,
   "matchedMemberVariantsDefaultHeld": True, "memberVariantSensitivity": "A collection excerpt from a merged source member whose primary text differs is excluded from report matrices by default. Optional sensitivity inclusion joins primary-row date, geography and encounter facets; these may describe a different narrative version.",
   "coding": "Materials and actions are conservative lexical facets of affirmative reviewer-written target/act summaries; unknown remains unspecified. Discovery excerpts never create a material or act facet.",
   "inference": "Descriptive co-reporting only; source copying, repeated versions, source coverage and uncertainty prevent incident-rate or causal conclusions."},
  "coverage": {"originalCompletedUtc": coverage.get("completed_utc"), "catalogReportsScanned": coverage.get("counts", {}).get("counts", {}).get("current_rows_scanned"),
   "originalReviewedCandidateN": coverage.get("all_candidate_dispositions"), "methodLimits": coverage.get("method_limits")}}
 runtime_pins, metadata_receipt = finalize_runtime_metadata(payload, args)
 pins.extend(runtime_pins)
 decoded = compact(payload); packed = gzip.compress(decoded, compresslevel=9, mtime=0)
 if len(decoded) > MAX_BYTES: raise ValueError("Collection sidecar exceeds bounded 5 MiB decoded budget")
 # Assert public artifact never leaks local source paths.
 if re.search(rb"[A-Za-z]:[\\/]Users[\\/]", decoded): raise ValueError("Local source path in public evidence")
 artifact = {"file": "evidence.json.gz", "url": "./data/collections/evidence.json.gz", "gzipBytes": len(packed), "decodedBytes": len(decoded), "gzipSha256": digest(packed), "decodedSha256": digest(decoded), "reportCount": len(reports), "caseCount": len(cases)}
 manifest = {"schemaId": SCHEMA, "schemaVersion": 1, "artifact": artifact, "taxonomy": taxonomy, "inputPins": pins,
  "counts": {"reports": len(reports), "dossierEntries": len(cases), "dispositions": dict(Counter(x["disposition"] for x in reports)), "scopes": dict(Counter(x["scope"] for x in reports)), "encounterFacetJoins": sum(x["encounterJoinStatus"].startswith("validated") for x in reports)},
  "canonicalChunkPins": chunk_pins, "metadataOverlayReceipt": metadata_receipt, "builderPin": pin(Path(__file__), "reproducible sidecar builder"), "policy": payload["policy"]}
 output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
 (output / "evidence.json.gz").write_bytes(packed); (output / "manifest.json").write_bytes(compact(manifest))
 print(json.dumps({"output": str(output), "artifact": artifact, "counts": manifest["counts"]}, indent=2))
 return manifest

def main():
 parser = argparse.ArgumentParser(description=__doc__)
 parser.add_argument("--dossier-dir", required=True)
 parser.add_argument("--shared-root", default=r"C:/Users/jarod/Desktop/UFO Timeline map tool")
 parser.add_argument("--encounters", default="data/encounters/evidence.json.gz")
 parser.add_argument("--output", default="data/collections")
 parser.add_argument("--additions", action="append", default=[])
 parser.add_argument("--source-review")
 parser.add_argument("--facet-reviews",default="docs/qa/collection-analysis-20261018/collection_facet_overrides.json")
 parser.add_argument("--complementary-coverage",default="docs/qa/collection-analysis-20261018/collection_recall_audit_summary.json")
 parser.add_argument("--node",default=r"C:/Program Files/nodejs/node.exe")
 parser.add_argument("--refresh-runtime-metadata",action="store_true")
 args=parser.parse_args()
 refresh_runtime_metadata(args) if args.refresh_runtime_metadata else build(args)

if __name__ == "__main__": main()
