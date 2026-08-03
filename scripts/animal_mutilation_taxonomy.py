"""Inclusive, sentence-local animal classification for mutilation research.

The Phase 1 discovery scanner intentionally favored recall.  This module is
the stricter second-generation contract: an animal is emitted as a reported
or possible victim only when the same evidence unit links that animal to an
explicit mutilation phrase or a distinctive injury finding.  Other animal
mentions are preserved as context instead of silently discarded.

The classifier is deterministic and lexical.  Its output is a review aid, not
an assertion that a reported incident occurred or that any anomalous cause is
established.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re
import unicodedata
from typing import Iterable, Sequence


@dataclass(frozen=True)
class TaxonDefinition:
    normalized_common_name: str
    species_group: str
    domestic_context: str
    terms: tuple[str, ...]


@dataclass(frozen=True)
class AnimalAssertion:
    reported_text: str
    reported_taxon_key: str
    normalized_common_name: str
    species_group: str
    domestic_context: str
    incident_role: str
    identification_basis: str
    identification_confidence: float
    evidence_excerpt: str


@dataclass(frozen=True)
class IncidentAnimalAnalysis:
    victim_assertions: tuple[AnimalAssertion, ...]
    context_assertions: tuple[AnimalAssertion, ...]
    all_animal_terms: tuple[str, ...]
    evidence_mode: str
    evidence_terms: tuple[str, ...]
    evidence_sentences: tuple[str, ...]
    nonclassic_harm_only: bool


TAXA: tuple[TaxonDefinition, ...] = (
    TaxonDefinition(
        "cattle",
        "bovine",
        "livestock",
        (
            "cattle", "cow", "cows", "calf", "calves", "bull", "bulls", "steer", "steers",
            "heifer", "heifers", "ox", "oxen", "bovine", "ganado", "vaca", "vacas", "boi",
            "bois", "gado", "rund", "rinder", "kuh", "kuhe", "koe", "koeien",
        ),
    ),
    TaxonDefinition("bison", "bovine", "wildlife_or_livestock", ("bison", "buffalo")),
    TaxonDefinition("other_bovine", "bovine", "livestock_or_wildlife", ("yak", "yaks", "water buffalo")),
    TaxonDefinition(
        "horse",
        "equine",
        "livestock_or_companion",
        ("horse", "horses", "mare", "mares", "stallion", "stallions", "equine", "caballo", "caballos", "cavalo", "cavalos", "paard", "paarden", "pferd", "pferde"),
    ),
    TaxonDefinition("donkey", "equine", "livestock", ("donkey", "donkeys", "burro", "burros", "asno", "asnos")),
    TaxonDefinition("mule", "equine", "livestock", ("mule", "mules", "mula", "mulas")),
    TaxonDefinition(
        "sheep",
        "ovine",
        "livestock",
        ("sheep", "ewe", "ewes", "lamb", "lambs", "cordero", "corderos", "oveja", "ovejas", "ovelha", "ovelhas", "schaap", "schapen", "schaf", "schafe"),
    ),
    TaxonDefinition("goat", "caprine", "livestock", ("goat", "goats", "cabra", "cabras", "geit", "geiten", "ziege", "ziegen")),
    TaxonDefinition(
        "pig",
        "porcine",
        "livestock_or_wildlife",
        ("pig", "pigs", "hog", "hogs", "swine", "boar", "boars", "sow", "sows", "cerdo", "cerdos", "puerco", "puercos", "porco", "porcos", "varken", "varkens", "schwein", "schweine"),
    ),
    TaxonDefinition("camelid", "camelid", "livestock", ("llama", "llamas", "alpaca", "alpacas", "camel", "camels")),
    TaxonDefinition(
        "deer",
        "cervid",
        "wildlife",
        ("deer", "elk", "moose", "reindeer", "caribou", "stag", "stags", "venado", "venados", "ciervo", "ciervos", "hirsch"),
    ),
    TaxonDefinition(
        "other_ungulate",
        "other_ungulate",
        "wildlife_or_livestock",
        (
            "antelope", "gazelle", "pronghorn", "zebra", "zebras", "giraffe", "giraffes",
            "rhinoceros", "rhinoceroses", "rhino", "rhinos", "hippopotamus",
            "hippopotamuses", "hippo", "hippos", "tapir", "tapirs",
        ),
    ),
    TaxonDefinition("dog", "canid", "companion_or_working", ("dog", "dogs", "canine", "perro", "perros", "cao", "caes", "cachorro", "cachorros", "hond", "honden", "hund", "hunde")),
    TaxonDefinition("wild_canid", "canid", "wildlife", ("coyote", "coyotes", "wolf", "wolves", "fox", "foxes", "jackal", "jackals")),
    TaxonDefinition("cat", "felid", "companion", ("cat", "cats", "feline", "gato", "gatos", "gata", "gatas", "kat", "katten", "katze", "katzen")),
    TaxonDefinition(
        "wild_felid",
        "felid",
        "wildlife",
        (
            "cougar", "cougars", "mountain lion", "mountain lions", "lion", "lions",
            "tiger", "tigers", "leopard", "leopards", "cheetah", "cheetahs", "panther",
            "panthers", "bobcat", "bobcats", "lynx", "jaguar", "jaguars",
        ),
    ),
    TaxonDefinition("rabbit_hare", "lagomorph", "wildlife_or_companion", ("rabbit", "rabbits", "hare", "hares", "bunny", "bunnies", "conejo", "conejos")),
    TaxonDefinition("rodent", "rodent", "wildlife_or_companion", ("rodent", "rodents", "rat", "rats", "mouse", "mice", "squirrel", "squirrels", "beaver", "beavers")),
    TaxonDefinition(
        "other_named",
        "other_mammal",
        "wildlife_or_captive",
        (
            "bear", "bears", "elephant", "elephants", "monkey", "monkeys", "ape", "apes",
            "gorilla", "gorillas", "chimpanzee", "chimpanzees", "primate", "primates",
            "raccoon", "raccoons", "opossum", "opossums", "skunk", "skunks", "badger",
            "badgers", "otter", "otters", "mink", "minks", "ferret", "ferrets", "weasel",
            "weasels", "bat", "bats", "hyena", "hyenas", "wolverine", "wolverines",
            "porcupine", "porcupines", "hedgehog", "hedgehogs", "kangaroo", "kangaroos",
            "wallaby", "wallabies", "koala", "koalas", "sloth", "sloths", "anteater",
            "anteaters", "armadillo", "armadillos", "platypus", "platypuses",
        ),
    ),
    TaxonDefinition(
        "poultry",
        "avian",
        "livestock",
        ("chicken", "chickens", "hen", "hens", "rooster", "roosters", "turkey", "turkeys", "duck", "ducks", "goose", "geese", "poultry", "pollo", "pollos", "gallina", "gallinas"),
    ),
    TaxonDefinition("wild_bird", "avian", "wildlife", ("bird", "birds", "eagle", "eagles", "hawk", "hawks", "owl", "owls", "vulture", "vultures", "crow", "crows", "raven", "ravens", "penguin", "penguins", "ostrich", "ostriches", "parrot", "parrots")),
    TaxonDefinition("fish", "fish", "wildlife_or_captive", ("fish", "fishes", "salmon", "trout", "shark", "sharks", "eel", "eels")),
    TaxonDefinition("marine_mammal", "marine_mammal", "wildlife", ("dolphin", "dolphins", "whale", "whales", "seal", "seals", "porpoise", "porpoises", "walrus", "walruses", "manatee", "manatees", "orca", "orcas")),
    TaxonDefinition("reptile", "reptile", "wildlife_or_captive", ("reptile", "reptiles", "snake", "snakes", "lizard", "lizards", "alligator", "alligators", "crocodile", "crocodiles", "turtle", "turtles", "iguana", "iguanas", "gecko", "geckos")),
    TaxonDefinition("amphibian", "amphibian", "wildlife_or_captive", ("amphibian", "amphibians", "frog", "frogs", "toad", "toads", "salamander", "salamanders", "newt", "newts")),
    TaxonDefinition(
        "invertebrate",
        "invertebrate",
        "wildlife_or_captive",
        (
            "invertebrate", "invertebrates", "insect", "insects", "bee", "bees", "wasp",
            "wasps", "butterfly", "butterflies", "moth", "moths", "beetle", "beetles",
            "spider", "spiders", "scorpion", "scorpions", "crab", "crabs", "lobster",
            "lobsters", "shrimp", "squid", "octopus", "octopuses", "snail", "snails",
            "slug", "slugs", "worm", "worms", "jellyfish",
        ),
    ),
)

GENERIC_ANIMAL_TERMS: tuple[str, ...] = (
    "animal", "animals", "livestock", "stock animal", "stock animals", "creature", "creatures",
    "animales", "animais", "dieren", "tiere",
)

MUTILATION_PATTERNS: tuple[str, ...] = (
    r"\bmutilat\w*\b",
    r"\bmutilac\w*\b",
    r"\bmutilad\w*\b",
    r"\bverstummel\w*\b",
    r"\bverminkt\w*\b",
)

NEGATED_MUTILATION_PATTERNS: tuple[str, ...] = (
    r"\bnot\s+(?:been\s+)?mutilat\w*\b",
    r"\b(?:no|none\s+of\s+the)\s+(?:[a-z0-9-]+\s+){0,5}(?:was|were|had\s+been)?\s*mutilat\w*\b",
    r"\bno\s+mutilations?\s+(?:occurred|were\s+found|reported)\b",
    r"\bnot\s+(?:a\s+)?(?:classic\s+)?mutilation\b",
    r"\black(?:ed|s|ing)?\s+(?:the\s+)?(?:classic\s+)?mutilation\s+features\b",
    r"\bdid\s+not\s+(?:have|show)\s+(?:the\s+)?(?:classic\s+)?mutilation\s+features\b",
    r"\bno\s+mutilation\s+(?:connection|link|association)\b",
)

PLACE_HOMONYM_PATTERNS: tuple[str, ...] = (
    r"\bbuffalo\s+(?:area|vicinity|county|city|new\s+york|ny)\b",
    r"\bcow\s+(?:down|drove\s+hill)\b",
    r"\bfort\s+keogh\s+livestock\s+(?:lab|laboratory)\b",
    r"\beagle\s+nest\b",
    r"\beagle\s+southeast\s+fairbanks\s+borough\b",
    r"\bfox\s+run\s+road\b",
    r"\botter\s+tail\s+county\b",
    r"\bseal\s+beach\b",
    r"\b(?:buffalo|cow|cattle|horse|deer|elk|eagle|turkey|fox|cat|dog)\s+"
    r"(?:area|county|city|town|township|village|borough|parish|district|province|state|"
    r"region|road|street|avenue|lane|drive|highway|mountain|mountains|river|lake|valley|"
    r"island|beach|bay|harbor|airfield|airport|base|laboratory|lab)\b",
)

NON_ANIMAL_HOMONYM_PATTERNS: tuple[str, ...] = (
    r"\b(?:robotic|mechanical)\s+(?:slug|spider|insect|beetle)\b",
    r"\bteddy\s+bear\b",
    r"\b(?:as\s+the\s+)?crow\s+flies\b",
    r"\bblack\s+hawk\s+helicopters?\b",
    r"\bcat[ -]nap\b",
    r"\bguinea\s+pigs?\b",
    r"\bfish\s+(?:and|&)\s+wildlife\b",
    r"\bwhirly[ -]birds?(?:\s+type)?\s+helicopters?\b",
    r"\bnewt\s+gingrich\b",
    r"\bpenguin(?:\s+random\s+house)?\s+"
    r"(?:press|publisher|published|publishes|publishing|books?|edition|editions|classics?)\b",
    r"\bostrich\s+(?:algorithm|algorithms|method|methods|model|models|"
    r"optimization|optimizer|approach|strategy)\b",
    r"\b(?:dog|cat|horse|cow)[ -]?sized\s+creatures?\b",
)

NEGATED_ANIMAL_EXISTENCE_PATTERNS: tuple[str, ...] = (
    r"\bno\s+(?:dead\s+|injured\s+|mutilated\s+)?(?:animal|animals|livestock|stock\s+animals?|creatures?)\b",
    r"\bnot\s+(?:an?|any)\s+(?:animal|livestock|creature)\b",
)

LOCATION_SUFFIX_PATTERN = re.compile(
    r"^\s+(?:area|vicinity|surroundings|county|city|town|"
    r"township|village|borough|parish|district|province|state|region|point|road|street|"
    r"avenue|lane|drive|highway|mountain|mountains|river|lake|valley|island|airfield|"
    r"airport|base|beach|bay|harbor|laboratory|lab)\b"
)

DISTINCTIVE_INJURY_PATTERNS: tuple[str, ...] = (
    r"\b(?:gutted|dissected|exsanguinated|decapitated)\b",
    r"\b(?:was|were|been|found)\s+(?:partially\s+|completely\s+)?skinned\b",
    r"\bskinned\s+(?:animal|livestock|carcass)\b",
    r"\b(?:drained|drainage)\s+(?:completely\s+)?(?:of\s+)?(?:its\s+|the\s+)?blood\b",
    r"\b(?:bloodless|no\s+blood|sin\s+sangre|sem\s+sangue|blutleer|bloedloos)\b",
    r"\b(?:crushed\s+and\s+bloodless|mashed\s+up)\b",
    r"\b(?:organs?|tissue|hide|skin|tongue|eyes?|ears?|udder|genitals?|sexual\s+organs?|rectum|anus|jaw|head|neck|torso|limbs?|legs?)\b.{0,55}\b(?:removed|missing|absent|excised|severed|cut\s+out|stripped|cored|surgically\s+cut)\b",
    r"\b(?:removed|excised|severed|cut\s+out|stripped|cored)\b.{0,55}\b(?:organs?|tissue|hide|skin|tongue|eyes?|ears?|udder|genitals?|sexual\s+organs?|rectum|anus|jaw|head|neck|torso|limbs?|legs?)\b",
    # ``missing`` is common non-injury prose (for example, a missing dog that
    # later "beat me home"). Keep the reverse form grammatical and local so a
    # later first-person verb such as "I head ..." cannot become a fictitious
    # missing-head finding.
    r"\b(?:missing|absent)\b(?:\s+(?:the|its|it\s+s|his|her|their|an?|one|both|of|left|right|entire|whole)){0,4}\s+(?:organs?|tissue|hide|skin|tongue|eyes?|ears?|udder|genitals?|sexual\s+organs?|rectum|anus|jaw|head|neck|torso|limbs?|legs?)\b",
    r"\b(?:organos?|tejido|lengua|ojos?|orejas?)\b.{0,55}\b(?:removidos?|extraidos?|ausentes?|cortados?)\b",
    r"\b(?:orgaos?|tecido|lingua|olhos?|orelhas?)\b.{0,55}\b(?:removidos?|extraidos?|ausentes?|cortados?)\b",
    r"\b(?:precision\s+surgical|surgical\s+precision|surgical\s+incisions?|precise\s+incisions?)\b",
    r"\b(?:circular|clean|precise)\s+(?:cuts?|incisions?|excision)\b",
)

NEGATED_DISTINCTIVE_INJURY_PATTERNS: tuple[str, ...] = (
    r"\b(?:not|never)\s+(?:been\s+|found\s+)?(?:gutted|dissected|exsanguinated|decapitated|skinned|bloodless)\b",
    r"\b(?:not|never)\s+drained\s+(?:completely\s+)?(?:of\s+)?(?:its\s+|the\s+)?blood\b",
    r"\bno\s+(?:organs?|tissue|hide|skin|tongue|eyes?|ears?|udder|genitals?|sexual\s+organs?|rectum|anus|jaw|head|neck|torso|limbs?|legs?)\s+(?:(?:was|were|are|is)\s+)?(?:missing|absent|removed|excised|severed|cut\s+out|stripped|cored)\b",
    r"\b(?:organs?|tissue|hide|skin|tongue|eyes?|ears?|udder|genitals?|sexual\s+organs?|rectum|anus|jaw|head|neck|torso|limbs?|legs?)\s+(?:(?:was|were|are|is)\s+)?(?:not|never)\s+(?:missing|absent|removed|excised|severed|cut\s+out|stripped|cored)\b",
    r"\bno\s+(?:circular|clean|precise|surgical)\s+(?:cuts?|incisions?|excision)\b",
)

NONCLASSIC_HARM_PATTERNS: tuple[str, ...] = (
    r"\b(?:dead|died|death|killed|slain|carcass|carcasses|corpse)\b",
    r"\b(?:muerto|muertos|muerta|muertas|morte|mortos|morta|mortas|dood|tot|cadaver|cadaveres)\b",
)

OCCURRENCE_PATTERNS: tuple[str, ...] = (
    r"\b(?:found|discovered|located|recovered|reported|investigated|occurred)\b",
    r"\b(?:hallado|hallada|hallados|halladas|encontrado|encontrada|encontrados|encontradas|gevonden|gefunden)\b",
    r"\b(?:was|were|is|are|had\s+been|have\s+been)\b",
)

COMPANION_CONTEXT_PATTERNS: tuple[str, ...] = (
    r"\b(?:taking|walking|with)\s+(?:my|his|her|their|the|a)?\s*(?:pet\s+)?(?:dog|dogs|cat|cats)\b",
    r"\b(?:dog|dogs|cat|cats)\s+(?:found|discovered|alerted|barked|reacted|watched|approached|led)\b",
    r"\b(?:my|his|her|their)\s+(?:dog|dogs|cat|cats)\b",
    r"\b(?:i|we)\s+(?:have|had)\s+(?:[a-z0-9-]+\s+){0,3}(?:dogs?|cats?)\s+and\s+(?:checked|examined)\s+(?:it|them)\b",
)

PREDATOR_CONTEXT_PATTERNS: tuple[str, ...] = (
    r"\b(?:coyote|coyotes|wolf|wolves|fox|foxes|vulture|vultures|crow|crows|raven|ravens|dog|dogs)\s+(?:(?:was|were|is|are)\s+)?(?:ate|eating|fed|feeding|scavenged|scavenging|attacked|consumed|nearby)\b",
    r"\b(?:predator|predators|scavenger|scavengers)\b",
    r"\b(?:blamed|attributed)\s+(?:on|to)\s+(?:some\s+type\s+of\s+)?(?:non\s+native\s+)?(?:coyote|coyotes|wolf|wolves|fox|foxes|vulture|vultures|crow|crows|raven|ravens|dog|dogs)\b",
    r"\b(?:due\s+to|caused\s+by)\s+(?:coyote|coyotes|wolf|wolves|fox|foxes|vulture|vultures|crow|crows|raven|ravens|dog|dogs)\b",
)

GENERIC_BACKGROUND_PATTERN = re.compile(
    r"\b(?:animal\s+mutilation\s+cases?|mutilated\s+animal\s+cases?|"
    r"(?:animal\s+)?mutilations?\s+(?:have\s+been|were)\s+reported|"
    r"common\s+to|heard\s+about|in\s+the\s+past|historically|typically|generally|"
    r"researchers?\s+(?:biograph\w*|profiles?|backgrounds?|careers?)|"
    r"research(?:ing)?\s+(?:the\s+)?(?:topic|subject|history)\s+of|"
    r"book|article|theory|theories)\b",
    flags=re.IGNORECASE,
)

GENERIC_NON_INCIDENT_PATTERNS: tuple[str, ...] = (
    # Explicit negatives and unsupported speculation are not incident reports.
    r"\bdid\s+not\s+(?:see|witness|observe|find|discover)\b.{0,100}\b"
    r"(?:animal|livestock|creatures?)\b.{0,45}\bmutilat\w*\b",
    r"\bnot\s+at\s+all\s+(?:an?\s+)?(?:case\s+of\s+)?"
    r"(?:animal|livestock)\s+mutilat\w*\b",
    r"\b(?:can|could)\s+only\s+assume\b.{0,140}\b"
    r"(?:animal|livestock|creatures?)\b.{0,45}\bmutilat\w*\b",
    r"\bnot\s+(?:trying\s+to\s+)?speculat\w*\b.{0,100}\b"
    r"(?:animal|livestock|creatures?)\b.{0,45}\bmutilat\w*\b",
    r"\b(?:might|may|could|would)\s+(?:be\s+)?(?:considered\s+)?"
    r"(?:an?\s+)?(?:animal|livestock)\s+mutilat\w*\b",
    r"\b(?:animal|livestock)\s+mutilation\s+tags?\b",
    # Entity descriptions, agents, analogies, and hypotheticals are context.
    r"\bcreatures?\b.{0,140}\bmissing\s+time\b",
    r"\b(?:man|woman|person|witness)\s+attacked\s+by\b.{0,100}\b"
    r"creatures?\b.{0,120}\banimal\s+mutilations?\s+reported\s+in\s+"
    r"(?:the\s+)?area\b",
    r"\bwild\s+animal\s+attacks?\b",
    r"\b(?:aura|air|appearance|metaphor|analogy|symbol)\s+of\b.{0,60}\b"
    r"(?:animal|livestock)\s+mutilat\w*\b",
    r"\b(?:when|if)\s+there\s+(?:is|are|was|were)\b.{0,50}\b"
    r"(?:animal|livestock)\s+mutilat\w*\b",
    # Source titles, catalogs, and discussion about incidents are not incidents.
    r"\b(?:sources?|catalog\s+entry|summary\s+report|bibliograph\w*|"
    r"citation)\b.{0,180}\b(?:animal|livestock)\s+mutilat\w*\b",
    r"\b(?:term\s+paper|book|article|paper|publication)\b.{0,140}\b"
    r"(?:animal|livestock)\s+mutilat\w*\b",
    r"\b(?:read|heard|learned)\s+about\b.{0,120}\b"
    r"(?:animal|livestock)\s+mutilat\w*\b",
    r"\b(?:animal|livestock)\s+mutilat\w*\b.{0,80}\b"
    r"(?:in|on)\s+(?:the\s+)?(?:news|media)\b",
    r"\b(?:watched|heard|saw)\b.{0,80}\b(?:news|broadcast|documentary)\b"
    r".{0,160}\b(?:animal|livestock)\b.{0,45}\bmutilat\w*\b",
    # Perpetrator theories do not establish an underlying animal incident.
    r"\bmy\s+guess\s+is\b.{0,180}\b(?:animal|livestock)\s+mutilat\w*\b",
    r"\bresponsible\s+(?:for|to)\b.{0,120}\b(?:animal|livestock)\s+"
    r"mutilat\w*\b",
    r"\bfree\s+to\s+(?:conduct|perform|carry\s+out)\b.{0,80}\b"
    r"(?:animal|livestock)\s+mutilat\w*\b",
    # Investigator, future-event, and reaction language is contextual only.
    r"\bstakeout\s+for\b.{0,60}\banimal\s+mutilators?\b",
    r"\bfuture\b.{0,80}\b(?:animal|livestock)\s+mutilat\w*\b",
    r"\b(?:animal|livestock)\s+mutilat\w*\b.{0,100}\b"
    r"(?:may|might|could|would)\s+(?:come|occur|happen|take\s+place)\b",
    r"\b(?:animal|livestock)\s+mutilat\w*\b\s+"
    r"(?:disgusts?|frightens?|fascinates?|interests?|worries?)\b",
    r"\banimal\s+mutilators?\b",
)


def normalize_for_match(value: object) -> str:
    text = unicodedata.normalize("NFKD", "" if value is None else str(value).casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _normalized_source_map(value: object) -> tuple[str, str, tuple[int, ...]]:
    """Return compact source text plus normalized text-to-source positions."""

    source = re.sub(r"\s+", " ", "" if value is None else str(value)).strip()
    normalized: list[str] = []
    source_positions: list[int] = []
    separator_position: int | None = None
    for source_position, source_char in enumerate(source):
        decomposed = unicodedata.normalize("NFKD", source_char.casefold())
        for char in decomposed:
            if unicodedata.combining(char):
                continue
            if ("a" <= char <= "z") or ("0" <= char <= "9"):
                if separator_position is not None and normalized:
                    normalized.append(" ")
                    source_positions.append(separator_position)
                separator_position = None
                normalized.append(char)
                source_positions.append(source_position)
            elif normalized:
                separator_position = source_position
    return source, "".join(normalized), tuple(source_positions)


def _localized_evidence_excerpt(
    text: str,
    normalized_spans: Sequence[tuple[int, int]],
    *,
    max_chars: int,
) -> str:
    """Keep the source window containing the animal and its closest harm text."""

    source, normalized, source_positions = _normalized_source_map(text)
    if not source or not normalized or not source_positions:
        return source[:max_chars]
    valid_spans = [
        (max(0, start), min(len(normalized), end))
        for start, end in normalized_spans
        if 0 <= start < end <= len(normalized)
    ]
    if not valid_spans:
        return source[:max_chars]
    source_start = source_positions[min(start for start, _end in valid_spans)]
    source_end = source_positions[max(end for _start, end in valid_spans) - 1] + 1
    if len(source) <= max_chars:
        return source

    marker_budget = 8
    content_budget = max(1, max_chars - marker_budget)
    anchor_width = source_end - source_start
    if anchor_width <= content_budget:
        padding = content_budget - anchor_width
        window_start = max(0, source_start - padding // 2)
        window_end = min(len(source), window_start + content_budget)
        window_start = max(0, window_end - content_budget)
        excerpt = source[window_start:window_end].strip()
        if window_start:
            excerpt = "... " + excerpt
        if window_end < len(source):
            excerpt += " ..."
        return excerpt[:max_chars]

    # Extremely distant anchors use two explicitly separated source windows.
    # This retains both factual anchors without presenting omitted prose as
    # contiguous text.
    disconnected_content_budget = max(2, max_chars - 13)
    left_budget = max(1, disconnected_content_budget // 2)
    right_budget = max(1, disconnected_content_budget - left_budget)
    left_end = min(len(source), source_start + left_budget)
    right_start = max(0, source_end - right_budget)
    excerpt = f"{source[source_start:left_end].strip()} ... {source[right_start:source_end].strip()}"
    if source_start:
        excerpt = "... " + excerpt
    if source_end < len(source):
        excerpt += " ..."
    return excerpt


@lru_cache(maxsize=None)
def _term_pattern(terms: tuple[str, ...]) -> re.Pattern[str]:
    normalized = sorted(
        {normalize_for_match(term) for term in terms if normalize_for_match(term)},
        key=lambda value: (-len(value), value),
    )
    if not normalized:
        return re.compile(r"(?!x)x")
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(term) for term in normalized) + r")(?![a-z0-9])")


@lru_cache(maxsize=None)
def _regex_union(patterns: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile("(?:" + ")|(?:".join(patterns) + ")", flags=re.IGNORECASE)


def all_specific_terms() -> tuple[str, ...]:
    return tuple(term for taxon in TAXA for term in taxon.terms)


def all_animal_terms() -> tuple[str, ...]:
    return (*all_specific_terms(), *GENERIC_ANIMAL_TERMS)


@lru_cache(maxsize=1)
def _taxon_by_normalized_term() -> dict[str, TaxonDefinition]:
    mapping: dict[str, TaxonDefinition] = {}
    for taxon in TAXA:
        for term in taxon.terms:
            normalized = normalize_for_match(term)
            if normalized and normalized not in mapping:
                mapping[normalized] = taxon
    return mapping


def _sentences(text: str) -> list[str]:
    compact = re.sub(r"[\t ]+", " ", str(text or "")).strip()
    if not compact:
        return []
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+|[\r\n]+|\s*;\s*", compact)
        if sentence.strip()
    ]


def _mentions(normalized_sentence: str) -> list[tuple[TaxonDefinition | None, str, int, int]]:
    matches: list[tuple[TaxonDefinition | None, str, int, int]] = []
    place_spans = [
        (match.start(), match.end())
        for match in _regex_union(PLACE_HOMONYM_PATTERNS).finditer(normalized_sentence)
    ]
    non_animal_spans = [
        (match.start(), match.end())
        for match in _regex_union(NON_ANIMAL_HOMONYM_PATTERNS).finditer(
            normalized_sentence
        )
    ]
    non_animal_spans.extend(
        (match.start(), match.end())
        for match in _regex_union(NEGATED_ANIMAL_EXISTENCE_PATTERNS).finditer(
            normalized_sentence
        )
    )

    def is_non_animal_mention(start: int, end: int) -> bool:
        if any(
            span_start <= start and end <= span_end
            for span_start, span_end in (*place_spans, *non_animal_spans)
        ):
            return True
        if LOCATION_SUFFIX_PATTERN.search(normalized_sentence[end : end + 70]):
            return True
        prefix = normalized_sentence[max(0, start - 70) : start]
        suffix = normalized_sentence[end : end + 30]
        term_text = normalized_sentence[start:end]
        trace_comparison = re.search(
            r"\b(?:tracks?|prints?|footprints?|signs?)\b.{0,45}\b"
            rf"(?:like|resembling|resemble[ds]?)\s+(?:an?\s+)?{re.escape(term_text)}\b",
            normalized_sentence,
        )
        if re.search(
            r"\b(?:like|resembling)\s+(?:(?:a|an|the)\s+)?(?:[a-z0-9-]+\s+){0,2}$",
            prefix,
        ) and not trace_comparison:
            return True
        if re.search(
            r"\b(?:bigger|larger|smaller)\s+than\s+(?:(?:a|an|the)\s+)?(?:[a-z0-9-]+\s+){0,2}$",
            prefix,
        ):
            return True
        return bool(re.match(r"^\s*(?:like|shaped)\b", suffix))

    term_taxa = _taxon_by_normalized_term()
    for match in _term_pattern(all_specific_terms()).finditer(normalized_sentence):
        if is_non_animal_mention(match.start(), match.end()):
            continue
        taxon = term_taxa[match.group(0)]
        matches.append((taxon, match.group(0), match.start(), match.end()))
    for match in _term_pattern(GENERIC_ANIMAL_TERMS).finditer(normalized_sentence):
        if is_non_animal_mention(match.start(), match.end()):
            continue
        matches.append((None, match.group(0), match.start(), match.end()))
    return sorted(matches, key=lambda row: (row[2], -(row[3] - row[2]), row[1]))


def _pattern_spans(normalized_sentence: str, patterns: tuple[str, ...]) -> list[tuple[str, int, int]]:
    return [
        (match.group(0), match.start(), match.end())
        for match in _regex_union(patterns).finditer(normalized_sentence)
    ]


def _span_distance(left: tuple[int, int], right: tuple[int, int]) -> int:
    if left[1] < right[0]:
        return right[0] - left[1]
    if right[1] < left[0]:
        return left[0] - right[1]
    return 0


def _has_passive_victim_link(sentence: str, term: str) -> bool:
    escaped = re.escape(term)
    injury = r"(?:mutilat\w*|gutted|dissected|drained|bloodless|decapitated|skinned|removed|missing|excised|severed|cut\s+out)"
    if re.search(
        rf"\b(?:found|discovered|located|recovered)\s+"
        rf"(?:(?:my|his|her|their|our|the|a|an)\s+)?{escaped}\b"
        rf"(?:\s+\w+){{0,2}}\s+{injury}\b",
        sentence,
    ):
        return True
    if re.search(
        rf"\b{escaped}\b\s+(?:was|were|is|are|had\s+been|have\s+been|found|reported)"
        rf"(?:\s+\w+){{0,3}}\s+{injury}\b",
        sentence,
    ):
        return True
    if re.search(
        rf"\b{escaped}\b\s+with(?:\s+[a-z0-9-]+){{1,5}}\s+"
        rf"(?:was|were)\s+found(?:\s+\w+){{0,2}}\s+{injury}\b",
        sentence,
    ):
        return True
    if re.search(
        rf"\b{escaped}\b.{{0,90}}\b(?:found|discovered)\s+(?:it|them|one)"
        rf"(?:\s+\w+){{0,2}}\s+{injury}\b",
        sentence,
    ):
        return True
    if re.search(
        rf"\b{escaped}\b.{{0,90}}\b(?:it|they|them)\s+(?:was|were)"
        rf"(?:\s+\w+){{0,2}}\s+{injury}\b",
        sentence,
    ):
        return True
    if re.search(
        rf"\b{escaped}\b(?:\s+\w+){{0,2}}\s+deaths?\b.{{0,240}}"
        rf"\bthe\s+deaths?\b.{{0,160}}\b{injury}\b",
        sentence,
    ):
        return True
    backward_injury = (
        r"(?:mutilated|gutted|dissected|drained|bloodless|decapitated|skinned|"
        r"removed|missing|excised|severed|cut\s+out)"
    )
    injury_pattern = re.compile(rf"\b{backward_injury}\b")
    term_pattern = re.compile(rf"\b{escaped}\b")
    for injury_match in injury_pattern.finditer(sentence):
        for term_match in term_pattern.finditer(sentence, injury_match.end()):
            between = sentence[injury_match.end() : term_match.start()]
            if len(between.split()) > 5:
                break
            if not re.search(
                r"\b(?:by|due\s+to|caused\s+by|blamed\s+on|attributed\s+to)\b",
                between,
            ):
                return True
    return False


def _generic_has_actual_incident_link(
    sentence: str,
    term: str,
    start: int,
    end: int,
    harm_spans: Sequence[tuple[str, int, int]],
) -> bool:
    """Require a predicate that governs a generic animal mention.

    ``animal mutilation`` is also the name of a topic, publication subject, and
    theory.  Proximity to that noun phrase therefore is not evidence that the
    record describes an animal incident.  Generic taxa are linked only by a
    bounded injury construction or by a nominal mutilation phrase with an
    occurrence verb.  Named taxa retain their existing, higher-recall path.
    """

    if any(
        re.search(pattern, sentence)
        for pattern in GENERIC_NON_INCIDENT_PATTERNS
    ):
        return False
    if re.search(
        r"\b(?:every|all)\s+creatures?\s+on\s+earth\b",
        sentence,
    ):
        return False
    if _has_passive_victim_link(sentence, term):
        return True

    escaped = re.escape(term)
    anatomy = (
        r"(?:organs?|tissue|hide|skin|tongue|eyes?|ears?|udder|genitals?|"
        r"sexual\s+organs?|rectum|anus|jaw|head|neck|torso|limbs?|legs?)"
    )
    injury = r"(?:removed|missing|absent|excised|severed|cut\s+out|stripped|cored)"
    if re.search(
        rf"\b{escaped}\b(?:\s+s)?\s+(?:had|has|have|with|whose)\b"
        rf".{{0,70}}\b{anatomy}\b.{{0,45}}\b{injury}\b",
        sentence,
    ):
        return True
    if re.search(
        rf"\b{escaped}\b\s+(?:appears?|appeared|seems?|seemed)\s+"
        rf"(?:to\s+have\s+been\s+|to\s+be\s+)?"
        r"(?:mutilated|gutted|dissected|drained|bloodless|decapitated|skinned)\b",
        sentence,
    ):
        return True

    occurrence = re.compile(
        r"\b(?:observed|reported|found|discovered|located|recovered|documented|"
        r"confirmed|recorded|verified|occurred|happened|took\s+place)\b"
    )
    nominal_mutilation = re.compile(
        r"^(?:mutilations?|mutilaciones?|mutilacoes?|mutilacao|"
        r"verstummelungen?|verminkingen?)$"
    )
    for harm, harm_start, harm_end in harm_spans:
        distance = _span_distance((start, end), (harm_start, harm_end))
        if distance > 55:
            continue
        between_start = min(end, harm_end)
        between_end = max(start, harm_start)
        between = sentence[between_start:between_end]
        if len(between.split()) > 7:
            continue
        if not nominal_mutilation.fullmatch(normalize_for_match(harm)):
            return True
        local_start = max(0, min(start, harm_start) - 65)
        local_end = min(len(sentence), max(end, harm_end) + 80)
        if occurrence.search(sentence[local_start:local_end]):
            return True
    return False


def _context_role(
    sentence: str,
    taxon: TaxonDefinition | None,
    term: str,
    start: int | None = None,
    end: int | None = None,
) -> str | None:
    if (
        taxon
        and taxon.normalized_common_name == "horse"
        and re.search(r"\bsnippy\b", sentence)
        and re.search(
            r"\b(?:remembered|well\s+known\s+case|historically|"
            r"weeks?\s+after\s+our\s+event|event\s+occurred\s+here\s+in\s+\d{4})\b",
            sentence,
        )
    ):
        return "context_only"
    if taxon and re.search(
        rf"\b(?:evoke|recall)\w*\b.{{0,50}}\bmemories?\s+of\b.{{0,50}}"
        rf"\b{re.escape(term)}\b(?:\s+[a-z0-9-]+){{0,2}}\s+mutilations?\b",
        sentence,
    ):
        return "context_only"
    if taxon and not _has_passive_victim_link(sentence, term) and re.search(
        rf"\bheard\b.{{0,45}}\b{re.escape(term)}\b"
        r"(?:\s+[a-z0-9-]+){0,2}\s+(?:croak\w*|calling)\b",
        sentence,
    ):
        return "context_only"
    if taxon and not _has_passive_victim_link(sentence, term) and (
        re.search(
            rf"\b{re.escape(term)}\b(?:\s+[a-z0-9-]+){{0,2}}\s+"
            r"(?:tracks?|prints?|footprints?|signs?)\b",
            sentence,
        )
        or re.search(
            r"\b(?:tracks?|prints?|footprints?|signs?)\b.{0,45}"
            rf"\b(?:like|resembling|resemble[ds]?)\s+"
            rf"(?:those\s+of\s+)?(?:an?\s+)?{re.escape(term)}\b",
            sentence,
        )
    ):
        return (
            "predator_or_scavenger"
            if taxon.species_group in {"canid", "felid"}
            else "context_only"
        )
    if taxon and not _has_passive_victim_link(sentence, term) and re.search(
        rf"\b{re.escape(term)}\b.{0,90}\b(?:checked|examined)\b.{0,70}\bno\s+blood\s+on\b",
        sentence,
    ):
        return "nearby_unaffected"
    if taxon and not _has_passive_victim_link(sentence, term) and (
        re.search(
            rf"\b{re.escape(term)}\b\s+(?:stood|remained|grazed|walked|waited)\s+nearby\b",
            sentence,
        )
        or re.search(
            rf"\b(?:rode|riding)\s+(?:an?\s+|the\s+)?{re.escape(term)}\b",
            sentence,
        )
    ):
        return "context_only"
    if taxon and not _has_passive_victim_link(sentence, term) and re.search(
        rf"\bby\s+(?:an?\s+|the\s+)?{re.escape(term)}\b",
        sentence,
    ):
        return (
            "predator_or_scavenger"
            if taxon.species_group in {"canid", "felid", "avian"}
            else "context_only"
        )
    if taxon and not _has_passive_victim_link(sentence, term):
        if any(re.search(pattern, sentence) for pattern in PREDATOR_CONTEXT_PATTERNS):
            predator_terms = {
                "coyote", "coyotes", "wolf", "wolves", "fox", "foxes",
                "vulture", "vultures", "crow", "crows", "raven", "ravens",
                "dog", "dogs",
            }
            if term in predator_terms:
                return "predator_or_scavenger"
        if start is not None and end is not None:
            for _harm, harm_start, harm_end in _pattern_spans(
                sentence, MUTILATION_PATTERNS
            ):
                active_verb = bool(re.fullmatch(r"mutilat(?:e|es|ing)", _harm))
                if (
                    active_verb
                    and end <= harm_start
                    and _term_pattern(all_specific_terms()).search(sentence, harm_end)
                ):
                    return (
                        "predator_or_scavenger"
                        if taxon.species_group in {"canid", "felid", "avian"}
                        else "context_only"
                    )
    if taxon and taxon.normalized_common_name in {"dog", "cat"}:
        if any(re.search(pattern, sentence) for pattern in COMPANION_CONTEXT_PATTERNS) and not _has_passive_victim_link(sentence, term):
            return "witness_companion"
    if taxon and taxon.normalized_common_name in {"wild_canid", "wild_bird", "dog"}:
        if any(re.search(pattern, sentence) for pattern in PREDATOR_CONTEXT_PATTERNS) and not _has_passive_victim_link(sentence, term):
            return "predator_or_scavenger"
    return None


def _assertion_key(
    assertion: AnimalAssertion, *, combine_roles: bool
) -> tuple[str, str, str]:
    return (
        assertion.normalized_common_name,
        assertion.reported_taxon_key,
        "" if combine_roles else assertion.incident_role,
    )


COARSE_TAXON_NAMES = {
    "other_bovine",
    "camelid",
    "deer",
    "other_ungulate",
    "wild_canid",
    "wild_felid",
    "rabbit_hare",
    "rodent",
    "poultry",
    "wild_bird",
    "fish",
    "marine_mammal",
    "reptile",
    "amphibian",
    "invertebrate",
    "other_named",
}

IRREGULAR_REPORTED_TAXA = {
    "fishes": "fish",
    "geese": "goose",
    "mice": "mouse",
    "wolves": "wolf",
    "foxes": "fox",
    "bunnies": "bunny",
    "butterflies": "butterfly",
    "wallabies": "wallaby",
    "octopuses": "octopus",
    "hippopotamuses": "hippopotamus",
    "rhinoceroses": "rhinoceros",
    "ostriches": "ostrich",
    "platypuses": "platypus",
    "walruses": "walrus",
}


def _reported_taxon_key(taxon: TaxonDefinition | None, term: str) -> str:
    if taxon is None:
        return "unknown_animal"
    if taxon.normalized_common_name not in COARSE_TAXON_NAMES:
        return taxon.normalized_common_name
    value = normalize_for_match(term)
    irregular = IRREGULAR_REPORTED_TAXA.get(value)
    if irregular is not None:
        return re.sub(r"[^a-z0-9]+", "_", irregular).strip("_")
    if value.endswith("ies") and len(value) > 4:
        value = value[:-3] + "y"
    elif value.endswith("s") and value not in {"rhinoceros"} and not value.endswith(("ss", "us")) and len(value) > 3:
        value = value[:-1]
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_") or taxon.normalized_common_name


def _dedupe_assertions(
    assertions: Iterable[AnimalAssertion], *, combine_roles: bool = False
) -> tuple[AnimalAssertion, ...]:
    chosen: dict[tuple[str, str, str], AnimalAssertion] = {}
    for assertion in assertions:
        key = _assertion_key(assertion, combine_roles=combine_roles)
        current = chosen.get(key)
        role_priority = {"reported_victim": 2, "possible_victim": 1}
        if current is None or (
            role_priority.get(assertion.incident_role, 0),
            assertion.identification_confidence,
            assertion.identification_basis,
            assertion.evidence_excerpt,
        ) > (
            role_priority.get(current.incident_role, 0),
            current.identification_confidence,
            current.identification_basis,
            current.evidence_excerpt,
        ):
            chosen[key] = assertion
    return tuple(
        sorted(
            chosen.values(),
            key=lambda item: _assertion_key(item, combine_roles=combine_roles),
        )
    )


def _make_assertion(
    taxon: TaxonDefinition | None,
    term: str,
    *,
    role: str,
    mode: str,
    sentence: str,
    evidence_spans: Sequence[tuple[int, int]] = (),
) -> AnimalAssertion:
    specific = taxon is not None
    if role == "reported_victim":
        confidence = 0.94 if mode == "explicit_mutilation" and specific else 0.84
    elif role == "possible_victim":
        confidence = 0.76 if specific else 0.64
    else:
        confidence = 0.75 if specific else 0.55
    return AnimalAssertion(
        reported_text=term,
        reported_taxon_key=_reported_taxon_key(taxon, term),
        normalized_common_name=taxon.normalized_common_name if taxon else "unknown_animal",
        species_group=taxon.species_group if taxon else "unknown",
        domestic_context=taxon.domestic_context if taxon else "unknown",
        incident_role=role,
        identification_basis=(
            "sentence_local_explicit_mutilation"
            if mode == "explicit_mutilation" and role in {"reported_victim", "possible_victim"}
            else "sentence_local_distinctive_injury"
            if mode == "distinctive_injury" and role in {"reported_victim", "possible_victim"}
            else "sentence_local_context"
        ),
        identification_confidence=confidence,
        evidence_excerpt=_localized_evidence_excerpt(
            sentence,
            evidence_spans,
            max_chars=320,
        ),
    )


def _analysis_units(text: str) -> list[str]:
    sentences = _sentences(text)
    units = list(sentences)
    for index in range(1, len(sentences)):
        current = normalize_for_match(sentences[index])
        previous = normalize_for_match(sentences[index - 1])
        current_has_injury = bool(
            _pattern_spans(current, MUTILATION_PATTERNS)
            or _pattern_spans(current, DISTINCTIVE_INJURY_PATTERNS)
        )
        current_has_animal = bool(_mentions(current))
        previous_has_animal = bool(_mentions(previous))
        anaphoric_injury = re.search(
            r"^(?:it|its|they|their|the\s+animal|the\s+carcass|the\s+deaths?)\b",
            current,
        )
        if (
            current_has_injury
            and previous_has_animal
            and (not current_has_animal or anaphoric_injury)
        ):
            units.append(f"{sentences[index - 1]} {sentences[index]}")
    return units


def _document_non_animal_terms(text: str) -> set[str]:
    """Return animal words explicitly introduced as mechanical objects."""

    normalized = normalize_for_match(text)
    return {
        match.group(1)
        for match in re.finditer(
            r"\b(?:robotic|mechanical)\s+"
            r"(slug|slugs|spider|spiders|insect|insects|beetle|beetles)\b",
            normalized,
        )
    }


def analyze_incident_animals(text: str) -> IncidentAnimalAnalysis:
    victims: list[AnimalAssertion] = []
    contexts: list[AnimalAssertion] = []
    all_labels: set[str] = set()
    evidence_modes: set[str] = set()
    evidence_terms: set[str] = set()
    evidence_sentences: set[str] = set()
    nonclassic_harm_only = False
    document_non_animal_terms = _document_non_animal_terms(text)

    for raw_sentence in _analysis_units(text):
        sentence = normalize_for_match(raw_sentence)
        mentions = [
            mention
            for mention in _mentions(sentence)
            if mention[1] not in document_non_animal_terms
        ]
        if not mentions:
            continue
        for taxon, _term, _start, _end in mentions:
            all_labels.add(taxon.normalized_common_name if taxon else "animal")

        mutilation_spans = _pattern_spans(sentence, MUTILATION_PATTERNS)
        negated_mutilation_spans = _pattern_spans(
            sentence, NEGATED_MUTILATION_PATTERNS
        )
        mutilation_spans = [
            span
            for span in mutilation_spans
            if not any(
                negative_start <= span[1] and span[2] <= negative_end
                for _negative, negative_start, negative_end in negated_mutilation_spans
            )
        ]
        injury_spans = _pattern_spans(sentence, DISTINCTIVE_INJURY_PATTERNS)
        negated_injury_spans = _pattern_spans(
            sentence, NEGATED_DISTINCTIVE_INJURY_PATTERNS
        )
        injury_spans = [
            span
            for span in injury_spans
            if not any(
                negative_start <= span[1] and span[2] <= negative_end
                for _negative, negative_start, negative_end in negated_injury_spans
            )
        ]
        injury_spans = [
            span
            for span in injury_spans
            if "removed obscenity" not in span[0]
            # Livestock counts use ``head`` as a unit: ``35 head of cattle
            # turned up missing`` describes missing animals, not missing
            # anatomy. A true anatomical phrase such as ``the cow's head was
            # missing`` does not contain this count-unit construction.
            and not re.search(
                r"\bhead(?:\s+of)?\s+(?:cattle|livestock|stock\s+animals?)\b",
                span[0],
            )
        ]
        ordinary_harm_spans = _pattern_spans(sentence, NONCLASSIC_HARM_PATTERNS)
        if not mutilation_spans and not injury_spans:
            if ordinary_harm_spans:
                nonclassic_harm_only = True
            for taxon, term, start, end in mentions:
                role = _context_role(sentence, taxon, term, start, end) or "context_only"
                contexts.append(
                    _make_assertion(
                        taxon,
                        term,
                        role=role,
                        mode="context",
                        sentence=raw_sentence,
                        evidence_spans=((start, end),),
                    )
                )
            continue

        mode = "explicit_mutilation" if mutilation_spans else "distinctive_injury"
        harm_spans = mutilation_spans or injury_spans
        evidence_modes.add(mode)
        evidence_terms.update(term for term, _start, _end in harm_spans)
        linked: list[tuple[TaxonDefinition | None, str, int, int, int]] = []
        for taxon, term, start, end in mentions:
            context_role = _context_role(sentence, taxon, term, start, end)
            if taxon is None and (
                GENERIC_BACKGROUND_PATTERN.search(sentence)
                or not _generic_has_actual_incident_link(
                    sentence,
                    term,
                    start,
                    end,
                    harm_spans,
                )
            ):
                context_role = "context_only"
            if context_role:
                contexts.append(
                    _make_assertion(
                        taxon,
                        term,
                        role=context_role,
                        mode="context",
                        sentence=raw_sentence,
                        evidence_spans=((start, end),),
                    )
                )
                continue
            distance = min(_span_distance((start, end), (harm_start, harm_end)) for _harm, harm_start, harm_end in harm_spans)
            if distance <= 120 or _has_passive_victim_link(sentence, term):
                linked.append((taxon, term, start, end, distance))
            else:
                contexts.append(
                    _make_assertion(
                        taxon,
                        term,
                        role="context_only",
                        mode="context",
                        sentence=raw_sentence,
                        evidence_spans=((start, end),),
                    )
                )

        specific_linked = [row for row in linked if row[0] is not None]
        selected = specific_linked or linked
        if not selected:
            continue

        # When prose names several animals but does not syntactically apply the
        # injury predicate to the full list, keep only the nearest mention(s).
        nearest = min(row[4] for row in selected)
        proximity_selected = [row for row in selected if row[4] <= nearest + 45]
        including_match = re.search(
            r"\bmutilat\w*\b.{0,120}\bincluding\b", sentence
        )
        if including_match:
            list_start = including_match.end()
            tail = sentence[list_start:]
            boundary = re.search(
                r"\b(?:while|whereas|although|but|when|as)\b|"
                r",\s+with\b|"
                r"\band\s+(?:an?\s+|the\s+)?(?:witness|person|rancher|farmer)\b|"
                r"\band\s+(?:an?\s+|the\s+)?[a-z0-9-]+\s+"
                r"(?:stood|remained|grazed|walked|waited|watched|rode)\b",
                tail,
            )
            list_end = list_start + (boundary.start() if boundary else len(tail))
            enumerated = [
                row
                for row in selected
                if list_start <= row[2] < list_end
            ]
            selected = sorted(
                {(*row[:4], row[4]): row for row in [*proximity_selected, *enumerated]}.values(),
                key=lambda row: (row[2], row[3], row[1]),
            )
        else:
            selected = proximity_selected
        occurrence = bool(_pattern_spans(sentence, OCCURRENCE_PATTERNS))
        for taxon, term, animal_start, animal_end, _distance in selected:
            passive_link = _has_passive_victim_link(sentence, term)
            role = (
                "reported_victim"
                if taxon is None
                or passive_link
                or occurrence
                or mode == "explicit_mutilation"
                else "possible_victim"
            )
            closest_harm = min(
                harm_spans,
                key=lambda span: (
                    _span_distance((animal_start, animal_end), (span[1], span[2])),
                    span[1],
                    span[2],
                    span[0],
                ),
            )
            evidence_spans = (
                (animal_start, animal_end),
                (closest_harm[1], closest_harm[2]),
            )
            assertion = _make_assertion(
                taxon,
                term,
                role=role,
                mode=mode,
                sentence=raw_sentence,
                evidence_spans=evidence_spans,
            )
            victims.append(assertion)
            evidence_sentences.add(
                _localized_evidence_excerpt(
                    raw_sentence,
                    evidence_spans,
                    max_chars=500,
                )
            )

    victim_rows = _dedupe_assertions(victims, combine_roles=True)
    victim_keys = {
        (row.normalized_common_name, row.reported_taxon_key)
        for row in victim_rows
    }
    context_rows = _dedupe_assertions(
        row
        for row in contexts
        if (row.normalized_common_name, row.reported_taxon_key) not in victim_keys
    )
    evidence_mode = (
        "explicit_mutilation"
        if "explicit_mutilation" in evidence_modes
        else "distinctive_injury"
        if "distinctive_injury" in evidence_modes
        else "nonclassic_harm_only"
        if nonclassic_harm_only
        else "none"
    )
    return IncidentAnimalAnalysis(
        victim_assertions=victim_rows,
        context_assertions=context_rows,
        all_animal_terms=tuple(sorted(all_labels)),
        evidence_mode=evidence_mode,
        evidence_terms=tuple(sorted(evidence_terms)),
        evidence_sentences=tuple(sorted(evidence_sentences)),
        nonclassic_harm_only=nonclassic_harm_only and not victim_rows,
    )


def assertion_to_public_row(assertion: AnimalAssertion, source_id: str) -> dict[str, object]:
    """Project one deterministic assertion into the public case contract."""

    return {
        "species": assertion.normalized_common_name,
        "reported_text": assertion.reported_text,
        "reported_taxon_key": assertion.reported_taxon_key,
        "normalized_common_name": assertion.normalized_common_name,
        "species_group": assertion.species_group,
        "domestic_context": assertion.domestic_context,
        "incident_role": assertion.incident_role,
        "identification_basis": assertion.identification_basis,
        "identification_confidence": assertion.identification_confidence,
        "source_ids": [source_id],
        "evidence_excerpt": assertion.evidence_excerpt,
        "breed": None,
        "sex": None,
        "age_class": None,
        "count": None,
        "condition_before_death": None,
        "ownership_public": None,
    }


def victim_labels(analysis: IncidentAnimalAnalysis) -> tuple[str, ...]:
    labels = [assertion.normalized_common_name for assertion in analysis.victim_assertions]
    return tuple(sorted("animal" if label == "unknown_animal" else label for label in labels))


def context_labels(analysis: IncidentAnimalAnalysis) -> tuple[str, ...]:
    return tuple(sorted(assertion.normalized_common_name for assertion in analysis.context_assertions))


def taxonomy_manifest() -> list[dict[str, object]]:
    return [
        {
            "normalized_common_name": taxon.normalized_common_name,
            "species_group": taxon.species_group,
            "domestic_context": taxon.domestic_context,
            "terms": list(taxon.terms),
        }
        for taxon in TAXA
    ]


def controlled_species_groups() -> tuple[str, ...]:
    return tuple(sorted({taxon.species_group for taxon in TAXA} | {"unknown"}))


def controlled_domestic_contexts() -> tuple[str, ...]:
    return tuple(sorted({taxon.domestic_context for taxon in TAXA} | {"unknown"}))


def has_any_animal_term(text: str) -> bool:
    normalized = normalize_for_match(text)
    return bool(_term_pattern(all_animal_terms()).search(normalized))


def terms_near(
    text: str,
    left_terms: Sequence[str],
    right_patterns: Sequence[str],
    max_chars: int,
) -> bool:
    normalized = normalize_for_match(text)
    left = [(match.start(), match.end()) for match in _term_pattern(tuple(left_terms)).finditer(normalized)]
    right = [(match.start(), match.end()) for match in _regex_union(tuple(right_patterns)).finditer(normalized)]
    return any(_span_distance(left_span, right_span) <= max_chars for left_span in left for right_span in right)
