"""Deterministic discovery of provisional building entities.

Discovery V1 extracts explicit development/building names from an explicitly
bounded listing sample, groups normalized variants, compares them with existing
``building_entities``, and emits proposals or abstentions. Dry-run is read-only;
explicit write mode creates only eligible entities and candidate relationships.
It is not connected to the scraper.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Callable, Iterable, Sequence


MAX_SAMPLE_SIZE = 50
MAX_ENTITY_COUNT = 500
CREATE_CANDIDATE_THRESHOLD = 0.85
REVIEW_THRESHOLD = 0.65
SIMILAR_ENTITY_THRESHOLD = 0.92
DISCOVERY_VERSION = "building_entity_discovery_v1"
AUTO_DISCOVERY_METHOD = "entity_discovery_v1_auto"
GRANULARITY_WARNING = (
    "Development/project-level evidence only; tower or block identity is not established."
)

PROPERTY_COLUMNS = (
    "source",
    "listing_id",
    "title",
    "description",
    "location",
    "standard_location",
    "agent_name",
)

KNOWN_NEIGHBORHOODS = {
    "garden estate",
    "gigiri",
    "karen",
    "kileleshwa",
    "kilimani",
    "kitisuru",
    "langata",
    "lavington",
    "nairobi",
    "parklands",
    "riverside",
    "ruaka",
    "runda",
    "south b",
    "south c",
    "spring valley",
    "upper hill",
    "westlands",
}

GENERIC_NAME_WORDS = {
    "a",
    "an",
    "and",
    "apartment",
    "apartments",
    "area",
    "at",
    "available",
    "bed",
    "bedroom",
    "bedrooms",
    "building",
    "development",
    "exclusive",
    "for",
    "furnished",
    "home",
    "homes",
    "house",
    "houses",
    "luxurious",
    "luxury",
    "major",
    "master",
    "guest",
    "modern",
    "new",
    "of",
    "premium",
    "prime",
    "property",
    "residential",
    "residence",
    "residences",
    "serviced",
    "spacious",
    "suite",
    "suites",
    "the",
    "this",
    "tower",
    "towers",
    "unfurnished",
    "unit",
    "units",
}

GENERIC_SECTION_WORDS = {
    "amenities",
    "amenity",
    "contact",
    "details",
    "facilities",
    "features",
    "highlights",
    "house",
    "inquiries",
    "key",
    "monthly",
    "price",
    "prices",
    "rent",
    "services",
    "unit",
    "units",
    "viewing",
}

LEADING_NAME_MODIFIERS = {
    "development",
    "exclusive",
    "modern",
    "premium",
    "residential",
    "spacious",
    "this",
}

ENTITY_TYPE_WORDS = {
    "apartment",
    "apartments",
    "building",
    "development",
    "residence",
    "residences",
    "tower",
    "towers",
}

ROAD_SUFFIXES = "Road|Street|Avenue|Lane|Drive|Crescent|Highway|Way"
LANDMARK_SUFFIXES = "Mall|Centre|Center|Hospital|School|University"
NAME_TOKEN = r"(?:[A-Z][A-Za-z0-9'’.-]*|[0-9]+|@|&)"
NAME_PHRASE = rf"{NAME_TOKEN}(?:\s+{NAME_TOKEN}){{0,4}}"
NAME_END = r"(?=\s+(?:on|along|near|off|for|from|with|within|and|is|offers?|featuring)\b|[,.;:!?\n]|$)"

CONTEXT_NAME_PATTERN = re.compile(
    rf"\b(?P<prefix>[Ll]ocated\s+(?:at|in)|[Aa]t|[Ii]n|[Ww]ithin)\s+(?:the\s+)?"
    rf"(?P<name>{NAME_PHRASE}){NAME_END}"
)
NAMED_PATTERN = re.compile(
    rf"\b(?:[Dd]evelopment|[Pp]roject|[Bb]uilding)\s+(?:named|called)\s+"
    rf"(?P<name>{NAME_PHRASE}){NAME_END}"
)
TYPED_NAME_PATTERN = re.compile(
    rf"\b(?P<name>{NAME_TOKEN}(?:\s+{NAME_TOKEN}){{0,3}}\s+"
    r"(?:Residences?|Towers?|Heights|Court|Gardens|Villas|Suites|Plaza|Apartments|Development))\b"
)
NAME_IS_PATTERN = re.compile(
    rf"\b(?P<name>{NAME_TOKEN}(?:\s+{NAME_TOKEN}){{1,4}})\s+is\s+(?:the|a|an)\b"
)
ROAD_PATTERN = re.compile(
    rf"\b(?P<road>[A-Z][A-Za-z'’-]*(?:[ \t]+[A-Z][A-Za-z'’-]*){{0,2}}"
    rf"[ \t]+(?:{ROAD_SUFFIXES}))\b"
)
LANDMARK_PATTERN = re.compile(
    rf"\b(?P<landmark>[A-Z][A-Za-z'’-]*(?:[ \t]+[A-Z][A-Za-z'’-]*){{0,2}}"
    rf"[ \t]+(?:{LANDMARK_SUFFIXES}))\b"
)

SIGNAL_STRENGTHS = {
    "named_development": 0.75,
    "title_context_name": 0.70,
    "heading_name": 0.70,
    "description_context_name": 0.65,
    "typed_building_name": 0.55,
    "name_statement": 0.55,
}


@dataclass(frozen=True)
class DiscoveryListing:
    apartment_id: int
    source: str
    listing_id: int
    title: str = ""
    description: str = ""
    location: str | None = None
    standard_location: str | None = None
    agent_name: str | None = None


@dataclass(frozen=True)
class ExistingEntity:
    id: int
    building_code: str
    canonical_name: str | None = None
    normalized_name: str | None = None
    location: str | None = None
    standard_location: str | None = None
    address_text: str | None = None


@dataclass(frozen=True)
class CandidateSignal:
    source: str
    listing_id: int
    apartment_id: int
    candidate_name: str
    normalized_name: str
    signal_type: str
    strength: float
    snippet: str
    source_location: str | None
    standard_location: str | None
    agent_name: str | None
    road_evidence: tuple[str, ...]
    landmark_evidence: tuple[str, ...]


@dataclass(frozen=True)
class ListingAbstention:
    source: str
    listing_id: int
    apartment_id: int
    reason: str
    rejected_candidates: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class DiscoveryProposal:
    proposed_canonical_name: str
    normalized_name: str
    listing_ids: tuple[int, ...]
    apartment_ids: tuple[int, ...]
    source_locations: tuple[str, ...]
    address_road_evidence: tuple[str, ...]
    text_signals: tuple[dict[str, Any], ...]
    independent_listing_count: int
    agents_involved: tuple[str, ...]
    confidence: float
    granularity_warning: str
    similar_entity_already_exists: bool
    similar_entity: dict[str, Any] | None
    proposed_action: str
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_candidate_name(value: Any) -> str:
    """Normalize punctuation/case variants without erasing meaningful @ text."""

    if value is None:
        return ""
    text = str(value).replace("@", " at ").replace("&", " and ")
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    normalized = " ".join(re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).split())
    if normalized.startswith("the "):
        normalized = normalized[4:]
    return normalized


def _canonicalize_name(value: str) -> str:
    cleaned = " ".join(value.strip(" \t\r\n-–—,.;:!?").split())
    if cleaned.lower().startswith("the "):
        cleaned = cleaned[4:]
    tokens = cleaned.split()
    while len(tokens) > 2 and normalize_candidate_name(tokens[0]) in LEADING_NAME_MODIFIERS:
        tokens.pop(0)
    cleaned = " ".join(tokens)
    if cleaned.isupper() or cleaned.islower():
        return cleaned.title()
    return cleaned


def _listing_locations(listing: DiscoveryListing) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            value.strip()
            for value in (listing.location, listing.standard_location)
            if value and value.strip()
        )
    )


def _exact_snippet(text: str, start: int, end: int, radius: int = 90) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return " ".join(text[left:right].strip().split())


def _context_phrases(text: str, pattern: re.Pattern[str], group: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(match.group(group).strip() for match in pattern.finditer(text or "")))


def _road_evidence(listing: DiscoveryListing) -> tuple[str, ...]:
    text = f"{listing.title}\n{listing.description}"
    return _context_phrases(text, ROAD_PATTERN, "road")


def _landmark_evidence(listing: DiscoveryListing) -> tuple[str, ...]:
    text = f"{listing.title}\n{listing.description}"
    return _context_phrases(text, LANDMARK_PATTERN, "landmark")


def candidate_rejection_reason(name: str, listing: DiscoveryListing) -> str | None:
    normalized = normalize_candidate_name(name)
    tokens = normalized.split()
    if normalized in KNOWN_NEIGHBORHOODS:
        return "candidate is a generic neighborhood/location"
    if not normalized or len(tokens) < 2:
        return "candidate is not a distinctive multi-token name"
    listing_location_values = {
        normalize_candidate_name(value) for value in _listing_locations(listing)
    }
    if normalized in listing_location_values:
        return "candidate repeats the listing location rather than a building name"
    if re.search(rf"\b(?:{ROAD_SUFFIXES})$", name, flags=re.IGNORECASE):
        return "candidate is a road/address, not a building name"
    if any(token in {"bed", "bedroom", "bedrooms", "ksh", "kes", "rent", "sale"} for token in tokens):
        return "candidate contains listing/price language"
    informative = [token for token in tokens if token not in GENERIC_NAME_WORDS]
    if not informative:
        return "candidate is only a generic marketing/property phrase"
    if all(token in GENERIC_NAME_WORDS | GENERIC_SECTION_WORDS for token in tokens):
        return "candidate is a generic listing section or marketing phrase"
    if len(informative) == 1 and all(token in GENERIC_NAME_WORDS for token in tokens if token != informative[0]):
        if informative[0] in {"beautiful", "executive", "stunning", "elegant"}:
            return "candidate is a weak generic marketing phrase"
    return None


def _heading_candidates(description: str) -> Iterable[tuple[str, int, int]]:
    offset = 0
    for line in description.splitlines(keepends=True):
        raw = line.strip()
        cleaned = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9@&'’. -]+$", "", raw).strip()
        words = cleaned.split()
        letters = [character for character in cleaned if character.isalpha()]
        uppercase_ratio = (
            sum(character.isupper() for character in letters) / len(letters)
            if letters
            else 0.0
        )
        if 2 <= len(words) <= 5 and uppercase_ratio >= 0.80 and not re.search(r"[:.!?]", cleaned):
            start = description.find(cleaned, offset)
            if start >= 0:
                yield cleaned, start, start + len(cleaned)
        offset += len(line)


def extract_candidate_signals(
    listing: DiscoveryListing,
) -> tuple[list[CandidateSignal], list[dict[str, str]]]:
    """Extract accepted name signals and retain rejected evidence for abstentions."""

    roads = _road_evidence(listing)
    landmarks = _landmark_evidence(listing)
    accepted: list[CandidateSignal] = []
    rejected: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    def consider(raw_name: str, signal_type: str, text: str, start: int, end: int) -> None:
        canonical_name = _canonicalize_name(raw_name)
        normalized_name = normalize_candidate_name(canonical_name)
        snippet = _exact_snippet(text, start, end)
        rejection = candidate_rejection_reason(canonical_name, listing)
        if rejection:
            item = {"candidate": canonical_name, "reason": rejection, "snippet": snippet}
            if item not in rejected:
                rejected.append(item)
            return
        key = (normalized_name, signal_type, snippet)
        if key in seen:
            return
        seen.add(key)
        accepted.append(
            CandidateSignal(
                source=listing.source,
                listing_id=listing.listing_id,
                apartment_id=listing.apartment_id,
                candidate_name=canonical_name,
                normalized_name=normalized_name,
                signal_type=signal_type,
                strength=SIGNAL_STRENGTHS[signal_type],
                snippet=snippet,
                source_location=listing.location,
                standard_location=listing.standard_location,
                agent_name=listing.agent_name,
                road_evidence=roads,
                landmark_evidence=landmarks,
            )
        )

    for match in CONTEXT_NAME_PATTERN.finditer(listing.title):
        consider(match.group("name"), "title_context_name", listing.title, *match.span("name"))
    for match in CONTEXT_NAME_PATTERN.finditer(listing.description):
        consider(
            match.group("name"),
            "description_context_name",
            listing.description,
            *match.span("name"),
        )
    for text in (listing.title, listing.description):
        for match in NAMED_PATTERN.finditer(text):
            consider(match.group("name"), "named_development", text, *match.span("name"))
        for match in TYPED_NAME_PATTERN.finditer(text):
            consider(match.group("name"), "typed_building_name", text, *match.span("name"))
        for match in NAME_IS_PATTERN.finditer(text):
            consider(match.group("name"), "name_statement", text, *match.span("name"))
    for name, start, end in _heading_candidates(listing.description):
        consider(name, "heading_name", listing.description, start, end)

    return accepted, rejected


def _location_values_from_signals(signals: Sequence[CandidateSignal]) -> tuple[str, ...]:
    values: list[str] = []
    for signal in signals:
        for value in (signal.source_location, signal.standard_location):
            if value and value.strip() and value.strip() not in values:
                values.append(value.strip())
    return tuple(values)


def _locations_conflict(values: Sequence[str]) -> bool:
    normalized = [normalize_candidate_name(value) for value in values if value]
    for index, left in enumerate(normalized):
        for right in normalized[index + 1 :]:
            if left == right or left in right or right in left:
                continue
            return True
    return False


def _entity_name(entity: ExistingEntity) -> str:
    return normalize_candidate_name(entity.normalized_name or entity.canonical_name)


def _identity_core(normalized_name: str) -> str:
    tokens = normalized_name.split()
    while len(tokens) > 1 and tokens[-1] in ENTITY_TYPE_WORDS:
        tokens.pop()
    return " ".join(tokens)


def _find_similar_entity(
    normalized_name: str,
    entities: Sequence[ExistingEntity],
) -> tuple[ExistingEntity | None, float]:
    best_entity: ExistingEntity | None = None
    best_similarity = 0.0
    for entity in entities:
        entity_name = _entity_name(entity)
        if not entity_name:
            continue
        if normalized_name == entity_name:
            similarity = 1.0
        elif _identity_core(normalized_name) == _identity_core(entity_name):
            similarity = 0.99
        else:
            similarity = SequenceMatcher(None, normalized_name, entity_name).ratio()
        if similarity > best_similarity:
            best_entity = entity
            best_similarity = similarity
    if best_similarity < SIMILAR_ENTITY_THRESHOLD:
        return None, best_similarity
    return best_entity, best_similarity


def _score_group(signals: Sequence[CandidateSignal]) -> float:
    independent_listings = len({(signal.source, signal.listing_id) for signal in signals})
    locations = _location_values_from_signals(signals)
    roads = {road for signal in signals for road in signal.road_evidence}
    landmarks = {landmark for signal in signals for landmark in signal.landmark_evidence}
    agents = {signal.agent_name for signal in signals if signal.agent_name}
    signal_types = {signal.signal_type for signal in signals}

    score = max(signal.strength for signal in signals)
    if locations:
        score += 0.15
    if roads:
        score += 0.15
    if landmarks:
        score += 0.05
    if independent_listings == 2:
        score += 0.15
    elif independent_listings >= 3:
        score += 0.20
    if len(agents) >= 2:
        score += 0.05
    if "title_context_name" in signal_types and any(
        signal_type in signal_types
        for signal_type in ("description_context_name", "heading_name", "name_statement")
    ):
        score += 0.05
    if _locations_conflict(locations):
        score = min(score - 0.30, REVIEW_THRESHOLD + 0.04)
    return round(max(0.0, min(1.0, score)), 4)


def _creation_evidence_bands(
    normalized_name: str,
    signals: Sequence[CandidateSignal],
    confidence: float,
) -> tuple[bool, bool]:
    """Reproduce the conservative single- and multi-listing creation rules."""

    if not signals:
        return False, False
    independent_count = len(
        {(signal.source, signal.listing_id) for signal in signals}
    )
    signal_types = {signal.signal_type for signal in signals}
    strongest = max(signal.strength for signal in signals)
    has_context = bool(
        _location_values_from_signals(signals)
        or any(signal.road_evidence for signal in signals)
        or any(signal.landmark_evidence for signal in signals)
    )
    has_non_title_name_evidence = bool(
        signal_types
        & {
            "named_development",
            "heading_name",
            "description_context_name",
            "typed_building_name",
            "name_statement",
        }
    )
    structurally_distinctive_title = bool(
        re.search(r"\d", normalized_name) and " at " in f" {normalized_name} "
    )
    strong_single = (
        independent_count == 1
        and strongest >= SIGNAL_STRENGTHS["description_context_name"]
        and has_context
        and (has_non_title_name_evidence or structurally_distinctive_title)
        and confidence >= CREATE_CANDIDATE_THRESHOLD
    )
    strong_multi = (
        independent_count >= 2
        and (has_non_title_name_evidence or structurally_distinctive_title)
        and confidence >= CREATE_CANDIDATE_THRESHOLD
    )
    return strong_single, strong_multi


def _canonical_name_for_group(signals: Sequence[CandidateSignal]) -> str:
    ranked = sorted(
        signals,
        key=lambda signal: (-signal.strength, len(signal.candidate_name), signal.candidate_name),
    )
    return ranked[0].candidate_name


def build_discovery_proposals(
    listings: Sequence[DiscoveryListing],
    existing_entities: Sequence[ExistingEntity],
) -> tuple[list[DiscoveryProposal], list[ListingAbstention]]:
    """Produce grouped discovery proposals without changing database state."""

    grouped: dict[str, list[CandidateSignal]] = {}
    abstentions: list[ListingAbstention] = []
    for listing in listings:
        accepted, rejected = extract_candidate_signals(listing)
        if not accepted:
            abstentions.append(
                ListingAbstention(
                    source=listing.source,
                    listing_id=listing.listing_id,
                    apartment_id=listing.apartment_id,
                    reason="No sufficiently distinctive explicit building/development name was found.",
                    rejected_candidates=tuple(rejected),
                )
            )
        for signal in accepted:
            grouped.setdefault(signal.normalized_name, []).append(signal)

    proposals: list[DiscoveryProposal] = []
    for normalized_name, signals in sorted(grouped.items()):
        canonical_name = _canonical_name_for_group(signals)
        listing_ids = tuple(sorted({signal.listing_id for signal in signals}))
        apartment_ids = tuple(sorted({signal.apartment_id for signal in signals}))
        locations = _location_values_from_signals(signals)
        roads = tuple(sorted({road for signal in signals for road in signal.road_evidence}))
        agents = tuple(sorted({signal.agent_name for signal in signals if signal.agent_name}))
        confidence = _score_group(signals)
        independent_count = len({(signal.source, signal.listing_id) for signal in signals})
        location_conflict = _locations_conflict(locations)
        similar_entity, similarity = _find_similar_entity(normalized_name, existing_entities)

        similar_entity_data = None
        entity_context_conflict = False
        if similar_entity:
            entity_locations = tuple(
                value
                for value in (similar_entity.location, similar_entity.standard_location)
                if value
            )
            entity_context_conflict = _locations_conflict((*locations, *entity_locations))
            similar_entity_data = {
                "id": similar_entity.id,
                "building_code": similar_entity.building_code,
                "canonical_name": similar_entity.canonical_name,
                "normalized_name": similar_entity.normalized_name,
                "similarity": round(similarity, 4),
                "location_context_conflict": entity_context_conflict,
            }

        strong_single, strong_multi = _creation_evidence_bands(
            normalized_name,
            signals,
            confidence,
        )

        if similar_entity and not entity_context_conflict:
            action = "existing_entity"
            explanation = (
                f"Normalized/similar name already matches {similar_entity.building_code}; "
                "no duplicate entity should be created."
            )
        elif location_conflict or entity_context_conflict:
            action = "review"
            explanation = "Conflicting location context prevents an automatic merge or creation proposal."
        elif strong_single:
            action = "create_candidate"
            explanation = "Very strong explicit single-listing name evidence is corroborated by location/address context."
        elif strong_multi:
            action = "create_candidate"
            explanation = "The same normalized name occurs independently across compatible listings."
        elif confidence >= REVIEW_THRESHOLD:
            action = "review"
            explanation = "A plausible name was found, but evidence does not meet the conservative creation threshold."
        else:
            action = "abstain"
            explanation = "Candidate evidence is too weak for safe entity creation."

        text_signals = tuple(
            {
                "source": signal.source,
                "listing_id": signal.listing_id,
                "apartment_id": signal.apartment_id,
                "signal_type": signal.signal_type,
                "strength": signal.strength,
                "snippet": signal.snippet,
                "landmark_evidence": list(signal.landmark_evidence),
            }
            for signal in sorted(
                signals,
                key=lambda item: (item.listing_id, -item.strength, item.signal_type, item.snippet),
            )
        )
        proposals.append(
            DiscoveryProposal(
                proposed_canonical_name=canonical_name,
                normalized_name=normalized_name,
                listing_ids=listing_ids,
                apartment_ids=apartment_ids,
                source_locations=locations,
                address_road_evidence=roads,
                text_signals=text_signals,
                independent_listing_count=independent_count,
                agents_involved=agents,
                confidence=confidence,
                granularity_warning=GRANULARITY_WARNING,
                similar_entity_already_exists=similar_entity is not None,
                similar_entity=similar_entity_data,
                proposed_action=action,
                explanation=explanation,
            )
        )

    return proposals, abstentions


def _response_data(response: Any) -> list[dict[str, Any]]:
    return list(response.data or [])


def _listings_from_rows(rows: Sequence[dict[str, Any]]) -> list[DiscoveryListing]:
    return [
        DiscoveryListing(
            apartment_id=int(row["apartment_id"]),
            source=str(row["source"]),
            listing_id=int(row["listing_id"]),
            title=row.get("title") or "",
            description=row.get("description") or "",
            location=row.get("location"),
            standard_location=row.get("standard_location"),
            agent_name=row.get("agent_name"),
        )
        for row in rows
    ]


def _entities_from_rows(rows: Sequence[dict[str, Any]]) -> list[ExistingEntity]:
    return [
        ExistingEntity(
            id=int(row["id"]),
            building_code=str(row["building_code"]),
            canonical_name=row.get("canonical_name"),
            normalized_name=row.get("normalized_name"),
            location=row.get("location"),
            standard_location=row.get("standard_location"),
            address_text=row.get("address_text"),
        )
        for row in rows
    ]


def fetch_existing_entities(client: Any) -> list[ExistingEntity]:
    """Read the current entity identity set for duplicate re-checks."""

    rows = _response_data(
        client.table("building_entities")
        .select(
            "id,building_code,canonical_name,normalized_name,location,"
            "standard_location,address_text"
        )
        .order("id")
        .limit(MAX_ENTITY_COUNT + 1)
        .execute()
    )
    if len(rows) > MAX_ENTITY_COUNT:
        raise RuntimeError(f"Entity count exceeds the V1 safety limit of {MAX_ENTITY_COUNT}.")
    return _entities_from_rows(rows)


def fetch_discovery_inputs(
    client: Any,
    listing_ids: Sequence[int],
    source: str = "BuyRentKenya",
) -> tuple[list[DiscoveryListing], list[ExistingEntity]]:
    """Read an explicit bounded sample and current entity names from Supabase."""

    requested_ids = sorted({int(listing_id) for listing_id in listing_ids})
    if not requested_ids:
        raise ValueError("At least one listing id is required.")
    if len(requested_ids) > MAX_SAMPLE_SIZE:
        raise ValueError(f"Discovery samples are limited to {MAX_SAMPLE_SIZE} listings.")

    mappings = _response_data(
        client.table("apartment_listings")
        .select("apartment_id,source,listing_id")
        .eq("source", source)
        .in_("listing_id", requested_ids)
        .execute()
    )
    mapping_by_id = {int(row["listing_id"]): int(row["apartment_id"]) for row in mappings}
    missing_mappings = [listing_id for listing_id in requested_ids if listing_id not in mapping_by_id]
    if missing_mappings:
        raise ValueError(f"Listings do not have apartment mappings: {missing_mappings}")

    property_rows = _response_data(
        client.table("properties")
        .select(",".join(PROPERTY_COLUMNS))
        .eq("source", source)
        .in_("listing_id", requested_ids)
        .execute()
    )
    properties_by_id = {int(row["listing_id"]): row for row in property_rows}
    missing_properties = [listing_id for listing_id in requested_ids if listing_id not in properties_by_id]
    if missing_properties:
        raise ValueError(f"Listings do not have property rows: {missing_properties}")
    listing_rows = [
        {**properties_by_id[listing_id], "apartment_id": mapping_by_id[listing_id]}
        for listing_id in requested_ids
    ]

    return _listings_from_rows(listing_rows), fetch_existing_entities(client)


def creation_ineligibility(proposal: DiscoveryProposal) -> str | None:
    """Return why a proposal cannot be auto-created, or None when eligible."""

    if proposal.proposed_action != "create_candidate":
        return proposal.proposed_action
    if proposal.confidence < CREATE_CANDIDATE_THRESHOLD:
        return "below_creation_threshold"
    if proposal.similar_entity_already_exists:
        return "similar_entity_exists"
    if _locations_conflict(proposal.source_locations):
        return "conflicting_location"
    return None


def _consistent_value(values: Iterable[str | None]) -> str | None:
    nonempty = [value.strip() for value in values if value and value.strip()]
    normalized = {normalize_candidate_name(value) for value in nonempty}
    if len(normalized) != 1:
        return None
    return nonempty[0]


def _proposal_signals(
    proposal: DiscoveryProposal,
    listings: Sequence[DiscoveryListing],
) -> list[CandidateSignal]:
    signals: list[CandidateSignal] = []
    for listing in listings:
        accepted, _ = extract_candidate_signals(listing)
        signals.extend(
            signal
            for signal in accepted
            if signal.normalized_name == proposal.normalized_name
        )
    return signals


def build_entity_insert_row(
    proposal: DiscoveryProposal,
    listings: Sequence[DiscoveryListing],
    observed_at: datetime,
) -> dict[str, Any]:
    """Build the supported provisional-entity fields for an eligible proposal."""

    reason = creation_ineligibility(proposal)
    if reason is not None:
        raise ValueError(f"Proposal is not eligible for automated creation: {reason}")

    signals = _proposal_signals(proposal, listings)
    if not signals:
        raise ValueError("Eligible proposal has no supporting listing signals.")
    if not any(
        _creation_evidence_bands(
            proposal.normalized_name,
            signals,
            proposal.confidence,
        )
    ):
        raise ValueError("Proposal does not reproduce the creation evidence rules.")
    standard_location = _consistent_value(signal.standard_location for signal in signals)
    location = (
        _consistent_value(signal.source_location for signal in signals)
        or standard_location
    )
    roads = sorted({road for signal in signals for road in signal.road_evidence})
    timestamp = observed_at.astimezone(timezone.utc).isoformat()
    row: dict[str, Any] = {
        "canonical_name": proposal.proposed_canonical_name,
        "normalized_name": proposal.normalized_name,
        "first_seen_at": timestamp,
        "last_seen_at": timestamp,
        "canonical_building_id": None,
    }
    if location:
        row["location"] = location
    if standard_location:
        row["standard_location"] = standard_location
    if roads:
        row["address_text"] = "; ".join(roads)
    return row


def _eligible_relationship_rows(
    proposal: DiscoveryProposal,
    listings: Sequence[DiscoveryListing],
    entity: ExistingEntity,
) -> list[dict[str, Any]]:
    signals = _proposal_signals(proposal, listings)
    by_apartment: dict[int, list[CandidateSignal]] = {}
    for signal in signals:
        by_apartment.setdefault(signal.apartment_id, []).append(signal)

    rows: list[dict[str, Any]] = []
    for apartment_id, apartment_signals in sorted(by_apartment.items()):
        individual_confidence = _score_group(apartment_signals)
        has_context = bool(
            _location_values_from_signals(apartment_signals)
            or any(signal.road_evidence for signal in apartment_signals)
            or any(signal.landmark_evidence for signal in apartment_signals)
        )
        if individual_confidence < REVIEW_THRESHOLD or not has_context:
            continue

        listing_ids = sorted({signal.listing_id for signal in apartment_signals})
        sources = sorted({signal.source for signal in apartment_signals})
        rows.append(
            {
                "apartment_id": apartment_id,
                "building_entity_id": entity.id,
                "match_status": "candidate",
                "match_confidence": individual_confidence,
                "match_method": AUTO_DISCOVERY_METHOD,
                "evidence": {
                    "discovery": {
                        "version": DISCOVERY_VERSION,
                        "method": AUTO_DISCOVERY_METHOD,
                        "proposal_action": proposal.proposed_action,
                        "proposal_confidence": proposal.confidence,
                        "individual_confidence": individual_confidence,
                    },
                    "source": sources[0] if len(sources) == 1 else sources,
                    "listing_ids": listing_ids,
                    "apartment_id": apartment_id,
                    "entity": {
                        "id": entity.id,
                        "code": entity.building_code,
                        "canonical_name": entity.canonical_name,
                        "normalized_name": entity.normalized_name,
                    },
                    "matched_identity_signals": [
                        {
                            "listing_id": signal.listing_id,
                            "signal_type": signal.signal_type,
                            "strength": signal.strength,
                            "snippet": signal.snippet,
                        }
                        for signal in apartment_signals
                    ],
                    "location_context": list(
                        _location_values_from_signals(apartment_signals)
                    ),
                    "address_road_evidence": sorted(
                        {
                            road
                            for signal in apartment_signals
                            for road in signal.road_evidence
                        }
                    ),
                    "landmark_evidence": sorted(
                        {
                            landmark
                            for signal in apartment_signals
                            for landmark in signal.landmark_evidence
                        }
                    ),
                    "agent_names": sorted(
                        {
                            signal.agent_name
                            for signal in apartment_signals
                            if signal.agent_name
                        }
                    ),
                    "conflicts": [],
                    "granularity_warning": proposal.granularity_warning,
                    "automatically_confirmed": False,
                },
            }
        )
    return rows


def _entity_from_inserted_row(row: dict[str, Any]) -> ExistingEntity:
    return _entities_from_rows([row])[0]


def _entity_location_conflicts(
    proposal: DiscoveryProposal,
    entity: ExistingEntity,
) -> bool:
    entity_locations = tuple(
        value for value in (entity.location, entity.standard_location) if value
    )
    return _locations_conflict((*proposal.source_locations, *entity_locations))


def write_discovery_candidates(
    client: Any,
    proposals: Sequence[DiscoveryProposal],
    listings: Sequence[DiscoveryListing],
    *,
    existing_entity_loader: Callable[[Any], list[ExistingEntity]] = fetch_existing_entities,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Create eligible provisional entities and their candidate relationships.

    Existing entities are re-read immediately before each insert. Relationship
    upserts ignore only the unique apartment/entity duplicate; other database
    errors propagate to the caller.
    """

    now = observed_at or datetime.now(timezone.utc)
    created_entities: list[dict[str, Any]] = []
    resolved_existing_entities: list[dict[str, Any]] = []
    inserted_relationships: list[dict[str, Any]] = []
    existing_relationships_skipped: list[dict[str, Any]] = []
    ineligible_skipped: list[dict[str, Any]] = []

    for proposal in proposals:
        reason = creation_ineligibility(proposal)
        if reason is not None:
            ineligible_skipped.append(
                {"reason": reason, "proposal": proposal.to_dict()}
            )
            continue

        proposal_signals = _proposal_signals(proposal, listings)
        if not any(
            _creation_evidence_bands(
                proposal.normalized_name,
                proposal_signals,
                proposal.confidence,
            )
        ):
            ineligible_skipped.append(
                {
                    "reason": "creation_evidence_not_reproduced",
                    "proposal": proposal.to_dict(),
                }
            )
            continue

        current_entities = existing_entity_loader(client)
        existing, similarity = _find_similar_entity(
            proposal.normalized_name, current_entities
        )
        entity: ExistingEntity
        if existing is not None:
            if _entity_location_conflicts(proposal, existing):
                ineligible_skipped.append(
                    {
                        "reason": "rechecked_similar_entity_location_conflict",
                        "proposal": proposal.to_dict(),
                        "entity": asdict(existing),
                    }
                )
                continue
            entity = existing
            resolved_existing_entities.append(
                {
                    "proposal": proposal.to_dict(),
                    "entity": asdict(existing),
                    "similarity": round(similarity, 4),
                    "resolution": "pre_insert_recheck",
                }
            )
        else:
            entity_row = build_entity_insert_row(proposal, listings, now)
            try:
                response = (
                    client.table("building_entities")
                    .insert(entity_row)
                    .select(
                        "id,building_code,canonical_name,normalized_name,location,"
                        "standard_location,address_text"
                    )
                    .execute()
                )
                persisted = _response_data(response)
                if len(persisted) != 1:
                    raise RuntimeError(
                        "Building entity insert did not return exactly one persisted row."
                    )
                entity = _entity_from_inserted_row(persisted[0])
                created_entities.append(asdict(entity))
            except Exception:
                refreshed_entities = existing_entity_loader(client)
                concurrent, concurrent_similarity = _find_similar_entity(
                    proposal.normalized_name, refreshed_entities
                )
                if concurrent is None:
                    raise
                if _entity_location_conflicts(proposal, concurrent):
                    raise RuntimeError(
                        "A similar entity appeared during insertion with conflicting "
                        "location context; relationships were not written."
                    )
                entity = concurrent
                resolved_existing_entities.append(
                    {
                        "proposal": proposal.to_dict(),
                        "entity": asdict(concurrent),
                        "similarity": round(concurrent_similarity, 4),
                        "resolution": "post_insert_error_recheck",
                    }
                )

        relationship_rows = _eligible_relationship_rows(proposal, listings, entity)
        if not relationship_rows:
            raise RuntimeError(
                f"Eligible entity {entity.building_code} has no individually eligible relationships."
            )
        response = (
            client.table("apartment_building_entities")
            .upsert(
                relationship_rows,
                on_conflict="apartment_id,building_entity_id",
                ignore_duplicates=True,
            )
            .execute()
        )
        persisted_relationships = _response_data(response)
        inserted_relationships.extend(persisted_relationships)
        persisted_pairs = {
            (int(row["apartment_id"]), int(row["building_entity_id"]))
            for row in persisted_relationships
        }
        existing_relationships_skipped.extend(
            row
            for row in relationship_rows
            if (int(row["apartment_id"]), int(row["building_entity_id"]))
            not in persisted_pairs
        )

    return {
        "created_entities": created_entities,
        "created_entity_count": len(created_entities),
        "resolved_existing_entities": resolved_existing_entities,
        "resolved_existing_entity_count": len(resolved_existing_entities),
        "inserted_relationships": inserted_relationships,
        "inserted_relationship_count": len(inserted_relationships),
        "existing_relationships_skipped": existing_relationships_skipped,
        "existing_relationships_skipped_count": len(existing_relationships_skipped),
        "ineligible_skipped": ineligible_skipped,
        "ineligible_skipped_count": len(ineligible_skipped),
    }


