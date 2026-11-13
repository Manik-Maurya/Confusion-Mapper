# Statistical methods reference

Every formula ConfusionMapper computes is listed here with the original source. Use this page to verify the implementation against the literature or to cite the underlying methods in a research paper.

## Cohen's kappa (nominal)

For two raters and a set of mutually exclusive categories, the nominal kappa is

    kappa = (Po - Pe) / (1 - Pe)

where Po is the observed proportion of agreement and Pe is the proportion expected by chance under independent marginals. Reference: Cohen (1960).

ConfusionMapper guards the degenerate Pe = 1 case (both raters unanimously choose the same single category) by returning kappa = 1 when Po = 1, in line with the standard convention.

## Weighted kappa

For ordinal taxonomies the formula generalises to

    kappa_w = 1 - (sum_ij w_ij * o_ij) / (sum_ij w_ij * e_ij)

where o_ij and e_ij are the observed and expected counts of pairs (i, j), and w_ij is a disagreement weight. ConfusionMapper supports two weighting schemes:

- Linear weights (Cicchetti and Allison): w_ij = |i - j| / (k - 1)
- Quadratic weights (Fleiss and Cohen): w_ij = (i - j)^2 / (k - 1)^2

The quadratic-weighted kappa is equivalent to the intraclass correlation coefficient under certain conditions.

## Landis and Koch interpretation

Cohen's kappa is interpreted via the qualitative bands proposed in Landis and Koch (1977):

| kappa range | Interpretation |
|---|---|
| < 0.20 | Slight |
| 0.20 to 0.40 | Fair |
| 0.40 to 0.60 | Moderate |
| 0.60 to 0.80 | Substantial |
| 0.80 to 1.00 | Almost perfect |

ConfusionMapper's research threshold of kappa >= 0.70 sits inside the substantial band.

## PABAK, bias index, prevalence index

When marginals are highly skewed, the standard kappa can be paradoxically low even when raters agree on most items. The prevalence-adjusted bias-adjusted kappa is

    PABAK = 2 * Po - 1

The bias index is the average absolute difference between the two raters' marginal proportions across categories, normalised to lie in [0, 1]. The prevalence index is the maximum, over categories, of |2 * p_pos - 1| where p_pos is the proportion of items both raters placed in that category. Reference: Byrt, Bishop and Carlin (1993).

## BCa bootstrap confidence interval

ConfusionMapper reports a 95% confidence interval for kappa using either the percentile bootstrap or the bias-corrected and accelerated (BCa) bootstrap of Efron (1987). For B resamples (default B = 10,000) drawn with replacement from the paired (human, AI) tuples, the BCa interval adjusts the percentile endpoints with a bias-correction term z0 derived from the bootstrap distribution and an acceleration term a derived from the leave-one-out jackknife. The seed parameter fixes the resampling order so reported intervals are reproducible bit-for-bit.

## Krippendorff's alpha

Alpha generalises kappa-style agreement to any number of raters, supports missing values, and admits three measurement levels:

- Nominal: delta(i, j) = 0 if i = j else 1
- Ordinal: delta(i, j) = ((|i - j|) / (k - 1))^2
- Interval: delta(i, j) = ((|i - j|) / (k - 1))^2 with numeric distances

The coefficient is

    alpha = 1 - (Dobs / Dexp)

where Dobs is the mean observed disagreement over rater pairs and Dexp is the mean expected disagreement under the full pool of labels. Reference: Krippendorff (2018).

## Fleiss's kappa for 3 or more raters

For r raters and n items the per-item agreement is

    P_i = sum_j (n_ij * (n_ij - 1)) / (r * (r - 1))

where n_ij is the number of raters who placed item i in category j. The overall agreement is the mean of P_i across items; the expected agreement is sum_j p_j^2 where p_j is the marginal proportion of category j. Fleiss kappa is then (P_bar - Pe) / (1 - Pe). Reference: Fleiss (1971).

## Sample-size estimator

