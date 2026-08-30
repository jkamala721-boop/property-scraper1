# LocationOS Current State — 2026-08-30

## Purpose

This document is the current development checkpoint for LocationOS. It supersedes older current-state statements that described price history, apartment identity, and building schema as purely planned.

The repository and production Supabase schema remain authoritative. Codex must inspect them before making changes.

## 1. Product Scope

Current focus:

Stage 1 — Nairobi apartments.

Current main ingestion source:

BuyRentKenya.

Planned additional sources:

- Property24
- HassConsult
- direct user-submitted listings
- public building/development information
- other approved real-estate data

LocationOS is intended to evolve away from dependency on any single scraped portal.

## 2. Current Database Checkpoint

Most recent development counts discussed:

- total properties: 16,373
- sale: 11,648
- rent: 4,723
- NULL listing type: 2
- live: 15,245
- inactive: 1,128

Core field checks:

- missing price: 0
- invalid/non-positive price: 13
- bedrooms present: 16,259
- bedrooms missing: 114
- invalid bedrooms: 0
- bathrooms present: 8,853
- bathrooms missing: 7,520
- invalid bathrooms: 0

These are snapshots, not constants. Re-query production before relying on them.

## 3. Listing Ingestion Foundation — IMPLEMENTED / TESTED

Implemented:

- BuyRentKenya link collection
- source/listing identity
- page requests and retry behavior
- JSON-LD graph parsing
- extraction
- normalization
- image extraction
- Supabase persistence
- upserts
- duplicate protection
- last_seen_at
- scrape runs
- scrape snapshots
- missing-listing detection

Historical known-good full test:

999 / 999 listings processed.

## 4. Source Listing Identity — IMPLEMENTED

Current source identity:

source + listing_id

This remains the stable source-record identity.

Duplicate URL analysis returned no duplicate source URLs at the reviewed checkpoint.

Listing ≠ Apartment.

## 5. Extractor — IMPLEMENTED

The current BuyRentKenya extractor uses JSON-LD entities including:

- Product
- Accommodation
- RealEstateListing
- RealEstateAgent

It extracts fields including:

- title
- description
- images
- bedrooms
- bathrooms
- price
- currency
- location
- listing_id
- source
- listing_type
- URL
- posted/updated dates
- live status
- agent

Important current source behavior:

BuyRentKenya may leave structured location information incomplete, so current extraction/normalization can infer location from listing title patterns. Do not remove that behavior casually.

Raw JSON-LD inspection showed additional useful evidence such as PostalAddress locality/region, breadcrumbs, Product category, and Place/Accommodation address relationships. Future enrichment may use those fields.

## 6. Normalization — IMPLEMENTED / TESTED

Current normalization areas include:

- location
- bedrooms
- bathrooms
- pricing
- amenities
- property fields

Current data quality is intentionally not being perfected before launch. Missing/weak fields such as bathrooms and ambiguous locations can be improved later through AI normalization, richer sources, and direct user submissions.

## 7. Scrape Lifecycle Safety — IMPLEMENTED IN CURRENT WORKING DESIGN

The scraper safety work added concepts including:

- batch upload failure propagation
- completed / incomplete / failed run states
- expected processed-count gating
- persisted snapshot-count verification before safe completion
- fail_scrape_run handling
- main() / __main__ execution structure

Codex must inspect current scraper.py and database.py to verify the exact repository state before changing this behavior.

A failed/incomplete run must not trigger mass inactive-property updates.

## 8. Price History V1 — IMPLEMENTED / TESTED

Current table:

property_price_history

Current derived view:

property_price_history_view

A controlled BuyRentKenya test used listing 4045566 and successfully produced multiple price observations across scrape runs.

The view correctly derived:

- previous_price
- current_price
- price_change
- price_change_percent
- price_direction

The tested repeated observations had the same price and correctly returned:

unchanged

This is asking-price history, not transaction-price history.

## 9. Apartment Identity V1 — IMPLEMENTED / TESTED

Current tables:

- apartments
- apartment_listings

A PostgreSQL sequence/default generates LocationOS apartment codes.

Examples verified during development:

- APT-000001 → BuyRentKenya listing 4045566 → confirmed
- APT-000003 → BuyRentKenya listing 4045574 → unmatched

A sequence gap is acceptable and identifiers must not be recycled.

Automatic identity logic was tested to:

- reuse an existing listing/apartment relationship
- create a new apartment identity for a new listing
- preserve unmatched status where a physical-unit match has not been established

This is an identity foundation, not a complete apartment-matching engine.

## 10. Apartment Matching Engine — NOT YET COMPLETE

A production fuzzy/AI apartment matching system is still planned.

Potential evidence later includes:

- building identity
- location
- size
- bedrooms
- bathrooms
- floor
- unit number
- price
- descriptions
- images
- amenities
- furnished status

Low confidence must remain unresolved.

## 11. Canonical Building Information Table — CREATED, NOT POPULATED

Current table:

buildings

Known fields include:

- id
- building_code
- name
- latitude
- longitude
- county
- area
- developer
- year_built
- number_of_floors
- number_of_units
- created_at
- updated_at

