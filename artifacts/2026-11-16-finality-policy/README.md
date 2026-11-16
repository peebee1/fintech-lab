# finality-policy

A confirmation count is a bet on the depth of the next reorg, priced in blocks and settled in dollars.

## Problem

A payments processor accepting stablecoins has to decide when a payment is money. Credit the
merchant at inclusion and a reorg can take the payment back after the balance moved. Wait for
confirmations and every customer waits, including the ones buying a coffee.

Teams answer this with a number. Twelve blocks, or thirty, or thirty two, usually copied from a
document, an exchange, or a tweet, applied to every ticket on every chain. The number is a bet:
it is only correct if the next deep reorg is shallower than the number, and nothing in the rule
knows how deep that is.

This artifact prices the bet. Five policies run over the same synthetic book on three chains with
different block times and different reorg processes, and every dollar of loss, every second of
wait and every false credit is counted.

## Why it matters

The loss is not proportional to the volume, it is proportional to the tail. A single payment that
sat on a block inside a deep fork can cost more than a month of confirmations saved. In this book,
crediting at inclusion loses USD 19,051.68 on one payment, 22 percent of the four week loss, and
136 basis points of the value processed.

Waiting has a cost too, and it is not the cost of capital. For a USD 20 ticket the carry is
nothing; what the merchant pays is a customer who cannot see the money, a support ticket, and an
abandoned checkout. That cost is roughly flat per payment, which is why the right depth depends on
the ticket size and not on the chain's reputation. A rule that treats a USD 56,000 invoice like a
USD 20 coffee is leaving money on one side or time on the other, and it does not know which.

## Design

Five policies, one simulator, one book:

- `credit_on_inclusion`, k = 1. Every payment is credited the block it lands in. The floor.
- `fixed_12`, k = 12 everywhere. The number most often copied.
- `chain_defaults`, 12 on the fast chain, 30 and 32 on the others. One number per chain, chosen once.
- `ticket_tiers`, a latency target per ticket band converted to blocks per chain: 12 seconds under
  USD 100, 45 seconds to USD 1,000, 120 seconds to USD 10,000, 300 seconds above.
- `calibrated`, the smallest k where the expected loss from a measured per chain curve is no worse
  than the cost of waiting that long.

The simulator has two clocks per payment. The **credit height** is `inclusion + k - 1`, when the
merchant balance moves. The **detection height** is where the replacement branch is at least as long
as the block that held the payment, which is the first height at which anyone can know the payment
was reorged out. Detection at or below credit means waiting caught it: the payment is re-included and
credited later, no loss. Detection above credit means the merchant was credited while the chain could
still take it back: a false credit, and a loss if the transaction never lands again.

Reorg depth is modelled in two classes: routine forks, mostly one or two blocks with a geometric
tail, and incidents, a deeper fork at a low rate. The incident class is the one a confirmation count
is supposed to cover and the one a team has to guess about.

The calibrated policy fits its loss curve on 28 days of a separate simulated history, then is scored
on four held out weeks. It never sees the evaluation book.

### Decisions and tradeoffs

| Decision | Why | What it costs |
|---|---|---|
| A stated synthetic reorg process, not measured chain history | Public reorg depth data is anecdotal and unequally published across chains | The rates are invented and set high enough to produce signal in a week. Results scale with them. This is a policy comparison, not a claim about Base, Polygon or Ethereum |
| Two clocks, credit and detection | The loss is about visibility, not about counting | Assumes a reorg is observable at the height where the new branch matches the old one, which ignores how a node actually learns about it |
| Waiting cost with a fixed per payment term | A rule that ignores ticket size cannot be right on both a coffee and an invoice | The USD 0.25 per payment hour is a judgement, and it decides how much a small ticket is allowed to wait |
| Calibration on a different seed, evaluation on four weeks | A rule fitted on its own test week proves nothing | The tail still comes from the same generator family, so the fitted rule is optimistic by construction. The stress table is there to show the size of that optimism |
| Report total cost next to loss and wait | A policy that loses nothing by waiting 20 minutes is not a better policy | Total cost inherits the cost parameters, so it is a stated objective, not a fact |
| Deepen incidents 1.5x for the stress run | The tail is the thing that breaks a fitted curve | One stress point is not a distribution, and picking 1.5x is a choice |

## Run

```bash
cd artifacts/2026-11-16-finality-policy
PYTHONPATH=. uv run python -m finality.cli bench   # rewrites results/
PYTHONPATH=. uv run python -m finality.cli show    # prints the committed policies
cd ../.. && uv run pytest artifacts/2026-11-16-finality-policy
```

No network, no keys, no wall clock. The bench takes about a second and a half, writes
`results/summary.json` and `results/summary.md`, and two runs produce identical bytes, which the
suite asserts.

## Results

Book: 4,000 synthetic payments a week, USD 1,671,976.24 of value, median ticket USD 136.26, p99
USD 4,304.82, largest USD 56,127.80, across base, polygon and ethereum. Four held out weeks, so
16,000 payments and USD 6.69 million scored per policy. Calibration is 28 days of a different
history.

