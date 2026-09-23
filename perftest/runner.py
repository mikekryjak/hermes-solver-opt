"""The campaign runner: prepare, launch, watch, extract, prune.

design.md section 8 is the specification. One cycle per trial:

    check the gates -> generate the case -> open the index row -> launch into
    a slot -> watch for a stall or a cutoff -> extract -> apply retention

Two properties matter more than the steps.

It orchestrates and never reimplements. Every step is an existing tool run as
a subprocess -- make_window.py, apply_recipe.py, the launcher, extract_test.py,
can_delete.py -- so each stays runnable by hand with the same command, and the
runner cannot drift away from what a person would do. The tools that ship here
are found relative to this file; only sdtools' apply_recipe.py comes from PATH.

The index is the only state. What is left to do is decided by reading it, so
the loop is idempotent: interrupt it, run it again, and it picks up the trials
that have no result yet rather than repeating finished work. A private progress
file would be a second record able to disagree with the first.

No path to any machine appears here. The store, the data directory and the
Hermes-3 checkout come from the environment or from arguments.
"""

import dataclasses
import datetime
import glob
import hashlib
import math
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time

from . import index as idx
from . import recipe as rcp
from . import campaign as cp
from . import store as st
from .campaign import (  # noqa: F401  (re-exported for the console tool)
    ApprovalMissing,
    CampaignProblem,
    load_campaign,
)

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 and older
    import tomli as tomllib

# A row in one of these states is an answer. The trial is not run again.
SETTLED = {idx.STATE_RECORDED, idx.STATE_UNPLANNED, idx.STATE_CANCELLED}

# Outcome names are design.md section 7. perftest.extract.classify_outcome owns
# every state decidable from the log and the dump; these two are not in either,
# because a killed run leaves the same evidence whatever the reason for the
# kill. A stall is recorded as a timeout for the same reason a cutoff is: it
# says "at least this slow", which is evidence, not a missing result.
KILL_OUTCOME = {"cutoff": "timeout", "stall": "timeout", "cancelled": "cancelled"}

# Only a completed run is a time. A crash says nothing about the recipe, and a
# timeout is a lower bound, so neither may set the cutoff for later runs.
SCORING_OUTCOME = "completed"

DUMP_GLOB = "BOUT.dmp.*.nc"

# Disk sizes are what `df -h` shows, so a gigabyte is 1024^3 bytes.
GB = 1024 ** 3

TOOL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_RECIPES = os.path.join(TOOL_ROOT, "hermes-perftest", "recipes")

# A tool that ships in this repository is resolved against TOOL_ROOT, not left
# to PATH. A screen created before the .bashrc line that adds cli/ has a PATH
# without it, and then every extraction in a campaign fails. This stores no
# path to any one machine: it is relative to this file.
MAKE_WINDOW = os.path.join(TOOL_ROOT, "hermes-perftest", "make_window.py")
EXTRACT = os.path.join(TOOL_ROOT, "cli", "extract_test.py")
CAN_DELETE = os.path.join(TOOL_ROOT, "cli", "can_delete.py")

# apply_recipe.py belongs to sdtools, not here. It is found on PATH, or under
# the `sdtools` variable's cli/ directory, by resolve_tool below.
APPLY_RECIPE = "apply_recipe.py"


def resolve_tool(name):
    """The path of a tool that belongs to sdtools, or a setup error.

    A name with a directory in it is taken as given. A bare name is looked up
    on PATH first, then under `$sdtools/cli`, the same way the store, data and
    hermes variables name the other roots. Failing that, the message names the
    variable, because a machine without sdtools on PATH fails the same way for
    every trial and should say so before the first one.
    """

    if os.sep in name:
        return name
    found = shutil.which(name)
    if found:
        return found
    root = os.environ.get("sdtools")
    if root:
        candidate = os.path.join(root, "cli", name)
        if os.path.isfile(candidate):
            return candidate
    raise RunnerProblem(
        f"cannot find {name}: it belongs to sdtools, which is neither on PATH"
        " nor named by the `sdtools` variable (export sdtools=<its clone>)."
    )

# The tools above start with `#!/usr/bin/env python3`, which picks up whatever
# python the calling shell has first. A screen made before the spack view was
# on its PATH has one that cannot import pandas, so the tool would be found
# and then die on its imports. Start them under the interpreter running this
# file instead: it has already imported this package, so it works.
PYTHON = sys.executable


# A window writes at least this many outputs, whatever its length.
MIN_OUTPUTS = 50
WINDOW_RE = re.compile(r"_(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)ms$")


