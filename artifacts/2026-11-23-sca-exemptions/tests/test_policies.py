from exempt.book import Txn
from exempt.policies import (
    ChallengeAll,
    FlatTop,
    State,
    TraRisk,
    TraTight,
    TraPlain,
)


def txn(amount_cents: int, risk: float = 0.05, card: str = "c1") -> Txn:
    return Txn(
        id=0,
        day=0,
        amount_cents=amount_cents,
        channel="web",
        mcc="fashion",
        card=card,
        risk=risk,
        is_fraud=False,
        abandon_draw=0.5,
        stop_draw=0.5,
    )


def test_challenge_all_never_exempts():
    policy = ChallengeAll()
    state = State()
    for cents in (500, 2000, 30000, 90000):
        decision = policy.decide(txn(cents, risk=0.0), 50000, state)
        assert not decision.exempt
        assert decision.basis == "challenge"


def test_low_value_counter_exempts_five_twenty_euro_payments_then_stops():
    policy = TraPlain()
    state = State()
    for _ in range(5):
        assert policy.decide(txn(2000), 0, state).exempt
    assert not policy.decide(txn(2000), 0, state).exempt
    assert state.counter_refusals == 1
    assert state.low_value_exemptions == 5


def test_a_challenge_resets_the_streak():
    policy = TraPlain()
    state = State()
    for _ in range(5):
        policy.decide(txn(2000), 0, state)
    policy.decide(txn(3100), 0, state)  # over the cap, so it is challenged
    assert policy.decide(txn(2000), 0, state).exempt


def test_low_value_amount_cap_is_hard():
    policy = TraPlain()
    state = State()
    assert not policy.decide(txn(3001), 0, state).exempt
    assert policy.decide(txn(3000), 0, state).exempt


def test_tra_respects_ceiling_and_risk():
    policy = TraRisk()
    state = State()
    assert policy.decide(txn(20000, risk=0.05), 25000, state).basis == "tra"
    assert not policy.decide(txn(30000, risk=0.05), 25000, state).exempt
    assert not policy.decide(txn(20000, risk=0.9), 25000, state).exempt


def test_no_tra_ceiling_means_no_tra_exemption():
    policy = TraRisk()
    state = State()
    assert not policy.decide(txn(20000, risk=0.0), 0, state).exempt


def test_ceiling_comes_from_the_lagged_rate():
    policy = TraRisk()
    assert policy.etv_for(None) == 0
    assert policy.etv_for(0.4) == 50000
    assert policy.etv_for(4.0) == 25000
    assert policy.etv_for(9.0) == 10000
    assert policy.etv_for(20.0) == 0


def test_tight_policy_steps_one_rung_down_for_the_same_estimate():
    assert TraRisk().etv_for(0.4) == 50000
    assert TraTight().etv_for(0.4) == 25000
    assert TraTight().etv_for(4.0) == 10000


def test_flat_policy_claims_the_top_band_regardless_of_anything():
    policy = FlatTop()
    assert policy.etv_for(None) == 50000
    assert policy.etv_for(40.0) == 50000
    assert policy.decide(txn(45000), 0, State()).exempt
