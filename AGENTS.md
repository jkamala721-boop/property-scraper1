# LocationOS — Codex Engineering Instructions

## 1. Project Identity

This project is called LocationOS.

LocationOS is a real-estate intelligence platform beginning with Nairobi apartments. It is not simply a property-listing website. Its purpose is to transform fragmented real-estate listings, direct user submissions, public building information, and other real-estate data into structured, verified, and useful real-estate intelligence.

The long-term relationship is:

Listing
→ Listing Identity
→ Apartment Identity
→ Building Entity / Building Match
→ Canonical Building Information
→ Location
→ Market
→ Investment Intelligence

## 2. Current Stage

Current product stage:

Stage 1 — Nairobi Apartments.

Current production ingestion source:

BuyRentKenya.

Planned additional ingestion sources include Property24, HassConsult, direct user-submitted listings, and approved public building-information sources. These should be developed as separate source modules and connected through LocationOS canonical layers rather than tightly coupling them to the BuyRentKenya scraper.

## 3. Current Verified / Implemented Foundation

The project has working functionality for:

- BuyRentKenya listing collection
- JSON-LD extraction
- property normalization
- location normalization
- bedroom normalization
- bathroom normalization
- pricing normalization
- amenity normalization
- Supabase property storage
- source-listing upsert/update
- duplicate protection using source + listing_id
- property image extraction and storage
- last_seen_at tracking
- scrape-run tracking
- scrape snapshots
- missing-listing detection after safe run completion
- scrape lifecycle states including completed / incomplete / failed logic in the current working implementation
- price-history observation storage
- price-history movement view
- apartment identity records
- source-listing-to-apartment relationships
- automatic apartment-code generation through PostgreSQL
- buildings table for future canonical/enriched building information
- apartment_buildings relationship table
- listing-derived building_entities table
- apartment_building_entities relationship table
- deterministic Building Matching V1 dry-run and explicit candidate-write workflow

Known historical scraper checkpoint:

999 / 999 listings successfully processed in a full test.

Recent database checkpoint discussed during development:

- total properties: 16,373
- sale: 11,648
- rent: 4,723
- NULL listing type: 2
- live: 15,245
- inactive: 1,128

These counts are time-sensitive. Codex must re-check the actual production database before relying on them.

## 4. Current Price History

Price History V1 is implemented.

Current structures:

- property_price_history
- property_price_history_view

The history layer records asking-price observations per source listing and scrape run. The view derives previous price, current price, absolute change, percentage change, and direction such as initial / unchanged / increased / reduced.

Observed asking prices are facts. Price movement is a derived metric. Do not describe asking-price history as transaction history.

## 5. Current Apartment Identity

The listing layer and physical-apartment identity layer are now separate.

Current structures:

- apartments
- apartment_listings

A source listing remains identified by:

source + listing_id

A LocationOS apartment receives an internal code such as:

APT-000001
APT-000003

Sequence gaps are acceptable and identifiers must never be recycled merely to make numbering consecutive.

The apartment identity foundation has been integration-tested with existing and new BuyRentKenya listings. Automatically created identities should remain unmatched until evidence supports a stronger match.

Listing ≠ Apartment.

Do not force multiple source listings into the same physical apartment without sufficient evidence.

## 6. Current Building Architecture

Two different concepts must remain separate.

### A. Listing-derived building identity

This listing-derived identity layer is implemented.

The implemented entity layer is:

building_entities

Its purpose is to represent an inferred physical-building identity derived from listing evidence, even when the official name, GPS, developer, year built, number of floors, or number of units is unknown.

Current fields:

- id
- building_code
- canonical_name
- normalized_name
- location
- standard_location
- address_text
- canonical_building_id
- first_seen_at
- last_seen_at
- created_at
- updated_at

The production schema remains authoritative and must still be inspected before
future changes.

`canonical_building_id` is nullable and references `buildings(id)` when a
listing-derived entity has been verified against canonical building information.

The separate `apartment_building_entities` relationship records the apartment
match and its evidence:

- id
- apartment_id
- building_entity_id
- match_status
- match_confidence
- match_method
- evidence JSONB
- created_at
- updated_at

Building Matching V1 is isolated from the scraper. It reads an explicit,
bounded listing sample and existing entity/reference evidence and provides an
explicit dry-run mode. Its explicit write mode inserts only unambiguous
`strong_candidate` relationships at confidence 0.85 or higher, always as
`candidate` with method `deterministic_v1_auto`. It never creates or changes
building entities or canonical-building records.

Reference evidence may come from confirmed relationships or from candidate
relationships explicitly marked `manual_multi_signal_review` at the minimum
confidence threshold. Automated candidates must never recursively seed more
automated candidates.

### B. Canonical / enriched building information

The existing buildings table is reserved for stronger building information gathered from trusted or public sources and later enrichment.

Its known schema includes fields such as:

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

Do not populate canonical building facts from weak listing inference merely to avoid NULLs.

