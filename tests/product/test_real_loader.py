"""F1 R3: the real loader's one entry into the market-data projection (`persistence.real_loader.load_release`; closes R4a review LOW-7).

The choice made (reported with its reasons in `reviews/ENGINEERING_SELF_VALIDATION.md`, "F1 R3"): option (a), the loader passes the identity's
`exchange_mic`, enforced structurally by a wrapper that has no way to omit it. Option (b) (`write_release` refuses a non-synthetic reading
when `exchange_of` is None) is not taken: R4a's own pinned test (`test_marketdata_listing_market_gate`, 1.16 item 27) states that omitting
`exchange_of` is the supported owner-side call and the 1.16 label describes `write_release` as shipped. Option (c), a database check, would
need the identity (the listing's market) inside the database, which the loader's grants deliberately exclude.

Pure tests here (no database: a connection stub that fails the test if touched). The PostgreSQL half is in `test_postgres_real_loader.py`.
All data is invented.
"""
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import marketdata_cp2c1_kit as k  # noqa: E402
import test_marketdata_listing_market_gate as g  # noqa: E402
from marketdata import profiles as prof  # noqa: E402
from marketdata.calendars import CalendarSet  # noqa: E402
from marketdata.manifest import MarketDataRelease  # noqa: E402
from marketdata.profiles import ProfileNotAdmittedError  # noqa: E402
from marketdata.store import StoreContents  # noqa: E402
from persistence import market_data_store as mds, real_loader  # noqa: E402


def us_labelled_cn_release():
    """A real quote on an XSHG listing under the US-labelled source: the case the listing-level gate refuses (SOURCE_MARKET_NOT_COVERED)."""
    ident = g.identity()
    cn = g.kit.listing_id(ident, "609999", "XSHG")
    m, _payload = g.manifest("alphavantage.us", "609999.SHH", k.CNY, g.CN_ROWS)
    reading = g.real_quote(cn, sha=m.file_sha256)
    release = MarketDataRelease(name="loader", files=(m.file_sha256,), source_precedence=())
    return ident, release, [m], StoreContents((reading,), (), (), (), (), False, ())


class LoaderEntryTests(unittest.TestCase):
    def test_the_identity_is_a_required_keyword_with_no_default(self):
        parameter = inspect.signature(real_loader.load_release).parameters["exchange_of"]
        self.assertIs(parameter.kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertIs(parameter.default, inspect.Parameter.empty)

    def test_no_identity_is_refused_before_any_statement(self):
        _ident, release, manifests, contents = us_labelled_cn_release()
        for bad in (None, "XSHG", 3):
            with self.subTest(bad=bad):
                with self.assertRaises(real_loader.RealLoaderError) as caught:
                    real_loader.load_release(g._NoDatabase(), release, manifests, contents, CalendarSet(), exchange_of=bad)
                self.assertEqual(caught.exception.code, real_loader.LOADER_NO_IDENTITY)
                self.assertIn("nothing is written", str(caught.exception))
        with self.assertRaises(real_loader.RealLoaderError):                    # and the same for a synthetic-only release: the rule is structural
            real_loader.load_release(g._NoDatabase(), release, manifests, StoreContents((), (), (), (), (), True, ()), CalendarSet(), exchange_of=None)

    def test_the_control_that_the_unwrapped_call_would_have_reached_the_database(self):
        """Why the wrapper exists: `write_release` with `exchange_of` omitted passes the same release to the (absent) database."""
        _ident, release, manifests, contents = us_labelled_cn_release()
        with self.assertRaises(AssertionError) as caught:
            mds.write_release(g._NoDatabase(), release, manifests, contents, CalendarSet())
        self.assertIn("the database was touched", str(caught.exception))

    def test_a_us_labelled_cn_reading_is_refused_with_the_identity_before_any_statement(self):
        ident, release, manifests, contents = us_labelled_cn_release()
        with self.assertRaises(ProfileNotAdmittedError) as caught:
            real_loader.load_release(g._NoDatabase(), release, manifests, contents, CalendarSet(), exchange_of=ident.exchange_mic)
        self.assertEqual(caught.exception.gate_code, prof.SOURCE_MARKET_NOT_COVERED)

    def test_the_wrapper_always_passes_the_identity_and_never_counts_rows(self):
        ident, release, manifests, contents = us_labelled_cn_release()
        with mock.patch.object(mds, "write_release", return_value="done") as write:
            out = real_loader.load_release("conn", release, manifests, contents, "cal", exchange_of=ident.exchange_mic)
        self.assertEqual(out, "done")
        write.assert_called_once_with("conn", release, manifests, contents, "cal", exchange_of=ident.exchange_mic, count_rows=False)

    def test_write_release_itself_is_unchanged(self):
        """R4a's pinned behaviour and the 1.16 wording stand: `exchange_of` is optional there, `count_rows` defaults to True."""
        parameters = inspect.signature(mds.write_release).parameters
        self.assertIsNone(parameters["exchange_of"].default)
        self.assertIs(parameters["count_rows"].default, True)


if __name__ == "__main__":
    unittest.main()
