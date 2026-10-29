My trading agent's API key sat in a log file on my laptop for eleven weeks.

I found it while closing a defect I had filed as "the SDK logs the Authorization header". The
filed version was too small. The Angel One SDK logs the whole failing request at ERROR level,
headers and body, and it attaches its own file handler in `logs/<date>/app.log`. That handler
is built inside the SDK's constructor, so my `logzero.loglevel(50)` never reached it. What was
actually on disk: 39 credential values across 32 lines in 6 log files, including the
`X-PrivateKey` API key, which had not changed since August, and the refresh token in the request
body.

Why my first fix would not have worked: silencing the logger is the obvious move, and it does
nothing here, because the file handler has its own level. The fix that holds is a filter on the
logger, not on a handler, so it also covers the handler the SDK attaches after import. It
rewrites JWTs, bearer tokens, anything under a secret key, and masks the IP and MAC on the same
line down to their network. A small script applies the same function to the files already
written, and a `--check` mode exits non zero while any secret remains.

The diagnosis still reads. The URL, the error code and the message survive, which is the whole
point of the log line.

Limit, said out loud: this was local, gitignored, and the tokens die at IST midnight, so the
blast radius was small and I got lucky on timing rather than on design. The filter also only
covers what goes through the SDK's logger. Code that formats a token into a string itself
still gets through, and no test in the repo catches that.

101 tests, 0 failures, and the purge now reports 0 secrets in 12 files, down from 39.

https://github.com/peebee1/angelone-smartapi/commit/48196f1
