import unittest
from unittest.mock import patch
from types import SimpleNamespace

from building_entity_discovery import DiscoveryListing
from building_identity_pipeline import (
    BatchItem,
    BatchPage,
    fetch_batch_page,
    fetch_scrape_run_page,
    process_batch_page,
    run_pipeline_for_scrape_run,
    validate_batch_size,
)
from building_matching import MatchDecision, Signal
from supabase_runtime import load_supabase_settings


def page(*items, cursor=None, next_cursor=None, has_more=False):
    return BatchPage(
        items=tuple(items),
        requested_cursor=cursor,
        next_cursor=next_cursor,
        has_more=has_more,
    )


def decision(apartment_id, listing_id, outcome="no_match", conflict=False):
    strong = outcome == "strong_candidate"
    conflicts = (
        (Signal("location_conflict", -0.4, "conflicting location"),)
        if conflict
        else ()
    )
    return MatchDecision(
        apartment_id=apartment_id,
        source="BuyRentKenya",
        listing_id=listing_id,
        outcome=outcome,
        confidence=0.95 if strong else 0.0,
        proposed_building_entity_id=2 if strong else None,
        proposed_building_code="BENT-000002" if strong else None,
        best_compared_entity_id=2,
        best_compared_building_code="BENT-000002",
        existing_relationship=False,
        matched_signals=(Signal("entity_name", 0.55, "name"),) if strong else (),
        conflicting_signals=conflicts,
        weak_compatibility_signals=(),
        explanation=(
            "Strong candidate for BENT-000002 from two signals."
            if strong
            else "Abstained: no entity evidence."
        ),
    )


def matching_loader(_client, listing_ids, _source):
    return list(listing_ids), []


class FakePageQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.cursor = None
        self.row_limit = None
        self.apartment_ids = None

    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def order(self, *_args):
        return self

    def limit(self, value):
        self.row_limit = value
        return self

    def gt(self, _column, value):
        self.cursor = value
        return self

    def in_(self, _column, values):
        self.apartment_ids = set(values)
        return self

    def execute(self):
        if self.table_name == "apartment_listings":
            rows = [
                row
                for row in self.client.mapping_rows
                if self.cursor is None or row["listing_id"] > self.cursor
            ]
            return SimpleNamespace(data=rows[: self.row_limit])
        if self.table_name == "apartment_building_entities":
            return SimpleNamespace(
                data=[
                    {"apartment_id": apartment_id}
                    for apartment_id in sorted(self.client.linked_apartments)
                    if apartment_id in self.apartment_ids
                ]
            )
        raise AssertionError(f"Unexpected table {self.table_name}")


class FakePageClient:
    def __init__(self, mapping_rows, linked_apartments=()):
        self.mapping_rows = mapping_rows
        self.linked_apartments = set(linked_apartments)
        self.tables = []

    def table(self, table_name):
        self.tables.append(table_name)
        return FakePageQuery(self, table_name)


class FakeSnapshotQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.filters = {}
        self.cursor = None
        self.row_limit = None
        self.in_values = None

    def select(self, *_args):
        return self

    def eq(self, column, value):
        self.filters[column] = value
        return self

    def gt(self, _column, value):
        self.cursor = int(value)
        return self

    def order(self, *_args):
        return self

    def limit(self, value):
        self.row_limit = value
        return self

    def in_(self, _column, values):
        self.in_values = {int(value) for value in values}
        return self

    def execute(self):
        if self.table_name == "scrape_runs":
            if self.client.run_status is None:
                return SimpleNamespace(data=[])
            return SimpleNamespace(
                data=[
                    {
                        "id": self.filters["id"],
                        "source": self.filters["source"],
                        "status": self.client.run_status,
                    }
                ]
            )
        if self.table_name == "scrape_run_properties":
            rows = [
                row
                for row in self.client.snapshot_rows
                if row["run_id"] == self.filters["run_id"]
                and row["source"] == self.filters["source"]
                and (self.cursor is None or row["listing_id"] > self.cursor)
            ]
            rows.sort(key=lambda row: row["listing_id"])
            return SimpleNamespace(data=rows[: self.row_limit])
        if self.table_name == "apartment_listings":
            return SimpleNamespace(
                data=[
                    row
                    for row in self.client.mapping_rows
                    if row["source"] == self.filters["source"]
                    and row["listing_id"] in self.in_values
                ]
            )
        if self.table_name == "apartment_building_entities":
            return SimpleNamespace(
                data=[
                    {"apartment_id": apartment_id}
                    for apartment_id in sorted(self.client.linked_apartments)
                    if apartment_id in self.in_values
                ]
            )
        raise AssertionError(f"Unexpected table {self.table_name}")


