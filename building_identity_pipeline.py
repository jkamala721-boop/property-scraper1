"""Bounded operational orchestration for LocationOS building identity V1."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any, Callable, Sequence

from building_entity_discovery import (
    MAX_SAMPLE_SIZE as DISCOVERY_SAMPLE_SIZE,
    build_discovery_proposals,
    eligible_supporting_apartment_ids,
    fetch_discovery_inputs,
    write_discovery_candidates,
)
from building_matching import (
    MAX_SAMPLE_SIZE as MATCHING_SAMPLE_SIZE,
    auto_write_ineligibility,
    fetch_dry_run_inputs,
    run_matcher,
    write_auto_candidates,
)
from supabase_runtime import create_supabase_client


MAX_BATCH_SIZE = 100
DEFAULT_BATCH_SIZE = 100
INTERNAL_CHUNK_SIZE = min(MATCHING_SAMPLE_SIZE, DISCOVERY_SAMPLE_SIZE)


@dataclass(frozen=True)
class BatchItem:
    apartment_id: int
    source: str
    listing_id: int
    already_linked: bool = False


@dataclass(frozen=True)
class BatchPage:
    items: tuple[BatchItem, ...]
    requested_cursor: int | None
    next_cursor: int | None
    has_more: bool
    unmapped_listing_ids: tuple[int, ...] = ()


def _response_data(response: Any) -> list[dict[str, Any]]:
    return list(response.data or [])


def validate_batch_size(batch_size: int) -> int:
    if batch_size < 1 or batch_size > MAX_BATCH_SIZE:
        raise ValueError(f"batch_size must be between 1 and {MAX_BATCH_SIZE}.")
    return batch_size


def fetch_batch_page(
    client: Any,
    source: str,
    batch_size: int,
    after_listing_id: int | None = None,
) -> BatchPage:
    """Fetch one stable keyset-paginated page of source listing mappings."""

    validate_batch_size(batch_size)
    query = (
        client.table("apartment_listings")
        .select("apartment_id,source,listing_id")
        .eq("source", source)
    )
    if after_listing_id is not None:
        query = query.gt("listing_id", int(after_listing_id))
    query = query.order("listing_id").limit(batch_size + 1)
    rows = _response_data(query.execute())
    page_rows = rows[:batch_size]
    apartment_ids = sorted({int(row["apartment_id"]) for row in page_rows})
    linked_apartments: set[int] = set()
    if apartment_ids:
        relationship_rows = _response_data(
            client.table("apartment_building_entities")
            .select("apartment_id")
            .in_("apartment_id", apartment_ids)
            .execute()
        )
        linked_apartments = {
            int(row["apartment_id"]) for row in relationship_rows
        }

    items = tuple(
        BatchItem(
            apartment_id=int(row["apartment_id"]),
            source=str(row["source"]),
            listing_id=int(row["listing_id"]),
            already_linked=int(row["apartment_id"]) in linked_apartments,
        )
        for row in page_rows
    )
    return BatchPage(
        items=items,
        requested_cursor=after_listing_id,
        next_cursor=items[-1].listing_id if items else after_listing_id,
        has_more=len(rows) > batch_size,
    )


def fetch_scrape_run_page(
    client: Any,
    run_id: int,
    source: str,
    batch_size: int,
    after_listing_id: int | None = None,
) -> BatchPage:
    """Fetch one bounded page from a completed scrape snapshot."""

    validate_batch_size(batch_size)
    query = (
        client.table("scrape_run_properties")
        .select("listing_id")
        .eq("run_id", int(run_id))
        .eq("source", source)
    )
    if after_listing_id is not None:
        query = query.gt("listing_id", int(after_listing_id))
    snapshot_rows = _response_data(
        query.order("listing_id").limit(batch_size + 1).execute()
    )
    page_rows = snapshot_rows[:batch_size]
    listing_ids = [int(row["listing_id"]) for row in page_rows]

    mapping_rows: list[dict[str, Any]] = []
    if listing_ids:
        mapping_rows = _response_data(
            client.table("apartment_listings")
            .select("apartment_id,source,listing_id")
            .eq("source", source)
            .in_("listing_id", listing_ids)
            .execute()
        )
    mappings_by_listing = {
        int(row["listing_id"]): row for row in mapping_rows
    }
    unmapped_listing_ids = tuple(
        listing_id
        for listing_id in listing_ids
        if listing_id not in mappings_by_listing
    )
    apartment_ids = sorted(
        {int(row["apartment_id"]) for row in mapping_rows}
    )
    linked_apartments: set[int] = set()
    if apartment_ids:
        relationship_rows = _response_data(
            client.table("apartment_building_entities")
            .select("apartment_id")
            .in_("apartment_id", apartment_ids)
            .execute()
        )
        linked_apartments = {
            int(row["apartment_id"]) for row in relationship_rows
        }

    items = tuple(
        BatchItem(
            apartment_id=int(mappings_by_listing[listing_id]["apartment_id"]),
            source=source,
            listing_id=listing_id,
            already_linked=(
                int(mappings_by_listing[listing_id]["apartment_id"])
                in linked_apartments
            ),
        )
        for listing_id in listing_ids
        if listing_id in mappings_by_listing
    )
    return BatchPage(
        items=items,
        requested_cursor=after_listing_id,
        next_cursor=listing_ids[-1] if listing_ids else after_listing_id,
        has_more=len(snapshot_rows) > batch_size,
        unmapped_listing_ids=unmapped_listing_ids,
    )


def _chunks(values: Sequence[int], size: int) -> list[list[int]]:
    return [list(values[index : index + size]) for index in range(0, len(values), size)]


def _is_match_ambiguity(decision: Any) -> bool:
    return "ambiguity" in decision.explanation.lower()


def _safe_discovery_proposals(
    proposals: Sequence[Any],
    listings: Sequence[Any],
) -> tuple[list[tuple[Any, tuple[int, ...]]], list[dict[str, Any]]]:
    candidates: list[tuple[Any, tuple[int, ...]]] = []
    apartment_candidates: dict[int, set[str]] = {}
    for proposal in proposals:
        if proposal.proposed_action != "create_candidate":
            continue
        supporters = eligible_supporting_apartment_ids(proposal, listings)
        if not supporters:
            continue
        candidates.append((proposal, supporters))
        for apartment_id in supporters:
            apartment_candidates.setdefault(apartment_id, set()).add(
                proposal.normalized_name
            )

    ambiguous_apartments = {
        apartment_id
        for apartment_id, names in apartment_candidates.items()
        if len(names) > 1
    }
    safe: list[tuple[Any, tuple[int, ...]]] = []
    ambiguous: list[dict[str, Any]] = []
    for proposal, supporters in candidates:
        conflicts = sorted(set(supporters) & ambiguous_apartments)
        if conflicts:
            ambiguous.append(
                {
                    "proposal": proposal.to_dict(),
                    "ambiguous_apartment_ids": conflicts,
                    "reason": "multiple discovery creation candidates for the same apartment",
                }
            )
        else:
            safe.append((proposal, supporters))
    return safe, ambiguous


def process_batch_page(
    client: Any,
    page: BatchPage,
    *,
    write: bool,
    matching_input_loader: Callable[..., Any] = fetch_dry_run_inputs,
    matcher: Callable[..., Any] = run_matcher,
    matching_writer: Callable[..., Any] = write_auto_candidates,
    discovery_input_loader: Callable[..., Any] = fetch_discovery_inputs,
    discovery_builder: Callable[..., Any] = build_discovery_proposals,
    discovery_writer: Callable[..., Any] = write_discovery_candidates,
) -> dict[str, Any]:
    """Run match-first then discovery-fallback orchestration for one page."""

    linked_apartments = {
        item.apartment_id for item in page.items if item.already_linked
    }
    seen_apartments: set[int] = set()
    eligible_items: list[BatchItem] = []
    duplicate_apartment_listings = 0
    for item in page.items:
        if item.already_linked:
            continue
        if item.apartment_id in seen_apartments:
            duplicate_apartment_listings += 1
            continue
        seen_apartments.add(item.apartment_id)
        eligible_items.append(item)

    matching_proposals: list[dict[str, Any]] = []
    discovery_proposals: list[dict[str, Any]] = []
    newly_created_entities: list[dict[str, Any]] = []
    matching_relationship_ids: list[int] = []
    discovery_relationship_ids: list[int] = []
    review_apartments: set[int] = set()
    abstention_apartments: set[int] = set()
    conflict_apartments: set[int] = set()
    errors: list[dict[str, Any]] = []
    if page.unmapped_listing_ids:
        errors.append(
            {
                "stage": "snapshot_apartment_mapping",
                "listing_ids": list(page.unmapped_listing_ids),
                "error": "completed scrape listing has no apartment_listings mapping",
            }
        )
    matching_relationships_proposed = 0
    matching_relationships_created = 0
    discovery_relationships_proposed = 0
    discovery_relationships_created = 0
    new_entities_proposed = 0

    for listing_ids in _chunks(
        [item.listing_id for item in eligible_items], INTERNAL_CHUNK_SIZE
    ):
        if not listing_ids:
            continue
        source = eligible_items[0].source
        try:
            matching_listings, entities = matching_input_loader(
                client, listing_ids, source
            )
            decisions = matcher(matching_listings, entities)
        except Exception as exc:
            errors.append(
                {
                    "stage": "matching_read_or_evaluation",
                    "listing_ids": listing_ids,
                    "error": str(exc),
                }
            )
            abstention_apartments.update(
                item.apartment_id
                for item in eligible_items
                if item.listing_id in listing_ids
            )
            continue

        fallback_listing_ids: list[int] = []
        for decision in decisions:
            if auto_write_ineligibility(decision) is None:
                matching_relationships_proposed += 1
                matching_proposals.append(decision.to_dict())
                if write:
                    try:
                        result = matching_writer(client, [decision])
                        matching_relationships_created += result["inserted_count"]
                        matching_relationship_ids.extend(
                            int(row["id"])
                            for row in result["inserted"]
                            if row.get("id") is not None
                        )
                    except Exception as exc:
                        errors.append(
                            {
                                "stage": "matching_write",
                                "listing_id": decision.listing_id,
                                "apartment_id": decision.apartment_id,
                                "error": str(exc),
                            }
                        )
                continue

            if decision.outcome == "review_candidate":
                review_apartments.add(decision.apartment_id)
            elif decision.conflicting_signals:
                conflict_apartments.add(decision.apartment_id)
                abstention_apartments.add(decision.apartment_id)
            elif _is_match_ambiguity(decision):
                review_apartments.add(decision.apartment_id)
                abstention_apartments.add(decision.apartment_id)
            elif decision.outcome == "no_match":
                fallback_listing_ids.append(decision.listing_id)
            else:
                abstention_apartments.add(decision.apartment_id)

        if not fallback_listing_ids:
            continue
        try:
            discovery_listings, existing_entities = discovery_input_loader(
                client, fallback_listing_ids, source
            )
            proposals, listing_abstentions = discovery_builder(
                discovery_listings, existing_entities
            )
        except Exception as exc:
            errors.append(
                {
                    "stage": "discovery_read_or_evaluation",
                    "listing_ids": fallback_listing_ids,
                    "error": str(exc),
                }
            )
            abstention_apartments.update(
                decision.apartment_id
                for decision in decisions
                if decision.listing_id in fallback_listing_ids
            )
            continue

        abstention_apartments.update(
            item.apartment_id for item in listing_abstentions
        )
        for proposal in proposals:
            supporters = set(proposal.apartment_ids)
            if proposal.proposed_action in {"review", "existing_entity"}:
                review_apartments.update(supporters)
            elif proposal.proposed_action == "abstain":
                abstention_apartments.update(supporters)
            if "conflict" in proposal.explanation.lower():
                conflict_apartments.update(supporters)

        safe_proposals, ambiguous_proposals = _safe_discovery_proposals(
            proposals, discovery_listings
        )
        for ambiguous in ambiguous_proposals:
            apartment_ids = ambiguous["ambiguous_apartment_ids"]
            review_apartments.update(apartment_ids)
            abstention_apartments.update(apartment_ids)
        for proposal, supporters in safe_proposals:
            new_entities_proposed += 1
            discovery_relationships_proposed += len(supporters)
            discovery_proposals.append(
                {
                    "proposal": proposal.to_dict(),
                    "eligible_supporting_apartment_ids": list(supporters),
                }
            )
            if not write:
                continue
            try:
                result = discovery_writer(
                    client, [proposal], discovery_listings
                )
                newly_created_entities.extend(result["created_entities"])
                discovery_relationships_created += result[
                    "inserted_relationship_count"
                ]
                discovery_relationship_ids.extend(
                    int(row["id"])
                    for row in result["inserted_relationships"]
                    if row.get("id") is not None
                )
            except Exception as exc:
                errors.append(
                    {
                        "stage": "discovery_write",
                        "normalized_name": proposal.normalized_name,
                        "apartment_ids": list(supporters),
                        "error": str(exc),
                    }
                )

    summary = {
        "listings_examined": len(page.items) + len(page.unmapped_listing_ids),
        "already_linked_skipped": len(linked_apartments),
        "duplicate_apartment_listings_skipped": duplicate_apartment_listings,
        "strong_existing_entity_matches": matching_relationships_proposed,
        "new_provisional_entities_proposed": new_entities_proposed,
        "new_provisional_entities_created": len(newly_created_entities),
        "discovery_relationships_proposed": discovery_relationships_proposed,
        "discovery_relationships_created": discovery_relationships_created,
        "matching_relationships_proposed": matching_relationships_proposed,
        "matching_relationships_created": matching_relationships_created,
        "review_cases": len(review_apartments),
        "abstentions": len(abstention_apartments),
        "conflicts": len(conflict_apartments),
        "errors": len(errors),
    }
    return {
        "mode": "write" if write else "dry_run",
        "writes_performed": bool(
            matching_relationships_created
            or discovery_relationships_created
            or newly_created_entities
        ),
        "cursor": {
            "requested": page.requested_cursor,
            "next": page.next_cursor,
            "has_more": page.has_more,
        },
        "summary": summary,
        "newly_created_entities": newly_created_entities,
        "matching_relationship_ids": matching_relationship_ids,
        "discovery_relationship_ids": discovery_relationship_ids,
        "matching_proposals": matching_proposals,
        "discovery_proposals": discovery_proposals,
        "review_apartment_ids": sorted(review_apartments),
        "abstention_apartment_ids": sorted(abstention_apartments),
        "conflict_apartment_ids": sorted(conflict_apartments),
        "errors": errors,
    }


def run_pipeline_batch(
    client: Any,
    source: str,
    batch_size: int,
    after_listing_id: int | None,
    *,
    write: bool,
) -> dict[str, Any]:
    page = fetch_batch_page(client, source, batch_size, after_listing_id)
    report = process_batch_page(client, page, write=write)
    report["source"] = source
    report["batch_size"] = batch_size
    return report


SUMMARY_FIELDS = (
    "listings_examined",
    "already_linked_skipped",
    "duplicate_apartment_listings_skipped",
    "strong_existing_entity_matches",
    "new_provisional_entities_proposed",
    "new_provisional_entities_created",
    "discovery_relationships_proposed",
    "discovery_relationships_created",
    "matching_relationships_proposed",
    "matching_relationships_created",
    "review_cases",
    "abstentions",
    "conflicts",
    "errors",
)


def _empty_summary() -> dict[str, int]:
    return {field: 0 for field in SUMMARY_FIELDS}


def _skipped_scrape_run_report(
    run_id: int,
    source: str,
    status: str,
    write: bool,
) -> dict[str, Any]:
    return {
        "mode": "write" if write else "dry_run",
        "source": source,
        "scrape_run_id": int(run_id),
        "scrape_run_status": status,
        "skipped": True,
        "skip_reason": f"scrape run status is {status}, not completed",
        "writes_performed": False,
        "batches_processed": 0,
        "summary": _empty_summary(),
        "newly_created_entities": [],
        "matching_relationship_ids": [],
        "discovery_relationship_ids": [],
        "errors": [],
    }


def run_pipeline_for_scrape_run(
    client: Any,
    run_id: int,
    source: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
    *,
    write: bool,
) -> dict[str, Any]:
    """Process only listings persisted in one successfully completed scrape."""

    validate_batch_size(batch_size)
    run_rows = _response_data(
        client.table("scrape_runs")
        .select("id,source,status")
        .eq("id", int(run_id))
        .eq("source", source)
        .limit(1)
        .execute()
    )
    if not run_rows:
        raise RuntimeError(
            f"Scrape run {run_id} for source {source} was not found."
        )
    run_status = str(run_rows[0].get("status") or "unknown")
    if run_status != "completed":
        return _skipped_scrape_run_report(
            run_id, source, run_status, write
        )

    summary = _empty_summary()
    reports: list[dict[str, Any]] = []
    next_cursor: int | None = None
    while True:
        page = fetch_scrape_run_page(
            client,
            run_id,
            source,
            batch_size,
            after_listing_id=next_cursor,
        )
        report = process_batch_page(client, page, write=write)
        reports.append(report)
        for field in SUMMARY_FIELDS:
            summary[field] += int(report["summary"][field])
        if not page.has_more:
            break
        if page.next_cursor is None or page.next_cursor == next_cursor:
            raise RuntimeError(
                f"Scrape run {run_id} snapshot pagination did not advance."
            )
        next_cursor = page.next_cursor

    return {
        "mode": "write" if write else "dry_run",
        "source": source,
        "scrape_run_id": int(run_id),
        "scrape_run_status": run_status,
        "skipped": False,
        "writes_performed": any(report["writes_performed"] for report in reports),
        "batch_size": batch_size,
        "batches_processed": len(reports),
        "summary": summary,
        "newly_created_entities": [
            entity
            for report in reports
            for entity in report["newly_created_entities"]
        ],
        "matching_relationship_ids": [
            relationship_id
            for report in reports
            for relationship_id in report["matching_relationship_ids"]
        ],
        "discovery_relationship_ids": [
            relationship_id
            for report in reports
            for relationship_id in report["discovery_relationship_ids"]
        ],
        "errors": [
            error for report in reports for error in report["errors"]
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bounded operational LocationOS building identity pipeline"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--write", action="store_true")
    parser.add_argument("--source", default="BuyRentKenya")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument(
        "--after-listing-id",
        type=int,
        help="Exclusive listing-id cursor returned by the previous batch",
    )
    parser.add_argument(
        "--scrape-run-id",
        type=int,
        help="Process the completed scrape snapshot, for isolated retry",
    )
    args = parser.parse_args(argv)
    validate_batch_size(args.batch_size)

    client = create_supabase_client()
    if args.scrape_run_id is not None:
        if args.after_listing_id is not None:
            parser.error(
                "--after-listing-id cannot be used with --scrape-run-id"
            )
        report = run_pipeline_for_scrape_run(
            client,
            args.scrape_run_id,
            args.source,
            args.batch_size,
            write=args.write,
        )
    else:
        report = run_pipeline_batch(
            client,
            args.source,
            args.batch_size,
            args.after_listing_id,
            write=args.write,
        )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["summary"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
