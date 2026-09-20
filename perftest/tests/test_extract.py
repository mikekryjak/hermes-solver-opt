"""Tests for the perftest extractor (R23).

The reductions here decide numbers that go into the results store and outlive
the dumps they came from, so the thing worth testing is not that they run but
that they exclude guard cells. A guard cell holds whatever was in that memory
-- on real runs up to 1e15 against an interior value of 1e-3 (F20) -- so a
reduction that includes them reports which field has the worst garbage, and
reports it as a physics result.

The synthetic dataset below is the smallest one xhermes' `clear_guards` will
accept: a single-null topology, two radial guard cells each side, no poloidal
guards.
"""

import numpy as np
import pytest
import xarray as xr

import xhermes  # noqa: F401 -- registers the .hermes accessors

from perftest.extract import (
    OUTCOMES,
    Report,
    _cutoff_seconds,
    _cvode_counters,
    _elapsed_seconds,
    _fail_reasons,
    _real_run_id,
    classify_outcome,
    log_markers,
    _ddt_series,
    _infer_test,
    _interior,
    _interior_mask,
    _residual_shares,
)
from perftest.index import INDEX_COLUMNS, _merge_columns

from perftest.logparse import build_type

NX, NTHETA, MXG = 8, 6, 2
GUARD_X = (0, 1, NX - 2, NX - 1)

METADATA = {
    "MXG": MXG, "MYG": 0,
    "nxg": NX, "nyg": NTHETA, "ny_inner": NTHETA // 2,
    "ixseps1": 4, "ixseps2": 4, "ixseps1g": 4, "ixseps2g": 4,
    "jyseps1_1g": 1, "jyseps2_1g": 2, "jyseps1_2g": 3, "jyseps2_2g": 4,
    "topology": "single-null",
    "keep_xboundaries": 1, "keep_yboundaries": 0,
}

GARBAGE = 1e15


def _field(interior, guard, nt=2):
    """A (t, x, theta) field holding `interior` everywhere except the radial
    guard columns, which hold `guard`."""
    values = np.full((nt, NX, NTHETA), float(interior))
    for x in GUARD_X:
        values[:, x, :] = float(guard)
    return values


def _dataset(fields, nt=2):
    """A dataset carrying `fields` plus the geometry the mask is built from."""
    data = {name: (("t", "x", "theta"), values) for name, values in fields.items()}
    for name in ("J", "dx", "dy", "dz"):
        data[name] = (("x", "theta"), np.ones((NX, NTHETA)))
    ds = xr.Dataset(data, coords={"t": np.arange(nt, dtype=float)})
    ds.attrs["metadata"] = METADATA
    for name in ds.data_vars:
        ds[name].attrs["metadata"] = METADATA
        ds[name].attrs["conversion"] = 1.0
    return ds


# =============================================================================
# The interior mask -- the thing everything else depends on
# =============================================================================
def test_mask_is_false_exactly_on_guard_cells():
    mask = _interior_mask(_dataset({}))
    assert mask is not None
    assert not mask.isel(x=list(GUARD_X)).values.any()
    assert mask.isel(x=slice(MXG, -MXG)).values.all()
    assert int(mask.values.sum()) == (NX - 2 * MXG) * NTHETA


def test_mask_has_no_time_dimension():
    """It is applied to fields that do have one, so it must broadcast."""
    assert "t" not in _interior_mask(_dataset({})).dims


def test_missing_geometry_is_a_problem_not_a_pass():
    """No mask must fail the extraction. Treating "cannot tell" as "no guards
    to remove" is exactly how the contaminated shares got recorded."""
    ds = xr.Dataset({"resid_A": (("t", "x", "theta"), np.ones((2, NX, NTHETA)))},
                    coords={"t": [0.0, 1.0]})
    report = Report("case")
    assert _interior_mask(ds, report) is None
    assert report.problems


def test_interior_without_a_mask_does_not_silently_trim():
    """`_interior(field, None)` returns the field untouched, so a caller that
    forgets to check gets an obviously wrong number rather than a plausible
    one."""
    ds = _dataset({"resid_A": _field(1.0, GARBAGE)})
    assert _interior(ds["resid_A"], None).equals(ds["resid_A"])


# =============================================================================
# Residual shares (F20)
# =============================================================================
def test_residual_shares_ignore_guard_garbage():
    """A field whose guards hold 1e15 and whose interior holds nothing must not
    take the whole norm from a field that is genuinely large inside."""
    ds = _dataset({
        "resid_loud_guards": _field(0.0, GARBAGE),
        "resid_real": _field(1.0, 0.0),
    })
    shares = _residual_shares(ds)
    assert shares["share_real"].iloc[0] == pytest.approx(1.0)
    assert shares["share_loud_guards"].iloc[0] == pytest.approx(0.0)


