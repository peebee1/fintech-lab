The book said the position was fine. It was 844 shares wrong.

I built a reconciliation bench for the seam between a broker, an exchange tape and a retail app's own fill record. 1,200 synthetic orders, 1,668 prints, 286 injected breaks across eight classes: duplicate fills, missing prints, price drift, quantity mismatch, a lagging broker snapshot, a fill that races a cancel, an orphan fill, and a position that moved with no fill behind it.

Four ways to reconcile it. Trust the broker's cumulative filled quantity and the book ends up 844 shares and 27.2 lakh rupees away from the tape, while reporting zero breaks, because it has nothing to compare against. Reconcile the app to the broker and you get 206 alerts at 43 percent precision, and the book is still 1,424 shares off. Book the archive in arrival order and it is worse than the broker: 1,779 shares and 5.5 lakh of cash, because duplicates stay in.

Use the tape as quantity truth and every share of drift has a name. The reconstructed book equals the tape, and the explained delta test closes to a maximum gap of 0 across the clean symbols and 0 paise on cash. The test can fail: flip the correction sign and the gap becomes 302 shares.

Then the boring problem showed up. A complete detector produces 286 breaks and nobody works 286 breaks. Ranked by rupee impact, 60 review tickets cover 87 percent of 1.47 crore of exposure. In arrival order, the same 60 tickets cover 26 percent. The ordering is worth more than the detection once detection is complete.

Limit, said out loud: the detector was written against the same eight-class taxonomy the simulator injects, so 1.00 precision and recall mean the taxonomy is separable from the three records, not that a live feed behaves this way. A real tape has exchange busts, mid-stream rejects and corporate actions this model does not carry.

Code and the committed results:
https://github.com/peebee1/fintech-lab/tree/main/artifacts/2026-11-09-exchange-recon
