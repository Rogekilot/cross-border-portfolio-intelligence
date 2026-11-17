"""`tests/product` — I4 tests for the CP0 product contract (`src/product_contract/`).

Each test module in this package inserts `src/` onto `sys.path` for itself at
import time (see the top of any `test_*.py` in this directory) rather than
relying on this `__init__.py` to do it once. That duplication is deliberate:
`unittest discover` only imports a directory's `__init__.py` as a package when
the discovery start directory is *above* this one (e.g. the repository's
canonical `python3 -m unittest discover -s tests -p 'test_*.py'`, run by
`scripts/self_test.py`). When this directory is itself the start directory
(e.g. `python3 -m unittest discover -s tests/product`), `unittest` treats its
modules as flat top-level modules and never executes this file at all — a
guarantee this package cannot rely on, confirmed by running both invocations
(see `reviews/TECH_REVIEW.md` B-3 and this task's handoff for both transcripts).
"""
