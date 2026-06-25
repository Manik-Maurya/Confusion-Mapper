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

## References

- Byrt, T., Bishop, J. and Carlin, J. B. (1993). Bias, Prevalence and Kappa. Journal of Clinical Epidemiology, 46(5), 423-429.
- Cohen, J. (1960). A coefficient of agreement for nominal scales. Educational and Psychological Measurement, 20(1), 37-46.
- Donner, A. and Eliasziw, M. (1992). A goodness-of-fit approach to inference procedures for the kappa statistic. Statistics in Medicine, 11(11), 1511-1519.
- Efron, B. (1987). Better Bootstrap Confidence Intervals. Journal of the American Statistical Association, 82(397), 171-185.
- Fleiss, J. L. (1971). Measuring nominal scale agreement among many raters. Psychological Bulletin, 76(5), 378-382.
- Krippendorff, K. (2018). Content Analysis: An Introduction to Its Methodology (4th ed.). SAGE Publications.
- Landis, J. R. and Koch, G. G. (1977). The measurement of observer agreement for categorical data. Biometrics, 33(1), 159-174.
