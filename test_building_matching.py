import unittest
from types import SimpleNamespace

from building_matching import (
    AUTO_MATCH_METHOD,
    BuildingEntityProfile,
    ListingEvidence,
    REVIEW_CANDIDATE_THRESHOLD,
    STRONG_CANDIDATE_THRESHOLD,
    build_profiles_from_rows,
    match_listing,
    score_entity,
    write_auto_candidates,
)


def listing(**overrides):
    values = {
        "apartment_id": 101,
        "source": "BuyRentKenya",
        "listing_id": 5001,
        "title": "Apartment for rent",
        "description": "",
        "location": None,
        "standard_location": None,
        "agent_name": None,
        "bedrooms": None,
        "bathrooms": None,
        "price": None,
        "currency": "KES",
        "listing_type": "rent",
        "posted_date": None,
        "amenities": frozenset(),
    }
    values.update(overrides)
    return ListingEvidence(**values)


def entity(**overrides):
    values = {
        "id": 2,
        "building_code": "BENT-000002",
        "canonical_name": "Garden City",
        "normalized_name": "garden city",
        "location": "Garden Estate",
        "standard_location": None,
        "address_text": "Garden City, near Garden City Mall and Thika Road",
        "reference_listings": (),
    }
    values.update(overrides)
    return BuildingEntityProfile(**values)


class FakeRelationshipClient:
    def __init__(self, existing_pairs=()):
        self.existing_pairs = set(existing_pairs)
        self.upsert_calls = []
        self.pending_row = None

    def table(self, table_name):
        if table_name != "apartment_building_entities":
            raise AssertionError(f"Unexpected table: {table_name}")
        return self

    def upsert(self, row, *, on_conflict, ignore_duplicates):
        self.upsert_calls.append(
            {
                "row": row,
                "on_conflict": on_conflict,
                "ignore_duplicates": ignore_duplicates,
            }
        )
        self.pending_row = row
        return self

    def execute(self):
        pair = (self.pending_row["apartment_id"], self.pending_row["building_entity_id"])
        if pair in self.existing_pairs:
            return SimpleNamespace(data=[])
        self.existing_pairs.add(pair)
        return SimpleNamespace(data=[{"id": len(self.existing_pairs), **self.pending_row}])