def outputs_for(window):
    """How many outputs a window writes: at least one per millisecond.

    The parent writes one per millisecond, and the stall limit is set against
    that cadence. A 100 ms window on 50 outputs would write every 2 ms, and a
    run a little slower than the baseline through an expensive stretch is then
    killed as stalled mid-run (findings: the fixed output cadence trap).
    """

    m = WINDOW_RE.search(window)
    if not m:
        raise RunnerProblem(f"{window}: not a window name (<test>_<a>-<b>ms).")
    length_ms = float(m[2]) - float(m[1])
    return max(MIN_OUTPUTS, int(math.ceil(length_ms)))


def python_tool(tool, *arguments):
    """A command for a python tool that ships here, run under this python."""

    return [PYTHON, tool, *arguments]

# `<window>-<YYYY-MM-DD>-<tag>`. The date is when the case was made, so a trial
# resumed the next day must be found by its window and tag alone.
CASE_DATE = r"\d{4}-\d{2}-\d{2}"


class Stop(Exception):
    """A gate closed. The loop ends cleanly rather than failing."""


class RunnerProblem(Exception):
    """Something the runner cannot decide for itself."""


# =============================================================================
# Trials and studies
# =============================================================================
@dataclasses.dataclass(frozen=True)
class Trial:
    """One intended run: a window, a recipe and the knobs moved off it.

    `overrides` is a sorted tuple of pairs rather than a dict so that two
    trials with the same settings hash the same however they were written.
    """

    window: str
    recipe: str
    overrides: tuple = ()
    repeat: int = 1
    rung: int = 0
    note: str = ""
    # The study file's stem. Left out of trial_tag: which file asked for a
    # configuration does not change the configuration.
    study: str = ""

    @property
    def varied(self):
        """What this run deliberately changes, in the index's `varied` form."""

        return "; ".join(f"{key}={value}" for key, value in self.overrides)


def _pairs(overrides, where):
    if not isinstance(overrides, dict):
        raise RunnerProblem(f"{where}: overrides must be a table of knob settings.")
    return tuple(sorted((str(k), _as_text(v)) for k, v in overrides.items()))


def _as_text(value):
    """A knob value as it will be written into BOUT.inp."""

    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def load_space(path):
    """The search space, as `{knob name: entry}`."""

    with open(path, "rb") as handle:
        return tomllib.load(handle).get("knobs", {})


def _canon(value):
    """One spelling for a setting's value, so `LU`, `lu` and ` lu ` agree."""

    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip().lower()


def depends_met(wanted, actual):
    """Whether one `depends` condition holds for the value actually in force.

    `wanted` is the search space's condition: a bool, a name, `not <name>` or
    `<a> or <b>`. `actual` is the value the run would use, or None when nothing
    sets it, which leaves the condition unknown rather than failed.
    Returns True, False or None.
    """

    if actual is None:
        return None
    have, want = _canon(actual), _canon(wanted)
    if want.startswith("not "):
        return have != want[4:].strip()
    return have in [w.strip() for w in want.split(" or ")]


def effective_settings(space, base, overrides):
    """What each knob would be set to: the override, else the recipe, else the
    search space's record of the current recipe. Missing everywhere is None."""

    def value_of(key):
        for name, value in overrides:
            if name == key:
                return value
        if key in base:
            return base[key]
        entry = space.get(key) or {}
        current = entry.get("current")
        # The space writes an unset knob as "unset, so <value>": prose for the
        # code's default, whose value is the entry's own default field.
        if isinstance(current, str) and current.startswith("unset"):
            return entry.get("default")
        return current

    return value_of


def check_overrides(space, overrides, where, base=None):
    """Refuse a knob the search space does not describe, or a value out of range,
    or one whose `depends` conditions the run would not satisfy.

    Checked before anything is generated. A proposal is allowed to be wrong;
    it is not allowed to spend machine time being wrong (design.md section 9).
    `base` is the recipe's settings, `{knob: value}`, against which a knob's
    `depends` is resolved once the overrides are applied on top.
    """

    value_of = effective_settings(space, base or {}, overrides)
    for key, value in overrides:
        entry = space.get(key)
        if entry is None:
            raise RunnerProblem(
                f"{where}: {key} is not in the search space, so no run may set it."
            )
        kind = entry.get("type")
        if kind == "choice" and value not in [str(v) for v in entry.get("values", [])]:
            raise RunnerProblem(
                f"{where}: {key} = {value} is not one of its allowed values"
                f" ({', '.join(str(v) for v in entry.get('values', []))})."
            )
        if kind == "switch" and value not in ("true", "false"):
            raise RunnerProblem(f"{where}: {key} is a switch, so it is true or false.")
        if kind in ("integer", "continuous"):
            low, high = entry.get("range", [None, None])
            try:
                number = float(value)
            except ValueError:
                raise RunnerProblem(
                    f"{where}: {key} = {value} is not a number."
                ) from None
            if low is not None and (number < low or number > high):
                raise RunnerProblem(
                    f"{where}: {key} = {value} is outside its range [{low}, {high}]."
                )
        for needed, wanted in (entry.get("depends") or {}).items():
            actual = value_of(needed)
            if depends_met(wanted, actual) is False:
                raise RunnerProblem(
                    f"{where}: {key} applies only when {needed} = {wanted},"
                    f" and this run would have {needed} = {actual}. The search"
                    " space says the setting cannot take effect, so no run may"
                    " spend time on it."
                )


