# LocationOS Database Architecture — 2026-08-30

## 1. Authority

Supabase/PostgreSQL production schema is authoritative.

This document records the latest development architecture discussed and verified. Codex must inspect the live schema before applying changes.

## 2. Current Core Tables

### properties — IMPLEMENTED

Represents source listing observations.

Stable identity:

source + listing_id

Current data snapshot discussed:

16,373 rows.

Important fields include listing/source identity, title, description, listing type, price, currency, location fields, bedroom/bathroom fields, agent, listing dates, URL, live state, normalization confidence, amenities, standard_location, and last_seen_at.

### property_images — IMPLEMENTED

Stores source listing images.

Current upsert relationship historically uses:

listing_id + image_url

Future multi-source work must review whether source/property foreign-key identity should be strengthened.

### scrape_runs — IMPLEMENTED

Tracks scraper executions and lifecycle.

Current working design distinguishes successful runs from failed/incomplete runs.

### scrape_run_properties — IMPLEMENTED

Stores listing observations for scrape snapshots.

Missing-listing deactivation must only occur after a sufficiently complete and successfully persisted run.

## 3. Price History — IMPLEMENTED

### property_price_history

Observed asking-price history.

Known fields:

- id
- source
- listing_id
- price
- currency
- observed_at
- scrape_run_id
- created_at

Unique observation design:

source + listing_id + scrape_run_id

### property_price_history_view

Derived view calculating price movement.

Outputs include:

- previous_price
- current_price
- price_change
- price_change_percent
- price_direction

Price history records asking observations, not completed transactions.

## 4. Apartment Identity — IMPLEMENTED

### apartments

Physical-apartment identity layer.

The table intentionally began minimal.

Known concepts:

- id
- apartment_code
- created_at
- updated_at

Apartment codes are generated with PostgreSQL sequence/default logic.

### apartment_listings

Maps source listings to LocationOS apartment identities.

Known fields/concepts:

- apartment_id
- source
- listing_id
- match_status
- match_confidence
- timestamps

The source listing remains independently identified by source + listing_id.

One apartment may eventually have multiple source listings, but fuzzy cross-listing matching is not yet complete.

## 5. Canonical Building Information — TABLE CREATED

### buildings

Reserved for stronger/canonical building information.

Known fields:

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

Last verified count:

0 buildings.

Do not fill canonical facts from weak listing inference.

## 6. Apartment / Canonical Building Relationship — TABLE CREATED

### apartment_buildings

Known fields/concepts:

- apartment_id
- building_id
- match_status
- match_confidence
- match_method
- created_at
- updated_at

Last verified count:

0 rows.

## 7. Listing-Derived Building Entity — NEXT TABLE

### building_entities — PLANNED / IMMEDIATE NEXT STEP

Purpose:

Represent an inferred building identity derived from listing evidence before canonical building information is known.

Proposed first-pass fields:

- id BIGINT identity primary key
- building_code TEXT unique not null
- canonical_name TEXT nullable
- normalized_name TEXT nullable
- location TEXT nullable
- standard_location TEXT nullable
- address_text TEXT nullable
- match_confidence DOUBLE PRECISION nullable
- match_method TEXT nullable
- first_seen_at TIMESTAMPTZ
- last_seen_at TIMESTAMPTZ
- created_at TIMESTAMPTZ
- updated_at TIMESTAMPTZ

Before creating this table:

1. inspect production schema
2. confirm it does not already exist
3. review relationship strategy
4. propose migration SQL
5. obtain human approval
6. execute
7. verify
8. only then connect application code

## 8. Recommended Relationship Model

Conceptual target:

properties / source listings
        ↓
apartment_listings
        ↓
apartments
        ↓
listing-derived building identity / matching
        ↓
building_entities
        ↓
verification / public enrichment
        ↓
buildings

The exact foreign-key/mapping design between apartments, building_entities, and canonical buildings still requires an explicit migration decision.

Do not silently overload apartment_buildings for a different concept.

## 9. Building Evidence

Listing-derived evidence may come from:

- title
- description
- normalized location
- standard_location
- address/road clues
- breadcrumbs / structured address data
- nearby landmarks
- agent/source patterns
- amenities as supporting evidence
- unit characteristics as supporting evidence
- images later
- GPS later

Canonical/public evidence may later come from:

- Property24 project/development information where appropriate
- HassConsult
- public building/developer/project sources
- verified direct submissions
- other approved sources

## 10. Historical / Provenance Principle

The database must preserve:

- what was observed
- when it was observed
- source/provenance
- what was derived
- confidence
- human verification where applicable
- unknown where evidence is insufficient

Do not overwrite useful historical evidence merely because a newer observation exists.

## 11. Database Safety

Before any production schema change:

1. inspect schema
2. explain purpose
3. identify affected application code
4. prepare SQL
5. review
6. obtain human approval
7. execute
8. verify
9. update code
10. test controlled sample

Never automatically perform destructive operations or identity changes.