class FakeSnapshotClient:
    def __init__(
        self,
        snapshot_rows=(),
        mapping_rows=(),
        linked_apartments=(),
        run_status="completed",
    ):
        self.snapshot_rows = list(snapshot_rows)
        self.mapping_rows = list(mapping_rows)
        self.linked_apartments = set(linked_apartments)
        self.run_status = run_status
        self.tables = []

    def table(self, table_name):
        self.tables.append(table_name)
        return FakeSnapshotQuery(self, table_name)


class BuildingIdentityPipelineTests(unittest.TestCase):
    def test_match_first_short_circuits_discovery(self):
        batch = page(BatchItem(1, "BuyRentKenya", 1001), next_cursor=1001)

        def matcher(_listings, _entities):
            return [decision(1, 1001, "strong_candidate")]

        def unexpected_discovery(*_args):
            raise AssertionError("Discovery must not run after a strong match")

        report = process_batch_page(
            object(),
            batch,
            write=False,
            matching_input_loader=matching_loader,
            matcher=matcher,
            discovery_input_loader=unexpected_discovery,
        )

        self.assertEqual(report["summary"]["strong_existing_entity_matches"], 1)
        self.assertEqual(report["summary"]["matching_relationships_proposed"], 1)
        self.assertEqual(report["summary"]["new_provisional_entities_proposed"], 0)

    def test_no_match_falls_back_to_discovery(self):
        batch = page(BatchItem(2, "BuyRentKenya", 1002), next_cursor=1002)

        def matcher(_listings, _entities):
            return [decision(2, 1002)]

        def discovery_loader(_client, _ids, _source):
            return [
                DiscoveryListing(
                    apartment_id=2,
                    source="BuyRentKenya",
                    listing_id=1002,
                    description="Located at Azure Heights, along Riverside Drive.",
                    standard_location="Riverside",
                )
            ], []

        report = process_batch_page(
            object(),
            batch,
            write=False,
            matching_input_loader=matching_loader,
            matcher=matcher,
            discovery_input_loader=discovery_loader,
        )

        self.assertEqual(report["summary"]["new_provisional_entities_proposed"], 1)
        self.assertEqual(report["summary"]["discovery_relationships_proposed"], 1)

    def test_existing_relationship_skips_all_identity_work(self):
        batch = page(
            BatchItem(3, "BuyRentKenya", 1003, already_linked=True),
            next_cursor=1003,
        )

        def unexpected(*_args):
            raise AssertionError("Linked apartments must not be evaluated")

        report = process_batch_page(
            object(),
            batch,
            write=True,
            matching_input_loader=unexpected,
            matcher=unexpected,
            discovery_input_loader=unexpected,
        )

        self.assertEqual(report["summary"]["already_linked_skipped"], 1)
        self.assertFalse(report["writes_performed"])

    def test_weak_generic_discovery_abstains(self):
        batch = page(BatchItem(4, "BuyRentKenya", 1004), next_cursor=1004)

        def matcher(_listings, _entities):
            return [decision(4, 1004)]

        def discovery_loader(_client, _ids, _source):
            return [
                DiscoveryListing(
                    apartment_id=4,
                    source="BuyRentKenya",
                    listing_id=1004,
                    title="Luxury apartment in Westlands",
                    standard_location="Westlands",
                )
            ], []

        report = process_batch_page(
            object(),
            batch,
            write=False,
            matching_input_loader=matching_loader,
            matcher=matcher,
            discovery_input_loader=discovery_loader,
        )

        self.assertEqual(report["summary"]["abstentions"], 1)
        self.assertEqual(report["summary"]["new_provisional_entities_proposed"], 0)

    def test_batch_bounds_are_enforced(self):
        self.assertEqual(validate_batch_size(100), 100)
        with self.assertRaises(ValueError):
            validate_batch_size(0)
        with self.assertRaises(ValueError):
            validate_batch_size(101)

    def test_runtime_configuration_prefers_environment_without_config_file(self):
        with patch.dict(
            "os.environ",
            {"SUPABASE_URL": "https://example.supabase.co", "SUPABASE_KEY": "test-key"},
            clear=True,
        ):
            self.assertEqual(
                load_supabase_settings(),
                ("https://example.supabase.co", "test-key"),
            )

    def test_keyset_cursor_advances_without_repeating_first_page(self):
        rows = [
            {"apartment_id": value, "source": "BuyRentKenya", "listing_id": value}
            for value in (1001, 1002, 1003, 1004, 1005)
        ]
        client = FakePageClient(rows, linked_apartments={1004})

        first = fetch_batch_page(client, "BuyRentKenya", 2)
        second = fetch_batch_page(
            client, "BuyRentKenya", 2, after_listing_id=first.next_cursor
        )

        self.assertEqual([item.listing_id for item in first.items], [1001, 1002])
        self.assertEqual(first.next_cursor, 1002)
        self.assertTrue(first.has_more)
        self.assertEqual([item.listing_id for item in second.items], [1003, 1004])
        self.assertEqual(second.next_cursor, 1004)
        self.assertTrue(second.items[-1].already_linked)

    def test_completed_scrape_page_uses_only_snapshot_listing_ids(self):
        snapshot_rows = [
            {"run_id": 42, "source": "BuyRentKenya", "listing_id": value}
            for value in (2002, 2004, 2008)
        ]
        mapping_rows = [
            {
                "apartment_id": index,
                "source": "BuyRentKenya",
                "listing_id": listing_id,
            }
            for index, listing_id in enumerate((1999, 2002, 2004, 2008), 1)
        ]
        client = FakeSnapshotClient(
            snapshot_rows,
            mapping_rows,
            linked_apartments={3},
        )

        first = fetch_scrape_run_page(client, 42, "BuyRentKenya", 2)
        second = fetch_scrape_run_page(
            client,
            42,
            "BuyRentKenya",
            2,
            after_listing_id=first.next_cursor,
        )

        self.assertEqual([item.listing_id for item in first.items], [2002, 2004])
        self.assertEqual([item.listing_id for item in second.items], [2008])
        self.assertNotIn(1999, [item.listing_id for item in first.items])
        self.assertTrue(first.items[-1].already_linked)
        self.assertTrue(first.has_more)
        self.assertFalse(second.has_more)

    def test_live_incomplete_run_is_rejected_before_snapshot_read(self):
        client = FakeSnapshotClient(run_status="incomplete")

        report = run_pipeline_for_scrape_run(
            client,
            42,
            "BuyRentKenya",
            100,
            write=True,
        )

        self.assertTrue(report["skipped"])
        self.assertEqual(client.tables, ["scrape_runs"])

    def test_write_delegates_to_existing_paths_and_is_idempotent_on_next_run(self):
        writes = []
        unlinked = page(BatchItem(5, "BuyRentKenya", 1005), next_cursor=1005)
        linked = page(
            BatchItem(5, "BuyRentKenya", 1005, already_linked=True),
            next_cursor=1005,
        )

        def matcher(_listings, _entities):
            return [decision(5, 1005, "strong_candidate")]

        def matching_writer(_client, decisions):
            writes.append(("matching", decisions[0].apartment_id))
            return {
                "inserted_count": 1,
                "inserted": [{"id": 55, "apartment_id": 5}],
            }

        first = process_batch_page(
            object(),
            unlinked,
            write=True,
            matching_input_loader=matching_loader,
            matcher=matcher,
            matching_writer=matching_writer,
        )
        second = process_batch_page(
            object(),
            linked,
            write=True,
            matching_input_loader=lambda *_args: self.fail("must skip"),
        )

        self.assertEqual(writes, [("matching", 5)])
        self.assertEqual(first["matching_relationship_ids"], [55])
        self.assertEqual(second["summary"]["already_linked_skipped"], 1)
        self.assertFalse(second["writes_performed"])

    def test_discovery_write_reports_entity_and_uses_no_canonical_path(self):
        batch = page(BatchItem(6, "BuyRentKenya", 1006), next_cursor=1006)
        client = SimpleNamespace(tables=[])

        def matcher(_listings, _entities):
            return [decision(6, 1006)]

        def discovery_loader(_client, _ids, _source):
            return [
                DiscoveryListing(
                    apartment_id=6,
                    source="BuyRentKenya",
                    listing_id=1006,
                    description="Located at Harbor Point, along Riverside Drive.",
                    standard_location="Riverside",
                )
            ], []

        def discovery_writer(_client, _proposals, _listings):
            return {
                "created_entities": [
                    {"id": 9, "building_code": "BENT-000009", "canonical_name": "Harbor Point"}
                ],
                "inserted_relationship_count": 1,
                "inserted_relationships": [{"id": 91, "apartment_id": 6}],
            }

        report = process_batch_page(
            client,
            batch,
            write=True,
            matching_input_loader=matching_loader,
            matcher=matcher,
            discovery_input_loader=discovery_loader,
            discovery_writer=discovery_writer,
        )

        self.assertEqual(report["newly_created_entities"][0]["building_code"], "BENT-000009")
        self.assertEqual(report["discovery_relationship_ids"], [91])
        self.assertEqual(client.tables, [])


if __name__ == "__main__":
    unittest.main()
