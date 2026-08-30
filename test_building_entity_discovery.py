import unittest
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

from building_entity_discovery import (
    AUTO_DISCOVERY_METHOD,
    DiscoveryListing,
    ExistingEntity,
    GRANULARITY_WARNING,
    build_discovery_proposals,
    write_discovery_candidates,
)
from building_matching import relationship_can_seed_reference


def listing(listing_id, **overrides):
    values = {
        "apartment_id": listing_id + 1000,
        "source": "BuyRentKenya",
        "listing_id": listing_id,
        "title": "Apartment for rent",
        "description": "",
        "location": None,
        "standard_location": None,
        "agent_name": None,
    }
    values.update(overrides)
    return DiscoveryListing(**values)


def capital_garden_listings():
    return [
        listing(
            4035766,
            apartment_id=8,
            description="CAPITAL GARDEN\nLocated along George Padmore Road in Kilimani.",
            location="Kilimani",
            standard_location="Kilimani",
            agent_name="Leissure Homes",
        ),
        listing(
            4048055,
            apartment_id=1063,
            description="Located at Capital Garden, along George Padmore Road.",
            location="Kilimani",
            standard_location="Kilimani",
            agent_name="A-List",
        ),
        listing(
            4048057,
            apartment_id=1026,
            description="CAPITAL GARDEN\nModern apartments in Kilimani.",
            location="Kilimani",
            standard_location="Kilimani",
            agent_name="A-List",
        ),
    ]


class FakeDiscoveryClient:
    def __init__(self, entities=(), existing_pairs=()):
        self.entities = [dict(entity) for entity in entities]
        self.relationships = []
        self.existing_pairs = set(existing_pairs)
        self.insert_calls = []
        self.upsert_calls = []
        self._operation = None
        self._payload = None

    def table(self, table_name):
        self._table = table_name
        return self

    def insert(self, row):
        self.insert_calls.append({"table": self._table, "row": row})
        self._operation = "insert"
        self._payload = row
        return self

    def select(self, *_args):
        return self

    def upsert(self, rows, *, on_conflict, ignore_duplicates):
        self.upsert_calls.append(
            {
                "table": self._table,
                "rows": rows,
                "on_conflict": on_conflict,
                "ignore_duplicates": ignore_duplicates,
            }
        )
        self._operation = "upsert"
        self._payload = rows
        return self

    def execute(self):
        if self._operation == "insert":
            entity = {
                "id": 10 + len(self.entities),
                "building_code": f"BENT-{10 + len(self.entities):06d}",
                **self._payload,
            }
            self.entities.append(entity)
            return SimpleNamespace(data=[entity])
        if self._operation == "upsert":
            inserted = []
            for row in self._payload:
                pair = (row["apartment_id"], row["building_entity_id"])
                if pair in self.existing_pairs:
                    continue
                self.existing_pairs.add(pair)
                persisted = {"id": 100 + len(self.relationships), **row}
                self.relationships.append(persisted)
                inserted.append(persisted)
            return SimpleNamespace(data=inserted)
        raise AssertionError("No fake database operation was configured")


def fake_entity_loader(client):
    return [
        ExistingEntity(
            id=row["id"],
            building_code=row["building_code"],
            canonical_name=row.get("canonical_name"),
            normalized_name=row.get("normalized_name"),
            location=row.get("location"),
            standard_location=row.get("standard_location"),
            address_text=row.get("address_text"),
        )
        for row in client.entities
    ]


