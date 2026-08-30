import unittest

from post_scrape_building_identity import run_post_scrape_building_identity


def pipeline_report(**summary_overrides):
    summary = {
        "listings_examined": 2,
        "already_linked_skipped": 0,
        "matching_relationships_created": 0,
        "new_provisional_entities_created": 0,
        "discovery_relationships_created": 0,
        "review_cases": 0,
        "abstentions": 2,
        "conflicts": 0,
        "errors": 0,
    }
    summary.update(summary_overrides)
    return {
        "scrape_run_id": 42,
        "scrape_run_status": "completed",
        "skipped": False,
        "writes_performed": bool(
            summary["matching_relationships_created"]
            or summary["discovery_relationships_created"]
        ),
        "summary": summary,
        "errors": [],
    }


class PostScrapeBuildingIdentityTests(unittest.TestCase):
    def test_completed_safe_scrape_runs_building_identity(self):
        calls = []

        def runner(client, run_id, source, batch_size, *, write):
            calls.append((client, run_id, source, batch_size, write))
            return pipeline_report()

        report = run_post_scrape_building_identity(
            {"run_id": 42, "source": "BuyRentKenya", "status": "completed"},
            client_factory=lambda: "client",
            pipeline_runner=runner,
        )

        self.assertEqual(calls, [("client", 42, "BuyRentKenya", 100, True)])
        self.assertFalse(report["skipped"])

    def test_incomplete_scrape_does_not_run(self):
        self._assert_status_skips("incomplete")

    def test_failed_scrape_does_not_run(self):
        self._assert_status_skips("failed")

    def _assert_status_skips(self, status):
        def unexpected():
            self.fail("Supabase client must not be created for an unsafe run")

        report = run_post_scrape_building_identity(
            {"run_id": 42, "source": "BuyRentKenya", "status": status},
            client_factory=unexpected,
            pipeline_runner=lambda *_args, **_kwargs: self.fail(
                "Pipeline must not run"
            ),
        )

        self.assertTrue(report["skipped"])
        self.assertFalse(report["writes_performed"])

    def test_building_identity_failure_does_not_change_scrape_completion(self):
        scrape_result = {
            "run_id": 42,
            "source": "BuyRentKenya",
            "status": "completed",
        }

        def failing_runner(*_args, **_kwargs):
            raise RuntimeError("isolated identity failure")

        report = run_post_scrape_building_identity(
            scrape_result,
            client_factory=object,
            pipeline_runner=failing_runner,
        )

        self.assertEqual(scrape_result["status"], "completed")
        self.assertEqual(report["summary"]["errors"], 1)
        self.assertIn("isolated identity failure", report["errors"][0]["error"])

    def test_repeated_execution_remains_idempotent(self):
        executions = 0

        def stateful_runner(*_args, **_kwargs):
            nonlocal executions
            executions += 1
            if executions == 1:
                return pipeline_report(matching_relationships_created=1)
            return pipeline_report(
                listings_examined=2,
                already_linked_skipped=1,
                matching_relationships_created=0,
            )

        scrape_result = {
            "run_id": 42,
            "source": "BuyRentKenya",
            "status": "completed",
        }
        first = run_post_scrape_building_identity(
            scrape_result,
            client_factory=object,
            pipeline_runner=stateful_runner,
        )
        second = run_post_scrape_building_identity(
            scrape_result,
            client_factory=object,
            pipeline_runner=stateful_runner,
        )

        self.assertTrue(first["writes_performed"])
        self.assertFalse(second["writes_performed"])
        self.assertEqual(second["summary"]["already_linked_skipped"], 1)


if __name__ == "__main__":
    unittest.main()
