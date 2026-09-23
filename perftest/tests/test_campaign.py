"""Tests for the campaign config and the runner's refusals (R23).

Four things here are worth a test, and they are the four that cost real time
when they go wrong.

A mistyped config that loads anyway spends machine hours against a budget
nobody meant. An approval that is absent or half-written must stop the runner,
because the user's approval of a campaign is what authorises every launch
inside it (R33). A budget or a disk floor that is not enforced is not a limit.
And a loop that is not resumable relaunches finished work, which on the full
window is hours of the machine's time for a result already in the index.

The launching, extraction and watching are not tested here: they are
subprocesses of tools that carry their own tests, and the runner's job is to
call them in the right order under the right conditions.
"""

import datetime
import glob
import os
import socket
import sys

import pytest

from perftest import campaign as cp
from perftest import index as idx
from perftest import recipe as rcp
from perftest import runner as rn


# =============================================================================
# Fixtures: the smallest campaign that is valid
# =============================================================================
GOOD = """\
[campaign]
name = "atest"
goal = "Check the runner refuses what it should."
test = "test2"
parent = "test2_0.0-100.0ms-20260919-201426"
epoch = "2026-09-neutlim"

[build]
hermes_commit = "ef2ef9dd"
hermes_branch = "neutlim-lagging"
build_dir = "build-va-neutlim"
limiter = "VanAlbada"
conduction_method = "Harmonic"
check_level = 2

[baseline]
recipe = "SNES-MUMPS-3"

[search]
space = "search-space.toml"

[[ladder]]
rung = 0
windows = ["test2_5.0-5.5ms", "test2_30.0-30.5ms"]
noise_bound = 0.15
repeats = 1

[[ladder]]
rung = 1
windows = ["test2_5.0-7.0ms"]
noise_bound = 0.10
repeats = 1

[limits]
cutoff_factor = 3.0
stall_s = 1800
max_wall_s = 21600
poll_s = 20

[budget]
slot_hours = 10.0

[disk]
budget_gb = 200.0
floor_gb = 50.0
keep_recent = 5
keep = []

[correctness]
window_tolerance = 0.2
endpoint_tolerance = 0.05
quantities = ["ne_target_max", "te_target_max"]

[machine]
name = "HOSTNAME"
cores_per_run = 10
slots = [1, 2, 3]
launch = ["sdrun.py", "-s={slot}", "-p={exe}", "-d={case}", "-y", "-restart"]

[approval]
approved_by = "the user"
approved_on = "2026-09-20"
slot_hours = 10.0
scope = "this ladder"
"""


def write_campaign(tmp_path, text=GOOD, name="atest"):
    """A campaign file where the runner expects one: <store>/campaigns/<name>.

    The machine name is this host's, so the campaign may run here; a test
    about a foreign host writes another name itself.
    """

    folder = tmp_path / "store" / "campaigns" / name
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "campaign.toml"
    path.write_text(text.replace("HOSTNAME", socket.gethostname()))
    return str(path)


def without(text, table):
    """The same file with one table deleted, for the missing-table cases."""

    lines, out, dropping = text.splitlines(), [], False
    for line in lines:
        if line.startswith("["):
            dropping = line.strip() in (f"[{table}]", f"[[{table}]]")
        if not dropping:
            out.append(line)
    return "\n".join(out) + "\n"


@pytest.fixture
def runner(tmp_path, monkeypatch):
    """A runner over an empty index, with the disk and the clock in hand.

    Free space is fixed here so no test depends on what this machine has
    today. A test about the disk patches it again with its own number.
    """

    monkeypatch.setattr(rn.Runner, "free_gb", lambda self: 500.0)
    path = write_campaign(tmp_path)
    made = rn.Runner(
        cp.load_campaign(path),
        store_dir=str(tmp_path / "store"),
        data_dir=str(tmp_path / "data"),
        hermes_dir=str(tmp_path / "hermes"),
        log=lambda message: None,
    )
    (tmp_path / "data" / "cases").mkdir(parents=True)
    return made


# =============================================================================
# The config validates on load
# =============================================================================
def test_good_campaign_loads():
    """The shipped example is valid, so it is a usable starting point."""

    example = os.path.join(rn.TOOL_ROOT, "campaign.example.toml")
    loaded = cp.load_campaign(example)
    assert loaded.rungs[0].number == 0
    assert loaded.rung_for(loaded.rungs[1].windows[0]).noise_bound == 0.10


def test_missing_table_names_itself(tmp_path):
    path = write_campaign(tmp_path, without(GOOD, "budget"))
    with pytest.raises(cp.CampaignProblem, match=r"\[budget\] is missing"):
        cp.load_campaign(path)


def test_noise_bound_as_a_percentage_is_refused(tmp_path):
    """15 rather than 0.15 is the mistake this catches."""

    path = write_campaign(tmp_path, GOOD.replace("noise_bound = 0.15", "noise_bound = 15"))
    with pytest.raises(cp.CampaignProblem, match="noise_bound"):
        cp.load_campaign(path)


def test_window_name_off_the_grid_is_refused(tmp_path):
    path = write_campaign(tmp_path, GOOD.replace("test2_5.0-5.5ms", "test2_5-5.5ms"))
    with pytest.raises(cp.CampaignProblem, match="test2_5-5.5ms"):
        cp.load_campaign(path)


