# Does the local embedding backend capture real signal? An empirical check

*Manik Maurya, ConfusionMapper v2.6.0, August 2026*

## Why this exists

`embeddings.py` ships two backends for the semantic-search and clustering
features: OpenAI's `text-embedding-3-small` (real embeddings, needs an API
key and network access) and a from-scratch, pure-stdlib hashed
bag-of-words vector (zero cost, zero dependencies, documented in the
module as "a weaker fallback, not presented as equivalent to real
embeddings"). That line was a judgment call, not a measurement. This is
the measurement.

## Method

[Adjusted Rand Index](https://en.wikipedia.org/wiki/Rand_index#Adjusted_Rand_index)
(Hubert & Arabie, 1985) between the local backend's cluster assignments
and each dataset's real, independently-assigned `human_label` column, at
five similarity thresholds, on the two labeled datasets already in this
repository: `sample_data/example_labels.csv` (n=30, CFI taxonomy) and
`sample_data/item_bank_demo.csv` (n=16, distractor-functioning taxonomy).
ARI is chance-corrected by construction -- 0.0 is what a random labeling
scores in expectation, 1.0 is a perfect match -- so it needs no separate
random baseline. Implementation and a hand-derived worked example (ARI on
a synthetic 6-item case, verified by hand arithmetic before being checked
against the code) are in `ari.py`.

This is not a claim that high ARI is the right goal for the discovery
workflow specifically -- `discovery.py`'s entire premise is that *low*
cluster/label purity is often the interesting signal (a candidate
taxonomy gap), not a failure. This is a narrower, prior question: does
the embedding capture real content similarity at all, well enough to be
worth using as clustering input in the first place.

## Results

| Dataset | Best ARI | At threshold | n |
|---|---|---|---|
| `example_labels.csv` | 0.0061 | 0.40 | 30 |
| `item_bank_demo.csv` | 0.0484 | 0.15 | 16 |

Full threshold sweep in `embedding_validation_study.py`'s output. Every
value is at or near zero. **The local backend's clusters do not recover
the human-assigned taxonomy labels on either dataset, at any threshold
tested.**

## Why, and what it actually means

Before concluding the embeddings are useless, look at what the labels
actually track:

```
PK  Q1_A Q2_C Q3_B Q3_D Q4_B Q5_A Q6_B Q7_A Q8_A
CF  Q1_B Q2_B Q3_A Q4_A Q5_B Q6_A Q7_B Q8_B
INT Q1_C Q2_A Q4_C Q5_D Q6_D Q7_D
RF  Q1_D Q2_D Q3_C Q4_D Q5_C Q6_C Q7_C
```

Every label spans items from nearly every question (topic) in the
dataset, while the four distractors *within* one question (`Q1_A`
through `Q1_D`) -- which share a topic and often overlapping vocabulary --
carry four different labels. By construction, in this taxonomy, **topical
similarity and cognitive-error-type are close to orthogonal**: an RF
answer about mitochondria and an RF answer about Newton's laws share
almost no vocabulary, while a CF and an RF answer to the *same* question
often share plenty. A bag-of-words backend -- and very plausibly a real
embedding model too, since both are fundamentally content/topic
detectors -- has no obvious reason to recover a label that is about *how*
a student got an answer wrong, not *what the answer is about*.

This reframes the finding rather than just softening it: clustering-based
discovery is well-suited to finding groups of semantically similar wrong
answers that a taxonomy's existing categories disagree about (its actual
design target), and there's no strong reason from this data to expect it
to reconstruct cognitive-process categories like RF/PK/CF/INT from
content alone -- a genuinely different task. A study that found *high*
ARI here would arguably be more suspicious, not less: it would suggest
the taxonomy is really just topic-clustering in disguise, which is not
what CFI (or the item-bank taxonomy) is supposed to be measuring.

## Real limitations, not hedging

- **n=30 and n=16 are small.** ARI is known to be noisy at this scale; a
  single reclassified item measurably moves the number. These are the
  labeled datasets that happen to ship with the package, not a
  purpose-built benchmark. Treat every value above as a rough estimate,
  not a precise one.
- **This tests the local backend only.** Whether OpenAI's real embeddings
  do meaningfully better is a real, currently unanswered question --
  `benchmark_embeddings.py` runs the identical methodology against the
  `openai` backend and is ready to go; it hasn't been run because doing
  so needs an API key and network access neither available in the
  environment this was written in. **Nobody has run the OpenAI half of
  this comparison yet.** Run it, and this table gains a second column
  that could change the interpretation.
- **This doesn't test the actual discovery use case end-to-end** -- i.e.,
  whether clusters flagged by `discover` (low purity, not high) correspond
  to real taxonomy gaps a domain expert would agree are real. That needs
  human judgment on real candidate proposals, not a label-recovery metric.

## What would make this a stronger study

1. Run `benchmark_embeddings.py` with a real `OPENAI_API_KEY` and report
   the second column honestly, whichever way it comes out.
2. A held-out set of item pairs a human explicitly judged "same
   underlying misconception" / "different," independent of the four-label
   taxonomy -- a more direct test of what semantic search is actually for.
3. Run this on the real RCT dataset once it exists (n~90 respondents x
   several items each) instead of the two small bundled samples.

## Files

- `ari.py` -- Adjusted Rand Index, from scratch, with the hand-derived
  worked example that was checked before being trusted.
- `embedding_validation_study.py` -- the local-only study reported above,
  fully run, real numbers.
- `benchmark_embeddings.py` -- the local-vs-OpenAI harness, same
  methodology, ready to run, not yet run.
