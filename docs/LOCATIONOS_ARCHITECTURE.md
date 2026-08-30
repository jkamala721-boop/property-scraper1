# LocationOS Architecture — Updated 2026-08-30

## 1. Purpose

LocationOS is a real-estate intelligence platform focused initially on Nairobi apartments.

The objective is to transform fragmented source listings, direct submissions, public building/development information, and historical observations into structured property intelligence.

The core idea remains:

Listing ≠ Apartment ≠ Building information source.

## 2. Updated High-Level Architecture

DATA SOURCES
    ↓
source-specific ingestion
    ↓
LISTING OBSERVATIONS
    ↓
NORMALIZATION / ENRICHMENT
    ↓
APARTMENT IDENTITY
    ↓
LISTING-DERIVED BUILDING ENTITY
    ↓
BUILDING MATCH / VERIFICATION
    ↓
CANONICAL BUILDING INFORMATION
    ↓
LOCATION INTELLIGENCE
    ↓
MARKET INTELLIGENCE
    ↓
TRANSACTIONS / HISTORICAL DATA
    ↓
INVESTMENT ENGINE
    ↓
APARTMENT INTELLIGENCE

## 3. Data Sources

Current:

- BuyRentKenya

Planned:

- Property24
- HassConsult
- direct user-submitted listings
- public building/development sources
- future transaction/market sources

Each source should have an isolated ingestion path where practical and connect through common LocationOS entities.

## 4. Listing Layer

A listing is a source observation.

Stable source identity:

source + listing_id

A listing retains source URL, raw/observed data, normalized representation, images, timestamps, and source provenance.

## 5. Price Observation Layer

Price History V1 is implemented.

Asking-price observations are stored historically and price movement is derived.

This enables:

- reductions
- increases
- unchanged periods
- later negotiation signals
- later trend analysis

Asking prices must not be confused with transaction prices.

## 6. Apartment Identity Layer

The apartment identity foundation is implemented.

Current architecture:

source listing
→ apartment_listings
→ apartments

A physical apartment may eventually have multiple listings.

Low-confidence apartment matches remain unresolved.

## 7. Building Architecture — Two Layers

### 7.1 Building Entity

A building_entity is a listing-derived inferred physical-building identity.

It may exist before LocationOS knows:

- official name
- GPS
- developer
- year built
- floors
- unit count

It should be created conservatively from multiple pieces of listing evidence.

Its fields are limited to identity and observed/derived building descriptors:

- id, building_code, canonical_name, normalized_name
- location, standard_location, address_text
- canonical_building_id (nullable foreign key to `buildings(id)`)
- first_seen_at, last_seen_at, created_at, updated_at

Match status, confidence, method, and evidence do not belong on the entity.

### 7.2 Apartment-to-Entity Relationship

`apartment_building_entities` connects an apartment to a listing-derived entity.
It owns `match_status`, `match_confidence`, `match_method`, and `evidence JSONB`,
plus its identity and timestamps.

### 7.3 Canonical Building

The existing buildings table represents stronger/enriched building information.

Potential information includes:

- verified/name variants
- GPS
- county/area
- developer
- year built
- floors
- units
- facilities
- management information

Canonical building information can later be scraped/enriched from approved public sources and matched back to building_entities.

`apartment_buildings` remains separate for future apartment-to-canonical-building relationships; it is not the provisional entity relationship.

Conceptual chain:

properties
→ apartment_listings
→ apartments
→ apartment_building_entities
→ building_entities
→ canonical_building_id
→ buildings

## 8. Building Matching

The system should not match buildings from one weak field.

Evidence may include:

- explicit building/development names
- road/address clues
- normalized location
- standard location
- description semantics
- landmarks
- agent/source repetition
- amenity fingerprints
- images
- GPS
- canonical public building data

Current empirical findings:

- standard_location alone is far too broad
- repeated titles can be generic templates
- amenities support but do not identify buildings
- description may contain useful development names/floors/landmarks
- low confidence = unresolved

## 9. Normalization and AI Enrichment

Current deterministic normalization remains valuable and should not be removed casually.

Later AI normalization can improve:

- location interpretation
- building/development names
- address extraction
- bathroom/field recovery
- contradiction detection
- semantic matching

AI output must be marked as AI-derived/estimated until verified. Raw evidence must be preserved.

## 10. Direct User Data

Long-term architecture should reduce dependence on scraping.

Direct listing submissions should enter the same normalization and identity layers while preserving their provenance.

## 11. Data Trust Model

Every meaningful value should be attributable to one of:

- observed fact
- derived metric
- AI estimate
- human verified
- unknown

This distinction is fundamental to LocationOS trustworthiness.

## 12. Iterative Principle

Collect
→ Structure
→ Enrich
→ Verify
→ Calculate
→ Learn
→ Update

LocationOS should launch useful intelligence before every field and matching model is perfect, while protecting identity and historical integrity.
