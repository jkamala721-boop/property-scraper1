# LocationOS Database Architecture

## 1. Purpose

This document describes the current database architecture used by
LocationOS.

It documents the database structures that have been implemented and
verified at the current development checkpoint.

It must not be interpreted as a complete description of the future
LocationOS database.

Future capabilities such as apartment identity, building matching,
price history, transactions, market intelligence, and investment
intelligence will require additional database structures.

---

# 2. Database Platform

LocationOS currently uses:

Supabase

with:

PostgreSQL

The database is used to store structured real-estate listing data,
property images, scrape execution history, and scrape snapshots.

---

# 3. Current Database Tables

The current verified data foundation includes:

properties

property_images

scrape_runs

scrape_run_properties

These tables form the current listing and scrape-history architecture.

Future tables may include:

- apartments
- buildings
- price_history
- developers
- locations
- neighborhoods
- transactions
- market_metrics
- investment_metrics
- data_confidence
- matching_candidates

These future structures are not assumed to exist until they are
explicitly implemented and verified.

---

# 4. Properties Table

The properties table is currently the primary real-estate listing
table.

It stores normalized information about source listings.

The current system uses it as the main record for an observed source
listing.

Important conceptual fields include:

- source
- listing_id
- title
- description
- listing_type
- price
- currency
- location
- bedrooms
- bathrooms
- URL
- agent information
- posted date
- last updated date
- is_live
- last_seen_at

The exact production schema should always be verified against the
actual Supabase database before making assumptions about field names
or data types.

---

# 5. Source Listing Identity

The current source-level identity is:

source + listing_id

This means the same listing ID from different sources should not be
assumed to represent the same source record.

For example:

BuyRentKenya + 12345

and:

AnotherSource + 12345

are different source listings.

The database currently protects the source/listing relationship with
a uniqueness constraint.

The verified constraint is conceptually:

source + listing_id → UNIQUE

This is important for safe upserts.

---

# 6. Property Upsert Behavior

The scraper uses an upsert strategy for properties.

The database operation is conceptually:

properties
→ upsert
→ source + listing_id

This allows an existing source listing to be updated when it appears
again in a later scrape.

The system therefore does not need to create a completely new property
record every time the same source listing is scraped.

This is essential for:

- current property information
- last-seen tracking
- price changes
- listing lifecycle
- future price history
- historical analysis

---

# 7. Property Images Table

The property_images table stores images separately from the main
property record.

A property may have multiple images.

Current image information includes:

- listing_id
- image_url
- image_order

The scraper extracts image URLs from the source Product image field.

The database layer then uploads them to:

property_images

The current image upsert conflict relationship is:

listing_id + image_url

This prevents the same image URL from being inserted repeatedly for
the same listing.

---

# 8. Image Relationship

The current relationship is conceptually:

properties
    │
    │ listing_id
    ↓
property_images
    │
    ├── image 1
    ├── image 2
    ├── image 3
    └── image N

Images remain associated with the source listing.

Future apartment and building matching systems may use these images
as evidence.

Possible future applications include:

- apartment matching
- building matching
- duplicate detection
- building appearance analysis
- visual property analysis

These future uses are planned and are not currently fully
implemented.

---

# 9. Scrape Runs Table

The scrape_runs table records individual scraper executions.

The scraper creates a scrape-run record when a scraping operation
starts.

Conceptually, a scrape run contains:

- run ID
- source
- status
- started_at
- completed_at
- finished_at where applicable
- properties_found

A typical lifecycle is:

running
    ↓
processing
    ↓
completed

A failed or incomplete run should not be treated as equivalent to a
successful complete snapshot.

---

# 10. Scrape Run Status

The scraper currently creates a run with:

source:
BuyRentKenya

status:
running

After successful completion, the run is updated to:

status:
completed

and the number of processed properties is recorded.

The completed run is then used as the basis for missing-listing
detection.

---

# 11. Scrape Run Properties Table

The scrape_run_properties table records which listings were observed
during a particular scrape run.

The conceptual relationship is:

scrape_runs
    │
    │ run_id
    ↓
scrape_run_properties
    │
    ├── listing 1
    ├── listing 2
    ├── listing 3
    └── listing N

The current record conceptually contains:

- run_id
- source
- listing_id
- observation information where implemented

The table allows LocationOS to reconstruct which listings were
observed during a particular completed scrape.

---

# 12. Scrape Snapshot Concept

A scrape snapshot represents the set of source listings observed
during one scrape run.

Example:

Run A:

A
B
C
D
E

Later Run B:

A
B
D
E

The system can determine that:

C

was not observed in Run B.

This is fundamentally different from assuming that C was never in the
database.

The snapshot system therefore preserves historical observation.

---

# 13. Missing Listing Detection

The current system uses scrape history and last-seen information to
identify listings that were not found during a subsequent completed
scrape.

The intended logic is:

Successful scrape
    ↓
