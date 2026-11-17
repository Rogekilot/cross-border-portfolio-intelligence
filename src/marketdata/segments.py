"""Segments: one series delivered in several files, each date in exactly one (`market-data/1.13` Ruling 0.1 (1.12, 1.13); tech plan 17.18, 17.19).

"At most one vintage per series" is read PER DATE. Several files of one series are admitted to a release as SEGMENTS of ONE series only when all four hold; otherwise the build fails closed and nothing is picked:

1. disjoint COVERAGE: each file's declared coverage `[start, end]` (start: the requested start, or the first date the file holds; end: the earlier of the requested end and the latest date whose scheduled close or
   publication is at or before the file's retrieval time). Two files that cover a common date are two vintages of that date, EVEN WHEN every value agrees and even when one of them holds no row there ("no print"
   that became "a print" is a revision);
2. one identity: source, series key, declared static fields, synthetic flag, adjustment status and anchor;
3. a vintage-stable series: raw prices, ECB fixings, published index levels, risk-free quotes the publisher does not revise. A vendor-adjusted series is never segmented;
4. each file passes its own checks (V0 and the after-retrieval test run per file, later in the build).

The outcomes are the Quant's (`cp4_golden/1.3-part3` `release_cases`): REFUSED_IDENTITY, REFUSED_NOT_SEGMENTABLE, REFUSED_OVERLAP (checked in that order); a fourth, REFUSED_COVERAGE_UNDETERMINED, is the engineer's: a coverage that
cannot be stated cannot be shown disjoint, so a series in several files without one is refused (a single file never needs one). All four are `TwoVintagesError`s. No vintage label is part of any identity field: the
vintage of a segment is its `retrieval_time`.

This module is pure: it compares what the build hands it and never reads a clock or a file.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from marketdata.contracts import CalendarDays, CalendarKind
from marketdata.manifest import VENDOR_ADJUSTED, FileManifest, TwoVintagesError

Interval = Tuple[datetime.date, datetime.date]

REFUSED_IDENTITY = "REFUSED_IDENTITY"
REFUSED_NOT_SEGMENTABLE = "REFUSED_NOT_SEGMENTABLE"
REFUSED_OVERLAP = "REFUSED_OVERLAP"
REFUSED_COVERAGE_UNDETERMINED = "REFUSED_COVERAGE_UNDETERMINED"
REFUSED_ROW_OUTSIDE_COVERAGE = "REFUSED_ROW_OUTSIDE_COVERAGE"
REFUSED_CALENDAR_MISMATCH = "REFUSED_CALENDAR_MISMATCH"
ADMITTED = "ADMITTED"


class SegmentError(TwoVintagesError):
    """A series in several files that Ruling 0.1 (1.12) does not admit. `outcome` is one of the REFUSED_* names; `overlap` is the union span of the shared intervals for an overlap."""

    outcome = ""

    def __init__(self, key: object, message: str, overlap: Optional[Interval] = None) -> None:
        super().__init__(f"{self.outcome}: series {key}: {message}")
        self.key = key
        self.overlap = overlap


class SegmentIdentityError(SegmentError):
    outcome = REFUSED_IDENTITY


class SegmentNotSegmentableError(SegmentError):
    outcome = REFUSED_NOT_SEGMENTABLE


class SegmentOverlapError(SegmentError):
    outcome = REFUSED_OVERLAP


class SegmentCoverageUndeterminedError(SegmentError):
    outcome = REFUSED_COVERAGE_UNDETERMINED


class SegmentRowsOutsideCoverageError(SegmentError):
    """CP4M-10: a file holds a row outside the interval it states (its request, or its derived coverage when it is one of several). Such a row is a second vintage of a date another file covers, so the file is
    refused, never widened to the hull of what it holds: a file that says one thing and holds another is not admitted."""

    outcome = REFUSED_ROW_OUTSIDE_COVERAGE


class SegmentCalendarMismatchError(SegmentError):
    """CP4M-10 point 3: a segmented benchmark file declares a calendar other than its catalog entry's."""

    outcome = REFUSED_CALENDAR_MISMATCH