Given an expected kappa, a target 95% CI half-width, and a number of categories k, the required calibration set size N is approximated under balanced marginals as

    Var(kappa) ~= Po * (1 - Po) / (1 - Pe)^2,  Pe = 1 / k,  Po = kappa * (1 - Pe) + Pe
    N >= ceil(z_alpha^2 * Var(kappa) / h^2)

where z_alpha is the standard normal critical value and h is the requested half-width. Reference: Donner and Eliasziw (1992).

## Prompt-refinement engine

The suggest_prompt_refinements function ranks the off-diagonal cells of the confusion matrix by count and emits a Markdown report that names each largest disagreement, reads the corresponding category definitions from the taxonomy, and proposes a contrastive instruction the researcher can paste into their AI prompt. The suggestions are deterministic given the same input.

## Alternative Annotator Test (can the AI replace a human coder?)

Implemented in `alttest.py`, following Calderon, Reichart and Dror (2025) and their reference notebook. For n items, m human coders h_1 to h_m and an AI f, let H_i be the coders who labelled item i and I_j the items coder j labelled. For every coder j and item i in I_j, compare the AI and coder j against the *other* coders on that item with an alignment score S:

    ACC(f, i, j)   = (1 / (|H_i| - 1)) * sum over k in H_i, k != j of 1{ f(x_i) = h_k(x_i) }
    -RMSE(f, i, j) = -sqrt( (1 / (|H_i| - 1)) * sum over k in H_i, k != j of (f(x_i) - h_k(x_i))^2 )

and the same with h_j in place of f. Then

    W_f(i, j) = 1 if S(f, i, j) >= S(h_j, i, j) else 0
    W_h(i, j) = 1 if S(h_j, i, j) >= S(f, i, j) else 0     (a tie counts for both)
    rho_f(j)  = mean of W_f over I_j,   rho_h(j) = mean of W_h over I_j

For each coder, a one-sided one-sample t-test on d_i = W_h - W_f:

    H0: rho_f(j) <= rho_h(j) - epsilon    vs    H1: rho_f(j) > rho_h(j) - epsilon
    t_j = (mean(d) - epsilon) / (s_d / sqrt(n_j)),   p_j = P(T_(n_j - 1) <= t_j)

The m p-values are corrected with the Benjamini-Yekutieli procedure at level q (default 0.05). The winning rate is the share of coders whose null was rejected, and the AI passes if it is at least 0.5. The advantage probability is the mean of rho_f over coders. Items with fewer than 2 human labels, and coders with fewer than 30 usable items, are left out, as in the reference code.

The Student's t CDF is computed through the regularized incomplete beta function, P(T <= t) = 1 - I_x(df/2, 1/2) / 2 for t >= 0 with x = df / (df + t^2), using the modified Lentz continued fraction. When the standard deviation of d is zero the p-value is taken as its limit: 0 if mean(d) < epsilon, otherwise 1.

Benjamini-Yekutieli: sort the p-values, find the largest k with p_(k) <= (k / m) * q / (1 + 1/2 + ... + 1/m), and reject the k smallest.

### Bootstrap robustness check (ConfusionMapper's addition)

Not part of the authors' procedure. `bootstrap_alt_test` draws B resamples of the items with replacement (each resample has as many draws as there are items, and a repeated item gets its own key), keeps every coder's label and the AI's label for each draw, and reruns the full alt-test, Benjamini-Yekutieli included. It reports the share of resamples that reach the same verdict as the real data, the percentile interval of the advantage probability (indices floor(B * alpha / 2) and ceil(B * (1 - alpha / 2)) - 1 of the sorted values, the same convention as `bootstrap_kappa_ci`), and how often each coder was beaten. Resamples in which no coder has enough items count as not passing. The verdict-held share is not a p-value and not power.

### Preregistration lock

