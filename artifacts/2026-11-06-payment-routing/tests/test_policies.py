"""Each policy does the thing it claims, including the ways it is wrong."""

from routelab import data, policies, psps

MICRO_CREDIT = data.Txn(0, 500, "credit", "domestic", "micro")
MID_CREDIT = data.Txn(1, 10000, "credit", "domestic", "mid")
LARGE_DEBIT = data.Txn(2, 80000, "debit", "domestic", "large")
CROSS_BORDER = data.Txn(3, 80000, "credit", "cross_border", "large")


def test_cheapest_is_the_fee_minimum_every_time():
    for amount in (300, 800, 1200, 5000, 80000):
        txn = data.Txn(0, amount, "credit", "domestic", "mid")
        first = policies.Cheapest().rank(txn)[0]
        assert psps.BY_NAME[first].fee(amount) == min(p.fee(amount) for p in psps.PSPS)


def test_cheapest_wins_micro_on_fee_and_loses_it_on_approval():
    cheapest = policies.Cheapest().rank(MICRO_CREDIT)[0]
    best = policies.Oracle().rank(MICRO_CREDIT)[0]
    assert cheapest == "charlie"
    assert best == "alpha"


def test_static_rules_follow_the_deck():
    assert policies.StaticRules().rank(CROSS_BORDER)[0] == "charlie"
    assert policies.StaticRules().rank(LARGE_DEBIT)[0] == "bravo"
    assert policies.StaticRules().rank(MID_CREDIT)[0] == "alpha"


def test_oracle_overrides_the_fee_choice_on_large_debit():
    assert policies.Cheapest().rank(LARGE_DEBIT)[0] == "alpha"
    assert policies.Oracle().rank(LARGE_DEBIT)[0] == "bravo"


def test_oracle_reacts_to_drift_where_the_rules_do_not():
    drift = psps.Drift(at=0, psp="bravo", delta=-5.0, token="channel:debit")
    shifted = policies.Oracle(drift=drift).rank(LARGE_DEBIT)[0]
    assert shifted != "bravo"
    assert policies.StaticRules().rank(LARGE_DEBIT)[0] == "bravo"


def test_thompson_counts_wins_and_losses_per_context():
    policy = policies.Thompson()
    for _ in range(5):
        policy.observe(MID_CREDIT, "alpha", True, 100)
    for _ in range(3):
        policy.observe(MID_CREDIT, "alpha", False, -2)
    assert policy.params(MID_CREDIT.context, "alpha") == (6.0, 4.0)


def test_thompson_prefers_an_arm_that_keeps_winning():
    policy = policies.Thompson(seed=1)
    for _ in range(60):
        policy.observe(MID_CREDIT, "bravo", True, 100)
    picks = [policy.rank(MID_CREDIT)[0] for _ in range(40)]
    assert picks.count("bravo") >= 30


def test_window_forgets_old_evidence():
    policy = policies.ThompsonWindow(window=4)
    for _ in range(8):
        policy.observe(MID_CREDIT, "alpha", True, 100)
    assert policy.params(MID_CREDIT.context, "alpha") == (5.0, 1.0)


def test_window_keeps_only_the_last_n_observations():
    policy = policies.ThompsonWindow(window=3)
    for outcome in (True, True, False, False):
        policy.observe(MID_CREDIT, "alpha", outcome, 100)
    # last three are win, loss, loss: a = 1 + 1, b = 1 + 2
    assert policy.params(MID_CREDIT.context, "alpha") == (2.0, 3.0)


def test_epsilon_greedy_explores_unseen_then_exploits():
    policy = policies.EpsilonGreedy(epsilon=0.0, seed=3)
    assert policy.rank(MID_CREDIT)[0] == "alpha"  # cheapest unseen arm first
    policy.observe(MID_CREDIT, "charlie", False, -2)  # every arm now seen once
    for _ in range(30):
        policy.observe(MID_CREDIT, "bravo", True, 120)
        policy.observe(MID_CREDIT, "alpha", False, -2)
    assert policy.rank(MID_CREDIT)[0] == "bravo"


def test_bandits_are_deterministic_for_a_seed():
    txn = MID_CREDIT
    a, b = policies.Thompson(seed=5), policies.Thompson(seed=5)
    assert [a.rank(txn) for _ in range(5)] == [b.rank(txn) for _ in range(5)]


def test_every_rank_is_a_full_permutation():
    for policy in (
        policies.Cheapest(),
        policies.StaticRules(),
        policies.Thompson(),
        policies.ThompsonWindow(),
        policies.EpsilonGreedy(),
        policies.Oracle(),
    ):
        assert sorted(policy.rank(LARGE_DEBIT)) == sorted(psps.names())