The table was intentionally reinterpreted as the future canonical/enriched building-information layer.

It should be populated from stronger building/development sources rather than weak listing guesses.

At the last verified checkpoint:

building_count = 0

## 12. Apartment-to-Canonical-Building Relationship — CREATED, NOT POPULATED

Current table:

apartment_buildings

Known relationship fields include:

- apartment_id
- building_id
- match_status
- match_confidence
- match_method
- timestamps

At the last verified checkpoint:

0 relationship rows

The relationship exists structurally but no production canonical-building matches were created. It must not be repurposed for provisional listing-derived building entities.

## 13. Listing-Derived Building Entity Layer — IMPLEMENTED / CONTROLLED SAMPLE

The next agreed architecture separates listing-derived building identity from canonical enriched building information.

Current table:

building_entities

Purpose:

Represent a LocationOS-inferred building cluster/entity when listings appear to refer to the same physical building, even if verified building metadata is not yet known.

Implemented fields:

- id
- building_code
- canonical_name
- normalized_name
- location
- standard_location
- address_text
- canonical_building_id NULL → buildings(id)
- first_seen_at
- last_seen_at
- created_at
- updated_at

The production table has been created. The first controlled provisional entity
is `BENT-000002` (`Garden City`) with no canonical-building link.

Current relationship table:

apartment_building_entities

- id
- apartment_id
- building_entity_id
- match_status
- match_confidence
- match_method
- evidence JSONB
- created_at
- updated_at

Match status, confidence, method, and evidence belong to this apartment-to-entity relationship, not to `building_entities`.

The controlled Garden City entity has candidate relationships to apartment IDs
1 and 4 at confidence 0.90 using `manual_multi_signal_review`. These are not
canonical-building relationships.

## 14. Building Matching V1 — DETERMINISTIC DRY RUN

An isolated deterministic matcher now supports read-only, explicitly bounded
dry runs. It compares listing/apartment evidence with existing
`building_entities` and trusted entity reference listings. It reports strong
candidates, review candidates, or explicit abstentions with matched signals,
conflicts, confidence, and an explanation.

V1 does not create entities or relationships, does not update existing rows,
and is not called by the production scraper. Automated proposals remain
candidate recommendations only.

Only confirmed relationships, or manually reviewed candidates using
`manual_multi_signal_review` at the minimum confidence threshold, can seed
reference evidence. High-confidence automated candidates are intentionally
excluded to prevent recursive confidence propagation.

Current design findings:

Data analysis showed:

- standard_location is too broad to identify buildings by itself
- Westlands alone contained thousands of listings
- exact repeated titles are often template-like and can represent many different properties
- description contains potentially useful building names, roads, landmarks, floors, and development clues
- amenities can support a match but are not unique building identifiers
- generic amenities must not determine identity
- multiple imperfect signals should be combined
- low confidence should not force a building assignment

Later matching can use:

- explicit development/building names
- normalized road/address clues
- description semantics
- standard/location fields
- agent/source patterns
- amenity fingerprints as supporting evidence
- images
- GPS
- public canonical building data
- AI matching

## 15. Public Building Enrichment Strategy — PLANNED

LocationOS should later collect actual building/development information from approved public sources.

That data can include:

- official/name variants
- GPS
- developer
- year built
- floors
- units
- amenities
- management information
- public development/project evidence

That canonical data should then be matched against listing-derived building_entities.

Conceptual flow:

properties
→ apartment_listings
→ apartments
→ apartment_building_entities
→ building_entities
→ canonical_building_id
→ buildings

## 16. Additional Source Strategy — PLANNED

Property24 and HassConsult are intentionally deferred.

They should be built as separate ingestion modules and later connect through the common LocationOS canonical layers.

Do not make their future integration disturb the existing BuyRentKenya pipeline.

## 17. Direct User Listings — LAUNCH / POST-LAUNCH PRIORITY

LocationOS should eventually allow users/agents/owners to submit listings directly.

Long-term goal:

reduce dependence on scraped portals and improve data completeness/quality.

AI normalization can later help standardize direct and scraped submissions while preserving raw source evidence.

## 18. Current Development Priority

Immediate next work:

1. inspect actual repository and production schema
2. update/reconcile documentation with actual state
3. review and calibrate Building Matching V1 dry-run results
4. approve a conservative listing-derived write workflow only after review
5. preserve buildings as canonical/enriched information
6. continue through Stage 1 launch-critical intelligence

Do not spend pre-launch time perfecting every source-data deficiency.

## 19. Not Yet Launch-Complete

Still important before/around first public launch:

- building identity V1
- building/entity relationships
- basic building enrichment
- location intelligence V1
- apartment information consolidation
- price/m² and rent/m² where size exists
- gross-yield calculation where inputs support it
- basic data confidence
- apartment intelligence UI
- search/filtering
- production frontend/deployment
- monitoring/analytics/security
- user listing submission path
- Property24 / HassConsult integration according to launch timing

Advanced liquidity, off-plan risk, full AI data stewardship, sophisticated investment scoring, and perfect matching should not block the first usable product unless explicitly reprioritized.
