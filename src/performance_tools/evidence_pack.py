"""The evidence-pack command line (human/CI; never imported by product code).

    PYTHONPATH=src python -m performance_tools.evidence_pack synthetic --out DIR
    PYTHONPATH=src python -m performance_tools.evidence_pack real --out DIR [--data data/marketdata]

`synthetic` builds Demonstration A (fully synthetic, labelled). `real` builds Demonstration B from the admitted real files on disk; if there is no real price file, or it needs calendars that are not
registered, it says so in `REAL_SLICE_REPORT.json` and in the summary (it never fabricates). Neither reads the network, the clock or the environment. Output is deterministic.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from performance_tools import pack, real_slice, synthetic


def run_synthetic(out: Path) -> int:
    subject, market = synthetic.build_synthetic_subject()
    try:
        result = pack.build_pack(subject, out)
    finally:
        market.close()
    print(f"evidence pack written to {out} ({len(result['files'])} files); summary: {out / 'SUMMARY.md'}")
    return 0


def run_real(out: Path, data: Path, exclude: Sequence[str] = (), only: Sequence[str] = ()) -> int:
    out.mkdir(parents=True, exist_ok=True)
    subject, report = real_slice.build_real_subject(data, exclude=exclude, only=only)
    (out / "REAL_SLICE_REPORT.json").write_text(pack.dumps(report), encoding="utf-8")
    if subject is None:
        lines = ["# Real slice: not built", "", f"Status: **{report['status']}**.", "", "No number is shown: the real slice needs the following from the owner.", ""]
        lines += [f"- {r}" for r in report["requirements"]]
        if report.get("file_set_chosen_by_operator"):
            lines += ["", "## File set chosen by the operator", "", json.dumps(pack.enc(report["file_set_chosen_by_operator"]), indent=1, sort_keys=True)]
        lines += ["", "Files on disk and why each is or is not admitted are in `REAL_SLICE_REPORT.json`.", ""]
        (out / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
        print(f"real slice NOT built ({report['status']}); see {out / 'SUMMARY.md'}")
        return 0
    result = pack.build_pack(subject, out)
    print(f"real-slice evidence pack written to {out} ({len(result['files'])} files); summary: {out / 'SUMMARY.md'}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="performance_tools.evidence_pack", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="mode", required=True)
    s = sub.add_parser("synthetic", help="Demonstration A: the fully synthetic cross-border portfolio")
    s.add_argument("--out", required=True)
    r = sub.add_parser("real", help="Demonstration B: the real US/ECB slice, from admitted files only")
    r.add_argument("--out", required=True)
    r.add_argument("--data", default=str(real_slice.DEFAULT_ROOT))
    r.add_argument("--exclude-file", action="append", default=[], metavar="SHA256", help="remove this file from M (repeatable): the operator's explicit choice between vintages")
    r.add_argument("--use-file", action="append", default=[], metavar="SHA256", help="M is exactly these admitted files (repeatable): the operator's explicit file set")
    args = parser.parse_args(argv)
    if args.mode == "synthetic":
        return run_synthetic(Path(args.out))
    return run_real(Path(args.out), Path(args.data), args.exclude_file, args.use_file)


if __name__ == "__main__":
    sys.exit(main())
