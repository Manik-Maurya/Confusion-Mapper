"""
Enables `python -m confusion_mapper [subcommand]`.

Replaces the old `python confusion_mapper.py [subcommand]` usage from the
pre-2.6.0 single-file layout, which is no longer possible once
confusion_mapper.py becomes a package directory of the same name.
"""

import sys

from .cli import run

if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
