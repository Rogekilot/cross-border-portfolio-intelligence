"""The one switch for tests that read human-downloaded vendor payloads (`data/marketdata/files/`).

That folder is gitignored (PD-0027/PD-0028, internal use only) and exists only on the owner's Mac. A cloud run, where the payloads are absent BY DESIGN, sets

    FINWEB_NO_VENDOR_FILES=1

and exactly the tests decorated with `needs_vendor_files` skip, with the reason below. With the flag unset (the Mac's default) the decorator does nothing: a missing payload is
still an error. There is deliberately no "skip if the file is missing" logic anywhere. Which tests are gated is pinned by `test_vendor_files_flag`; adding one is a reviewed
change to that pin. The pin also refuses any other reference to the flag or to this module in the test tree, and compares the skip marks of a flag-set and a flag-unset load
of the whole suite, so the gate cannot grow by another spelling.

Known narrowing (recorded, not gated; review TVF-L3). `test_performance_cp4_part_a2.CalendarCheckTests` scans `data/marketdata/**` for calendar documents, `files/` included.
Its assertions need only the four tracked drafts (at least four documents; the NYSE, ECB, HKEX and CN-A draft names), so it passes without the payloads and without the
registered calendar files. A cloud run therefore checks a narrower set than the owner's Mac does for that one test, and the Mac does not error if the registered calendar files
are moved. The manual calendar files are not vendor payloads, so the test is left ungated.
"""

import os
import unittest
from typing import Mapping, Optional

FLAG = "FINWEB_NO_VENDOR_FILES"
REASON = f"vendor payloads absent by design ({FLAG}=1; PD-0027/PD-0028)"


def vendor_files_absent(env: Optional[Mapping[str, str]] = None) -> bool:
    """True only when the flag is exactly "1". Anything else (unset, "0", "", "true") leaves every test running."""
    return (os.environ if env is None else env).get(FLAG) == "1"


needs_vendor_files = unittest.skipIf(vendor_files_absent(), REASON)
