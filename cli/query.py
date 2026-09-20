#!/usr/bin/env python3
"""Ask the results index a question and get back a few columns.

The index has more than fifty columns, and reading it whole is the mistake this
tool exists to prevent. Measured work shows a model reading a wide table counts
and filters badly, while a single value looked up in a narrow table is nearly
always right. A person scrolling a spreadsheet fares no better. So every read of
the record goes through a filter, a sort and a small projection, and neither
reader ever aggregates the table by eye.

    query.py [--where col=value ...] [--sort col [--desc]] [--group col]
             [--columns a,b,c] [--limit N] [--tsv] [--store DIR]

The store is found from the `store` environment variable, which the user's
shell sets, and `--store` overrides it. Column names and meanings live in the
store's schema.md.

An empty cell means the value was never measured. It is never a zero: blanks sort
last in either direction and are left out of every median.
"""

import argparse
import csv
import difflib
import os
import pathlib
import statistics
import sys

# This repository ships no packaging; cli/ is on $PATH and its tools are run
# by name, so each puts the repository root on the path itself.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from perftest.store import Store, number  # noqa: E402

# The ten columns that answer "what did we try, and what happened" without
# opening anything else. `test` and `varied` say what the run was; `outcome`
# and `verdict` say whether it worked and whether the physics still agreed;
# `wall_s` and `ms_per_24h` are the cost; `nl_its`, `lin_its` and
# `solver_fails` say where the cost came from; `recipe` names the baseline the
# run varied. Every other column is provenance or detail, and asking for it
# should be a deliberate --columns.
DEFAULT_COLUMNS = [
    "test",
    "varied",
    "outcome",
    "wall_s",
    "ms_per_24h",
    "nl_its",
    "lin_its",
    "solver_fails",
    "verdict",
    "recipe",
]

# Longest and shortest operators share a prefix, so the two-character ones are
# tried first or `>=` would parse as `>` against the value "=3".
OPERATORS = ["!=", ">=", "<=", "=", ">", "<"]

# Shown where a cell is empty. A run of blank columns at the end of a row is
# hard to read as a table, and the marker keeps the shape of the row visible.
BLANK = "-"


class QueryProblem(Exception):
    """The question cannot be answered as asked, and guessing would mislead."""


def find_store(argument):
    """The store directory, from the flag or the environment.

    The shell variable is the one the user already exports, so a query needs no
    path typed at all. Failing loudly beats falling back to a guessed path: a
    wrong store would answer every question with somebody else's runs.
    """

    root = argument or os.environ.get("store") or os.environ.get("SOLVER_OPT_STORE")
    if not root:
        raise QueryProblem(
            "no store given: pass --store DIR or export `store` to the results"
            " store directory"
        )
    if not os.path.isfile(os.path.join(root, "index.tsv")):
        raise QueryProblem(f"no index.tsv in {root}")
    return root


def header_columns(index_path):
    """The column names, read from the file's own first line.

    Read from the file rather than from perftest.index.INDEX_COLUMNS because the
    file is the thing being queried. A canonical column the file does not yet
    carry would validate here and then print as empty for every row.
    """

    with open(index_path, newline="") as f:
        names = next(csv.reader(f, delimiter="\t"))
    return [n.strip() for n in names]


def check_column(name, columns, what="column"):
    """Fail on an unknown column, and say which real one was probably meant."""

    if name in columns:
        return name
    close = difflib.get_close_matches(name, columns, n=3, cutoff=0.4)
    hint = f" Did you mean: {', '.join(close)}?" if close else ""
    raise QueryProblem(f"no such {what}: {name!r}.{hint}")