@dataclass(frozen=True)
class FileSegment:
    """What one file contributes to one series: the facts Ruling 0.1 (1.12) judges. `coverage` None: it cannot be stated. `identity`: sorted `(name, value)` pairs of the declared static fields (the series key's
    adjustment status and anchor and the synthetic flag among them). `segmentable`: the series is vintage-stable."""

    file_sha256: str
    retrieval_time: datetime.datetime
    coverage: Optional[Interval]
    identity: Tuple[Tuple[str, object], ...]
    segmentable: bool
    rows_outside: Tuple[datetime.date, ...] = ()  # the dates the file holds outside its stated coverage (market-data Ruling 0.1 (1.13) item 1(c))

    def __post_init__(self) -> None:
        if self.coverage is not None and self.coverage[0] > self.coverage[1]:
            raise ValueError("an empty coverage is not stated; give None or a non-empty interval")


def _differing(a: Tuple[Tuple[str, object], ...], b: Tuple[Tuple[str, object], ...]) -> List[str]:
    da, db = dict(a), dict(b)
    return sorted(k for k in set(da) | set(db) if da.get(k) != db.get(k))


def admit_segments(key: object, files: Sequence[FileSegment]) -> Tuple[FileSegment, ...]:
    """The files of one series in coverage order, or a `SegmentError`. One file is always admitted."""
    if len({f.file_sha256 for f in files}) != len(files):
        raise SegmentIdentityError(key, "one file is listed twice")
    ordered = sorted(files, key=lambda f: (f.coverage is None, f.coverage, f.retrieval_time, f.file_sha256))
    if len(ordered) <= 1:
        return tuple(ordered)
    first = ordered[0]
    for other in ordered[1:]:
        names = _differing(first.identity, other.identity)
        if names:
            raise SegmentIdentityError(key, f"files {first.file_sha256[:12]} and {other.file_sha256[:12]} differ in {', '.join(names)}: segments share one identity")
    if not all(f.segmentable for f in ordered):
        raise SegmentNotSegmentableError(key, f"{len(ordered)} files of a series that is not vintage-stable (a vendor-adjusted or revisable series is never segmented); building a release with two vintages of it is refused")
    if any(f.coverage is None for f in ordered):
        raise SegmentCoverageUndeterminedError(key, "a file's coverage cannot be stated (no requested end and no calendar to bound it), so it cannot be shown disjoint from the others")
    for f in ordered:  # (1.13 item 1(c)) after the coverage is known and before any overlap: the coverage is never widened to the hull of the rows
        if f.rows_outside:
            assert f.coverage is not None
            raise SegmentRowsOutsideCoverageError(key, f"file {f.file_sha256[:12]} states the coverage {f.coverage[0].isoformat()} to {f.coverage[1].isoformat()} but holds {len(f.rows_outside)} row(s) outside it "
                                                       f"({min(f.rows_outside).isoformat()} .. {max(f.rows_outside).isoformat()}): a file that says one thing and holds another is refused, never widened")
    shared: List[Interval] = []
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            assert a.coverage is not None and b.coverage is not None
            low, high = max(a.coverage[0], b.coverage[0]), min(a.coverage[1], b.coverage[1])
            if low <= high:
                shared.append((low, high))
    if shared:
        span = (min(s[0] for s in shared), max(s[1] for s in shared))
        raise SegmentOverlapError(key, f"{len(ordered)} files cover a common date ({span[0].isoformat()} to {span[1].isoformat()}): two vintages of those dates, refused even if their values agree", span)
    return tuple(ordered)


# --- coverage from a manifest and a calendar ----------------------------------------------------------------------------------------------------

def requested_interval(manifest: FileManifest) -> Tuple[Optional[datetime.date], Optional[datetime.date], bool]:
    """`(start, end, well_formed)`: the request's `start` (or `read_start`) and `end` (or `read_end`), as in Ruling 1.1a item 5."""
    request = dict(manifest.request)

    def iso(*keys: str) -> Optional[datetime.date]:
        for key in keys:
            text = request.get(key)
            if text:
                return datetime.date.fromisoformat(text)
        return None

    try:
        return iso("start", "read_start"), iso("end", "read_end"), True
    except ValueError:
        return None, None, False


