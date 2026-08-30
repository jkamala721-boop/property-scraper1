import math


MIN_DISCOVERY_COVERAGE = 0.90


def has_sufficient_discovery_coverage(
    discovered_properties,
    previous_completed_properties,
):
    """Return whether a discovered corpus is safe to use for deactivation."""

    if discovered_properties <= 0:
        return False

    # With no completed baseline there is nothing to compare or deactivate.
    if previous_completed_properties is None:
        return True

    if previous_completed_properties <= 0:
        return False

    minimum_expected = math.ceil(
        previous_completed_properties * MIN_DISCOVERY_COVERAGE
    )

    return discovered_properties >= minimum_expected
