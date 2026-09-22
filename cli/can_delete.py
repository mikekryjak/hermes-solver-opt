#!/usr/bin/env python3
"""Say whether one run's dumps can be deleted, and refuse when they cannot.

The retention rule is that dumps are expendable once the record is extracted,
because disk is scarce. That rule is right for an ordinary run and wrong for a
parent run, whose dumps are also the only source of seeds. On 2026-09-20 it was
applied to the test5 parent four minutes after its record was committed, and
16.6 hours of simulation became unrepeatable work. This tool is the check that
was missing.

    can_delete.py CASE_DIR [--store DIR] [--seeds DIR] [--seed-times a,b,...]

Exit status is the answer, so this runs as a gate in front of a deletion:

    can_delete.py "$case" && rm "$case"/BOUT.dmp.*.nc

    0  safe to delete
    1  refused, with the reason on stderr
    2  the question could not be answered, so also refused

A refusal is never a failure of this tool. Deleting a dump cannot be undone and
re-running a parent costs a day, so every doubt resolves towards keeping it.
"""

import argparse
import glob
import os
import pathlib
import sys

# pyproject.toml packages these tools for an installed copy on another machine.
# Here nothing is installed: cli/ is on $PATH and the tools run by name, so
# each puts the repository root on the path itself. This line is load-bearing.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from perftest.index import STATE_PLANNED, STATE_RECORDED, case_key  # noqa: E402
from perftest.store import Store  # noqa: E402

# The one outcome whose record stands on its own. Every other class in R19 is a
# run that stopped early or finished wrong, and its dumps are the only place
# the reason for that is visible. A blank outcome means nobody has classified
# the run yet, which is the same answer.
TRUSTED_OUTCOME = "completed"

# What BOUT++ writes in `run_restart_from` for a run from initial conditions.
# It was recorded verbatim until 2026-09-20 and left empty after, so both forms
# mean the same thing.
FROM_SCRATCH = "z" * 36

# The seed library keys on the Hermes-3 commit, because seeds cut under one
# build are not reused under another (R18).
SEED_GLOB = "BOUT.restart.*.nc"
DUMP_GLOB = "BOUT.dmp.*.nc"


class Refused(Exception):
    """Deletion is not allowed, and the message says why."""

    status = 1


class CannotTell(Refused):
    """The question cannot be answered, so deletion is not allowed either."""

    status = 2


def find_store(argument):
    """The store directory, from the flag or the environment.

    Same resolution as query.py, because the user already exports `store` and
    typing a path into a deletion gate is how the wrong store gets consulted.
    A wrong store would clear every run against somebody else's record.
    """

    root = argument or os.environ.get("store") or os.environ.get("SOLVER_OPT_STORE")
    if not root:
        raise CannotTell(
            "no store given: pass --store DIR or export `store` to the results"
            " store directory"
        )
    if not os.path.isfile(os.path.join(root, "index.tsv")):
        raise CannotTell(f"no index.tsv in {root}")
    return root


def find_seeds(argument, case_path):
    """The seed library directory, or None when no candidate exists.

    The order follows make_window.py, which writes the seeds and is the
    authority on where they go: the flag, then SOLVEROPT_SEEDS, then `seeds/`
    beside the case area. `$data/seeds` is appended because that is where the
    library actually sits, and make_window's own fallback resolves one level
    short of it. The first candidate that exists wins, so a variable pointing
    at an empty path cannot make a parent look unseeded.
    """

    area = os.path.dirname(os.path.abspath(case_path))
    candidates = [
        argument,
        os.environ.get("SOLVEROPT_SEEDS"),
        os.path.join(area, "seeds"),
        os.path.join(os.path.dirname(area), "seeds"),
    ]
    data = os.environ.get("data")
    if data:
        candidates.append(os.path.join(data, "seeds"))

    for candidate in candidates:
        if candidate and os.path.isdir(candidate):
            return candidate
    return None


