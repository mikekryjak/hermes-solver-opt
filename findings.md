# Findings log

Learned rules, agent-facing and terse. Started fresh 2026-09-18 when the
previous optimisation work was archived; the old log is in
`archive/2026-08-tuning/findings.md` and its conclusions do not carry over,
because the new project starts from a known recipe on a fixed build.

Format: one entry per finding, with these fields on the heading line or
immediately under it.

- date: when it was learned.
- status: active, superseded, or graduated.
- scope: which test, rung, build or campaign it holds for. Never "everything"
  unless that has been shown.
- evidence: the run identities or study it rests on.
- supersedes: the finding it replaces, if any.

A finding graduates into a requirement, a procedure, an extraction test or a
config default. Its status then changes to graduated and it stays, with a
pointer to where it landed. Nothing is deleted. There is no cap on how many
findings exist; the cap is on how many are loaded at once.

## Findings

### A repeat of a 17-hour run lands within 1.4%, and the counts are not identical
- date: 2026-09-21
- status: active
- scope: any comparison of two full 0-100 ms parent runs.
- evidence: test5_0.0-100.0ms-2026-09-19-neutlag-va against its -repeat, same
  input and same binary. wall_s 59773 -> 60583 (+1.4%), nl_its 160777 ->
  161284 (+0.3%), solver_fails 63019 -> 63721 (+1.1%). The original ran beside
  two other parents at concurrency 1.06 and the repeat ran alone at 1.00, so
  1.4% is an upper bound on the clock and the true repeat spread is smaller.
- rule: the counts are the better metric but they are NOT exactly reproducible
  either, so a difference under about 0.5% in nl_its is noise. A wall-clock
  difference under 2% between runs at different concurrency says nothing at
  all. This is the project's first repeat measurement; one pair is not a
  distribution, and a campaign that wants a real noise bound still needs
  repeats at its own window length.

### An evenly split parent millisecond predicts a window's cost badly, both ways
- date: 2026-09-21
- status: active
- scope: windows cut inside a transient. Shown on test4's 2-6 ms transient;
  expected wherever a parent's cost varies sharply within one millisecond.
- evidence: the baseline study of the test4-jacobian campaign, three windows at
  SNES-MUMPS-3 on build ef2ef9dd. Predicted by splitting the parent's in-line
  cost for the enclosing millisecond evenly: 68 / 272 / 170 s. Measured:
  test4_2.0-2.3ms 21 s (83 nl_its, t_jac_frac 0.58), test4_3.0-3.2ms 205 s
  (1082 nl_its, 0.73), test4_4.0-4.3ms 414 s (2155 nl_its, 0.73). Wrong by 3.2x
  low and 2.4x high. The total, 640 s against 510 s predicted, hides both
  errors, so an aggregate check would have passed.
- rule: never size a window from a parent's per-millisecond cost. Run a
  baseline-only study first and read the real costs off it. Keep a window only
  if it does solver work throughout: test4_2.0-2.3ms ends with output steps of
  one RHS evaluation and over 90% I/O, so it coasts and no Jacobian knob can
  move it.

### The Jacobian must be rebuilt every iteration on the test4 transient
- date: 2026-09-21
- status: active
- scope: test4's 2-6 ms transient, build ef2ef9dd, recipe SNES-MUMPS-3, rung 0.
  NOT yet shown at rung 1 or 2, nor on test2 or test5.
- supersedes: the 2026-09-21 entry that read "Lagging the Jacobian costs more
  than it saves", whose claim of a monotonic cost curve the fuller sweep below
  falsifies. The winner is unchanged; the shape of the curve is not.
- evidence: rung 0 of the test4-jacobian campaign, `solver:lag_jacobian` swept
  over 1, 2, the baseline's 3, 4, 6, 10 and 20 on three windows. Wall seconds /
  nonlinear iterations.

  | window | 1 | 2 | 3 | 4 | 6 | 10 | 20 |
  |---|---|---|---|---|---|---|---|
  | 2.0-3.0ms | 36/81 | 281/1071 | 213/1094 | 349/2190 | 423/3619 | 423/4350 | 450/4636 |
  | 3.0-3.2ms | 126/273 | 251/941 | 205/1082 | 227/1432 | 254/2032 | 238/2404 | 234/2404 |
  | 4.0-4.1ms | 79/170 | 130/466 | 129/646 | 215/1342 | 186/1603 | 174/1779 | 173/1779 |

- rule: set `solver:lag_jacobian = 1`. It wins on every window by 1.6 to 5.9
  times, with 4 to 13 times fewer nonlinear iterations, and target density and
  temperature agree with the baseline to about 5e-5. The production recipe's
  lag of 3 is a cost, not a saving.