| Policy | k median | lost USD | loss bps | false credits | median wait s | p95 wait s | within 60s | total cost USD |
|---|---|---|---|---|---|---|---|---|
| credit_on_inclusion | 1 | 84,791.45 | 136.4 | 366 | 4 | 21 | 100.0% | 84,798.95 |
| fixed_12 | 12 | 13,912.83 | 22.4 | 58 | 26 | 153 | 80.0% | 13,970.44 |
| chain_defaults | 30 | 13,857.15 | 22.3 | 56 | 61 | 393 | 45.0% | 13,983.52 |
| ticket_tiers | 6 | 2,832.36 | 4.6 | 56 | 47 | 121 | 92.5% | 2,879.95 |
| calibrated | 35 | 202.64 | 0.3 | 3 | 93 | 344 | 3.1% | 345.90 |

Total cost is loss plus the stated waiting cost, so it is an expression of the objective in the
design, not a neutral score.

Three things stand out.

**Twelve blocks buys most of the easy money and none of the hard money.** It removes 84 percent of
the loss against crediting at inclusion and still leaves USD 13,912.83, of which USD 13,857.15 sits
on the fast chain, where the incidents that matter fork deeper than 12. The per chain defaults do
not help: 12 on base is the same leak, and 30 and 32 on the other two chains buy 61 seconds of median
wait for USD 55.68 of avoided loss over four weeks.

**The loss curve is a cliff, not a slope.** Pooled over the four weeks, a fixed depth gives:

| k | 1 | 12 | 24 | 32 | 40 | 48 |
|---|---|---|---|---|---|---|
| lost USD | 84,791 | 13,913 | 8,258 | 6,608 | 359 | 0 |
| loss bps | 136.4 | 22.4 | 13.3 | 10.6 | 0.6 | 0.0 |
| median wait s | 4 | 26 | 50 | 66 | 82 | 98 |

Going from 12 to 32 confirmations, more than doubling the wait, halves the loss. Going from 32 to 40
almost eliminates it. The step is where k passes the depth of the incidents in that history. A team
copying 12, 16 or 24 is standing on the flat part of the curve and cannot tell from the number that
it is.

**Ticket size carries more information than the chain does.** The tier table, which is just four
rows and a latency target, takes the same book to 4.6 bps while 92.5 percent of payments still clear
inside a minute. The fitted curve takes it to 0.3 bps, and the money it saves is where the tiers
still leak: USD 994.59 of sub USD 100 losses and USD 1,837.77 in the USD 100 to 1,000 band, against
USD 69.16 and USD 133.48 for the fitted rule.

The fitted curve is the cheapest in this book, and that is partly by construction, because it
optimises the same cost the table reports. The honest test is the stress run: the same four weeks,
every incident 1.5x deeper than anything in the calibration month, policies keeping the depth they
were fitted with.

| Policy | stress lost USD | stress bps | in sample lost USD |
|---|---|---|---|
| credit_on_inclusion | 123,974.86 | 199.4 | 84,791.45 |
| fixed_12 | 16,355.88 | 26.3 | 13,912.83 |
| chain_defaults | 16,002.61 | 25.7 | 13,857.15 |
| ticket_tiers | 5,321.96 | 8.6 | 2,832.36 |
| calibrated | 6,740.41 | 10.8 | 202.64 |

The fitted rule goes from USD 203 to USD 6,740 and is beaten by the four row table, because the
table's top band asks for 300 seconds, which is 64 blocks on the fast chains and 25 on the other,
while the fitted rule stopped at the deepest incident it had evidence for. That is the point of the
artifact. A rule learned from history is a rule about history, and the ticket tier version fails more
gracefully when the tail moves.

## Limits

- **The reorg process is synthetic and the rates are high on purpose.** 150 routine reorgs a day on
  a 2 second chain, with 4 percent of them incidents of 20 to 48 blocks, is a stress setting chosen
  so a one week window contains enough events to separate policies. It is not a measurement of Base,
  Polygon or Ethereum, and the dollar figures move with the rate.
- The drop probability is constant per chain (0.55 to 0.60), so a reorged payment is a coin flip
  between re-inclusion and a permanent loss. Real double spends are rarer and correlated with value.
- Only the credit is modelled. A processor that has already paid out to the merchant has a recovery
  problem and a customer relationship on top of the loss, and neither is priced here.
- The cost of waiting is two numbers, USD 0.25 per payment hour plus 12 percent a year on the
  ticket. Change them and the winner changes, which is why the objective is stated rather than
  implied.
- Calibration resolution is bounded by 28 days. The curve reaches zero at the deepest incident in
  that window, so the fitted policy cannot price a rare deeper one. The stress run measures how bad
  that is at 1.5x, not at 5x.
- Percentiles are nearest rank stepping down, so a p95 over few samples is coarse.
- One currency and one direction of payment. No FX, no refunds, no chargebacks, no card rails.
- Everything here is generated by committed code and labelled synthetic. No real chain data, no real
  merchants, no customer data.

## Next

1. Fit the loss curve on real chain headers: record every fork from an RPC subscription, keep the
   depth distribution per chain per quarter, and treat the deepest observed fork as a floor, not a
   maximum.
2. Add an exposure cap per ticket so a single payment cannot lose more than a stated amount,
   independent of how deep the next incident goes. Today the policy covers depth; it does not cap
   severity.
3. Model the published balance, not just the credit. A merchant who has already been paid out turns
   a reorg into a receivable, and the cost of that is a different number.
4. Price the payout schedule with the finality policy, since a payment credited at 40 blocks and
   paid out at 48 is a different risk than one credited and paid at the same height.
