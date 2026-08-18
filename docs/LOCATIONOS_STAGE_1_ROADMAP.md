# LocationOS Stage 1 Roadmap

## Stage 1 Objective

Stage 1 focuses on building the foundation of LocationOS around
Nairobi apartments.

The objective is to move from fragmented property listings toward a
structured system that understands:

Listing
→ Apartment
→ Building
→ Location
→ Market
→ Investment

Stage 1 should prioritize data quality, identity resolution,
historical tracking, provenance, and confidence before advanced AI
features.

---

# PHASE A — DATA FOUNDATION

## Step 1 — Source Listing Collection

Collect property listings from approved sources.

Current primary source:

BuyRentKenya.

Current listing types:

- Sale
- Rent

The scraper should collect available listing information and images.

Important source information includes:

- source
- listing ID
- URL
- title
- description
- listing type
- price
- currency
- bedrooms
- bathrooms
- location
- agent information
- listing dates
- source images

The source listing remains an observation.

---

## Step 2 — Extraction

Extract structured information from source pages.

Current extraction includes structured data such as:

- Product
- Accommodation
- RealEstateListing
- RealEstateAgent

The extractor should remain resilient to missing fields.

Missing information should remain unknown rather than being fabricated.

---

## Step 3 — Normalization

Normalize source information into consistent LocationOS fields.

Current normalization areas include:

- location
- bedrooms
- bathrooms
- pricing
- amenities
- property information

Normalization should make data consistent without destroying useful
source evidence.

---

## Step 4 — Property Storage

Store normalized source listings in Supabase.

Current source identity:

source + listing_id

This identity must be protected by an appropriate uniqueness
constraint.

Property records should be updated rather than blindly duplicated
when the same source listing is encountered again.

---

## Step 5 — Property Images

Store source property images.

Images should be associated with the appropriate listing.

The system should preserve:

- listing ID
- image URL
- image order
- source relationship

Images are important future evidence for:

- apartment matching
- building matching
- duplicate detection
- visual analysis

---

# PHASE B — SCRAPE HISTORY AND DATA LIFECYCLE

## Step 6 — Scrape Run Tracking

Each scraper execution should have a scrape-run record.

A scrape run should track information such as:

- run ID
- source
- status
- start time
- completion time
- number of properties found

The system should distinguish successful runs from incomplete or
failed runs.

---

## Step 7 — Scrape Snapshots

Each completed scrape should record the listings observed during
that run.

The snapshot relationship is:

Scrape Run
→ Listings observed during that run

This allows LocationOS to compare different observations over time.

Current snapshot system has been tested with:

999/999 listings successfully processed.

---

## Step 8 — Missing Listing Detection

After a sufficiently complete successful scrape, compare the current
snapshot with previous observations.

If a previously observed listing is absent from a later complete
snapshot, it may be marked inactive.

Important safety rule:

Incomplete scrapes must not cause mass deactivation of existing
properties.

A listing should not be marked inactive merely because a scraper
failed or processed an incomplete dataset.

---

## Step 9 — Price History

Track changes in asking prices over time.

Example:

January    12.0M
March      11.7M
May        11.2M
August     10.8M

Price history should allow LocationOS to understand:

- price reductions
- price increases
- pricing duration
- price movement
- negotiation signals
- historical asking behavior

The historical record should not be replaced merely because the
current price changed.

---

# PHASE C — PROPERTY IDENTITY

## Step 10 — Apartment Identification

Introduce the distinction between:

Listing

and:

Apartment.

A listing represents a source observation.

An apartment represents a physical residential unit.

One apartment may eventually have multiple listings.

Therefore:

Listing ≠ Apartment

Create stable internal Apartment IDs when sufficient evidence exists.

---

## Step 11 — Apartment Matching Engine

Attempt to determine whether different listings represent the same
physical apartment.

Potential evidence:

- GPS or approximate location
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

The matching engine should produce evidence and confidence.

Low confidence must not result in forced merging.

Unknown is an acceptable and preferred outcome when evidence is weak.

---

# PHASE D — BUILDING INTELLIGENCE

## Step 12 — Building Identification

Create internal building identifiers when the actual building name is
unknown.

Examples:

BLD-00001
BLD-00002
BLD-00003

The internal ID represents an entity identified by LocationOS.

It does not imply that the official building name is known.

---

## Step 13 — Building Matching Engine

Attempt to associate apartments/listings with buildings.

Example:

BLD-00017 → 91%
BLD-00102 → 67%
BLD-00054 → 31%

Potential evidence:

- GPS or approximate location
- exterior photos
- interior photos
- building appearance
- number of floors
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

Critical rule:

Low confidence = no forced match.

A property may remain:

Unknown building.

---

## Step 14 — Building Information

Once a building has sufficient identification confidence, create its
profile.

Potential information:

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
- Other facilities
- Property manager
- Management information

The building becomes a central anchor connecting apartments.

---

# PHASE E — APARTMENT INFORMATION

## Step 15 — Apartment Information Layer

Each apartment may eventually contain:

- Apartment ID
- Building ID
- Floor
- Unit number where known
- Bedrooms
- Bathrooms
- Size
- Balcony
- Furnished
- Parking
- Condition where known
- Year built
- Photos
- Current status

The system must distinguish observed values from estimated or
derived values.

---

# PHASE F — LOCATION INTELLIGENCE

## Step 16 — Location Intelligence

