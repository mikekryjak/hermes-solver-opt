#!/usr/bin/env python3
"""Every knob the SNES solver path exposes, taken from the source that defines it.

    scan_options.py --petsc /path/to/petsc-source --out snes-space.tsv

Writes one row per option registration: what it is called, what kind of value
it takes, what gates it, and where in the source it is defined. This is the
whole space. `search-space.toml` is the small curated part of it that a
campaign may vary, and the two are not the same thing.

Why the source and not the manual. PETSc registers an option by calling
PetscOptionsBool, PetscOptionsInt and so on, and the call carries the name, the
help text and the type. Parsing those calls is exact. The manual is a
description of a different version, and the built library gives names without
types. The library is still used, but only to say which options the build in
use actually contains.

Scope: the nonlinear solve and everything under it -- SNES, the line search,
KSP, every preconditioner implementation, and the Mat code this path uses,
being the matrix-free product, the coloured finite-difference Jacobian and the
direct-solver packages. It leaves out DM, Vec and TS, and BOUT++'s run-level
controls such as nout and datadir, which are not solver settings.
"""

import argparse
import csv
import os
import re
import sys

# --- what a registration call means ----------------------------------------
# Every call used anywhere on this path, found by listing them rather than by
# guessing. PetscOptionsViewer and PetscOptionsDeprecated are left out on
# purpose: the first is a diagnostic, the second an alias for a name that is
# already registered under its current spelling.
KIND = {
    "Bool": "bool", "BoolGroup": "bool", "BoolGroupBegin": "bool",
    "BoolGroupEnd": "bool", "Name": "bool",
    "Int": "int", "BoundedInt": "int", "RangeInt": "int", "MPIInt": "int",
    "MUMPSInt": "int",
    "Real": "real", "BoundedReal": "real", "RangeReal": "real", "Scalar": "real",
    "Enum": "enum", "EList": "enum", "FList": "enum",
    "String": "string",
    "IntArray": "array", "RealArray": "array", "StringArray": "array",
    "ScalarArray": "array", "BoolArray": "array",
}

CALL = re.compile(r"PetscOptions(" + "|".join(sorted(KIND, key=len, reverse=True)) + r")\s*\(")

# Which part of the solve an option belongs to, decided by where it is
# registered. Order matters: the first match wins, so the narrower path is
# listed before the wider one it sits inside.
FAMILY = [
    ("src/snes/linesearch", "linesearch"),
    ("src/snes", "snes"),
    ("src/ksp/pc/impls/hypre", "hypre"),
    ("src/ksp/pc/impls/gamg", "gamg"),
    ("src/ksp/pc", "pc"),
    ("src/ksp/ksp", "ksp"),
    ("src/mat/impls/aij/mpi/mumps", "mumps"),
    ("src/mat/impls/aij/mpi/strumpack", "strumpack"),
    ("src/mat", "mat"),
]

# The Mat code the SNES path uses. The rest of src/mat is assembly and storage,
# which the solve does not tune.
MAT_KEEP = ("mumps", "strumpack", "mffd", "matfd", "color", "superlu", "cholmod", "umfpack")

# PETSc's implementation directory is not always the value the option takes.
# These are the ones that differ, checked against the RegisterAll files. A `|`
# means one directory serves several values of the same option.
SELECTOR_RENAME = {
    "snes_type=ls": "snes_type=newtonls",
    "snes_type=tr": "snes_type=newtontr",
    "snes_type=vi": "snes_type=vinewtonrsls|vinewtonssls",
    "snes_type=rich": "snes_type=nrichardson",
    "snes_type=gs": "snes_type=ngs",
    "pc_type=factor": "pc_type=lu|ilu|cholesky|icc",
    "ksp_type=rich": "ksp_type=richardson",
    "ksp_type=cheby": "ksp_type=chebyshev",
    "ksp_type=gmres": "ksp_type=gmres|fgmres|lgmres|dgmres|pgmres|agmres",
}

# How many values the big categorical options accept. Their lists are built at
# run time, so the registration call cannot say; the count comes from the
# RegisterAll file that fills the list.
REGISTER_FILES = {
    "pc_type": ("src/ksp/pc/interface/pcregis.c", "PCRegister"),
    "ksp_type": ("src/ksp/ksp/interface/itregis.c", "KSPRegister"),
    "snes_type": ("src/snes/interface/snesregi.c", "SNESRegister"),
    "snes_linesearch_type": ("src/snes/linesearch/interface/linesearchregi.c",
                             "SNESLineSearchRegister"),
}

# A monitor, a view or a reason flag reports on the solve without changing it,
# so counting one as a dimension of the search space would overstate it.
DIAGNOSTIC = re.compile(
    r"(monitor|view|_draw|draw_|log_|_log|verbose|print|debug|dump|_test|test_"
    r"|check|reason|history|error_if|info|ascii|python)"
)

COLUMNS = ["option", "kind", "default", "family", "object", "depends",
           "source", "help", "role", "n_values", "in_build"]


