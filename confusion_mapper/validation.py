"""
Simple data-quality checks I run before any statistic is computed.

The story here: on my very first run of a real dataset the kappa looked
strangely low. I dug in and found two rows with typos in the label
column, one row with an empty item_id, and a duplicate id. None of that
should have been kappa's problem. So this module catches those issues
and prints a warning before the number is computed, and the --strict
flag makes it hard-fail so a paper is never written on dirty data.
"""

from .taxonomy import ERROR_TYPES


def validate_dataset(rows, categories=None):
    """
    Check a list of coded-item records for the data-quality problems most
    likely to distort or crash a reliability computation.

    Args:
        rows (list[dict]): one dict per coded item, typically produced by
            csv.DictReader() over a file shaped like sample_data/
            example_labels.csv (columns: item_id, distractor_text,
            human_label, ai_label). Only human_label and ai_label are
            required keys; item_id and distractor_text are checked if
            present.
        categories (list[str] | None): the valid label set. If None, uses
            the module-level ERROR_TYPES.

    Returns:
        dict:
            valid (bool):     True iff there are zero errors. Warnings
                               alone do not fail validation.
            n_records (int)
            errors   (list[dict]): {row, item_id, issue}, would silently
                distort a kappa/AC1/alpha computation or crash a stats
                function. Examples: empty human_label, a label that isn't
                in `categories` (a typo, e.g. "CG" instead of "CF"), a
                duplicate item_id.
            warnings (list[dict]): {row, item_id, issue}, worth a look,
                won't break a computation. Examples: missing item_id
                (duplicate-checking can't cover that row), empty
                distractor_text.

    `row` is 1-indexed and matches the line a human would open the CSV to.
    """
    if categories is None:
        categories = ERROR_TYPES

    errors = []
    warnings = []
    seen_ids = {}

    for i, row in enumerate(rows):
        row_num = i + 1
        item_id = (row.get("item_id") or "").strip()

        human = (row.get("human_label") or "").strip()
        ai    = (row.get("ai_label") or "").strip()

        if not human:
            errors.append({"row": row_num, "item_id": item_id or None,
                            "issue": "human_label is missing or empty."})
        elif human not in categories:
            errors.append({"row": row_num, "item_id": item_id or None,
                            "issue": f"human_label {human!r} is not one of "
                                     f"{categories}. impossible value, "
                                     f"probably a typo."})

        if not ai:
            errors.append({"row": row_num, "item_id": item_id or None,
                            "issue": "ai_label is missing or empty."})
        elif ai not in categories:
            errors.append({"row": row_num, "item_id": item_id or None,
                            "issue": f"ai_label {ai!r} is not one of "
                                     f"{categories}. impossible value, "
                                     f"probably a typo."})

        if item_id:
            if item_id in seen_ids:
                errors.append({"row": row_num, "item_id": item_id,
                                "issue": f"duplicate item_id, first seen "
                                         f"at row {seen_ids[item_id]}."})
            else:
                seen_ids[item_id] = row_num
        else:
            warnings.append({"row": row_num, "item_id": None,
                              "issue": "item_id is missing; duplicate-ID "
                                       "checking cannot cover this row."})

        if "distractor_text" in row and not (row.get("distractor_text") or "").strip():
            warnings.append({"row": row_num, "item_id": item_id or None,
                              "issue": "distractor_text is empty."})

    return {
        "valid":     len(errors) == 0,
        "n_records": len(rows),
        "errors":    errors,
        "warnings":  warnings,
    }
