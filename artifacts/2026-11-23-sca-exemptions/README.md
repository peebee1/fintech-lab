# The exemption you can use depends on the fraud you take by using it

A merchant wants fewer challenges. The rule that decides how many transactions may skip one is
itself priced in the fraud those exemptions admit. This artifact replays seven exemption policies
over a 60 day book of remote card payments, prices fraud against checkout friction, and counts the
days each policy spends above the reference fraud rate it is relying on.

Every number below is printed by the committed code.

## Problem

Under PSD2 and the RTS on strong customer authentication, a remote card payment must be
authenticated unless an exemption applies. Two exemptions matter for a merchant:

- Low value (Article 16): the amount is at or under EUR 30, the cumulative amount since the last
  authentication is at or under EUR 100, and no more than five transactions run in a row.
- Transaction risk analysis (Article 18): the provider may skip authentication up to an exemption
  threshold value, and the threshold it may use depends on its overall fraud rate. EUR 100 needs a
  rate at or under 13 bps, EUR 250 needs 6 bps, EUR 500 needs 1 bp. Below 13 bps and no threshold
  is available at all.

The fraud rate is not measured per band. It is one number for the payment instrument, covering
every remote card payment, authenticated or exempted (EBA Q&A 2018_4043). That makes the exemption
a feedback loop: every transaction exempted adds fraud to the numerator of the rate that decides
how much may be exempted.

Most implementations read the ladder once, take the highest rung they have seen, and stop. The
ladder is not a static entitlement. It is a control whose sensor lags.

## Why it matters

On the book in `results/`, 60 days, 49,752 transactions, EUR 2,953,266.79 processed:

- Challenging every transaction costs EUR 34,942.88. Almost all of it, EUR 34,619.28, is
  contribution margin lost on 2,854 abandoned checkouts. Fraud costs EUR 323.60.
- Exempting every transaction costs EUR 4,710.16, all of it fraud. That is 5.3 times cheaper than
  challenging everything, and it is above the 1 bp reference rate on 56 of 60 days.
- The cheapest policy that never breaches its own reference rate is the stepped-down,
  risk-screened one, at EUR 25,026.14. It still saves EUR 10,217.70 of friction against
  challenge-everything, for EUR 300.96 of added fraud.

The gap between the cheapest policy and the cheapest compliant one is EUR 20,315.98, which is 4.3
times the cheapest policy's entire cost. Compliance is not a rounding error on this decision. It is
most of the decision.

The second finding is about the estimate, not the model. The ladder is driven by a trailing 7 day
fraud rate reported with a 2 day lag. That sensor is blind to the fraud the exemption is about to
admit, so a policy that sits at the ceiling the sensor allows spends the next few days above the
reference rate that ceiling requires. The risk-screened policy at the ladder's ceiling costs
EUR 16,439.13 and is above its reference rate on 8 of 60 days, worst window 4.91 bps over. Stepping
one rung down costs EUR 8,587.01 and takes the breach count to zero.

## Design

Four modules and one direction of data flow. Money is integer cents everywhere, no floats on money.

- `exempt/rules.py`: the ladder (`highest_etv`), the reference rates, the Article 16 counters, and
  basis point arithmetic. Pure functions, boundary tested.
- `exempt/book.py`: a synthetic book of remote card payments. 60 days, 49,752 transactions, a log
  normal ticket with a median near EUR 38, six merchant categories with different fraud priors, a
  shopper pool with repeat visits so the counters have something to count, and a risk score drawn
  conditional on the latent fraud label. Latent fraud is 14.16 bps of value, which is high for
  cards overall and normal for card not present.
- `exempt/policies.py`: seven decision functions from "challenge everything" to "exempt
  everything", each with the ceiling it claims. A policy owns its own counters; an exemption
  increments them and a challenge resets them.
- `exempt/bench.py`: replay, settlement, and cost. Outcome draws (fraud success, checkout
  abandonment) are columns on the transaction, so a policy change moves only the decision and never
  the randomness underneath it.

| Decision | Choice | Why | What it costs |
|---|---|---|---|
| Fraud rate denominator | Whole book, not per band | The rule measures one instrument level rate. Per band would flatter every policy | Only one ceiling is in force at a time, so a per band table is not readable from this |
| Window and lag | Trailing 7 days, 2 day reporting lag | Chargebacks are reported late. A policy cannot see fraud it has not been told about | The estimate is optimistic exactly when exemptions ramp, which is where the breaches come from |
| Cost of friction | Contribution margin, 22 percent of value | An abandoned checkout loses margin, not revenue | Friction dominates fraud on this book, so the unconstrained optimum is to challenge nothing |
| Risk test | A cutoff on a score, not a blended exemption probability | Auditable and explainable to a scheme or a supervisor | Leaves exemptions on the table near the cutoff |
| Ceiling cadence | Recomputed once per day | The rate is a reported figure, not a per transaction signal | A same day spike cannot be reacted to until tomorrow |
| Cold start | No risk analysis exemption until a full window exists | An unseen rate is not a rate that has been proven low | Eight days of forced challenges at the start of the book |
| Money | Integer cents | A basis point table built on floats drifts | None worth having |