def test_one_window_on_two_rungs_is_refused(tmp_path):
    path = write_campaign(tmp_path, GOOD.replace('["test2_5.0-7.0ms"]', '["test2_5.0-5.5ms"]'))
    with pytest.raises(cp.CampaignProblem, match="belongs to one rung"):
        cp.load_campaign(path)


def test_disk_floor_above_the_budget_is_refused(tmp_path):
    path = write_campaign(tmp_path, GOOD.replace("floor_gb = 50.0", "floor_gb = 300.0"))
    with pytest.raises(cp.CampaignProblem, match="floor_gb"):
        cp.load_campaign(path)


def test_correctness_quantity_must_be_an_index_column(tmp_path):
    path = write_campaign(tmp_path, GOOD.replace('"te_target_max"', '"te_at_the_target"'))
    with pytest.raises(cp.CampaignProblem, match="te_at_the_target"):
        cp.load_campaign(path)


def test_launch_command_must_name_the_case(tmp_path):
    path = write_campaign(tmp_path, GOOD.replace('"-d={case}", ', ""))
    with pytest.raises(cp.CampaignProblem, match="case"):
        cp.load_campaign(path)


def test_machine_name_is_required(tmp_path):
    path = write_campaign(tmp_path, GOOD.replace('name = "HOSTNAME"\n', ""))
    with pytest.raises(cp.CampaignProblem, match=r"\[machine\].*name"):
        cp.load_campaign(path)


def test_a_campaign_refuses_a_foreign_host(tmp_path):
    """Two machines on one campaign would each repeat the other's trials."""

    path = write_campaign(tmp_path, GOOD.replace("HOSTNAME", "elsewhere"))
    campaign = cp.load_campaign(path)
    with pytest.raises(cp.CampaignProblem, match="elsewhere"):
        cp.check_machine(campaign)
    cp.check_machine(campaign, hostname="elsewhere")


def test_cores_come_one_per_slot(tmp_path):
    pinned = GOOD.replace(
        'launch = ["sdrun.py", "-s={slot}", "-p={exe}", "-d={case}", "-y", "-restart"]',
        'cores = ["0-9", "10-19", "20-29"]\n'
        'launch = ["taskset", "-c", "{cores}", "mpirun", "{exe}", "-d", "{case}"]',
    )
    loaded = cp.load_campaign(write_campaign(tmp_path, pinned))
    assert loaded.machine["cores"] == {1: "0-9", 2: "10-19", 3: "20-29"}

    short = pinned.replace('cores = ["0-9", "10-19", "20-29"]', 'cores = ["0-9"]')
    with pytest.raises(cp.CampaignProblem, match="1 core sets for 3 slots"):
        cp.load_campaign(write_campaign(tmp_path, short))

    unpinned = pinned.replace('cores = ["0-9", "10-19", "20-29"]\n', "")
    with pytest.raises(cp.CampaignProblem, match="no\n? ?cores list|gives no"):
        cp.load_campaign(write_campaign(tmp_path, unpinned))

    unused = GOOD.replace('slots = [1, 2, 3]\n', 'slots = [1, 2, 3]\ncores = ["0-9", "10-19", "20-29"]\n')
    with pytest.raises(cp.CampaignProblem, match="never names"):
        cp.load_campaign(write_campaign(tmp_path, unused))


def test_a_tool_is_found_under_sdtools_when_not_on_path(tmp_path, monkeypatch):
    """A fresh machine has no sdtools on PATH; the variable names its clone."""

    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.delenv("sdtools", raising=False)
    with pytest.raises(rn.RunnerProblem, match="sdtools"):
        rn.resolve_tool("apply_recipe.py")

    clone = tmp_path / "sdtools" / "cli"
    clone.mkdir(parents=True)
    (clone / "apply_recipe.py").write_text("")
    monkeypatch.setenv("sdtools", str(tmp_path / "sdtools"))
    assert rn.resolve_tool("apply_recipe.py") == str(clone / "apply_recipe.py")
    assert rn.resolve_tool("/abs/tool.py") == "/abs/tool.py"


# =============================================================================
# Approval: the runner refuses to start without one
# =============================================================================
def test_missing_approval_still_loads(tmp_path):
    """Loading and launching are different questions, so a campaign still
    being written can be read."""

    loaded = cp.load_campaign(write_campaign(tmp_path, without(GOOD, "approval")))
    assert loaded.approval is None


def test_missing_approval_refuses_to_launch(tmp_path):
    loaded = cp.load_campaign(write_campaign(tmp_path, without(GOOD, "approval")))
    with pytest.raises(cp.ApprovalMissing, match="no .approval. table"):
        loaded.require_approval()


def test_incomplete_approval_refuses_to_launch(tmp_path):
    text = GOOD.replace('approved_by = "the user"\n', "")
    loaded = cp.load_campaign(write_campaign(tmp_path, text))
    with pytest.raises(cp.ApprovalMissing, match="incomplete"):
        loaded.require_approval()


def test_approval_date_must_be_a_date(tmp_path):
    text = GOOD.replace('approved_on = "2026-09-20"', 'approved_on = "last Tuesday"')
    loaded = cp.load_campaign(write_campaign(tmp_path, text))
    with pytest.raises(cp.ApprovalMissing, match="not a date"):
        loaded.require_approval()


