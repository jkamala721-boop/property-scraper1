# LocationOS Architecture

## 1. Purpose

LocationOS is a real-estate intelligence platform.

The first implementation focuses on Nairobi apartments.

The objective is to transform fragmented property listings and
real-estate data into structured property intelligence.

LocationOS should eventually allow the system to understand the
relationship between:

Listing
→ Apartment
→ Building
→ Location
→ Neighborhood
→ Market
→ Investment

LocationOS is therefore fundamentally different from a conventional
property-listing portal.

A listing is an observation of a property.

The long-term objective is to identify the underlying physical
apartment and building represented by those observations.

---

## 2. Core Architecture

The intended high-level architecture is:

REPOSITORIES / DATA SOURCES
        ↓
LISTINGS
        ↓
LISTING IDENTIFICATION
        ↓
NORMALIZATION
        ↓
APARTMENT MATCHING
        ↓
BUILDING MATCHING
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

---

## 3. Listing Layer

A listing represents an individual source observation.

A listing may come from:

- BuyRentKenya
- future property portals
- future direct property sources
- future transaction sources
- other approved real-estate data sources

The current primary source is:

BuyRentKenya.

Each source listing should retain:

- source
- source listing ID
- source URL
- listing type
- raw/observed information where appropriate
- extraction timestamp
- last-seen information
- source images where available

The current source identity is:

source + listing_id

This identity must remain stable.

---

## 4. Normalization Layer

Raw source information should not immediately become assumed facts.

The normalization layer converts inconsistent source information into
structured fields.

Examples include:

- location
- bedrooms
- bathrooms
- pricing
- amenities
- property characteristics

Normalization should make data consistent while preserving the
distinction between the original observation and the normalized
representation.

Normalization must not fabricate information.

Unknown information should remain unknown.

---

## 5. Apartment Layer

An apartment represents the underlying physical residential unit.

The long-term apartment record may contain:

- Apartment ID
- Building ID
- Floor
- Unit number
- Bedrooms
- Bathrooms
- Size
- Balcony
- Furnished status
- Parking
- Condition
- Year built
- Photos
- Current status

The apartment layer is different from the listing layer.

One physical apartment may eventually have multiple listings over time.

Therefore:

Listing ≠ Apartment

A listing may be linked to an apartment when sufficient evidence exists.

---

## 6. Apartment Matching

The matching engine attempts to determine whether multiple listings
represent the same physical apartment.

Potential evidence includes:

- GPS or approximate location
- building location
- apartment size
- bedrooms
- bathrooms
- floor
- unit number
- price
- description similarity
- photographs
- amenities
- parking
- furnished status
- other identifying characteristics

The matching system should produce evidence and confidence.

It must not force a match when evidence is insufficient.

Low-confidence cases should remain unresolved rather than being
incorrectly merged.

---

## 7. Building Layer

A building is the central physical anchor connecting multiple
apartments.

Initially, buildings may not have reliable names.

Therefore LocationOS can create internal identifiers such as:

BLD-00001
BLD-00002
BLD-00003

These IDs represent system-created building entities and do not
necessarily imply that the official building name is known.

A building profile may eventually contain:

- Building ID
- Building name
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

---

## 8. Building Matching Engine

Building identification is one of the most difficult parts of
LocationOS.

Listings may hide:

- building name
- exact location
- unit number

Therefore LocationOS must not assume the building.

The matching engine may produce results such as:

BLD-00017 → 91%
BLD-00102 → 67%
BLD-00054 → 31%

Potential evidence includes:

- GPS or approximate location
- exterior photographs
- interior photographs
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
- description similarities

Important rule:

Low confidence = no forced match.

The property can remain:

Unknown building.

This protects the integrity of the database.

---

## 9. Pricing Layer

The pricing layer records current and historical pricing information.

For rental properties:

- Asking rent
- Actual rent where available
- Service charge
- Listing date
- Date rented where available
- Rent per square metre

For sale properties:

- Asking sale price
- Actual sale price where available
- Listing date
- Date sold where available
- Sale price per square metre

Pricing should preserve historical observations.

The system should eventually understand price movement rather than only
the current asking price.

Example:

January    12.0M
March      11.7M
May        11.2M
August     10.8M

This enables analysis of:

- price reductions
- price movement
- pricing trends
- negotiation signals
- historical asking behavior

---

## 10. Location Intelligence

Location intelligence should primarily be attached to the physical
building/location rather than repeatedly duplicating the same
information for every apartment.

Potential location relationships include:

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