class BuildingMatchingTests(unittest.TestCase):
    def test_only_manual_candidates_or_confirmed_relationships_seed_references(self):
        reference_rows = [
            {
                "apartment_id": apartment_id,
                "source": "BuyRentKenya",
                "listing_id": 7000 + apartment_id,
                "title": "Reference listing",
                "description": "Reference description",
            }
            for apartment_id in (201, 202, 203)
        ]
        entity_rows = [
            {
                "id": entity_id,
                "building_code": f"BENT-{entity_id:06d}",
                "canonical_name": f"Entity {entity_id}",
            }
            for entity_id in (2, 3, 4)
        ]
        relationship_rows = [
            {
                "apartment_id": 201,
                "building_entity_id": 2,
                "match_status": "candidate",
                "match_confidence": 0.99,
                "match_method": AUTO_MATCH_METHOD,
            },
            {
                "apartment_id": 202,
                "building_entity_id": 3,
                "match_status": "candidate",
                "match_confidence": 0.85,
                "match_method": "manual_multi_signal_review",
            },
            {
                "apartment_id": 203,
                "building_entity_id": 4,
                "match_status": "confirmed",
                "match_confidence": None,
                "match_method": "deterministic_v1",
            },
        ]

        _, profiles = build_profiles_from_rows(
            candidate_rows=[],
            reference_rows=reference_rows,
            entity_rows=entity_rows,
            relationship_rows=relationship_rows,
        )
        references_by_entity = {
            profile.id: [item.apartment_id for item in profile.reference_listings]
            for profile in profiles
        }

        self.assertEqual(references_by_entity[2], [])
        self.assertEqual(references_by_entity[3], [202])
        self.assertEqual(references_by_entity[4], [203])

    def test_auto_relationship_is_tracked_as_existing_but_cannot_seed_reference(self):
        candidate_rows = [
            {
                "apartment_id": 201,
                "source": "BuyRentKenya",
                "listing_id": 7201,
                "title": "Garden City apartment",
                "description": "Garden City apartment in Garden Estate",
            }
        ]
        relationship_rows = [
            {
                "apartment_id": 201,
                "building_entity_id": 2,
                "match_status": "candidate",
                "match_confidence": 1.0,
                "match_method": AUTO_MATCH_METHOD,
            }
        ]
        candidates, profiles = build_profiles_from_rows(
            candidate_rows=candidate_rows,
            reference_rows=candidate_rows,
            entity_rows=[{"id": 2, "building_code": "BENT-000002", "canonical_name": "Garden City"}],
            relationship_rows=relationship_rows,
        )

        self.assertEqual(candidates[0].existing_entity_ids, frozenset({2}))
        self.assertEqual(profiles[0].reference_listings, ())

    def test_strong_entity_name_in_title_and_location(self):
        candidate = listing(
            title="Garden City apartment for rent",
            location="Garden Estate",
        )

        decision = match_listing(candidate, [entity()])

        self.assertEqual(decision.outcome, "strong_candidate")
        self.assertGreaterEqual(decision.confidence, STRONG_CANDIDATE_THRESHOLD)

    def test_strong_description_and_address_evidence_can_produce_review_candidate(self):
        reference = listing(
            apartment_id=201,
            listing_id=6001,
            description="Riverside Drive near Arboretum centre, 9th floor, rooftop gym and pool",
            location="Riverside",
            agent_name="Example Homes",
            posted_date="2026-08-01T10:00:00+00:00",
            amenities=frozenset({"gym", "swimming_pool"}),
        )
        candidate = listing(
            description="Modern home on Riverside Drive near Arboretum centre, 9th floor, rooftop gym and pool",
            location="Riverside",
            agent_name="Example Homes",
            posted_date="2026-08-01T12:00:00+00:00",
            amenities=frozenset({"gym", "swimming_pool"}),
        )
        profile = entity(
            canonical_name="Aurora Heights",
            normalized_name="aurora heights",
            location="Riverside",
            address_text="Riverside Drive near Arboretum Centre",
            reference_listings=(reference,),
        )

        decision = match_listing(candidate, [profile])

        self.assertIn(decision.outcome, {"review_candidate", "strong_candidate"})
        self.assertGreaterEqual(decision.confidence, REVIEW_CANDIDATE_THRESHOLD)

    def test_supporting_signals_increase_confidence(self):
        candidate = listing(
            description="Garden City on 13th floor with pool, gym and parking; call 0705507369",
            location="Garden Estate",
            agent_name="Mirage Real Estate Ltd",
            posted_date="2026-08-17T12:00:00+00:00",
            amenities=frozenset({"swimming_pool", "gym", "parking"}),
        )
        reference = listing(
            apartment_id=202,
            listing_id=6002,
            description="Garden City on 13th floor with pool, gym and parking; call 0705507369",
            location="Garden Estate",
            agent_name="Mirage Real Estate Ltd",
            posted_date="2026-08-17T12:05:00+00:00",
            amenities=frozenset({"swimming_pool", "gym", "parking"}),
        )

        without_reference = score_entity(candidate, entity(reference_listings=()))
        with_reference = score_entity(candidate, entity(reference_listings=(reference,)))

        self.assertGreater(with_reference.score, without_reference.score)
        self.assertTrue(any(signal.name == "same_agent" for signal in with_reference.matched_signals))
        self.assertTrue(any(signal.name == "same_floor" for signal in with_reference.matched_signals))

    def test_bedroom_and_price_alone_do_not_match(self):
        reference = listing(apartment_id=203, listing_id=6003, bedrooms=1, price=70000)
        candidate = listing(bedrooms=1, price=70000)

        decision = match_listing(candidate, [entity(reference_listings=(reference,))])

        self.assertEqual(decision.outcome, "no_match")
        self.assertEqual(decision.confidence, 0.0)
        self.assertIn("same bedrooms", decision.weak_compatibility_signals)
        self.assertIn("same price", decision.weak_compatibility_signals)

    def test_ambiguous_entities_cause_abstention(self):
        candidate = listing(
            title="Garden City apartment for rent",
            location="Garden Estate",
        )
        first = entity(id=2, building_code="BENT-000002")
        second = entity(id=3, building_code="BENT-000003")

        decision = match_listing(candidate, [first, second])

        self.assertEqual(decision.outcome, "no_match")
        self.assertIn("ambiguity", decision.explanation)

    def test_conflicting_location_prevents_match(self):
        candidate = listing(
            title="Garden City apartment for rent",
            description="Close to Garden City Mall on Thika Road",
            location="Kilimani",
            standard_location="Kilimani",
        )

        decision = match_listing(candidate, [entity()])

        self.assertEqual(decision.outcome, "no_match")
        self.assertTrue(any(signal.name == "location_conflict" for signal in decision.conflicting_signals))

    def test_garden_city_regression(self):
        first = listing(
            apartment_id=1,
            listing_id=4045566,
            description="Furnished 1-bedroom in Garden City on 13th Floor. Close to Garden City Mall, Thika Road. Call 0705507369.",
            location="Garden Estate",
            agent_name="Mirage Real Estate Ltd",
            posted_date="2026-08-17T12:01:07+00:00",
            amenities=frozenset({"swimming_pool", "gym", "parking", "lift", "borehole"}),
        )
        second = listing(
            apartment_id=4,
            listing_id=4045574,
            description="Unfurnished 1-bedroom in Garden City on 13th Floor. Close to Garden City Mall, Thika Road. Call 0705507369.",
            location="Garden Estate",
            agent_name="Mirage Real Estate Ltd",
            posted_date="2026-08-17T12:04:58+00:00",
            amenities=frozenset({"swimming_pool", "gym", "parking", "lift", "borehole"}),
        )
        profile = entity(reference_listings=(second,))

        decision = match_listing(first, [profile])

        self.assertEqual(decision.proposed_building_code, "BENT-000002")
        self.assertEqual(decision.outcome, "strong_candidate")
        self.assertGreaterEqual(decision.confidence, STRONG_CANDIDATE_THRESHOLD)

    def test_strong_candidate_is_written_as_candidate_with_structured_evidence(self):
        decision = match_listing(
            listing(title="Garden City apartment", location="Garden Estate"),
            [entity()],
        )
        client = FakeRelationshipClient()

        result = write_auto_candidates(client, [decision])

        self.assertEqual(result["inserted_count"], 1)
        self.assertEqual(len(client.upsert_calls), 1)
        call = client.upsert_calls[0]
        row = call["row"]
        self.assertEqual(call["on_conflict"], "apartment_id,building_entity_id")
        self.assertTrue(call["ignore_duplicates"])
        self.assertEqual(row["match_status"], "candidate")
        self.assertEqual(row["match_method"], AUTO_MATCH_METHOD)
        self.assertEqual(row["match_confidence"], decision.confidence)
        self.assertEqual(row["evidence"]["source"], "BuyRentKenya")
        self.assertEqual(row["evidence"]["listing_id"], 5001)
        self.assertEqual(row["evidence"]["entity"]["code"], "BENT-000002")
        self.assertEqual(row["evidence"]["matcher"]["score"], decision.confidence)

    def test_review_and_no_match_are_not_written(self):
        review = match_listing(
            listing(description="Garden City apartment", location="Garden Estate"),
            [entity()],
        )
        no_match = match_listing(
            listing(bedrooms=2, price=100000),
            [entity(reference_listings=(listing(apartment_id=202, bedrooms=2, price=100000),))],
        )
        client = FakeRelationshipClient()

        result = write_auto_candidates(client, [review, no_match])

        self.assertEqual(review.outcome, "review_candidate")
        self.assertEqual(no_match.outcome, "no_match")
        self.assertEqual(result["inserted_count"], 0)
        self.assertEqual(result["ineligible_skipped_count"], 2)
        self.assertEqual(client.upsert_calls, [])

    def test_ambiguous_candidate_is_not_written(self):
        candidate = listing(title="Garden City apartment", location="Garden Estate")
        decision = match_listing(
            candidate,
            [entity(id=2, building_code="BENT-000002"), entity(id=3, building_code="BENT-000003")],
        )
        client = FakeRelationshipClient()

        result = write_auto_candidates(client, [decision])

        self.assertIn("ambiguity", decision.explanation)
        self.assertEqual(result["inserted_count"], 0)
        self.assertEqual(client.upsert_calls, [])

    def test_conflicting_location_is_not_written(self):
        decision = match_listing(
            listing(
                title="Garden City apartment",
                description="Garden City Mall on Thika Road",
                location="Kilimani",
                standard_location="Kilimani",
            ),
            [entity()],
        )
        client = FakeRelationshipClient()

        result = write_auto_candidates(client, [decision])

        self.assertTrue(decision.conflicting_signals)
        self.assertEqual(result["inserted_count"], 0)
        self.assertEqual(client.upsert_calls, [])

    def test_duplicate_relationship_is_skipped_without_upsert(self):
        decision = match_listing(
            listing(
                title="Garden City apartment",
                location="Garden Estate",
                existing_entity_ids=frozenset({2}),
            ),
            [entity()],
        )
        client = FakeRelationshipClient(existing_pairs={(101, 2)})

        result = write_auto_candidates(client, [decision])

        self.assertTrue(decision.existing_relationship)
        self.assertEqual(result["existing_relationships_skipped_count"], 1)
        self.assertEqual(result["inserted_count"], 0)
        self.assertEqual(client.upsert_calls, [])

    def test_concurrent_duplicate_is_an_idempotent_no_op(self):
        decision = match_listing(
            listing(title="Garden City apartment", location="Garden Estate"),
            [entity()],
        )
        client = FakeRelationshipClient(existing_pairs={(101, 2)})

        result = write_auto_candidates(client, [decision])

        self.assertEqual(len(client.upsert_calls), 1)
        self.assertEqual(result["inserted_count"], 0)
        self.assertEqual(result["existing_relationships_skipped_count"], 1)


if __name__ == "__main__":
    unittest.main()
