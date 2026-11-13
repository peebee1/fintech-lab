import pytest

from uwcal import book, policy


def test_break_even_is_derived_from_margin_and_lgd():
    assert policy.BREAK_EVEN_PD == pytest.approx(policy.MARGIN / policy.LGD)


def test_single_loan_value_math():
    performing = book.Loan(0, 0.2, 0.3, 0.7, 60.0, 0, 40, 1000.0, 0, 0.05)
    defaulted = book.Loan(1, 0.2, 0.3, 0.7, 60.0, 1, 40, 1000.0, 1, 0.05)

    good = policy.evaluate([0.02], [performing])
    assert good.approved == 1
    assert good.value == pytest.approx(policy.MARGIN * 1000.0)
    assert good.realized_loss == 0.0
    assert good.reported_expected_loss == pytest.approx(0.02 * 1000.0 * policy.LGD)

    bad = policy.evaluate([0.02], [defaulted])
    assert bad.value == pytest.approx(policy.MARGIN * 1000.0 - policy.LGD * 1000.0)
    assert bad.realized_loss == pytest.approx(policy.LGD * 1000.0)


def test_rejection_bookkeeping():
    performing = book.Loan(0, 0.2, 0.3, 0.7, 60.0, 0, 40, 1000.0, 0, 0.05)
    defaulted = book.Loan(1, 0.2, 0.3, 0.7, 60.0, 1, 40, 1000.0, 1, 0.05)
    result = policy.evaluate([0.5, 0.5], [performing, defaulted])
    assert result.approved == 0
    assert result.rejected_good_count == 1
    assert result.forgone_contribution == pytest.approx(policy.MARGIN * 1000.0)
    assert result.avoided_loss == pytest.approx(policy.LGD * 1000.0)
    assert result.value == 0.0


def test_break_even_loan_is_neither_profit_nor_loss():
    loan = book.Loan(0, 0.2, 0.3, 0.7, 60.0, 0, 40, 1000.0, 0, 0.05)
    at_cutoff = policy.evaluate([policy.BREAK_EVEN_PD], [loan])
    assert at_cutoff.approved == 1


def test_higher_cutoff_approves_more(card, parts):
    holdout = parts["holdout"]
    preds = card.predict(holdout)
    counts = [policy.evaluate(preds, holdout, cutoff=c).approved for c in (0.02, 0.05, 0.2)]
    assert counts == sorted(counts)
    assert counts[0] < counts[-1]


def test_loss_multiple_guards_zero_realized_loss():
    loan = book.Loan(0, 0.2, 0.3, 0.7, 60.0, 0, 40, 1000.0, 0, 0.05)
    assert policy.evaluate([0.01], [loan]).loss_multiple == 0.0


def test_probability_count_must_match(card, parts):
    with pytest.raises(ValueError):
        policy.evaluate([0.1], parts["holdout"][:3])
