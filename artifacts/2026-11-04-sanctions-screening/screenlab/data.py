"""Synthetic watchlist and customer book, with injected ground truth.

The list structure mirrors a published designations list: a primary name, zero
to two transliteration aliases, a date of birth that is sometimes only a year,
one or more countries, and an identity number that is often absent.

No real person is named here. Every value comes from a fixed pool in this file,
so the dataset is reproducible from the seed and safe to publish.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict

from .model import Dataset, ListEntry, Subject
from .text import similarity

SEED = 20261104
LISTED = 26
BOOK_SIZE = 2400
TRUE_COUNT = 36
NAMESAKE_COUNT = 110
NEAR_MISS_COUNT = 60

GIVEN = {
    "MENA": ["Muhammad", "Ahmed", "Yusuf", "Omar", "Khalid", "Ibrahim", "Abdullah",
             "Hassan", "Tariq", "Samir", "Fatima", "Aisha", "Layla", "Nadia",
             "Zainab", "Mariam", "Bilal", "Hamza", "Rania", "Salma", "Yasmin",
             "Faisal", "Karim", "Huda"],
    "SAS": ["Arjun", "Rahul", "Vikram", "Sanjay", "Imran", "Farhan", "Neha",
            "Priya", "Anjali", "Ayesha", "Rohan", "Aditya", "Kavita", "Sneha",
            "Deepak", "Meera", "Ravi", "Zara"],
    "EAS": ["Wei", "Jing", "Ming", "Ling", "Hui", "Ying", "Tao", "Chen",
            "Xiang", "Yun", "Bo", "Fang", "Jian", "Lan", "Qiang", "Xiu"],
    "LATAM": ["Carlos", "Jorge", "Miguel", "Luis", "Diego", "Ana", "Rosa", "Elena",
              "Sofia", "Mateo", "Paula", "Andres", "Camila", "Rodrigo", "Isabel",
              "Tomas"],
    "EEUR": ["Dmitri", "Sergei", "Andrei", "Nikolai", "Olga", "Irina", "Katya", "Pavel",
             "Viktor", "Svetlana", "Yuri", "Anya", "Mikhail", "Larisa", "Oleg",
             "Tatiana"],
    "WEUR": ["Thomas", "Daniel", "Michael", "Sarah", "Laura", "Emma", "Peter", "Julia",
             "Andrew", "Claire", "Martin", "Helen", "Simon", "Rachel", "Gareth",
             "Fiona"],
}

FAMILY = {
    "MENA": ["Al-Rashid", "Al-Mansouri", "Haddad", "Khoury", "Nasser", "Saleh",
             "Barakat", "Hamdan", "Qureshi", "Zaman", "Darwish", "Fadel",
             "Jaber", "Kassem", "Maloof", "Sabbagh"],
    "SAS": ["Sharma", "Patel", "Iyer", "Reddy", "Khan", "Mehta", "Chowdhury", "Bhat",
            "Kulkarni", "Sinha", "Nair", "Desai", "Rao", "Ali"],
    "EAS": ["Wang", "Li", "Zhang", "Chen", "Liu", "Huang", "Xu", "Zhao",
            "Zhou", "Wu", "Sun", "Guo", "Lin", "He"],
    "LATAM": ["Morales", "Vargas", "Castillo", "Herrera", "Silva", "Ramos", "Ortiz",
              "Fuentes", "Navarro", "Paredes", "Quiroga", "Salas", "Tapia"],
    "EEUR": ["Volkov", "Petrov", "Sokolov", "Ivanov", "Kuznetsov", "Orlov", "Lebedev",
             "Morozov", "Novikov", "Fedorov", "Zaitsev", "Belov", "Gusev"],
    "WEUR": ["Brennan", "Whitfield", "Hollis", "Marsh", "Doyle", "Fenwick", "Ashby",
             "Cadwell", "Prentice", "Rutherford", "Ellery", "Sandford"],
}

COUNTY = {
    "MENA": ["SY", "IR", "IQ", "AE", "JO"],
    "SAS": ["PK", "IN", "BD", "LK"],
    "EAS": ["CN", "HK", "SG", "MY"],
    "LATAM": ["MX", "CO", "PE", "VE"],
    "EEUR": ["RU", "BY", "UA", "KZ"],
    "WEUR": ["GB", "DE", "FR", "NL"],
}

OTHER_COUNTRY = {
    "MENA": ["DE", "TR", "GB"],
    "SAS": ["GB", "AE", "CA"],
    "EAS": ["CA", "AU", "GB"],
    "LATAM": ["ES", "US", "GB"],
    "EEUR": ["GB", "DE", "CY"],
    "WEUR": ["AU", "CA", "US"],
}

TRANSLIT_PAIRS = (
    ("muhammad", "mohammed"), ("mohammed", "muhammad"), ("ahmed", "ahmad"),
    ("ahmad", "ahmed"), ("hussein", "husain"), ("yusuf", "yousef"),
    ("ibrahim", "ebrahim"), ("abdullah", "abdallah"), ("hassan", "hasan"),
    ("tariq", "tarik"), ("fatima", "fatimah"), ("aisha", "ayesha"),
    ("zainab", "zaynab"), ("khalid", "khaled"), ("omar", "umar"),
    ("layla", "leila"), ("mariam", "maryam"), ("samir", "sameer"),
    ("nadia", "nadya"), ("rashid", "rasheed"), ("jing", "ching"),
    ("wei", "way"), ("dmitri", "dmitry"), ("sergei", "sergey"),
)

PROGRAMS = ["SDGT", "IRAN", "SYRIA", "DPRK3", "RUSSIA-EO14024"]


def _swap_translit(name: str) -> str:
    low = name.lower()
    for src, dst in TRANSLIT_PAIRS:
        if src in low:
            return name.lower().replace(src, dst, 1).title()
    return name


def _squash(name: str) -> str:
    low = name.lower()
    for ch in "bcdfgklmnprstz":
        if ch * 2 in low:
            return name.replace(ch * 2, ch)
    return _swap_translit(name)


def _reorder(name: str) -> str:
    parts = name.split()
    return " ".join([parts[-1]] + parts[:-1]) if len(parts) > 1 else name


def _drop_middle(name: str) -> str:
    parts = name.split()
    if len(parts) < 3:
        return _reorder(name)
    return " ".join([parts[0], parts[-1]])


def _dehyphenate(name: str) -> str:
    return name.replace("Al-", "Al ").replace("al-", "al ")


VARIANT_RULES = (_swap_translit, _squash, _reorder, _drop_middle, _dehyphenate)


def variant(name: str, rng: random.Random, steps: int = 1) -> str:
    """Apply `steps` documented drift rules. One step stays recognisable; two is
    what a list alias usually looks like by the time it reaches a screen."""
    out = name
    for _ in range(steps):
        out = VARIANT_RULES[rng.randrange(len(VARIANT_RULES))](out)
    return out


def _dob(rng: random.Random) -> str:
    return f"{rng.randrange(1952, 2001)}-{rng.randrange(1, 13):02d}-{rng.randrange(1, 29):02d}"


def _dob_year(dob: str) -> str:
    return dob.split("-")[0]


def _shift_year(dob: str, years: int) -> str:
    year, month, day = dob.split("-")
    return f"{int(year) + years:04d}-{month}-{day}"


def _person(rng: random.Random) -> tuple[str, str, str]:
    region = rng.choice(list(GIVEN))
    return rng.choice(GIVEN[region]), rng.choice(FAMILY[region]), region


def build(seed: int = SEED) -> Dataset:
    rng = random.Random(seed)
    regions = list(GIVEN)
    used_names: set[str] = set()
    entries: list[ListEntry] = []

    while len(entries) < LISTED:
        region = regions[len(entries) % len(regions)]
        given = rng.choice(GIVEN[region])
        family = rng.choice(FAMILY[region])
        name = f"{given} {family}"
        if name in used_names:
            continue
        used_names.add(name)
        aliases = [variant(name, rng, 2)] if rng.random() < 0.7 else []
        if rng.random() < 0.35:
            extra = variant(name, rng, 2)
            if extra not in aliases and extra != name:
                aliases.append(extra)
        dob = _dob(rng)
        if rng.random() < 0.3:
            dob = _dob_year(dob)  # list publishes year only
        countries = (rng.choice(COUNTY[region]),)
        if rng.random() < 0.3:
            countries = countries + (rng.choice(OTHER_COUNTRY[region]),)
        id_numbers = (f"P{rng.randrange(10**7, 10**8)}",) if rng.random() < 0.7 else ()
        entries.append(ListEntry(
            entry_id=f"SDN-{len(entries) + 1:03d}",
            name=name,
            aliases=tuple(aliases),
            dob=dob,
            countries=countries,
            id_numbers=id_numbers,
            program=rng.choice(PROGRAMS),
        ))

    subjects: list[Subject] = []

    def add(name: str, dob: str, country: str, national_id: str, segment: str,
            truth: str | None, kind: str) -> None:
        subjects.append(Subject(
            subject_id=f"C-{len(subjects) + 1:05d}",
            name=name.strip(),
            dob=dob,
            country=country,
            national_id=national_id,
            segment=segment,
            truth_entry_id=truth,
            truth_kind=kind,
        ))

    # Injected true matches: the customers who really are the listed person.
    # A year-only match is only possible when the list itself publishes a year,
    # otherwise the truth is either a name variant or a relocated identity.
    quota = ["exact", "alias", "alias", "relocated"]
    for index in range(TRUE_COUNT):
        entry = entries[index % len(entries)]
        if len(entry.dob) == 4:
            kind = "year_only" if index % 2 == 0 else "alias"
        else:
            kind = quota[index % len(quota)]
        if index % 12 == 11:
            kind = "kunya"  # listed under a kunya: the list name never appears
        elif index % 6 == 5:
            kind = "thin_kyc"  # no date of birth on file, name is a variant
        if kind == "exact":
            name, dob, country = entry.name, entry.dob, entry.countries[0]
            national_id = entry.id_numbers[0] if entry.id_numbers else f"ID{index:06d}"
        elif kind == "alias":
            name = entry.aliases[0] if entry.aliases else variant(entry.name, rng, 2)
            dob = entry.dob if len(entry.dob) == 10 else f"{entry.dob}-{rng.randrange(1, 13):02d}-{rng.randrange(1, 29):02d}"
            country = entry.countries[0]
            national_id = f"ID{index:06d}"
        elif kind == "year_only":
            name = entry.aliases[0] if entry.aliases else entry.name
            dob = f"{_dob_year(entry.dob)}-{rng.randrange(1, 13):02d}-{rng.randrange(1, 29):02d}"
            country = entry.countries[0]
            national_id = f"ID{index:06d}"
        elif kind == "kunya":
            family = entry.name.split()[-1].replace("Al-", "").replace("al-", "")
            name = f"Abu {family}"
            dob = entry.dob if len(entry.dob) == 10 else f"{entry.dob}-{rng.randrange(1, 13):02d}-{rng.randrange(1, 29):02d}"
            country = entry.countries[0]
            national_id = f"ID{index:06d}"
        elif kind == "thin_kyc":
            name = variant(entry.name, rng, 2)
            dob = ""
            country = rng.choice(OTHER_COUNTRY[regions[index % len(regions)]])
            national_id = f"ID{index:06d}"
        else:  # relocated: name and papers match, the address does not
            name = variant(entry.name, rng, 2)
            dob = entry.dob if len(entry.dob) == 10 else f"{entry.dob}-{rng.randrange(1, 13):02d}-{rng.randrange(1, 29):02d}"
            country = rng.choice(OTHER_COUNTRY[regions[index % len(regions)]])
            national_id = entry.id_numbers[0] if entry.id_numbers else f"ID{index:06d}"
        add(name, dob, country, national_id, rng.choice(["retail", "sme"]),
            entry.entry_id, kind)

    # Namesakes: same name, different person. This is the false positive class.
    for index in range(NAMESAKE_COUNT):
        entry = entries[index % len(entries)]
        name = entry.name if index % 2 == 0 else (
            entry.aliases[0] if entry.aliases else variant(entry.name, rng))
        base = entry.dob if len(entry.dob) == 10 else f"{entry.dob}-01-01"
        dob = _shift_year(base, rng.randrange(7, 26))
        country = rng.choice(OTHER_COUNTRY[regions[index % len(regions)]])
        add(name, dob, country, f"ID{index:06d}", rng.choice(["retail", "sme"]),
            None, "namesake")

    # Near misses: one shared token, a family name one edit away, other facts differ.
    for index in range(NEAR_MISS_COUNT):
        entry = entries[(index + 5) % len(entries)]
        given = entry.name.split()[0]
        family = entry.name.split()[-1]
        mutated = family[:-1] + rng.choice("aeiou") if len(family) > 4 else family + "i"
        add(f"{given} {mutated}", _dob(rng), rng.choice(OTHER_COUNTRY[regions[index % len(regions)]]),
            f"ID{index:06d}", "retail", None, "near_miss")

    # The rest of the book: nothing to do with the list.
    while len(subjects) < BOOK_SIZE:
        given, family, region = _person(rng)
        name = f"{given} {family}"
        if any(similarity(name, entry_name) >= 0.93
               for entry in entries for entry_name in entry.all_names()):
            continue
        add(name, _dob(rng), rng.choice(COUNTY[region]), f"ID{len(subjects):06d}",
            "retail" if rng.random() < 0.8 else "sme", None, "clean")

    # Shuffle before numbering. If ids follow the generation order, the true
    # matches all sit at the front of the book and any tie break by id becomes
    # an accidental oracle: a screen that "catches" 28 of 36 only because ids
    # happen to correlate with the label.
    rng.shuffle(subjects)
    subjects = [
        Subject(subject_id=f"C-{index:05d}", name=s.name, dob=s.dob, country=s.country,
                national_id=s.national_id, segment=s.segment,
                truth_entry_id=s.truth_entry_id, truth_kind=s.truth_kind)
        for index, s in enumerate(subjects, start=1)
    ]

    dataset = Dataset(entries=tuple(entries), subjects=tuple(subjects), seed=seed)
    validate(dataset)
    return dataset


def validate(dataset: Dataset) -> None:
    """Fail loudly if the injected truth is ambiguous, so precision means something."""
    ids = [s.subject_id for s in dataset.subjects]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate subject ids")
    entries = {e.entry_id: e for e in dataset.entries}
    if len(entries) != len(dataset.entries):
        raise ValueError("duplicate entry ids")
    for subject in dataset.subjects:
        if subject.truth_entry_id is None:
            continue
        entry = entries[subject.truth_entry_id]
        if not subject.dob:
            continue  # thin KYC file: the record exists but carries no date
        if entry.dob and len(entry.dob) == 4:
            if subject.dob.split("-")[0] != entry.dob:
                raise ValueError(f"{subject.subject_id} truth dob does not agree with list")
        elif entry.dob and subject.dob != entry.dob:
            raise ValueError(f"{subject.subject_id} truth dob does not agree with list")
    kinds = {s.truth_kind for s in dataset.subjects if s.truth_entry_id}
    allowed = {"exact", "alias", "year_only", "relocated", "thin_kyc", "kunya"}
    if not kinds <= allowed or len(kinds) < 2:
        raise ValueError(f"bad truth kinds: {kinds}")


def digest(dataset: Dataset) -> str:
    """Content hash of the dataset, so a run can prove which data produced a number."""
    payload = {
        "seed": dataset.seed,
        "entries": [asdict(e) for e in dataset.entries],
        "subjects": [asdict(s) for s in dataset.subjects],
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()
