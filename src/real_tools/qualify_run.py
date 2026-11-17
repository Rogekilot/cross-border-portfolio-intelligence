"""F1 R8: the OFFLINE qualification command (R8 step (2)'s first half and step (3)'s input; install plan section 5 item 6).

    python -m real_tools.qualify_run --store-root DIR --release-name NAME --file SHA [--file SHA ...] [--sidecar PATH ...] \\
        [--registered-check SHA ...] --proposal-out FILE --seed-out FILE

It runs the qualification of design 6.4 over the named files of a market-data store in the REAL scope (`real_inputs.rebuild_real`, the same build the
loader's window tool repeats), prints the listing of every member against the owner's confirmation table (6.3), and writes TWO new files, each by exclusive
create (an existing file is never overwritten, and nothing is written if either path exists):

  * `--proposal-out`: the proposal bytes (`qualification.save_proposal`), which the owner reviews at step (3) and which the publisher later publishes;
  * `--seed-out`: the identity seed file (`identity_seed.seed_bytes(resolver)`, install plan section 5 item 6), written only after the seed is read back and
    its `identity_digest` is shown equal to the proposal's snapshot's: the file the owner-run `identity_seed` tool will accept.

THIS TOOL OPENS NO CONNECTION AND TAKES NO PASSWORD. It imports no driver, no preflight and no prompt, and has no option for a socket, a database or a
user. It never publishes and never loads: loading is `loader_window load`. The REAL scope only: no option names a scope, and a test scope has no sidecar to
give. Without one valid sidecar per member (design 6.1, O5) it refuses and writes nothing.

Exit status: 0 done, 2 refused (an input, a verification or an existing output file; nothing, or nothing further, was written: the output says which).
"""
from __future__ import annotations

import sys

from persistence import real_proposal
from real_tools import identity_seed, qualification as q, real_inputs

EXIT_DONE, EXIT_REFUSED = 0, 2


def _build_parser():
    import argparse
    parser = argparse.ArgumentParser(prog="qualify_run", description="Offline qualification of the real release: writes the proposal and the identity seed "
                                     "file; opens no connection and takes no password.")
    parser.add_argument("--store-root", required=True, help="the market-data store (the directory holding files/ and SOURCES.json); read only")
    parser.add_argument("--release-name", required=True)
    parser.add_argument("--file", action="append", required=True, help="the payload SHA-256 of one member of the release (repeat for each)")
    parser.add_argument("--sidecar", action="append", help="a sidecar acquisition record file, one per member (repeat)")
    parser.add_argument("--registered-check", action="append", help="a payload SHA-256 that has a registered check instead of a row of the 6.3 table")
    parser.add_argument("--proposal-out", required=True)
    parser.add_argument("--seed-out", required=True)
    return parser


def main(argv=None, *, out=None, build=None):
    """`build(args)` returns a `real_inputs.Rebuilt` (the tests' seam; the default is `real_inputs.rebuild_real`, the REAL scope)."""
    args = _build_parser().parse_args(argv)
    say = (lambda text: print(text, file=out)) if out is not None else print
    try:
        real_inputs.require_new_files((args.proposal_out, args.seed_out))
        rebuilt = (build or real_inputs.rebuild_real)(args)
        qualification = rebuilt.qualification
        verified = real_proposal.verify_proposal(qualification.proposal)
        seed = identity_seed.seed_bytes(rebuilt.resolver)
        identity_seed.check_digest(identity_seed.read_seed(seed), verified.snapshot.content["identity_digest"])
    except real_inputs.INPUT_REFUSALS as error:
        say("REFUSED %s. Nothing was written." % (str(error) if hasattr(error, "code") else "%s: %s" % (type(error).__name__, error)))
        return EXIT_REFUSED
    for line in qualification.lines():
        say(line)
    try:
        q.save_proposal(args.proposal_out, qualification)
    except (OSError, q.QualificationError) as error:
        say("REFUSED %s. Nothing was written." % error)
        return EXIT_REFUSED
    say("wrote the proposal (%d bytes, context %s) to %s" % (len(qualification.proposal), qualification.context_id, args.proposal_out))
    try:
        real_inputs.write_new_file(args.seed_out, seed)
    except OSError as error:
        say("REFUSED the seed file: %s. The proposal WAS written (%s); the seed was not." % (error, args.proposal_out))
        return EXIT_REFUSED
    say("wrote the identity seed (%d bytes; its identity digest equals the proposal's) to %s" % (len(seed), args.seed_out))
    if qualification.needs_review:
        say("the run decides nothing about admissibility: the lines marked 'needs review' above are for the owner's review at step (3)")
    say("No connection was opened, no password was asked, nothing was published and nothing was loaded.")
    return EXIT_DONE


if __name__ == "__main__":
    sys.exit(main())