def latest_available(calendar: Optional[CalendarDays], retrieval_time: datetime.datetime) -> Optional[datetime.date]:
    """The latest date of `calendar` whose scheduled close (an exchange calendar) or nominal publication (an ECB or rate-publication calendar) is at or before `retrieval_time`; None when there is no calendar or
    nothing was available yet. Dates beyond the calendar's own coverage are not counted (the calendar says nothing there)."""
    if calendar is None:
        return None
    zone = ZoneInfo(calendar.timezone)
    for day in reversed(calendar.dates):  # availability instants increase with the date, so the first one found from the end is the latest
        at = calendar.close_time(day) if calendar.kind is CalendarKind.EXCHANGE_SESSIONS else calendar.publication_time
        if at is not None and datetime.datetime.combine(day, at, tzinfo=zone) <= retrieval_time:
            return day
    return None


#: payload formats that deliver a publisher's WHOLE history in one file (market-data Ruling 1.1a item 5: the ECB `eurofxref-hist` file). A file is also full-history when its request says so (`full_history` = `true`).
FULL_HISTORY_FORMATS = ("ecb_eurofxref_hist_csv/1",)


def is_full_history(manifest: FileManifest) -> bool:
    return manifest.payload_format in FULL_HISTORY_FORMATS or dict(manifest.request).get("full_history") == "true"


def declared_coverage(manifest: FileManifest, calendar: Optional[CalendarDays], held: Iterable[datetime.date]) -> Optional[Interval]:
    """Ruling 0.1 (1.12, 1.13) item 1: `start` is the requested start; ONLY a full-history file, which has no requested start, takes the first date it holds (1.13: a file whose coverage the content would define
    is `REFUSED_COVERAGE_UNDETERMINED`); `end` is the earlier of the requested end and the latest date available by the retrieval time. With a bound on one side only the bound is used (a superset of the true
    interval: disjointness shown with it is sound); with no start and not full-history, or no end bound at all, None. An empty coverage is None."""
    start, end, well_formed = requested_interval(manifest)
    if not well_formed:
        return None
    held = sorted(held)
    if start is None:
        if not held or not is_full_history(manifest):
            return None
        start = held[0]
    available = latest_available(calendar, manifest.retrieval_time)
    if end is None:
        end = available
    elif available is not None:
        end = min(end, available)
    if end is None or end < start:
        return None
    return (start, end)


# --- rows inside the declared request (CP4M-10) -------------------------------------------------------------------------------------------------

def declared_request(manifest: FileManifest) -> Tuple[Optional[datetime.date], Optional[datetime.date]]:
    """The window a file says it REQUESTED: its `start` and `end` (either may be absent). `read_start` and `read_end` are not a request: they say which window of a full-history file a human READ (market-data
    Ruling 1.1a item 5), and such a file legitimately holds rows outside it. A malformed date states nothing."""
    request = dict(manifest.request)
    try:
        return (datetime.date.fromisoformat(request["start"]) if request.get("start") else None,
                datetime.date.fromisoformat(request["end"]) if request.get("end") else None)
    except ValueError:
        return None, None


def file_dates_of(readings: Iterable[object], benchmarks: Iterable[object], adjusted: Iterable[object], risk_free: Iterable[object]) -> Dict[str, List[datetime.date]]:
    """The dates each file holds rows for, over every kind the rule covers (prices, FX, benchmark levels, risk-free quotes, adjusted quotes). Corporate actions are dated by their ex-date, not by a series, and are not
    covered by a request window."""
    from marketdata.contracts import FXObservation, QuoteObservation  # noqa: PLC0415

    out: Dict[str, List[datetime.date]] = {}
    for r in readings:
        if isinstance(r.observation, (QuoteObservation, FXObservation)):  # type: ignore[attr-defined]
            out.setdefault(r.file_sha256, []).append(r.observation.value_date)  # type: ignore[attr-defined]
    for b in benchmarks:
        out.setdefault(b.file_sha256, []).extend(p.value_date for p in b.series.points)  # type: ignore[attr-defined]
    for rf in risk_free:
        out.setdefault(rf.file_sha256, []).extend(p.value_date for p in rf.series.points)  # type: ignore[attr-defined]
    for a in adjusted:
        out.setdefault(a.lineage.file_sha256 or "", []).append(a.value_date)  # type: ignore[attr-defined]
    return out


