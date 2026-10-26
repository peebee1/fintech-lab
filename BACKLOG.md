# Backlog

Ranked by the rubric, not by enthusiasm. Machine readable source is `state/backlog.json`.
Run `python3 tools/select.py` for the selector's pick, including the anti repetition penalties.

## Open

| Score | Item | Theme | Claim |
|---|---|---|---|
| 4.70 | Agent-to-agent credit with exposure limits and netting | agentic-commerce | If agents transact with each other all day, someone has to underwrite the float between them. |
| 4.50 | Money allocation and FX rounding engine | money-movement | The penny that goes missing when you split a payment across three parties is a real bug class, not a rounding footnote. |
| 4.50 | Idempotency conformance suite for payment APIs | reliability | A payments API is not idempotent until a buyer can replay it and get the same answer. Most cannot. |
| 4.45 | Sanctions screening that cuts false positives | risk | Screening is not a search box. It is entity resolution, and the cost of a false positive is a frozen customer. |
| 4.45 | Authorization-rate aware payment routing | acquiring | Routing on cost alone leaves money on the table. Routing on approval probability is where the margin is. |
| 4.40 | Broker order, fill, and position reconciliation | market-infra | Retail trading apps fail quietly at the seam between the broker, the exchange, and the books. |
| 4.30 | Chargeback representment state machine | risk | Every dispute is a clock. The product is knowing which clock is running and what evidence still matters. |
| 4.25 | LLM underwriting judged by calibration, not vibes | credit | An underwriting model is good when its probabilities mean something. Brier score does not care how confident the prompt sounded. |
| 4.15 | Append only ledger with a provable close | money-movement | Closing the books is a testable property, not a monthly meeting. |

## Closed

| Status | Item | Theme |
|---|---|---|
| shipped | Spend policy engine for agent-initiated payments | agentic-commerce |
| shipped | Settlement reconciliation that balances to zero | money-movement |
| shipped | Subscription mandate simulator across rails | recurring |
| parked | PAN vault with scoped detokenization | security |
| parked | Bank statement to normalized ledger | data |
| parked | Regulatory change watcher for PSD3, RBI, MiCA | compliance |
