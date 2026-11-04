# Sanctions screening that survives a review budget

A screening queue is not a search result. Somebody has to read every alert, and the number of
alerts they can read today is fixed. This artifact measures four screening designs at the same
fixed review budget instead of at a similarity threshold, because the budget is the constraint
that ruins real screening programs.

Headline: at 48 reviews, entity resolution catches 33 of the 36 listed customers in the book.
A name-only screen catches 11, and spends 36 of its 48 reviews on people who are not the listed
person.

## Problem

Screening a customer book against a designations list looks like a search problem. It is not.
A search returns a ranked list; a screen has to decide which customers a human will look at
before the day ends, and every customer in that queue is a person whose account is frozen until
somebody clears them.

Two failure modes cost money in opposite directions:

- A false positive freezes a legitimate customer. The queue is the product, and a queue full of
  the wrong names is the same defect as a missed match.
- A false negative is a regulatory finding. The customer who really is the listed person was
  screened, alerted, and pushed below the line by namesakes who share the name.

The work in this artifact is the ordering, not the threshold.

## Why it matters

Every screening vendor says "entity resolution" and almost none publishes recall at a fixed
review budget, because the numbers look bad. The interesting quantity is not "what is your false
positive rate at a 0.9 threshold" but "given the analysts you employ, how many listed customers
do you find, and how many legitimate customers do you freeze doing it".

The measured answer here is blunt: a name similarity score puts 130 customers at the same top
score of 1.0, so a 48 slot queue is decided by an arbitrary tie break. The screen alerted on 28
of the 36 listed customers and delivered 11 of them to an analyst. The other 17 were inside its
own output and lost to a name that looks the same.

## Design

The bench builds a synthetic book and list, screens every customer against every entry under
four policies, and reports what a human would find after reviewing the top K.

### The data

Synthetic, seeded, and labelled. No real person appears.

- 26 list entries, each with a primary name, zero to two transliteration aliases, a date of birth
  that is sometimes only a year, one or more countries, and an identity number on 70 percent.
- 2400 customers, of whom 36 really are a listed person, in six classes: name and date exact, a
  published alias, a list that publishes only the birth year, a relocated match whose country
  contradicts the list, a thin file with no date of birth, and three customers who exist on the
  book only under a kunya ("Abu Rashid"), where the listed name never appears at all.
- 110 namesakes: the same name as a listed person, a different date of birth, a different
  country, a different identity number. This is the class that eats the budget.
- 60 near misses: a shared given name and a family name one letter away.

Customers are shuffled before they are numbered. Without that, the true matches sit at the front
of the book and a tie break by customer id becomes an accidental oracle: the first run of this
bench caught 28 of 36 for that reason alone and the number collapsed to 11 once the labels were
spread across the id space.

`screenlab.data.digest` hashes the whole dataset and the hash is committed in
`results/summary.json`, so a number can be traced to the exact book that produced it.

### The four policies

| Policy | What it does |
|---|---|
| `exact_name` | Alert only when the folded name is identical to a listed name or alias. Score is 1.0 for every alert. |
| `name_only` | Alert when full-string Jaro-Winkler on the folded name is at least 0.85. This is the search box. |
| `name_country` | `name_only` plus a hard country gate: drop any alert whose country is not on the list. One variable different from `name_only`. |
| `entity_resolution` | Blended name score across three views, plus date of birth, country and identity number as evidence, with a named rule per alert. |

The entity resolution name score is `0.20 * full string + 0.60 * order free + 0.20 * phonetic`,
each a Jaro-Winkler similarity. Dates of birth are compared as `exact`, `year`, `absent` or
`conflict`, and an absent date is scored as a weak negative rather than as a contradiction,
because a missing field is not evidence against a match.

Each alert carries the rule that fired, so a reviewer sees why: `id_exact`, `name_exact_dob`,
`name_close_dob`, `name_variant_dob`, `name_no_dob`, `name_over_dob_conflict`.

### Decisions and tradeoffs

| Decision | Alternative | Why this way | What it costs |
|---|---|---|---|
| Score at a fixed review budget | Score at a fixed similarity threshold | Analyst capacity is the real constraint, and threshold metrics hide the ordering problem | Every number is budget specific; the sweep is reported instead of a single point |
| Blend three name views | Take the maximum of the views | A maximum acts as an OR: it inflates any pair whose consonants line up, so unrelated names enter the queue | A single very strong view cannot carry a pair on its own |
| Order free key carries 0.60 | Raw string carries the weight | A given and family name swap scored 0.77 on raw string and looked like a typo | Genuine middle name drift is diluted |
| Country is evidence, not a delete rule | Drop alerts on country mismatch | Relocated customers are the expensive miss: all 6 relocated matches are real people whose country contradicts the list | Longer queue: 196 instead of 144 |
| Date of birth conflict suppresses below 0.95 | Queue every conflict | You have positive contradictory evidence, so the slot is better spent elsewhere | Removed 85 pairs and changed nothing at a 48 budget; an exact name with a mistyped date below 0.95 is cleared without a human |
| Missing date of birth scores as a weak negative | Treat missing as conflict | Absent data is not evidence against a match | Thin files rank lower than identical ones with a date |

## Run