def row_for(store, name):
    """The recorded row for this case directory, refusing when there is none.

    The index defines what exists. A directory with no row has not been
    recorded, so its dumps are not a duplicate of anything: they are the only
    copy of the run.
    """

    row = store.row_for_case(name)
    if row is None:
        raise Refused(
            f"{name} has no row in the index. An unrecorded run's dumps are its"
            " only record, so nothing may be deleted until it is extracted."
        )
    return row


def check_record(store, name, row):
    """Refuse unless the record is finished, validated and trustworthy."""

    open_rows = [
        r
        for r in store.rows()
        if case_key(r.get("case_dir", "")) == name
        and r.get("state", "") == STATE_PLANNED
    ]
    if open_rows:
        raise Refused(
            f"{name} has an open `{STATE_PLANNED}` row, so a run is declared or"
            " in flight in that directory."
        )

    state = (row.get("state") or "").strip()
    if state != STATE_RECORDED:
        raise Refused(
            f"{name} is `{state or 'blank'}`, not `{STATE_RECORDED}`. Only an"
            " extracted and validated record licenses a deletion."
        )

    outcome = (row.get("outcome") or "").strip()
    if outcome != TRUSTED_OUTCOME:
        raise Refused(
            f"{name} ended as `{outcome or 'unclassified'}`. Its dumps are the"
            " only evidence of how it went wrong."
        )

    if (row.get("verdict") or "").strip() == "fail":
        raise Refused(
            f"{name} failed its correctness check, and the dumps are what a"
            " person needs to find out why."
        )


def is_parent(store, row):
    """Whether this run is a parent, and the evidence for saying so.

    The signal is the `seed` column: it holds the run_id this run restarted
    from, and a parent is a run from initial conditions, so a parent's cell
    carries BOUT's from-scratch placeholder or is empty. This is measured from
    the dump rather than typed, it survives a rename and a move, and the
    directory name does not enter into it.

    Its weakness is that the cell is also empty when the value was never
    measured, and that a from-scratch run which nobody ever cuts a seed from
    reads the same as a parent. Both mistakes keep dumps that could have gone,
    which is the direction this tool is allowed to be wrong in.

    A second signal is proof rather than inference: another row whose `seed` is
    this run's run_id has already been cut from it. Absence of such a row
    proves nothing, since a parent's first seed may not be cut yet, so it can
    only add to the answer.
    """

    reasons = []

    seed = (row.get("seed") or "").strip()
    if not seed:
        reasons.append("its `seed` cell is empty, so nothing seeded it")
    elif seed == FROM_SCRATCH:
        reasons.append("its `seed` cell is BOUT's from-scratch placeholder")

    run_id = (row.get("run_id") or "").strip()
    if run_id:
        children = [
            r for r in store.rows() if (r.get("seed") or "").strip() == run_id
        ]
        if children:
            reasons.append(f"{len(children)} recorded runs restarted from it")

    return bool(reasons), reasons


def seeds_cut(seeds_root, commit, name):
    """The times, in ms, that this parent already has complete seeds for.

    A seed directory with no restart files in it is a cut that did not finish,
    and counts as missing rather than present.
    """

    parent_seeds = os.path.join(seeds_root, commit, name)
    if not os.path.isdir(parent_seeds):
        return []

    times = []
    for entry in sorted(os.listdir(parent_seeds)):
        if not entry.endswith("ms"):
            continue
        if not glob.glob(os.path.join(parent_seeds, entry, SEED_GLOB)):
            continue
        try:
            times.append(float(entry[:-2]))
        except ValueError:
            continue
    return sorted(times)


def wanted_times(argument):
    """The seed times the caller says this parent must have, or None.

    None is the normal answer today, and it is a refusal rather than a default.
    Nothing machine-readable records which seeds a parent owes: the ladder in
    design.md is marked as provisional, and no campaign.toml exists yet. So the
    required set has to be stated by whoever asks for the deletion.
    """

    if not argument:
        return None
    times = []
    for piece in argument.replace(",", " ").split():
        try:
            times.append(float(piece.rstrip("ms")))
        except ValueError:
            raise CannotTell(f"cannot read the seed time {piece!r}: expected e.g. 20.0")
    return sorted(times)


