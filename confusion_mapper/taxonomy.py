"""
The CFI taxonomy. Four categories: RF, PK, CF, INT.

RF is Recall Failure, the student remembers nothing.
PK is Partial Knowledge, some idea of the right region, incomplete.
CF is Confabulation, confident recall of something that is wrong.
INT is Interference, another concept overwrites the right one.

I keep the definitions here because everything else in the package
imports from this file. If the taxonomy ever needs a new category, this
is the first file to touch, and taxonomy_fingerprint() will change with
the definitions so any old sessions can be traced back to the version
they used.
"""

import hashlib
import json

APP_VERSION       = "1.0"
DATA_FILE         = "confusion_mapper_sessions.json"
ASSIST_DATA_FILE  = "confusion_mapper_assist_sessions.json"
ERROR_TYPES       = ["RF", "PK", "CF", "INT"]

# the actual definitions. Anything user-facing pulls the "definition"
# field from here so I only have to change wording in one place.
TAXONOMY = {
    "RF": {
        "name":      "Recall Failure",
        "number":    "1",
        "definition": (
            "No consolidated memory trace. The answer is random, implausible, "
            "or reflects explicit uncertainty. The student simply has no encoding."
        ),
        "example":   "Answering 'mitochondria' to a photosynthesis question, no logical link.",
        "color":     "#4a90d9",
    },
    "PK": {
        "name":      "Partial Knowledge",
        "number":    "2",
        "definition": (
            "Correct direction but incomplete model. Student is 'almost right', "
            "the concept is partially encoded. Scaffolding resolves this quickly."
        ),
        "example":   "Knowing photosynthesis needs sunlight, but not that it produces oxygen.",
        "color":     "#f5a623",
    },
    "CF": {
        "name":      "Confabulation",
        "number":    "3",
        "definition": (
            "Strong incorrect belief, a documented misconception. The student selects "
            "with moderate-to-high confidence. The wrong answer is coherent and plausible."
        ),
        "example":   "Believing plants get food from soil because 'roots absorb nutrients'.",
        "color":     "#e74c3c",
    },
    "INT": {
        "name":      "Interference",
        "number":    "4",
        "definition": (
            "Correct answer for a DIFFERENT topic. Well-encoded knowledge from Topic A "
            "fires incorrectly in response to a Topic B question."
        ),
        "example":   "Answering 'chloroplast' (correct for photosynthesis) to a cellular-respiration question.",
        "color":     "#9b59b6",
    },
}


def taxonomy_fingerprint():
    """
    Short stable id for the exact TAXONOMY dict above. Added in 2.6.0.

    Not a security hash, a change detector. If two sessions carry the same
    fingerprint, they were coded under the exact same category definitions.
    If they differ, someone edited TAXONOMY between the two runs, and the
    reviewer needs to know that before comparing kappas across the two.

    12 hex chars of sha256 over a sorted JSON dump. Plenty for this.
    """
    canonical = json.dumps(TAXONOMY, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
