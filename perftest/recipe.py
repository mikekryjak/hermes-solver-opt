"""Comparing a case against the recipe it was supposed to run.

A recipe is a named block of `[solver]` and `[petsc]` settings. `apply_recipe`
replaces those two sections of a BOUT.inp wholesale, so once a recipe has been
applied any difference in them is a later edit -- deliberate or accidental.

That makes the comparison a free consistency check. What the run was declared to
be testing is recorded by hand; what actually differs is measured here. When the
measurement contains something the declaration does not, a setting changed that
nobody intended.
"""

import os
import re

MANAGED_SECTIONS = ("solver", "petsc")

# Added per case by cli/add_views.py to record the solver objects PETSc built,
# never by a recipe. They are diagnostic, so a case carrying them has not
# deviated from its recipe and must not be reported as though it had.
TOOLING_FLAGS = ("petsc:snes_view", "petsc:ksp_view")

# Written into every applied recipe by the runner, outside a trial's overrides,
# so they never enter `varied` or the configuration tag. They change what a run
# prints, not what it computes: diagnose_failures prints every field's minimum
# and maximum at each failed solve, where BOUT++ otherwise prints only the last.
DIAGNOSTICS = (("solver:diagnose_failures", "true"),)

# The same setting under its two spellings. BOUT++ applies the [solver] values
# with explicit calls and reads [petsc] last (snes.cxx line 770), so a setting
# written on both sides is decided by the petsc one whatever the other says.
# A run whose recipe does that is mislabelled, not merely untidy, which is why
# the pairs are listed rather than left to whoever reads the recipe.
#
# These pairs hold for the SNES solver only. Under `type = petsc`, which is the
# TS path, BOUT++ spends solver:atol and solver:rtol on TSSetTolerances and
# leaves the SNES tolerances to PETSc (petsc.cxx lines 330 and 397), so there
# solver:atol and petsc:snes_atol are two different settings that happen to
# share a name. The same caution applies to the CVODE path.
#
# Option names checked against this build's libpetsc.
SAME_SETTING = {
    "solver:snes_type": "petsc:snes_type",
    "solver:ksp_type": "petsc:ksp_type",
    "solver:pc_type": "petsc:pc_type",
    "solver:pc_hypre_type": "petsc:pc_hypre_type",
    "solver:line_search_type": "petsc:snes_linesearch_type",
    "solver:atol": "petsc:snes_atol",
    "solver:rtol": "petsc:snes_rtol",
    "solver:stol": "petsc:snes_stol",
    "solver:max_nonlinear_iterations": "petsc:snes_max_it",
    "solver:maxf": "petsc:snes_max_funcs",
    "solver:maxl": "petsc:ksp_max_it",
    "solver:max_snes_failures": "petsc:snes_max_linear_solve_fail",
    "solver:lag_jacobian": "petsc:snes_lag_jacobian",
    "solver:jacobian_persists": "petsc:snes_lag_jacobian_persists",
    "solver:kspsetinitialguessnonzero": "petsc:ksp_initial_guess_nonzero",
    "solver:matrix_free": "petsc:snes_mf",
    "solver:matrix_free_operator": "petsc:snes_mf_operator",
}


def other_spelling(key):
    """The same setting written for the other section, or None."""

    if key in SAME_SETTING:
        return SAME_SETTING[key]
    for solver_key, petsc_key in SAME_SETTING.items():
        if petsc_key == key:
            return solver_key
    return None


def shadowed(settings, key):
    """The key in `settings` that would override `key`, or None.

    `settings` is a parsed recipe. A setting written in both sections is
    decided by the [petsc] one, so setting the [solver] spelling changes the
    file and not the run.
    """

    family = settings.get("solver:type", "snes").strip().lower()
    if family not in ("", "snes"):
        return None
    twin = other_spelling(key)
    if twin is None or twin not in settings:
        return None
    # The petsc side wins, so nothing shadows a key that is itself on it.
    return None if key.startswith("petsc:") else twin


def parse_settings(path, sections=MANAGED_SECTIONS):
    """
    `{"section:key": value}` for the named sections of a BOUT.inp or recipe file.

    A bare line with no `=` is a PETSc flag, which is meaningful by its presence
    alone; it is recorded with an empty value so that adding or removing one
    still shows up as a difference.

    `sections=None` reads every section, which is how the physics comparison
    sees the parts a recipe does not manage.
    """

    wanted = None if sections is None else {s.lower() for s in sections}
    settings = {}
    section = None

    with open(path, errors="ignore") as f:
        for raw in f:
            line = raw.split("#")[0].strip()
            if not line:
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1].strip().lower()
                continue
            if wanted is not None and section not in wanted:
                continue
            if section is None:
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                settings[f"{section}:{key.strip()}"] = value.strip()
            else:
                settings[f"{section}:{line}"] = ""

    return settings


def find_recipe(recipe, recipes_dir):
    """Path to a named recipe, or None. Names are as written in the index."""

    if not recipe or not recipes_dir:
        return None
    path = os.path.join(recipes_dir, f"{recipe}.txt")
    return path if os.path.exists(path) else None


def _comparable(value):
    """Numeric values compared as numbers, so 1e-7 and 1.0e-7 are not a diff."""

    text = value.strip().strip("\"'")
    if re.fullmatch(r"[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?", text):
        return repr(float(text))
    return text.lower()


def diff_physics(case_dir, reference_inp):
    """
    Every deviation of a case's PHYSICS settings from a reference BOUT.inp, as
    the key names alone, sorted.

    Physics means everything outside `[solver]` and `[petsc]`: the limiter, the
    boundary conditions, the sources, the species list. `diff_against_recipe`
    cannot see any of it, so two runs could be compared as "same physics,
    different solver" while a boundary condition differed between them.

    Names without values, because the index is read whole and both inputs are
    kept in their bundles: the name says where to look, and nothing is lost.
    """

    case = parse_settings(os.path.join(case_dir, "BOUT.inp"), sections=None)
    reference = parse_settings(reference_inp, sections=None)

    changed = []
    for key in sorted(set(case) | set(reference)):
        if key.split(":", 1)[0] in MANAGED_SECTIONS:
            continue
        if key not in reference or key not in case:
            changed.append(key)
        elif _comparable(case[key]) != _comparable(reference[key]):
            changed.append(key)

    return changed


def diff_against_recipe(case_dir, recipe_path):
    """
    Every deviation of a case's `[solver]`/`[petsc]` sections from its recipe,
    as `section:key: from -> to` strings, sorted so two runs that deviate the
    same way produce identical text.

    `(absent)` on either side means the setting exists in only one of the two.
    """

    case = parse_settings(os.path.join(case_dir, "BOUT.inp"))
    named = parse_settings(recipe_path)

    diffs = []
    for key in sorted(set(case) | set(named)):
        if key in TOOLING_FLAGS and key not in named:
            continue
        if key not in named:
            diffs.append(f"{key}: (absent) -> {case[key] or '(set)'}")
        elif key not in case:
            diffs.append(f"{key}: {named[key] or '(set)'} -> (absent)")
        elif _comparable(case[key]) != _comparable(named[key]):
            diffs.append(f"{key}: {named[key]} -> {case[key]}")

    return diffs
