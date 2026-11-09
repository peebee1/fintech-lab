# Order, fill, and position reconciliation

A retail trading app shows a position. Behind it are three records that disagree: the
broker's order book, the exchange's trade tape, and the app's own fill archive. This
harness builds a synthetic session with known breaks, runs four reconciliation policies
over it, and scores what each one finds and what each one leaves in the book.

The headline: a book reconciled to the broker snapshot alone is 844 shares and
₹27.2 lakh away from the tape on a 1,200 order session, and it reports zero breaks while
being wrong. Naming every break from the tape closes the gap to zero and covers 87% of
the rupee exposure in 60 review tickets.

## Problem

Order state lives in three places and each is authoritative for a different fact.

- The **broker** knows the order exists, its status, and its cumulative filled quantity.
  That quantity lags. A snapshot taken while the last fill is in flight under-reports.
- The **exchange tape** knows every print, in sequence, with a trade id. It is the only
  record that can settle how many shares actually traded and at what price.
- The **app** keeps what its websocket handler booked. It can drop a frame, book one
  twice, record a price it inferred from the limit, or move a position for a corporate
  action that never printed.

A reconciliation job that compares only two of these can see a disagreement but cannot
tell which side is wrong, so it reports "break" and leaves the position as it was. The
book then looks reconciled because nobody fixed it.

## Why it matters

Retail brokers reconcile overnight, and the customer sees the result in the morning. The
failure is quiet: a position that is off by a few shares, a cash balance that is short by
the fee on a duplicate fill, an order the app marked cancelled that the exchange filled.
None of these throw. They surface weeks later when a client sells shares the book does
not have, or when a settlement fails.

For an AI agent that trades, the seam gets worse, not better: the agent trusts a position
number to size the next order. A stale reconciliation is a wrong input to a live decision.

## Design

`orderrecon` has four parts.

1. `sim.py` builds one deterministic session from a seed: 1,200 orders over 12 NSE names,
   1,668 prints, a broker snapshot with a lag, an app archive, and an app position book.
   It injects eight break classes and records the ground truth for each.
2. `recon.py` holds four policies. Each returns a position book, a cash book, and a list
   of named breaks carrying the share and cash correction that would fix the book.
3. `metrics.py` scores breaks by exact `(class, key)` match, and scores triage under a
   fixed review budget.
4. `bench.py` runs all four over one session and writes `results/summary.json` and
   `results/summary.md`.

The eight break classes:

| Class | What is wrong | Where it shows |
|---|---|---|
| `duplicate_fill` | A replayed frame booked the same trade id twice | App archive |
| `missing_fill` | A print never reached the app | Tape against archive |
| `price_drift` | The app recorded a price that never traded | Tape against archive |
| `qty_mismatch` | Same trade id, different quantity | Tape against archive |
| `broker_qty_lag` | Broker cumulative quantity is behind the tape | Broker against tape |
| `fill_after_cancel` | Order marked cancelled, a print landed after the cancel | Status against tape |
| `orphan_fill` | A fill for an order the app was never told about | App archive |
| `phantom_position` | Position moved with no fill behind it | Position against archive |

The four policies:

- `broker_only` books the broker's cumulative filled quantity. No detection.
- `broker_vs_app` compares the app archive to the broker. It can see a disagreement, so it
  guesses: app high means duplicate, app low means missing. No tape access.
- `stream_replay` books the app archive in arrival order and alerts on repeated trade ids
  without removing them.
- `tape_three_way` treats the tape as quantity truth, the broker as order state truth, and
  the archive as the claim. It names a class for every disagreement and carries the
  correction.

### Decisions and tradeoffs

| Decision | Choice | Why | What it costs |
|---|---|---|---|
| Quantity truth | Exchange tape | A trade id is the only identifier that survives a replay | Requires tape access, which some retail stacks do not have intraday |
| Order state truth | Broker | The broker saw the cancel ack and the reject | A stale snapshot still passes as truth when the tape is silent |
| Identity key | `trade_id` | A duplicate frame repeats it exactly; order id plus qty plus price does not | Fills with no exchange id need a separate path, not modelled here |
| Correct then classify | Class first, correction carries the delta | A correction without a named class is an unposted journal entry | A misclassified break still posts the right share delta, so books can look clean with the wrong label |
| Phantom positions | Corrected by the observed gap, excluded from the equality test | There is no fill to derive the correction from | The class is asserted, not independently proven |
| Triage ordering | Rupee impact | The review budget is the binding constraint, not detection | Ignores regulatory severity, which is not a rupee number |

