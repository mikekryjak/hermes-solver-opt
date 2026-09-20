#!/usr/bin/env python3
"""Ask PETSc to print the solver objects it actually built.

`-snes_view` and `-ksp_view` make PETSc dump the configured SNES and KSP at the
end of a run, into the captured console and nowhere else. Without them a bundle
records what the input file asked for, not what PETSc did with it -- and the
two differ often enough to matter: every run so far reports options PETSc never
used.

    add_views.py <case-dir> [<case-dir> ...] [--remove]

The flags are diagnostic and change no numerics, but they are added per case
rather than to the shared recipes in hermes-perftest, whose other users do not
want the extra console output.
"""

import argparse
import os

# Written without the leading dash, the way BOUT's [petsc] section takes its
# flags -- it prepends the dash itself, and `log_view` beside them proves the
# convention. A dashed flag here reaches PETSc as `--snes_view` and is ignored.
VIEW_FLAGS = ("snes_view", "ksp_view")


def add_views(path, remove=False):
    """Add the view flags to a BOUT.inp's [petsc] section. Returns what changed.

    Idempotent: a flag already present is left alone, so re-running over a case
    directory, or over one prepared by an earlier version of this tool, adds
    nothing twice.
    """

    with open(path, errors="ignore") as f:
        lines = f.read().splitlines()

    section, present, petsc_end = None, set(), None
    for i, raw in enumerate(lines):
        line = raw.split("#")[0].strip()
        if line.startswith("[") and line.endswith("]"):
            if section == "petsc":
                petsc_end = i
            section = line[1:-1].strip().lower()
            continue
        if section == "petsc" and line in VIEW_FLAGS:
            present.add(line)
    if section == "petsc":
        petsc_end = len(lines)

    if remove:
        kept = [l for l in lines if l.split("#")[0].strip() not in VIEW_FLAGS]
        removed = len(lines) - len(kept)
        if removed:
            _write(path, kept)
        return [f"removed {removed} flag(s)"] if removed else []

    missing = [flag for flag in VIEW_FLAGS if flag not in present]
    if not missing:
        return []

    if petsc_end is None:
        lines += ["", "[petsc]"] + missing
    else:
        lines[petsc_end:petsc_end] = missing
    _write(path, lines)
    return missing


def _write(path, lines):
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("cases", nargs="+", help="case directories to edit")
    parser.add_argument(
        "--remove", action="store_true", help="take the flags out again"
    )
    args = parser.parse_args()

    missing = 0
    for case in args.cases:
        path = os.path.join(case, "BOUT.inp")
        if not os.path.exists(path):
            print(f"{case}: no BOUT.inp")
            missing += 1
            continue
        changed = add_views(path, remove=args.remove)
        print(f"{case}: {', '.join(changed) if changed else 'already as asked'}")

    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
