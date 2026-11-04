"""Name folding, phonetic keys, and string similarity.

Everything here is pure: no network, no clock, no state. Screening quality is
decided almost entirely by how aggressively names are folded before comparison,
so this module is the one that has to be right.
"""

from __future__ import annotations

import unicodedata

HONORIFICS = {
    "mr", "mrs", "ms", "miss", "dr", "prof", "eng", "shaykh", "sheikh",
    "haji", "hajji", "hafiz", "mullah", "maulana", "sir",
}
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v", "phd", "md", "esq"}

# Documented approximations. Applied to phonetic keys only, never to the
# display name, because collapsing "gh" inside a Latin name would be wrong.
TRANSLIT = (
    ("ph", "f"), ("ck", "k"), ("gh", "g"), ("kh", "k"),
    ("dh", "d"), ("th", "t"), ("sh", "s"), ("ee", "i"), ("oo", "u"),
)

VOWELS = set("aeiouy")


def fold(text: str) -> str:
    """Casefold, strip diacritics, remove punctuation, collapse whitespace."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    kept = []
    for ch in stripped.casefold():
        if ch.isalnum():
            kept.append(ch)
        elif ch in {"'", "."}:
            continue  # O'Brien and St. John fold to single tokens
        else:
            kept.append(" ")
    return " ".join("".join(kept).split())


def tokens(text: str) -> list[str]:
    """Folded name tokens with honorifics and generational suffixes removed."""
    out = [t for t in fold(text).split() if t not in HONORIFICS and t not in SUFFIXES]
    return out or fold(text).split()


def name_key(text: str) -> str:
    """Order independent key: sorted tokens, so 'Ali Hassan' == 'Hassan Ali'."""
    return " ".join(sorted(tokens(text)))


def collapse_doubles(token: str) -> str:
    out = []
    for ch in token:
        if out and out[-1] == ch:
            continue
        out.append(ch)
    return "".join(out)


def phonetic(token: str) -> str:
    """Consonant skeleton: the view that survives transliteration drift."""
    token = collapse_doubles(fold(token).replace(" ", ""))
    for src, dst in TRANSLIT:
        token = token.replace(src, dst)
    if not token:
        return ""
    head = token[0]
    body = "".join(ch for ch in token[1:] if ch not in VOWELS)
    return head + body


def phonetic_key(text: str) -> str:
    return " ".join(sorted(phonetic(t) for t in tokens(text) if t))


_SOUNDEX = {
    **dict.fromkeys("bfpv", "1"), **dict.fromkeys("cgjkqsxz", "2"),
    **dict.fromkeys("dt", "3"), "l": "4", **dict.fromkeys("mn", "5"), "r": "6",
}


def soundex(token: str) -> str:
    letters = [ch for ch in fold(token) if ch.isalpha()]
    if not letters:
        return ""
    first = letters[0]
    digits = []
    previous = _SOUNDEX.get(first, "")
    for ch in letters[1:]:
        code = _SOUNDEX.get(ch, "")
        if code and code != previous:
            digits.append(code)
        if ch not in "hw":
            previous = code
    return (first + "".join(digits) + "000")[:4]


def jaro(a: str, b: str) -> float:
    """Jaro similarity, 0 to 1."""
    if a == b:
        return 1.0 if a else 0.0
    len_a, len_b = len(a), len(b)
    if len_a == 0 or len_b == 0:
        return 0.0
    window = max(len_a, len_b) // 2 - 1
    window = max(window, 0)
    flags_a = [False] * len_a
    flags_b = [False] * len_b
    matches = 0
    for i, ch in enumerate(a):
        low = max(0, i - window)
        high = min(i + window + 1, len_b)
        for j in range(low, high):
            if not flags_b[j] and b[j] == ch:
                flags_a[i] = flags_b[j] = True
                matches += 1
                break
    if matches == 0:
        return 0.0
    transpositions = 0
    k = 0
    for i in range(len_a):
        if not flags_a[i]:
            continue
        while not flags_b[k]:
            k += 1
        if a[i] != b[k]:
            transpositions += 1
        k += 1
    transpositions //= 2
    return (matches / len_a + matches / len_b + (matches - transpositions) / matches) / 3.0


def jaro_winkler(a: str, b: str, prefix_scale: float = 0.1) -> float:
    base = jaro(a, b)
    if base <= 0.7:
        return base
    prefix = 0
    for left, right in zip(a, b):
        if left != right or prefix == 4:
            break
        prefix += 1
    return min(1.0, base + prefix * prefix_scale * (1.0 - base))


def similarity(a: str, b: str) -> float:
    """Weighted blend of three views: raw text, order free key, phonetic key.

    A blend rather than a max: max acts as an OR and inflates every pair whose
    consonants happen to line up, which is how a screen ends up alerting on a
    third of the book. The order free key carries the most weight because a
    name arrives as given-family in one system and family-given in the other,
    and a whole string comparison punishes that reorder as if it were a typo.
    """
    full = jaro_winkler(fold(a), fold(b))
    order_free = jaro_winkler(name_key(a), name_key(b))
    sound = jaro_winkler(phonetic_key(a), phonetic_key(b))
    return 0.20 * full + 0.60 * order_free + 0.20 * sound
