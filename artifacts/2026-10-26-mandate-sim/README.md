# Subscription mandates across three rails

## Problem

A subscription that bills by card, by SEPA direct debit, and by UPI autopay is three
different products wearing one checkout button. The rails disagree about almost
everything a scheduler has to decide:

| | Card recurring | SEPA direct debit | UPI autopay |
|---|---|---|---|
| Pre-debit notice | none | 14 calendar days | 24 hours |
| Retry spacing | 1 day | 2 days, plus a fresh 14 day notice | 1 day, plus a fresh 24 hour notice |
| Amount ceiling | none | none | INR 15,000 without authentication |
| Refund right | scheme chargeback, 120 days | 8 weeks, unconditional | dispute window |

Source for the UPI rows: RBI Digital Payments E-mandate Framework, 21 April 2026.
SEPA rows follow the core direct debit rulebook. Every value lives in one table in
`mandate/rails.py` and is treated as a parameter, not as legal advice.

## Why it matters

Billing code is usually written once, against the rail the first customer used, and
copied for the others. That copy carries assumptions that are only wrong on two of
the three rails. The failure is not a crash: money lands, then leaves again as a
refund, and the refund arrives with a complaint attached.

The cost is asymmetric and invisible in a dashboard. A debit taken before its notice
window has run is not a failed payment. It is revenue you have to pay back, on demand,
for eight weeks, at a moment of the payer's choosing.

## Design

Three planners, one book, one engine.

- `naive`: debit on the due date, retry daily, no notice, no cap check.
- `notice_aware`: waits out the notice window, asks for authentication above the cap,
  respects the retry gap, ignores revocation.
- `rail_aware`: the same, and stops presenting the moment the payer asks to stop.

The engine (`mandate/sim.py`) is a pure function. A planner maps an invoice to day
numbers; the rail decides what happens to each presentation. There is no clock: days
are integers from day 0, and every random draw comes from one seed.

Each settled debit resolves into one of five buckets, and the five buckets sum to the
billed amount exactly:

- `clean`: settled, and the payer has no claim.
- `exposed`: settled, and the payer still holds a refund right. This is the number
  that most billing dashboards do not show.
- `reversed`: settled, and the payer exercised the right.
- `declined`: at least one presentation, none settled.
- `not_presented`: the planner chose not to present.

A refund right and a refund are not the same thing, so they are measured apart. The
payer acts on a right with a probability fixed per violation kind (0.35 for a missed
notice, 0.80 for a debit taken after they cancelled), drawn once per invoice from the
seed. Without that split, a rule violation would be booked as a certain loss and every
planner that avoids the violation would look better than it is.

### Decisions and tradeoffs

| Decision | Alternative | Why this one |
|---|---|---|
| Exposure separate from reversal | Treat every rule violation as refunded | The first is a measured risk with a stated probability; the second is an assumption dressed as a result |
| One state per invoice, five buckets | Running totals over presentations | Presentations repeat; adding every declined attempt double counts the invoice |
| Cross rail rates as an equal weight mean | Sum minor units, then divide | Cards and SEPA bill in EUR, UPI in INR. Added minor units are an FX rate nobody stated |
| Authentication drawn per presentation, with decay | One flag per mandate | A payer who ignored one prompt may still approve the next; a flat rate would hide the retry ladder |
| Notice as a day gap, not a boolean | `notified: True` | Every rule here is about days, and the off by one case is where disputes come from |
| Integer days, seeded draws | Wall clock and real calendars | The gate runs the suite twice and compares, so nondeterminism fails the build |
| Rail rules in a data table | Rules inline in the scheduler | One place to change a parameter, and the eval recomputes every figure |

## Run

From the repository root:

```
PYTHONPATH=artifacts/2026-10-26-mandate-sim uv run python -m mandate.cli eval
```

That prints every table below and rewrites `results/eval.md` and `results/eval.json`.
Under a second, no network, no keys.

Tests:

```
uv run pytest artifacts/2026-10-26-mandate-sim
```

33 tests, deterministic, no clock and no network.

## Results

Synthetic book: 2000 subscribers, 11,630 invoices, 180 days, seed 7. Cards and SEPA
bill in EUR, UPI in INR. Rates are basis points of that rail's billable amount.

