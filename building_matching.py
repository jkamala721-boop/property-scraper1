"""Deterministic apartment-to-building-entity matching.

Building Matching V1 is read-only by default.  Its explicit write mode can
only insert strong, unambiguous candidate relationships for an explicitly
bounded listing-id sample.  It never creates or changes building entities,
canonical buildings, or canonical-building relationships.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence


STRONG_CANDIDATE_THRESHOLD = 0.85
REVIEW_CANDIDATE_THRESHOLD = 0.70
AMBIGUITY_MARGIN = 0.08
MAX_SAMPLE_SIZE = 50
MAX_ENTITY_COUNT = 500
MAX_REFERENCE_RELATIONSHIPS = 5000
MATCHER_VERSION = "deterministic_v1"
AUTO_MATCH_METHOD = "deterministic_v1_auto"

WEIGHTS = {
    "entity_name": 0.55,
    "entity_name_in_title": 0.10,
    "location": 0.20,
    "road_address": 0.20,
    "landmark": 0.10,
    "description_similarity_strong": 0.12,
    "description_similarity_medium": 0.08,
    "description_similarity_weak": 0.04,
    "same_agent": 0.04,
    "same_contact": 0.04,
    "same_floor": 0.04,
    "amenities_high": 0.04,
    "amenities_medium": 0.02,
    "posting_within_day": 0.03,
    "posting_within_week": 0.01,
    "location_conflict": -0.40,
    "road_conflict": -0.15,
}

AMENITY_FIELDS = (
    "swimming_pool",
    "gym",
    "parking",
    "lift",
    "backup_generator",
    "borehole",
    "cctv",
    "security",
    "fiber_internet",
    "garden",
    "children_play_area",
)

PROPERTY_COLUMNS = (
    "source",
    "listing_id",
    "title",
    "description",
    "location",
    "standard_location",
    "agent_name",
    "bedrooms",
    "bathrooms",
    "price",
    "currency",
    "listing_type",
    "posted_date",
    *AMENITY_FIELDS,
)

STOPWORDS = {
    "a",
    "an",
    "and",
    "apartment",
    "apartments",
    "at",
    "available",
    "bedroom",
    "bedrooms",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "property",
    "rent",
    "sale",
    "the",
    "this",
    "to",
    "with",
}

ROAD_SUFFIXES = {"road", "street", "avenue", "lane", "drive", "crescent", "highway"}
LANDMARK_SUFFIXES = {"mall", "centre", "center", "hospital", "school", "university"}
GENERIC_SINGLE_NAMES = {
    "apartment",
    "apartments",
    "building",
    "estate",
    "homes",
    "residence",
    "residences",
    "tower",
    "towers",
}


@dataclass(frozen=True)
class ListingEvidence:
    apartment_id: int
    source: str
    listing_id: int
    title: str = ""
    description: str = ""
    location: str | None = None
    standard_location: str | None = None
    agent_name: str | None = None
    bedrooms: float | int | None = None
    bathrooms: float | int | None = None
    price: float | int | None = None
    currency: str | None = None
    listing_type: str | None = None
    posted_date: str | None = None
    amenities: frozenset[str] = field(default_factory=frozenset)
    existing_entity_ids: frozenset[int] = field(default_factory=frozenset)


@dataclass(frozen=True)
class BuildingEntityProfile:
    id: int
    building_code: str
    canonical_name: str | None = None
    normalized_name: str | None = None
    location: str | None = None
    standard_location: str | None = None
    address_text: str | None = None
    reference_listings: tuple[ListingEvidence, ...] = ()


@dataclass(frozen=True)
class Signal:
    name: str
    value: float
    detail: str


@dataclass(frozen=True)
class EntityScore:
    entity_id: int
    building_code: str
    score: float
    identity_signal_count: int
    matched_signals: tuple[Signal, ...]
    conflicting_signals: tuple[Signal, ...]
    weak_compatibility_signals: tuple[str, ...]


@dataclass(frozen=True)
class MatchDecision:
    apartment_id: int
    source: str
    listing_id: int
    outcome: str
    confidence: float
    proposed_building_entity_id: int | None
    proposed_building_code: str | None
    best_compared_entity_id: int | None
    best_compared_building_code: str | None
    existing_relationship: bool
    matched_signals: tuple[Signal, ...]
    conflicting_signals: tuple[Signal, ...]
    weak_compatibility_signals: tuple[str, ...]
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_text(value: Any) -> str:
    """Normalize text for deterministic phrase comparisons."""

    if value is None:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(value))
    ascii_text = "".join(character for character in decomposed if not unicodedata.combining(character))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).split())


def _phrase_present(phrase: str, text: str) -> bool:
    if not phrase or not text:
        return False
    return f" {phrase} " in f" {text} "


def _entity_name(entity: BuildingEntityProfile) -> str:
    name = normalize_text(entity.normalized_name or entity.canonical_name)
    tokens = name.split()
    if not tokens:
        return ""
    if len(tokens) == 1 and (tokens[0] in GENERIC_SINGLE_NAMES or len(tokens[0]) < 5):
        return ""
    return name


def _location_values(listing_or_entity: Any) -> set[str]:
    return {
        normalized
        for normalized in (
            normalize_text(getattr(listing_or_entity, "location", None)),
            normalize_text(getattr(listing_or_entity, "standard_location", None)),
        )
        if normalized
    }


def _suffix_phrases(text: str, suffixes: set[str]) -> set[str]:
    tokens = normalize_text(text).split()
    phrases: set[str] = set()
    for index, token in enumerate(tokens):
        if token not in suffixes or index == 0:
            continue
        previous = tokens[index - 1]
        if previous not in STOPWORDS:
            phrases.add(f"{previous} {token}")
        if index >= 2 and tokens[index - 2] not in STOPWORDS:
            phrases.add(f"{tokens[index - 2]} {previous} {token}")
    return phrases


def _phones(text: str) -> set[str]:
    results: set[str] = set()
    for match in re.findall(r"(?:\+?254|0)[0-9\s().-]{7,16}[0-9]", text or ""):
        digits = re.sub(r"\D", "", match)
        if digits.startswith("254") and len(digits) == 12:
            digits = "0" + digits[3:]
        if len(digits) == 10:
            results.add(digits)
    return results


def _floors(text: str) -> set[int]:
    normalized = normalize_text(text)
    results: set[int] = set()
    for match in re.finditer(r"\b(\d{1,3})(?:st|nd|rd|th)? floor\b|\bfloor (\d{1,3})\b", normalized):
        value = match.group(1) or match.group(2)
        results.add(int(value))
    return results


def _informative_tokens(text: str) -> set[str]:
    return {
        token
        for token in normalize_text(text).split()
        if len(token) >= 3 and token not in STOPWORDS and not token.isdigit()
    }


def _jaccard(left: set[str] | frozenset[str], right: set[str] | frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _listing_text(listing: ListingEvidence) -> str:
    return " ".join(part for part in (listing.title, listing.description) if part)


def _best_reference_support(
    listing: ListingEvidence,
    references: Sequence[ListingEvidence],
) -> tuple[list[Signal], list[str], bool]:
    best_signals: list[Signal] = []
    best_weak: list[str] = []
    best_description_is_identity_signal = False
    best_points = -1.0

    candidate_text = _listing_text(listing)
    candidate_tokens = _informative_tokens(candidate_text)
    candidate_phones = _phones(candidate_text)
    candidate_floors = _floors(candidate_text)

    for reference in references:
        if (
            reference.apartment_id == listing.apartment_id
            or (reference.source == listing.source and reference.listing_id == listing.listing_id)
        ):
            continue

        signals: list[Signal] = []
        weak: list[str] = []
        reference_text = _listing_text(reference)
        similarity = _jaccard(candidate_tokens, _informative_tokens(reference_text))
        description_is_identity_signal = similarity >= 0.55

        if similarity >= 0.75:
            signals.append(Signal("description_similarity", WEIGHTS["description_similarity_strong"], f"{similarity:.2f} token similarity to listing {reference.listing_id}"))
        elif similarity >= 0.55:
            signals.append(Signal("description_similarity", WEIGHTS["description_similarity_medium"], f"{similarity:.2f} token similarity to listing {reference.listing_id}"))
        elif similarity >= 0.35:
            signals.append(Signal("description_similarity", WEIGHTS["description_similarity_weak"], f"{similarity:.2f} token similarity to listing {reference.listing_id}"))

        if normalize_text(listing.agent_name) and normalize_text(listing.agent_name) == normalize_text(reference.agent_name):
            signals.append(Signal("same_agent", WEIGHTS["same_agent"], f"same agent as listing {reference.listing_id}"))

        reference_phones = _phones(reference_text)
        if candidate_phones and candidate_phones & reference_phones:
            signals.append(Signal("same_contact", WEIGHTS["same_contact"], f"same contact as listing {reference.listing_id}"))

        reference_floors = _floors(reference_text)
        if candidate_floors and candidate_floors & reference_floors:
            signals.append(Signal("same_floor", WEIGHTS["same_floor"], f"same floor as listing {reference.listing_id}"))

        amenity_similarity = _jaccard(listing.amenities, reference.amenities)
        if amenity_similarity >= 0.80:
            signals.append(Signal("amenity_similarity", WEIGHTS["amenities_high"], f"{amenity_similarity:.2f} amenity similarity to listing {reference.listing_id}"))
        elif amenity_similarity >= 0.60:
            signals.append(Signal("amenity_similarity", WEIGHTS["amenities_medium"], f"{amenity_similarity:.2f} amenity similarity to listing {reference.listing_id}"))

        candidate_date = _parse_datetime(listing.posted_date)
        reference_date = _parse_datetime(reference.posted_date)
        if candidate_date and reference_date:
            day_gap = abs((candidate_date - reference_date).total_seconds()) / 86400
            if day_gap <= 1:
                signals.append(Signal("posting_time_proximity", WEIGHTS["posting_within_day"], f"{day_gap:.2f} days from listing {reference.listing_id}"))
            elif day_gap <= 7:
                signals.append(Signal("posting_time_proximity", WEIGHTS["posting_within_week"], f"{day_gap:.2f} days from listing {reference.listing_id}"))

        if listing.bedrooms is not None and listing.bedrooms == reference.bedrooms:
            weak.append("same bedrooms")
        if listing.bathrooms is not None and listing.bathrooms == reference.bathrooms:
            weak.append("same bathrooms")
        if listing.price is not None and listing.price == reference.price:
            weak.append("same price")
        if listing.listing_type and listing.listing_type == reference.listing_type:
            weak.append("same listing type")

        points = sum(signal.value for signal in signals)
        if points > best_points:
            best_points = points
            best_signals = signals
            best_weak = weak
            best_description_is_identity_signal = description_is_identity_signal

    return best_signals, best_weak, best_description_is_identity_signal


def score_entity(listing: ListingEvidence, entity: BuildingEntityProfile) -> EntityScore:
    """Score one listing against one existing entity without changing state."""

    matched: list[Signal] = []
    conflicts: list[Signal] = []
    identity_signal_count = 0
    listing_title = normalize_text(listing.title)
    listing_text = normalize_text(_listing_text(listing))

    entity_name = _entity_name(entity)
    if entity_name and _phrase_present(entity_name, listing_text):
        matched.append(Signal("entity_name", WEIGHTS["entity_name"], f"exact phrase '{entity_name}'"))
        identity_signal_count += 1
        if _phrase_present(entity_name, listing_title):
            matched.append(Signal("entity_name_in_title", WEIGHTS["entity_name_in_title"], "entity name appears in title"))

    listing_locations = _location_values(listing)
    entity_locations = _location_values(entity)
    if listing_locations and entity_locations:
        location_overlap = listing_locations & entity_locations
        if location_overlap:
            matched.append(Signal("location", WEIGHTS["location"], f"matching location: {sorted(location_overlap)[0]}"))
            identity_signal_count += 1
        else:
            conflicts.append(Signal("location_conflict", WEIGHTS["location_conflict"], f"listing={sorted(listing_locations)}, entity={sorted(entity_locations)}"))

    entity_roads = _suffix_phrases(entity.address_text or "", ROAD_SUFFIXES)
    listing_roads = _suffix_phrases(_listing_text(listing), ROAD_SUFFIXES)
    road_overlap = entity_roads & listing_roads
    if road_overlap:
        matched.append(Signal("road_address", WEIGHTS["road_address"], f"matching road: {sorted(road_overlap, key=len)[-1]}"))
        identity_signal_count += 1
    elif entity_roads and listing_roads:
        conflicts.append(Signal("road_conflict", WEIGHTS["road_conflict"], f"listing={sorted(listing_roads)}, entity={sorted(entity_roads)}"))

    entity_landmarks = _suffix_phrases(entity.address_text or "", LANDMARK_SUFFIXES)
    listing_landmarks = _suffix_phrases(_listing_text(listing), LANDMARK_SUFFIXES)
    landmark_overlap = entity_landmarks & listing_landmarks
    if landmark_overlap:
        matched.append(Signal("landmark", WEIGHTS["landmark"], f"matching landmark: {sorted(landmark_overlap, key=len)[-1]}"))
        identity_signal_count += 1

    reference_signals, weak_signals, description_is_identity_signal = _best_reference_support(
        listing,
        entity.reference_listings,
    )
    matched.extend(reference_signals)
    if description_is_identity_signal:
        identity_signal_count += 1

    score = sum(signal.value for signal in matched) + sum(signal.value for signal in conflicts)
    if conflicts:
        conflict_names = {signal.name for signal in conflicts}
        if "location_conflict" in conflict_names or "road_conflict" in conflict_names:
            score = min(score, REVIEW_CANDIDATE_THRESHOLD - 0.01)

    return EntityScore(
        entity_id=entity.id,
        building_code=entity.building_code,
        score=round(max(0.0, min(1.0, score)), 4),
        identity_signal_count=identity_signal_count,
        matched_signals=tuple(matched),
        conflicting_signals=tuple(conflicts),
        weak_compatibility_signals=tuple(weak_signals),
    )


def match_listing(
    listing: ListingEvidence,
    entities: Sequence[BuildingEntityProfile],
) -> MatchDecision:
    """Return a candidate recommendation or an explicit abstention."""

    if not entities:
        return MatchDecision(
            apartment_id=listing.apartment_id,
            source=listing.source,
            listing_id=listing.listing_id,
            outcome="no_match",
            confidence=0.0,
            proposed_building_entity_id=None,
            proposed_building_code=None,
            best_compared_entity_id=None,
            best_compared_building_code=None,
            existing_relationship=False,
            matched_signals=(),
            conflicting_signals=(),
            weak_compatibility_signals=(),
            explanation="No building entities are available for comparison.",
        )

    scores = sorted(
        (score_entity(listing, entity) for entity in entities),
        key=lambda item: (-item.score, item.entity_id),
    )
    best = scores[0]
    existing_relationship = best.entity_id in listing.existing_entity_ids

    if best.identity_signal_count < 2:
        outcome = "no_match"
        explanation = f"Abstained: {best.building_code} had fewer than two independent identity signals."
    elif best.conflicting_signals:
        outcome = "no_match"
        explanation = f"Abstained: conflicting evidence prevents a safe match to {best.building_code}."
    elif len(scores) > 1 and scores[1].score >= REVIEW_CANDIDATE_THRESHOLD and best.score - scores[1].score < AMBIGUITY_MARGIN:
        outcome = "no_match"
        explanation = f"Abstained: {best.building_code} and {scores[1].building_code} are within the {AMBIGUITY_MARGIN:.2f} ambiguity margin."
    elif best.score >= STRONG_CANDIDATE_THRESHOLD:
        outcome = "strong_candidate"
        explanation = f"Strong candidate for {best.building_code} from {best.identity_signal_count} independent identity signals."
    elif best.score >= REVIEW_CANDIDATE_THRESHOLD:
        outcome = "review_candidate"
        explanation = f"Review candidate for {best.building_code}; evidence is credible but below the strong threshold."
    else:
        outcome = "no_match"
        explanation = f"Abstained: best score for {best.building_code} was below {REVIEW_CANDIDATE_THRESHOLD:.2f}."

    proposed = outcome != "no_match"
    return MatchDecision(
        apartment_id=listing.apartment_id,
        source=listing.source,
        listing_id=listing.listing_id,
        outcome=outcome,
        confidence=best.score,
        proposed_building_entity_id=best.entity_id if proposed else None,
        proposed_building_code=best.building_code if proposed else None,
        best_compared_entity_id=best.entity_id,
        best_compared_building_code=best.building_code,
        existing_relationship=existing_relationship,
        matched_signals=best.matched_signals,
        conflicting_signals=best.conflicting_signals,
        weak_compatibility_signals=best.weak_compatibility_signals,
        explanation=explanation,
    )


def run_matcher(
    listings: Sequence[ListingEvidence],
    entities: Sequence[BuildingEntityProfile],
) -> list[MatchDecision]:
    return [match_listing(listing, entities) for listing in listings]


def _listing_from_rows(
    property_row: dict[str, Any],
    apartment_id: int,
    existing_entity_ids: Iterable[int] = (),
) -> ListingEvidence:
    return ListingEvidence(
        apartment_id=int(apartment_id),
        source=str(property_row["source"]),
        listing_id=int(property_row["listing_id"]),
        title=property_row.get("title") or "",
        description=property_row.get("description") or "",
        location=property_row.get("location"),
        standard_location=property_row.get("standard_location"),
        agent_name=property_row.get("agent_name"),
        bedrooms=property_row.get("bedrooms"),
        bathrooms=property_row.get("bathrooms"),
        price=property_row.get("price"),
        currency=property_row.get("currency"),
        listing_type=property_row.get("listing_type"),
        posted_date=property_row.get("posted_date"),
        amenities=frozenset(field for field in AMENITY_FIELDS if property_row.get(field) is True),
        existing_entity_ids=frozenset(int(entity_id) for entity_id in existing_entity_ids),
    )


def relationship_can_seed_reference(row: dict[str, Any]) -> bool:
    """Allow only confirmed or explicitly manual candidate evidence to propagate."""

    if row.get("match_status") == "confirmed":
        return True

    confidence = row.get("match_confidence")
    return (
        row.get("match_status") == "candidate"
        and row.get("match_method") == "manual_multi_signal_review"
        and confidence is not None
        and float(confidence) >= STRONG_CANDIDATE_THRESHOLD
    )


def build_profiles_from_rows(
    candidate_rows: Sequence[dict[str, Any]],
    reference_rows: Sequence[dict[str, Any]],
    entity_rows: Sequence[dict[str, Any]],
    relationship_rows: Sequence[dict[str, Any]],
) -> tuple[list[ListingEvidence], list[BuildingEntityProfile]]:
    """Build pure matcher inputs from joined read-only query rows."""

    accepted_relationships = [
        row for row in relationship_rows if relationship_can_seed_reference(row)
    ]
    existing_by_apartment: dict[int, set[int]] = {}
    for row in relationship_rows:
        existing_by_apartment.setdefault(int(row["apartment_id"]), set()).add(int(row["building_entity_id"]))

    candidates = [
        _listing_from_rows(row, int(row["apartment_id"]), existing_by_apartment.get(int(row["apartment_id"]), ()))
        for row in candidate_rows
    ]
    references = [
        _listing_from_rows(row, int(row["apartment_id"]), existing_by_apartment.get(int(row["apartment_id"]), ()))
        for row in reference_rows
    ]
    references_by_apartment = {listing.apartment_id: listing for listing in references}
    apartment_ids_by_entity: dict[int, list[int]] = {}
    for row in accepted_relationships:
        apartment_ids_by_entity.setdefault(int(row["building_entity_id"]), []).append(int(row["apartment_id"]))

    entities = [
        BuildingEntityProfile(
            id=int(row["id"]),
            building_code=str(row["building_code"]),
            canonical_name=row.get("canonical_name"),
            normalized_name=row.get("normalized_name"),
            location=row.get("location"),
            standard_location=row.get("standard_location"),
            address_text=row.get("address_text"),
            reference_listings=tuple(
                references_by_apartment[apartment_id]
                for apartment_id in apartment_ids_by_entity.get(int(row["id"]), ())
                if apartment_id in references_by_apartment
            ),
        )
        for row in entity_rows
    ]
    return candidates, entities


def _response_data(response: Any) -> list[dict[str, Any]]:
    return list(response.data or [])


def _fetch_properties(client: Any, keys: Sequence[tuple[str, int]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in sorted({source for source, _ in keys}):
        listing_ids = sorted({listing_id for row_source, listing_id in keys if row_source == source})
        if not listing_ids:
            continue
        response = (
            client.table("properties")
            .select(",".join(PROPERTY_COLUMNS))
            .eq("source", source)
            .in_("listing_id", listing_ids)
            .execute()
        )
        rows.extend(_response_data(response))
    return rows


def fetch_dry_run_inputs(
    client: Any,
    listing_ids: Sequence[int],
    source: str = "BuyRentKenya",
) -> tuple[list[ListingEvidence], list[BuildingEntityProfile]]:
    """Read a bounded sample and existing entity profiles from Supabase."""

    requested_ids = sorted({int(listing_id) for listing_id in listing_ids})
    if not requested_ids:
        raise ValueError("At least one listing id is required.")
    if len(requested_ids) > MAX_SAMPLE_SIZE:
        raise ValueError(f"Dry-run samples are limited to {MAX_SAMPLE_SIZE} listings.")

    candidate_mappings = _response_data(
        client.table("apartment_listings")
        .select("apartment_id,source,listing_id")
        .eq("source", source)
        .in_("listing_id", requested_ids)
        .execute()
    )
    mapping_by_key = {
        (str(row["source"]), int(row["listing_id"])): int(row["apartment_id"])
        for row in candidate_mappings
    }
    missing = [listing_id for listing_id in requested_ids if (source, listing_id) not in mapping_by_key]
    if missing:
        raise ValueError(f"Listings do not have apartment mappings: {missing}")

    candidate_properties = _fetch_properties(client, [(source, listing_id) for listing_id in requested_ids])
    candidate_rows = [
        {**row, "apartment_id": mapping_by_key[(str(row["source"]), int(row["listing_id"]))]}
        for row in candidate_properties
    ]

    entity_rows = _response_data(
        client.table("building_entities")
        .select("id,building_code,canonical_name,normalized_name,location,standard_location,address_text")
        .order("id")
        .limit(MAX_ENTITY_COUNT + 1)
        .execute()
    )
    if len(entity_rows) > MAX_ENTITY_COUNT:
        raise RuntimeError(f"Entity count exceeds the V1 safety limit of {MAX_ENTITY_COUNT}.")

    relationship_rows = _response_data(
        client.table("apartment_building_entities")
        .select("apartment_id,building_entity_id,match_status,match_confidence,match_method")
        .order("id")
        .limit(MAX_REFERENCE_RELATIONSHIPS + 1)
        .execute()
    )
    if len(relationship_rows) > MAX_REFERENCE_RELATIONSHIPS:
        raise RuntimeError(
            f"Reference relationship count exceeds the V1 safety limit of {MAX_REFERENCE_RELATIONSHIPS}."
        )

    accepted_apartment_ids = sorted({
        int(row["apartment_id"])
        for row in relationship_rows
        if relationship_can_seed_reference(row)
    })
    reference_mappings: list[dict[str, Any]] = []
    if accepted_apartment_ids:
        reference_mappings = _response_data(
            client.table("apartment_listings")
            .select("apartment_id,source,listing_id")
            .in_("apartment_id", accepted_apartment_ids)
            .execute()
        )
    reference_keys = [(str(row["source"]), int(row["listing_id"])) for row in reference_mappings]
    reference_properties = {
        (str(row["source"]), int(row["listing_id"])): row
        for row in _fetch_properties(client, reference_keys)
    }
    reference_rows = [
        {
            **reference_properties[(str(mapping["source"]), int(mapping["listing_id"]))],
            "apartment_id": int(mapping["apartment_id"]),
        }
        for mapping in reference_mappings
        if (str(mapping["source"]), int(mapping["listing_id"])) in reference_properties
    ]
    return build_profiles_from_rows(candidate_rows, reference_rows, entity_rows, relationship_rows)


def _load_client() -> Any:
    from supabase import create_client

    from config import SUPABASE_KEY, SUPABASE_URL

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def _is_ambiguous(decision: MatchDecision) -> bool:
    return decision.outcome == "no_match" and "ambiguity" in decision.explanation.lower()


def auto_write_ineligibility(decision: MatchDecision) -> str | None:
    """Return why a decision cannot be auto-written, or None when eligible."""

    if decision.existing_relationship:
        return "existing_relationship"
    if decision.outcome != "strong_candidate":
        return decision.outcome
    if decision.confidence < STRONG_CANDIDATE_THRESHOLD:
        return "below_strong_threshold"
    if decision.conflicting_signals:
        return "conflicting_evidence"
    if decision.proposed_building_entity_id is None or decision.proposed_building_code is None:
        return "missing_proposed_entity"
    return None


def build_auto_candidate_row(decision: MatchDecision) -> dict[str, Any]:
    """Build the only relationship shape permitted for automated V1 writes."""

    ineligibility = auto_write_ineligibility(decision)
    if ineligibility is not None:
        raise ValueError(f"Decision is not eligible for automated write: {ineligibility}")

    return {
        "apartment_id": decision.apartment_id,
        "building_entity_id": decision.proposed_building_entity_id,
        "match_status": "candidate",
        "match_confidence": decision.confidence,
        "match_method": AUTO_MATCH_METHOD,
        "evidence": {
            "source": decision.source,
            "listing_id": decision.listing_id,
            "matcher": {
                "version": MATCHER_VERSION,
                "method": AUTO_MATCH_METHOD,
                "outcome": decision.outcome,
                "score": decision.confidence,
            },
            "entity": {
                "id": decision.proposed_building_entity_id,
                "code": decision.proposed_building_code,
            },
            "matched_signals": [asdict(signal) for signal in decision.matched_signals],
            "conflicting_signals": [asdict(signal) for signal in decision.conflicting_signals],
            "weak_compatibility_signals": list(decision.weak_compatibility_signals),
            "explanation": decision.explanation,
            "thresholds": {
                "strong_candidate": STRONG_CANDIDATE_THRESHOLD,
                "review_candidate": REVIEW_CANDIDATE_THRESHOLD,
                "ambiguity_margin": AMBIGUITY_MARGIN,
                "minimum_identity_signals": 2,
            },
        },
    }


def write_auto_candidates(client: Any, decisions: Sequence[MatchDecision]) -> dict[str, Any]:
    """Insert eligible candidate rows without updating duplicates.

    The database uniqueness constraint on (apartment_id, building_entity_id)
    is the final idempotency guard.  ``ignore_duplicates`` makes a concurrent
    or already-present relationship a no-op while all other database errors
    still propagate.
    """

    inserted: list[dict[str, Any]] = []
    existing_relationships_skipped: list[dict[str, Any]] = []
    ineligible_skipped: list[dict[str, Any]] = []

    for decision in decisions:
        reason = auto_write_ineligibility(decision)
        if reason == "existing_relationship":
            existing_relationships_skipped.append(decision.to_dict())
            continue
        if reason is not None:
            ineligible_skipped.append({"reason": reason, "decision": decision.to_dict()})
            continue

        row = build_auto_candidate_row(decision)
        response = (
            client.table("apartment_building_entities")
            .upsert(
                row,
                on_conflict="apartment_id,building_entity_id",
                ignore_duplicates=True,
            )
            .execute()
        )
        persisted_rows = _response_data(response)
        if persisted_rows:
            inserted.extend(persisted_rows)
        else:
            existing_relationships_skipped.append(decision.to_dict())

    return {
        "inserted": inserted,
        "inserted_count": len(inserted),
        "existing_relationships_skipped": existing_relationships_skipped,
        "existing_relationships_skipped_count": len(existing_relationships_skipped),
        "ineligible_skipped": ineligible_skipped,
        "ineligible_skipped_count": len(ineligible_skipped),
    }


def _report(decisions: Sequence[MatchDecision], mode: str = "dry_run") -> dict[str, Any]:
    strong_candidates = [decision for decision in decisions if decision.outcome == "strong_candidate"]
    abstentions = [decision for decision in decisions if decision.outcome != "strong_candidate"]
    ambiguous_cases = [decision for decision in decisions if _is_ambiguous(decision)]
    conflicts = [decision for decision in decisions if decision.conflicting_signals]
    existing_relationships = [decision for decision in decisions if decision.existing_relationship]

    return {
        "mode": mode,
        "writes_performed": False,
        "thresholds": {
            "strong_candidate": STRONG_CANDIDATE_THRESHOLD,
            "review_candidate": REVIEW_CANDIDATE_THRESHOLD,
            "ambiguity_margin": AMBIGUITY_MARGIN,
            "minimum_identity_signals": 2,
        },
        "summary": {
            "listings_evaluated": len(decisions),
            "strong_candidates": len(strong_candidates),
            "abstentions": len(abstentions),
            "ambiguous_cases": len(ambiguous_cases),
            "conflicts": len(conflicts),
            "existing_relationships_skipped": len(existing_relationships),
        },
        "strong_candidates": [decision.to_dict() for decision in strong_candidates],
        "abstentions": [decision.to_dict() for decision in abstentions],
        "ambiguous_cases": [decision.to_dict() for decision in ambiguous_cases],
        "conflicts": [decision.to_dict() for decision in conflicts],
        "existing_relationships_skipped": [decision.to_dict() for decision in existing_relationships],
        "results": [decision.to_dict() for decision in decisions],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic Building Matching V1 workflow")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Evaluate and report without writes")
    mode.add_argument("--write", action="store_true", help="Insert only eligible strong candidate relationships")
    parser.add_argument("--listing-id", type=int, action="append", required=True, help="Explicit listing id; repeat for a small sample")
    parser.add_argument("--source", default="BuyRentKenya")
    args = parser.parse_args(argv)

    client = _load_client()
    listings, entities = fetch_dry_run_inputs(client, args.listing_id, args.source)
    decisions = run_matcher(listings, entities)
    report = _report(decisions, mode="write" if args.write else "dry_run")

    if args.write:
        print(
            json.dumps({"phase": "pre_write", **report}, indent=2, sort_keys=True),
            flush=True,
        )
        write_result = write_auto_candidates(client, decisions)
        report["writes_performed"] = write_result["inserted_count"] > 0
        report["write_result"] = write_result

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