Connect apartments/buildings to their surrounding environment.

Potential relationships:

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

Location intelligence should primarily attach to the
building/location to avoid unnecessary duplication.

---

# PHASE G — MARKET INTELLIGENCE

## Step 17 — Market Intelligence

Build neighborhood-level market intelligence.

Potential indicators:

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

The intended hierarchy is:

Apartment
→ Building
→ Neighborhood
→ Nairobi market

---

# PHASE H — TRANSACTIONS

## Step 18 — Transaction Data

Eventually collect or integrate transaction evidence.

Transaction information may include:

- transaction date
- transaction price
- property
- apartment
- building
- transaction type
- source
- confidence

Transactions are important because asking prices are not the same as
actual transaction prices.

Transaction data should therefore be clearly distinguished from
listing observations.

---

# PHASE I — INVESTMENT INTELLIGENCE

## Step 19 — Investment Calculations

Calculate:

### Gross rental yield

Annual rent
────────────── × 100
Property value

### Net yield

Rent
- vacancy
- service charges
- management
- maintenance
- other applicable costs
────────────────────────────
Investment value

### Price per square metre

Property price
───────────────
Apartment size

### Rent per square metre

Monthly rent
────────────
Apartment size

Derived calculations must identify their underlying evidence.

---

## Step 20 — Liquidity Score

Estimate how easily an apartment can be resold.

Potential inputs:

- days on market
- area
- building
- unit type
- price bracket
- historical transactions

Example:

Liquidity: 84/100

The system should explain the score.

---

## Step 21 — Off-Plan Risk

For off-plan properties/projects, evaluate:

- developer history
- previous completion
- delivery delays
- project performance
- historical reliability

Output:

Low
Medium
High

The system should not produce strong risk conclusions when
insufficient developer/project data exists.

---

## Step 22 — Investment Score

An initial framework:

Yield — 40%
Appreciation — 30%
Vacancy risk — 20%
Liquidity — 10%

This should eventually become dynamic according to investor
objectives.

Examples:

Income investor:
Prioritize yield.

Capital appreciation investor:
Prioritize appreciation.

Conservative investor:
Prioritize liquidity and risk.

The objective is:

Best apartment for this particular investor.

---

# PHASE J — DATA CONFIDENCE

## Step 23 — Data Confidence

Every major intelligence output should eventually have a confidence
measure.

Example:

Fair value:
KES 11.4M

Confidence:
91%

Evidence:

- 14 comparable properties
- 6 transaction records
- strong building match
- recent price information

Another property may have:

Fair value:
KES 11.4M

Confidence:
43%

Because:

- only 2 comparable listings
- no transaction data
- weak building identification

Confidence should reflect evidence quality.

---

# PHASE K — AI DATA STEWARD

## Step 24 — AI Data Steward

Once sufficient data exists, continuously monitor:

- duplicates
- contradictions
- suspicious prices
- missing information
- outdated records
- bad building matches
- unusual changes
- normalization problems
- data quality problems

Low-risk formatting and normalization issues may eventually be
automatically corrected.

Important factual changes should require evidence and, when necessary,
human review.

---

# PHASE L — APARTMENT INTELLIGENCE

## Step 25 — Apartment Intelligence Page

The final Stage 1 objective is an apartment intelligence interface.

Example:

Apartment
2BR — Kilimani

Current asking:
KES 11.2M

Estimated fair value:
KES 10.6–11.0M

Gross yield:
7.8%

Estimated net yield:
6.4%

Liquidity:
81/100

Investment score:
86/100

Building:
BLD-00127

Developer:
XYZ

Data confidence:
92%

Airbnb potential:
High

Market trend:
Positive

RECOMMENDATION:
Negotiate

The system should explain the reasoning behind the assessment.

---

# DATA TRUST MODEL

Throughout Stage 1, LocationOS must preserve the distinction between:

1. Observed fact
2. Derived metric
3. AI estimate
4. Human verified information
5. Unknown

This distinction is mandatory for trustworthy real-estate intelligence.

---

# DEVELOPMENT PRINCIPLE

LocationOS does not need to perfectly collect every possible field
before moving forward.

The development process is:

Collect
→ Structure
→ Enrich
→ Verify
→ Calculate
→ Learn
→ Update

Each stage should strengthen the previous stages.

---

# CURRENT POSITION

LocationOS has completed substantial portions of the data foundation.

Current verified capabilities include:

- BuyRentKenya listing collection
- extraction
- normalization
- Supabase storage
- property upsert/update
- duplicate protection
- image extraction
- image storage
- last_seen_at tracking
- scrape-run tracking
- scrape snapshots
- missing-listing detection

A full test was successfully completed with:

999/999 listings.

The next major roadmap item after the current foundation is:

Price History

However, advanced roadmap work should only begin after the current
foundation remains stable and documented.

---

# FINAL STAGE 1 FLOW

The intended Stage 1 progression is:

Source Listings
→ Extraction
→ Normalization
→ Property Database
→ Images
→ Scrape History
→ Price History
→ Apartment Identity
→ Apartment Matching
→ Building Identification
→ Building Matching
→ Building Information
→ Apartment Information
→ Location Intelligence
→ Market Intelligence
→ Transactions
→ Investment Calculations
→ Liquidity
→ Off-Plan Risk
→ Investment Score
→ Data Confidence
→ AI Data Steward
→ Apartment Intelligence
