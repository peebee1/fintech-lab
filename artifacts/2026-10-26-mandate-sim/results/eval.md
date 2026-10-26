# Mandate simulator eval

Produced by `mandate.cli eval`. Synthetic book, no real customers.

- subscribers: 2000
- invoices: 11630
- horizon: 180 days
- seed: 7

Per rail rates are basis points of that rail's billed amount. The mean columns are the equal
weight mean of the three rail rates, because EUR and INR are never summed here.

Kept is money still in the account. Exposure is money in the account that the payer still has
a right to take back. Reversed is a right that was exercised. Risk adjusted is kept with every
outstanding right treated as already exercised, which is the floor.

## Collection

| Planner | Mean kept | Mean exposure | Mean reversed | Mean declined | Mean not presented | Mean risk adjusted | Median days late | p90 |
|---|---|---|---|---|---|---|---|---|
| naive | 6903 | 3587 | 1973 | 1124 | 0 | 3316 | 0 | 0 |
| notice_aware | 9711 | 2 | 4 | 235 | 50 | 9709 | 0 | 3 |
| rail_aware | 9709 | 0 | 0 | 157 | 134 | 9709 | 0 | 3 |

## By rail

| Planner | Rail | Invoices | Billed | Kept | Exposed | Reversed | Kept bps | Exposure bps | Risk adjusted bps |
|---|---|---|---|---|---|---|---|---|---|
| naive | card | 5924 | EUR 405,742.47 | EUR 403,638.61 | EUR 0.00 | EUR 0.00 | 9948 | 0 | 9948 |
| naive | sepa | 3538 | EUR 229,412.79 | EUR 139,353.46 | EUR 139,353.46 | EUR 72,665.41 | 6074 | 6074 | 0 |
| naive | upi | 2168 | INR 5,854,511.00 | INR 2,744,031.00 | INR 2,744,031.00 | INR 1,611,029.00 | 4687 | 4687 | 0 |
| notice_aware | card | 5924 | EUR 405,742.47 | EUR 403,638.61 | EUR 0.00 | EUR 0.00 | 9948 | 0 | 9948 |
| notice_aware | sepa | 3538 | EUR 229,412.79 | EUR 222,928.21 | EUR 149.00 | EUR 73.99 | 9717 | 6 | 9711 |
| notice_aware | upi | 2168 | INR 5,854,511.00 | INR 5,543,037.00 | INR 0.00 | INR 5,498.00 | 9468 | 0 | 9468 |
| rail_aware | card | 5924 | EUR 405,742.47 | EUR 403,638.61 | EUR 0.00 | EUR 0.00 | 9948 | 0 | 9948 |
| rail_aware | sepa | 3538 | EUR 229,412.79 | EUR 222,779.21 | EUR 0.00 | EUR 0.00 | 9711 | 0 | 9711 |
| rail_aware | upi | 2168 | INR 5,854,511.00 | INR 5,543,037.00 | INR 0.00 | INR 0.00 | 9468 | 0 | 9468 |

## Book composition

| Rail | Invoices | Billed | Over cap invoices | Over cap value share | Mean days late | On time |
|---|---|---|---|---|---|---|
| card | 5924 | EUR 405,742.47 | 0 | 0 bps | 0.1 | 9315 bps |
| sepa | 3538 | EUR 229,412.79 | 0 | 0 bps | 4.8 | 6399 bps |
| upi | 2168 | INR 5,854,511.00 | 70 | 2497 bps | 0.4 | 6988 bps |

## Invoice states

| Planner | Invoices | Clean | Exposed | Reversed | Declined | Not presented |
|---|---|---|---|---|---|---|
| naive | 11630 | 5889 | 3493 | 1865 | 383 | 0 |
| notice_aware | 11630 | 11462 | 1 | 4 | 110 | 53 |
| rail_aware | 11630 | 11462 | 0 | 0 | 37 | 131 |

## Presentation outcomes

| Planner | settled | declined_funds | declined_afa | declined_revoked | declined_too_soon |
|---|---|---|---|---|---|
| naive | 11247 | 780 | 207 | 201 | 488 |
| notice_aware | 11467 | 786 | 40 | 213 | 0 |
| rail_aware | 11462 | 786 | 40 | 0 | 0 |

## Reconciliation

Billed splits exactly once into the five states, and presentations split into settled and declined.

- naive: PASS
- notice_aware: PASS
- rail_aware: PASS

## Revocation lag sensitivity

Same book, same planner (notice and cap aware, revocation blind), only the lag changes.
The lag is the window where the payer has asked to stop and the rail has not stopped yet.

| Revocation lag (days) | Mean kept bps | Mean exposure bps | Mean reversed bps |
|---|---|---|---|
| 0 | 9709 | 0 | 0 |
| 1 | 9711 | 2 | 4 |
| 2 | 9711 | 2 | 10 |
| 3 | 9713 | 4 | 10 |
| 7 | 9715 | 6 | 21 |
