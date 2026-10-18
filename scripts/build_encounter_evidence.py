"""Build source-pinned, sparse reported encounter facets across the UFO corpus.

This classifies preserved reports, never verifies an abduction or a biological
species. Original records, coordinates and craft classifications are untouched.
Source fields and guarded own-episode narratives are separate evidence methods.
Missing rows mean not indexed, never a negative observation. A source-coded
being without a reported craft is deliberately excluded from craft associations.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import time

SHARED = Path(r"C:/Users/jarod/Desktop/UFO Timeline map tool")
DEFAULT_OUTPUT = SHARED / "data/research/encounters-20261013/validated"
SCHEMA_ID = "ufo-encounter-evidence-v1"
RELEASE_ID = "encounters-20261013-v1"
MAX_SAFE_ID = 9_007_199_254_740_991
EXPECTED_CATALOG_COUNT = 702_893
MAX_OUTPUT_BYTES = 20 * 1024 * 1024
SOURCES = {"ufocat", "majestic", "nuforc", "mufon", "phenomenainon_updb"}
PRIMARY_CODEBOOK = "https://cufos.org/PDFs/UFOCAT%20Codebook%202023.pdf"

TAXONOMY = [
    {"key": "grey", "label": "Grey / gray", "group": "Named source labels"},
    {"key": "nordic", "label": "Nordic", "group": "Named source labels"},
    {"key": "reptilian", "label": "Reptilian", "group": "Named source labels"},
    {"key": "mantis_like", "label": "Mantis-like", "group": "Named source labels"},
    {"key": "insectoid", "label": "Insectoid", "group": "Named source labels"},
    {"key": "human_like", "label": "Human-like", "group": "Reported appearance"},
    {"key": "humanoid", "label": "Humanoid", "group": "Reported appearance"},
    {"key": "small_humanoid", "label": "Small / short humanoid", "group": "Reported appearance"},
    {"key": "tall_humanoid", "label": "Tall humanoid", "group": "Reported appearance"},
    {"key": "giant", "label": "Giant", "group": "Reported appearance"},
    {"key": "hairy", "label": "Hairy / Bigfoot-like", "group": "Reported appearance"},
    {"key": "robotic", "label": "Robotic", "group": "Reported appearance"},
    {"key": "luminous", "label": "Luminous", "group": "Reported appearance"},
    {"key": "animal_like", "label": "Animal-like / winged", "group": "Reported appearance"},
    {"key": "men_in_black", "label": "Men in Black", "group": "Other reported categories"},
    {"key": "apparition", "label": "Apparition / ghost-like", "group": "Other reported categories"},
    {"key": "mixed", "label": "Mixed beings", "group": "Other reported categories"},
    {"key": "other_described", "label": "Other described being", "group": "Other reported categories"},
    {"key": "unspecified", "label": "Type unspecified", "group": "Other reported categories"},
]
KEY_ORDER = {row["key"]: i for i, row in enumerate(TAXONOMY)}
EMPTY = {"", "unknown", "unk", "n/a", "na", "none", "null", "-", "?", "0"}
ABDUCTION = re.compile(r"\b(?:abduct(?:ion|ed|ee|ees)|kidnapp(?:ed|ing))\b", re.I)
NEGATION = re.compile(r"\b(?:no|not|never|without|den(?:y|ied|ies)|didn['’]?t|wasn['’]?t|weren['’]?t)\b", re.I)
SPECULATION = re.compile(r"\b(?:possible|possibly|potential|probably|probable|maybe|perhaps|suspect(?:ed|s)?|might|could|may have|wonder(?:ed|ing)?|believ(?:e|ed)|think|thought|seemed|felt like|apparently|allegedly)\b|\?", re.I)
DREAM_CONTEXT = re.compile(r"\b(?:dream|dreamt|dreamed|dreaming|sleep paralysis)\b", re.I)
OTHER_EPISODE = re.compile(r"\b(?:previous(?:ly)?|years? (?:ago|earlier|before)|months? (?:ago|earlier|before)|another (?:case|incident|encounter|abduction)|other (?:cases?|incidents?|abductions?)|earlier (?:case|incident|encounter)|prior (?:case|incident|encounter)|used to|history of|childhood|recurring|every night|repeated(?:ly)?|for years|since (?:the )?age(?:\s*\d+)?|since I was|ever since|throughout my life|all my life|for \d+ years|multiple times|on several occasions|many times)\b", re.I)
UNOBSERVED_FRAME = re.compile(r"\b(?:want(?:ed|ing|s)?\s+to\s+(?:see|meet|observe|find|encounter)|hop(?:e|ed|es|ing)\s+to\s+(?:see|meet|observe|find|encounter)|wish(?:ed|es|ing)?\s+to\s+(?:see|meet|observe|find|encounter)|theor(?:y|ies|ize|ized|izing)|assum(?:e|ed|es|ing)|guess(?:ed|ing)?|convinced|gonna|going to abduct|will abduct|would abduct|might abduct|may abduct)\b", re.I)
REFERENCE_FRAME = re.compile(r"\b(?:remind(?:ed|s)?\s+(?:me|us|him|her|them)\s+of|similar\s+to|compared\s+(?:with|to)|comparison\s+(?:with|to)|unlike|like\s+the\s+(?:case|incident|abduction)|as\s+in\s+the\s+(?:case|incident|abduction)|(?:I|we)\s+(?:remembered|recalled|thought\s+of))\b", re.I)
PUBLICATION = re.compile(r"\b(?:book|books|movie|movies|film|films|documentary|television|tv show|lecture|conference|fiction|fictional|novel|novels|article about|articles about|read about|reading about|stories about|story about|discuss(?:ed|ing)|describ(?:es|ing) other|research (?:into|on)|abduction research|abduction researchers?)\b", re.I)
CONTEXT = re.compile(r"\b(?:ufos?|uaps?|aliens?|extraterrestrial|space\s*ship|spacecraft|flying saucer|flying disc|flying disk|humanoids?|ufonauts)\b", re.I)
OBJECT = re.compile(r"\b(?:ufos?|uaps?|space\s*ship|spacecraft|craft|flying saucer|flying disc|flying disk|disc|disk|saucer|object)\b", re.I)
ALIEN_NOUN = r"aliens?(?!['’]s\b)(?![- ](?:looking|like|shaped|style)\b)(?!\s+(?:(?:triangular|grey|gray|silver|metallic|flying|strange|shiny|large|huge|small|oval|insect|robotic|unmanned)\s+){0,3}(?:ufos?|ufo['’]s|uaps?|crafts?|ships?|spacecrafts?|spaceships?|saucers?|discs?|disks?|objects?|aircrafts?|drones?|technolog(?:y|ies)|lights?|sightings?)\b)"
ENTITY_NOUN = rf"(?:beings?|entities|entity|{ALIEN_NOUN}|humanoids?|occupants?|ufonauts?|creatures?|figures?)"
BEING_ADJECTIVE = r"(?:small|short|tall|thin|large|grey|gray|reptilian|mantis-like|insectoid|human-like|robotic|luminous|hairy|strange|unknown|odd|mysterious|slender|naked|white|black|green|red|brown|blue|silver|glowing|pallid)"
ENTITY = re.compile(rf"\b(?:beings|entities|{ALIEN_NOUN}|humanoids?|occupants?|ufonauts)\b|\b(?:a|an|one|the|\d+)\s+(?:{BEING_ADJECTIVE}\s+){{0,4}}being\b", re.I)
NARRATIVE_SIGNAL = re.compile(r"\b(?:abduct(?:ion|ed|ee|ees)|kidnapp(?:ed|ing)|humanoids?|aliens?|ufonauts?|entities|entity|beings?|occupants?|bigfoot|sasquatch|yeti|MIB|apparition|men in black|creatures?|figures?)\b", re.I)
OBSERVED = re.compile(r"\b(?:saw|seen|see|sees|observed|witnessed|encountered|appeared|emerged|exited|entered|stood|standing|approached|came|met|taken|abducted|carried|reported)\b", re.I)
DIRECT_ABDUCTION = re.compile(r"\b(?:(?:was|were|been|is|am|are|got)\s+(?:\w+\s+){0,2}abducted|abducted\s+(?:me|us|him|her|them)|(?:I|we)\s+experienced\s+(?:an?\s+)?abduction)\b", re.I)
LEADING_ABDUCTION = re.compile(r"^\s*(?:Type\s+[A-Z]\.\s*)?(?:alien\s+|mass\s+)?abduction\b", re.I)
NO_CRAFT = re.compile(r"\b(?:no\s+(?:ufos?|craft|objects?|spacecraft)|(?:without|no sighting of)\s+(?:an?\s+)?(?:ufos?|craft|objects?|spacecraft)|(?:ufos?|craft|objects?|spacecraft)\s+(?:was|were)?\s*not\s+(?:seen|observed|reported))\b", re.I)
NOUN_QUALIFIERS = r"(?:[- ](?:like|looking|type|shaped|skinned))?(?:\s+(?:small|short|tall|thin|large|hairy|luminous|pallid|skinned|looking|shaped)){0,3}\s+"
TYPE_PATTERNS = [
    ("grey", rf"\b(?:grey|gray){NOUN_QUALIFIERS}{ENTITY_NOUN}\b"),
    ("nordic", rf"\b(?:nordic|blond|blonde){NOUN_QUALIFIERS}{ENTITY_NOUN}\b"),
    ("reptilian", rf"\b(?:reptilian|reptile|lizard){NOUN_QUALIFIERS}{ENTITY_NOUN}\b"),
    ("mantis_like", rf"\b(?:praying[- ]mantis|mantis){NOUN_QUALIFIERS}{ENTITY_NOUN}\b"),
    ("insectoid", rf"\b(?:insectoid|insect){NOUN_QUALIFIERS}{ENTITY_NOUN}\b"),
    ("human_like", rf"\bhuman[- ](?:like|looking)\s+{ENTITY_NOUN}\b"),
    ("humanoid", r"\bhumanoids?\b"),
    ("small_humanoid", r"\b(?:small|short|tiny|little|dwarf)[- ]+(?:beings?|entities|entity|aliens?|humanoids?|occupants?|ufonauts)\b"),
    ("tall_humanoid", r"\b(?:very\s+)?tall(?:\s+thin)?\s+(?:beings?|entities|entity|aliens?|humanoids?|occupants?|ufonauts)\b"),
    ("giant", rf"\bgiant{NOUN_QUALIFIERS}{ENTITY_NOUN}\b"),
    ("hairy", rf"\bhairy{NOUN_QUALIFIERS}{ENTITY_NOUN}\b|\b(?:bigfoot|sasquatch|yeti)\b"),
    ("robotic", rf"\b(?:robot|robotic){NOUN_QUALIFIERS}{ENTITY_NOUN}\b"),
    ("luminous", rf"\b(?:luminous|glowing){NOUN_QUALIFIERS}{ENTITY_NOUN}\b"),
    ("animal_like", rf"\b(?:animal|dog|wolf|bird|canine)[- ]like\s+{ENTITY_NOUN}\b|\bwinged\s+{ENTITY_NOUN}\b"),
    ("men_in_black", r"\b(?:men in black|MIB)\b"),
    ("apparition", rf"\b(?:ghostly|ghost[- ]like|spectral)\s+{ENTITY_NOUN}\b|\bapparition\b"),
    ("mixed", r"\b(?:mixed|different|multiple)\s+(?:types|kinds)\s+of\s+(?:beings|entities|aliens|humanoids)\b"),
]
TYPE_PATTERNS = [(key, re.compile(pattern, re.I)) for key, pattern in TYPE_PATTERNS]
ASSOCIATION = re.compile(
    rf"\b{ENTITY_NOUN}\b.{{0,70}}\b(?:emerged|exited|entered|boarded|came out of|stepped out of|aboard|inside|beneath|beside|next to|near)\b.{{0,45}}\b(?:ufos?|uaps?|craft|spacecraft|spaceship|saucer|disc|disk|object)\b|"
    rf"\b(?:ufos?|uaps?|craft|spacecraft|spaceship|saucer|disc|disk|object)\b.{{0,70}}\b(?:with|contained|carrying|inside|beneath|beside|near|from)\b.{{0,45}}\b{ENTITY_NOUN}\b|"
    rf"\b(?:emerged|exited|entered)\b.{{0,35}}\b(?:ufos?|uaps?|craft|spacecraft|spaceship|saucer|disc|disk)\b", re.I
)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def compact(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def field_text(value) -> str:
    return str(value).strip() if value is not None else ""


def source_fields(event):
    value = event.get("raw_source_row")
    if not isinstance(value, dict) or not value:
        value = event.get("raw_fields")
    return value if isinstance(value, dict) else {}


def source_being_types(value: str) -> list[str]:
    """Group actual source labels, retaining their original value in evidence.

    Stature groups derive only from explicit descriptive labels, never height.
    Unrecognized labels remain 'other_described'; abbreviations are not decoded.
    """
    label = re.sub(r"[\s_-]+", " ", value.strip().lower())
    if label in EMPTY:
        return []
    exact = {
        "human": ["human_like"], "human like": ["human_like"],
        "humanoid": ["humanoid"], "flying humanoid": ["humanoid"],
        "grey": ["grey"], "gray": ["grey"], "greys": ["grey"], "grays": ["grey"],
        "nordic": ["nordic"], "nordic asiatic": ["nordic"],
        "reptilian": ["reptilian"], "reptile": ["reptilian"],
        "mantis": ["mantis_like"], "insectoid": ["insectoid"],
        "mib": ["men_in_black"], "men in black": ["men_in_black"],
        "mixed": ["mixed"], "apparition": ["apparition"], "ghost": ["apparition"],
        "creature": ["unspecified"], "entity": ["unspecified"], "alien": ["unspecified"],
        "being": ["unspecified"], "occupant": ["unspecified"],
    }
    if label in exact:
        return exact[label]
    keys = set()
    if re.search(r"\b(?:grey|gray)\b", label): keys.add("grey")
    if re.search(r"\b(?:dwarf|short|tiny|small|goblin)\b", label): keys.add("small_humanoid")
    if re.search(r"\btall\b", label): keys.add("tall_humanoid")
    if re.search(r"\bgiant\b", label): keys.add("giant")
    if re.search(r"\b(?:hairy|bigfoot|sasquatch|yeti|pongid)\b", label): keys.add("hairy")
    if re.search(r"\b(?:robot|robotic)\b", label): keys.add("robotic")
    if re.search(r"\b(?:luminous|glowing)\b", label): keys.add("luminous")
    if label in {"winged", "mothman", "werewolf", "bird", "mermaid", "chupacabra", "bipedal canine", "hairy beast", "amphibian"}: keys.add("animal_like")
    return sorted(keys or {"other_described"}, key=KEY_ORDER.get)


def sentences(text: str):
    return [(m.group().strip(), m.start()) for m in re.finditer(r"[^.!?\r\n]+[.!?]?", text) if m.group().strip()]


def excerpt(text: str, start=0, width=220) -> str:
    offset = max(0, start - 65)
    result = text[offset:offset + width].strip()
    return result or text.strip()[:width]


def narratives(event, raw):
    source = event.get("source")
    fields = {
        "ufocat": ["NOTES"], "majestic": ["desc", "key_vals/HatchDesc"],
        "mufon": ["Short Description", "Long Description"],
        "nuforc": ["Description"], "phenomenainon_updb": ["description"],
    }.get(source, [])
    result = [(key, field_text(raw.get(key))) for key in fields if field_text(raw.get(key))]
    if not result and field_text(event.get("description")):
        result.append(("description", field_text(event["description"])))
    return result


def metric_height_conflicts(number: float, text: str) -> list[dict]:
    """Find a narrow same-number metric stature conflict, never convert it.

    The codebook declares Height in feet, but some rows repeat a narrative's
    metric number verbatim. A stature phrase must concern an entity: UFO sizes,
    altitudes, distances, and witnesses' heights are not entity measurements.
    Multiple subjects remain an attribution problem, not permission to choose
    a being or infer a species from its reported stature.
    """
    if not math.isfinite(number) or number <= 0 or not text:
        return []
    entity = re.compile(r"\b(?:beings?|entities|entity|humanoids?|occupants?|ufonauts?|creatures?|figures?|silhouettes?|aliens?|greys|grays)\b", re.I)
    other_subject = re.compile(r"\b(?:ufos?|uaps?|craft|spacecraft|spaceship|objects?|saucers?|discs?|disks?|trees?|towers?|houses?|buildings?|walls?|fences?|witness(?:es)?|observers?|man|woman|men|women|boys?|girls?|grandsons?|granddaughters?|he|she|they|it)\b", re.I)
    metric = re.compile(r"(?<![\w.])(?P<value>\d+(?:\.\d+)?)\s*-?\s*(?P<unit>met(?:er|re)s?|m)\s*-?\s*(?:tall|in\s+height)\b", re.I)
    modifiers = r"(?:(?:small|short|tall|thin|large|huge|grey|gray|hairy|winged|strange|unknown|ape-like|simian|human-like|robotic|luminous|glowing|slender|naked|white|black|green|red|brown|blue|silver)\s+){0,4}"
    following_entity = re.compile(r"^\s*" + modifiers + r"(?:beings?|entities|entity|humanoids?|occupants?|ufonauts?|creatures?|figures?|silhouettes?|aliens?)\b", re.I)
    following_other = re.compile(r"^\s*" + modifiers + other_subject.pattern, re.I)
    # Unlike sentences(), this does not split decimal measurements at the dot.
    stops = list(re.finditer(r"(?<!\d)[.!?]|[.!?](?!\d)|[\r\n]+", text))

    def entity_subject(match):
        prior_stops = [stop for stop in stops if stop.end() <= match.start()]
        start = prior_stops[-1].end() if prior_stops else 0
        after_stop = next((stop.start() for stop in stops if stop.start() >= match.end()), len(text))
        following = text[match.end():after_stop]
        if following_entity.match(following):
            return True
        if following_other.match(following):
            return False
        before = text[start:match.start()]
        # A standalone stature sentence may qualify the preceding entity.
        if not before.strip(" ,:;()") and prior_stops:
            previous_start = prior_stops[-2].end() if len(prior_stops) > 1 else 0
            before = text[previous_start:prior_stops[-1].start()]
        before = before[-120:]
        subjects = [(m.start(), True) for m in entity.finditer(before)]
        subjects += [(m.start(), False) for m in other_subject.finditer(before)]
        return bool(subjects and max(subjects)[1])

    candidates = [match for match in metric.finditer(text) if entity_subject(match)]
    if not candidates:
        return []
    all_stature = re.compile(r"(?<![\w.])\d+(?:\.\d+)?\s*-?\s*(?:met(?:er|re)s?|m|feet|foot|ft|inches?|in|['\u2032])\s*-?\s*(?:tall|in\s+height)\b", re.I)
    stature_subjects = [match for match in all_stature.finditer(text) if entity_subject(match)]
    plural = re.search(r"\b(?:[2-9]\d*|[1-9]\d+|two|three|four|five|six|several|other|another)\s+(?:(?:grey|gray|small|short|tall|hairy|winged)\s+){0,3}(?:beings?|entities|entity|humanoids?|creatures?|figures?|aliens?|greys|grays)\b", text, re.I)
    ambiguous = bool(plural or len(stature_subjects) > 1)
    return [{"start": match.start(), "end": match.end(), "value": float(match["value"]),
             "unit": "m", "subjectAmbiguous": ambiguous}
            for match in candidates
            if math.isclose(number, float(match["value"]), rel_tol=1e-6, abs_tol=1e-6)]


def classify(event):
    source = event.get("source")
    if source not in SOURCES:
        raise ValueError(f"Undocumented source {source!r}")
    raw = source_fields(event)
    fields = {str(k).upper(): field_text(v) for k, v in raw.items()}
    evidence = []
    keys = set()
    review = set()
    status = ""
    entity_coded = False
    coded_association = False
    source_no_craft = False
    objs_positive = False
    association_explicit = False
    object_seen = False
    narrative_no_craft = False

    def add(field, value, rule):
        item = {"field": field, "excerpt": value[:220], "ruleId": rule}
        if item not in evidence and value.strip(): evidence.append(item)

    if source == "ufocat":
        hynek = fields.get("HYNEK", "").upper()
        vallee = fields.get("VALLEE", "").upper()
        type_code = fields.get("TYPE", "").upper()
        label = fields.get("UFONAUT", "")
        keys.update(source_being_types(label))
        if keys:
            entity_coded = True
            add("Ufonaut", label, "ufocat_reported_ufonaut_label_v1")
        if hynek == "CE4":
            status = "source_reported"
            add("HYNEK", fields["HYNEK"], "ufocat_hynek_ce4_abduction_class_v1")
        elif re.match(r"^9[A-Z0-9_.^]*[AB]", type_code):
            status = "ambiguous"
            add("TYPE", fields["TYPE"], "ufocat_abduction_disappearance_teleportation_class_v1")
            review.add("source_class_also_covers_disappearance_or_teleportation")
        if hynek == "CE3":
            entity_coded = True
            add("HYNEK", fields["HYNEK"], "ufocat_hynek_ce3_entity_class_v1")
        if vallee in {"CE3", "FB3", "MA3", "AN3"}:
            entity_coded = True
            add("VALLEE", fields["VALLEE"], "ufocat_vallee_entity_class_v1")
            coded_association = vallee in {"CE3", "FB3", "MA3"}
        if re.match(r"^[78]", type_code) and not type_code.startswith("8K"):
            entity_coded = True
            add("TYPE", fields["TYPE"], "ufocat_occupant_or_contact_class_v1")
        if type_code.startswith(("5O", "6O")):
            entity_coded = coded_association = True
            add("TYPE", fields["TYPE"], "ufocat_inside_occupant_class_v1")
        if type_code.startswith("8K"):
            keys.add("men_in_black")
            entity_coded = True
            add("TYPE", fields["TYPE"], "ufocat_men_in_black_class_v1")
        if type_code.startswith("0H"):
            entity_coded = source_no_craft = True
            if not keys: keys.add("human_like")
            add("TYPE", fields["TYPE"], "ufocat_humanoid_without_ufo_class_v1")
        if vallee == "AN3": source_no_craft = True
        objs = fields.get("OBJS", "")
        if re.fullmatch(r"\d+(?:\.0+)?", objs):
            number = float(objs)
            source_no_craft = source_no_craft or number == 0
            objs_positive = number > 0
        if keys or entity_coded:
            if objs and (source_no_craft or objs_positive): add("OBJS", objs, "ufocat_object_count_association_guard_v1")
        # Dedicated source appearance fields can establish an unspecified being
        # report, but never supply a named type from the numeric height alone.
        try: direct_height = float(fields.get("HEIGHT", ""))
        except (ValueError, TypeError): direct_height = math.nan
        direct_uniform = fields.get("UNIFORM", "")
        if math.isfinite(direct_height) and direct_height > 0 or direct_uniform.lower() not in EMPTY:
            entity_coded = True
            if objs and (source_no_craft or objs_positive): add("OBJS", objs, "ufocat_object_count_association_guard_v1")
    else:
        for field in (key for key in raw if str(key).startswith("type/") or key in {"type", "Type"}):
            value = field_text(raw[field])
            normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
            if normalized in {"abduction", "alien abduction", "mass abduction", "abduction report"}:
                status = "source_reported"
                add(str(field), value, "source_explicit_abduction_type_v1")
            if normalized in {"alien encounter", "entity encounter", "occupant encounter", "humanoid encounter"}:
                entity_coded = True
                add(str(field), value, "source_explicit_entity_type_v1")
        attribute_fields = [key for key in raw if str(key).startswith("attributes/") or key == "Characteristics"]
        for field in attribute_fields:
            value = field_text(raw[field])
            if re.search(r"\bpossible abduction\b", value, re.I) and not re.search(r"\bno possible abduction\b", value, re.I):
                if not status: status = "ambiguous"
                add(str(field), value, "source_possible_abduction_attribute_v1")
                review.add("possible_abduction_not_established")

    narrative_fields = narratives(event, raw)
    record_narrative = " ".join(text for _, text in narrative_fields)
    record_hold = bool(PUBLICATION.search(record_narrative) or OTHER_EPISODE.search(record_narrative) or REFERENCE_FRAME.search(record_narrative) or UNOBSERVED_FRAME.search(record_narrative))
    if record_hold and NARRATIVE_SIGNAL.search(record_narrative):
        review.add("narrative_episode_or_observation_attribution_held")
    for field, text in ([] if record_hold else narrative_fields):
        if not NARRATIVE_SIGNAL.search(text): continue
        pieces = sentences(text)
        for position, (sentence, start) in enumerate(pieces):
            has_abduction = bool(ABDUCTION.search(sentence))
            type_matches = [(key, pattern.search(sentence)) for key, pattern in TYPE_PATTERNS]
            type_matches = [(key, match) for key, match in type_matches if match]
            type_matches = [(key, match) for key, match in type_matches if not (
                key == "tall_humanoid" and (
                    re.search(r"\d+(?:\.\d+)?\s*(?:['’\"]|ft|feet|foot|m|meters?|metres?)\s*$", sentence[:match.start()], re.I)
                    or re.search(r"\d+\s*$", sentence[:match.start()]) and re.search(r"\b(?:humanoid|being|alien|entity|occupant|ufonaut)$", match.group(), re.I)
                )
            )]
            has_entity = bool(ENTITY.search(sentence)) or bool(type_matches)
            if not has_abduction and not has_entity: continue
            local_context = " ".join(p[0] for p in pieces[max(0, position - 1):position + 2])
            # The incident frame can be declared in the preceding sentence.
            # Do not borrow its UFO context while ignoring its book/prior-case
            # attribution (e.g. 'I read a book. Its victim was abducted...').
            publication = bool(PUBLICATION.search(local_context))
            other_episode = bool(OTHER_EPISODE.search(local_context) or REFERENCE_FRAME.search(local_context))
            if publication or other_episode:
                review.add("narrative_other_episode_or_publication_held")
                continue
            negated = bool(NEGATION.search(sentence))
            dream_context = bool(DREAM_CONTEXT.search(local_context))
            speculative = bool(SPECULATION.search(sentence)) or dream_context
            if dream_context: review.add("hypnosis_dream_or_sleep_context")
            typed_context = any(key in {"grey", "nordic", "reptilian", "mantis_like", "insectoid", "robotic", "apparition", "hairy"} for key, _ in type_matches)
            context = bool(CONTEXT.search(local_context)) or typed_context or entity_coded or status == "source_reported"
            if has_abduction:
                if negated:
                    if status == "source_reported": review.add("source_classification_narrative_negation_requires_review")
                elif context and (DIRECT_ABDUCTION.search(sentence) or LEADING_ABDUCTION.search(sentence)):
                    if speculative:
                        if not status: status = "ambiguous"
                        add(field, excerpt(text, start + ABDUCTION.search(sentence).start()), "narrative_possible_abduction_v1")
                        review.add("possible_abduction_not_established")
                    else:
                        if status != "source_reported": status = "narrative_reported"
                        add(field, excerpt(text, start + ABDUCTION.search(sentence).start()), "narrative_own_report_abduction_v1")
            # 'No UFO was seen' negates craft presence, not the described being.
            entity_negated = bool(NEGATION.search(NO_CRAFT.sub("", sentence)))
            if not has_entity or entity_negated or speculative: continue
            if not context or not (OBSERVED.search(sentence) or entity_coded or status in {"source_reported", "narrative_reported"}): continue
            for key, match in type_matches:
                # A named animal, a conventional robot or an MIB acronym alone
                # is not a UFO-associated entity report without local context.
                keys.add(key)
                add(field, excerpt(text, start + match.start()), "narrative_reported_being_appearance_v1")
            if not type_matches:
                keys.add("unspecified")
                match = ENTITY.search(sentence)
                add(field, excerpt(text, start + match.start()), "narrative_reported_being_unspecified_v1")
            if ASSOCIATION.search(sentence):
                association_explicit = True
                add(field, excerpt(text, start + ASSOCIATION.search(sentence).start()), "narrative_explicit_being_craft_relation_v1")
            if OBJECT.search(local_context): object_seen = True
            if NO_CRAFT.search(local_context): narrative_no_craft = True
            if re.search(r"\b(?:hypno(?:sis|tic|tized)|hypnotic regression|dream|dreamt|dreamed|sleep paralysis)\b", local_context, re.I):
                review.add("hypnosis_dream_or_sleep_context")

    if entity_coded and not keys: keys.add("unspecified")
    if not keys and not status: return None
    if "unspecified" in keys and len(keys) > 1: keys.remove("unspecified")
    association = "not_established"
    if keys:
        if source_no_craft or narrative_no_craft:
            association = "none_reported"
            if coded_association or association_explicit: review.add("source_craft_presence_conflict")
        elif coded_association or association_explicit:
            association = "explicit"
        elif objs_positive or object_seen:
            association = "co_reported"
    result = {
        "source": source, "sourceEventId": field_text(event.get("source_id")),
        "abductionStatus": status, "beingTypes": sorted(keys, key=KEY_ORDER.get),
        "craftAssociation": association, "evidence": evidence,
    }
    if source == "ufocat" and keys:
        height = fields.get("HEIGHT", "")
        try: number = float(height)
        except (ValueError, TypeError): number = math.nan
        if math.isfinite(number) and number > 0:
            conflicts = [(field, text, match) for field, text in narrative_fields
                         for match in metric_height_conflicts(number, text)]
            if conflicts:
                review.add("ufocat_height_unit_conflict")
                add("Height", height, "ufocat_reported_height_unit_conflict_v1")
                for field, text, match in conflicts:
                    add(field, excerpt(text, match["start"]), "ufocat_narrative_metric_height_conflict_v1")
                    if match["subjectAmbiguous"]:
                        review.add("ufocat_height_subject_ambiguous")
            else:
                result["heightFeet"] = number
                add("Height", height, "ufocat_reported_height_feet_v1")
        uniform = fields.get("UNIFORM", "")
        if uniform:
            result["uniform"] = uniform
            add("Uniform", uniform, "ufocat_reported_uniform_v1")
    if review: result["reviewFlags"] = sorted(review)
    if not evidence: raise ValueError("Indexed encounter has no evidence")
    return result


def build(shared_root: Path, output: Path, expected_count=EXPECTED_CATALOG_COUNT):
    started = time.monotonic()
    builder = Path(__file__).resolve()
    builder_bytes = builder.read_bytes()
    builder_pin = {"path": str(builder), "bytes": len(builder_bytes), "sha256": digest(builder_bytes)}
    chunk_root = shared_root / "data/canonical_web/event_chunks"
    counts = Counter()
    source_counts = Counter()
    indexed_sources = Counter()
    statuses = Counter()
    statuses_by_source = defaultdict(Counter)
    being_counts = Counter()
    beings_by_source = defaultdict(Counter)
    associations = Counter()
    review_counts = Counter()
    labels = Counter()
    rules = Counter()
    samples = defaultdict(list)
    rows = []
    seen_ids = set()
    input_pins = []
    for path in sorted(chunk_root.glob("chunk_*.json")):
        raw_bytes = path.read_bytes()
        chunk_hash = digest(raw_bytes)
        events = json.loads(raw_bytes)
        if not isinstance(events, list): raise ValueError("Canonical chunk must be an array")
        input_pins.append({"chunk": path.stem, "bytes": len(raw_bytes), "sha256": chunk_hash, "rowCount": len(events)})
        for detail_index, event in enumerate(events):
            event_id = event.get("event_id")
            if type(event_id) is not int or not 0 < event_id <= MAX_SAFE_ID or event_id in seen_ids:
                raise ValueError("Canonical event ID is unsafe, repeated or missing")
            seen_ids.add(event_id)
            counts["catalogCount"] += 1
            source_counts[event.get("source")] += 1
            row = classify(event)
            if row is None: continue
            row["eventId"] = str(event_id)
            row["sourceRef"] = {"chunk": path.stem, "detailIndex": detail_index, "chunkSha256": chunk_hash}
            rows.append(row)
            indexed_sources[row["source"]] += 1
            if row["abductionStatus"]:
                statuses[row["abductionStatus"]] += 1
                statuses_by_source[row["source"]][row["abductionStatus"]] += 1
            if row["beingTypes"]:
                counts["beingReportCount"] += 1
                associations[row["craftAssociation"]] += 1
                being_counts.update(row["beingTypes"])
                beings_by_source[row["source"]].update(row["beingTypes"])
            review_counts.update(row.get("reviewFlags", []))
            rules.update(item["ruleId"] for item in row["evidence"])
            if row["source"] == "ufocat":
                value = field_text(source_fields(event).get("Ufonaut"))
                if value: labels[value] += 1
            group = row["abductionStatus"] or row["craftAssociation"]
            if len(samples[group]) < 8: samples[group].append(row)
        print(f"Read {path.stem}: {counts['catalogCount']:,} reports, {len(rows):,} encounter rows", flush=True) if len(input_pins) % 50 == 0 else None
    if counts["catalogCount"] != expected_count:
        raise ValueError(f"Catalog count drift: {counts['catalogCount']} != {expected_count}")
    rows.sort(key=lambda row: int(row["eventId"]))
    payload = {"schemaId": SCHEMA_ID, "releaseId": RELEASE_ID, "catalogCount": counts["catalogCount"], "taxonomy": TAXONOMY, "rows": rows}
    decoded = compact(payload)
    packed = gzip.compress(decoded, compresslevel=9, mtime=0)
    artifact = {"file": "evidence.json.gz", "url": "./data/encounters/evidence.json.gz", "rowCount": len(rows), "gzipBytes": len(packed), "decodedBytes": len(decoded), "gzipSha256": digest(packed), "decodedSha256": digest(decoded), "sha256": digest(decoded)}
    policy = {
        "catalogRecordsMutated": False, "coordinatesMutated": False, "craftClassificationsMutated": False,
        "claimsVerified": False, "absenceMeans": "not_indexed_not_negative", "beingLabelsAre": "source_reported_appearance_or_named_labels_not_biological_species",
        "associationMeans": "same_record_reported_relation_not_verified_common_origin", "heightUnit": "feet_from_ufocat_source_only",
        "codedAbductionRule": "UFOCAT HYNEK CE4 or explicit source abduction type; Vallee CE4 is not equivalent",
        "ambiguousClasses": "UFOCAT TYPE9A/9B cover disappearance/teleportation too; possible-abduction attributes stay ambiguous",
        "narrativeRules": "Own-episode affirmative narrow templates; negation/speculation held. Whole-record publication/comparison/prior/recurring/desire/theory frames withhold all narrative additions; source-coded classifications and direct Ufonaut/Height/Uniform fields remain independent. Alien craft/UFO/plural vessel adjectives are not being nouns. Numeric height followed by tall is not a Tall type.",
        "sourceCodebook": {"url": PRIMARY_CODEBOOK, "printedPages": [10, 28, 29, 31, 32, 33, 34, 35]},
        "taxonomyGrouping": "Stature descriptors come only from direct Ufonaut labels or own narrative words, never numeric height. Unrecognized source labels remain other_described.",
    }
    totals = {"catalogCount": counts["catalogCount"], "rowCount": len(rows), "beingReportCount": counts["beingReportCount"], "abductionStatusCounts": dict(statuses), "abductionStatusBySource": {key: dict(value) for key, value in statuses_by_source.items()}, "beingTypeCounts": dict(being_counts), "beingTypesBySource": {key: dict(value) for key, value in beings_by_source.items()}, "craftAssociationCounts": dict(associations), "sourceCounts": dict(source_counts), "indexedSourceCounts": dict(indexed_sources)}
    generated = datetime.now(timezone.utc).isoformat()
    manifest = {"schemaId": SCHEMA_ID, "releaseId": RELEASE_ID, "generatedAtUtc": generated, "catalogCount": counts["catalogCount"], "rowCount": len(rows), "taxonomy": TAXONOMY, "artifact": artifact, "counts": totals, "policy": policy}
    if digest(builder.read_bytes()) != builder_pin["sha256"]:
        raise ValueError("Extractor changed during corpus scan; no evidence release written")
    audit = {"schemaId": SCHEMA_ID, "releaseId": RELEASE_ID, "generatedAtUtc": generated, "elapsedSeconds": round(time.monotonic() - started, 3), "builderPin": builder_pin, "inputRoot": str(chunk_root.resolve()), "inputChunkCount": len(input_pins), "inputPins": input_pins, "counts": totals, "sourceUfonautValues": dict(labels.most_common()), "evidenceRuleCounts": dict(rules), "reviewFlagCounts": dict(review_counts), "policy": policy, "rebuild": f"py -3 scripts/build_encounter_evidence.py --shared-root \"{shared_root}\" --output \"{output}\"", "retention": "Current sparse encounter research evidence; preserve pinned original chunks, source audit and fixtures. No full corpus, staging tree, deployment or rollback copy created."}
    outputs = {"evidence.json.gz": packed, "manifest.json": compact(manifest), "audit.json": compact(audit), "review_fixtures.json": compact(dict(samples))}
    total_bytes = sum(len(value) for value in outputs.values())
    if total_bytes > MAX_OUTPUT_BYTES: raise ValueError(f"Output budget exceeded: {total_bytes} bytes")
    output.mkdir(parents=True, exist_ok=True)
    if any((output / name).exists() for name in outputs): raise ValueError("Refusing to overwrite an existing evidence release")
    for name, value in outputs.items(): (output / name).write_bytes(value)
    print(json.dumps({"output": str(output), "bytesWritten": total_bytes, "artifact": artifact, "counts": totals}, sort_keys=True), flush=True)
    return manifest


def apply_reviewed_holds(base: Path, shared_root: Path, output: Path):
    """Withdraw only two source-verified narrative-only classification rows.

    This replays a reviewed whole-record hold against the compact sidecar. It
    never edits a canonical report or removes coded evidence. The base artifact,
    its executed extractor, and all original source bytes remain protected.
    """
    started = time.monotonic()
    builder = Path(__file__).resolve()
    builder_bytes = builder.read_bytes()
    refinement_pin = {"path": str(builder), "bytes": len(builder_bytes), "sha256": digest(builder_bytes)}
    base_manifest_bytes = (base / "manifest.json").read_bytes()
    base_manifest = json.loads(base_manifest_bytes)
    base_packed = (base / "evidence.json.gz").read_bytes()
    base_decoded = gzip.decompress(base_packed)
    if digest(base_packed) != base_manifest["artifact"]["gzipSha256"] or digest(base_decoded) != base_manifest["artifact"]["decodedSha256"]:
        raise ValueError("Reviewed hold base does not match its source pins")
    payload = json.loads(base_decoded)
    base_audit = json.loads((base / "audit.json").read_bytes())
    retained_extractor = base / "held_extractor_before_review_holds.py"
    if digest(retained_extractor.read_bytes()) != base_audit["builderPin"]["sha256"]:
        raise ValueError("Executed base extractor was not retained byte-for-byte")
    quality_path = base.parent / "held_candidate_quality_receipt.json"
    quality_bytes = quality_path.read_bytes()
    reviewed = {row["eventId"]: row for row in json.loads(quality_bytes)["aliasTrapRecords"]}
    target_ids = {"3919630007821778", "3977655147900412"}
    removed = []
    rows = []
    for row in payload["rows"]:
        if row["eventId"] not in target_ids:
            rows.append(row)
            continue
        if row["eventId"] not in reviewed or row["sourceRef"] != reviewed[row["eventId"]]["sourceRef"]:
            raise ValueError("Reviewed hold identity or original chunk pin drift")
        if not row["evidence"] or any(not item["ruleId"].startswith("narrative_") for item in row["evidence"]):
            raise ValueError("Cannot withdraw a source-coded record in a narrative-only hold")
        ref = row["sourceRef"]
        path = shared_root / "data/canonical_web/event_chunks" / (ref["chunk"] + ".json")
        source_bytes = path.read_bytes()
        if digest(source_bytes) != ref["chunkSha256"]:
            raise ValueError("Original reviewed source chunk changed")
        event = json.loads(source_bytes)[ref["detailIndex"]]
        if str(event["event_id"]) != row["eventId"] or event["source"] != row["source"] or field_text(event.get("source_id")) != row["sourceEventId"]:
            raise ValueError("Original reviewed source record changed")
        raw = source_fields(event)
        excerpts = []
        for item in row["evidence"]:
            actual = field_text(raw.get(item["field"])) if item["field"] in raw else field_text(event.get(item["field"]))
            if item["excerpt"] not in actual:
                raise ValueError("Reviewed source quote is not a verbatim original field excerpt")
            excerpts.append(item)
        removed.append({"eventId": row["eventId"], "source": row["source"], "sourceEventId": row["sourceEventId"], "sourceRef": ref, "originalSourceBytes": len(source_bytes), "evidence": excerpts, "reason": "The same narrative calls sky lights alien and discusses what police might think; it does not report an observed being. Hold every narrative addition for this record; canonical report remains inspectable."})
    if {row["eventId"] for row in removed} != target_ids:
        raise ValueError("Both exact reviewed rows must be present in the pinned base")
    payload["rows"] = rows
    counts = Counter()
    statuses = Counter()
    indexed_sources = Counter()
    being_counts = Counter()
    associations = Counter()
    statuses_by_source = defaultdict(Counter)
    beings_by_source = defaultdict(Counter)
    samples = defaultdict(list)
    for row in rows:
        indexed_sources[row["source"]] += 1
        if row["abductionStatus"]:
            statuses[row["abductionStatus"]] += 1
            statuses_by_source[row["source"]][row["abductionStatus"]] += 1
        if row["beingTypes"]:
            counts["beingReportCount"] += 1
            being_counts.update(row["beingTypes"])
            beings_by_source[row["source"]].update(row["beingTypes"])
            associations[row["craftAssociation"]] += 1
        group = row["abductionStatus"] or row["craftAssociation"]
        if len(samples[group]) < 8: samples[group].append(row)
    totals = {"catalogCount": payload["catalogCount"], "rowCount": len(rows), "beingReportCount": counts["beingReportCount"], "abductionStatusCounts": dict(statuses), "abductionStatusBySource": {key: dict(value) for key, value in statuses_by_source.items()}, "beingTypeCounts": dict(being_counts), "beingTypesBySource": {key: dict(value) for key, value in beings_by_source.items()}, "craftAssociationCounts": dict(associations), "sourceCounts": base_manifest["counts"]["sourceCounts"], "indexedSourceCounts": dict(indexed_sources)}
    decoded = compact(payload)
    packed = gzip.compress(decoded, compresslevel=9, mtime=0)
    artifact = {"file": "evidence.json.gz", "url": "./data/encounters/evidence.json.gz", "rowCount": len(rows), "gzipBytes": len(packed), "decodedBytes": len(decoded), "gzipSha256": digest(packed), "decodedSha256": digest(decoded), "sha256": digest(decoded)}
    generated = datetime.now(timezone.utc).isoformat()
    policy = dict(base_manifest["policy"])
    policy["reviewedWholeRecordHolds"] = "Two exact source-verified narrative-only records withdrawn from this positive index; no canonical records or direct source-coded evidence removed."
    manifest = {"schemaId": SCHEMA_ID, "releaseId": RELEASE_ID, "generatedAtUtc": generated, "catalogCount": payload["catalogCount"], "rowCount": len(rows), "taxonomy": TAXONOMY, "artifact": artifact, "counts": totals, "policy": policy}
    if digest(builder.read_bytes()) != refinement_pin["sha256"]:
        raise ValueError("Reviewed hold transformer changed during verification")
    audit = {"schemaId": SCHEMA_ID, "releaseId": RELEASE_ID, "generatedAtUtc": generated, "elapsedSeconds": round(time.monotonic() - started, 3), "role": "Canonical reviewed sparse evidence, derived from source-pinned full corpus extraction", "builderPin": refinement_pin, "baseExtractorPin": base_audit["builderPin"], "retainedBaseExtractor": str(retained_extractor), "inputRoot": base_audit["inputRoot"], "inputChunkCount": base_audit["inputChunkCount"], "inputPins": base_audit["inputPins"], "baseArtifact": {"path": str(base / "evidence.json.gz"), "gzipSha256": digest(base_packed), "decodedSha256": digest(base_decoded)}, "qualityReviewPin": {"path": str(quality_path), "bytes": len(quality_bytes), "sha256": digest(quality_bytes)}, "reviewedHolds": removed, "beforeCounts": base_manifest["counts"], "counts": totals, "sourceCodedFactsUntouched": True, "policy": policy, "replay": f"py -3 scripts/build_encounter_evidence.py --apply-reviewed-holds \"{base}\" --shared-root \"{shared_root}\" --output \"{output}\"", "retention": "Retain this final canonical sparse evidence and its unique earlier quality intermediates/extractors. Original corpus and production/rollback releases are unchanged. No deletion or full corpus copy performed."}
    outputs = {"evidence.json.gz": packed, "manifest.json": compact(manifest), "audit.json": compact(audit), "review_fixtures.json": compact(dict(samples))}
    total_bytes = sum(len(value) for value in outputs.values())
    if total_bytes > MAX_OUTPUT_BYTES: raise ValueError("Reviewed artifact output budget exceeded")
    output.mkdir(parents=True, exist_ok=True)
    if any((output / name).exists() for name in outputs): raise ValueError("Refusing to overwrite a protected evidence artifact")
    for name, value in outputs.items(): (output / name).write_bytes(value)
    print(json.dumps({"output": str(output), "bytesWritten": total_bytes, "artifact": artifact, "counts": totals, "reviewedHolds": sorted(target_ids)}, sort_keys=True))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shared-root", type=Path, default=SHARED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--apply-reviewed-holds", type=Path, help="Pinned full-corpus candidate directory for the two reviewed narrative-only holds")
    args = parser.parse_args()
    if args.apply_reviewed_holds:
        apply_reviewed_holds(args.apply_reviewed_holds, args.shared_root, args.output)
    else:
        build(args.shared_root, args.output)
