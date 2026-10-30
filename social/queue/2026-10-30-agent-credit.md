A limit on what an agent spends is not a limit on what it owes.

I built a small clearing house for agent to agent payments: a credit limit per member,
multilateral netting at the window close, and a default model. Twelve synthetic agents,
3,000 obligations, 20 settlement windows.

One number first. Multilateral netting removed 94.59% of the money that would have moved:
$215,945.19 of obligations settled in $11,687.43 of payments. Netting per pair only reached
68.76%, because a cycle of five agents nets to zero only if all five are in the same set.

Then the part I did not expect. The obvious control is a cap on gross outflow, the
"spent + amount > limit" check most of us write first. At $200 it carried 21.26% of the
market's value. A cap on net debit, what the agent would still owe at the close, carried
97.84% at the same $200 of worst case loss. That is 4.6x the payment volume for the same
risk ceiling, and it is not a clever model, it is the difference between counting what an
agent sends and counting what it owes.

The gross rule only admits the whole market at a limit 7.5x larger than the loss it ever
needs to cover. Until then it is refusing routers, the agents whose net position stays near
zero because they are paid and paid back in circles all day. In this data the largest
debtor owed $217.20 net after sending $935.80 gross.

That 4.8x is the argument for netting and the size of the bet, at the same time. The
counterparties only ever needed $217.20 from that agent, and they were exposed to $935.80
of its payments until the netting set held.

Limit, said out loud: the benefit and the loss are the same quantity. This models one
failure and stops. No margin, no clearing fund, no second default, and no legal view on
close out netting against a counterparty that has already failed. The flows are synthetic,
and cycle depth is the parameter that drives the 94.59%.

Code, tests and the committed results:

https://github.com/peebee1/fintech-lab/tree/main/artifacts/2026-10-30-agent-credit
