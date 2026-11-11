# The three clocks in a chargeback

Every dispute runs on a clock, and the clock is not one number. The issuer has a
filing window counted from the transaction. The merchant has a response window counted
from the chargeback receipt, shorter for fraud codes than for service codes. The
pre-arbitration window only starts after the merchant has already won, counted from the
day the issuer pushes back.

This is a simulator and a state machine for those clocks. It builds a synthetic book of
2,000 disputes with known defences, runs five policies over it under one analyst
budget, and scores what each one recovers.

The headline: a status tracker recovers **21.3%** of the money it could have won. The
same book, the same 40 analyst minutes a day, with all three clocks, two zero evidence
checks and a value per minute queue, recovers **94.0%**. That is **$201,675** on
$356,862 of disputes, with no extra headcount.

## Problem

A merchant dispute team usually has a status field and a habit. The status field says
`open`, `submitted`, `won`, `lost`. The habit is a weekly or three weekly sweep. Both
are reasonable, and both are wrong in the same way: they treat the dispute as a record
rather than as a set of deadlines.

Three things are true at once for every case:

1. **The issuer's clock.** A chargeback filed outside the network's filing window is
   procedurally invalid. The merchant wins it without producing a single document.
   Nothing in a status tracker knows this.
2. **The merchant's clock.** The response window is counted from when the chargeback
   reached the merchant, not from the transaction. It is shorter for fraud codes than
   for service codes, and a deadline that lands on a non processing day rolls forward.
3. **The pre-arbitration clock.** After a merchant win the issuer can push back. That
   clock starts late, has its own window, and forfeits money the merchant had already
   recovered on the books.

A policy that models one clock is silently wrong about the other two. Silence is the
problem: a failed case looks exactly like a case that was lost on the merits.

## Why it matters

Disputes are a P&L line and a compliance surface at the same time. The money is the
clear part. The other part is that networks put merchants into a monitoring program when
the ratio of chargebacks to transactions crosses a threshold, and that program adds
fees and a remediation clock that nobody budgets for. A team that wins 65% of the
disputes it could have won is not just leaving money on the table, it is sitting on a
ratio it cannot explain.

The structural finding in this book is the one to remember: **55.2% of the recoverable
value needs no evidence at all** ($153,411 of $277,708). It is either procedurally
invalid or liability shifted to the issuer by an authenticated 3DS transaction or a
chip read. The status tracker in this model captured **6.4%** of it. You cannot win what
you do not check.

## Design

`disputeclock` has six parts.

1. `model.py` holds the case, the reason codes, the state enum, and the legal transition
   map. `liability_shifted` lives here because it is a fact about the terminal, not a
   policy opinion.
2. `netcalendar.py` does the business day arithmetic: weekend and holiday roll forward,
   processing day counts, and the window add that produces a deadline.
3. `rules.py` holds the two network variants, the evidence requirement per reason code,
   the analyst minutes each evidence item costs, and the three deadline functions.
4. `engine.py` runs one policy over one book, one day at a time, with a per day budget.
   It refuses any transition that is not in `ALLOWED`, expires anything that reaches its
   deadline unresolved, and schedules the pushback after a win.
5. `sim.py` builds the book from one seed and records, for every case, whether a defence
   existed. That flag is the ceiling every policy is scored against.
6. `bench.py` runs the ladder and checks six invariants.

The evidence requirement is a tuple, not a score. Asking for a delivery signature is not
a weaker defence than asking for a delivery signature plus a signed terms acceptance: it
is a different requirement. A case with four of five items is undefensible, which is why
the precision numbers move the way they do.

The five policies are additive, so each step prices one decision:

- `status_only`: no clock at all. Sweeps every case 25 days after it arrives and submits
  whatever has landed by then. This is a straw man by construction, and its job is to
  price the clock, not to represent a competent team.
- `response_clock`: the real response deadline per network and reason code, with the
  business day roll, worked oldest deadline first.
