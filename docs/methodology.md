# Methodology (short version)

A human and the AI look at each distractor and pick a category. Neither can see the other's answer while they are picking.

We measure how much they end up agreeing with Cohen's kappa:

    kappa = (Po - Pe) / (1 - Pe)

Where Po is how often they picked the same category and Pe is how often that agreement would have happened by chance alone. Cohen (1960) is the original paper.

We treat kappa >= 0.70 as the research threshold. Below that, the taxonomy is not reliable enough to build a study on, and we go back and rewrite either the definitions or the AI prompt before trying again.

The longer version, with every formula and citation, is in [`methods.md`](methods.md).
