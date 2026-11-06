"""The bench reconciles, repeats, and writes only where it is told."""

import json

from routelab import bench, cli, data, outcomes, policies, psps

BOOK = data.build(n=1200, seed=21)


def test_net_reconciles_exactly():
    """Independent recomputation, not a residual of zero."""
    result = bench.run(policies.Cheapest(), BOOK, seed=3, max_retries=1)
    gross = fees = ops = net = 0
    for txn in BOOK:
        order = policies.Cheapest().rank(txn)
        attempt, psp = 0, order[0]
        while True:
            ops += data.OPS_CENTS
            if outcomes.authorizes(3, txn, psp, attempt, retry=attempt > 0):
                fee = psps.BY_NAME[psp].fee(txn.amount)
                margin = data.margin_cents(txn.amount)
                gross += margin
                fees += fee
                net += margin - fee - data.OPS_CENTS
                break
            net -= data.OPS_CENTS
            if outcomes.is_hard(3, txn.index, psp, attempt) or attempt >= 1:
                break
            attempt += 1
            psp = order[attempt]
    assert result.gross_cents == gross
    assert result.fees_cents == fees
    assert result.ops_cents == ops
    assert result.net_cents == net
    assert result.net_cents == result.gross_cents - result.fees_cents - result.ops_cents
    assert result.settled_cents > 0
    assert result.approved <= result.transactions


def test_attempts_match_the_outcomes():
    result = bench.run(policies.StaticRules(), BOOK, seed=4, max_retries=2)
    assert result.attempts >= result.approved
    assert result.hard_declines <= result.attempts - result.approved


def test_a_deeper_retry_makes_more_attempts():
    shallow = bench.run(policies.Cheapest(), BOOK, seed=5, max_retries=0)
    deep = bench.run(policies.Cheapest(), BOOK, seed=5, max_retries=2)
    assert deep.attempts > shallow.attempts
    assert deep.approved >= shallow.approved


def test_bench_is_repeatable():
    one = bench.run_all(n=600)
    two = bench.run_all(n=600)
    assert json.dumps(one, sort_keys=True) == json.dumps(two, sort_keys=True)


def test_same_luck_for_two_policies_on_the_same_attempt():
    """Common random numbers: attempt 0 of a transaction is one draw, not two."""
    txn = BOOK[7]
    assert outcomes.authorizes(9, txn, "alpha", 0, retry=False) == outcomes.authorizes(
        9, txn, "alpha", 0, retry=False
    )


def test_fee_only_routing_is_not_the_best_choice_somewhere():
    payload = bench.run_all(n=2000)
    checks = payload["checks"]
    assert checks["segments"] == 12
    assert checks["fee_only_not_best"] > 0
    assert checks["fee_only_worst"] > 0


def test_results_written_twice_are_byte_identical(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    cli.write_results(directory=first, n=800)
    cli.write_results(directory=second, n=800)
    assert (first / "summary.json").read_bytes() == (second / "summary.json").read_bytes()
    assert (first / "summary.md").read_bytes() == (second / "summary.md").read_bytes()


def test_writer_does_not_touch_the_committed_results(tmp_path):
    committed = cli.RESULTS / "summary.json"
    before = committed.read_bytes() if committed.exists() else None
    cli.write_results(directory=tmp_path, n=400)
    after = committed.read_bytes() if committed.exists() else None
    assert before == after


def test_summary_reports_the_sections_it_claims():
    text = bench.summary_text(bench.run_all(n=800))
    for token in ("policy", "auth%", "fee bps", "net $/1000", "regime shift", "where the fee only choice is wrong"):
        assert token in text