- `frees_added`: the same, plus the procedural and liability cases, which cost zero
  analyst minutes.
- `complete_evidence`: the same, but never submits a set that cannot win.
- `three_clock`: the same, plus a value per minute queue, a three day urgency band, and
  pushback answers.

### Decisions and tradeoffs

| Decision | Choice | Why | What it costs |
|---|---|---|---|
| Where the clock starts | Chargeback receipt date | The network counts from receipt, not from the transaction | Needs the chargeback feed, not just the order system |
| Fraud window | 20 days, shorter than the service window | Issuers move fraud claims faster | One number per network against a real rulebook of many |
| Deadline on a non processing day | Roll forward to the next one | That is what the network accepts | A rolled deadline consumes a day of capacity |
| Evidence requirement | An exact set | A partial set is not a weaker defence, it is no defence | A case with 4 of 5 items is scored as undefensible |
| Pushback win probability | A 0.55 prior in the policy | Pushbacks hold slightly more often than they fail | A constant, not a learned rate |
| Queue order | Value per minute, urgent first | The analyst budget is the binding constraint | Ignores severity and merchant goodwill |
| Baseline | A fixed 25 day sweep | It isolates the clock from the team | Deliberately weak, so the first delta is overstated |

Three invariants are asserted, not assumed.

- **Every edge is legal.** `move()` raises on any transition outside `ALLOWED`, and the
  suite asserts that an illegal move is refused.
- **Every case resolves.** Each policy returns exactly one row per case in the book, and
  every final state is terminal.
- **Money is conserved.** For every policy, recovered plus lost equals the book total,
  computed as an equality between a sum over the case book and a sum over the outcome
  buckets. The same check runs in the bench and fails the run.

The deadline itself is property tested: over 120 start dates and three windows, the
deadline is the first processing day at or after the calendar deadline, and no earlier
day qualifies.

## Run

```
PYTHONPATH=artifacts/2026-11-11-dispute-clock uv run python -m disputeclock.cli run
uv run pytest artifacts/2026-11-11-dispute-clock
```

Stdlib only, no network, no clock, one seed. The suite is 32 tests and runs in under a
second. The command rewrites `results/summary.json` and `results/summary.md` and exits
non zero if a bench check fails.

## Results

Seed 11, 2,000 disputes, $356,862.36 disputed, 96 days of arrivals, 360 day horizon,
40 analyst minutes a day. Budget and book are fixed across every row except the last.

| Policy | Recovered | Share of defensible | Forfeited cases | Contests | Precision | Minutes | Wasted |
|---|---|---|---|---|---|---|---|
| `status_only` | $59,229.73 | 21.3% | 804 | 1,044 | 0.53 | 6,713 | 2,385 |
| `response_clock` | $184,670.09 | 66.5% | 473 | 1,457 | 0.61 | 7,191 | 3,706 |
| `frees_added` | $204,871.27 | 73.8% | 384 | 932 | 0.45 | 6,382 | 3,233 |
| `complete_evidence` | $214,603.78 | 77.3% | 392 | 506 | 0.94 | 6,237 | 2,660 |
| `three_clock` | $260,904.99 | 94.0% | 151 | 747 | 0.96 | 6,987 | 934 |
| `three_clock`, unlimited time | $272,586.98 | 98.2% | 0 | 898 | 0.96 | 9,215 | 1,002 |

The ceiling is $277,707.98, which is the 77.8% of the disputed value that had a defence
at all. The other 22.2% was lost before anyone touched it: no signature, no terms record,
no authenticated 3DS, and no way to produce one in time.

What each step is worth:

- **The clock: +$125,440.** This is the biggest single step and the least interesting one,
  because the baseline is designed to be blind. It says a fixed sweep misses a fifth of
  the book. Note what the sweep breaks on: 563 of its 804 forfeits are fraud claims,
  because a 25 day habit is longer than a 20 day fraud window. It never wins a single
  fraud dispute.