def test_residual_shares_sum_to_one():
    ds = _dataset({
        "resid_A": _field(1.0, GARBAGE),
        "resid_B": _field(3.0, 0.0),
    })
    shares = _residual_shares(ds)
    columns = [c for c in shares.columns if c.startswith("share_")]
    assert shares[columns].sum(axis=1).values == pytest.approx(1.0)
    # 1 and 3 in every interior cell -> squares 1 and 9.
    assert shares["share_A"].iloc[0] == pytest.approx(0.1)


def test_residual_total_counts_interior_cells_only():
    ds = _dataset({"resid_A": _field(2.0, GARBAGE)})
    total = _residual_shares(ds)["resid_ss_total"].iloc[0]
    assert total == pytest.approx(4.0 * (NX - 2 * MXG) * NTHETA)


# =============================================================================
# Rate of change
# =============================================================================
def test_ddt_rms_and_peak_ignore_guard_garbage():
    ds = _dataset({"ddt(A)": _field(2.0, GARBAGE), "A": _field(4.0, GARBAGE)})
    row = _ddt_series(ds).iloc[0]
    assert row["rms_ddt"] == pytest.approx(2.0)
    assert row["max_abs_ddt"] == pytest.approx(2.0)
    assert row["rms_state"] == pytest.approx(4.0)


def test_volume_weighting_agrees_with_plain_rms_on_uniform_cells():
    """Every cell has the same volume here, so the two norms cannot differ.
    If they do, the weighting is picking up cells the plain norm is not --
    which on a real grid would be the guards."""
    ds = _dataset({"ddt(A)": _field(3.0, GARBAGE), "A": _field(1.0, 0.0)})
    row = _ddt_series(ds).iloc[0]
    assert row["rms_ddt_vw"] == pytest.approx(row["rms_ddt"])


def test_ddt_carries_the_normalisation_factor():
    ds = _dataset({"ddt(A)": _field(1.0, 0.0), "A": _field(1.0, 0.0)})
    ds["ddt(A)"].attrs["conversion"] = 7.5
    assert _ddt_series(ds)["conversion"].iloc[0] == pytest.approx(7.5)


# =============================================================================
# Build type, read back from the compile flags
# =============================================================================
@pytest.mark.parametrize("flags, expected", [
    ("-Wall -DCHECK=2 -O2 -g -DNDEBUG", "RelWithDebInfo"),
    ("-Wall -O3 -DNDEBUG", "Release"),
    ("-Wall -Os -DNDEBUG", "MinSizeRel"),
    ("-Wall -O0 -g", "Debug"),
    ("-Wall -g", "Debug"),
])
def test_build_type_recognises_the_cmake_defaults(flags, expected):
    assert build_type(flags) == expected


def test_unrecognised_flags_report_themselves_rather_than_guessing():
    assert build_type("-Wall -march=native") == "unknown"
    assert build_type("-O1 -g -DNDEBUG") == "-O1 -g -DNDEBUG"


def test_build_type_of_nothing_is_nothing():
    assert build_type(None) is None
    assert build_type("") is None


# =============================================================================
# Index columns -- a schema that grows must not disturb what is there
# =============================================================================
def test_a_new_canonical_column_lands_in_its_canonical_place():
    without = [c for c in INDEX_COLUMNS if c != "build_type"]
    assert _merge_columns(without) == INDEX_COLUMNS


def test_existing_column_order_is_never_rearranged():
    """The file is hand-edited and read in a spreadsheet, so its own order
    wins."""
    shuffled = ["wall_s", "test_id", "case_dir"]
    merged = _merge_columns(shuffled)
    assert [c for c in merged if c in shuffled] == shuffled


def test_columns_the_schema_has_never_heard_of_are_kept():
    merged = _merge_columns(list(INDEX_COLUMNS) + ["someones_private_note"])
    assert "someones_private_note" in merged