def load_study(path, campaign, space=None, recipes_dir=None):
    """Read a study file into trials, one per window per repeat.

    A study names a rung and the variants to try on it. The windows and the
    number of repeats come from the campaign's ladder, so a study never
    restates them and cannot contradict them. With `recipes_dir`, each
    variant's overrides are checked against its recipe's settings too.
    """

    with open(path, "rb") as handle:
        data = tomllib.load(handle)

    where = os.path.basename(path)
    stem = os.path.splitext(where)[0]
    variants = data.get("variant")
    if not isinstance(variants, list) or not variants:
        raise RunnerProblem(f"{where}: no [[variant]] entries, so there is nothing to run.")

    default_rung = data.get("study", {}).get("rung", 0)
    trials = []
    for position, entry in enumerate(variants):
        at = f"{where}: [[variant]] {position + 1}"
        number = entry.get("rung", default_rung)
        rung = next((r for r in campaign.rungs if r.number == number), None)
        if rung is None:
            raise RunnerProblem(f"{at}: the campaign's ladder has no rung {number}.")

        overrides = _pairs(entry.get("overrides", {}), at)
        if space is not None:
            recipe_file = rcp.find_recipe(
                entry.get("recipe", campaign.recipe), recipes_dir or DEFAULT_RECIPES
            )
            base = rcp.parse_settings(recipe_file) if recipe_file else {}
            check_overrides(space, overrides, at, base=base)

        windows = entry.get("windows", list(rung.windows))
        unknown = [w for w in windows if w not in rung.windows]
        if unknown:
            raise RunnerProblem(
                f"{at}: {', '.join(unknown)} is not on rung {number}."
            )

        for window in windows:
            for repeat in range(1, rung.repeats + 1):
                trials.append(
                    Trial(
                        window=window,
                        recipe=entry.get("recipe", campaign.recipe),
                        overrides=overrides,
                        repeat=repeat,
                        rung=number,
                        note=entry.get("note", ""),
                        study=stem,
                    )
                )
    return trials


def trial_tag(campaign, trial):
    """A short, stable name for this exact configuration.

    Everything a timing depends on goes in (R17): the window, the recipe with
    its overrides, the build and the core count. Two runs of one configuration
    therefore share a tag and are told apart by the repeat suffix, which makes
    an accidental duplicate and a deliberate repeat different things.

    The slot is left out on purpose. It is which ten cores of an otherwise
    identical machine the run took, and including it would make a resumed trial
    on another slot look like a configuration nobody had tried.
    """

    parts = [
        trial.window,
        trial.recipe,
        ";".join(f"{k}={v}" for k, v in trial.overrides),
        campaign.build["hermes_commit"],
        campaign.build["limiter"],
        str(campaign.build["check_level"]),
        str(campaign.machine["cores_per_run"]),
    ]
    digest = hashlib.sha1("|".join(parts).encode()).hexdigest()[:8]
    return digest if trial.repeat == 1 else f"{digest}-{trial.repeat}"


# =============================================================================
# The runner
# =============================================================================
def find_store(argument=None):
    """The store directory. Never guessed: the wrong store answers every
    question with somebody else's runs."""

    root = argument or os.environ.get("store") or os.environ.get("SOLVER_OPT_STORE")
    if not root:
        raise RunnerProblem(
            "no store: pass --store, or set the `store` environment variable."
        )
    return root


def find_hermes(argument=None):
    """The Hermes-3 checkout that holds the campaign's build directory."""

    root = argument or os.environ.get("hermes") or os.environ.get("HERMES_ROOT")
    if not root:
        raise RunnerProblem(
            "no Hermes-3 checkout: pass --hermes, or set the `hermes`"
            " environment variable."
        )
    return root


