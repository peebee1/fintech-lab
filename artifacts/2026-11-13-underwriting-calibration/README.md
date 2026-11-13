# An underwriting model is a probability, or it is a personality test

Three models score the same 1,500 loan holdout. All three rank the borrowers
identically: AUC 0.7402, and the same 86.2% accuracy at a 0.5 cutoff. One of them
approves 85.9% of the book, reports a mean default probability of 5.99% against a
realized 13.73%, and loses **$150,633** of contribution on loans it should have
declined. The calibrated model on the same book makes **$267,123**.

The difference between those two outcomes is a probability that means something.
Two parameters fitted on 1,500 settled loans, and the losing model's Brier score
falls 8.8%, its calibration error falls from 0.0951 to 0.0213, and its contribution
goes from negative to $3,256 above the calibrated baseline.

## Problem

An underwriting eval usually reports one of three things: AUC, accuracy at 0.5, or a
confusion matrix. All three are rankings. None of them reads the number the model
actually emits, and the number is what the decision consumes:

- the cutoff is a probability threshold, so a model that says 4% when the truth is
  11% gets the approval,
- the price is a function of expected loss, so a model that says 4% undercharges,
- the reserve is a sum of probabilities times exposure, so a model that says 4%
  under-reserves by the same factor.

A rank metric cannot see any of this. Two models can order the book identically and
disagree by a factor of 7 about how much money they expect to lose on it.

That is not a hypothetical failure mode for a prompted model. A language model
asked to underwrite returns a number because you asked for a number, and nothing in
the format keeps it honest. The failure is uniform overconfidence, not bad ranking,
so it hides behind every metric that only looks at order.

## Why it matters

Credit decisions are made at a threshold, and a threshold is only meaningful if the
probability is. In this book the break-even default probability is 9.54%: net revenue
on a performing loan is 6.2% of exposure, a default costs 65% of exposure, so the
line is 0.062 / 0.65. Every loan the model puts below that line gets approved.

The overconfident model puts 1,288 of 1,500 loans below it. The realized default
rate among those 1,288 loans is 10.64%, and it reports $144,899 of expected loss
against $1,067,395 of realized loss. It understates loss by 7.4 times on the book it
chose. No ranking metric flags that, and the approval rate goes up, which looks like
growth until the vintage matures.

The reverse failure is just as expensive and just as invisible. A hedged model that
flattens every probability toward 0.5 approves 29 of 1,500 loans and leaves
$909,728 of contribution on the table while it waits for certainties.

## Design

`uwcal` is seven small modules and no dependencies outside the standard library.

1. `book.py` generates a synthetic settled book: 6,000 loans, six features, a known
   default probability per loan from a fixed coefficient set. The outcome is drawn
   from that probability, so calibration has a truth to be measured against. Ids are
   assigned after a shuffle, so an id based tie break cannot see the label.
2. `metrics.py` holds the scoring rules: Brier, log loss, AUC, expected calibration
   error, and Murphy's three way decomposition (reliability, resolution,
   uncertainty), which says whether a model is wrong about levels or blind to
   differences.
3. `models.py` fits a scorecard by Newton-Raphson (IRLS) with a ridge penalty, then
   produces two distortions of its output: a sharpened score (`k = 2.1`) and a
   flattened one (`k = 0.55`). Both are monotone maps in logit space, so they leave
   the AUC and the accuracy untouched by construction and change only the number.
4. `calibrate.py` fits Platt scaling, two parameters in logit space, on a slice the
   model was not fitted on. Newton with a backtracking line search: plain Newton
   diverges on a sharply tempered score, where the first step sends the intercept to
   the billions because the curvature at a saturated prediction is near zero.
5. `policy.py` turns probabilities into a decision. The cutoff is derived, not
   chosen: net revenue over loss given default. It reports contribution, reported
   expected loss, realized loss, the multiple between them, and the contribution
   forgone on rejected good loans.
