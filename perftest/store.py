"""Reading a results store back out.

The counterpart to extract.py. Extraction happens once and cannot be repeated
after the dumps are deleted; reading happens as often as the questions change.
Keeping them apart means analysis never touches a case directory, and so keeps
working on runs whose dumps are long gone.

Everything here reads the index and the bundles. Nothing reads a dump.

The index is in git and the bundles are not. A bundle is per-case evidence and
there are hundreds of megabytes of it, so it lives in the data directory beside
the cases and seeds it came from, and the store repository stays small.
"""

import csv
import os

# Bundles under the data directory, one directory per run.
BUNDLE_DIR = "bundles"

# Where bundles were written until 2026-09-20, relative to the store.
OLD_BUNDLE_DIR = "runs"

# Used when nothing else names the data directory. query.py refuses to guess a
# store, because the wrong store answers every question with somebody else's
# runs. A bundle path is read against the index, which names the run, so the
# wrong directory shows up at once as a bundle that is not there.
DEFAULT_DATA = "/home/mike/work/solver-opt-data"

# Tables an extraction writes into each bundle, and what each one is a history
# of. Three different clocks, and mixing them silently is the easy mistake:
#   series      -- per output step, from the dump
#   steps       -- per output step, from BOUT.log.0
#   snes_steps  -- per INTERNAL solver step, so usually fewer rows than outputs
#                  once the timestep grows past the output interval
#   events      -- once per run, the log_view cost breakdown
#   resid_regions -- per output step, long: one row per (step, region, equation)
#   ddt         -- per output step, long: one row per (step, evolved variable)
#   physics     -- per output step, the monitor quantities
TABLES = ("series", "steps", "snes_steps", "events", "resid_regions", "ddt",
          "physics")


def find_data(argument=None):
    """The data directory, from the argument or the environment.

    Same order as query.py resolves the store, because the user already exports
    `data` and a path typed by hand is how the wrong one gets used.
    """

    return (
        argument
        or os.environ.get("data")
        or os.environ.get("SOLVER_OPT_DATA")
        or DEFAULT_DATA
    )


def bundle_root(data_dir=None):
    """Where bundles are written: `<data>/bundles`."""

    return os.path.join(find_data(data_dir), BUNDLE_DIR)


def bundle_path(test_id, data_dir=None, store_dir=None):
    """Where this run's bundle is, for reading.

    The new location wins, and a bundle still sitting in the store is found
    anyway. The fallback exists for the move of 2026-09-20 and can go once no
    bundle remains under `<store>/runs`.
    """

    new = os.path.join(bundle_root(data_dir), test_id)
    if store_dir and not os.path.isdir(new):
        old = os.path.join(store_dir, OLD_BUNDLE_DIR, test_id)
        if os.path.isdir(old):
            return old
    return new


class Store:
    """A results store: one index in git, many bundles outside it."""

    def __init__(self, root, index_name="index.tsv", data_dir=None):
        self.root = root
        self.index_path = os.path.join(root, index_name)
        self.data_dir = data_dir

    def rows(self, **filters):
        """
        Index rows, optionally filtered by exact column match.

        `state="recorded"` is the usual one. Values are strings, as stored —
        conversion is the caller's business, because what counts as a number
        differs by column and an empty cell must stay empty rather than become
        a zero.
        """

        with open(self.index_path, newline="") as f:
            rows = [dict(r) for r in csv.DictReader(f, delimiter="\t")]

        for key, value in filters.items():
            rows = [r for r in rows if r.get(key) == value]
        return rows

    def row_for_case(self, case_dir):
        """The recorded row for a case directory name, or None."""

        key = os.path.basename(os.path.normpath(case_dir))
        matches = [
            r
            for r in self.rows()
            if os.path.basename(os.path.normpath(r.get("case_dir", ""))) == key
            and r.get("test_id")
        ]
        return matches[-1] if matches else None

    def bundle(self, test_id):
        return bundle_path(test_id, self.data_dir, self.root)

    def table(self, test_id, name):
        """
        One bundle table as a dataframe, or None if this run has no such table.

        None is a real answer, not a failure: CVODE runs have no snes_steps, and
        a run launched without capturing stdout has no events.
        """

        import pandas as pd

        path = os.path.join(self.bundle(test_id), f"{name}.tsv")
        if not os.path.exists(path):
            return None
        index_col = 0 if name == "events" else None
        return pd.read_csv(path, sep="\t", index_col=index_col)

    def tables(self, test_id):
        """Every table a bundle holds, keyed by name, missing ones omitted."""

        found = {n: self.table(test_id, n) for n in TABLES}
        return {n: t for n, t in found.items() if t is not None}


def number(row, column, default=float("nan")):
    """A numeric cell, with empty meaning unknown rather than zero."""

    value = (row.get(column) or "").strip()
    try:
        return float(value)
    except ValueError:
        return default