class Runner:
    """One campaign, one slot, one trial at a time."""

    def __init__(
        self,
        campaign,
        store_dir=None,
        data_dir=None,
        hermes_dir=None,
        recipes_dir=None,
        slot=None,
        dry_run=False,
        log=None,
    ):
        self.campaign = campaign
        self.store_dir = find_store(store_dir)
        self.data_dir = st.find_data(data_dir)
        self.hermes_dir = hermes_dir
        self.recipes_dir = recipes_dir or DEFAULT_RECIPES
        self.dry_run = dry_run
        self.slot = slot if slot is not None else campaign.machine["slots"][0]
        self._log = log or self._default_log

        self.campaign_dir = os.path.join(
            self.store_dir, "campaigns", campaign.name
        )
        self.index_path = os.path.join(self.campaign_dir, "index.tsv")

        # The index sits beside the config it belongs to. A campaign read from
        # somewhere else would fill an index in a directory nobody is looking
        # at, and the two records would then disagree about what exists.
        held = os.path.abspath(os.path.dirname(campaign.path))
        if held != os.path.abspath(self.campaign_dir):
            raise RunnerProblem(
                f"campaign {campaign.name} is named after {self.campaign_dir}"
                f" but was read from {held}; move it or rename it."
            )
        self.cases_dir = os.path.join(self.data_dir, "cases")
        self.seeds_dir = os.path.join(self.data_dir, "seeds")
        self.parent_dir = os.path.join(self.cases_dir, campaign.parent)

    # --- talking ---------------------------------------------------------
    def _default_log(self, message):
        line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {message}"
        print(line, flush=True)
        if self.dry_run:
            return
        # Output, not record: it goes with the bundles in the data directory,
        # not into the store, whose campaign directories are committed.
        logs = os.path.join(self.data_dir, "logs")
        os.makedirs(logs, exist_ok=True)
        with open(os.path.join(logs, f"{self.campaign.name}-runner.log"), "a") as handle:
            handle.write(line + "\n")

    def say(self, message):
        self._log(message)

    def run_tool(self, command, cwd=None, check=True):
        """Run a tool, echoing it so the same line can be typed by hand."""

        self.say("$ " + " ".join(shlex.quote(word) for word in command))
        if self.dry_run:
            return None
        try:
            result = subprocess.run(command, cwd=cwd)
        except OSError as problem:
            # The tool could not be started at all, which is a fault in the
            # setup and not in this trial: it will fail the same way for every
            # trial that follows. Stop, rather than spend the whole budget on
            # runs that can never be extracted.
            raise Stop(f"cannot run {command[0]}: {problem}") from None
        if check and result.returncode != 0:
            raise RunnerProblem(
                f"{command[0]} failed ({result.returncode}): "
                + " ".join(shlex.quote(w) for w in command)
            )
        return result

    # --- the index is the state ------------------------------------------
    def rows(self):
        rows, _ = idx.read_index(self.index_path)
        return rows

    def rows_for_case(self, case_name):
        key = idx.case_key(case_name)
        return [r for r in self.rows() if idx.case_key(r.get("case_dir", "")) == key]

    def state_of(self, case_name):
        """The state of this case's most recent row, or None if it has none."""

        rows = self.rows_for_case(case_name)
        return rows[-1].get("state") if rows else None

    def slot_hours_spent(self):
        """Machine time this campaign has already spent.

        Every row counts, including failures and timeouts. They cost the same
        hours as a result does, and a budget that ignored them would be spent
        without noticing.
        """

        seconds = 0.0
        for row in self.rows():
            try:
                # elapsed_s is how long the attempt held its slot, and is
                # written for a killed run too; wall_s needs the log's finish
                # stamp, which a killed run never writes.
                seconds += float(row.get("elapsed_s") or row.get("wall_s") or 0.0)
            except ValueError:
                continue
        return seconds / 3600.0

    def free_gb(self):
        target = self.data_dir if os.path.isdir(self.data_dir) else TOOL_ROOT
        return shutil.disk_usage(target).free / GB

    def best_wall(self, window):
        """The fastest completed run of this window, whatever it varied, or None.

        This is the campaign's best time, reported as a result. It is no longer
        what sets the kill cutoff -- see `cutoff_s` for why.
        """

        return self._fastest(window)

    def baseline_wall(self, window):
        """The fastest completed BASELINE run of this window, or None.

        The baseline is the campaign's own recipe with nothing overridden, so
        `varied` is empty. A row that varied something is a different
        configuration and cannot anchor the cutoff, however fast it was.
        """

        return self._fastest(
            window,
            only=lambda row: (
                (row.get("recipe") or "") == self.campaign.recipe
                and not (row.get("varied") or "").strip()
            ),
        )

    def _fastest(self, window, only=None):
        """The shortest completed wall time for this window, or None.

        Only completed runs. A timeout is a lower bound and a crash is not
        about the recipe at all, so letting either set the cutoff would make
        the next run's kill time depend on a number that means nothing.
        """

        times = []
        for row in self.rows():
            if row.get("test") != window:
                continue
            if row.get("outcome") != SCORING_OUTCOME:
                continue
            if only is not None and not only(row):
                continue
            try:
                times.append(float(row.get("wall_s") or ""))
            except ValueError:
                continue
        return min(times) if times else None

    def cutoff_s(self, window):
        """When to kill a run of this window, and why that is the number.

        Anchored on the baseline, not on the fastest run. The fastest run moves
        down as the campaign succeeds, and on 2026-09-21 that killed two valid
        configurations: lag_jacobian=1 came in at 36 s on test4_2.0-3.0ms, so
        the cutoff became 108 s, below the 213 s the baseline itself takes.
        Anchoring on the baseline stops the number moving once it is measured,
        and makes cutoff_factor mean what it sounds like -- how much worse than
        the reference is worth waiting for.
        """

        anchor, what = self.baseline_wall(window), "the baseline"
        if anchor is None:
            # No baseline for this window yet, so the best available time is
            # the only anchor there is. It is still better than no limit.
            anchor, what = self.best_wall(window), "the best"
        if anchor is None:
            return float(self.campaign.limits["max_wall_s"]), "no completed run yet"
        cutoff = anchor * self.campaign.limits["cutoff_factor"]
        capped = min(cutoff, float(self.campaign.limits["max_wall_s"]))
        return capped, f"{self.campaign.limits['cutoff_factor']}x {what} {anchor:.0f} s"

    def require_reachable_disk_budget(self):
        """Raise unless pruning can fire before the disk floor stops the loop.

        The runner prunes dumps only once a campaign's dumps exceed
        `[disk] budget_gb`, and refuses to launch once free space falls below
        `floor_gb`. A budget larger than the space actually available is never
        reached, so nothing is ever pruned and a long campaign dies on the
        floor instead. Checked once, before anything is generated, so the
        failure names the setting rather than arriving hours in.
        """

        budget = self.campaign.disk["budget_gb"]
        floor = self.campaign.disk["floor_gb"]
        headroom = self.free_gb() - floor
        if budget <= headroom:
            return
        raise Stop(
            f"[disk] budget_gb is {budget:.0f} GB but only {headroom:.0f} GB"
            f" can be used on {self.data_dir} before the {floor:.0f} GB floor,"
            " so pruning would never fire. Lower budget_gb below that."
        )

    # --- gates ------------------------------------------------------------
    def check_gates(self):
        """Approval, budget and disk. Raises Stop when the loop must end."""

        self.campaign.require_approval()

        spent = self.slot_hours_spent()
        if spent >= self.campaign.slot_hours:
            raise Stop(
                f"budget spent: {spent:.1f} of {self.campaign.slot_hours:.1f}"
                " approved slot-hours are used."
            )

        free = self.free_gb()
        floor = self.campaign.disk["floor_gb"]
        if free < floor:
            raise Stop(
                f"disk floor reached: {free:.0f} GB free on {self.data_dir},"
                f" below the {floor:.0f} GB floor."
            )

    # --- the steps --------------------------------------------------------
    def case_name(self, trial, when=None):
        day = (when or datetime.date.today()).isoformat()
        return f"{trial.window}-{day}-{trial_tag(self.campaign, trial)}"

    def existing_case(self, trial):
        """A case already made for this trial, whatever day it was made on."""

        tag = trial_tag(self.campaign, trial)
        pattern = re.compile(
            rf"^{re.escape(trial.window)}-{CASE_DATE}-{re.escape(tag)}$"
        )
        if not os.path.isdir(self.cases_dir):
            return None
        for name in sorted(os.listdir(self.cases_dir)):
            if pattern.match(name):
                return name
        return None

    def is_finished(self, case_name):
        """True if this case already holds a run that reached the end."""

        log = os.path.join(self.cases_dir, case_name, "BOUT.log.0")
        if not os.path.exists(log):
            return False
        with open(log, errors="replace") as handle:
            return "Run finished at" in handle.read()

    def write_recipe(self, trial, case_path):
        """A copy of the named recipe carrying the overrides and the diagnostics.

        Written into the case rather than edited in place afterwards, so the
        whole `[solver]` and `[petsc]` block is applied once and any later
        difference from it is a real deviation (perftest/recipe.py).
        """

        named = os.path.join(self.recipes_dir, f"{trial.recipe}.txt")
        if not os.path.exists(named):
            raise RunnerProblem(f"no recipe file for {trial.recipe} at {named}")
        settings = rcp.parse_settings(named)
        for key, _ in trial.overrides:
            twin = rcp.shadowed(settings, key)
            if twin:
                # Refused before anything is generated. Writing the override
                # would produce a case whose recipe says one thing and whose
                # solver does another, and the row would carry the value that
                # was not used.
                raise RunnerProblem(
                    f"{trial.recipe} sets {twin}, which BOUT++ reads after"
                    f" {key} and which would override it. Give the setting one"
                    " home in the recipe before varying it."
                )

        with open(named) as handle:
            lines = handle.read().splitlines()

        for key, value in trial.overrides + rcp.DIAGNOSTICS:
            section, option = key.split(":", 1)
            lines = _set_option(lines, section, option, value, key)

        out = os.path.join(case_path, "recipe-applied.txt")
        if not self.dry_run:
            with open(out, "w") as handle:
                handle.write("\n".join(lines) + "\n")
        return out

    def prepare(self, trial):
        """Generate the case and apply the recipe. Returns the case name."""

        case_name = self.existing_case(trial)
        if case_name and not self.is_finished(case_name):
            # Never relaunch into a half-run case: the new run would write over
            # the old dumps and logs, and the case would be a mix of two.
            self.say(f"{case_name}: previous attempt was interrupted, starting again")
            if not self.dry_run:
                shutil.rmtree(os.path.join(self.cases_dir, case_name))
            case_name = None
        if case_name:
            return case_name

        case_name = self.case_name(trial)
        case_path = os.path.join(self.cases_dir, case_name)
        self.run_tool(
            python_tool(
                MAKE_WINDOW,
                trial.window,
                self.parent_dir,
                case_path,
                "--seeds",
                self.seeds_dir,
                "--nout",
                str(outputs_for(trial.window)),
            )
        )
        self.run_tool(
            [resolve_tool(APPLY_RECIPE), case_path, self.write_recipe(trial, case_path)]
        )
        return case_name

    def open_row(self, trial, case_name):
        """Append this run's declared intent. Measurement comes later.

        Only the intent columns are written. Declaring what the run should have
        been built from would hide the disagreement if it was not, and that
        disagreement is the finding the index exists to catch.
        """

        if self.state_of(case_name) == idx.STATE_PLANNED:
            return
        lock = idx.lock_index(self.index_path)
        rows, columns = idx.read_index(self.index_path)
        row = {c: "" for c in columns}
        row.update(
            {
                "project": idx.PROJECT_DEFAULT,
                "case_dir": case_name,
                "state": idx.STATE_PLANNED,
                "test": trial.window,
                "recipe": trial.recipe,
                "varied": trial.varied,
                "study": trial.study,
                "epoch": self.campaign.epoch,
                "slot": str(self.slot),
                "note": self.note_for(trial),
            }
        )
        rows.append(row)
        self.say(f"{case_name}: row opened as {idx.STATE_PLANNED}")
        if not self.dry_run:
            idx.write_index(self.index_path, rows, columns)
        idx.unlock_index(lock)

    def note_for(self, trial):
        text = (
            f"Campaign {self.campaign.name}, rung {trial.rung}. "
            f"{trial.recipe} on {trial.window}"
        )
        if trial.overrides:
            text += " with " + trial.varied
        if trial.repeat > 1:
            text += f", repeat {trial.repeat}"
        return text + f". Set up and run by the campaign runner. {trial.note}".rstrip()

    def update_row(self, case_name, overwrite=(), **changes):
        """Write into the most recent row for this case, blank cells only.

        Blank cells only, for the same reason the extractor works that way: a
        value already in the index was either declared by a person or measured
        from the run, and the runner is not better informed than either.
        `state` is the exception, because moving a row through its lifecycle is
        the runner's job.

        `overwrite` names the columns this one call may replace anyway. It
        exists for the single fact the runner holds and the record cannot: a
        run it stopped itself leaves a log identical to a run that died, so
        the extractor reads a deliberate stop as a crash. Name a column here
        only where the runner is the authority on it.
        """

        lock = idx.lock_index(self.index_path)
        rows, columns = idx.read_index(self.index_path)
        key = idx.case_key(case_name)
        positions = [
            i for i, r in enumerate(rows)
            if idx.case_key(r.get("case_dir", "")) == key
        ]
        if not positions:
            idx.unlock_index(lock)
            return False
        row = rows[positions[-1]]
        for name, value in changes.items():
            if value in (None, ""):
                continue
            if (name == "state" or name in overwrite
                    or not (row.get(name) or "").strip()):
                row[name] = str(value).replace("\t", " ")
        if not self.dry_run:
            idx.write_index(self.index_path, rows, columns)
        idx.unlock_index(lock)
        return True

    def launch(self, case_name, cutoff):
        """Run it, watched. Returns (kill reason or None, wall seconds).

        Watched on the dumps rather than the log, because a stalling run keeps
        writing solver-step lines indefinitely while its output steps stop.
        """

        case_path = os.path.join(self.cases_dir, case_name)
        exe = os.path.join(
            find_hermes(self.hermes_dir),
            self.campaign.build["build_dir"],
            "hermes-3",
        )
        command = [
            word.format(
                slot=self.slot,
                exe=exe,
                case=case_path,
                cores=self.campaign.machine["cores"].get(self.slot, ""),
            )
            for word in self.campaign.machine["launch"]
        ]
        command[0] = resolve_tool(command[0])
        console = os.path.join(case_path, "BOUT.log.console")
        self.say(
            "$ " + " ".join(shlex.quote(w) for w in command) + f" > {console}"
        )
        if self.dry_run:
            return None, 0.0

        stall = self.campaign.limits["stall_s"]
        poll = self.campaign.limits["poll_s"]
        started = time.time()
        with open(console, "w") as sink:
            process = subprocess.Popen(
                command,
                cwd=self.cases_dir,
                stdout=sink,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
            try:
                while process.poll() is None:
                    now = time.time()
                    progressed = _last_output_at(case_path) or started
                    if now - progressed > stall:
                        self.say(
                            f"{case_name}: no output step for"
                            f" {(now - progressed) / 60:.0f} min, killing it"
                        )
                        _kill(process)
                        return "stall", now - started
                    if now - started > cutoff:
                        self.say(
                            f"{case_name}: past the cutoff of {cutoff / 60:.0f} min,"
                            " killing it"
                        )
                        _kill(process)
                        return "cutoff", now - started
                    time.sleep(poll)
            except KeyboardInterrupt:
                self.say(f"{case_name}: interrupted, killing it")
                _kill(process)
                return "cancelled", time.time() - started

        took = time.time() - started
        self.say(
            f"{case_name}: exited {process.returncode} after {took / 60:.1f} min"
        )
        return (None if process.returncode == 0 else "failed"), took

    def extract(self, case_name):
        """Extract the bundle and fill the row. True if it validated."""

        command = python_tool(
            EXTRACT,
            os.path.join(self.cases_dir, case_name),
            "--store",
            self.campaign_dir,
            "--recipes",
            self.recipes_dir,
            "--epoch",
            self.campaign.epoch,
            "--conduction",
            self.campaign.build["conduction_method"],
        )
        result = self.run_tool(command, check=False)
        return True if result is None else result.returncode == 0

    # --- retention --------------------------------------------------------
    def dumps_gb(self, case_name):
        pattern = os.path.join(self.cases_dir, case_name, DUMP_GLOB)
        return sum(os.path.getsize(f) for f in glob.glob(pattern)) / GB

    def prune(self):
        """Delete the dumps of old runs once the campaign is over its budget.

        Candidates come from the index and never from listing directories: a
        directory without a row belongs to somebody else's work. Each deletion
        is gated by can_delete.py, which is the tool that knows a parent run's
        dumps are also the only source of its seeds.
        """

        recorded = [
            r for r in self.rows() if r.get("state") == idx.STATE_RECORDED
        ]
        keep = set(self.campaign.disk["keep"])
        # Spelled out because `recorded[-0:]` is the whole list, which would
        # silently turn "keep none" into "keep everything".
        keep_recent = self.campaign.disk["keep_recent"]
        recent = {
            idx.case_key(r.get("case_dir", ""))
            for r in (recorded[-keep_recent:] if keep_recent else [])
        }

        sizes = {}
        for row in recorded:
            name = idx.case_key(row.get("case_dir", ""))
            if name and name not in sizes:
                sizes[name] = self.dumps_gb(name)
        total = sum(sizes.values())
        budget = self.campaign.disk["budget_gb"]
        if total <= budget:
            return 0

        self.say(f"dumps hold {total:.0f} GB against a {budget:.0f} GB budget")
        freed = 0
        for row in recorded:
            if total <= budget:
                break
            name = idx.case_key(row.get("case_dir", ""))
            if not name or name in keep or name in recent or not sizes.get(name):
                continue
            case_path = os.path.join(self.cases_dir, name)
            gate = self.run_tool(
                python_tool(CAN_DELETE, case_path, "--store", self.campaign_dir),
                check=False,
            )
            if gate is not None and gate.returncode != 0:
                self.say(f"{name}: kept, can_delete.py refused")
                continue
            self.say(f"{name}: deleting {sizes[name]:.0f} GB of dumps")
            if not self.dry_run:
                for path in glob.glob(os.path.join(case_path, DUMP_GLOB)):
                    os.remove(path)
            total -= sizes[name]
            freed += 1
        return freed

    # --- one trial --------------------------------------------------------
    def do_trial(self, trial):
        """Everything for one trial. Returns the case name, or None if skipped."""

        existing = self.existing_case(trial)
        if existing and self.state_of(existing) in SETTLED:
            self.say(f"{existing}: already {self.state_of(existing)}, skipping")
            return None

        self.check_gates()

        case_name = self.prepare(trial)
        self.open_row(trial, case_name)

        if self.is_finished(case_name):
            # Resuming onto a run that already finished: record it, never
            # repeat it. The machine time is already spent.
            self.say(f"{case_name}: already holds a finished run, extracting only")
            kill_reason = None
        else:
            cutoff, why = self.cutoff_s(trial.window)
            self.say(
                f"{case_name}: launching on slot {self.slot}, cutoff"
                f" {cutoff / 60:.0f} min ({why})"
            )
            kill_reason, _ = self.launch(case_name, cutoff)

        ok = self.extract(case_name)

        if not ok:
            # extract_test.py writes the row as recorded before deciding whether
            # it validated, so a failed extraction would otherwise leave a bad
            # row looking like a result.
            self.update_row(
                case_name,
                state=idx.STATE_CANCELLED,
                note="Extraction did not validate; case kept for inspection.",
            )
            self.say(f"{case_name}: extraction did not validate, case kept")
            return case_name

        if kill_reason in KILL_OUTCOME:
            # The extractor has already written an outcome, and for a run the
            # runner killed that outcome is crashed: the log stops mid-step
            # and cannot say who stopped it. Correct it, because only the
            # runner knows the stop was deliberate. A run that died on its
            # own is left alone below, where the extractor's reading stands.
            self.update_row(
                case_name,
                outcome=KILL_OUTCOME[kill_reason],
                overwrite=("outcome",),
            )
        elif kill_reason == "failed":
            # The launcher exited non-zero and the log did not say why, so this
            # is a death outside the solver. It is a row with no usable timing,
            # never a bad score for the recipe.
            self.update_row(case_name, outcome="crashed")

        self.prune()
        self.say(f"{case_name}: done")
        return case_name

    def run(self, trials):
        """Every trial that has no result yet. Returns how many ran."""

        # Before anything is generated, not only before each launch. A campaign
        # with no approval must say so once and stop, rather than report the
        # same refusal against every trial in turn.
        self.campaign.require_approval()
        cp.check_machine(self.campaign)
        self.require_reachable_disk_budget()

        self.say(
            f"campaign {self.campaign.name}: {len(trials)} trials, slot"
            f" {self.slot}, {self.slot_hours_spent():.1f} of"
            f" {self.campaign.slot_hours:.1f} slot-hours spent"
        )
        done = skipped = errored = 0
        stopped = None
        for trial in trials:
            try:
                if self.do_trial(trial) is None:
                    skipped += 1
                else:
                    done += 1
            except Stop as stop:
                stopped = str(stop)
                self.say(f"stopping: {stop}")
                break
            except ApprovalMissing:
                # Never swallowed as one trial's problem: it is the whole
                # campaign's permission, and it can be withdrawn mid-run by
                # editing the file.
                raise
            except Exception as problem:  # one bad trial must not end the campaign
                errored += 1
                self.say(f"{trial.window}: ERROR {problem}")
        # Every trial is accounted for, because "0 trial(s) run" had once been
        # printed after four Hermes runs whose extraction failed, and a reader
        # of that log would conclude the slot time was still free.
        summary = (
            f"campaign {self.campaign.name}: {len(trials)} trial(s),"
            f" {done} recorded, {skipped} already settled, {errored} errored"
        )
        if stopped is not None:
            summary += f", stopped early ({stopped})"
        self.say(summary)
        return done

    def status(self):
        """One line per state, for a person deciding whether to run more."""

        counts = {}
        for row in self.rows():
            counts[row.get("state", "")] = counts.get(row.get("state", ""), 0) + 1
        return {
            "rows": len(self.rows()),
            "states": counts,
            "slot_hours_spent": self.slot_hours_spent(),
            "slot_hours_budget": self.campaign.slot_hours,
            "free_gb": self.free_gb(),
        }


# =============================================================================
# Small helpers
# =============================================================================
def _last_output_at(case_path):
    """When this run last wrote an output step, or None before the first one."""

    times = [
        os.path.getmtime(path)
        for path in glob.glob(os.path.join(case_path, DUMP_GLOB))
    ]
    return max(times) if times else None


def _kill(process):
    """Stop the whole process group, politely and then not."""

    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(os.getpgid(process.pid), sig)
        except (ProcessLookupError, PermissionError):
            return
        for _ in range(15):
            if process.poll() is not None:
                return
            time.sleep(2)


def _set_option(lines, section, option, value, key):
    """Set one `option = value` inside one section of a recipe file.

    Replaced in place where it exists and inserted under the section header
    where it does not, so the recipe stays readable and BOUT++ never sees the
    same option twice.
    """

    out = []
    current = None
    written = False
    seen_section = False
    for line in lines:
        stripped = line.split("#")[0].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if current == section and not written:
                out.append(f"{option} = {value}")
                written = True
            current = stripped[1:-1].strip().lower()
            seen_section = seen_section or current == section
            out.append(line)
            continue
        if current == section and not written and "=" in stripped:
            name = stripped.split("=", 1)[0].strip()
            if name == option:
                out.append(f"{option} = {value}")
                written = True
                continue
        out.append(line)

    if not written and seen_section:
        out.append(f"{option} = {value}")
        written = True
    if not written:
        raise RunnerProblem(
            f"the recipe has no [{section}] section, so {key} cannot be set."
        )
    return out
