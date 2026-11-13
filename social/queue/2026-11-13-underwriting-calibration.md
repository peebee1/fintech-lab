Two underwriting models can put every borrower in the exact same order and still be $418,000 apart.

I built a book of 6,000 synthetic loans with a known default probability per loan, so a probability can be checked against the truth instead of against a ranking.

Three models score the same 1,500 loan holdout. All three have AUC 0.7402. All three have 0.862 accuracy at a 0.5 cutoff. If your eval reports either number, these models are indistinguishable.

They are not.

One reports a mean default probability of 5.99% on a slice where 13.73% actually default. At a break-even threshold of 9.54%, derived from a 6.2% net margin and 65% loss given default, it approves 85.9% of the book. It projects $144,899 of loss on that book. The book loses $1,067,395. Contribution goes negative: minus $150,633, against $267,123 for the calibrated model. Same loans, same order, $417,755 of difference.

The bad model is not slightly wrong everywhere. 1,292 of the 1,500 loans sit below 0.1 with a mean reported probability of 1.64%, and 10.7% of them default. It is confidently wrong about most of the book, which is exactly what a prompt that answers with a number will do.

Two parameters fix it. Platt scaling fitted on 1,500 settled loans takes Brier from 0.1171 to 0.1067, expected calibration error from 0.0951 to 0.0213, and contribution to $270,379. That is $3,256 above the calibrated scorecard, which itself was mildly overconfident with a fitted slope of 0.87.

The warning inside the result: all three models recalibrate to the same probabilities, because they carried the same ranking information and differed only by a monotone map. Recalibration can restore a level. It cannot add information.

Limit, said out loud: the book is synthetic and the distortion is an exact monotone map, which flatters two parameter calibration. I did not ship predictions from a language model, because a model version cannot be pinned and replayed offline, and a fixture I cannot reproduce is a number I cannot defend. The harness takes any model's loan_id,pd file, which is the seam for that.

Code and the committed numbers:
https://github.com/peebee1/fintech-lab/tree/main/artifacts/2026-11-13-underwriting-calibration