def clean(value, limit=120):
    return re.sub(r"\s+", " ", str(value)).strip()[:limit]


def family_of(path):
    for prefix, name in FAMILY:
        if path.startswith(prefix):
            return name
    return None


def selector_of(path, family):
    """What must be chosen for this option to exist at all."""

    match = re.search(r"impls/([^/]+)/", path)
    if not match:
        return ""
    impl = match.group(1)
    if family == "linesearch":
        selector = f"snes_linesearch_type={impl}"
    elif family == "snes":
        selector = f"snes_type={impl}"
    elif family == "ksp":
        selector = f"ksp_type={impl}"
    elif family in ("pc", "hypre", "gamg"):
        selector = f"pc_type={impl}"
    elif family in ("mumps", "strumpack"):
        selector = f"pc_factor_mat_solver_type={family}"
    else:
        return ""
    return SELECTOR_RENAME.get(selector, selector)


def arguments(text, start):
    """The argument list of a call whose opening bracket is at `start`."""

    depth, out, current, i = 0, [], "", start
    while i < len(text):
        char = text[i]
        if char == "(":
            depth += 1
            if depth == 1:
                i += 1
                continue
        elif char == ")":
            depth -= 1
            if depth == 0:
                out.append(current)
                return out
        if depth == 1 and char == ",":
            out.append(current)
            current = ""
        else:
            current += char
        i += 1
    return out


def literal(text):
    match = re.match(r'\s*"((?:[^"\\]|\\.)*)"', text)
    return match.group(1) if match else None


def value_lists(root):
    """`{array name: how many values}` for every list of option values.

    PETSc names an enum's values in a `const char *const name[]` array whose
    last two entries are the enum's own name and a NULL, neither of which is
    selectable.
    """

    # Both spellings appear: a file-scope `const char *const name[]` and a
    # local `const char *name[]` passed straight to PetscOptionsEList.
    declaration = re.compile(
        r"const\s+char\s*\*\s*(?:const\s+)?(\w+)\s*\[\s*\]\s*=\s*\{(.*?)\}\s*;", re.S
    )
    found = {}
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", "docs") and not d.startswith("arch-")]
        for name in files:
            if not name.endswith((".c", ".h", ".cxx", ".hpp")):
                continue
            try:
                text = open(os.path.join(base, name), errors="ignore").read()
            except OSError:
                continue
            for match in declaration.finditer(text):
                entries = [e.strip() for e in match.group(2).split(",")]
                values = [e for e in entries if e.startswith('"')]
                if len(values) < 2:
                    continue
                # A `const char *const` list ends with the enum's own name and
                # a NULL, neither of which is selectable. A local list passed
                # to EList with its own length carries values only.
                trailing_null = any(e in ("NULL", "0") for e in entries)
                found.setdefault(match.group(1), len(values) - 2 if trailing_null else len(values))
    return found


def n_values(root, option, source, lists):
    """How many values a categorical option accepts, where the source says."""

    path, _, _ = source.rpartition(":")
    full = os.path.join(root, path)
    if not os.path.exists(full):
        return ""
    text = open(full, errors="ignore").read()
    call = re.search(
        r'PetscOptions(?:Enum|EList)\s*\(\s*"-' + re.escape(option) + r'"(.{0,400}?)\)\s*\)',
        text, re.S,
    )
    if not call:
        return ""
    body = call.group(1)
    for identifier in re.findall(r"\b([A-Za-z_]\w*)\s*(?:,|\))", body):
        if identifier in lists:
            return lists[identifier]
    # An inline list: the first two strings are the help text and the manual
    # page, so anything past them is a value.
    inline = re.findall(r'"([^"]+)"', body)
    return len(inline) - 2 if len(inline) > 3 else ""


def registered_counts(root):
    counts = {}
    for option, (path, call) in REGISTER_FILES.items():
        full = os.path.join(root, path)
        if not os.path.exists(full):
            continue
        # Only the calls, not the function's own definition or its docs.
        counts[option] = len(re.findall(
            r"PetscCall\(" + re.escape(call) + r"\(", open(full, errors="ignore").read()))
    return counts