def require_rows_inside_request(dates_by_file: Dict[str, List[datetime.date]], manifests: Dict[str, FileManifest]) -> None:
    """A file of a series in SEVERAL files that declares a request `start` and/or `end` holds no row before the start or after the end (market-data Ruling 0.1 (1.13) item 1(c); a single-file series is unchanged, its
    rows are judged by Ruling 3.1). The PostgreSQL projection calls this calendar-free subset of the build's check, so a file that says one thing and holds another is in no stored release; the build itself judges the
    full coverage (including the derived end) inside `admit_segments`."""
    groups: Dict[Tuple[str, ...], set] = {}
    for sha, manifest in manifests.items():
        for key in manifest.series_keys():
            groups.setdefault(key, set()).add(sha)
    several = {sha for members in groups.values() if len(members) > 1 for sha in members}
    for sha in sorted(dates_by_file):
        manifest = manifests.get(sha)
        if manifest is None or sha not in several:
            continue
        start, end = declared_request(manifest)
        if start is None and end is None:
            continue
        outside = sorted({d for d in dates_by_file[sha] if (start is not None and d < start) or (end is not None and d > end)})
        if outside:
            raise SegmentRowsOutsideCoverageError(
                (manifest.source_id, manifest.data_kind.value, sha[:12]),
                f"the file declares the request {None if start is None else start.isoformat()} to {None if end is None else end.isoformat()} but holds {len(outside)} row(s) outside it "
                f"({outside[0].isoformat()} .. {outside[-1].isoformat()}): refused, never widened to what it holds")


# --- the manifest-level proof (before any file is read) ------------------------------------------------------------------------------------------

#: manifests of these kinds can never be segmented: calendars are one version per id, identities and corporate actions are not in the list of vintage-stable series of Ruling 0.1 (1.12)
NOT_SEGMENTABLE_KINDS = ("CORPORATE_ACTION", "IDENTITY", "CALENDAR")


def manifest_level_check(key: object, manifests: Sequence[FileManifest]) -> None:
    """What the manifests ALONE can show, with no calendar and no row: several files of one series key are admitted only when the series is of a segmentable kind and every file DECLARES its request interval
    (`start` and `end`) and the declared intervals are pairwise disjoint (the coverage is inside the declared interval, so disjoint declarations make disjoint coverage). Otherwise the manifests prove nothing and the
    release is refused; the build repeats the exact check of Ruling 0.1 (1.12) on the loaded rows and calendars for every release, however it was cut."""
    if len({m.file_sha256 for m in manifests}) <= 1:
        return
    first = manifests[0]
    for other in manifests[1:]:  # identity first (the Quant's order): what a manifest declares about the series
        names = [n for n in ("usage_scope", "adjustment_anchor", "declared_adjustment", "declared_currency", "declared_delay", "market") if getattr(first, n) != getattr(other, n)]
        if names:
            raise SegmentIdentityError(key, f"files {first.file_sha256[:12]} and {other.file_sha256[:12]} differ in {', '.join(names)}: segments share one identity (the synthetic flag is the usage scope)")
    if any(m.data_kind.value in NOT_SEGMENTABLE_KINDS for m in manifests):
        raise SegmentNotSegmentableError(key, "several files of a series of a kind that is never segmented")
    if any(m.declared_adjustment in VENDOR_ADJUSTED for m in manifests):
        raise SegmentNotSegmentableError(key, "several files of a vendor-adjusted series (never segmented)")
    intervals: Dict[str, Interval] = {}
    for m in manifests:
        start, end, well_formed = requested_interval(m)
        if not well_formed or start is None or end is None or end < start:
            raise SegmentCoverageUndeterminedError(key, f"file {m.file_sha256[:12]} does not declare a request start and end: the manifests cannot show its coverage disjoint from the others")
        intervals[m.file_sha256] = (start, end)
    shas = sorted(intervals, key=lambda s: intervals[s])
    for a, b in zip(shas, shas[1:]):
        if intervals[b][0] <= intervals[a][1]:
            raise SegmentOverlapError(key, f"files {a[:12]} and {b[:12]} declare requests that share a date: two vintages, refused even if their values agree", (intervals[b][0], min(intervals[a][1], intervals[b][1])))
