# LocationOS Stage 1 Roadmap — Updated 2026-08-30

## Stage 1 Objective

Build a useful Nairobi apartment intelligence product and launch without waiting for every future intelligence model to become perfect.

## Phase A — Data Foundation

### Source listing collection — IMPLEMENTED

BuyRentKenya ingestion is working.

### Extraction — IMPLEMENTED

JSON-LD extraction is working.

### Normalization — IMPLEMENTED

Location, bedrooms, bathrooms, pricing, amenities, and property normalization are working.

### Property storage — IMPLEMENTED

Supabase upsert/storage with source + listing_id identity is working.

### Images — IMPLEMENTED

Property image extraction/storage is working.

## Phase B — Scrape History and Lifecycle

### Scrape runs — IMPLEMENTED

### Snapshots — IMPLEMENTED

### Missing-listing detection — IMPLEMENTED

### Failure/incomplete safety hardening — IMPLEMENTED IN CURRENT WORKING DESIGN

Codex must inspect repository state before changing this logic.

## Phase C — Price History

### Price History V1 — IMPLEMENTED / TESTED

Implemented:

- property_price_history
- property_price_history_view
- repeated observations
- previous/current comparison
- absolute and percentage price change
- direction

Next improvements can wait until needed by the UI/analytics.

## Phase D — Apartment Identity

### Apartment Identity V1 — IMPLEMENTED / TESTED

Implemented:

- apartments
- apartment_listings
- PostgreSQL-generated apartment codes
- existing relationship reuse
- new identity creation
- unmatched status for unverified physical matches

### Advanced Apartment Matching — PLANNED

Do not block launch on perfect fuzzy apartment matching.

## Phase E — Building Intelligence

### Canonical building table — CREATED

Existing buildings table is reserved for enriched/canonical facts.

### apartment_buildings — CREATED

Relationship structure exists for later apartment-to-canonical-building matches; no verified production matches at last checkpoint.

### building_entities — IMPLEMENTED

Create a separate listing-derived building identity layer.

Goal:

Listings/apartments can cluster toward a physical building identity without inventing canonical facts such as GPS, developer, year built, floors, or unit count.

The entity has a nullable `canonical_building_id` to `buildings(id)`. The
separate `apartment_building_entities` relationship owns match status,
confidence, method, and evidence. The first controlled Garden City entity and
four reviewed candidate relationships are present; `apartment_buildings`
remains separate.

### Building Matching V1 — DETERMINISTIC DRY RUN / CANDIDATE WRITE IMPLEMENTED

Use multiple signals conservatively:

- explicit names
- road/address clues
- location
- descriptions
- landmarks
- agent/source patterns
- amenities as supporting evidence

Low confidence remains unresolved.

The V1 implementation uses an explicitly bounded sample and produces
explainable candidate or abstention reports. It has explicit dry-run and write
modes and is not connected to the scraper. Write mode inserts only unambiguous
strong candidates at confidence 0.85 or higher, never updates an existing
relationship, and never writes canonical-building data.

Only confirmed relationships or sufficiently confident candidates explicitly
marked `manual_multi_signal_review` may seed reference evidence. Automated
candidate output cannot recursively seed later matches.

### Building Entity Discovery V1 — BOUNDED WRITE WORKFLOW IMPLEMENTED

The isolated discovery workflow extracts explicit development/building-name
evidence from an explicit sample of at most 50 listings, groups normalized name
variants, rejects generic neighborhoods and marketing phrases, checks existing
entities, and reports creation candidates, existing entities, review cases, or
abstentions. Conflicting locations do not merge. Development-level evidence
does not fabricate tower/block identity. Explicit write mode creates only
eligible `create_candidate` entities at confidence 0.85 or higher after a fresh
duplicate recheck, then adds individually supported candidate relationships
with method `entity_discovery_v1_auto`. It never writes canonical buildings,
and automatic discovery relationships cannot seed matching reference evidence.

The first controlled production write created `BENT-000003` / `Capital Garden`
and candidate relationships for apartments `8`, `1063`, and `1026`. Canonical
building tables were not changed.

### Operational Building Identity Pipeline V1 — IMPLEMENTED

Matching and discovery are composed by an explicit bounded command. It skips
already-linked apartments, attempts matching first, uses discovery only after a
plain no-match, and abstains on review, ambiguity, or conflict. Batches are
keyset-paginated at a maximum of 100 while existing V1 evaluation limits remain
50 internally. The pipeline is not integrated into the scraper and does not
touch canonical building tables.

The first 100-listing production batch completed with no errors and no writes:
zero strong matches or discovery creation proposals, five review cases, and 96
conservative abstentions. The next exclusive listing cursor is `3866377`.

### Canonical Building Enrichment — LATER / PRE-LAUNCH OR POST-LAUNCH

Scrape/collect actual building/development information from approved public sources.

Then match:

building_entities
→ canonical buildings

## Phase F — Additional Sources

### Property24 — PLANNED

Build separately, integrate through shared LocationOS identity layers.

### HassConsult — PLANNED

Build separately, integrate through shared LocationOS identity layers.

### Direct user listings — LAUNCH PRIORITY

Create a path for agents/owners/users to submit listings directly so LocationOS becomes progressively less dependent on scraped portals.

## Phase G — Apartment / Building Information V1

Before launch, implement enough consolidated information to support useful property pages.

Do not wait for complete data coverage.

## Phase H — Location Intelligence V1

Add useful building/location context:

- area
- major landmarks
- key nearby facilities
- basic distances where available

More sophisticated geospatial intelligence can follow.

## Phase I — Basic Investment Metrics

Launch-critical where inputs are available:

- sale price per m²
- rent per m²
- gross rental yield
- basic asking-price trend/history

Do not fabricate metrics where size/rent/value inputs are missing.

## Phase J — Basic Data Confidence

Provide a simple evidence-based confidence layer before making strong intelligence claims.

## Phase K — Product UI

Launch-critical:

- search/filtering
- listing/apartment results
- apartment intelligence page
- price history display
- building/entity context where available
- confidence/provenance cues

## Phase L — Launch Infrastructure

Before public launch:

- production frontend
- scraper scheduling/monitoring
- error reporting
- analytics
- authentication/user flows where needed
- secrets/security review
- backups/recovery basics
- direct listing submission workflow

## Post-Launch / Non-Blocking Advanced Work

Do not delay first launch for:

- perfect apartment matching
- perfect building matching
- full AI normalization
- full AI Data Steward
- sophisticated fair-value model
- liquidity score
- off-plan risk engine
- dynamic investor-specific scoring
- complete transaction history
- exhaustive Nairobi POI coverage

## Current Position

Completed or substantially implemented:

Listing collection
→ Extraction
→ Normalization
→ Property storage
→ Images
→ Scrape history
→ Price History V1
→ Apartment Identity V1

Current next milestone:

Validate Building Entity Discovery V1 writes on small reviewed samples
→ keep automatic discovery explicitly bounded before any wider run
→ Canonical Building Enrichment
→ Location / Basic Metrics
→ Product UI
→ Launch

Development principle:

Move quickly, preserve data integrity, validate important identities, and improve models after real users begin generating feedback and better data.