class BuildingEntityDiscoveryTests(unittest.TestCase):
    def test_explicit_named_development_with_context_is_candidate(self):
        sample = listing(
            101,
            description="Located at Azure Heights, along Riverside Drive near Arboretum Centre.",
            location="Riverside",
            agent_name="Example Homes",
        )

        proposals, abstentions = build_discovery_proposals([sample], [])

        self.assertEqual(abstentions, [])
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].normalized_name, "azure heights")
        self.assertEqual(proposals[0].proposed_action, "create_candidate")
        self.assertIn("Riverside Drive", proposals[0].address_road_evidence)

    def test_generic_neighborhood_abstains(self):
        sample = listing(
            102,
            title="2 Bed Apartment in Westlands for KSh 100,000",
            location="Westlands",
        )

        proposals, abstentions = build_discovery_proposals([sample], [])

        self.assertEqual(proposals, [])
        self.assertEqual(len(abstentions), 1)
        self.assertTrue(
            any("neighborhood" in item["reason"] for item in abstentions[0].rejected_candidates)
        )

    def test_normalized_variants_across_listings_form_one_candidate(self):
        samples = [
            listing(
                103,
                description="Located at Capital-Garden, along George Padmore Road.",
                standard_location="Kilimani",
                agent_name="Agent One",
            ),
            listing(
                104,
                description="CAPITAL GARDEN\nA residential project in Kilimani.",
                standard_location="Kilimani",
                agent_name="Agent Two",
            ),
        ]

        proposals, _ = build_discovery_proposals(samples, [])

        capital = [proposal for proposal in proposals if proposal.normalized_name == "capital garden"]
        self.assertEqual(len(capital), 1)
        self.assertEqual(capital[0].listing_ids, (103, 104))
        self.assertEqual(capital[0].independent_listing_count, 2)
        self.assertEqual(capital[0].proposed_action, "create_candidate")

    def test_existing_garden_city_is_not_duplicate(self):
        sample = listing(
            105,
            description="Furnished apartment in Garden-City on 13th Floor near Thika Road.",
            location="Garden Estate",
        )
        existing = ExistingEntity(
            id=2,
            building_code="BENT-000002",
            canonical_name="Garden City",
            normalized_name="garden city",
            location="Garden Estate",
        )

        proposals, _ = build_discovery_proposals([sample], [existing])

        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].proposed_action, "existing_entity")
        self.assertTrue(proposals[0].similar_entity_already_exists)
        self.assertEqual(proposals[0].similar_entity["building_code"], "BENT-000002")

    def test_existing_entity_type_suffix_is_not_a_duplicate(self):
        sample = listing(
            111,
            description="Located at Garden City Apartments, near Thika Road.",
            location="Garden Estate",
        )
        existing = ExistingEntity(
            id=2,
            building_code="BENT-000002",
            canonical_name="Garden City",
            normalized_name="garden city",
            location="Garden Estate",
        )

        proposals, _ = build_discovery_proposals([sample], [existing])

        garden_city = next(
            proposal for proposal in proposals if proposal.normalized_name == "garden city apartments"
        )
        self.assertEqual(garden_city.proposed_action, "existing_entity")

    def test_conflicting_locations_require_review(self):
        samples = [
            listing(
                106,
                description="Located at Skyline Residences, along Wood Avenue.",
                standard_location="Kilimani",
            ),
            listing(
                107,
                description="Located at Skyline Residences, near Sarit Centre.",
                standard_location="Westlands",
            ),
        ]

        proposals, _ = build_discovery_proposals(samples, [])
        skyline = next(
            proposal for proposal in proposals if proposal.normalized_name == "skyline residences"
        )

        self.assertEqual(skyline.proposed_action, "review")
        self.assertIn("Conflicting location", skyline.explanation)

    def test_weak_generic_marketing_phrase_abstains(self):
        sample = listing(
            108,
            title="Luxury Apartments in Kilimani",
            description="HOUSE FEATURES\nModern luxury apartments with premium finishes.",
            standard_location="Kilimani",
        )

        proposals, abstentions = build_discovery_proposals([sample], [])

        self.assertEqual(proposals, [])
        self.assertEqual(len(abstentions), 1)
        reasons = [item["reason"] for item in abstentions[0].rejected_candidates]
        self.assertTrue(any("generic" in reason for reason in reasons))

    def test_available_apartments_section_heading_abstains(self):
        sample = listing(
            112,
            description="AVAILABLE APARTMENTS\n2br - 86 square metres",
            standard_location="Kileleshwa",
        )

        proposals, abstentions = build_discovery_proposals([sample], [])

        self.assertEqual(proposals, [])
        self.assertEqual(len(abstentions), 1)

    def test_title_only_at_phrase_does_not_create_entity(self):
        sample = listing(
            113,
            title="1 Bed Apartment at General Mathenge for KSh 9,500,000",
            standard_location="Westlands",
        )

        proposals, _ = build_discovery_proposals([sample], [])

        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].proposed_action, "review")

    def test_typed_name_strips_leading_marketing_modifiers(self):
        sample = listing(
            114,
            description="Exclusive Residential Development Merlin Court comprises 58 apartments.",
            standard_location="Lavington",
        )

        proposals, _ = build_discovery_proposals([sample], [])

        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].normalized_name, "merlin court")

    def test_development_evidence_does_not_fabricate_tower_identity(self):
        sample = listing(
            109,
            description="Development named Harbor Point, located along Riverside Drive.",
            standard_location="Riverside",
        )

        proposals, _ = build_discovery_proposals([sample], [])

        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].proposed_canonical_name, "Harbor Point")
        self.assertEqual(proposals[0].granularity_warning, GRANULARITY_WARNING)
        self.assertNotIn("tower", proposals[0].proposed_canonical_name.lower())

    def test_number_at_location_can_be_distinctive_name(self):
        sample = listing(
            110,
            title="2 Bed Apartment at 17 @ Kitisuru for KSh 150,000",
            location="Kitisuru",
        )

        proposals, _ = build_discovery_proposals([sample], [])

        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].normalized_name, "17 at kitisuru")
        self.assertEqual(proposals[0].proposed_action, "create_candidate")

    def test_eligible_candidate_creates_entity_and_supporting_relationships(self):
        samples = capital_garden_listings()
        proposals, _ = build_discovery_proposals(samples, [])
        capital = [proposal for proposal in proposals if proposal.normalized_name == "capital garden"]
        client = FakeDiscoveryClient()

        result = write_discovery_candidates(
            client,
            capital,
            samples,
            existing_entity_loader=fake_entity_loader,
            observed_at=datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(result["created_entity_count"], 1)
        self.assertEqual(result["inserted_relationship_count"], 3)
        entity_row = client.insert_calls[0]["row"]
        self.assertEqual(entity_row["canonical_name"], "Capital Garden")
        self.assertEqual(entity_row["normalized_name"], "capital garden")
        self.assertEqual(entity_row["location"], "Kilimani")
        self.assertEqual(entity_row["standard_location"], "Kilimani")
        self.assertEqual(entity_row["address_text"], "George Padmore Road")
        self.assertIsNone(entity_row["canonical_building_id"])
        relationship_rows = client.upsert_calls[0]["rows"]
        self.assertEqual({row["apartment_id"] for row in relationship_rows}, {8, 1026, 1063})
        self.assertTrue(all(row["match_status"] == "candidate" for row in relationship_rows))
        self.assertTrue(
            all(row["match_method"] == AUTO_DISCOVERY_METHOD for row in relationship_rows)
        )
        self.assertTrue(
            all(row["evidence"]["matched_identity_signals"] for row in relationship_rows)
        )

    def test_pre_insert_recheck_resolves_existing_entity_without_duplicate(self):
        samples = capital_garden_listings()
        proposals, _ = build_discovery_proposals(samples, [])
        capital = [proposal for proposal in proposals if proposal.normalized_name == "capital garden"]
        client = FakeDiscoveryClient(
            entities=[
                {
                    "id": 7,
                    "building_code": "BENT-000007",
                    "canonical_name": "Capital Garden",
                    "normalized_name": "capital garden",
                    "location": "Kilimani",
                    "standard_location": "Kilimani",
                    "address_text": "George Padmore Road",
                }
            ]
        )

        result = write_discovery_candidates(
            client,
            capital,
            samples,
            existing_entity_loader=fake_entity_loader,
        )

        self.assertEqual(result["created_entity_count"], 0)
        self.assertEqual(result["resolved_existing_entity_count"], 1)
        self.assertEqual(client.insert_calls, [])
        self.assertEqual(
            {row["building_entity_id"] for row in client.upsert_calls[0]["rows"]},
            {7},
        )

    def test_duplicate_relationships_are_idempotent_no_ops(self):
        samples = capital_garden_listings()
        proposals, _ = build_discovery_proposals(samples, [])
        capital = [proposal for proposal in proposals if proposal.normalized_name == "capital garden"]
        client = FakeDiscoveryClient(
            entities=[
                {
                    "id": 7,
                    "building_code": "BENT-000007",
                    "canonical_name": "Capital Garden",
                    "normalized_name": "capital garden",
                    "location": "Kilimani",
                }
            ],
            existing_pairs={(8, 7), (1026, 7), (1063, 7)},
        )

        result = write_discovery_candidates(
            client,
            capital,
            samples,
            existing_entity_loader=fake_entity_loader,
        )

        self.assertEqual(result["inserted_relationship_count"], 0)
        self.assertEqual(result["existing_relationships_skipped_count"], 3)

    def test_rechecked_similar_entity_with_location_conflict_blocks_writes(self):
        samples = capital_garden_listings()
        proposals, _ = build_discovery_proposals(samples, [])
        capital = [proposal for proposal in proposals if proposal.normalized_name == "capital garden"]
        client = FakeDiscoveryClient(
            entities=[
                {
                    "id": 7,
                    "building_code": "BENT-000007",
                    "canonical_name": "Capital Garden",
                    "normalized_name": "capital garden",
                    "location": "Westlands",
                }
            ]
        )

        result = write_discovery_candidates(
            client,
            capital,
            samples,
            existing_entity_loader=fake_entity_loader,
        )

        self.assertEqual(result["created_entity_count"], 0)
        self.assertEqual(result["inserted_relationship_count"], 0)
        self.assertEqual(result["ineligible_skipped_count"], 1)
        self.assertEqual(
            result["ineligible_skipped"][0]["reason"],
            "rechecked_similar_entity_location_conflict",
        )
        self.assertEqual(client.insert_calls, [])
        self.assertEqual(client.upsert_calls, [])

    def test_review_and_abstain_proposals_never_write(self):
        sample = listing(
            113,
            title="1 Bed Apartment at General Mathenge for KSh 9,500,000",
            standard_location="Westlands",
        )
        proposals, _ = build_discovery_proposals([sample], [])
        review = proposals[0]
        abstain = replace(review, proposed_action="abstain", confidence=0.2)
        client = FakeDiscoveryClient()

        result = write_discovery_candidates(
            client,
            [review, abstain],
            [sample],
            existing_entity_loader=fake_entity_loader,
        )

        self.assertEqual(result["created_entity_count"], 0)
        self.assertEqual(result["inserted_relationship_count"], 0)
        self.assertEqual(result["ineligible_skipped_count"], 2)
        self.assertEqual(client.insert_calls, [])
        self.assertEqual(client.upsert_calls, [])

    def test_write_recomputes_creation_evidence_instead_of_trusting_label(self):
        sample = listing(
            115,
            title="1 Bed Apartment at General Mathenge for KSh 9,500,000",
            standard_location="Westlands",
        )
        proposals, _ = build_discovery_proposals([sample], [])
        mislabeled = replace(
            proposals[0],
            proposed_action="create_candidate",
            confidence=0.90,
        )
        client = FakeDiscoveryClient()

        result = write_discovery_candidates(
            client,
            [mislabeled],
            [sample],
            existing_entity_loader=fake_entity_loader,
        )

        self.assertEqual(result["created_entity_count"], 0)
        self.assertEqual(result["ineligible_skipped_count"], 1)
        self.assertEqual(
            result["ineligible_skipped"][0]["reason"],
            "creation_evidence_not_reproduced",
        )
        self.assertEqual(client.insert_calls, [])

    def test_auto_discovery_relationship_cannot_seed_matching_reference(self):
        row = {
            "match_status": "candidate",
            "match_confidence": 1.0,
            "match_method": AUTO_DISCOVERY_METHOD,
        }

        self.assertFalse(relationship_can_seed_reference(row))


if __name__ == "__main__":
    unittest.main()
