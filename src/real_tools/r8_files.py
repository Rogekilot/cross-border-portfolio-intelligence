"""F1 R8: the OFFLINE writers of the two input files that no other tool writes (install plan section 14, G7 and G9).

    python -m real_tools.r8_files evidence --alphavantage-pd PD-NNNN --alphavantage-commit GIT40 --alphavantage-sha DOC64 \\
        --openfigi-pd ... --openfigi-commit ... --openfigi-sha ... --calendar-pd ... --calendar-commit ... --calendar-sha ... --out E
    python -m real_tools.r8_files contexts --store-root DIR --release-name NAME --file SHA (repeat) [--sidecar PATH (repeat)] [--registered-check SHA (repeat)] \\
        --proposal P --generation N --out C

THIS TOOL OPENS NO CONNECTION AND TAKES NO PASSWORD, writes one NEW file (exclusive create: an existing file is never overwritten) and publishes nothing.

  * `evidence` writes the publish's expiry-evidence file `E` (`real_workspace_store publish --evidence-file E`), per PD-0068 answer 4: `LEASE_TERM` for `alphavantage.us` with
    `term_end_not_after` 2027-10-01T00:00:00Z, `NOT_ASSESSED` for `calendar.manual` and `openfigi`. EACH entry cites its OWN decision, given by its three options (a PD id, the 40-hex git
    commit that holds it, the 64-hex SHA-256 of that file at that commit): the owner's records, which this tool cannot know and does not check. Which record each
    entry cites is for the owner and the PM (the design names PD-0066 decision 5 for `alphavantage.us` and no record for the two `NOT_ASSESSED` entries).
    The publish's OWN decision record is a different record, given to `publish` as its own `--pd --commit --sha`.
  * `contexts` writes the launcher's contexts file `C` (`web_api.real_launcher --contexts-file C`, schema `finweb.real_mode_contexts/1`), mode 0600. It rebuilds the
    qualification from INPUTS (the same build as `qualify_run`) and refuses unless its proposal bytes equal `--proposal`, so `C` names the reviewed context. The one
    input it cannot know offline is `--generation`: the number the PUBLISH printed ("published context ... at generation N"), copied by the owner. The file holds the
    context id, that generation, and the BOUND candidate's context digest and members (no witness: v1 manifests carry none).

Exit status: 0 done, 2 refused (nothing was written).
"""
from __future__ import annotations

import sys

from real_tools import real_inputs

EXIT_DONE, EXIT_REFUSED = 0, 2
#: The option prefix of each evidence entry's decision triple (`--alphavantage-pd`, `--openfigi-commit`, `--calendar-sha`, ...).
SOURCE_PREFIXES = (("alphavantage", "alphavantage.us"), ("openfigi", "openfigi"), ("calendar", "calendar.manual"))


def _build_parser():
    import argparse
    parser = argparse.ArgumentParser(prog="r8_files", description="Offline writers of the publish evidence file and the launcher's contexts file.")
    sub = parser.add_subparsers(dest="command", required=True)
    ev = sub.add_parser("evidence")
    for prefix, source in SOURCE_PREFIXES:
        ev.add_argument("--%s-pd" % prefix, required=True, help="the PD id of the record %s's entry cites" % source)
        ev.add_argument("--%s-commit" % prefix, required=True, help="the 40-hex git commit that holds it")
        ev.add_argument("--%s-sha" % prefix, required=True, help="the 64-hex SHA-256 of that file at that commit")
    ev.add_argument("--out", required=True)
    cx = sub.add_parser("contexts")
    cx.add_argument("--store-root", required=True)
    cx.add_argument("--release-name", required=True)
    cx.add_argument("--file", action="append", required=True)
    cx.add_argument("--sidecar", action="append")
    cx.add_argument("--registered-check", action="append")
    cx.add_argument("--proposal", required=True)
    cx.add_argument("--generation", type=int, required=True, help="the generation the publish printed")
    cx.add_argument("--out", required=True)
    return parser


def main(argv=None, *, out=None, build=None):
    """`build(args)` returns a `real_inputs.Rebuilt` (the tests' seam; the default is the REAL scope)."""
    args = _build_parser().parse_args(argv)
    say = (lambda text: print(text, file=out)) if out is not None else print
    try:
        real_inputs.require_new_files((args.out,))
        if args.command == "evidence":
            refs = {"alphavantage.us": (args.alphavantage_pd, args.alphavantage_commit, args.alphavantage_sha),
                    "openfigi": (args.openfigi_pd, args.openfigi_commit, args.openfigi_sha),
                    "calendar.manual": (args.calendar_pd, args.calendar_commit, args.calendar_sha)}
            data, mode = real_inputs.evidence_document(refs), None
        else:
            proposal, _verified = real_inputs.read_proposal(args.proposal)
            rebuilt = (build or real_inputs.rebuild_real)(args)
            if rebuilt.qualification.proposal != proposal:
                raise real_inputs.InputError("RW_LOADER_PROPOSAL_DIFFERS", "the qualification rebuilt from the inputs is not the proposal file %s" % args.proposal)
            data, mode = real_inputs.contexts_document(rebuilt, args.generation), 0o600
        real_inputs.write_new_file(args.out, data, mode=mode)
    except (*real_inputs.INPUT_REFUSALS, OSError) as error:
        say("REFUSED %s. Nothing was written." % (str(error) if hasattr(error, "code") else "%s: %s" % (type(error).__name__, error)))
        return EXIT_REFUSED
    say("wrote %s (%d bytes%s) to %s" % ("the expiry-evidence file" if args.command == "evidence" else "the contexts file", len(data),
                                         "" if mode is None else ", mode 0600", args.out))
    say("No connection was opened, no password was asked, nothing was published.")
    return EXIT_DONE


if __name__ == "__main__":
    sys.exit(main())