# =============================================================================
# Test name inference
# =============================================================================
# A wrong test name does not raise: it lands in the index, and test_id is built
# from it, so a whole row is mislabelled silently. Span-style names such as
# test2_0-20ms contain hyphens, so the date is the only reliable anchor.
@pytest.mark.parametrize(
    "case_dir, expected",
    [
        # Span-style names, whose hyphens must survive
        ("test2_0-20ms-2026-07-31", "test2_0-20ms"),
        ("test2_0-20ms-2026-07-31-mc-a35e2f5e", "test2_0-20ms"),
        ("test4_3-3.5ms-2026-07-31-mc", "test4_3-3.5ms"),
        # Legacy adjective names must keep working
        ("test2scratch-2026-07-31", "test2scratch"),
        ("test4steady-2026-07-30-va-mumps1", "test4steady"),
        # A description containing something date-like must not win over the
        # real date, which comes first
        ("test2_0-20ms-2026-07-31-rebuild-of-2025-08-01", "test2_0-20ms"),
        # No date at all: fall back rather than fail
        ("test2scratch", "test2scratch"),
    ],
)
def test_test_name_survives_hyphens_in_the_name(case_dir, expected):
    assert _infer_test(case_dir) == expected


# =============================================================================
# OUTCOME -- what the run's ending is called
#
# Six states, one test each. The rule that decides between them must run on the
# log and the dump alone: a state that needed the program which launched the run
# to remember something would be unavailable to anyone re-extracting the case
# later, which is most of the time.
# =============================================================================
def test_recovered_snes_failures_do_not_make_a_run_a_failure():
    """BOUT++ prints the failed-SNES marker every time it recovers from a
    failure by cutting the timestep. Eleven runs in the store were recorded as
    snes_failure on that marker alone, including two parents that finished in
    54 s and 41 min with all 101 steps written."""

    assert classify_outcome(True, 101, 101) == ("completed", None)


def test_a_clean_full_run_is_completed():
    assert classify_outcome(True, 51, 51) == ("completed", None)


def test_a_run_that_finished_short_of_its_window_is_invalid():
    """It exited on its own and nothing stopped it, so its cost is real -- but
    it covers less plasma time than the runs it would be compared against."""

    assert classify_outcome(True, 30, 101) == ("invalid", None)


def test_a_run_that_failed_the_correctness_check_is_invalid():
    """Fast and finished, and the answer is wrong. The most dangerous class,
    because nothing about the run itself announces it."""

    assert classify_outcome(True, 51, 51, correctness_ok=False) == ("invalid", None)


def test_the_failure_cap_is_divergence_although_the_run_exits_cleanly():
    """SNES returns rather than throwing when it hits max_snes_failures, so
    BoutFinalise runs and BOUT.settings carries a finish stamp. Reading the
    stamp alone calls the run an ordinary short one."""

    assert classify_outcome(True, 30, 101, solver_aborted=True) == ("diverged", None)


def test_non_finite_values_are_divergence():
    assert classify_outcome(
        False, 12, 101, error="Field3D: Operation on non-finite data at [4][5][6]"
    ) == ("diverged", None)


def test_divergence_wins_over_the_cutoff():
    """A run that blew up after a long time died of its recipe, not of the
    clock. Calling it a timeout would hide the one ending that says most."""

    assert classify_outcome(
        False, 12, 101, solver_aborted=True, elapsed_s=9000.0, cutoff_s=5000.0
    ) == ("diverged", None)


def test_a_segmentation_fault_is_a_crash_not_a_divergence():
    """A crash says nothing about the recipe, so it must never be read as a
    slow or a failed result."""

    assert classify_outcome(
        False, 12, 101, error="****** SEGMENTATION FAULT CAUGHT ******"
    ) == ("crashed", None)


def test_a_run_killed_with_no_message_at_all_is_a_crash():
    """SIGKILL cannot be caught, so the log simply stops. That is what an
    out-of-memory kill looks like too."""

    outcome, warning = classify_outcome(False, 12, 101)
    assert outcome == "crashed"
    assert "killed outright" in warning


def test_the_wall_clock_limit_is_a_timeout():
    """BOUT++ quits cleanly when its own wall_limit is nearly spent, so the run
    finishes and writes a stamp with only part of its window done."""

    assert classify_outcome(
        True, 30, 101, wall_limit=True, quit_requested=True
    ) == ("timeout", None)


def test_a_run_stopped_past_the_cutoff_is_a_timeout_not_a_crash():
    """"At least this slow" is evidence. Recording it as a crash would throw
    away the one thing the run measured."""

    assert classify_outcome(
        False, 30, 101, elapsed_s=5400.0, cutoff_s=5000.0
    ) == ("timeout", None)


def test_a_deliberate_stop_under_the_cutoff_is_cancelled():
    assert classify_outcome(
        True, 30, 101, stop_file=True, quit_requested=True,
        elapsed_s=100.0, cutoff_s=5000.0,
    ) == ("cancelled", None)


def test_an_interrupt_is_cancelled_not_crashed():
    """An interrupt arrives as an exception like any other, so the message has
    to be read rather than just counted."""

    assert classify_outcome(
        False, 30, 101, error="****** SigInt caught ******"
    ) == ("cancelled", None)


