# Validating the alt-test implementation

`confusion_mapper/alttest.py` implements the Alternative Annotator Test from Calderon, Reichart and Dror (ACL 2025). The method is theirs. What I had to get right was the implementation: the package has no numpy or scipy, so the Student's t distribution and the Benjamini-Yekutieli correction are written from scratch. A small bug in either would quietly flip pass/fail verdicts, so I checked everything against independent code before trusting it.

Script: [`alttest_crosscheck.py`](alttest_crosscheck.py). It needs numpy and scipy, which ConfusionMapper itself does not depend on.

```bash
pip install numpy scipy
python benchmarks/alttest_crosscheck.py
```

## Results (run on 12 November 2026, scipy 1.15.3)

| Check | Compared against | Cases | Result |
|---|---|---|---|
| `t_cdf` | `scipy.stats.t.cdf` | 6,734 points, df from 1 to 500, t from -12 to 12 | max absolute error 1.07e-13 |
| `benjamini_yekutieli` | numpy version from the authors' notebook | 20,000 random p-value sets of size 1 to 12 | 0 mismatches |
| full `alt_test` | the authors' `alt_test` logic with `scipy.stats.ttest_1samp` | 369 random synthetic panels | 0 winning-rate mismatches, 0 advantage-probability mismatches, max p-value difference 5.4e-14 |

The panels varied the number of coders (2 to 6), categories (2 to 4), items (30 to 150), coder and AI noise, and epsilon (0, 0.1, 0.15, 0.2). Half of them had about 10% of human labels deleted at random, to exercise the missing-data path. 400 panels were generated; in 31 of them the deletions left no coder with the 30 usable items the test requires, so neither implementation had anything to test and those were not compared.

## The one place I deliberately differ

When every per-item difference is identical, the standard error is zero. If the mean is below epsilon, scipy returns t = -inf and p = 0, and so do I. If it is above, both return t = inf and p = 1. Only when the mean sits exactly on epsilon does scipy return nan, and there I return p = 1, since there is no evidence against the null and a nan would only muddle the correction step. In the 369 panels that exact case came up twice. Neither a nan nor a 1 counts as a rejection, so the verdicts are identical.

## A second sanity check, from the simulator

The authors' README says their annotator noise levels map to inter-annotator kappa roughly like this: 0.1 to 0.80, 0.2 to 0.63, 0.3 to 0.48, 0.4 to 0.36. ConfusionMapper's power simulator reimplements their generative model with the `random` module, and it reports the kappa its noise settings imply. At noise 0.3 with 3 coders and 4 categories it gives a mean human kappa of 0.49 over 200 simulated panels, close to their 0.48.

## What this does not show

These checks show the code computes the same thing as the reference. They say nothing about whether the alt-test is the right test for a given study. That judgement, and especially the choice of epsilon, stays with the researcher.