`create_prereg` stores the decisions that determine the verdict (epsilon and its source, q, scoring function, both minimums, pass threshold, AI and human column names, planned item count) in a "locked" block, and records SHA-256 of that block serialised as JSON with sorted keys and no whitespace. `load_prereg` recomputes the hash and refuses a file whose locked block no longer matches it. `check_against_prereg` reports any locked setting or column set that differs from the run as a deviation, and a different item count as a note. The creation date and free-text notes are deliberately outside the hash.

### Power simulator

The power simulator (`simulate_alt_test_power`) follows the authors' appendix C: a label prior drawn from a flat Dirichlet, a true label per item from that prior, and each coder (and the AI) reporting the true label with probability 1 - noise, otherwise a draw from the prior.

## Item analysis of classroom answers

Implemented in `itemanalysis.py`. Each child's answers are scored with the same rules as the class report (blank is zero, a row with no answers at all is skipped as absent), giving a students by items matrix of points.

Difficulty of item j is the mean score divided by the item's maximum points. The corrected item-total correlation is the Pearson correlation between the item score and the total score minus that item. For the upper-lower index, students are sorted by total score (ties broken by the order they were entered) and the bottom and top round(0.27 n) students form the two groups (Kelley, 1939); D is the mean item score of the upper group minus that of the lower group, divided by the maximum points. D is read with Ebel's rule of thumb: .40 and above very good, .30 to .39 reasonably good, .20 to .29 marginal, below .20 poor (Ebel, 1972).

For a multiple-choice item, each option's share is the proportion of all students who chose it, and the same proportion within the upper and lower groups. A distractor chosen by fewer than 5% of students is non-functioning (Haladyna and Downing, 1993). A distractor chosen more often by the upper group than the lower group, or an item with negative D or negative corrected correlation, is flagged for review.

Reliability is Cronbach's alpha, k / (k - 1) * (1 - sum of item variances / variance of total scores), with population variances throughout. For right/wrong items it equals KR-20, which the tests check on random matrices.

## Comparing two rounds

`compare_rounds` matches questions across two scored sets by unit template and question position. For every CFI type seen on a shared question in either round, it reports the number of answering students who made that mistake and the rate, count divided by the number who answered that question. It also reports diagnosed errors per child by type for each round. Questions present in only one round are left out.

## References

- Benjamini, Y. and Yekutieli, D. (2001). The control of the false discovery rate in multiple testing under dependency. Annals of Statistics, 29(4), 1165-1188.
- Cronbach, L. J. (1951). Coefficient alpha and the internal structure of tests. Psychometrika, 16(3), 297-334.
- Ebel, R. L. (1972). Essentials of Educational Measurement. Prentice-Hall.
- Haladyna, T. M. and Downing, S. M. (1993). How many options is enough for a multiple-choice test item? Educational and Psychological Measurement, 53(4), 999-1010.
- Kelley, T. L. (1939). The selection of upper and lower groups for the validation of test items. Journal of Educational Psychology, 30(1), 17-24.
- Calderon, N., Reichart, R. and Dror, R. (2025). The Alternative Annotator Test for LLM-as-a-Judge: How to Statistically Justify Replacing Human Annotators with LLMs. Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers), 16051-16081.

- Byrt, T., Bishop, J. and Carlin, J. B. (1993). Bias, Prevalence and Kappa. Journal of Clinical Epidemiology, 46(5), 423-429.
- Cohen, J. (1960). A coefficient of agreement for nominal scales. Educational and Psychological Measurement, 20(1), 37-46.
- Donner, A. and Eliasziw, M. (1992). A goodness-of-fit approach to inference procedures for the kappa statistic. Statistics in Medicine, 11(11), 1511-1519.
- Efron, B. (1987). Better Bootstrap Confidence Intervals. Journal of the American Statistical Association, 82(397), 171-185.
- Fleiss, J. L. (1971). Measuring nominal scale agreement among many raters. Psychological Bulletin, 76(5), 378-382.
- Krippendorff, K. (2018). Content Analysis: An Introduction to Its Methodology (4th ed.). SAGE Publications.
- Landis, J. R. and Koch, G. G. (1977). The measurement of observer agreement for categorical data. Biometrics, 33(1), 159-174.