def test_a_completed_run_is_never_relabelled_by_a_later_faster_one():
    """The cutoff is computed from the index at extraction time, which can be
    long after a run that was the best of its day. Reaching the end of the
    window is what completed means; how long it took is a separate column."""

    assert classify_outcome(True, 51, 51, elapsed_s=9e9, cutoff_s=1.0) == (
        "completed",
        None,
    )


def test_an_unknown_step_count_is_never_called_completed():
    """nout unreadable: whether the window was reached cannot be known, and an
    unknown is left unknown rather than guessed at."""

    outcome, warning = classify_outcome(True, 51, None)
    assert outcome is None
    assert "51 output steps" in warning


@pytest.mark.parametrize("arguments", [
    {},
    {"solver_aborted": True},
    {"error": "****** SEGMENTATION FAULT CAUGHT ******"},
    {"wall_limit": True},
    {"stop_file": True},
    {"correctness_ok": False},
])
def test_the_classifier_only_ever_returns_a_named_state(arguments):
    """A typo in one branch would put a state in the index that nothing
    downstream filters on, and a row nobody counts is a row nobody reads."""

    outcome, _ = classify_outcome(True, 51, 51, **arguments)
    assert outcome is None or outcome in OUTCOMES


# =============================================================================
# The evidence the classifier runs on
# =============================================================================
def test_log_markers_read_the_endings_bout_prints(tmp_path):
    (tmp_path / "BOUT.log.0").write_text(
        "Sim Time  |  RHS evals  | Wall Time\n"
        "Too many SNES failures (12). Aborting.\n"
        "\nStop file BOUT.stop exists -- triggering exit\n"
        "User signalled to quit. Returning\n"
        "Error encountered: \n"
        "****** SEGMENTATION FAULT CAUGHT ******\n"
    )

    markers = log_markers(str(tmp_path))
    assert markers["solver_aborted"]
    assert markers["stop_file"]
    assert markers["quit_requested"]
    assert not markers["wall_limit"]
    # The signal handler's message starts on the line after the marker, so a
    # one-line read would report an empty message and call this a silent kill.
    assert "SEGMENTATION FAULT" in markers["error"]


def test_a_log_with_nothing_wrong_reports_no_markers(tmp_path):
    (tmp_path / "BOUT.log.0").write_text("Run finished at  : Thu Jul 31 2026\n")
    markers = log_markers(str(tmp_path))
    assert markers["error"] is None
    assert not any(markers[k] for k in markers if k != "error")


def _rows(*specs):
    return [
        {"project": project, "test": test, "outcome": outcome, "wall_s": wall,
         "case_dir": "somewhere"}
        for project, test, outcome, wall in specs
    ]


def test_the_cutoff_is_twice_the_best_completed_run_of_that_window():
    rows = _rows(
        ("solver-opt", "test4_3.0-4.0ms", "completed", "1300"),
        ("solver-opt", "test4_3.0-4.0ms", "completed", "1000"),
    )
    assert _cutoff_seconds(rows, "test4_3.0-4.0ms", "solver-opt") == 2000.0


def test_the_cutoff_ignores_other_windows_projects_and_failures():
    """A window's cost is its own, and a row from another project is never
    compared with one from this project."""

    rows = _rows(
        ("solver-opt", "test4_20.0-21.0ms", "completed", "20"),
        ("perf-bisect", "test4_3.0-4.0ms", "completed", "30"),
        ("solver-opt", "test4_3.0-4.0ms", "diverged", "40"),
        ("solver-opt", "test4_3.0-4.0ms", "completed", "1000"),
    )
    assert _cutoff_seconds(rows, "test4_3.0-4.0ms", "solver-opt") == 2000.0


def test_a_window_with_no_completed_run_has_no_cutoff():
    """Nothing is called a timeout until something has shown what the window
    costs."""

    rows = _rows(("solver-opt", "test4_3.0-4.0ms", "diverged", "40"))
    assert _cutoff_seconds(rows, "test4_3.0-4.0ms", "solver-opt") is None


def test_a_killed_run_is_timed_by_the_dump(tmp_path):
    """wall_s needs both time stamps in the log and a killed run wrote only
    one, so the clock has to come from the dump's elapsed-seconds series."""

    import pandas as pd

    series = pd.DataFrame({"wall_time": [10.0, 400.0, 900.0]})
    assert _elapsed_seconds(None, series) == 900.0
    assert _elapsed_seconds(1234.0, series) == 1234.0
    assert _elapsed_seconds(None, None) is None


