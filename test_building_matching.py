import unittest

from building_matching import (
    BuildingEntityProfile,
    ListingEvidence,
    REVIEW_CANDIDATE_THRESHOLD,
    STRONG_CANDIDATE_THRESHOLD,
    build_profiles_from_rows,
    match_listing,
    score_entity,
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
                "match_method": "deterministic_v1",
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


if __name__ == "__main__":
    unittest.main()
