# consent-refresh

A consent is a lease with an expiry date. Every renewal is a chance for the customer to leave, and the timing of the ask decides which loss you take.

## Problem

An account to account subscription does not debit a card on file. It debits an authorisation, and the authorisation expires. Rails put a maximum lifetime on it: ninety days, sometimes less, sometimes with a rule that says the customer must be present again. So every subscription business on this rail runs a renewal programme, and every renewal programme has two ways to lose money on the same customer:

- Ask late, and the debit is refused. The customer gets a failed payment notice and the revenue for that cycle is gone.
- Ask on a calendar, and the prompt lands in the middle of a month, unattached to anything the customer was doing. Some fraction of them look at it, decide this is effort, and cancel.

Most teams solve this with a cadence, because a cadence is easy to schedule. This artifact asks the other question: what if the prompt is timed against the payment, not against the clock?

## Why it matters

The cost of a prompt is not the notification. It is the customer. In this book the mean walk away probability per prompt is 11.6 percent, and a 30 day cadence sends 6.4 prompts per payer per year. Two thirds of the customers who ever see the accountant side of the product get asked to prove themselves again and again, and each ask has a price.

The two losses have different shapes. A refusal is one payment, bounded and visible in the ledger. A walk away is the rest of the relationship, invisible, and it shows up months later as churn that nobody attributes to a re-authorisation. A policy that optimises the visible number buys prompts with the invisible one.

## Design

One book, one simulator, 360 days, eight policies, plus a reference that is not achievable.

The book: 1,200 payers across 12 merchants, one scheduled debit a month on a fixed day, median bill USD 32.65, 13,834 scheduled debits, USD 525,635.54 billed. Each payer has a consent that starts in the first 30 days and expires 90 days later, a personal re-authorisation latency, a personal walk away probability per prompt, and a monthly natural churn hazard.

The simulator has two clocks per payer. The **consent clock** is the expiry, at an hour resolution. The **response clock** starts when a prompt is issued at the 18:00 batch and ends at the response, which is the issue time plus a log normal draw around that payer's median. A debit is attempted at 10:00 on its due day, and it settles only if the consent expiry is still ahead of that moment. If the response lands after the debit, the renewal does not save that cycle.

The mechanism the artifact is built around: a prompt sent within three days of a scheduled debit is **contextual**. The customer is already dealing with that payment, so the walk away probability is multiplied by 0.45. A prompt sent after a refusal is multiplied by 1.6, because a failed debit makes the product look broken. Both multipliers are judgements, and the stress table exists to show what happens without the first one.

Policies:

- `no_expiry`: reference only. Consent never expires, natural churn still applies. This is the ceiling.
- `never_refresh`: no prompts at all. The consent runs out and the second half of the year refuses.
- `on_failure`: no planned prompts. Ask only after a debit has been refused.
- `fixed_30`, `fixed_90`: ask every 30 or 90 days after the last ask, as long as a debit is still scheduled.
- `jit_1`, `jit_2`, `jit_3`, `jit_7`: ask only when a scheduled debit would land after expiry, and only that many days before it.
- `adaptive_lead`: the same rule, with the lead set from the customer's own observed response latency (worst observed plus a day, floored at 2 and capped at 21).

### Decisions and tradeoffs

| Decision | Why | What it costs |
|---|---|---|
| A 90 day consent lifetime | Modelled on the re-authentication rule open banking regimes apply to long lived consents | Other regimes allow longer, and a longer lifetime makes every policy look better. The ranking between policies does not depend on it, the size of the gap does |
| Walk away probability drawn per payer, 3% to 20% | Prompt fatigue is a customer trait, not a constant | The mean (11.6%) decides how much a prompt costs. The stress runs test 1.0x and slower responses, not a different walk away distribution |
| Contextual prompts convert at 0.45x | The customer is already in the payment flow, not interrupted by it | This single multiplier is what makes the 3 day lead win. The no-context stress removes it, and the winner changes to a 7 day lead |
| Refusals are not retried | A refused A2A debit is a separate re-presentment with its own drop off | It makes `on_failure` look worse than a system that retries. The honest read is that retry moves the cost, it does not remove it |
| Prompt batch at 18:00, debit at 10:00 | One fixed schedule for both, so the response window is comparable across policies | A real system prompts on demand. Fine hour level timing is therefore not modelled, day level timing is |
| A reference ceiling that no rail allows | To separate natural churn from policy losses | The ceiling is arithmetic, not a target. 9.9% of billed revenue is gone before any consent expires |
| Same seed for every policy | Every policy meets the same customers and the same bills | Random draws still diverge once prompt counts differ, so policy gaps carry sampling noise. The sweep shows its size |

