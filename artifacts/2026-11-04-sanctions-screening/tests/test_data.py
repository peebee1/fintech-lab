import pytest

from screenlab import data
from screenlab.model import Dataset


def test_the_same_seed_builds_the_same_book(dataset):
    assert data.digest(dataset) == data.digest(data.build())
    assert len(dataset.subjects) == data.BOOK_SIZE


def test_a_different_seed_builds_a_different_book():
    assert data.digest(data.build(seed=7)) != data.digest(data.build(seed=8))


def test_ground_truth_counts_are_exact(dataset):
    designated = [s for s in dataset.subjects if s.truth_entry_id]
    assert len(dataset.entries) == data.LISTED
    assert len(designated) == data.TRUE_COUNT
    assert sum(1 for s in dataset.subjects if s.truth_kind == "namesake") == data.NAMESAKE_COUNT
    assert len(dataset.subjects) == data.BOOK_SIZE


def test_every_truth_kind_appears_and_is_consistent_with_the_list(dataset):
    kinds = {s.truth_kind for s in dataset.subjects if s.truth_entry_id}
    assert kinds == {"exact", "alias", "year_only", "relocated", "thin_kyc", "kunya"}
    for subject in dataset.designated:
        entry = dataset.entry_by_id(subject.truth_entry_id)
        if subject.dob and len(entry.dob) == 10:
            assert subject.dob == entry.dob
        if subject.dob and len(entry.dob) == 4:
            assert subject.dob.split("-")[0] == entry.dob


def test_a_broken_truth_record_is_rejected(dataset):
    broken = list(dataset.subjects)
    index = next(i for i, s in enumerate(broken) if s.truth_entry_id and len(s.dob) == 10)
    broken[index] = type(broken[index])(**{**broken[index].__dict__, "dob": "1901-01-01"})
    with pytest.raises(ValueError):
        data.validate(Dataset(entries=dataset.entries, subjects=tuple(broken), seed=dataset.seed))


def test_namesakes_are_lookalikes_flagged_as_not_designated(dataset):
    from screenlab.text import similarity

    namesakes = [s for s in dataset.subjects if s.truth_kind == "namesake"]
    assert len(namesakes) == data.NAMESAKE_COUNT
    listed = [n for e in dataset.entries for n in e.all_names()]
    for subject in namesakes:
        assert subject.truth_entry_id is None
        assert subject.dob and subject.country
        # a namesake is only interesting if the name really looks like a listed one,
        # so every one must trip the entity resolution screen at its threshold
        assert max(similarity(subject.name, name) for name in listed) >= 0.88


def test_the_book_contains_no_real_identifiers(dataset):
    for subject in dataset.subjects:
        assert subject.national_id.startswith("ID") or subject.national_id.startswith("P")
        parts = subject.dob.split("-") if subject.dob else ["0000"]
        assert len(parts) in {1, 3}
        assert len(parts[0]) == 4
