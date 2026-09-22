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

### Krylov settings are inert while the preconditioner is an exact solve
- date: 2026-09-21
- status: active
- scope: any SNES recipe with `solver:pc_type = lu` and a direct factorisation
  package. It stops holding the moment the preconditioner is inexact.
- evidence: all 34 rows of the test4-jacobian index have `lin_its` equal to
  `nl_its`, so every Krylov solve converged in one iteration.
- rule: spend no runs on `petsc:ksp_type` or `solver:maxl` under an exact LU.
  They cannot move the wall clock. The one meaningful KSP change there is
  `preonly`, which drops the Krylov wrapper altogether. Screen Krylov settings
  only after an inexact preconditioner has won.

### PETSc's own ILU is sequential, and pc_factor options die under a non-factor PC
- date: 2026-09-21
- status: active
- scope: this build, 10 ranks, an MPIAIJ Jacobian. Any parallel run.
- evidence: PCILU is registered for sequential matrices only, so
  `solver:pc_type = ilu` on 10 ranks fails in PCSetUp within seconds.
  Separately, `petsc:pc_factor_*` options belong to a factorisation
  preconditioner and are never consumed under bjacobi, asm or gamg, and the
  extractor refuses any run whose varied key PETSc left unused.
- rule: reach incomplete factorisation in parallel through `bjacobi` or `asm`,
  whose per-rank sub-preconditioner is ILU, and set its options with the `sub_`
  prefix. Never pair a `pc_factor_*` override with a non-factorising `pc_type`:
  the run records nothing at all, so the slot time is spent for no row.

### Two runs with identical iteration counts are not a noise measurement
- date: 2026-09-21
- status: active
- scope: reading repeat spread out of this project's index.
- evidence: the lag 10 and lag 20 rows on test4_3.0-3.2ms and test4_4.0-4.1ms
  have bit-identical `nl_its`, 2404 and 1779, yet differ by 1.7 and 0.6 per
  cent in wall clock. They also ran at different loading, concurrency 2.35
  against 1.81 and 2.05 against 2.00, and the more loaded run was the slower
  one both times. `wall_s` is the difference of two one-second log stamps, so
  174 against 173 is a single quantum.
- rule: identical work at different loading measures loading, not noise. Quote
  a noise figure only from repeats that hold loading fixed, and never from a
  pair. On a run of a few hundred seconds the timestamp alone carries a few
  tenths of a per cent.

### A long window's output cadence is fixed, and can trip the stall limit
- date: 2026-09-21
- status: active
- scope: any window much longer than a millisecond cut by make_window.py.
- evidence: NOUT is 50 whatever the window's length, so a 0-100 ms window
  writes an output every 2 ms while its parent wrote every 1 ms. The test4
  parent spent 1360 s on 3-4 ms, so one output interval runs about 1590 s
  against a 1800 s stall limit: a 12 per cent margin for the baseline and a
  kill for anything slower.
- rule: before queueing a long window, multiply the parent's worst
  per-millisecond cost by the window's output interval and compare it with
  `stall_s`. A stall kill also records no `wall_s`, so it costs the slot-hour
  budget nothing and the gate never sees the time it spent.

### Lag 1 holds on every rung, including the whole 100 ms run
- date: 2026-09-22
- status: active
- scope: test4 on the ef2ef9dd neutlim-lagging build, SNES-MUMPS-3 as baseline.
- evidence: the overnight campaign of 2026-09-21, 138 runs, three repeats per
  cell, all at concurrency near 3. Mean wall against the baseline mean:
  rung 0 0.18 (2.0-3.0ms), 0.74 (3.0-3.2ms), 0.57 (4.0-4.1ms); rung 1 0.79
  (3.0-4.0ms), 0.72 (4.0-5.0ms); rung 2 0.55 (0.0-100.0ms: 2047, 1438, 1089 s
  against 2862, 2711, 2765 s). Lag 2 is at or above 1.0 on both rung-1
  windows; lag 20 is 0.97 and 1.25.
- the per-iteration cost is what lag 1 buys with: 0.45-0.47 s per nonlinear
  iteration against 0.19-0.20 s for lag 3 on every window, and 2.4-3.3x fewer
  iterations, so the ratio is set by the iteration count alone.
- rule: lag 1 is the recipe to beat. The rung-2 ratio is 0.55 as a mean but
  0.38 to 0.72 across three repeats, for the reason in the next finding, so
  quote the range and never the mean alone.