The same scheduler, one line of policy, three rails:

| Planner | Rail | Invoices | Billed | Kept | Exposure | Reversed | Kept bps |
|---|---|---|---|---|---|---|---|
| naive | card | 5924 | EUR 405,742.47 | EUR 403,638.61 | EUR 0.00 | EUR 0.00 | 9948 |
| naive | sepa | 3538 | EUR 229,412.79 | EUR 139,353.46 | EUR 139,353.46 | EUR 72,665.41 | 6074 |
| naive | upi | 2168 | INR 5,854,511.00 | INR 2,744,031.00 | INR 2,744,031.00 | INR 1,611,029.00 | 4687 |

Read that as three different products. The naive ladder keeps 99.48% of the card book,
60.74% of the SEPA book, and 46.87% of the UPI book. On SEPA and UPI, every single
collected invoice also carries a live refund right, so the risk adjusted floor for those
two rails is zero: `clean` is 0 bps on both.

Across the three rails, the naive ladder keeps 69.03% of billable value now, and its
floor is 33.16% once every outstanding right is exercised. The rail aware planner:

| Planner | Mean kept | Mean exposure | Mean reversed | Mean declined | Mean not presented | Mean risk adjusted |
|---|---|---|---|---|---|---|
| naive | 6903 | 3587 | 1973 | 1124 | 0 | 3316 |
| notice_aware | 9711 | 2 | 4 | 235 | 50 | 9709 |
| rail_aware | 9709 | 0 | 0 | 157 | 134 | 9709 |

Three things the numbers say that the design did not assume:

- **The notice window is the expensive disagreement, not the revocation lag.**
  Handling revocation removes 4 bps of reversal and 2 bps of exposure, and gives up
  2 bps of collection and 84 bps of invoices it stops presenting. That is close to a
  wash. Varying the lag from 0 to 7 days moves mean exposure from 0 to 6 bps.
- **The cap is a revenue cliff, not a compliance detail.** 70 invoices, 3.2% of the
  UPI book by count, carry 24.97% of its value. The naive ladder loses every one of
  them: 207 authenticated debits were never requested.
- **Compliance costs days, and the cost is visible.** The rail aware planner collects
  63.99% of the SEPA book on the due date, at a mean of 4.8 days late, because a
  quarter of those invoices were issued on the day they were due and the notice window
  starts then. Nothing is lost; 14 days of float is the price.

Reconciliation runs on every eval: billed splits exactly once into the five states,
presentations split into settled and declined, and rail totals equal the book totals.
All three planners pass.

## Limits

- The book is synthetic. Every subscriber, funding gap, and authentication result comes
  from one seed, and the numbers move if the parameters move.
- The naive planner is a strawman on purpose. The interesting comparison is
  `notice_aware` against `rail_aware`, and it is the one that came out close.
- UPI category exemptions are not modelled: the framework allows up to INR 100,000
  without authentication for insurance premiums, mutual fund subscriptions, and credit
  card bills. That omission overstates the UPI authentication losses here.
- Retry ladders are simplified: three attempts per invoice, one day apart on card, and
  a fresh notice per retry where the rail demands one. No intelligent retry timing.
- Amounts never change mid mandate, there is no proration, no partial capture, no
  network fee, and no currency conversion. `kept` is gross of cost.
- Dispute windows are parameters (120, 56, and 30 days) and are never used to expire a
  right: the model assumes a right that exists gets exercised or does not, within the
  horizon.
- Months are a 30 day grid, so a due day of 31 does not exist and February does not
  shorten the cycle.
- Churn is 8% of subscribers over 180 days, which is low for consumer subscriptions.
  The lag sensitivity shows this is not where the money is, but the level is a guess.

## Next

- Model the UPI category exemptions, so the cap story is measured on the real rule
  instead of the strict one.
- Add a planner that notifies 20 days before the due date for every invoice, including
  the ones issued late, and measure what the 14 day float costs against the revenue it
  protects.
- Replace the fixed three attempt ladder with a retry budget that spends attempts where
  the decline reason suggests a different day will help.
- Run the book for 12 months with monthly churn, so the reversal tail from month 6 is
  inside the window rather than past the horizon.
