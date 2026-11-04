import pytest

from screenlab import text


def test_fold_removes_diacritics_case_and_punctuation():
    assert text.fold("  José   O'Brien-Smith ") == "jose obrien smith"
    assert text.fold("AL-RASHID") == "al rashid"
    assert text.fold("") == ""


def test_tokens_drop_honorifics_and_suffixes():
    assert text.tokens("Dr. Ahmed Al-Rashid Jr") == ["ahmed", "al", "rashid"]
    assert text.tokens("Mr") == ["mr"]  # never returns empty


def test_name_key_is_order_independent():
    assert text.name_key("Hassan Ali") == text.name_key("Ali Hassan")
    assert text.name_key("Wei Wang") != text.name_key("Wang Wei Junior")


def test_phonetic_key_survives_transliteration():
    assert text.phonetic_key("Muhammad Al-Rashid") == text.phonetic_key("Mohammed Al Rashid")
    assert text.phonetic("Yusuf") == text.phonetic("Yousef")


def test_soundex_reference_values():
    assert text.soundex("Robert") == "r163"
    assert text.soundex("Rupert") == "r163"
    assert text.soundex("") == ""


def test_jaro_reference_values():
    assert text.jaro("MARTHA", "MARHTA") == pytest.approx(0.9444, abs=1e-4)
    assert text.jaro("DWAYNE", "DUANE") == pytest.approx(0.8222, abs=1e-4)
    assert text.jaro("", "") == 0.0
    assert text.jaro("abc", "xyz") == 0.0


def test_jaro_winkler_reference_values():
    assert text.jaro_winkler("MARTHA", "MARHTA") == pytest.approx(0.9611, abs=1e-4)
    assert text.jaro_winkler("DIXON", "DICKSONX") == pytest.approx(0.8133, abs=1e-4)


def test_similarity_is_symmetric_and_maxes_on_identity():
    assert text.similarity("Ahmed Haddad", "Ahmed Haddad") == pytest.approx(1.0)
    left = text.similarity("Ahmed Al-Haddad", "Ahmad Al Haddad")
    right = text.similarity("Ahmad Al Haddad", "Ahmed Al-Haddad")
    assert left == pytest.approx(right)


def test_similarity_blend_demotes_unrelated_names():
    """The blend is what stops a phonetic coincidence from looking like a match."""
    assert text.similarity("Wei Ling", "Wang Li") < 0.75
    variant_match = text.similarity("Muhammad Al-Rashid", "Mohammed Al Rashid")
    assert variant_match > 0.90
    assert variant_match < 1.0  # a variant is not an identity
