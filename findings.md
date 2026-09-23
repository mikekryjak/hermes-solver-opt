# Findings log

This file holds findings shown on more than one test, or about the run
system or PETSc. One test's findings live in `campaigns/<campaign>/findings.md`,
named after the store campaign, with the campaign's conclusion and next steps
first. Load `findings.md` and the current campaign's file, never another's.

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
### Judge a cell by its iteration spread before its wall spread
- date: 2026-09-22
- status: active
- scope: any campaign whose windows contain a transient; shown on test4.
- evidence: `campaigns/test4-jacobian/findings.md`, "Repeat spread is the
  solver's path". Wall per nonlinear iteration was within 5 per cent in 45 of
  48 three-repeat cells while nl_its varied up to 2.25x; the same seed and
  options took different paths through the transient, and a lag of 1
  amplified the divergence. Loading cost a few per cent.
- rule: a cell whose wall per iteration is tight but whose nl_its is not has
  path noise, and three repeats give a range, not a mean. Size repeats per
  window from the measured nl_its spread, and prefer screening windows that
  avoid the transient. Check every full-length result against its parent
  before believing a cheap path: the run system does not do this itself.

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

### `resid_drop` and `resid_per_rhs` carry nothing on a window
- date: 2026-09-22
- status: active
- scope: the index columns derived from `snes_global_residual` on any short
  window run under a relative-tolerance stop (every SNES recipe so far).
- evidence: test4-jacobian, both rung-0 screening windows, every setting: the
  end-of-step residual sits at 2e-4 to 6e-4 whatever the setting, is
  independent of the timestep (log-log slope 0.03), and the orders dropped
  across a window are within ±0.7 for every setting, so `resid_per_rhs` is a
  small number of either sign. On the full 100 ms run the drop is about 2
  orders and may mean something.
- rule: never rank or filter on `resid_drop` or `resid_per_rhs` from a window.
  The informative reduction of the same data is the per-equation share
  (`share_<equation>` in the bundle series), which is a remainder after a
  converged solve and reads as "which equation the solver stopped on", never
  as cost. Candidate for the capture set: drop the two columns or mark them
  full-run only.

### `solver:prune_jacobian` aborts with C++ heap corruption in BOUT++
- date: 2026-09-22
- status: active
- scope: any run setting `solver:prune_jacobian = true` in BOUT++.
- evidence: test5-pilot screening batch 1, 4 trials across `test5_0.0-0.1ms` and
  `test5_24.0-24.2ms`. All 4 crashed after 0.3 min with SIGABRT (exit code 134)
  and glibc heap corruption error: `free(): corrupted unsorted chunks` /
  `corrupted size vs. prev_size`.
- rule: quarantine `solver:prune_jacobian = true`. Never sample it in any
  campaign until the BOUT++ CSR element filtering routine is patched.

### `solver:jacobian_persists` diverges across time steps unconditionally
- date: 2026-09-22
- status: active
- scope: implicit time integration with PETSc SNES across step boundaries.
- evidence: 4 of 4 trials in test5-pilot (`test5_0.0-0.1ms` and
  `test5_24.0-24.2ms`) and 4 of 4 trials in test4-jacobian diverged with SNES
  reason -9:1 (`DIVERGED_STEP_TRUNCATED`).
- rule: never set `solver:jacobian_persists = true` in Hermes-3. Carrying
  Jacobians across time steps causes line search step truncation failures in
  every plasma regime tested.

### The SNES failure printout and the dumps cannot show a negative neutral density or pressure
- date: 2026-09-23
- status: active
- scope: builds whose neutral_mixed clamps in place; read in
  hermes-3-neutlim-lagging ef2ef9dd.
- evidence: code read. neutral_mixed.cxx:459-460 sets `Nn = floor(Nn, 0.0)`
  and `Pn = floor(Pn, 0.0)` on the evolved fields (registered at :49-50) at
  the start of every RHS call. The "SNES failed" block (BOUT-dev snes.cxx
  817-829) and the dump both read those fields afterwards. The plasma density
  and pressure are clamped into copies, so their printed minimum is true.
- rule: a printed or dumped Nd or Pd minimum of exactly 0 means some cell was
  at or below zero, not that none went negative. Never read "min 0" as "never
  negative". Investigation 04 in the store follows this up.
