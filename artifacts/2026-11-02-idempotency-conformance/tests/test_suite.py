import json

from idemconform import suite

FAILING = {
    "naive": {
        "missing_key", "replay_same_body", "replay_different_body", "overlap_two", "burst_five",
        "crash_after_effect", "in_lease_replay", "expiry",
    },
    "global_key": {"key_scope"},
    "store_after": {"overlap_two", "burst_five", "crash_after_effect", "in_lease_replay", "expiry"},
    "error_cached": {"error_then_retry"},
    "reserve": set(),
}


def test_suite_has_one_named_check_per_property():
    names = [c.name for c in suite.CHECKS]
    assert len(names) == 11
    assert len(set(names)) == len(names)
    assert all(c.proves for c in suite.CHECKS)


def test_the_matrix_is_what_the_readme_claims():
    payload = suite.run_all()
    assert payload["meta"]["checks"] == 11
    by_mode = {impl["mode"]: impl for impl in payload["implementations"]}
    assert set(by_mode) == set(FAILING)
    for mode, expected in FAILING.items():
        impl = by_mode[mode]
        failed = {r["check"] for r in impl["results"] if not r["passed"]}
        assert failed == expected, f"{mode}: {sorted(failed)} != {sorted(expected)}"
        assert impl["checks_passed"] == 11 - len(expected)


def test_the_reference_implementation_passes_every_check():
    payload = suite.run_all(["reserve"])
    impl = payload["implementations"][0]
    assert impl["checks_passed"] == impl["checks_total"] == 11
    assert impl["violation_classes"] == {}
    assert impl["excess_charges"] == 0


def test_excess_charges_and_value_are_consistent():
    payload = suite.run_all()
    for impl in payload["implementations"]:
        excess = sum(max(0, r["charges"] - r["expected_charges"]) for r in impl["results"])
        value = sum(max(0, r["charges"] - r["expected_charges"]) * r["value_minor"] for r in impl["results"])
        assert impl["excess_charges"] == excess
        assert impl["excess_value_minor"] == value


def test_every_failed_check_carries_a_violation_code():
    payload = suite.run_all()
    for impl in payload["implementations"]:
        for result in impl["results"]:
            assert result["passed"] == (result["violations"] == [])


def test_two_runs_produce_identical_results():
    first = json.dumps(suite.run_all(), sort_keys=True)
    second = json.dumps(suite.run_all(), sort_keys=True)
    assert first == second


def test_a_suite_with_no_failures_reports_itself_as_undiscriminating():
    payload = suite.run_all(["reserve"])
    assert "not discriminating" in suite.summary_text(payload)
    mixed = suite.run_all(["naive", "reserve"])
    assert "not discriminating" not in suite.summary_text(mixed)


def test_overhead_returns_positive_microseconds():
    payload = suite.measure_overhead(500)
    assert payload["n"] == 500
    for mode in ("naive", "store_after", "reserve"):
        assert payload["modes"][mode] > 0
