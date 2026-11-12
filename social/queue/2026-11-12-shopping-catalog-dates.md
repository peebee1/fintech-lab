A fresh clone of a 100 day old product catalog told me its data was 0 minutes old.

That is the whole bug, and it was mine.

The trust layer in my shopping agent prints a line under every answer:

    data as of 2026-11-12 08:02 UTC (fresh, 0m old)

The date came from the catalog file's mtime. Git does not preserve mtime: every checkout stamps the file with the clone time. So the freshness label was measuring the checkout, not the data. Anyone cloning the repo saw fresh data forever, and the 7 day staleness threshold could never fire. Neither committed catalog carried a date at all, so there was nothing else to fall back to.

The fix is one field. The catalog now records `_meta.data_as_of` when the crawl or the generator saves it, and the loader reads that before it touches the filesystem. Legacy files with no field still fall back to mtime, but the source now reports which one it used, so a fallback is visible instead of silent. The eval report carries the same date next to the score, because a score without a data vintage cannot be compared to anything later.

I refreshed both books the same way a reader would: 243 synthetic products regenerated from committed code (byte identical products, only the metadata changed), then the real store re-crawled, 35 pages fetched, 7 products seen again, 0 price changes.

Two clones, before and after. Before, a clone of the old commit reported "as of 08:02", the clone time, on August data. After, a clone of the new commit reports "as of 08:03", the date the data was made, with the file stamped 09:06 on disk.

The limit: this makes the date honest, it does not make the price right. A recorded date can still belong to a crawl that missed a variant or read a list price as a sale price, and 7 re-read products is a small sample. What it removes is the failure mode where the number looks fine because the clock restarted.

Code: https://github.com/peebee1/shopping-concierge/commit/6983743
