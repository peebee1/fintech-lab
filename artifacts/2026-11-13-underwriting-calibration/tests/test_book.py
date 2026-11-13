import pytest

from uwcal import book


def test_same_seed_same_book(loans):
    again = book.build(seed=13, n=1200)
    assert [(loan.loan_id, loan.exposure, loan.defaulted) for loan in loans] == [
        (loan.loan_id, loan.exposure, loan.defaulted) for loan in again
    ]


def test_different_seed_different_book():
    a = book.build(seed=1, n=200)
    b = book.build(seed=2, n=200)
    assert [loan.defaulted for loan in a] != [loan.defaulted for loan in b]


def test_ids_are_contiguous_and_features_are_complete(loans):
    assert [loan.loan_id for loan in loans] == list(range(len(loans)))
    for loan in loans:
        assert len(loan.features()) == len(book.FEATURES)
        assert 0.0 < loan.true_pd < 1.0
        assert loan.defaulted in (0, 1)
        assert loan.exposure > 0


def test_low_ids_do_not_hold_the_defaults(loans):
    """Ids are assigned after a shuffle, so the first tenth is not the good book."""
    head = loans[: len(loans) // 10]
    rate = sum(loan.defaulted for loan in head) / len(head)
    overall = sum(loan.defaulted for loan in loans) / len(loans)
    assert abs(rate - overall) < 0.06


def test_observed_rate_tracks_the_generating_process(loans):
    observed = sum(loan.defaulted for loan in loans) / len(loans)
    expected = sum(loan.true_pd for loan in loans) / len(loans)
    assert observed == pytest.approx(expected, abs=0.03)
    assert 0.05 < observed < 0.30


def test_split_is_disjoint_and_ordered(parts):
    ids = [loan.loan_id for part in parts.values() for loan in part]
    assert len(ids) == len(set(ids))
    assert len(parts["holdout"]) > 0
    assert len(parts["train"]) > len(parts["calibration"]) > len(parts["holdout"]) / 2


def test_split_refuses_an_empty_holdout():
    with pytest.raises(ValueError):
        book.split(book.build(seed=3, n=2), train=2, calibration=1)


def test_sigmoid_and_logit_round_trip():
    for p in (0.01, 0.2, 0.5, 0.93):
        assert book.sigmoid(book.logit(p)) == pytest.approx(p, abs=1e-12)


def test_true_pd_rises_with_leverage():
    low = book.true_pd(0.15, 0.10, 0.55, 80.0, 0, 60)
    high = book.true_pd(0.62, 0.95, 1.02, 30.0, 3, 4)
    assert high > low * 5