Location intelligence should allow LocationOS to understand the
environment surrounding an apartment.

---

## 11. Market Intelligence

LocationOS should eventually aggregate information at the
neighborhood and market level.

Potential indicators include:

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

The intended relationship is:

Apartment
    ↓
Building
    ↓
Neighborhood
    ↓
Nairobi market

---

## 12. Investment Engine

Once sufficient structured and historical data exists, LocationOS
can calculate investment metrics.

### Gross Rental Yield

Annual rent
────────────── × 100
Property value

### Net Yield

Rent
- vacancy
- service charges
- management
- maintenance
- other applicable costs
────────────────────────────
Investment value

### Price per Square Metre

Property price
───────────────
Apartment size

### Rent per Square Metre

Monthly rent
────────────
Apartment size

These calculations must clearly distinguish observed values from
derived metrics.

---

## 13. Liquidity Score

LocationOS should eventually estimate how easily an apartment can be
resold.

Potential inputs include:

- days on market
- area
- building
- unit type
- price bracket
- historical transactions

Example:

Liquidity: 84/100

The score should be accompanied by an explanation of the evidence
behind it.

---

## 14. Off-Plan Risk

For off-plan properties and developments, LocationOS should eventually
evaluate:

- developer history
- previous project completion
- delivery delays
- project performance
- historical reliability

The output may eventually be:

Low
Medium
High

This capability should only become strong after sufficient
developer/project data has been collected.

---

## 15. Investment Score

LocationOS may eventually calculate a combined investment score.

An initial conceptual framework is:

Yield — 40%
Appreciation — 30%
Vacancy risk — 20%
Liquidity — 10%

However, this should eventually become investor-dependent.

Examples:

Income investor:
Greater weighting toward yield.

Capital appreciation investor:
Greater weighting toward appreciation.

Conservative investor:
Greater weighting toward liquidity and risk.

The long-term objective is not to identify one universally "best"
apartment.

The objective is:

Best apartment for this particular investor.

---

## 16. Data Confidence

Data confidence must exist throughout the system.

Example:

Apartment A

Fair value: KES 11.4M
Confidence: 91%

Evidence:

- 14 comparable properties
- 6 transaction records
- strong building match
- recent price information

Another property may have:

Fair value: KES 11.4M
Confidence: 43%

Because:

- only 2 comparable listings
- no transaction data
- weak building identification

Confidence should communicate how strong the underlying evidence is.

It should not be confused with certainty.

---

## 17. Data Provenance

LocationOS should preserve the distinction between:

### Observed fact

Directly obtained from a source.

### Derived metric

Calculated from observed data.

### AI estimate

Produced by an analytical model.

### Human verified

Confirmed by a human or trusted verification process.

### Unknown

The system does not have sufficient evidence.

This distinction is fundamental to LocationOS trustworthiness.

---

## 18. AI Data Steward

Once the database becomes sufficiently large, an AI Data Steward can
continuously monitor data quality.

It should look for:

- duplicates
- contradictions
- suspicious prices
- missing information
- outdated records
- bad building matches
- unusual changes
- normalization problems
- data quality issues

Low-risk formatting and normalization problems may eventually be
automatically corrected.

Important factual changes should require evidence and, where
appropriate, human review.

---

## 19. Apartment Intelligence

The eventual apartment page should not look like a conventional
listing page.

It should function as an investment intelligence interface.

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

REOS assessment:
Negotiate

The system should explain why it reached the assessment.

---

## 20. Iterative Development Principle

LocationOS does not need to collect 100% of every possible field
before moving forward.

The intended process is:

Collect
→ Structure
→ Enrich
→ Verify
→ Calculate
→ Learn
→ Update

The architecture should therefore support incremental improvement.

The database should preserve historical information whenever
practical rather than repeatedly replacing useful evidence.

---

## 21. Long-Term Relationship

The intended final relationship is:

                    LocationOS
                        │
                    LISTINGS
                        │
                   Listing IDs
                        ↓
                 MATCHING ENGINE
                        ↓
                    APARTMENT
                        │
              ┌─────────┴─────────┐
              ↓                   ↓
           BUILDING             PRICES
              │                   │
              ↓                   ↓
          DEVELOPER             HISTORY
              │
              ↓
           LOCATION
              │
              ↓
            MARKET
              │
              ↓
            AIRBNB
              │
              ↓
         TRANSACTIONS
              │
              ↓
       INVESTMENT ENGINE
              │
              ↓
     APARTMENT INTELLIGENCE

This architecture is the long-term direction.

The current implementation represents only the foundation of this
architecture.