### Repeat spread is the solver's path, not the machine, and it lives in the 2-6 ms transient
- date: 2026-09-22
- status: active
- scope: test4 with lag_jacobian = 1; weaker with lag 3; every window that
  contains the 2-6 ms transient.
- evidence: the three rung-2 lag-1 repeats did 4455, 3104 and 2442 nonlinear
  iterations from a seed identical to eleven digits in Ne, with byte-identical
  BOUT.inp, and ended within 4e-5 of each other in total Ne. Wall per
  iteration was 0.446-0.463 s across the three. RHS evaluations in the 2-4 ms
  output interval were 351k, 90k and 4.8k against the baseline's 701k; in
  4-6 ms 266k, 285k and 186k against 328k; before 2 ms and after 6 ms the
  four runs agree to within a few per cent. Across all 48 cells with three
  completed repeats, wall per nonlinear iteration varies by under 5 per cent
  in 45 of them, while nl_its varies by up to 1.8x (lag 1 on 2.0-3.0ms and on
  0.0-100.0ms) and 2.25x (superlu_dist on 4.0-4.1ms). The baseline's own
  sd/mean is 0.02-0.03 on 3.0-3.2ms, 3.0-4.0ms and 0.0-100.0ms, but 0.17 on
  4.0-4.1ms and 0.23 on 2.0-3.0ms. Loading is small beside this: the one
  baseline that ran alone on 3.0-3.2ms took 205 s against 212 and 219 s loaded.
- the run is not deterministic: the same seed and options take different
  paths through the transient, and lag 1 amplifies the divergence. The
  cheapest repeat crossed 2-4 ms in 4.8k RHS evaluations, which is the
  "coasted" signature the run skill warns about. Checked the same morning
  against the parent on ne_target_max and te_target_max at every output: all
  three lag-1 runs deviate under 3 per cent over 0-10 ms and under 0.05 per
  cent at 100 ms, inside the campaign's 0.20 and 0.05 tolerances, and the
  cheapest is no worse than the others. On the 2 ms output grid the cheap path
  resolved the transient; the check cannot see between outputs.
- rule: judge a cell by its nl_its spread before its wall spread. A cell whose
  wall per iteration is tight but whose nl_its is not has path noise, and
  three repeats give a range, not a mean. Windows that avoid 2-6 ms (3.0-3.2ms,
  3.0-4.0ms) are the ones with usable 3 per cent noise. Machine and loading
  noise together are a few per cent and are not the limiting factor.

### Nothing in the screening beats lag 1 alone on both rung-0 windows
- date: 2026-09-22
- status: active
- scope: 15 configurations on lag 1, three repeats each, on test4_3.0-3.2ms
  and test4_4.0-4.1ms; ratios are against lag 1 alone on the same window.
- evidence: kI=0.3, kP=0.7 is 0.46 on 3.0-3.2ms (72, 73, 72 s, nl_its spread
  1.00) and 1.41 on 4.0-4.1ms. max_nonlinear_iterations=20 is 1.04 and 1.05.
  ksp_type=preonly 0.87 and 1.54. atol=0.01 1.01 and 1.82. Everything else is
  above 1.1 on both windows: strumpack 1.11/1.92, superlu_dist 1.33/2.42,
  matrix_free_operator 1.11/2.41, asm 2.06/2.27, bjacobi 2.49/2.82,
  target_its=3 2.10/3.04, target_its=5 1.17/2.30, target_its=10 with 20 max
  iterations 1.25/1.38, kD=0.15 1.30/2.29, rtol=1e-4 1.30/1.89, atol=1e-4
  1.33/2.14. jacobian_persists diverged again, alone and with lag 10.
- caveats: preonly, atol=0.01, rtol=1e-4, atol=1e-4 and max_nonlinear_iterations=20
  on 3.0-3.2ms ran at concurrency 1-2 at the tail of the night, which flatters
  them by a few per cent. Lag 1 alone on 4.0-4.1ms was 79, 79, 79 s with 170
  iterations each time, so that window's ratios are against a deterministic
  reference.
- rule: the timestep controller gains are the one lead, and they are window
  dependent: the aggressive controller wins where the transient is mild and
  loses where it is not. Screen it on rung 1 before believing it. The
  preconditioner and the Krylov side are settled: an exact MUMPS solve with
  lag 1 is the floor for this problem on this build.