record observed listings
    ↓
compare against previous observations
    ↓
identify previously seen listings not observed
    ↓
mark appropriate listings inactive

The system must not perform mass deactivation based on an incomplete
scrape.

---

# 14. Safety Rule for Inactive Properties

The inactive-property mechanism is intentionally conservative.

A scraper failure should not mean:

"Every property not found is inactive."

Instead:

Incomplete scrape
    ↓
Do not perform destructive deactivation

Successful sufficiently complete scrape
    ↓
Compare snapshots
    ↓
Update missing listings

This protects historical data from scraper outages, blocked requests,
network problems, parsing errors, and partial source failures.

---

# 15. last_seen_at

The properties table currently uses:

last_seen_at

to record when a listing was most recently observed.

The scraper updates this field when a property is processed.

Conceptually:

listing scraped
    ↓
last_seen_at = current observation time

This field is important for:

- listing lifecycle
- missing-listing detection
- freshness
- historical observation
- future market analysis

---

# 16. Current is_live Data Type

Important verified database behavior:

The current is_live field is stored as text rather than PostgreSQL
boolean.

Therefore SQL should not assume that the field supports:

is_live = true

unless the database schema has explicitly been changed.

For current analysis, the safe approach is to inspect the stored
values directly.

Example:

SELECT
    is_live,
    COUNT(*) AS count
FROM properties
GROUP BY is_live;

Any future migration from text to boolean must be treated as an
explicit database schema change.

---

# 17. Current Database Scale

At the current development checkpoint, the properties table contains:

14,702 properties

Distribution:

Sale:
10,549

Rent:
4,151

NULL:
2

These numbers represent a development checkpoint and will change as
the scraper continues to collect data.

---

# 18. Current Scrape Snapshot Scale

The current full test scrape processed:

999 listings

Distribution of the source links used for the test:

Sale:
523

Rent:
476

Total:
999

The full scrape successfully completed:

999 / 999 properties

The associated scrape-run and snapshot verification succeeded.

The test also reported:

No properties disappeared.

This represents a known-good database checkpoint.

---

# 19. Duplicate Protection

The current property identity protection is based on:

source + listing_id

The database has a uniqueness constraint protecting this relationship.

The application uses an upsert operation rather than blindly inserting
new records.

The current verified behavior is:

same source + same listing_id
    ↓
existing record updated

different source + same listing_id
    ↓
different source listing

This distinction must be preserved.

---

# 20. Historical Data Principle

LocationOS should preserve useful historical observations.

The database should not repeatedly destroy and recreate records when
source information changes.

For example, if a property changes price:

Current listing:

KES 11,200,000

The future price-history layer should preserve previous observations
such as:

KES 12,000,000
KES 11,700,000
KES 11,200,000

The current database foundation is designed to support this future
historical layer, but a complete price-history system has not yet been
implemented.

---

# 21. Future Price History

The planned price-history structure will eventually separate:

Current property state

from:

Historical price observations

Conceptually:

properties
    │
    │ property/listing identity
    ↓
price_history
    ├── observation 1
    ├── observation 2
    ├── observation 3
    └── observation N

Future historical records may include:

- property/listing identity
- price
- currency
- price type
- observed_at
- source
- evidence/provenance

The exact schema must be designed and approved before implementation.

---

# 22. Future Apartment Database Layer

The current properties table represents source listings.

The future architecture requires a separate apartment entity.

Conceptually:

properties
    ↓
matching engine
    ↓
apartments

An apartment represents a physical residential unit.

Multiple source listings may eventually be associated with one
apartment.

This means:

listing ≠ apartment

The apartment layer is not currently fully implemented.

---

# 23. Future Building Database Layer

The future building layer will provide the physical structure linking
multiple apartments.

Conceptually:

building
    │
    ├── apartment
    ├── apartment
    ├── apartment
    └── apartment

A building may initially receive an internal identifier such as:

BLD-00001

even when the official building name is unknown.

The building matching system must preserve confidence and evidence.

Low-confidence matches should remain unresolved.

---

# 24. Future Location Layer

Location intelligence should eventually be attached primarily to
buildings and geographic entities.

Potential entities include:

- neighborhoods
- schools
- hospitals
- shopping centres
- universities
- office parks
- transport
- roads
- railways
- landmarks

The database should avoid unnecessary duplication of identical
location information across thousands of apartments.

---

# 25. Future Market Layer

Future market-level data may include:

- supply
- demand
- vacancy
- rent growth
- price growth
- new developments
- infrastructure
- population
- income indicators
- traffic
- crime indicators

Market data should be linked to geographic entities and time periods
where appropriate.

The system should preserve historical market observations rather than
only current values.

---

# 26. Future Transaction Layer

Transactions should be stored separately from asking-price listings.

This distinction is important because:

asking price ≠ actual transaction price

Future transaction data may include:

- transaction date
- transaction price
- property
- apartment
- building
- transaction type
- source
- confidence
- verification status

Transaction data will eventually strengthen:

- fair-value estimation
- investment calculations
- liquidity scoring
- market intelligence
- price analysis

---

# 27. Future Data Confidence

LocationOS should eventually associate confidence with important
intelligence outputs.

Confidence may depend on:

- quantity of comparable properties
- transaction evidence
- building-match confidence
- recency
- source reliability
- consistency between sources
- historical evidence

Confidence should communicate evidence strength.

It should not be represented as certainty.

---

# 28. Data Provenance

The database architecture should preserve provenance wherever
practical.

LocationOS should distinguish:

Observed fact

Derived metric

AI estimate

Human verified

Unknown

For example:

Observed:

asking price = KES 11.2M

Derived:

rent per square metre = KES X

AI estimate:

fair value = KES 10.6M–11.0M

Human verified:

building identity confirmed

Unknown:

actual transaction price

This distinction is fundamental to trust.

---

# 29. Database Change Policy

Database changes must be controlled.

Before adding or changing a production table or column:

1. Inspect the current schema.
2. Explain the purpose of the change.
3. Identify affected application code.
4. Prepare the SQL migration.
5. Review the migration.
6. Obtain human approval.
7. Execute the migration.
8. Verify the resulting schema.
9. Update application code.
10. Test the affected workflow.

Do not silently modify the production schema.

---

# 30. Destructive Operations

The following require explicit human approval:

- DROP TABLE
- TRUNCATE
- DELETE of historical records
- mass updates
- changing primary/unique identity
- changing column data types
- removing historical data
- rebuilding tables
- dropping indexes
- replacing production data

Codex must not perform these operations automatically.

---

# 31. Database and Application Relationship

The application should treat the database as a persistent source of
truth for stored observations.

The general flow is:

Source
    ↓
Scraper
    ↓
Extractor
    ↓
Normalizer
    ↓
Database layer
    ↓
Supabase/PostgreSQL

The database layer should handle:

- batch preparation
- upsert behavior
- image storage
- scrape-run tracking
- snapshot tracking
- lifecycle updates

Application code should not assume database structures that have not
been verified.

---

# 32. Database Testing

Database changes should be tested using controlled examples before
full scraper execution.

Preferred sequence:

1. Change schema.
2. Verify schema.
3. Test one listing.
4. Verify database record.
5. Test small batch.
6. Verify database behavior.
7. Run full scraper.
8. Verify counts and relationships.

This reduces the risk of corrupting or incorrectly updating thousands
of records.

---

# 33. Current Known-Good Database Checkpoint

The current database foundation has been tested with:

14,702 existing properties

and a full:

999-listing

scrape.

The successful scrape produced:

- property updates
- image records
- scrape-run records
- scrape snapshot records

The system completed successfully.

No properties disappeared during the tested snapshot comparison.

This is the current known-good baseline.

---

# 34. Current Database Status

Current verified components:

properties
    IMPLEMENTED

property_images
    IMPLEMENTED

scrape_runs
    IMPLEMENTED

scrape_run_properties
    IMPLEMENTED

property upsert
    IMPLEMENTED

duplicate protection
    IMPLEMENTED

image upsert
    IMPLEMENTED

last_seen_at
    IMPLEMENTED

scrape snapshot tracking
    IMPLEMENTED

missing-listing detection
    TESTED

price history
    PLANNED

apartments
    PLANNED

buildings
    PLANNED

transactions
    PLANNED

market intelligence
    PLANNED

investment intelligence
    PLANNED

---

# 35. Important Rule for Codex

The actual Supabase schema is authoritative.

This document describes the verified architecture and known behavior.

If this document conflicts with the actual production schema:

1. Do not guess.
2. Inspect the actual schema.
3. Report the discrepancy.
4. Ask for clarification when necessary.
5. Do not silently change production data.

The same principle applies to application code.

---

# 36. Long-Term Database Relationship

The intended long-term structure is approximately:

SOURCE LISTINGS
      │
      ↓
LISTING IDENTITY
      │
      ↓
MATCHING ENGINE
      │
      ↓
APARTMENT
      │
      ├──────────────→ PRICE HISTORY
      │
      ↓
BUILDING
      │
      ├──────────────→ DEVELOPER
      │
      ↓
LOCATION
      │
      ↓
NEIGHBORHOOD
      │
      ↓
MARKET
      │
      ↓
TRANSACTIONS
      │
      ↓
INVESTMENT ENGINE
      │
      ↓
APARTMENT INTELLIGENCE

The database should evolve toward this architecture incrementally.

---

# 37. Core Database Principle

LocationOS should preserve information rather than unnecessarily
replace it.

The system should be able to answer:

What did we observe?

When did we observe it?

Where did it come from?

How confident are we?

What did we derive from it?

What changed over time?

This is the foundation required for trustworthy real-estate
intelligence.