def test_budget_may_not_exceed_what_was_approved(tmp_path):
    """The approval is for a number of slot-hours, so raising the budget
    afterwards is a campaign the user has not approved."""

    text = GOOD.replace("[budget]\nslot_hours = 10.0", "[budget]\nslot_hours = 40.0")
    loaded = cp.load_campaign(write_campaign(tmp_path, text))
    with pytest.raises(cp.ApprovalMissing, match="exceeds its approval"):
        loaded.require_approval()


def test_approval_is_its_own_exception_type():
    """The caller reports a missing approval plainly, not as a broken file."""

    assert issubclass(cp.ApprovalMissing, cp.CampaignProblem)


# =============================================================================
# The gates: budget and disk
# =============================================================================
def add_row(runner, **values):
    rows, columns = idx.read_index(runner.index_path)
    row = {c: "" for c in columns}
    row.update(values)
    rows.append(row)
    idx.write_index(runner.index_path, rows, columns)


def test_gates_pass_on_an_empty_campaign(runner, monkeypatch):
    monkeypatch.setattr(rn.Runner, "free_gb", lambda self: 500.0)
    runner.check_gates()


def test_spent_budget_stops_the_loop(runner, monkeypatch):
    monkeypatch.setattr(rn.Runner, "free_gb", lambda self: 500.0)
    add_row(runner, case_dir="a", state=idx.STATE_RECORDED, wall_s="21600")
    add_row(runner, case_dir="b", state=idx.STATE_RECORDED, wall_s="18000")
    assert runner.slot_hours_spent() == pytest.approx(11.0)
    with pytest.raises(rn.Stop, match="budget spent"):
        runner.check_gates()


def test_failed_runs_count_against_the_budget(runner):
    """A crash costs the same hours as a result, so it is not free."""

    add_row(runner, case_dir="a", state=idx.STATE_CANCELLED,
            outcome="crashed", wall_s="3600")
    assert runner.slot_hours_spent() == pytest.approx(1.0)


def test_a_window_writes_at_least_one_output_per_millisecond():
    assert rn.outputs_for("test4_3.0-3.2ms") == 50
    assert rn.outputs_for("test4_2.0-3.0ms") == 50
    assert rn.outputs_for("test4_0.0-100.0ms") == 100
    assert rn.outputs_for("test2_4.0-64.5ms") == 61
    with pytest.raises(rn.RunnerProblem, match="not a window name"):
        rn.outputs_for("test4_full")


def test_a_killed_run_charges_the_time_it_held_the_slot(runner):
    """A killed run writes no finish stamp, so wall_s is blank; elapsed_s,
    from the dump's clock, is what it cost and what the budget must count."""

    add_row(runner, case_dir="k", state=idx.STATE_RECORDED,
            outcome="timeout", wall_s="", elapsed_s="7200")
    add_row(runner, case_dir="c", state=idx.STATE_RECORDED,
            outcome="completed", wall_s="3600", elapsed_s="3600")
    assert runner.slot_hours_spent() == pytest.approx(3.0)


def test_index_writes_are_serialised(tmp_path):
    """Two writers on one index: the lock makes the second wait for the first,
    so no rewrite can replace a version it never read."""

    import multiprocessing

    path = str(tmp_path / "index.tsv")

    def append(name):
        lock = idx.lock_index(path)
        rows, columns = idx.read_index(path)
        rows.append({"case_dir": name})
        idx.write_index(path, rows, columns)
        idx.unlock_index(lock)

    workers = [multiprocessing.Process(target=append, args=(f"r{i}",)) for i in range(12)]
    for w in workers:
        w.start()
    for w in workers:
        w.join()
    rows, _ = idx.read_index(path)
    assert sorted(r["case_dir"] for r in rows) == sorted(f"r{i}" for i in range(12))


def test_disk_floor_stops_the_loop(runner, monkeypatch):
    monkeypatch.setattr(rn.Runner, "free_gb", lambda self: 10.0)
    with pytest.raises(rn.Stop, match="disk floor"):
        runner.check_gates()


def test_a_crash_never_sets_the_cutoff(runner):
    """A crashed or timed-out run is not a time, so it cannot shorten the
    cutoff for every run after it."""

    add_row(runner, case_dir="a", test="test2_5.0-5.5ms", outcome="crashed",
            wall_s="60", state=idx.STATE_RECORDED)
    add_row(runner, case_dir="b", test="test2_5.0-5.5ms", outcome="timeout",
            wall_s="90", state=idx.STATE_RECORDED)
    assert runner.best_wall("test2_5.0-5.5ms") is None
    cutoff, why = runner.cutoff_s("test2_5.0-5.5ms")
    assert cutoff == 21600.0 and "no completed run" in why

    add_row(runner, case_dir="c", test="test2_5.0-5.5ms", outcome="completed",
            wall_s="1000", state=idx.STATE_RECORDED)
    cutoff, why = runner.cutoff_s("test2_5.0-5.5ms")
    assert cutoff == pytest.approx(3000.0)