def _load_client() -> Any:
    from supabase import create_client

    from config import SUPABASE_KEY, SUPABASE_URL

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def _load_json_bundle(path: str) -> tuple[list[DiscoveryListing], list[ExistingEntity]]:
    if path == "-":
        raw = sys.stdin.readline()
    else:
        with open(path, encoding="utf-8") as handle:
            raw = handle.read()
    bundle = json.loads(raw)
    return (
        _listings_from_rows(bundle.get("listings") or []),
        _entities_from_rows(bundle.get("existing_entities") or []),
    )


def _load_base64_stdin_bundle() -> tuple[list[DiscoveryListing], list[ExistingEntity]]:
    chunks: list[str] = []
    for line in sys.stdin:
        stripped = line.strip()
        if stripped == "LOCATIONOS_JSON_END":
            break
        if stripped:
            chunks.append(stripped)
    raw = base64.b64decode("".join(chunks), validate=True).decode("utf-8")
    bundle = json.loads(raw)
    return (
        _listings_from_rows(bundle.get("listings") or []),
        _entities_from_rows(bundle.get("existing_entities") or []),
    )


def build_report(
    listings: Sequence[DiscoveryListing],
    existing_entities: Sequence[ExistingEntity],
    mode: str = "dry_run",
) -> dict[str, Any]:
    proposals, abstentions = build_discovery_proposals(listings, existing_entities)
    action_counts = {
        action: sum(proposal.proposed_action == action for proposal in proposals)
        for action in ("create_candidate", "existing_entity", "review", "abstain")
    }
    return {
        "mode": mode,
        "writes_performed": False,
        "thresholds": {
            "create_candidate": CREATE_CANDIDATE_THRESHOLD,
            "review": REVIEW_THRESHOLD,
            "similar_entity": SIMILAR_ENTITY_THRESHOLD,
        },
        "summary": {
            "listings_evaluated": len(listings),
            "candidate_groups": len(proposals),
            "listing_abstentions": len(abstentions),
            **action_counts,
        },
        "proposals": [proposal.to_dict() for proposal in proposals],
        "abstentions": [asdict(abstention) for abstention in abstentions],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Building Entity Discovery V1 workflow")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Evaluate and report without writes")
    mode.add_argument(
        "--write",
        action="store_true",
        help="Create only eligible provisional entities and candidate relationships",
    )
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument(
        "--listing-id",
        type=int,
        action="append",
        help="Explicit listing id; repeat for a bounded sample",
    )
    inputs.add_argument(
        "--input-json",
        help="Local JSON bundle path, or '-' for one JSON line on stdin",
    )
    inputs.add_argument(
        "--input-json-base64-stdin",
        action="store_true",
        help="Read chunked base64 JSON from stdin until LOCATIONOS_JSON_END",
    )
    parser.add_argument("--source", default="BuyRentKenya")
    args = parser.parse_args(argv)

    if args.write and (args.input_json or args.input_json_base64_stdin):
        parser.error("--write requires explicit --listing-id values and a fresh database read")

    client = None
    if args.input_json_base64_stdin:
        listings, entities = _load_base64_stdin_bundle()
        if len(listings) > MAX_SAMPLE_SIZE:
            raise ValueError(f"Discovery samples are limited to {MAX_SAMPLE_SIZE} listings.")
    elif args.input_json:
        listings, entities = _load_json_bundle(args.input_json)
        if len(listings) > MAX_SAMPLE_SIZE:
            raise ValueError(f"Discovery samples are limited to {MAX_SAMPLE_SIZE} listings.")
    else:
        client = _load_client()
        listings, entities = fetch_discovery_inputs(client, args.listing_id, args.source)

    proposals, _ = build_discovery_proposals(listings, entities)
    report = build_report(
        listings,
        entities,
        mode="write" if args.write else "dry_run",
    )
    if args.write:
        print(
            json.dumps({"phase": "pre_write", **report}, indent=2, sort_keys=True),
            flush=True,
        )
        write_result = write_discovery_candidates(
            client,
            proposals,
            listings,
        )
        report["writes_performed"] = bool(
            write_result["created_entity_count"]
            or write_result["inserted_relationship_count"]
        )
        report["write_result"] = write_result

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