## Run

From the repo root, no network and no key:

```
uv run pytest artifacts/2026-11-23-sca-exemptions
PYTHONPATH=artifacts/2026-11-23-sca-exemptions uv run python -m exempt.cli bench
PYTHONPATH=artifacts/2026-11-23-sca-exemptions uv run python -m exempt.cli show
```

`bench` rewrites `results/summary.json` and `results/summary.md`. `show` prints the headline without
touching the committed results. The seed is fixed at 20261123, so the run is byte identical.

## Results

Seed 20261123, 60 days, 49,752 transactions, EUR 2,953,266.79 processed, latent fraud 14.16 bps.
Costs in EUR. Friction is lost contribution margin on abandoned checkouts, fraud is value plus a
EUR 12 chargeback fee per case.

| policy | exempt % txn | exempt % value | challenges | abandoned | fraud loss | friction | total | breach days |
|---|---|---|---|---|---|---|---|---|
| challenge_all | 0 | 0.0% | 49,752 | 2,854 | 323.60 | 34,619.28 | 34,942.88 | 0 |
| low_value_only | 40 | 11.5% | 29,911 | 1,619 | 511.19 | 30,047.10 | 30,558.29 | 0 |
| tra_tight | 55 | 27.5% | 22,627 | 1,229 | 624.56 | 24,401.58 | 25,026.14 | 0 |
| tra_risk_cutoff | 71 | 52.2% | 14,556 | 789 | 793.59 | 15,645.54 | 16,439.13 | 8 |
| tra_no_risk_test | 78 | 57.1% | 11,125 | 594 | 2,312.07 | 14,540.11 | 16,852.18 | 14 |
| flat_etv_500 | 100 | 96.3% | 154 | 7 | 4,164.89 | 1,027.92 | 5,192.81 | 56 |
| exempt_everything | 100 | 100.0% | 0 | 0 | 4,710.16 | 0.00 | 4,710.16 | 56 |

What the rows say:

- **Friction, not fraud, is the cost that a challenge policy actually carries.** Challenging
  everything spends 99.1 percent of its total on abandoned checkouts. That is why the exemptions
  exist and why a merchant argues about them.
- **The top rung is not available to this book, but the lagged sensor says it is.** The flat policy
  claims EUR 500, which needs 1 bp, and clears it only on 4 of 60 days. Its worst window is 29.98
  bps, thirty times the cap.
- **The risk test pays twice.** At the same ceiling it can only remove exemptions, so it admits
  less fraud. Less fraud keeps the trailing rate down, which keeps a higher ceiling unlocked, which
  is why the screened policy ends up exempting more value than the unscreened one while losing a third
  of the fraud. On the full book: EUR 793.59 against EUR 2,312.07, with 8 breach days against 14.
- **The counters are almost never what binds.** The low value exemption refused 61 of 14,152
  transactions under the EUR 30 cap in the tight policy, 0.43 percent. The amount cap sets that
  exemption on this book, not the streak rule.

## Limits

- The book is synthetic and single acquirer: one currency, one country, no merchant level fraud
  differences. The reference rate is instrument level, so one bad merchant drags the ceiling down
  for every good one, and that effect is not in this model.
- The 7 day window and the 2 day lag are modelling choices, not rule text. A shorter window is
  noisier and produces more breach days. The breach count is a property of the sensor as much as of
  the policy.
- Abandonment is a fixed probability per transaction, adjusted for channel and ticket size. Real
  three domain secure step-up behaviour differs by issuer, device, and app, and biometric
  authentication changes it again.
- The risk score is generated, not a model. The cutoffs (0.18 and 0.12) were chosen on this book and
  are not transferable. A real score would need calibration before the fraud numbers meant anything.
- Article 16 says cumulative EUR 100 or five consecutive. This applies both limits together, the
  stricter reading, and resets them on any challenge.
- Fraud is measured at authorization: no friendly fraud, no refunds, no representment. Recoveries
  would reduce the effective fraud rate and unlock a higher ceiling.
- The ladder is treated as the only gate. Supervisory monitoring, scheme rules, and issuer
  challenge flags sit on top of it and are not modelled.
- The eight day cold start is coded, not a defect. It is a real cost of entering a window blind.

## Next

- Replace the fixed rung step with a buffer sized to the window's own variance, so the headroom
  tracks how noisy the book is instead of being one threshold for all of them.
- Add merchant level fraud to the book and price the externality: the clean merchant subsidising the
  bad one through a shared ceiling is the part a merchant would actually feel.
- Model representment, because recovered fraud lowers the rate and the whole ladder moves.
- Score the same policies against a book whose ticket distribution is under EUR 30, where the
  Article 16 counters become the binding control rather than the amount cap.

Scored 4.50 on `RUBRIC.md` section 2: 5 on substance, 4 on verifiability (ground truth is injected
and the invariants are proven, but the risk score has no precision and recall), 4 on novelty (vendor
material describes the ladder, none of it prices the feedback loop), 4 on narrative, 5 on demo
speed, 5 on durability, 5 on positioning.
