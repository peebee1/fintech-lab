A deposit sweep can leave 2.3 percent of the book uninsured while every yield report looks correct.

I built a synthetic program book: 1,500 customers, USD 50,410,003.08 of deposits, 8 partner banks paying 3.40 to 4.55 percent. Insurance is per customer per bank up to USD 250,000. The default engine fills the best paying bank first and never asks whether one customer now holds more than that. The result is USD 1,162,238.27 uninsured, and all of it sits on 10 customers.

Capping every customer at 250,000 per bank with at most three links cuts the exposure to USD 133,344.23, 0.26 percent, for 12 extra links and USD 18 a year. Interest does not move by a cent. It is USD 1,910,440.10 either way.

That equality is the point. Capacity is what binds. Seven of eight banks are full and the network sits at 91.65 percent of capacity, so the blended rate is set by how much the banks will take, not by which customer gets the money. Double every bank's capacity and income rises USD 137,525.01, 7.20 percent.

The mistake is paying for the fix in links. Splitting every customer equally across all eight banks also reaches zero uninsured, with 5,088 links instead of 1,520, at USD 5,352 a year more in statements and tax forms.

Order matters as well, and it costs nothing to get right. Serve the smallest balances first at the same three link cap and uninsured dollars go from USD 133,344.23 to USD 1,185,313.75. Total interest is identical to the cent. The difference is who gets covered and who is offered the best rate.

What I left out: joint accounts, deposit beta, and the same day liquidity buffer. And the free part is conditional. When the book is small enough to fit inside the top bank, the cap does cost yield: 1.41 bps on a 60 customer book.

Code and numbers:
https://github.com/peebee1/fintech-lab/tree/main/artifacts/2026-11-28-deposit-sweep
