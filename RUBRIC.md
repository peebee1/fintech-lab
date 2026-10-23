# Evaluation rubric

Every item that enters this repo is scored here before it is built, and re-scored after.
The rubric exists to stop two failure modes: shipping demos that prove nothing, and
shipping the same idea twice with a new name.

## 1. Hard gates

Any failed gate means the item is parked, not shipped. Gates are binary and checked by
`tools/gate.py`.

| Gate | Rule | Why |
|---|---|---|
| G1 Runnable | One documented command runs it from a clean checkout, no paid key needed | A repo nobody can run is a blog post |
| G2 Tested | Tests pass, are deterministic, and cover the central claim | Flaky or decorative tests hide regressions |
| G3 Measured | At least one number is produced by committed code, with the command to reproduce it | Claims without numbers are marketing |
| G4 Honest | No secrets, no PII, no live credentials, synthetic data labeled as synthetic | Trust is the product in fintech |
| G5 Documented | README has Problem, Why it matters, Design, Run, Results, Limits, Next | The limits section is where credibility lives |
| G6 Portable | Stdlib or pinned deps, no service to boot, CI green | A demo that needs five servers never runs again |
| G7 Scoped | Fits one build cycle, roughly 700 changed lines or fewer | Half-finished work is worse than unstarted work |

## 2. Scored dimensions

Each dimension is scored 1 to 5. Anchors are explicit so two runs of the selector agree.

### S1 Fintech substance (weight 25%)

| Score | Anchor |
|---|---|
| 5 | Implements a primitive where being wrong costs real money: settlement, reconciliation, idempotency, mandates, limits, ledger invariants, FX rounding, dispute state machines |
| 4 | Real fintech behavior with some edge cases left out |
| 3 | Fintech-adjacent workflow, no money semantics |
| 2 | Generic tool wearing fintech vocabulary |
| 1 | Unrelated demo with a payments logo |

### S2 Verifiability (weight 20%)

| Score | Anchor |
|---|---|
| 5 | Ground truth is injected, error classes are measured (precision, recall, F1), and a hard invariant is proven (for example: the books balance to zero) |
| 4 | Reproducible benchmark with clear pass or fail thresholds |
| 3 | Unit tests only |
| 2 | Manual walkthrough |
| 1 | Screenshots |

### S3 Novelty (weight 15%)

| Score | Anchor |
|---|---|
| 5 | Nobody publicly demonstrates this end to end, or the public version is a vendor brochure |
| 4 | A meaningfully better version of something that exists |
| 3 | Solid rebuild of a known pattern |
| 2 | Tutorial clone with renamed variables |
| 1 | Repo scaffolding with no idea inside |

### S4 Narrative (weight 15%)

| Score | Anchor |
|---|---|
| 5 | One sentence a payments PM would repeat at dinner |
| 4 | Clear hook, needs one supporting line |
| 3 | Describable, not memorable |
| 2 | Needs a paragraph |
| 1 | Cannot be explained without the code |

### S5 Demo speed (weight 10%)

| Score | Anchor |
|---|---|
| 5 | One command, under 60 seconds, produces something visible |
| 3 | Two commands, a minute or two |
| 1 | Multi-service setup |

### S6 Durability (weight 5%)

| Score | Anchor |
|---|---|
| 5 | Pure logic, no external API, still true in a year |
| 3 | Needs occasional dependency refresh |
| 1 | Depends on a vendor endpoint or a model version that will vanish |

### S7 Positioning fit (weight 10%)

| Score | Anchor |
|---|---|
| 5 | Directly supports the thesis: AI-native fintech infrastructure, built in the open, by a product leader who can also write the code |
| 3 | Adjacent |
| 1 | Off-brand |

Weighted score = 0.25 S1 + 0.20 S2 + 0.15 S3 + 0.15 S4 + 0.10 S5 + 0.05 S6 + 0.10 S7.

## 3. Thresholds

| Weighted score | Action |
|---|---|
| >= 4.2 | Build, and mark as a promotion candidate for a standalone repo |
| 3.6 to 4.2 | Build in the lab |
| 3.2 to 3.6 | Build only if the backlog is thin |
| < 3.2 | Park, keep the one-line thesis in the backlog |

## 4. Anti repetition

- Minus 0.5 if keyword overlap with any of the last 10 shipped items exceeds 40 percent.
- Minus 1.0 if the same theme shipped twice in the last 5 build days.
- Ceiling of 2 items per theme per calendar month, regardless of score.

The penalty is applied by `tools/select.py` at selection time, not by the model, so a
good mood cannot override it.

## 5. Improvement items (existing repos)

Improvements to existing public repos are scored separately, because they are about
paying down trust, not novelty.

`priority = (impact x confidence) / effort`, each 1 to 5.

| Field | Question |
|---|---|
| Impact | Does this change what a stranger sees in the first 60 seconds, or whether CI is green? |
| Confidence | Do we know the defect is real, from a failing test or a measured gap? |
| Effort | Can it land in this cycle without half-finishing anything? |

Ship at 4.0 or above. Fix order: broken tests, then missing CI, then README credibility,
then fintech angle, then new features.

## 6. Promotion rule

An artifact becomes a standalone repo when all of the following hold:

1. Weighted score is 4.2 or higher after the build.
2. Its measurements reproduce on a second run, or in CI.
3. It has a name and a one-line thesis that survive without this lab.

Promotion means: new repo, README rewritten for a cold reader, the lab README links to
it, and the artifact directory stays as the historical record.

## 7. What is deliberately not rewarded

- Commit count on its own. The streak matters only because it forces finished work.
- Stars. This is a trust surface for hiring and partnerships, not a growth channel.
- Coverage percentage on glue code.
- New frameworks. Stack choice is free, so it is never a reason to ship.
