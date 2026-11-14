# ledger-close

Closing the books is a testable property, not a monthly meeting.

## Problem

Almost every ledger starts as a table of balances. You post a transaction, you add to a
running total, and at month end you freeze the totals and call the period closed. The
number you reported is then a snapshot of mutable state. If a bank fee turns up late, or an
operator reclassifies a line, or a client retries a payment, the snapshot stops matching the
facts, and nothing in the system says so.

The failure is quiet. Nobody gets an error. The closed month simply reads differently the
next time someone looks at it.

## Why it matters

Money that moved is a fact. What you reported about it is a claim. Most ledger designs store
the claim and hope the facts do not change. That works until the first backdated correction,
which is not an edge case: it is what month end actually is.

In payments this matters twice. Once for the report you sent to a board or a regulator, and
once for the audit question that follows: prove this number. A snapshot cannot be proven. A
hash can.

## Design

Two ledgers run over the same synthetic book:

- `ledgerclose.ledger.Ledger`, the sealed ledger. Append only, hash chained, balances derived
  on every read, corrections only by reversal, writes into a closed period refused by name.
- `ledgerclose.naive.MutableLedger`, the baseline. Stored balances, editable postings, closes
  that are a timestamp and a dict. It exists to be measured, not used.

An entry is a balanced list of signed postings in integer minor units. Each entry stores
`seq`, `prev_hash`, and `hash`, where the hash covers the canonical entry body plus
`prev_hash`. Two callers sending the same postings in a different order produce the same
hash, because lines are normalised before hashing.

A close record stores the period, the journal head sequence at the moment of closing, the
hash of that entry, the control totals per account, and a digest over all of it. Verifying a
close recomputes the totals from the journal at that cut and compares, then recomputes the
digest. Three things can fail independently: the head hash, the totals, the digest.

Refusals are named rules, so a caller can assert on the reason: `Unbalanced`, `ClosedPeriod`,
`NoAmend`, `ReversalOfMissing`, `ReversalNotExact`, `AlreadyReversed`, `ReversalBeforeOriginal`,
`OutOfOrderClose`, `AlreadyClosed`, `DuplicateEntryId`, `EmptyPosting`.

### Decisions and tradeoffs

| Decision | Why | What it costs |
|---|---|---|
| Hash chain over the journal | Any later write changes every downstream hash, so a close can be checked against the facts it covered | Detects, does not prevent. Whoever can write the file can rewrite the chain |
| Balances derived, never stored | A running total is a cache of the facts, and caches drift | Every balance read is O(entries). Fine here, not fine at a billion rows |
| Backdated writes into a closed period refused | The reported number stays true, which is the whole claim | A real correction now has to be dated in the open period, which needs a policy, not just a check |
| Reversal plus repost instead of edit | The audit trail keeps both the wrong fact and the reason it changed | Doubles the entry count for every correction |
| Integer minor units, currency as a field | No float drift, no rounding surprises in a sum | No FX here, so a multi currency book is untested |
| Close records in their own append only file | Keeps the journal and the claims about it separate and simple | That file is not itself chained. State it, do not hide it |

## Run

```bash
cd artifacts/2026-11-14-ledger-close
PYTHONPATH=. uv run python -m ledgerclose.cli bench   # rewrites results/
uv run pytest                                         # from the repo root
```

No network, no keys, no wall clock. The bench runs on a fixed clock so two runs produce the
same bytes, and the tests assert that.

## Results

Book: 281 transactions over six months, 240 payments, 35 refunds, 6 payouts.
Gross processed INR 6,375,195.38. Average payment INR 26,563.31. Fees 1.9 percent with 18
percent tax. Four periods closed: 2026-01 through 2026-04.

Five events are then attempted on both ledgers: a bank fee backdated into March, an operator
reclassifying January fee revenue, a client retry with the same idempotency key, a posting
whose lines do not sum to zero, and an edit of the journal on disk.

| Measure | Sealed | Baseline |
|---|---|---|
| Closed periods whose reported total changed | 0 of 4 | 3 of 4 |
| Absolute drift across closed periods | INR 0.00 | INR 22,700.00 |
| Closes that still reproduce | 4 of 4 | 1 of 4 |
| Periods where debits equal credits | 6 of 6 | 4 of 6 |
| Whole book nets to zero | INR 0.00 | INR 2,000.00 |
| Retry appended an entry | 0 | 1, and INR 548.36 of fee revenue credited twice |
| Out of band edit detected | yes, chain broken at seq 1 | no |

The sealed ledger refused four writes: `ClosedPeriod` twice (the backdated fee, and a
backdated short posting), `NoAmend` once, `Unbalanced` once. The five named rules above are
all pinned in tests, so a rule that stops firing fails the suite.

The tamper event is the interesting one. One January entry is edited on disk, out of band,
adding INR 25,000.00 of revenue to a line. A fresh process reads the journal and reports the
chain broken at seq 1, and the January close no longer reproduces: three of four closes still
verify, and the one that covered the edited entry does not. The baseline accepts the same
edit and reports nothing.

## Limits

- **Detection, not prevention.** The journal is a file. Someone with write access can edit
  every downstream hash and every close digest. What the chain buys you is that an honest
  verifier notices a single edit, and that hiding one requires rewriting everything after it.
  A real system anchors the daily head somewhere it cannot rewrite: WORM storage, a
  timestamping authority, or a second party.
- The close file itself is not chained, only the journal it points at.
- One currency, one calendar month close. No fiscal calendars, no 4-4-5, no FX.
- No accrual journals, no revenue recognition, no sub ledgers, no intercompany.
- The baseline is a deliberate strawman. It is the shape most ledgers start as, not a
  measured competitor. It is not evidence that any named real system behaves this way.
- 284 journal entries is small. Nothing here is timed, and derived balances are untested at
  volume.
- The synthetic book is generated by committed code and labelled as such. No real payments,
  no real merchants, no customer data.

## Next

1. Anchor the head daily: publish `(date, seq, hash)` to an append only store and verify it
   on read, which turns tampering into a mismatch against an external record.
2. A reopen procedure that records who reopened a period, why, and a new signed close, so the
   refusal path in this artifact becomes an auditable exception instead of a dead end.
3. Materiality on adjustments: a correction above a threshold should need a second approval
   before it posts into the open period.
4. Bind the chart of accounts into the close digest, so a mapping change cannot silently
   restate a closed month.