The existing apartment_buildings table is reserved for later apartment-to-canonical-building relationships while preserving:

- match_status
- match_confidence
- match_method

At the last verified checkpoint, the buildings table and apartment_buildings table were empty of production building matches.

## 7. Building Matching Philosophy

Building identification must combine multiple pieces of evidence. Do not rely on one field.

Potential evidence includes:

- explicit building/project names in titles or descriptions
- road/street/address clues
- normalized location
- standard location
- nearby landmarks
- description similarity
- agent/source patterns
- amenities as supporting evidence
- bedrooms / bathrooms / price only as supporting unit-level evidence
- images later
- GPS later
- canonical public building information later
- AI/semantic matching later

Important findings from current BuyRentKenya data:

- standard_location is far too broad to identify a building by itself
- repeated titles are often listing templates and are not building identity
- amenity fingerprints are useful only as supporting evidence
- low confidence must not force a building match

Unknown building is a valid result.

## 8. Future Source Strategy

Do not make LocationOS permanently dependent on scraping one portal.

The target ingestion architecture is:

BuyRentKenya ─────┐
Property24 ───────┤
HassConsult ──────┤
Direct user data ─┤
Public buildings ─┘
        ↓
source-specific ingestion
        ↓
normalization / enrichment
        ↓
LocationOS canonical identity layers

Property24 and HassConsult should be implemented as separate modules and integrated later through common LocationOS entities. Do not retrofit their logic into BuyRentKenya-specific code unless a shared abstraction is intentionally introduced.

Direct user-submitted listings are a launch/product priority because long-term data quality should improve beyond scraped portal data.

## 9. Data Integrity

Preserve the distinction between:

- Observed fact
- Derived metric
- AI estimate
- Human verified information
- Unknown

Never fabricate missing information.

AI normalization/enrichment may later improve messy source fields such as location and bathrooms, but it must preserve source evidence and provenance.

## 10. Scraper Safety

Do not unnecessarily disrupt:

- request handling
- retry behavior
- extraction
- normalization
- batching
- database uploads
- image collection
- scrape-run tracking
- price-history recording
- apartment-identity recording

A scraper failure must not automatically cause existing properties to become inactive.

Before changing scrape lifecycle behavior, inspect the current database.py and scraper.py because safety hardening was added after the original documentation was written.

## 11. Database Safety

LocationOS uses Supabase/PostgreSQL.

Never, without explicit human approval:

- delete production property data
- truncate tables
- drop tables
- change primary/unique identity
- change column types
- perform destructive mass updates
- silently create/change production schema
- rebuild production tables
- remove historical information

For schema changes:

1. inspect actual schema
2. explain why the change is required
3. propose SQL
4. wait for human approval
5. execute only after approval
6. verify resulting schema
7. then update application code
8. test on a controlled sample

The actual Supabase schema is authoritative.

## 12. Secrets

Never expose, print, commit, or document:

- Supabase keys
- service-role keys
- passwords
- access tokens
- GitHub tokens
- .env contents
- other credentials

Never commit `.env`.

## 13. Testing

Before a large scraper run:

- test relevant code on one or a few listings
- verify database behavior
- verify history/identity rows
- verify snapshot behavior
- verify failures do not trigger destructive updates

After Python changes, run syntax checks, for example:

python3 -m py_compile database.py scraper.py

For meaningful changes, run available tests.

## 14. Git

Before significant changes:

- inspect git status
- inspect relevant commits
- confirm local/remote relationship

Do not casually use:

- git reset --hard
- git rebase
- git push --force

Prefer small descriptive commits.

Do not assume an old documented commit hash is still current. Inspect Git first.

## 15. Documentation

When implementing a significant capability, update:

- AGENTS.md
- docs/LOCATIONOS_ARCHITECTURE.md
- docs/LOCATIONOS_CURRENT_STATE.md
- docs/LOCATIONOS_DATABASE.md
- docs/LOCATIONOS_STAGE_1_ROADMAP.md

Current-state documents must describe actual implementation, not plans.

## 16. Current Priority

The immediate engineering priority is:

1. inspect repository and production schema
2. reconcile these updated docs with actual code/database
3. review and calibrate the deterministic Building Matching V1 dry run
4. validate the explicit, conservative Building Matching V1 candidate-write
   workflow on small reviewed samples before any wider run
5. preserve the separate canonical buildings enrichment layer
6. continue Stage 1 launch work without over-engineering pre-launch systems

Advanced AI matching, full market intelligence, off-plan risk, liquidity scoring, and sophisticated investment scoring are not the immediate implementation target unless explicitly requested.

## 17. Development Behavior

When asked to implement a feature:

1. inspect relevant files and schema first
2. explain the current implementation briefly
3. identify dependencies and risks
4. propose the smallest safe change
5. do not modify unrelated files
6. implement
7. test
8. report exactly what changed
9. report assumptions and remaining risks

Do not blindly follow a technically incorrect instruction. If the proposed approach is unsafe or weak, explain why and propose a better one.