- **The zero evidence checks: +$20,201.** 621 cases, $153,411 of defensible value. The
  rung below it, with the right clock and no rule table, already captures 89.2% of that
  value by accident, because its deadline queue happens to reach those cases in time. The
  rule table closes the last 10.8% and frees the minutes the free wins would have cost,
  which is why the delta is larger than the missing value alone.
- **The evidence gate: +$9,733.** Contest precision jumps from 0.45 to 0.94 and wasted
  analyst minutes fall from 3,233 to 2,660, because half of the contests in the previous
  rung were unwinnable by construction. The money barely moves; the team stops doing
  work that cannot pay.
- **The queue and the pushback: +$46,301.** With the clocks right and the evidence
  honest, the only remaining decision is which case to work next, and the budget is what
  makes that decision expensive. 151 forfeits remain, all of them cases the policy chose
  not to defend with the minutes it had. Pushback answers are part of this: 56 pushbacks
  opened, 46 answered, $6,125.65 recovered that every lower rung simply forfeited.
- **What one analyst costs: $11,682.** Run the same policy with unlimited analyst time and
  recovery goes from 94.0% to 98.2% with zero forfeits. That is the price of the staffing
  constraint, smaller than the clock or the queue decisions and comparable to the evidence
  gate, which is the useful part: the constraint is not headcount, it is what the queue is
  sorting on.

All six bench checks pass: every case resolved, one row per case, every case terminal,
money conserved, budget binds, deadline binds. The budget check is a comparison against
an unbounded run rather than an assertion about utilisation, because a budget that is
never exhausted on a busy day would make the whole comparison decorative.

## Limits

- The windows are illustrative. They are shaped like public Visa and Mastercard dispute
  rules, one window per network with a shorter fraud variant, and they are not a
  reproduction of any current rulebook. A real one varies by reason code, has filing
  fees, and has more than two networks.
- The simulator and the policies share one taxonomy. A case is winnable if its required
  evidence set landed before the deadline, so a precision of 0.96 measures that the rule
  table is separable from the feed, not that an issuer will agree. Real disputes are lost
  on evidence quality, not evidence presence.
- A complete set wins with probability one. Real representment wins roughly half the time
  on a complete set, because the issuer judges the document and not its existence. The
  model prices the clock and the queue, not adjudication.
- The 0.55 pushback prior is a constant, and the simulator draws pushback outcomes from
  the same rate. That makes the prior right in aggregate and wrong case by case, which is
  the real condition, but it means the model cannot claim a better pushback strategy than
  answer when the value per minute justifies it.
- The merchant always has the terminal facts: the 3DS result and the EMV flag. Real
  stacks lose those across processor migrations, and a case that looks liability shifted
  in this model can look undefended in production.
- Fees are absent. No network filing fee, no scheme arbitration fee, no cost of goods.
  A representment that wins on a $20 ticket can still cost more than it recovers, and the
  model has no opinion about that.
- The budget is 40 minutes a day against about 21 new disputes a day, roughly one part
  time analyst. Change it and the last delta grows or disappears. The bench check exists
  precisely because a non binding budget makes the queue comparison meaningless.
- Counts are per case, not per rupee of exposure, and the triage is by value per minute
  only. Severity, regulatory categories and merchant goodwill are not modelled.
- Synthetic data throughout. No cardholder, no real transaction, no merchant, no issuer,
  and nothing here is connected to any live mandate or broker session.

## Next

- Move to reason code level windows per network, with the filing fee attached, so the
  model can answer "is this ticket worth contesting at all".
- Learn the pushback rate per reason code from outcomes instead of holding a constant,
  and report the calibration, not just the recovery.
- Price evidence quality as a score so a four of five set is worth something instead of
  nothing, which is closer to how an issuer actually reads a representment.
- Add the chargeback ratio itself as a tracked state, so the policy can trade a small
  recovery against the monitoring threshold.
- Replay a recorded acquirer feed and report the false positive rate on data the rule
  table was not written for.
