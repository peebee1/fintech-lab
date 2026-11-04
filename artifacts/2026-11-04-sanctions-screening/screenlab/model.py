"""Typed records for the watchlist, the customer book, and one alert."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ListEntry:
    entry_id: str
    name: str
    aliases: tuple[str, ...]
    dob: str  # "1979-04-12", "1979", or "" when the list is silent
    countries: tuple[str, ...]
    id_numbers: tuple[str, ...]
    program: str

    def all_names(self) -> tuple[str, ...]:
        return (self.name,) + self.aliases


@dataclass(frozen=True)
class Subject:
    subject_id: str
    name: str
    dob: str
    country: str
    national_id: str
    segment: str
    truth_entry_id: str | None = None
    truth_kind: str = "clean"


@dataclass(frozen=True)
class Alert:
    subject_id: str
    entry_id: str
    name_score: float
    score: float
    rule: str
    reasons: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Dataset:
    entries: tuple[ListEntry, ...]
    subjects: tuple[Subject, ...]
    seed: int

    @property
    def designated(self) -> tuple[Subject, ...]:
        return tuple(s for s in self.subjects if s.truth_entry_id)

    def entry_by_id(self, entry_id: str) -> ListEntry:
        for entry in self.entries:
            if entry.entry_id == entry_id:
                return entry
        raise KeyError(entry_id)