- the minimum is sharp, not the end of a trend: lag 2 is WORSE than lag 3 on
  all three windows, and on 4.0-4.1ms wall time falls again from lag 4 to lag
  20. Nothing between 2 and 20 is worth sampling.
- rank on wall clock, never on iteration counts alone. Nonlinear iterations
  rise monotonically with the lag while wall time does not, so the two metrics
  disagree across most of this range and only agree at the winner.
- the search space gives this knob the range 1-20 with its optimum at the
  floor, so the range is pointing the wrong way and should be reconsidered.

### Neither of the other two Jacobian knobs is usable on this problem
- date: 2026-09-21
- status: active
- scope: test4 rung-0 windows, build ef2ef9dd. Both knobs were untested before
  today, on this or any test.
- evidence: `solver:jacobian_persists = true` diverged on all three windows,
  alone and combined with lag 10. On test4_2.0-3.0ms it reached 20 SNES
  failures in 8 s with the solution blown up -- Nd+ to 1807, Nd to 5466, Pd+ to
  5482 against physical values of order 10. `solver:prune_jacobian = true`
  wrote exactly one internal solver step, at the initial timestep of 0.1, and
  then advanced no further until the cutoff killed it, on all three windows,
  with no SNES failure and no error.
- rule: do not propose either knob for this problem again without a reason to
  think something changed. Persisting the Jacobian is the same trade as lagging
  it, further in the direction the sweep above shows is wrong.
- open, and NOT established: whether pruning was actually active. The killed
  run's `BOUT.settings` lists `prune_jacobian` as unused, but that file is
  written before finalize, and the input sets `error_on_unused_options = true`,
  which would have stopped the run outright had the option been unread.
  Deciding this needs a pruning run that finishes.

### The Jacobian lag saturates where a solve is shorter than the lag
- date: 2026-09-21
- status: active
- scope: test4 rung-0 windows. The mechanism should hold wherever SNES
  converges in fewer iterations than the lag.
- evidence: lag 10 and lag 20 did identical work on the two short windows --
  2404 and 2404 nonlinear iterations on test4_3.0-3.2ms, 1779 and 1779 on
  test4_4.0-4.1ms, same solver_fails, target values identical to every printed
  digit. On the whole-millisecond window test4_2.0-3.0ms they did NOT: 4350
  against 4636. That window's solves are long enough for a lag of 20 to differ
  from a lag of 10.
- rule: treat a lag above the typical iterations per solve as one setting, but
  check the window before assuming it, because a longer window moves the point
  where saturation starts.
- the saturation is also a free control: on the two windows where the work was
  provably identical, wall clock differed by 1.7% and 0.6%, at concurrency 2.35
  against 1.81 and 2.05 against 2.00, with the more loaded run slower both
  times. That is the project's first same-work timing comparison and puts noise
  plus loading at a few per cent, well inside the 15% rung-0 bound. Two pairs,
  not a distribution.

## Traps

### In the run screens, `python` is the pyenv shim and it bus-errors on pandas
- date: 2026-09-20
- status: active
- scope: screens h1, h2, h3, and anything launched from a runplan line.
- evidence: the first test-drive launch exited at once and wrote a zero-byte
  log. In h2, `python -c 'import pandas'` dies with "Bus error (core dumped)",
  exit 135. The screens do carry SPACK_ENV, but .bashrc puts the pyenv shims
  ahead of the environment's own bin, so `python` is not the Spack one.
- rule: a runplan line that runs python must put
  `/home/mike/spack/var/spack/environments/hermes3/.spack-env/view/bin` first
  on PATH, so the runner starts under an interpreter that works. A crash on a
  signal writes nothing through a pipe, so an empty log is a symptom of this,
  not of a tool that did nothing.
- partly graduated 2026-09-20: the runner no longer passes the problem on. It
  starts make_window.py, extract_test.py and can_delete.py under its own
  interpreter rather than through their `#!/usr/bin/env python3` line, and a
  test holds that. The rule above still stands for the runner itself and for
  anything else a runplan line runs by hand.

### A stub that writes nothing hides an integration bug
- date: 2026-09-20
- status: active
- scope: any test that monkeypatches one stage of the runner loop.
- evidence: test_a_kill_is_recorded_as_a_timeout passed for a day while the
  runner's kill outcome never reached the index. Its stubbed extract returned
  True and wrote no row, so the cell the runner meant to correct was blank and
  the blank-cells-only rule never fired.
- rule: a stub standing in for a stage must write what the real stage writes,
  or it tests the caller against a world that does not exist.