## Run

```bash
# from the repo root
PYTHONPATH=artifacts/2026-11-18-consent-refresh uv run python -m consent.cli bench
uv run pytest artifacts/2026-11-18-consent-refresh
```

The bench rewrites `results/summary.json` and `results/summary.md` and takes about 25 seconds. Standard library only, no network, no clock reads.

## Results

Book: 1,200 payers, 13,834 scheduled debits, USD 525,635.54 billed, median bill USD 32.65, median re-auth latency 20.4 hours, mean walk away 11.6% per prompt. Scored on 360 days.

| Policy | Settled | Refused | Refused USD | Captured USD | Capture rate | Prompts | Prompts/payer | USD per prompt |
|---|---|---|---|---|---|---|---|---|
| no_expiry (ceiling) | - | - | - | 473,680.11 | 100.0% | 0 | 0.0 | - |
| never_refresh | 3,548 | 9,007 | 339,382.93 | 134,297.18 | 28.3% | 0 | 0.0 | - |
| on_failure | 8,279 | 2,322 | 87,972.04 | 312,873.07 | 66.0% | 1,990 | 1.66 | 157.22 |
| fixed_30 | 6,403 | 0 | 0.00 | 241,699.56 | 51.0% | 7,669 | 6.39 | 31.52 |
| fixed_90 | 9,226 | 39 | 1,560.38 | 349,661.46 | 73.8% | 3,741 | 3.12 | 93.47 |
| jit_1 | 10,089 | 1,590 | 60,239.29 | 380,585.24 | 80.3% | 2,789 | 2.32 | 136.46 |
| jit_2 | 11,012 | 687 | 26,937.41 | 418,007.49 | 88.2% | 2,963 | 2.47 | 141.08 |
| jit_3 | 10,899 | 350 | 13,383.83 | 424,678.49 | 89.7% | 3,024 | 2.52 | 140.44 |
| jit_7 | 10,676 | 66 | 2,210.78 | 401,479.08 | 84.8% | 2,889 | 2.41 | 138.97 |
| adaptive_lead | 10,853 | 173 | 6,259.31 | 408,803.52 | 86.3% | 2,919 | 2.43 | 140.05 |

Three things the table says:

1. **A refresh calendar is barely better than no refresh at all.** `fixed_30` captured USD 241,699.56, which is 1.80 times `never_refresh`, while sending 7,669 prompts and losing 787 mandates to walk away. `never_refresh` lost its mandates to expiry instead. The 30 day cadence pays in customers for revenue it could have had by waiting.
2. **Timing against the debit is the whole game.** `jit_3` captured 89.7% of the ceiling with 2.54 times fewer prompts than `fixed_30`, and USD 182,978.93 more revenue. Against the ceiling it leaves USD 49,001.62, and 9.9% of billed revenue was never available because of natural churn.
3. **More lead is not more safety.** `jit_7` refused 66 payments against `jit_3`'s 350, and still captured USD 23,199.41 less, because a prompt a week out is out of the payment context and loses 11.6% of the customers it asks. The best policy is not the one with the fewest refusals.

### Lead sweep

The same just in time policy, lead from 1 to 12 days. The jump at day 3 to 4 is the context window, not a slope:

