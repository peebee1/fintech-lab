import json

from exempt import bench
from exempt.book import generate
from exempt.policies import ChallengeAll, ExemptEverything, FlatTop, State, TraPlain, TraRisk

SMALL = dict(seed=5, days=16, per_day=150)


def small_replay(policy):
    return bench.replay(generate(**SMALL), policy)


def test_buckets_add_up():
    book = generate(**SMALL)
    for policy in (ChallengeAll(), FlatTop(), ExemptEverything()):
        result = bench.replay(book, policy)
        assert result.exempt_txn + result.challenges == len(book)
        assert result.low_value_txn + result.tra_txn == result.exempt_txn
        assert 0 <= result.exempt_cents <= result.processed_cents


def test_exempt_everything_loses_exactly_the_latent_fraud():
    book = generate(**SMALL)
    result = bench.replay(book, ExemptEverything())
    cases = sum(1 for t in book.txns if t.is_fraud)
    assert result.challenges == 0
    assert result.abandoned == 0
    assert result.fraud_cases == cases
    assert result.fraud_loss_cents == book.latent_fraud_cents()
    assert result.chargeback_fees_cents == cases * bench.CONFIG.chargeback_fee_cents


def test_challenge_all_is_never_in_breach_and_exempts_nothing():
    result = small_replay(ChallengeAll())
    assert result.exempt_txn == 0
    assert result.breach_days == 0
    assert result.abandoned > 0


def test_the_compliance_control_binds():
    # If the naive top band policy never breached, the table would prove nothing.
    result = small_replay(FlatTop())
    assert result.breach_days > 0
    assert result.max_overshoot_bps > 0


def _exempt_profile(policy, txns, etv):
    state = State()
    exempt = 0
    exempt_fraud = 0
    for txn in txns:
        if policy.decide(txn, etv, state).exempt:
            exempt += 1
            exempt_fraud += txn.amount_cents if txn.is_fraud else 0
    return exempt, exempt_fraud


def test_risk_screening_exempts_a_subset_at_a_fixed_ceiling():
    # At the same ceiling the risk test can only remove transactions, never add them.
    # The bench can show the reverse total, because screening keeps fraud down and
    # with it the ceiling up, which is the point of the test below.
    book = generate(**SMALL)
    plain = _exempt_profile(TraPlain(), book.txns, 25000)
    risk = _exempt_profile(TraRisk(), book.txns, 25000)
    assert risk[0] <= plain[0]
    assert risk[1] <= plain[1]
    assert risk[1] < plain[1]


def test_screening_holds_the_ceiling_higher_because_fraud_stays_lower():
    book = generate(**SMALL)
    plain = bench.replay(book, TraPlain())
    risk = bench.replay(book, TraRisk())
    assert risk.fraud_loss_cents <= plain.fraud_loss_cents
    assert risk.breach_days <= plain.breach_days


def test_replay_is_deterministic():
    book = generate(**SMALL)
    assert bench.replay(book, FlatTop()).as_dict() == bench.replay(book, FlatTop()).as_dict()


def test_run_is_deterministic_and_complete():
    first = bench.run(**SMALL)
    second = bench.run(**SMALL)
    assert first == second
    assert len(first["policies"]) == 7
    assert first["headline"]["best_compliant_policy"] is not None


def test_write_results_is_byte_stable_in_a_temporary_directory(tmp_path):
    bench.write_results(tmp_path, seed=5, days=16, per_day=150)
    first = (tmp_path / "summary.json").read_bytes(), (tmp_path / "summary.md").read_bytes()
    bench.write_results(tmp_path, seed=5, days=16, per_day=150)
    second = (tmp_path / "summary.json").read_bytes(), (tmp_path / "summary.md").read_bytes()
    assert first == second
    assert json.loads(first[0])["seed"] == 5


def test_default_results_path_resolves_at_call_time(tmp_path, monkeypatch):
    monkeypatch.setattr(bench, "RESULTS", tmp_path / "late")
    target = bench.write_results(None, seed=5, days=16, per_day=150)
    assert target == tmp_path / "late"
    assert (tmp_path / "late" / "summary.json").exists()