6. `ingest.py` reads a `loan_id,pd` file from any model. This is the contract that
   makes the harness model agnostic: a scorecard, a gradient booster, or a prompt
   wrapped in a loop all drop in the same way. Parsing is strict, because a row with
   an extra field or a duplicate id shifts every label after it and the score still
   looks plausible.
7. `bench.py` and `cli.py` run the three way split (3,000 fit, 1,500 calibration,
   1,500 holdout), score everything on the holdout, and write `results/`.

### Decisions and tradeoffs

| Decision | Why | What it costs |
|---|---|---|
| Synthetic book with a known true probability | Calibration needs ground truth; a real book only gives one noisy draw | No macro cycle, no default correlation, one period |
| Three way split, Platt fitted on its own slice | Otherwise recalibration is scored on the data it was fitted to | 1,500 fewer rows for the scorecard |
| Monotone distortion instead of a second model | Isolates calibration from ranking, which is the claim | An exactly invertible distortion flatters Platt |
| Brier plus ECE plus Murphy, not accuracy | Accuracy at 0.5 cannot see a level error, and here it reads 0.862 for all three models | Brier weights the whole curve, not just the decision region |
| Cutoff derived from margin over LGD | A chosen cutoff hides the economics in an assumption | Single period economics, no price elasticity |
| Backtracking Newton for Platt | Plain Newton diverged to b=6.6e9 on the sharpened score | More code, ~60 iterations instead of 8 |
| Strict CSV contract with exact coverage | Silent misalignment is the failure that looks like a good score | A model must emit one row per loan, no partial files |
| No committed model weights | A floating model version cannot be reproduced by CI | The repo measures the method, not a named model |

## Run

```bash
cd artifacts/2026-11-13-underwriting-calibration
PYTHONPATH=. uv run python -m uwcal.cli run
```

That rewrites `results/summary.json`, `results/summary.md` and
`results/reliability_overconfident.csv` and prints the table below. From the repo
root, `uv run pytest` runs the 60 tests in about a quarter of a second.

To score a model of your own, write one row per holdout loan and point the harness
at it:

```csv
loan_id,pd
3000,0.0412
3001,0.1187
3002,0.0063
```

```bash
PYTHONPATH=. uv run python -m uwcal.cli score preds.csv
```

The holdout ids are the last 1,500 ids of the seed 13 book (`loan_id` 4500 to 5999).
Partial coverage is refused, not padded.

## Results

Holdout, 1,500 loans, $17,288,542 of exposure, 13.73% defaulted. All numbers come
from `uwcal.cli run` and are committed in `results/summary.json`.

| Model | AUC | Accuracy at 0.5 | Brier | Log loss | ECE (10 bins) | Mean PD | Approval |
|---|---|---|---|---|---|---|---|
| Scorecard | 0.7402 | 0.8620 | 0.1074 | 0.3551 | 0.0195 | 14.23% | 48.27% |
| Overconfident | 0.7402 | 0.8620 | 0.1171 | 0.4751 | 0.0951 | 5.99% | 85.87% |
| Hedged | 0.7402 | 0.8620 | 0.1193 | 0.4002 | 0.1123 | 24.91% | 1.93% |
| All three after Platt | 0.7402 | 0.8673 | 0.1067 | 0.3542 | 0.0213 | 13.89% | 45.27% |

The same three models as decisions, at the derived cutoff of 9.54%:

| Model | Approved | Defaults | Realized rate | Reported loss | Realized loss | Loss multiple | Contribution |
|---|---|---|---|---|---|---|---|
| Scorecard | 724 | 37 | 5.11% | $297,036 | $254,260 | 1.17 | $267,123 |
| Overconfident | 1,288 | 137 | 10.64% | $144,899 | $1,067,395 | 0.14 | -$150,633 |
| Hedged | 29 | 0 | 0.00% | $14,287 | $0 | 0.00 | $16,362 |
| Overconfident after Platt | 679 | 32 | 4.71% | $302,616 | $219,821 | 1.38 | $270,379 |

What the tables say:

- **Ranking metrics are flat.** AUC is 0.7402 and accuracy at 0.5 is 0.862 for all
  three models, to the last digit. A team reporting either of those would call all
  three identical and ship any of them.
- **The probability is not.** Brier moves from 0.1074 to 0.1171 (9.1% worse) and ECE
  moves from 0.0195 to 0.0951 (4.9 times worse) on the same ranking.
- **The decision gap is money.** $417,755 of contribution between the calibrated
  model and the overconfident one on the same loans, which is $24.16 per $1,000 of
  the holdout book and $278.50 per loan.
- **The shape of the error is underconfidence in the tail.** In the reliability
  file, 1,292 of 1,500 holdout loans land in the 0 to 0.1 bin with a mean reported
  probability of 1.64%, and 10.68% of them default. The model is not slightly wrong
  everywhere, it is confidently wrong about most of the book.
- **The decomposition localizes the fault.** The ten bin reliability term rises from
  0.0019 to 0.0104 and resolution falls from 0.0116 to 0.0098. The model got worse at
  saying how much, and slightly worse at telling borrowers apart, which is the
  opposite of what an AUC review would conclude.
- **Two parameters recover it.** Fitted on the 1,500 loan calibration slice, Platt
  takes Brier from 0.1171 to 0.1067 and ECE from 0.0951 to 0.0213, and contribution
  to $270,379, which is $3,256 (1.2%) above the calibrated scorecard. It also moved
  the scorecard itself by 0.6% on Brier: even the in-house model was mildly
  overconfident, with a fitted slope of 0.8696 against an honest 1.0.
- **The recovery is exact, and that is a warning.** All three recalibrated rows are
  identical because the three models carried the same ranking information and
  differed only by a monotone map. Platt found the same map. Recalibration cannot
  add information, it can only restore a level, so a model whose ranking is bad is
  not rescued by it.

A check on the fit: the recovered slope for the sharpened model is 0.4141. The true
inverse of the applied temperature is 0.4762, and 0.4141 / 0.8696 is exactly 0.4762.
The calibration step recovered the distortion times the scorecard's own mild
miscalibration, which is the only thing the data can identify.

## Limits

- **The book is synthetic.** It is labeled as such in `results/summary.json`
  (`provenance.data`). One period, no macro cycle, no correlated defaults. A real
  book would make every number noisier, and the 1.38 loss multiple after
  recalibration is one draw on 679 loans, not a stable estimate of 1.
- **No LLM predictions are committed.** A model version cannot be pinned or replayed
  offline, so a fixture of prompt outputs would be a number I cannot defend in CI.
  The harness is model agnostic and takes predictions as a file; this repo measures
  the method, not a vendor.
- **The distortion is clean.** A monotone map is exactly invertible, which flatters
  Platt. Real miscalibration is usually heteroscedastic: overconfident in the middle,
  calibrated in the tail. Platt fits one slope and will not fix that, and isotonic
  regression would fit the shape at the cost of overfitting small slices.
- **The economics are one period.** Contribution is margin minus loss. There is no
  price elasticity, no prepayment, no customer lifetime value, and no cost of
  capital, so the dollar gap is a decision quality measure, not a business case.
- **The scorecard's specification matches the generator.** It ranks well because it
  is the right functional form. A misspecified or prompted model would rank worse as
  well as miscalibrate, and the two failures would be harder to separate.
- **One cutoff.** Real portfolios run segment cutoffs. A single threshold makes the
  policy comparison clean and understates how much a segment level level error costs.

## Next

- Score a pinned model's predictions file and publish the same table next to this
  one. The CSV contract and `score` subcommand are already the seam for it.
- Add beta calibration (three parameters) and compare out of sample with Platt and
  isotonic on the same slice, so the choice of recalibration is measured rather than
  assumed.
- Add a per segment reliability view, because a single global ECE can hide two
  offsetting errors in different parts of the book.
- Make the decision value a CI check: a pull request that changes a model must
  report its contribution on the held out book, not only its AUC.