def test_a_fast_variant_never_shortens_the_cutoff(runner):
    """The cutoff anchors on the baseline, so a configuration that happens to
    be very fast cannot push the kill time below what a normal one needs.

    On 2026-09-21 lag_jacobian=1 ran test4_2.0-3.0ms in 36 s against the
    baseline's 213 s. Anchored on the fastest run, the cutoff fell to 108 s and
    killed the next two configurations -- and would have killed the baseline.
    """

    add_row(runner, case_dir="base", test="test2_5.0-5.5ms", outcome="completed",
            recipe="SNES-MUMPS-3", varied="", wall_s="213",
            state=idx.STATE_RECORDED)
    add_row(runner, case_dir="fast", test="test2_5.0-5.5ms", outcome="completed",
            recipe="SNES-MUMPS-3", varied="solver:lag_jacobian=1", wall_s="36",
            state=idx.STATE_RECORDED)

    assert runner.best_wall("test2_5.0-5.5ms") == pytest.approx(36.0)
    assert runner.baseline_wall("test2_5.0-5.5ms") == pytest.approx(213.0)

    cutoff, why = runner.cutoff_s("test2_5.0-5.5ms")
    assert cutoff == pytest.approx(639.0)
    assert "baseline" in why
    # The baseline's own time must survive its own cutoff, or the reference
    # every result is read against could never be measured again.
    assert cutoff > 213.0


def test_the_best_anchors_the_cutoff_until_a_baseline_exists(runner):
    """A window whose baseline has not run yet still gets a limit."""

    add_row(runner, case_dir="v", test="test2_5.0-5.5ms", outcome="completed",
            recipe="SNES-MUMPS-3", varied="solver:lag_jacobian=1", wall_s="100",
            state=idx.STATE_RECORDED)
    assert runner.baseline_wall("test2_5.0-5.5ms") is None
    cutoff, why = runner.cutoff_s("test2_5.0-5.5ms")
    assert cutoff == pytest.approx(300.0) and "the best" in why


def test_a_baseline_of_another_recipe_does_not_anchor(runner):
    """`varied` empty is not enough: the row must be the campaign's own
    baseline recipe, or a walk between recipes would anchor the cutoff on
    whichever one happened to be recorded."""

    add_row(runner, case_dir="other", test="test2_5.0-5.5ms", outcome="completed",
            recipe="CVODE-1", varied="", wall_s="900",
            state=idx.STATE_RECORDED)
    assert runner.baseline_wall("test2_5.0-5.5ms") is None


# =============================================================================
# Resumability: the index is the only state
# =============================================================================
def a_trial(window="test2_5.0-5.5ms"):
    return rn.Trial(window=window, recipe="SNES-MUMPS-3",
                    overrides=(("solver:lag_jacobian", "4"),), rung=0)


def make_case(runner, trial, finished, day="2026-09-20"):
    """A case directory on disk, as a previous run of this trial left it."""

    name = runner.case_name(trial, when=datetime.date.fromisoformat(day))
    path = os.path.join(runner.cases_dir, name)
    os.makedirs(path)
    text = "Run started at : x\n" + ("Run finished at : y\n" if finished else "")
    with open(os.path.join(path, "BOUT.log.0"), "w") as handle:
        handle.write(text)
    return name


def test_the_tag_is_stable_and_the_date_is_not(runner):
    """A trial resumed on another day must still be recognised."""

    trial = a_trial()
    first = runner.case_name(trial, when=datetime.date(2026, 9, 20))
    second = runner.case_name(trial, when=datetime.date(2026, 9, 21))
    assert first != second
    assert first.split("-")[-1] == second.split("-")[-1]


def test_repeats_are_not_duplicates(runner):
    """Two runs of one configuration share a tag and differ by the repeat, so
    an accidental duplicate and a deliberate repeat are different things."""

    one = rn.trial_tag(runner.campaign, a_trial())
    two = rn.trial_tag(runner.campaign, dataclasses_replace(a_trial(), repeat=2))
    assert two.startswith(one) and two.endswith("-2")


def dataclasses_replace(trial, **changes):
    import dataclasses

    return dataclasses.replace(trial, **changes)


def test_a_settled_trial_is_not_run_again(runner, monkeypatch):
    trial = a_trial()
    name = make_case(runner, trial, finished=True)
    add_row(runner, case_dir=name, state=idx.STATE_RECORDED,
            test=trial.window, outcome="completed", wall_s="1000")

    monkeypatch.setattr(rn.Runner, "launch", _refuse("launch"))
    monkeypatch.setattr(rn.Runner, "extract", _refuse("extract"))
    assert runner.do_trial(trial) is None


def test_a_finished_case_is_extracted_not_relaunched(runner, monkeypatch):
    """The machine time is already spent, so a resumed run is recorded rather
    than repeated."""

    trial = a_trial()
    name = make_case(runner, trial, finished=True)
    add_row(runner, case_dir=name, state=idx.STATE_PLANNED, test=trial.window)

    monkeypatch.setattr(rn.Runner, "free_gb", lambda self: 500.0)
    monkeypatch.setattr(rn.Runner, "launch", _refuse("launch"))
    monkeypatch.setattr(rn.Runner, "prune", lambda self: 0)
    extracted = []
    monkeypatch.setattr(rn.Runner, "extract",
                        lambda self, case: extracted.append(case) or True)
    assert runner.do_trial(trial) == name
    assert extracted == [name]


