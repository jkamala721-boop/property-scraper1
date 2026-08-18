# LocationOS Current State

## Purpose

This document describes the actual implementation state of LocationOS
at the current development checkpoint.

It must be treated as a snapshot of what is implemented and verified,
not as a description of future functionality.

Status labels:

- IMPLEMENTED — working and verified
- TESTED — specifically tested successfully
- IN PROGRESS — currently being developed
- PLANNED — not yet implemented
- UNKNOWN — implementation state has not been verified

---

# 1. Current Product Scope

LocationOS is currently focused on:

Nairobi apartment real-estate data.

Current primary source:

BuyRentKenya.

Current listing categories:

- Sale
- Rent

The present system is primarily a data collection, normalization,
storage, image collection, and scrape-history foundation.

Advanced investment intelligence is not yet fully implemented.

---

# 2. Current Database Size

At the current checkpoint, the Supabase database contains:

Total properties:
14,702

Property distribution:

Sale:
10,549

Rent:
4,151

NULL listing type:
2

These numbers represent the current database state and should not be
assumed to remain constant as scraping continues.

---

# 3. Current Scrape Test

The current links file contained:

Sale listings:
523

Rent listings:
476

Total:
999

A full scraper test was successfully completed.

Result:

999 / 999 properties processed.

This is an important verified checkpoint.

---

# 4. Current Scraper

Primary scraper:

scraper.py

Current responsibilities include:

- reading listing records
- identifying listing type
- requesting source pages
- checking whether a listing is available
- retrying failed requests
- parsing HTML
- locating JSON-LD structured data
- passing extracted graph data to extractor.py
- normalizing extracted property data
- saving properties
- collecting property images
- flushing batches
- tracking scrape runs
- recording properties found during a run
- finishing the scrape run

Current status:

IMPLEMENTED

TESTED

---

# 5. Current Extractor

Primary extraction module:

extractor.py

The extractor currently identifies relevant JSON-LD entities including:

- Product
- Accommodation
- RealEstateListing
- RealEstateAgent

Current extraction includes fields such as:

- title
- description
- image URLs
- bedrooms
- bathrooms
- price
- currency
- location
- listing ID
- source
- listing type
- URL
- posted date
- last updated date
- live status
- agent name

Current status:

IMPLEMENTED

TESTED

---

# 6. Current Image Collection

Property image extraction is implemented.

Images are extracted from the Product image field.

The system supports image representations including:

- lists
- dictionaries
- strings

Image URLs are collected into:

image_urls

The database layer then stores image information in:

property_images

Current image information includes:

- listing ID
- image URL
- image order

A full scraper test successfully processed property images.

Current status:

IMPLEMENTED

TESTED

---

# 7. Current Normalization

The normalization system is implemented.

The project contains a normalize module used to transform raw extracted
property information into a structured representation.

Current normalization areas include:

- location
- bedrooms
- bathrooms
- pricing
- amenities
- property information

Normalization is performed before saving the property.

Current status:

IMPLEMENTED

TESTED

---

# 8. Current Property Storage

Properties are stored in Supabase.

The database layer performs batch uploads.

Current batch size:

100 properties

Property records are upserted using:

source + listing_id

The purpose is to update existing source listings rather than blindly
create duplicates.

The database has a uniqueness constraint protecting the source/listing
identity.

Current status:

IMPLEMENTED

TESTED

---

# 9. Current Property Image Storage

Images are stored separately from the main property record.

Current table:

property_images

The database uses:

listing_id + image_url

as the conflict target for image upserts.

This allows multiple images to belong to the same listing while
preventing duplicate image records.

Current status:

IMPLEMENTED

TESTED

---

# 10. Current Last-Seen Tracking

Properties currently receive:

last_seen_at

when they are processed by the scraper.

This allows LocationOS to determine when a listing was last observed.

Current status:

IMPLEMENTED

TESTED

---

# 11. Current Scrape Run Tracking

The database contains:

scrape_runs

A scrape run records information including:

- source
- status
- started_at
- completed_at
- properties_found

The scraper starts a run before processing listings and completes the
run after the scrape finishes.

Current status:

IMPLEMENTED

TESTED

---

# 12. Current Scrape Snapshot Tracking

The database contains:

