"""The only forecast a policy gets: trailing history, rounded up, with an uplift."""

from __future__ import annotations

import math

from .book import Book, Site

UPLIFT = 1.10
OCCURRENCES = 4


def trailing_daily(book: Book, site: Site, day: int, occurrences: int = OCCURRENCES) -> int:
    """Mean of the last few same weekday demands, using rows strictly before `day`.

    Before enough history exists the site's stated base load stands in. That is a
    parameter of the site, not an observation of the future, so the no lookahead
    property holds from day 0.
    """
    same = [row.notes for row in book.rows[site.id][:day] if row.day % 7 == day % 7]
    if not same:
        return max(1, math.ceil(site.base_notes * UPLIFT))
    window = same[-occurrences:]
    return max(1, math.ceil(sum(window) / len(window) * UPLIFT))


def actual_daily(book: Book, site: Site, day: int) -> int:
    """Perfect foresight, used only by the reference policy."""
    return max(1, book.rows[site.id][day].notes)
