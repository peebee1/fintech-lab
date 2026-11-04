import pytest

from screenlab import match
from screenlab.model import ListEntry, Subject


def entry(**kw):
    base = dict(entry_id="SDN-001", name="Muhammad Al-Rashid", aliases=("Mohammed Al Rashid",),
                dob="1979-04-12", countries=("SY",), id_numbers=("P12345678",), program="SDGT")
    base.update(kw)
    return ListEntry(**base)


def subject(**kw):
    base = dict(subject_id="C-00001", name="Muhammad Al-Rashid", dob="1979-04-12",
                country="SY", national_id="ID000001", segment="retail")
    base.update(kw)
    return Subject(**base)


def test_dob_state_separates_absent_from_conflict():
    """Missing data must never be scored like contradictory data."""
    listed = entry()
    assert match.dob_state(listed, subject()) == "exact"
    assert match.dob_state(listed, subject(dob="")) == "absent"
    assert match.dob_state(listed, subject(dob="1979")) == "conflict"
    assert match.dob_state(listed, subject(dob="1988-04-12")) == "conflict"
    year_listed = entry(dob="1979")
    assert match.dob_state(year_listed, subject(dob="1979-12-01")) == "year"
    assert match.dob_state(entry(dob=""), subject()) == "absent"


def test_id_number_in_list_is_a_confirmed_match():
    alert, reason = match._entity_score(
        subject(name="Mohammed Al-Rashid", dob="1987-01-01", country="DE", national_id="P12345678"),
        entry(), 0.97)
    assert reason == ""
    assert alert is not None
    assert alert.rule == "id_exact"
    assert alert.score == 1.0
    assert "identity number in list" in alert.reasons


def test_near_exact_name_outranks_a_dob_conflict_instead_of_clearing_it():
    alert, reason = match._entity_score(subject(dob="1961-04-12"), entry(), 0.99)
    assert reason == ""
    assert alert is not None
    assert alert.rule == "name_over_dob_conflict"
    assert alert.score < 0.8


def test_weak_name_with_a_dob_conflict_is_suppressed_and_counted():
    alert, reason = match._entity_score(subject(dob="1961-04-12"), entry(), 0.90)
    assert alert is None
    assert reason == "weak_name_dob_conflict"


def test_missing_dob_alerts_without_being_treated_as_evidence_against():
    alert, _ = match._entity_score(subject(dob=""), entry(), 0.93)
    assert alert is not None
    assert alert.rule == "name_no_dob"
    assert "date of birth missing on one side" in alert.reasons


def test_country_conflict_demotes_but_does_not_clear():
    alert, _ = match._entity_score(subject(country="DE"), entry(), 0.96)
    assert alert is not None
    assert any("country conflicts" in r for r in alert.reasons)


def test_scores_are_clipped_and_rules_are_named():
    alert, _ = match._entity_score(subject(), entry(), 0.99)
    assert alert is not None
    assert 0.0 <= alert.score <= 1.0
    assert alert.rule in {
        "id_exact", "name_over_dob_conflict", "name_exact_dob", "name_close_dob",
        "name_variant_dob", "name_no_dob", "name_only",
    }


def test_run_rejects_an_unknown_policy(dataset):
    with pytest.raises(ValueError):
        match.run(dataset, "vibes")


def test_exact_policy_only_fires_on_identical_or_alias_names(dataset):
    alerts = match.run(dataset, "exact_name")
    assert alerts
    subjects = {s.subject_id: s for s in dataset.subjects}
    for alert in alerts:
        assert subjects[alert.subject_id].name.strip()
        assert alert.score == 1.0
        assert alert.rule == "exact_name"


def test_every_policy_returns_alerts_with_known_rules(dataset):
    known = {
        "exact_name", "name_only", "name_and_country", "id_exact",
        "name_over_dob_conflict", "name_exact_dob", "name_close_dob",
        "name_variant_dob", "name_no_dob",
    }
    for policy in match.POLICIES:
        alerts = match.run(dataset, policy)
        assert alerts, policy
        for alert in alerts:
            assert alert.rule in known
            assert 0.0 <= alert.score <= 1.0
            assert 0.0 <= alert.name_score <= 1.0