scrape_run_properties

This table records which listings were observed during a scrape run.

The relationship is:

scrape_runs
→ scrape_run_properties

The current snapshot system was tested using the 999-listing scrape.

Expected verified result:

999 listings recorded for the completed scrape run.

Current status:

IMPLEMENTED

TESTED

---

# 13. Current Missing-Listing Detection

The scraper compares the current successful scrape against previously
observed listings.

The system can identify properties that were not seen during a later
completed scrape.

The system is designed to mark missing listings inactive only after
the relevant scrape has successfully completed.

This prevents an incomplete scrape from causing mass false
deactivation.

The 999-listing test completed successfully and reported:

No properties disappeared.

Current status:

IMPLEMENTED

TESTED

---

# 14. Current Active/Inactive Representation

The current database represents the live status field as text rather
than PostgreSQL boolean.

This is important when writing SQL.

For example, queries should not assume:

is_live = true

unless the actual database type has been changed.

The current verified SQL approach groups the values directly:

SELECT is_live, COUNT(*)
FROM properties
GROUP BY is_live;

Current status:

IMPLEMENTED

TESTED

---

# 15. Current Property Identity

The current source-level property identity is:

source + listing_id

The database contains a uniqueness constraint protecting this
relationship.

This prevents duplicate source listings from being inserted as
separate records when the same source listing is encountered again.

Current status:

IMPLEMENTED

TESTED

---

# 16. Current Database Tables

The current LocationOS data foundation uses tables including:

properties

property_images

scrape_runs

scrape_run_properties

These tables form the current listing and scrape-history foundation.

Future tables may be introduced for:

- apartments
- buildings
- price history
- locations
- transactions
- developers
- market intelligence
- investment calculations

Those future tables are not assumed to exist unless verified.

---

# 17. Current Apartment Layer

A separate physical-apartment identity layer has not yet been fully
implemented.

The system currently stores source listings.

The future architecture will distinguish:

Listing
→ Apartment

Multiple listings may eventually represent the same physical
apartment.

Current status:

PLANNED

---

# 18. Current Apartment Matching Engine

A production apartment matching engine has not yet been implemented.

The planned matching engine will eventually consider evidence such as:

- GPS
- approximate location
- building
- apartment size
- bedrooms
- bathrooms
- floor
- unit number
- price
- descriptions
- photographs
- amenities
- parking
- furnished status

Low-confidence matches should remain unresolved.

Current status:

PLANNED

---

# 19. Current Building Layer

A production building identity system has not yet been implemented.

The future system may create internal building identifiers such as:

BLD-00001
BLD-00002
BLD-00003

These IDs will represent system entities even when official building
names are unknown.

Current status:

PLANNED

---

# 20. Current Building Matching Engine

A production building matching engine has not yet been implemented.

Future evidence may include:

- GPS
- approximate location
- exterior photographs
- interior photographs
- building appearance
- floors
- amenities
- pool
- gym
- parking
- apartment size
- floor
- bedrooms
- price
- nearby landmarks
- description similarity

Low-confidence matches must remain:

Unknown building.

Current status:

PLANNED

---

# 21. Current Building Information

A complete building profile is not yet implemented.

Future building information may include:

- Building ID
- Name
- GPS
- County
- Area
- Developer
- Year built
- Number of floors
- Number of units
- Amenities
- Elevator
- Generator
- Borehole
- Swimming pool
- Gym
- CCTV
- Security
- Fiber
- Parking
- Property manager
- Management information

Current status:

PLANNED

---

# 22. Current Price History

Price history tracking is not yet implemented as a complete
historical pricing system.

The current system stores current listing information.

The future price-history system should preserve changes such as:

January:
12.0M

March:
11.7M

May:
11.2M

August:
10.8M

The historical system should allow LocationOS to analyze:

- price reductions
- price increases
- pricing duration
- price movement
- negotiation signals

Current status:

PLANNED

---

# 23. Current Location Intelligence

A complete location-intelligence layer has not yet been implemented.

Future relationships may include:

- CBD
- schools
- hospitals
- shopping centres
- universities
- office parks
- industrial areas
- bus stops
- railway
- highways
- major landmarks

Current status:

PLANNED

---

# 24. Current Market Intelligence