def check_parent(name, seeds_root, cut, wanted):
    """Refuse unless every seed this parent owes has already been cut."""

    if seeds_root is None:
        raise CannotTell(
            f"{name} is a parent run and no seed library was found. Pass"
            " --seeds DIR or export SOLVEROPT_SEEDS."
        )

    if wanted is None:
        have = ", ".join(f"{t}ms" for t in cut) or "none"
        raise CannotTell(
            f"{name} is a parent run and nothing records which seeds it owes."
            f" Seeds cut so far: {have}. State the full set with --seed-times"
            " and this check will answer, or cut the rest first."
        )

    missing = [t for t in wanted if t not in cut]
    if missing:
        listed = ", ".join(f"{t}ms" for t in missing)
        raise Refused(
            f"{name} is a parent run and its seeds at {listed} are not cut."
            " Seeds come only from these dumps, so deleting them makes those"
            " seeds impossible forever."
        )


def report(lines):
    """What the tool found, so a refusal can be argued with."""

    for line in lines:
        print(line)


def run():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("case", help="the case directory to ask about")
    parser.add_argument("--store", help="results store (holds index.tsv)")
    parser.add_argument("--seeds", help="seed library directory")
    parser.add_argument("--seed-times", help="the seed times this parent owes,"
                        " comma separated, e.g. 0.0,20.0")
    args = parser.parse_args()

    # Parsed before anything is read, so a mistyped time fails at once rather
    # than after a page of findings.
    wanted = wanted_times(args.seed_times)

    case_path = os.path.abspath(os.path.expanduser(args.case))
    name = case_key(case_path)
    if not os.path.isdir(case_path):
        raise Refused(f"no such case directory: {case_path}")

    store = Store(find_store(args.store))
    row = row_for(store, name)
    check_record(store, name, row)

    dumps = len(glob.glob(os.path.join(case_path, DUMP_GLOB)))
    lines = [
        f"case     {name}",
        f"row      {row.get('test_id')}  state={row.get('state')}"
        f"  outcome={row.get('outcome')}  verdict={row.get('verdict')}",
        f"dumps    {dumps} {DUMP_GLOB} files present",
    ]

    parent, reasons = is_parent(store, row)
    if parent:
        commit = (row.get("hermes_commit") or "").strip()
        lines.append("parent   yes: " + "; ".join(reasons))
        report(lines)
        if not commit:
            raise CannotTell(
                f"{name} is a parent run and its row records no hermes_commit."
                " The seed library keys on that commit, so which seeds exist"
                " cannot be established."
            )
        seeds_root = find_seeds(args.seeds, case_path)
        cut = seeds_cut(seeds_root, commit, name) if seeds_root else []
        print(f"seeds    {', '.join(f'{t}ms' for t in cut) or 'none'} cut under"
              f" {commit[:12]}")
        check_parent(name, seeds_root, cut, wanted)
        print("\nSAFE: every seed this parent owes is cut.")
        return 0

    lines.append("parent   no: it was restarted from " + (row.get("seed") or ""))
    report(lines)
    print("\nSAFE: an ordinary run whose record is validated.")
    return 0


def main():
    # The handler lives here rather than under the __main__ guard because a
    # console entry point calls main() directly, and a guard never runs for it.
    # This tool's whole job is to refuse clearly, so a traceback is a failure.
    try:
        return run()
    except Refused as refusal:
        # The findings are printed as they are gathered, and a refusal must read
        # underneath them rather than above, so stdout goes out first.
        sys.stdout.flush()
        print(f"can_delete.py: REFUSED: {refusal}", file=sys.stderr)
        return refusal.status


if __name__ == "__main__":
    raise SystemExit(main())
