# LocationOS — Codex Engineering Instructions

## 1. Project Identity

This project is called LocationOS.

LocationOS is a real-estate intelligence platform beginning with
Nairobi apartments.

LocationOS is not simply a property-listing website.

Its purpose is to transform fragmented real-estate listings and
other real-estate data into structured, verified, and useful
real-estate intelligence.

The long-term relationship is:

Listing
→ Listing ID
→ Matching Engine
→ Apartment
→ Building
→ Location
→ Market
→ Investment Intelligence

---

## 2. Current Stage

The current product stage is:

Stage 1 — Nairobi Apartments.

The initial source currently being scraped is:

BuyRentKenya.

The scraper currently collects listing information and property
images and stores structured information in Supabase.

Do not assume that future data sources or future stages are already
implemented.

---

## 3. Current Working Systems

The repository currently contains working functionality for:

- BuyRentKenya listing collection
- Listing extraction
- Property normalization
- Location normalization
- Bedroom normalization
- Bathroom normalization
- Amenity normalization
- Property storage in Supabase
- Existing-property upsert/update
- Duplicate protection
- Property image extraction
- Property image storage
- last_seen_at tracking
- Scrape-run tracking
- Scrape snapshots
- Detection of listings missing from a completed scrape
- GitHub-based project management

The current implementation has been tested with:

999/999 listings successfully scraped.

Do not rebuild these systems unnecessarily.

---

## 4. Engineering Philosophy

Before changing code:

1. Inspect the existing implementation.
2. Understand how the relevant components interact.
3. Identify the smallest safe change.
4. Make the change.
5. Run appropriate tests.
6. Verify that existing functionality still works.

Do not rewrite working systems merely to make the code look
different.

Prefer incremental, reversible changes over large rewrites.

If an existing implementation is working, preserve its behavior unless
there is a demonstrated reason to change it.

---

## 5. Database Safety

LocationOS uses Supabase/PostgreSQL.

The production database contains historical real-estate data.

Never:

- delete production property data without explicit approval
- truncate production tables
- automatically change the production schema
- automatically create database columns from Python
- drop tables
- change column types without explicit approval
- run destructive SQL without explicit approval

If a database schema change is required:

1. Explain why the change is required.
2. Provide the proposed SQL.
3. Wait for human approval.
4. The SQL can then be executed manually.
5. Verify the result.
6. Only then modify application code if necessary.

---

## 6. Secrets and Credentials

Never expose, print, commit, or document:

- Supabase service-role keys
- Supabase API keys
- passwords
- access tokens
- GitHub tokens
- .env contents
- other credentials

Never commit `.env`.

Use `.env.example` when documentation of environment variables is
needed.

---

## 7. Data Integrity

LocationOS must preserve the distinction between:

- Observed fact
- Derived metric
- AI estimate
- Human verified information
- Unknown

Never fabricate missing property information.

If information cannot be reliably established, use:

Unknown

or the appropriate null representation.

Do not infer a building merely because a listing appears to be nearby.

Low-confidence building matches must remain:

Unknown building.

---

## 8. Property Identity

A source listing is currently identified using:

source + listing_id

This identity must be preserved.

Do not introduce a different property identity model without
understanding the existing database and obtaining approval.

A source listing and a physical apartment are not necessarily the same
thing.

Future architecture will distinguish:

Listing
→ Apartment
→ Building

Multiple listings may eventually represent the same physical
apartment.

---

## 9. Building Matching

Building identification is a major LocationOS capability.

Possible evidence includes:

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

The system must not force a building match when confidence is low.

A confidence score should be treated as evidence, not certainty.

---

## 10. Images

Property images are important data.

Do not remove or overwrite image records without understanding their
relationship to the property.

Images may later be used for:

- building identification
- apartment matching
- duplicate detection
- property intelligence
- visual analysis

Preserve image provenance whenever possible.

---

## 11. Scraping

The scraper currently works with BuyRentKenya.

Do not make changes that unnecessarily disrupt:

- request handling
- retry behavior
- extraction
- normalization
- batching
- database uploads
- image collection
- scrape-run tracking

A scraper failure must not automatically cause existing properties
to become inactive.

Inactive-property detection should only operate after a sufficiently
complete and successful scrape.

---

## 12. Scrape Snapshots

LocationOS records properties found during scrape runs.

The purpose is to distinguish:

Property was never part of a monitored snapshot

from:

Property was previously observed but disappeared from a later
successful snapshot.

Never mark thousands of historical properties inactive merely because
they are absent from a partial or incomplete scrape.

---

## 13. Testing Rules

Before a large scraper run:

- test the relevant code on a small number of listings
- verify database behavior
- verify images when relevant
- verify snapshot behavior
- verify that failures do not cause destructive updates

After Python changes, run an appropriate syntax check.

For example:

python3 -m py_compile filename.py

For meaningful changes, run the project's available tests.

Never assume that code works merely because it looks correct.

---

## 14. Git Rules

Do not casually rewrite Git history.

Before significant changes:

- inspect git status
- inspect relevant commits
- understand whether local and remote branches differ

Do not run:

- git reset --hard
- git rebase
- git push --force

unless explicitly instructed and the consequences are understood.

Prefer small commits with descriptive messages.

---

## 15. Documentation

When implementing a significant LocationOS capability, update the
relevant documentation under:

docs/

Documentation should reflect the actual implementation.

Do not document planned functionality as if it already exists.

Clearly distinguish:

Implemented
In progress
Planned

---

## 16. LocationOS Stage 1 Architecture

The intended architecture is:

REOS listings
→ Listing IDs
→ Matching Engine
→ Apartment IDs
→ Building
→ Pricing
→ Price History
→ Location
→ Market
→ Transactions
→ Investment Engine
→ Apartment Intelligence

The project should evolve iteratively.

The goal is not to collect every possible field before producing value.

The intended process is:

Collect
→ Structure
→ Enrich
→ Verify
→ Calculate
→ Learn
→ Update

---

## 17. Development Behavior

When asked to implement a feature:

1. Inspect relevant files first.
2. Explain the current implementation briefly.
3. Identify dependencies and risks.
4. Propose the smallest safe implementation.
5. Do not modify unrelated files.
6. Implement.
7. Test.
8. Report exactly what changed.
9. Report any assumptions or remaining risks.

If the requested approach is unsafe or technically weak, say so
clearly and propose a safer alternative.

Do not blindly follow a technically incorrect instruction.

---

## 18. Human Approval Required

Ask for approval before:

- production database schema changes
- destructive database operations
- deleting historical data
- changing the core property identity model
- major scraper rewrites
- changing Git history
- changing production infrastructure
- introducing irreversible migrations

---

## 19. Current Priority

The immediate priority is to preserve and strengthen the existing
LocationOS data foundation.

Do not jump ahead to advanced AI intelligence features simply because
they appear in the long-term roadmap.

The foundation must remain reliable before higher-level intelligence is
built on top of it.