A complete market-intelligence layer has not yet been implemented.

Future indicators may include:

- rental demand
- vacancy
- population growth
- income indicators
- apartment supply
- new developments
- infrastructure projects
- traffic
- crime indicators
- price growth
- rent growth

Current status:

PLANNED

---

# 25. Current Transaction Layer

Actual transaction data is not currently a complete implemented
component of the system.

Future transaction information may include:

- transaction date
- transaction price
- property
- apartment
- building
- transaction type
- source
- confidence

Current status:

PLANNED

---

# 26. Current Investment Calculations

The full LocationOS investment engine has not yet been implemented.

Future calculations include:

- gross rental yield
- net rental yield
- price per square metre
- rent per square metre

Current status:

PLANNED

---

# 27. Current Liquidity Score

A production liquidity scoring system has not yet been implemented.

Future inputs may include:

- days on market
- area
- building
- unit type
- price bracket
- historical transactions

Current status:

PLANNED

---

# 28. Current Off-Plan Risk Engine

A production off-plan risk engine has not yet been implemented.

Future evidence may include:

- developer history
- project completion history
- delivery delays
- project performance
- historical reliability

Current status:

PLANNED

---

# 29. Current Investment Score

A production investment scoring system has not yet been implemented.

The conceptual future framework is:

Yield — 40%
Appreciation — 30%
Vacancy risk — 20%
Liquidity — 10%

The long-term objective is to make weighting dependent on investor
objectives.

Current status:

PLANNED

---

# 30. Current Data Confidence System

A complete data-confidence system has not yet been implemented.

Future intelligence outputs should communicate the strength of their
evidence.

Potential evidence includes:

- comparable properties
- transaction records
- building match strength
- price recency
- historical data quantity
- source quality

Current status:

PLANNED

---

# 31. Current AI Data Steward

The AI Data Steward has not yet been implemented.

Future monitoring may include:

- duplicates
- contradictions
- suspicious prices
- missing information
- outdated records
- bad building matches
- unusual changes
- normalization problems
- data-quality issues

Current status:

PLANNED

---

# 32. Current Apartment Intelligence Page

The final Apartment Intelligence interface has not yet been
implemented.

The intended interface may eventually display:

- current asking price
- estimated fair value
- gross yield
- net yield
- liquidity
- investment score
- building
- developer
- data confidence
- Airbnb potential
- market trend
- LocationOS assessment
- explanation of the assessment

Current status:

PLANNED

---

# 33. Verified Full-Scrape Checkpoint

The current development checkpoint includes a successful full scrape.

Input:

999 listings

Result:

999 / 999 properties processed.

The run completed successfully.

The system reported:

No properties disappeared.

The corresponding database verification also confirmed the expected
scrape-run and snapshot results.

This checkpoint should be treated as a known-good baseline.

---

# 34. Current Development Priority

The current priority is not to immediately implement advanced
investment intelligence.

The priority is to continue strengthening the data foundation in a
controlled sequence.

The next major planned capability is:

Price History.

Before implementing it, the current codebase and database behavior
should remain stable and documented.

---

# 35. Important Development Rule

The roadmap contains future functionality.

The current state document contains implemented functionality.

Codex must not assume that something is implemented merely because it
appears in:

LOCATIONOS_STAGE_1_ROADMAP.md

When there is a conflict:

- inspect the actual code
- inspect the actual database schema
- inspect tests
- treat verified implementation as authoritative

Do not implement a planned feature twice.

---

# 36. Current Known-Good Git Checkpoint

The current working code was committed locally and pushed to GitHub.

Current main commit:

adc1f20

Commit message:

Complete LocationOS scraping pipeline

The local branch is synchronized with:

origin/main

The only intentionally untracked runtime file is:

property_scraper.log

It should not be committed.

---

# 37. Current Repository State

Important current project components include:

AGENTS.md

scraper.py

extractor.py

database.py

normalize/

docs/

The repository should be inspected before making architectural
changes.

---

# 38. Development Principle

The current system should evolve iteratively:

Collect
→ Structure
→ Enrich
→ Verify
→ Calculate
→ Learn
→ Update

Do not sacrifice data integrity for feature speed.

The objective is a trustworthy real-estate intelligence system.