def as_number(text):
    """The cell as a float, or None when it is blank or not a number.

    None rather than nan, because nan compares false against everything and
    would quietly drop rows from a sort instead of placing them last.
    """

    value = (text or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def is_numeric_column(rows, column):
    """True when every value present in this column is a number.

    A column of measurements with one hand-typed note in it is treated as text,
    because sorting it numerically would silently move that row.
    """

    values = [(r.get(column) or "").strip() for r in rows]
    present = [v for v in values if v]
    if not present:
        return False
    return all(as_number(v) is not None for v in present)


def parse_where(expression, columns):
    """Split `col op value` into its three parts, checking the column exists."""

    for operator in OPERATORS:
        if operator in expression:
            column, _, value = expression.partition(operator)
            column = column.strip()
            check_column(column, columns)
            return column, operator, value.strip()
    raise QueryProblem(
        f"cannot read the filter {expression!r}: expected col=value, with one of"
        f" {', '.join(OPERATORS)}"
    )


def text_matches(cell, wanted):
    """Compare two strings the way somebody typing at a prompt expects.

    Case is ignored, because `completed` and `Completed` are the same outcome. A
    trailing star matches a prefix, which is how a whole family of tests is
    selected without listing them.
    """

    cell = (cell or "").strip().lower()
    wanted = wanted.strip().lower()
    if wanted.endswith("*"):
        return cell.startswith(wanted[:-1])
    return cell == wanted


def row_matches(row, column, operator, wanted):
    """Whether one row passes one filter.

    Numbers are compared as numbers when both sides are numbers, so
    `wall_s>100` does not order by the first digit. Text is compared as text,
    which is what makes `recorded_at>=2026-09-01` work. An ordering test against
    a blank cell is always false: "not measured" is neither above nor below a
    threshold, and calling it zero would report failures as the fastest runs.
    """

    cell = (row.get(column) or "").strip()
    left, right = as_number(cell), as_number(wanted)

    if operator in ("=", "!="):
        if left is not None and right is not None:
            same = left == right
        else:
            same = text_matches(cell, wanted)
        return same if operator == "=" else not same

    if not cell:
        return False
    if left is None or right is None:
        left, right = cell.lower(), wanted.strip().lower()

    if operator == ">":
        return left > right
    if operator == "<":
        return left < right
    if operator == ">=":
        return left >= right
    return left <= right


def sort_rows(rows, column, descending):
    """Rank the rows, keeping unmeasured ones at the bottom.

    Blanks are pulled out and appended rather than given a sort key, so they stay
    last under --desc too. A blank is the absence of a measurement, so it belongs
    at neither end of the ranking, and the bottom is where it is least likely to
    be read as a result.
    """

    measured = [r for r in rows if (r.get(column) or "").strip()]
    blank = [r for r in rows if not (r.get(column) or "").strip()]

    if is_numeric_column(rows, column):
        key = lambda r: as_number(r.get(column))  # noqa: E731
    else:
        key = lambda r: (r.get(column) or "").strip().lower()  # noqa: E731

    return sorted(measured, key=key, reverse=descending) + blank


def median_of(rows, column):
    """The median of the values present, or None when none are.

    The median, not the mean, because these timings carry outliers from other
    runs competing for the machine. One contended run doubles a mean and barely
    moves a median.
    """

    values = [as_number(r.get(column)) for r in rows]
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def group_rows(rows, column, projection):
    """One summary row per distinct value: the count, then a median each.

    Text columns in the projection carry no median and are dropped from the
    summary, because there is no honest single value to show for them.
    """

    numeric = [c for c in projection if c != column and is_numeric_column(rows, c)]

    groups = {}
    for row in rows:
        groups.setdefault((row.get(column) or "").strip(), []).append(row)

    columns = [column, "n"] + [f"{c}_med" for c in numeric]
    summary = []
    for value, members in groups.items():
        entry = {column: value or "", "n": str(len(members))}
        for name in numeric:
            middle = median_of(members, name)
            entry[f"{name}_med"] = "" if middle is None else format_number(middle)
        summary.append(entry)
    return summary, columns


def format_number(value):
    """A number short enough to read in a table, without losing its size.

    Stored values carry full float precision, which is right for the file and
    unreadable in a terminal. Whole numbers lose their point, and the rest keep
    three decimals; very small and very large values fall back to exponent form.
    """

    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    if 1e-3 <= abs(value) < 1e7:
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return f"{value:.4g}"


def render_cell(row, column, numeric):
    """One cell as it should appear in the aligned table."""

    text = (row.get(column) or "").strip()
    if not text:
        return BLANK
    if numeric:
        value = as_number(text)
        if value is not None:
            return format_number(value)
    return text


def print_table(rows, columns, max_width, stream=sys.stdout):
    """Print an aligned table, numbers to the right and text to the left.

    Long free-text cells are cut to --max-width so one `varied` string cannot
    push every other column off the screen. Use --tsv when the full value
    matters; that output is never cut.
    """

    numeric = {c: is_numeric_column(rows, c) for c in columns}
    table = [[render_cell(r, c, numeric[c]) for c in columns] for r in rows]

    if max_width:
        table = [
            [cell if len(cell) <= max_width else cell[: max_width - 3] + "..."
             for cell in line]
            for line in table
        ]

    widths = [len(c) for c in columns]
    for line in table:
        widths = [max(w, len(cell)) for w, cell in zip(widths, line)]

    def lay_out(cells):
        parts = [
            cell.rjust(w) if numeric[c] else cell.ljust(w)
            for cell, w, c in zip(cells, widths, columns)
        ]
        return "  ".join(parts).rstrip()

    print(lay_out(columns), file=stream)
    print("  ".join("-" * w for w in widths), file=stream)
    for line in table:
        print(lay_out(line), file=stream)


def print_tsv(rows, columns, stream=sys.stdout):
    """Print the stored text, tab separated, for another program to read.

    Values go out exactly as the index holds them, with blanks left blank, so a
    reader of this output sees the record and not this tool's formatting.
    """

    writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([(row.get(c) or "").strip() for c in columns])


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--store", help="results store (holds index.tsv)")
    parser.add_argument("--columns", help="comma separated columns to show")
    parser.add_argument("--where", action="append", default=[], metavar="COL=VALUE",
                        help="filter, repeatable; also != > < >= <=")
    parser.add_argument("--sort", help="column to rank by; blanks always last")
    parser.add_argument("--desc", action="store_true", help="rank downwards")
    parser.add_argument("--group", help="column to group by; prints count and medians")
    parser.add_argument("--limit", type=int, default=20,
                        help="show at most this many rows (0 for all)")
    parser.add_argument("--max-width", type=int, default=40,
                        help="cut table cells longer than this (0 to keep them)")
    parser.add_argument("--tsv", action="store_true",
                        help="tab separated output, uncut and unformatted")
    args = parser.parse_args()

    root = find_store(args.store)
    store = Store(root)
    columns = header_columns(store.index_path)
    rows = store.rows()

    if args.columns:
        projection = [c.strip() for c in args.columns.split(",") if c.strip()]
        for name in projection:
            check_column(name, columns)
    else:
        # A column can be missing from an older store, and dropping it beats
        # printing a column of blanks that looks like missing measurements.
        projection = [c for c in DEFAULT_COLUMNS if c in columns]

    for expression in args.where:
        column, operator, value = parse_where(expression, columns)
        rows = [r for r in rows if row_matches(r, column, operator, value)]

    matched = len(rows)

    if args.group:
        check_column(args.group, columns)
        rows, out_columns = group_rows(rows, args.group, projection)
        if args.sort:
            # Asking to sort groups by a projection column means its median,
            # which is the only value a group has for it.
            sort_column = args.sort
            if sort_column not in out_columns:
                sort_column = f"{sort_column}_med"
            if sort_column not in out_columns:
                raise QueryProblem(
                    f"cannot sort groups by {args.sort!r}: a group has a value for"
                    f" {', '.join(out_columns)} only"
                )
            rows = sort_rows(rows, sort_column, args.desc)
        else:
            rows = sort_rows(rows, args.group, args.desc)
        matched = len(rows)
        unit = "groups"
    else:
        out_columns = projection
        if args.sort:
            check_column(args.sort, columns)
            rows = sort_rows(rows, args.sort, args.desc)
        unit = "rows"

    shown = rows[: args.limit] if args.limit else rows

    if args.tsv:
        print_tsv(shown, out_columns)
    else:
        print_table(shown, out_columns, args.max_width)

    # The count goes to stderr under --tsv so that stdout stays a clean table
    # for whatever reads it. It is never dropped: a reader who cannot see how
    # many rows were hidden by --limit will take the first page for the whole
    # answer.
    summary = f"\n{matched} {unit} matched, {len(shown)} shown"
    print(summary, file=sys.stderr if args.tsv else sys.stdout)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except QueryProblem as problem:
        print(f"query.py: {problem}", file=sys.stderr)
        raise SystemExit(2)