| Lead | Refused | Captured USD | Capture rate | Contextual share |
|---|---|---|---|---|
| 1 | 1,590 | 380,585.24 | 80.3% | 100% |
| 2 | 687 | 418,007.49 | 88.2% | 100% |
| 3 | 350 | 424,678.49 | 89.7% | 100% |
| 4 | 197 | 394,185.30 | 83.2% | 0% |
| 5 | 125 | 407,128.04 | 86.0% | 0% |
| 6 | 99 | 401,419.69 | 84.7% | 0% |
| 7 | 66 | 401,479.08 | 84.8% | 0% |
| 8 | 45 | 410,019.83 | 86.6% | 0% |
| 9 | 35 | 410,839.41 | 86.7% | 0% |
| 10 | 24 | 405,182.09 | 85.5% | 0% |
| 11 | 16 | 406,830.88 | 85.9% | 0% |
| 12 | 18 | 408,695.44 | 86.3% | 0% |

Past four days the refusal count falls to double digits and the capture rate stops moving in one direction: 16 refusals at eleven days against 18 at twelve is noise, not a trend. Everything above 83% in that tail is the same policy wearing different offsets.

### Stress

| Run | fixed_30 | jit_2 | jit_7 | adaptive_lead |
|---|---|---|---|---|
| Base | 51.0% | 88.2% | 84.8% | 86.3% |
| Contextual prompts convert no better (1.0x) | 49.8% | 81.4% | 84.8% | 84.4% |
| Responses 1.5x slower | 53.4% | 85.7% | 85.1% | 85.8% |

Without the contextual advantage, the short lead stops winning and the ranking falls back to whichever policy refuses least. That is the honest version of the finding: the 3 day optimum is the product insight doing the work, and it is an assumption with a measured price of about 7 points of revenue.

The adaptive policy is the negative result. It learns each customer's latency, halves refusals against the fixed 3 day lead (173 against 350), and still finishes USD 15,874.97 behind it, because the lead it chooses is longer: 266 customers walk away at the prompt against 174 for `jit_3`. Precision about response time moves the ask out of the payment context, and the context is worth more than the refusal it prevents. It only wins when responses are slow: 85.8% against 85.7% for `jit_2` at 1.5x latency.

## Limits

- Every number comes from a synthetic book. The payers, bills, latencies, walk away probabilities, and churn hazards are generated by `consent/book.py`, and none of the rates are measured from a real product.
- The causal claim rests on two multipliers, 0.45 for a prompt near a debit and 1.6 after a refusal. Neither is estimated from data. Remove the first and the winner changes, which the stress table shows.
- Refusals are not retried. A real programme re-presents a failed debit, usually with a fresh prompt, so `on_failure` and `never_refresh` understate what a real operator recovers.
- Consent lifetime is a single 90 day constant for every payer and every merchant. Real regimes and real banks differ, and a longer lifetime shrinks every gap in the table.
- The prompt is a batch at 18:00. Response latency is log normal around a per payer median, with no time of day effect, no weekend effect, and no second prompt if the first is ignored.
- Walk away is modelled as an exit from the mandate, not as churn from the merchant. A customer who abandons the consent and pays by card is counted as lost.
- One merchant context per payer. Nothing models the same customer holding several consents and getting tired of all of them together.
- Natural churn is a monthly hazard applied at month boundaries, so the ceiling itself carries the generator's shape.

## Next

- Replace the 0.45 context multiplier with a measured one. A holdout that randomises prompt timing against the debit date would price it in a quarter, and it is the only assumption the answer hinges on.
- Model re-presentment after a refusal, with its own walk away rate, so `on_failure` is scored against a policy that actually tries.
- Give each payer several consents across merchants and test whether fatigue is per merchant or per customer. If it is per customer, the right unit of policy is the customer, not the mandate.
- Add prompt channel and copy as policy dimensions. The table measures when to ask and ignores how, which is probably worth as much as when.
- Test the 3 day rule on rails with a different lifetime, starting with one that requires customer presence every 90 days regardless of activity.