# =============================================================================
# CVODE counters -- the cost columns for a solver that writes no log lines
# =============================================================================
def _counter_dataset(**columns):
    return xr.Dataset(
        {name: (("t",), np.asarray(values)) for name, values in columns.items()},
        coords={"t": np.arange(3, dtype=float)},
    )


def test_cvode_counters_are_the_last_value_not_the_sum():
    """These counters are cumulative over the run, unlike the SNES per-step
    numbers the log carries. Summing them counts every step again at every
    later step -- here it would report 41 nonlinear iterations instead of 25."""

    ds = _counter_dataset(
        cvode_nniters=[6, 10, 25],
        cvode_nliters=[8, 20, 60],
        cvode_nonlin_fails=[0, 1, 4],
    )
    assert _cvode_counters(ds) == {
        "nl_its": 25,
        "lin_its": 60,
        "solver_fails": 4,
    }


def test_a_dump_without_cvode_counters_yields_nothing():
    """A SNES run has none of these fields, and an absent counter must stay
    absent rather than being recorded as zero work."""

    assert _cvode_counters(_counter_dataset(cvode_nsteps=[1, 2, 3])) == {}


# =============================================================================
# FAILURE BLOCKS -- what the solver was doing when it gave up
# =============================================================================
def _events(pairs):
    import pandas as pd

    return pd.DataFrame(
        [{"event": kind, "reason": reason} for kind, reason in pairs],
        columns=["event", "reason"],
    )


def test_fail_reasons_counts_only_the_failures():
    frame = _events([("step", 2), ("fail", -9), ("step", 2), ("fail", -9),
                     ("fail", -5)])
    assert _fail_reasons(frame) == "-9:2 -5:1"


def test_fail_reasons_is_empty_when_nothing_failed():
    assert _fail_reasons(_events([("step", 2), ("step", 2)])) == ""


def test_fail_reasons_survives_a_frame_from_before_the_event_column():
    import pandas as pd

    assert _fail_reasons(pd.DataFrame({"reason": [2, 2]})) == ""


def test_consecutive_failures_are_separate_rows(tmp_path):
    """Two failures with no step between them print two blocks and one
    annotation, `SNES failures: 2`. Ending a block only at the next `Time:`
    collapsed them: a real run had 326 blocks read as 267 rows."""

    from perftest.logparse import snes_steps

    block = (
        "======== SNES failed =========\n\n"
        "Return code: 0, reason: -9\n"
        "Pd : (0 -> 65.2), ddt: (-0.001 -> 489.4)\n"
        "Pe : (0.1 -> 5559.4), ddt: (-0.01 -> 0.016)\n"
    )
    (tmp_path / "BOUT.log.0").write_text(
        block + block
        + "Time: 288284.6, timestep: 75.4, nl iter: 4, lin iter: 4,"
        " reason: 2, SNES failures: 2\n"
    )

    frame = snes_steps(str(tmp_path))
    fails = frame[frame["event"] == "fail"]
    assert len(fails) == 2
    assert list(fails["reason"]) == [-9, -9]
    # The retry's time is carried back onto both, which is when they happened.
    assert list(fails["time"]) == [288284.6, 288284.6]


def test_the_failed_block_names_the_equation_that_ran_away(tmp_path):
    from perftest.logparse import snes_steps

    (tmp_path / "BOUT.log.0").write_text(
        "======== SNES failed =========\n\n"
        "Return code: 0, reason: -5\n"
        "Nd+ : (8.2 -> 1721.4), ddt: (-0.0028 -> 0.0024)\n"
        "Pd : (0 -> 65.2), ddt: (-0.0011 -> 489.4)\n"
        "Time: 1.0, timestep: 2.0, nl iter: 1, lin iter: 1, reason: 2\n"
    )

    fail = snes_steps(str(tmp_path)).iloc[0]
    assert fail["event"] == "fail"
    assert fail["worst_var"] == "Pd"
    assert fail["worst_ddt"] == 489.4


# =============================================================================
# SEED -- what a run restarted from
# =============================================================================
def test_the_null_restart_id_is_not_a_seed():
    """BOUT writes 36 z's when nothing was restarted from. Recorded as an id it
    grouped three unrelated from-scratch parents as though they shared one."""

    assert _real_run_id("z" * 36) is None


def test_a_real_restart_id_is_kept():
    """A window's seed is the parent's run_id, which joins the two rows."""

    assert _real_run_id("ea3bb152-6816-4469-af5d-3ea455b4d157") == (
        "ea3bb152-6816-4469-af5d-3ea455b4d157"
    )


def test_a_missing_restart_id_is_not_invented():
    assert _real_run_id(None) is None
    assert _real_run_id("   ") is None
