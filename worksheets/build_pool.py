"""
Rebuilds the unit pool inside worksheets/index.html.

The page never computes an answer itself. It carries a fixed pool of units
made by confusion_mapper.pisa, so the Python templates stay the only place
an answer is worked out, and the tests that recompute every answer cover
the page as well. Run this after changing a template:

    python worksheets/build_pool.py

tests/test_worksheets.py fails if the page and the generator ever disagree.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from confusion_mapper.pisa import web_pool_json  # noqa: E402

PAGE = os.path.join(HERE, "index.html")
POOL_TAG = re.compile(r'(<script id="cm-pool" type="application/json">)(.*?)(</script>)', re.S)


def main():
    with open(PAGE, encoding="utf-8") as f:
        html = f.read()
    if len(POOL_TAG.findall(html)) != 1:
        sys.exit("could not find exactly one cm-pool script tag in index.html")
    pool = web_pool_json()
    html = POOL_TAG.sub(lambda m: m.group(1) + pool + m.group(3), html)
    with open(PAGE, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    print(f"wrote {len(pool.encode('utf-8')) // 1024} KB of units into {os.path.relpath(PAGE)}")


if __name__ == "__main__":
    main()