def test_an_interrupted_case_is_started_again(runner, monkeypatch):
    """Relaunching into a half-run case would mix two runs in one directory."""

    trial = a_trial()
    name = make_case(runner, trial, finished=False)
    add_row(runner, case_dir=name, state=idx.STATE_PLANNED, test=trial.window)

    monkeypatch.setattr(rn.Runner, "free_gb", lambda self: 500.0)
    prepared = []

    def stub_tool(self, command, cwd=None, check=True):
        # A python tool that ships here is run as `<python> <tool> ...`, so the
        # tool is the first word that is not the interpreter.
        tool = command[1] if command[0] == rn.PYTHON else command[0]
        prepared.append(tool)
        if tool == rn.MAKE_WINDOW:
            os.makedirs(command[4])       # what make_window.py would have made

    monkeypatch.setattr(rn.Runner, "run_tool", stub_tool)
    monkeypatch.setattr(rn.Runner, "launch", lambda self, case, cutoff: (None, 1.0))
    monkeypatch.setattr(rn.Runner, "extract", lambda self, case: True)
    monkeypatch.setattr(rn.Runner, "prune", lambda self: 0)

    runner.do_trial(trial)
    # The half-run case was cleared and made again, so no log of the earlier
    # attempt survives into the directory the new run will write into.
    assert not os.path.exists(os.path.join(runner.cases_dir, name, "BOUT.log.0"))
    assert prepared[0] == rn.MAKE_WINDOW
    assert os.path.basename(prepared[1]) == rn.APPLY_RECIPE


def test_the_row_is_opened_once(runner):
    """Resuming must not open a second row for one case: two open rows for one
    directory is an error the extractor refuses to guess at."""

    trial = a_trial()
    name = make_case(runner, trial, finished=False)
    runner.open_row(trial, name)
    runner.open_row(trial, name)
    rows = runner.rows_for_case(name)
    assert len(rows) == 1
    assert rows[0]["varied"] == "solver:lag_jacobian=4"
    assert rows[0]["test"] == trial.window


def test_a_kill_is_recorded_as_a_timeout(runner, monkeypatch):
    """Cutoff and stall both mean at least this slow, which is evidence."""

    assert rn.KILL_OUTCOME["cutoff"] == "timeout"
    assert rn.KILL_OUTCOME["stall"] == "timeout"
    assert rn.KILL_OUTCOME["cancelled"] == "cancelled"

    trial = a_trial()
    name = make_case(runner, trial, finished=False)
    add_row(runner, case_dir=name, state=idx.STATE_PLANNED, test=trial.window)
    monkeypatch.setattr(rn.Runner, "free_gb", lambda self: 500.0)
    monkeypatch.setattr(rn.Runner, "prepare", lambda self, t: name)
    monkeypatch.setattr(rn.Runner, "launch",
                        lambda self, case, cutoff: ("cutoff", 99.0))
    # The real extractor reads a killed run's log, finds no finish stamp and
    # no error, and writes crashed. Stubbing that out hid the bug this test
    # exists for: the runner's correction was silently dropped.
    def extract_as_crashed(self, case):
        self.update_row(case, outcome="crashed", overwrite=("outcome",))
        return True

    monkeypatch.setattr(rn.Runner, "extract", extract_as_crashed)
    monkeypatch.setattr(rn.Runner, "prune", lambda self: 0)

    runner.do_trial(trial)
    assert runner.rows_for_case(name)[-1]["outcome"] == "timeout"


def test_a_run_that_died_on_its_own_keeps_the_extractor_reading(runner,
                                                                monkeypatch):
    """The runner corrects only what it caused. A launcher that exited by
    itself says nothing the log has not already said better, so a divergence
    the extractor read stands."""

    trial = a_trial()
    name = make_case(runner, trial, finished=False)
    add_row(runner, case_dir=name, state=idx.STATE_PLANNED, test=trial.window)
    monkeypatch.setattr(rn.Runner, "free_gb", lambda self: 500.0)
    monkeypatch.setattr(rn.Runner, "prepare", lambda self, t: name)
    monkeypatch.setattr(rn.Runner, "launch",
                        lambda self, case, cutoff: ("failed", 99.0))

    def extract_as_diverged(self, case):
        self.update_row(case, outcome="diverged", overwrite=("outcome",))
        return True

    monkeypatch.setattr(rn.Runner, "extract", extract_as_diverged)
    monkeypatch.setattr(rn.Runner, "prune", lambda self: 0)

    runner.do_trial(trial)
    assert runner.rows_for_case(name)[-1]["outcome"] == "diverged"


def test_overwrite_names_only_the_columns_it_lists(runner):
    """The blank-cells-only rule still holds for every column not named."""

    add_row(runner, case_dir="a", state=idx.STATE_RECORDED,
            outcome="completed", wall_s="123")
    runner.update_row("a", outcome="timeout", wall_s="999",
                      overwrite=("outcome",))
    row = runner.rows_for_case("a")[-1]
    assert row["outcome"] == "timeout"
    assert row["wall_s"] == "123"


def test_update_row_keeps_what_is_already_there(runner):
    """A measured or declared value is never overwritten by the runner."""

    add_row(runner, case_dir="a", state=idx.STATE_RECORDED, outcome="completed")
    runner.update_row("a", outcome="timeout", state=idx.STATE_CANCELLED)
    row = runner.rows_for_case("a")[-1]
    assert row["outcome"] == "completed"
    assert row["state"] == idx.STATE_CANCELLED


def _refuse(name):
    def refuse(self, *args, **kwargs):
        raise AssertionError(f"{name} must not be called")

    return refuse


# =============================================================================
# Studies: a trial may only move a knob the search space describes
# =============================================================================
STUDY = """\
[study]
name = "lag-jacobian"
question = "Does lagging the Jacobian pay on rung 0?"
rung = 0

[[variant]]
overrides = { "solver:lag_jacobian" = 4 }
note = "half the current"
"""


