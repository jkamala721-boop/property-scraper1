import unittest

from scrape_safety import has_sufficient_discovery_coverage


class DiscoveryCoverageTests(unittest.TestCase):
    def test_zero_discovered_links_are_not_safe(self):
        self.assertFalse(has_sufficient_discovery_coverage(0, 999))

    def test_severely_partial_discovery_is_not_safe(self):
        self.assertFalse(has_sufficient_discovery_coverage(200, 999))

    def test_healthy_discovery_is_safe(self):
        self.assertTrue(has_sufficient_discovery_coverage(999, 999))

    def test_ordinary_inventory_change_is_safe(self):
        self.assertTrue(has_sufficient_discovery_coverage(960, 999))


if __name__ == "__main__":
    unittest.main()