def scan_petsc(root):
    """Every option registered on the SNES path, from the PETSc source."""

    rows, seen = [], set()
    for base, dirs, files in os.walk(os.path.join(root, "src")):
        dirs[:] = [d for d in dirs
                   if d not in ("tests", "tutorials", "ftn-auto", "ftn-custom", "f90-custom")]
        relative = os.path.relpath(base, root)
        family = family_of(relative)
        if family is None:
            continue
        if family == "mat" and not any(k in relative for k in MAT_KEEP):
            continue
        for name in sorted(files):
            if not name.endswith(".c"):
                continue
            path = os.path.join(base, name)
            relative_file = os.path.relpath(path, root)
            text = open(path, errors="ignore").read()
            for match in CALL.finditer(text):
                kind = KIND[match.group(1)]
                args = arguments(text, match.end() - 1)
                if not args:
                    continue
                option = literal(args[0])
                if not option or not option.startswith("-"):
                    continue
                option = option.lstrip("-")
                if (option, relative_file) in seen:
                    continue
                seen.add((option, relative_file))
                default = ""
                if kind in ("bool", "int", "real") and len(args) > 3:
                    default = args[3]
                elif kind in ("enum", "string") and len(args) > 4:
                    default = args[4]
                rows.append({
                    "option": clean(option, 80),
                    "kind": kind,
                    "default": clean(default, 40),
                    "family": family,
                    "object": clean(os.path.splitext(name)[0], 40),
                    "depends": clean(selector_of(relative_file, family), 60),
                    "source": clean(f"{relative_file}:{text[:match.start()].count(chr(10)) + 1}", 90),
                    "help": clean(literal(args[1]) if len(args) > 1 else ""),
                })
    return rows


def scan_bout(path):
    """The [solver] options BOUT++'s SNES solver reads, from its constructor."""

    if not os.path.exists(path):
        return []
    text = open(path, errors="ignore").read()
    pattern = re.compile(
        r'\(\*options\)\[\s*"([A-Za-z0-9_]+)"\s*\](.{0,600}?)\.withDefault(?:<[^>]+>)?\s*\(', re.S
    )
    rows, seen = [], set()
    for match in pattern.finditer(text):
        name = match.group(1)
        if name in seen:
            continue
        seen.add(name)
        default = arguments(text, match.end() - 1)
        default = default[0] if default else ""
        stripped = default.strip()
        if stripped in ("true", "false") or stripped.startswith("static_cast<bool>"):
            kind = "bool"
        elif re.fullmatch(r"-?\d+", stripped):
            kind = "int"
        elif re.fullmatch(r"-?\d*\.?\d+([eE][-+]?\d+)?", stripped):
            kind = "real"
        elif stripped.startswith('"') or "::" in stripped or "BoutSnes" in stripped:
            kind = "enum"
        elif re.search(r"\d", stripped):
            kind = "real"
        else:
            kind = "string"
        doc = re.search(r'\.doc\(\s*"((?:[^"\\]|\\.)*)"', match.group(2))
        rows.append({
            "option": f"solver:{name}",
            "kind": kind,
            "default": clean(stripped.strip('"'), 40),
            "family": "bout",
            "object": "BOUT++ SNES solver",
            "depends": "solver:type=snes",
            "source": clean(f"{path}:{text[:match.start()].count(chr(10)) + 1}", 90),
            "help": clean(doc.group(1) if doc else ""),
        })
    return rows


def built_options(library):
    """The option names present in a built library, from its strings."""

    if not library or not os.path.exists(library):
        return set()
    import subprocess
    result = subprocess.run(["strings", "-a", library], capture_output=True, text=True)
    return {line[1:] for line in result.stdout.splitlines()
            if line.startswith("-") and len(line) > 2 and line[1].isalpha()}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--petsc", required=True, help="a PETSc source tree")
    parser.add_argument("--bout", help="BOUT-dev's snes.cxx")
    parser.add_argument("--lib", help="the built libpetsc this run links, to mark reachability")
    parser.add_argument("--out", default="snes-space.tsv")
    args = parser.parse_args()

    if not os.path.isdir(os.path.join(args.petsc, "src")):
        print(f"scan_options.py: no src/ under {args.petsc}", file=sys.stderr)
        return 1

    rows = scan_petsc(args.petsc)
    rows += scan_bout(args.bout) if args.bout else []

    lists = value_lists(args.petsc)
    counts = registered_counts(args.petsc)
    built = built_options(args.lib)

    for row in rows:
        row["role"] = "diagnostic" if DIAGNOSTIC.search(row["option"]) else "tuning"
        row["n_values"] = ""
        if row["kind"] == "enum" and row["family"] != "bout":
            row["n_values"] = str(n_values(args.petsc, row["option"], row["source"], lists))
        if not row["n_values"]:
            bare = row["option"].split(":", 1)[-1]
            if bare in counts:
                row["n_values"] = str(counts[bare])

    # A BOUT++ option that forwards a PETSc one takes the same values, so it
    # inherits the count rather than being left blank.
    from_petsc = {r["option"]: r["n_values"] for r in rows
                  if r["family"] != "bout" and r["n_values"]}
    for row in rows:
        if row["family"] == "bout" and not row["n_values"]:
            row["n_values"] = from_petsc.get(row["option"].split(":", 1)[-1], "")
        row["in_build"] = ("bout" if row["family"] == "bout"
                           else "yes" if row["option"] in built
                           else "not found" if built else "")

    with open(args.out, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, delimiter="\t")
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: (r["family"], r["option"])))

    tuning = [r for r in rows if r["role"] == "tuning"]
    print(f"{len(rows)} registrations, {len({r['option'] for r in rows})} distinct options")
    print(f"{len(tuning)} tuning, {len(rows) - len(tuning)} diagnostic -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