def write_study(tmp_path, text=STUDY):
    path = tmp_path / "study.toml"
    path.write_text(text)
    return str(path)


def test_a_study_expands_over_the_rung(tmp_path, runner):
    trials = rn.load_study(write_study(tmp_path), runner.campaign)
    assert [t.window for t in trials] == list(runner.campaign.rungs[0].windows)
    assert all(t.recipe == "SNES-MUMPS-3" for t in trials)


def test_a_row_names_the_study_file_that_launched_it(tmp_path, runner):
    """Reports select a study's runs by this column, not by launch time."""

    trial = rn.load_study(write_study(tmp_path), runner.campaign)[0]
    assert trial.study == "study"
    name = make_case(runner, trial, finished=False)
    runner.open_row(trial, name)
    assert runner.rows_for_case(name)[0]["study"] == "study"


def test_an_unknown_knob_is_refused_before_anything_runs(tmp_path, runner):
    space = {"solver:lag_jacobian": {"type": "integer", "range": [1, 20]}}
    text = STUDY.replace("solver:lag_jacobian", "solver:lag_jacobean")
    with pytest.raises(rn.RunnerProblem, match="not in the search space"):
        rn.load_study(write_study(tmp_path, text), runner.campaign, space)


def test_a_value_out_of_range_is_refused(tmp_path, runner):
    space = {"solver:lag_jacobian": {"type": "integer", "range": [1, 20]}}
    text = STUDY.replace("= 4 }", "= 400 }")
    with pytest.raises(rn.RunnerProblem, match="outside its range"):
        rn.load_study(write_study(tmp_path, text), runner.campaign, space)


def test_a_knob_whose_dependency_fails_is_refused(tmp_path, runner):
    """search-space.toml says under which settings a knob applies. A study
    that sets it anyway would spend machine time on a run PETSc ignores."""

    space = {
        "solver:pc_type": {"type": "choice", "values": ["lu", "asm"], "current": "lu"},
        "petsc:pc_factor_mat_solver_type": {
            "type": "choice", "values": ["mumps", "superlu_dist"],
            "depends": {"solver:pc_type": "lu"},
        },
        "solver:pc_asm_overlap": {
            "type": "integer", "range": [0, 4], "depends": {"solver:pc_type": "not lu"},
        },
        "solver:matrix_free_operator": {
            "type": "switch", "depends": {"solver:matrix_free": False},
        },
    }
    # Set alongside asm: the factorisation package is never consumed.
    text = STUDY.replace(
        '{ "solver:lag_jacobian" = 4 }',
        '{ "solver:pc_type" = "asm", "petsc:pc_factor_mat_solver_type" = "superlu_dist" }',
    )
    with pytest.raises(rn.RunnerProblem, match="applies only when solver:pc_type = lu"):
        rn.load_study(write_study(tmp_path, text), runner.campaign, space)

    # The recipe's own value decides when the study leaves the knob alone:
    # pc_type is lu in the recipe, so an asm-only knob cannot apply.
    text = STUDY.replace('{ "solver:lag_jacobian" = 4 }', '{ "solver:pc_asm_overlap" = 2 }')
    with pytest.raises(rn.RunnerProblem, match="not lu"):
        rn.load_study(write_study(tmp_path, text), runner.campaign, space,
                      recipes_dir=os.path.join(rn.TOOL_ROOT, "hermes-perftest", "recipes"))

    # A dependency on a knob nothing sets is unknown, not a refusal.
    text = STUDY.replace('{ "solver:lag_jacobian" = 4 }', '{ "solver:matrix_free_operator" = true }')
    assert rn.load_study(write_study(tmp_path, text), runner.campaign, space)

    # An unset knob is recorded as "unset, so <default>" in the space, which
    # is prose for its default, not a value in its own right.
    space["solver:matrix_free"] = {
        "type": "switch", "default": False, "current": "unset, so false",
    }
    text = STUDY.replace('{ "solver:lag_jacobian" = 4 }', '{ "solver:matrix_free_operator" = false }')
    assert rn.load_study(write_study(tmp_path, text), runner.campaign, space)

    # The "a or b" and boolean forms.
    assert rn.depends_met("lu or ilu", "ILU") is True
    assert rn.depends_met("lu or ilu", "asm") is False
    assert rn.depends_met(False, "false") is True
    assert rn.depends_met("not lu", None) is None


def test_overrides_reach_the_recipe(tmp_path, runner):
    """The override is applied by rewriting the recipe, so the applied block is
    one thing and every later difference from it is a real deviation."""

    recipes = tmp_path / "recipes"
    recipes.mkdir()
    (recipes / "SNES-MUMPS-3.txt").write_text(
        "# SNES-MUMPS-3\n[solver]\ntype = snes\nlag_jacobian = 8\n\n[petsc]\n-pc_type lu\n"
    )
    runner.recipes_dir = str(recipes)
    case = tmp_path / "case"
    case.mkdir()

    written = runner.write_recipe(a_trial(), str(case))
    text = open(written).read()
    assert "lag_jacobian = 4" in text
    assert "lag_jacobian = 8" not in text


