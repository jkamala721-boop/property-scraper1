"""Failure-isolated post-scrape building identity hook."""

from __future__ import annotations

import json
from typing import Any, Callable

from building_identity_pipeline import (
    DEFAULT_BATCH_SIZE,
    run_pipeline_for_scrape_run,
)
from supabase_runtime import create_supabase_client


SOURCE = "BuyRentKenya"


def _failure_report(run_id: int, source: str, error: Exception) -> dict[str, Any]:
    return {
        "mode": "write",
        "source": source,
        "scrape_run_id": int(run_id),
        "scrape_run_status": "completed",
        "skipped": False,
        "writes_performed": False,
        "batches_processed": 0,
        "summary": {
            "listings_examined": 0,
            "already_linked_skipped": 0,
            "strong_existing_entity_matches": 0,
            "new_provisional_entities_created": 0,
            "matching_relationships_created": 0,
            "discovery_relationships_created": 0,
            "review_cases": 0,
            "abstentions": 0,
            "conflicts": 0,
            "errors": 1,
        },
        "newly_created_entities": [],
        "matching_relationship_ids": [],
        "discovery_relationship_ids": [],
        "errors": [
            {
                "stage": "post_scrape_building_identity",
                "error": str(error),
            }
        ],
    }


def _skipped_report(scrape_result: dict[str, Any] | None) -> dict[str, Any]:
    status = (
        str(scrape_result.get("status"))
        if scrape_result is not None
        else "unknown"
    )
    run_id = scrape_result.get("run_id") if scrape_result else None
    return {
        "mode": "write",
        "source": SOURCE,
        "scrape_run_id": run_id,
        "scrape_run_status": status,
        "skipped": True,
        "skip_reason": "building identity runs only after a completed safe scrape",
        "writes_performed": False,
        "batches_processed": 0,
        "summary": {"errors": 0},
        "errors": [],
    }


def compact_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary", {})
    return {
        "listings evaluated": summary.get("listings_examined", 0),
        "already linked": summary.get("already_linked_skipped", 0),
        "matched to existing entities": summary.get(
            "matching_relationships_created", 0
        ),
        "new provisional entities": summary.get(
            "new_provisional_entities_created", 0
        ),
        "relationships created": (
            summary.get("matching_relationships_created", 0)
            + summary.get("discovery_relationships_created", 0)
        ),
        "reviews": summary.get("review_cases", 0),
        "abstentions": summary.get("abstentions", 0),
        "conflicts": summary.get("conflicts", 0),
        "errors": summary.get("errors", 0),
    }


def run_post_scrape_building_identity(
    scrape_result: dict[str, Any] | None,
    *,
    client_factory: Callable[[], Any] = create_supabase_client,
    pipeline_runner: Callable[..., dict[str, Any]] = run_pipeline_for_scrape_run,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[str, Any]:
    """Run identity for a completed scrape without changing scrape outcome."""

    if not scrape_result or scrape_result.get("status") != "completed":
        return _skipped_report(scrape_result)

    source = str(scrape_result.get("source") or SOURCE)
    run_id = scrape_result.get("run_id")
    try:
        run_id = int(run_id)
        report = pipeline_runner(
            client_factory(),
            run_id,
            source,
            batch_size,
            write=True,
        )
        rendered_summary = compact_summary(report)
    except Exception as exc:
        safe_run_id = int(run_id) if isinstance(run_id, int) else 0
        report = _failure_report(safe_run_id, source, exc)
        rendered_summary = compact_summary(report)

    print("Building identity post-scrape summary:")
    print(json.dumps(rendered_summary, indent=2, sort_keys=True))
    if report.get("skipped"):
        print(f"Building identity skipped: {report.get('skip_reason')}")
    if report.get("errors"):
        print("Building identity errors (scrape remains completed):")
        print(json.dumps(report["errors"], indent=2, sort_keys=True))
    return report