The explained delta test is the point of the design. For every symbol without a phantom
break, the share difference between the app book and the tape must equal the sum of the
corrections derived from the fill archive:

```
app_position - tape_position == sum(correction by class: missing + duplicate + qty)
```

The two sides are computed from different records, so a sign flip or a missing class
leaves a gap. On dirty data the gap is zero. With the correction sign flipped it is 302
shares, which is how we know the test can fail.

## Run

```
PYTHONPATH=artifacts/2026-11-09-exchange-recon uv run python -m orderrecon.cli reconcile
uv run pytest artifacts/2026-11-09-exchange-recon
```

Stdlib only, no network, no clock, seeded. The suite is 24 tests and runs in under a
second.

## Results

From `results/summary.json`, seed 11, 1,200 orders, 40 injected cases per order level
class, 6 phantom symbols, review budget 60.

| Policy | Breaks | Precision | Recall | Position gap (shares) | Position gap (INR) | Cash gap (INR) |
|---|---|---|---|---|---|---|
| `broker_only` | 0 | 0.00 | 0.00 | 844 | 2,720,292 | n/a |
| `broker_vs_app` | 206 | 0.43 | 0.31 | 1,424 | 3,303,826 | n/a |
| `stream_replay` | 40 | 1.00 | 0.14 | 1,779 | 3,434,396 | -554,078 |
| `tape_three_way` | 286 | 1.00 | 1.00 | 0 | 0 | 0 |

What the table says:

- Trusting the broker book leaves **844 shares** unexplained, worth **₹27.2 lakh**, and
  the policy emits no break at all, because it has nothing to compare against.
- Reconciling the app to the broker flags 206 items but only **43%** of them are the right
  class, and the book is still **1,424 shares** off. It found the alarm and not the fault.
- Booking the archive in arrival order is worse than trusting the broker: **1,779 shares**
  and **₹5.54 lakh** of cash, because duplicates stay in the book. It catches 40
  duplicates and nothing else: recall 0.14.
- The three way job names all 286 breaks, and the reconstructed book equals the tape
  exactly, shares and cash.

Per class, `tape_three_way`:

| Class | Correct | Injected |
|---|---|---|
| `duplicate_fill` | 40 | 40 |
| `missing_fill` | 40 | 40 |
| `price_drift` | 40 | 40 |
| `qty_mismatch` | 40 | 40 |
| `broker_qty_lag` | 40 | 40 |
| `fill_after_cancel` | 40 | 40 |
| `orphan_fill` | 40 | 40 |
| `phantom_position` | 6 | 6 |

The book, not the classifier, is the invariant: 1,231 shares of correction are explained
across 6 clean symbols with a maximum gap of 0, and the cash book closes with a gap of 0
paise.

Triage is where the numbers get uncomfortable. 286 breaks is not a queue anyone works.
With 60 review tickets:

- ranked by rupee impact: **87%** of ₹1.47 crore of exposure is reviewed
- in arrival order: **26%**
- random order: **20%**
- the top ten breaks alone carry **41%**

So the ordering matters more than the detection rate once detection is complete.

## Limits

- The detector is written against the same eight class taxonomy the simulator injects.
  Precision and recall of 1.00 measure that the taxonomy is separable from the three
  records, not that a real feed behaves this way. A live stream has breaks this model
  does not have: exchange busts, cancelled trades, off book transfers, mid stream rejects.
- The broker is a snapshot with a quantity lag. It does not model message ordering,
  out of order acks, or a broker that over-reports.
- Fees are synthetic: 1 bps capped at ₹20. The cash book ignores STT, stamp duty, GST,
  and T+1 settlement, so it is a trade dated book, not a settled one.
- Phantom positions are capped at 6 of 12 symbols so the equality test keeps clean
  symbols. The class is under weighted relative to how often a botched corporate action
  shows up in a real book.
- Shorts are allowed with no borrow cost and no margin check.
- The corrected book balances because it is rebuilt from the tape. That is by
  construction. The measured claims are the drift in the other three policies, the
  detection quality against ground truth, and the explained delta equality.
- Synthetic data throughout. No real order, no real client, no live broker session, and
  nothing here is connected to the Angel One mandate.

## Next

- Add settlement date: T+1 cash, then reconcile the settled book separately from the
  traded book.
- Model corporate actions as first class events, so a split credit is expected rather
  than phantom.
- Replay a real broker session from a recorded tape and report the false positive rate on
  data the taxonomy was not written for.
- Turn the triage list into a queue with SLA clocks per class, because age is the second
  dimension that matters after rupee impact.