def test_an_override_for_an_absent_option_is_added(tmp_path, runner):
    recipes = tmp_path / "recipes"
    recipes.mkdir()
    (recipes / "SNES-MUMPS-3.txt").write_text("[solver]\ntype = snes\n[petsc]\n-pc_type lu\n")
    runner.recipes_dir = str(recipes)
    case = tmp_path / "case"
    case.mkdir()

    text = open(runner.write_recipe(a_trial(), str(case))).read()
    lines = [l.strip() for l in text.splitlines()]
    assert "lag_jacobian = 4" in lines
    assert lines.index("lag_jacobian = 4") < lines.index("[petsc]")


def test_an_unapproved_campaign_launches_nothing(tmp_path, monkeypatch):
    """The refusal comes once, before any case is generated, and not as one
    error per trial."""

    path = write_campaign(tmp_path, without(GOOD, "approval"))
    runner = rn.Runner(
        cp.load_campaign(path),
        store_dir=str(tmp_path / "store"),
        data_dir=str(tmp_path / "data"),
        log=lambda message: None,
    )
    monkeypatch.setattr(rn.Runner, "prepare", _refuse("prepare"))
    with pytest.raises(cp.ApprovalMissing):
        runner.run([a_trial()])


def test_keeping_no_recent_runs_keeps_none(runner, monkeypatch):
    """`keep_recent = 0` must mean none, not all: a slice from -0 is the whole
    list, and that would quietly disable the retention rule."""

    runner.campaign.disk["keep_recent"] = 0
    add_row(runner, case_dir="old", state=idx.STATE_RECORDED)
    monkeypatch.setattr(rn.Runner, "dumps_gb", lambda self, case: 300.0)
    monkeypatch.setattr(rn.Runner, "run_tool",
                        lambda self, command, cwd=None, check=True: None)
    assert runner.prune() == 1


def test_the_tools_that_ship_here_do_not_need_PATH():
    """A screen created before cli/ was added to PATH carries a PATH without
    it, and then every extraction in a campaign fails while the runs go on
    costing machine time. The tools that ship in this repository are therefore
    resolved against it, and this test fails if one is renamed or moved."""

    for tool in (rn.EXTRACT, rn.CAN_DELETE, rn.MAKE_WINDOW):
        assert os.path.isabs(tool)
        assert os.path.isfile(tool), tool
    # apply_recipe.py belongs to sdtools, not here, so it stays a PATH lookup.
    assert rn.APPLY_RECIPE == "apply_recipe.py"


def test_a_tool_that_cannot_start_stops_the_loop(runner, monkeypatch):
    """A tool that cannot be started at all is a fault in the setup, not in
    this trial, so it will fail the same way for every trial that follows."""

    def not_there(command, cwd=None):
        raise FileNotFoundError(2, "No such file or directory", command[0])

    monkeypatch.setattr(rn.subprocess, "run", not_there)
    with pytest.raises(rn.Stop):
        runner.run_tool([rn.EXTRACT, "a-case"], check=False)


def test_a_stop_leaves_the_rest_of_the_budget_unspent(runner, monkeypatch):
    """The alternative, once seen for real, is a campaign that spends every
    trial's machine time and records none of it."""

    attempted = []

    def stop_on_the_first(self, trial):
        attempted.append(trial.window)
        raise rn.Stop("cannot run extract_test.py")

    monkeypatch.setattr(rn.Runner, "do_trial", stop_on_the_first)
    runner.run([a_trial("test2_5.0-5.5ms"), a_trial("test2_30.0-30.5ms")])
    assert attempted == ["test2_5.0-5.5ms"]


def test_the_summary_counts_every_trial(runner, monkeypatch):
    """"0 trial(s) run" was once printed after four Hermes runs whose
    extraction had failed, and a reader of that log would conclude the slot
    time was still free."""

    said = []
    runner._log = said.append
    outcomes = {"test2_5.0-5.5ms": "case-a", "test2_30.0-30.5ms": None}

    def one_of_each(self, trial):
        if trial.window == "test2_1.0-1.5ms":
            raise RuntimeError("extraction fell over")
        return outcomes[trial.window]

    monkeypatch.setattr(rn.Runner, "do_trial", one_of_each)
    runner.run([a_trial(w) for w in
                ("test2_5.0-5.5ms", "test2_30.0-30.5ms", "test2_1.0-1.5ms")])
    summary = [line for line in said if "trial(s)" in line][-1]
    assert "3 trial(s)" in summary
    assert "1 recorded" in summary
    assert "1 already settled" in summary
    assert "1 errored" in summary


def test_the_tools_run_under_this_python(runner, monkeypatch):
    """`#!/usr/bin/env python3` picks up whatever python the calling shell has
    first. A screen made before the spack view was on its PATH has one that
    cannot import pandas, so the extractor would be found and then die on its
    imports."""

    commands = []
    monkeypatch.setattr(rn.Runner, "run_tool",
                        lambda self, command, cwd=None, check=True:
                        commands.append(command))
    runner.extract("a-case")
    assert commands[0][:2] == [rn.PYTHON, rn.EXTRACT]
    assert rn.PYTHON == sys.executable


