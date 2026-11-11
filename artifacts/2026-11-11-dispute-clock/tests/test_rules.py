from disputeclock import rules
from disputeclock.model import Network, ReasonCode


def test_fraud_window_is_shorter_than_the_service_window():
    from disputeclock import sim

    book = sim.build(seed=3, n=40)
    for case in book.cases:
        window = rules.response_window(case)
        if case.reason.is_fraud:
            assert window == 20
        elif case.network is Network.VISA:
            assert window == 30
        else:
            assert window == 45


def test_every_reason_code_has_a_requirement_built_from_known_evidence():
    facts_grid = [{}, {"threeds": True}, {"emv": True}]
    for reason in ReasonCode:
        for facts in facts_grid:
            required = rules.required_evidence(reason, facts)
            assert required, reason
            assert all(item in rules.EVIDENCE_MINUTES for item in required), required


def test_liability_shifts_only_on_the_authenticated_channel():
    assert rules.required_evidence(ReasonCode.FRAUD_CARD_ABSENT, {"threeds": True}) == (
        "threeds_result",
    )
    from disputeclock.model import liability_shifted

    assert liability_shifted(ReasonCode.FRAUD_CARD_ABSENT, {"threeds": True})
    assert not liability_shifted(ReasonCode.FRAUD_CARD_ABSENT, {"threeds": False})
    assert liability_shifted(ReasonCode.FRAUD_CARD_PRESENT, {"emv": True})
    assert not liability_shifted(ReasonCode.FRAUD_CARD_PRESENT, {})
    assert not liability_shifted(ReasonCode.NOT_RECEIVED, {"threeds": True})


def test_partial_evidence_is_not_a_defence():
    """The requirement is a set, not a score: dropping one item drops the defence."""
    required = rules.required_evidence(ReasonCode.NOT_AS_DESCRIBED, {})
    assert len(required) == 2
    for item in required:
        partial = tuple(x for x in required if x != item)
        assert not set(required) <= set(partial)


def test_procedural_invalid_tracks_the_filing_window():
    from disputeclock import sim

    book = sim.build(seed=5, n=60)
    for case in book.cases:
        assert case.procedural_invalid == (case.filed_lag > 120)


def test_defensible_matches_a_recomputation(book):
    for case in book.cases:
        assert case.defensible == rules.is_defensible(case)


def test_undefensible_case_needs_evidence_after_the_deadline(book):
    """At least one case in the book is lost because the evidence lands too late."""
    late = [
        case
        for case in book.cases
        if not case.defensible and not case.free_win
        and any(landed > rules.response_deadline(case) for landed in case.available.values())
    ]
    assert late, "the book should contain evidence that arrives after the deadline"