```
cd /Users/parthbatra/fintech-lab
PYTHONPATH=artifacts/2026-11-04-sanctions-screening uv run python -m screenlab.cli screen
uv run pytest artifacts/2026-11-04-sanctions-screening
```

The first command rewrites `results/`. The second is deterministic: no network, no wall clock,
no sleeps. 31 tests, about 19 seconds, most of it building the book once.

## Results

Produced by the command above, committed in `results/summary.json` and `results/summary.md`.

```
book 2400 customers, list 26 entries, 36 true matches, 110 namesakes
review budget 48 cases (2.00% of the book)

policy             reviewed  caught  namesakes  precision  recall     f1   days
exact_name               48      11         36      0.229   0.306  0.262    2.7
name_only                48      11         36      0.229   0.306  0.262   11.5
name_country             48      21         11      0.438   0.583  0.500    3.0
entity_resolution        48      33         11      0.688   0.917  0.786    4.1

queue and ordering at the same budget
policy              queued   days    top   at top  alerted true  ranking loss
exact_name             130    2.7   1.00      130            28            17
name_only              553   11.5   1.00      130            28            17
name_country           144    3.0   1.00       32            21             0
entity_resolution      196    4.1   1.00       30            33             0

recall by class of true match, entity resolution versus name only
class            n    er   name only
exact            7     7           1
alias           14    14           8
year_only        3     3           0
relocated        6     6           0
thin_kyc         3     3           2
kunya            3     0           0
```

`days` is the queue divided by the budget: how long the backlog takes to clear at 48 reviews a
day. `ranking loss` counts listed customers the policy alerted on and then failed to fit inside
the budget.

What the numbers say:

- **The namesake problem is a ranking problem, not a threshold problem.** `name_only` alerted on
  28 of the 36 listed customers and delivered 11. Its own output contained the other 17 and the
  ordering buried them, because 130 customers share the top score of 1.0 and the tie break is a
  customer id. A painstaking analyst could not fix this: the alert says "Muhammad Al-Rashid,
  1.000" 130 times.
- **A wider name threshold buys queue, not catches.** `exact_name` and `name_only` both catch 11,
  and the fuzzy screen puts 423 more customers in front of a human to get there: 553 instead of
  130, which is 11.5 analyst days instead of 2.7.
- **The country gate is the expensive shortcut.** Deleting alerts on a country mismatch lifts
  this book to 21 of 36, and then loses all 6 relocated matches and all 3 thin files. It looks
  better than the name-only screen and it silently drops the class of customer who most needs
  catching. Recall is where the bill arrives.
- **The budget curve is the argument.** At 24 reviews entity resolution catches 24 with no
  namesakes reviewed, while the baselines catch 6. The name-only screen needs 192 reviews, 8
  percent of the book, to reach 28 of 36. Entity resolution reaches 33 with 48 and never gets
  past 33, because three customers only exist under a kunya.
- **The ceiling is 0.688.** Three customers are unreachable by name, so 33 of 48 is the highest
  precision available at this budget and entity resolution hits it exactly.
- **Ties decide the baselines, evidence decides the rest.** Reversing the tie break moves
  `exact_name` and `name_only` from 11 to 12 catches. `name_country` stays at 21 and
  `entity_resolution` stays at 33, because their ordering is driven by dates and identity
  numbers rather than by a name string.
- Of the 33 entity resolution catches: 10 come from an identity number, 16 from an exact name
  with a matching date, 4 from a close name with a matching date, and 3 from a name with no date
  on file.

## Limits

- **The book is synthetic and I wrote the generator.** Truth classes are shaped by my own rules.
  This measures whether the logic does what it says on a designed population, not what a real
  book will do. Precision and recall here are not estimates of production performance.
- **Settings were chosen by hand and changed during the build.** The view weights moved after a
  pure name swap scored 0.77, the conflict suppression cut was added after the first table, and
  the customer shuffle was added after the first run showed a tie break that knew the answer.
  This is a bench, not a prospective validation. The threshold is a single operating point at
  0.88 and no threshold sweep is committed; a deployment calibrates on a labelled sample from
  its own book.
- **`name_only` is one reasonable baseline, not the best one.** A vendor with a better
  transliteration engine would close part of the gap on the alias class. The comparison is
  against a plain Jaro-Winkler screen, which is what a search box does.
- **The kunya class is unreachable by design and by fact.** Three of 36 are missed by every
  policy. No similarity threshold fixes a name that is not in the data; that is an adverse media
  or investigator problem, not a matcher problem.
- **No entity records, no ID fuzzy matching, no date-shift detection.** Companies, passports with
  one transposed digit, and dates written day-month reversed are all out of scope. Those are the
  next three ways this would fail on a real book.
- **Speed is not claimed.** The bench runs in about 12 seconds for 2400 by 26 in pure Python.
  It is a correctness artifact, not a latency result.

## Next

1. Add corporate entries with legal form folding (`FZE`, `LLC`, `SA`) and the same budget metric,
   because half a real list is companies.
2. Score at the customer level rather than the pair level: one case per customer with the best
   evidence attached, so the queue length stops depending on how many entries a name resembles.
3. Publish the alias rules as a fixture set with expected verdicts, so the phonetic view can be
   changed without moving the numbers silently.