# =============================================================================
# One home per setting: a [petsc] entry overrides the [solver] one
# =============================================================================
def test_an_override_the_recipe_would_shadow_is_refused(tmp_path, runner):
    """BOUT++ reads [petsc] after it has applied [solver], so a recipe holding
    the same setting twice decides the run by its [petsc] copy. Writing the
    override anyway would produce a case whose recipe says ilu, whose solver
    runs lu, and whose row reports ilu."""

    recipes = tmp_path / "recipes"
    recipes.mkdir()
    (recipes / "SNES-MUMPS-3.txt").write_text(
        "[solver]\ntype = snes\npc_type = lu\n\n[petsc]\npc_type = lu\n"
    )
    runner.recipes_dir = str(recipes)
    case = tmp_path / "case"
    case.mkdir()
    trial = rn.Trial(window="test2_5.0-5.5ms", recipe="SNES-MUMPS-3",
                     overrides=(("solver:pc_type", "ilu"),), rung=0)

    with pytest.raises(rn.RunnerProblem, match="one home"):
        runner.write_recipe(trial, str(case))


def test_the_two_spellings_of_one_setting_are_recognised(tmp_path, runner):
    """The names differ across the two sections, so a literal match is not
    enough: BOUT++'s line_search_type is PETSc's snes_linesearch_type."""

    recipes = tmp_path / "recipes"
    recipes.mkdir()
    (recipes / "SNES-MUMPS-3.txt").write_text(
        "[solver]\ntype = snes\n\n[petsc]\nsnes_linesearch_type = basic\n"
    )
    runner.recipes_dir = str(recipes)
    case = tmp_path / "case"
    case.mkdir()
    trial = rn.Trial(window="test2_5.0-5.5ms", recipe="SNES-MUMPS-3",
                     overrides=(("solver:line_search_type", "bt"),), rung=0)

    with pytest.raises(rn.RunnerProblem, match="one home"):
        runner.write_recipe(trial, str(case))


def test_the_petsc_side_of_a_pair_is_not_refused(tmp_path, runner):
    """It is the side that wins, so setting it is exactly what should happen."""

    recipes = tmp_path / "recipes"
    recipes.mkdir()
    (recipes / "SNES-MUMPS-3.txt").write_text(
        "[solver]\ntype = snes\npc_type = lu\n\n[petsc]\nsnes_linesearch_type = basic\n"
    )
    runner.recipes_dir = str(recipes)
    case = tmp_path / "case"
    case.mkdir()
    trial = rn.Trial(window="test2_5.0-5.5ms", recipe="SNES-MUMPS-3",
                     overrides=(("petsc:snes_linesearch_type", "bt"),), rung=0)

    text = open(runner.write_recipe(trial, str(case))).read()
    assert "snes_linesearch_type = bt" in text


def test_the_search_space_gives_every_setting_one_home():
    """A knob offered under both spellings would let a proposal set the side
    that loses."""

    space = rn.load_space(os.path.join(rn.TOOL_ROOT, "search-space.toml"))
    twinned = [k for k in space if rcp.other_spelling(k) in space]
    assert twinned == []


def test_no_recipe_writes_one_setting_on_both_sides():
    """Every recipe a campaign may name, checked against the same rule the
    runner enforces on overrides."""

    for path in sorted(glob.glob(os.path.join(rn.DEFAULT_RECIPES, "*.txt"))):
        settings = rcp.parse_settings(path)
        clashes = [k for k in settings if rcp.shadowed(settings, k)]
        assert clashes == [], f"{os.path.basename(path)}: {clashes}"


def test_the_ts_path_keeps_its_two_tolerances_apart(tmp_path, runner):
    """Under `type = petsc` BOUT++ spends solver:atol on TSSetTolerances and
    leaves the SNES tolerance to PETSc, so the two names are two settings and
    refusing the override would be wrong."""

    recipes = tmp_path / "recipes"
    recipes.mkdir()
    (recipes / "SNES-MUMPS-3.txt").write_text(
        "[solver]\ntype = petsc\natol = 4e-8\n\n[petsc]\nsnes_atol = 4e-8\n"
    )
    runner.recipes_dir = str(recipes)
    case = tmp_path / "case"
    case.mkdir()
    trial = rn.Trial(window="test2_5.0-5.5ms", recipe="SNES-MUMPS-3",
                     overrides=(("solver:atol", "1e-7"),), rung=0)

    text = open(runner.write_recipe(trial, str(case))).read()
    assert "atol = 1e-7" in text


def test_an_unreachable_disk_budget_stops_before_anything_runs(runner, monkeypatch):
    """A budget bigger than the usable space means pruning never fires, and
    the campaign dies on the floor hours in instead. Caught at the start.

    Found 2026-09-21: budget_gb was 200 on a machine with 92 GB free and a
    50 GB floor, so the prune threshold could not be reached.
    """

    monkeypatch.setattr(rn.Runner, "free_gb", lambda self: 92.0)
    runner.campaign.disk["budget_gb"] = 200.0
    runner.campaign.disk["floor_gb"] = 50.0
    with pytest.raises(rn.Stop, match="budget_gb"):
        runner.require_reachable_disk_budget()

    runner.campaign.disk["floor_gb"] = 20.0
    runner.campaign.disk["budget_gb"] = 40.0
    runner.require_reachable_disk_budget()


def test_the_disk_budget_check_runs_before_any_trial(runner, monkeypatch):
    """It is a gate on the loop, not on each trial, so nothing is generated."""

    monkeypatch.setattr(rn.Runner, "free_gb", lambda self: 92.0)
    runner.campaign.disk["budget_gb"] = 200.0
    runner.campaign.disk["floor_gb"] = 50.0
    made = []
    monkeypatch.setattr(rn.Runner, "prepare", lambda self, t: made.append(t))
    with pytest.raises(rn.Stop, match="budget_gb"):
        runner.run([a_trial()])
    assert made == []
