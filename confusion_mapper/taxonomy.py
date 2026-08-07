"""
Constants and the Confusion Fingerprint Index (CFI) taxonomy definition.

APP_VERSION, DATA_FILE, ERROR_TYPES, and TAXONOMY were moved unmodified from
the "SECTION 1, CONSTANTS & TAXONOMY DEFINITIONS" block of the pre-2.6.0
single-file confusion_mapper.py during the v2.6.0 package reorganization --
none of those values changed. taxonomy_fingerprint() and ASSIST_DATA_FILE
are new in this release: the former supports session provenance (see
storage.py / console.py), the latter keeps assist-mode sessions (see
assist.py) in a file of their own, never mixed with DATA_FILE, the file the
blind reliability-check session (console.py's run_session()) reads and
writes.
"""

import hashlib
import json

APP_VERSION       = "1.0"
DATA_FILE         = "confusion_mapper_sessions.json"
ASSIST_DATA_FILE  = "confusion_mapper_assist_sessions.json"
ERROR_TYPES       = ["RF", "PK", "CF", "INT"]

# Full taxonomy, used for on-screen reference and ChatGPT prompting
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
    A short, stable identifier for the exact TAXONOMY definitions currently
    in effect. New in v2.6.0.

    Not a security hash -- a change detector. Two sessions with the same
    fingerprint were coded under byte-identical category definitions; two
    sessions with different fingerprints were not, even if neither person
    remembers editing TAXONOMY in between. sha256 of a deterministic JSON
    serialization of TAXONOMY (sorted keys), first 12 hex characters --
    long enough that an accidental collision between two genuinely
    different taxonomies is not a practical concern for this use case.
    """
    canonical = json.dumps(TAXONOMY, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
