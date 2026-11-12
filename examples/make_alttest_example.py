"""
Rebuilds sample_data/example_alttest.csv from scratch.

The file is synthetic. It is a made-up panel of three human coders and
two AI "prompts" labelling 81 distractors with CFI codes, generated with
the same model the alt-test power simulator uses. I made it so the
alt-test has something realistic to run on out of the box, and so anyone
can check that the file was not hand-tuned: run this script and you get
the same CSV byte for byte.

    ai_prompt_v1  a fairly reliable AI (noise 0.15)
    ai_prompt_v2  a sloppy one (noise 0.55)
    coders        noise 0.25 each, which lands around kappa 0.6

A few cells are blanked on purpose, coder_C skipped some items, to show
that the test copes with missing labels.

    python examples/make_alttest_example.py
"""

import csv
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from confusion_mapper.alttest import generate_synthetic_panel  # noqa: E402

SEED = 20261112
OUT = os.path.join(os.path.dirname(__file__), "..", "sample_data", "example_alttest.csv")


def main():
    panel = generate_synthetic_panel(
        n_items=81, n_coders=3, categories=("RF", "PK", "CF", "INT"),
        coder_noise=0.25, ai_noises=(0.15, 0.55), seed=SEED,
    )
    humans, ais = panel["humans"], panel["ais"]
    items = list(panel["gold"])

    # 27 questions x 3 distractors, named the way the RCT item bank is
    ids = {item: f"Q{q + 1:02d}_D{d + 1}" for item, (q, d) in
           zip(items, ((k // 3, k % 3) for k in range(len(items))))}

    # coder_C missed six items
    rng = random.Random(SEED)
    for item in rng.sample(items, 6):
        del humans["coder_3"][item]

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["item_id", "coder_A", "coder_B", "coder_C", "ai_prompt_v1", "ai_prompt_v2"])
        for item in items:
            w.writerow([ids[item]]
                       + [humans[c].get(item, "") for c in ("coder_1", "coder_2", "coder_3")]
                       + [ais["ai_1"][item], ais["ai_2"][item]])
    print(f"wrote {os.path.normpath(OUT)} ({len(items)} items)")


if __name__ == "__main__":
    main()
