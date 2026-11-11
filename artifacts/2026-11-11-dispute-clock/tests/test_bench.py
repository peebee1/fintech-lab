import json
from functools import lru_cache

from disputeclock import bench, engine, sim
from disputeclock.model import TERMINAL

SMALL = dict(seed=13, n=800, horizon=360, budget=16)


@lru_cache(maxsize=1)
def payload():
    return bench.run(**SMALL)


def test_every_bench_check_passes():
    result = payload()
    assert result["passed"], result["checks"]
    assert all(result["checks"].values())


def test_two_runs_are_byte_identical():
    one = json.dumps(bench.run(**SMALL), sort_keys=True)
    two = json.dumps(bench.run(**SMALL), sort_keys=True)
    assert one == two


def test_money_is_conserved_per_policy():
    book = sim.build(seed=13, n=800)
    for policy in bench.LADDER:
        result = engine.run(book, policy(), budget_per_day=16)
        assert result.recovered_minor + result.lost_minor == book.total_minor


def test_every_case_ends_terminal_and_no_ceiling_is_exceeded():
    book = sim.build(seed=13, n=800)
    ceiling = book.recoverable_minor
    for policy in bench.LADDER:
        result = engine.run(book, policy(), budget_per_day=16)
        assert all(s.state in TERMINAL for s in result.states)
        assert result.recovered_minor <= ceiling


def test_recovery_rises_up_the_ladder():
    rates = [row["recovery_rate"] for row in payload()["policies"]]
    assert rates == sorted(rates), rates
    assert rates[-1] > rates[0]


def test_the_budget_binds():
    """A control that never bites proves nothing, so the bench checks it."""
    result = payload()
    assert result["checks"]["budget_binds"]
    assert result["unbounded"]["recovered_usd"] > result["policies"][-1]["recovered_usd"]


def test_the_deadline_binds():
    result = payload()
    assert result["checks"]["deadline_binds"]
    assert result["policies"][0]["forfeited_cases"] > 0
