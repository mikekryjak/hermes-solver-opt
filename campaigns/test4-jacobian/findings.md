# test4-jacobian campaign findings

Test test4, build ef2ef9dd (neutlim-lagging), baseline recipe SNES-MUMPS-3,
this workstation, September 2026. Rules and format as in the root
`findings.md`. Nothing here is shown on another test.

## Conclusion and next steps

The recipe to beat is lag 1 with the controller gains kI 0.3, kP 0.7: 0.39
of the baseline wall time over the whole 100 ms run (five repeats, 0.24 to
0.56), end state within 0.04 per cent. Quote the range, never the mean alone.
Every win so far is fewer Newton iterations; a Jacobian build costs 0.29 s on
every setting.

Leads: kI 0.6, kP 0.7 beats the gains on both rung-1 windows. The predictor
off and target 10 iterations are faster still on short windows but miss the
end state by more than any other setting.

Next study (report S03): kI 0.6 over the full run at five repeats beside the
gains; the predictor-off and target-10 cells over the full run with end
states checked; screen at rung 1 only; ratios against the gains.

Records: the index, runlog, tables and reports S01-S03 in the store's
campaign directory; report scripts under `analysis/studies/test4-jacobian/`.

## Findings

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
### The rungs agree on the order of settings, not on the size of their gain
- date: 2026-09-22
- status: active
- scope: every pair of windows the campaign ran, on the settings both windows
  completed, baseline excluded; ratios are against the baseline on the same
  window. Report section 7, made by `analysis/rung_agreement.py` in the store.
- evidence: lag 1 beats lag 2 and lag 20 on every window of every rung. The
  two 0.2 ms screening windows (3.0-3.2ms, 4.0-4.1ms) rank-correlate 0.67 over
  21 settings but give the same verdict (faster, slower, within the noise
  bound) for only 38 per cent of them. The settings that look best on one
  window move most on the other: kI=0.3, kP=0.7 is 0.34 and 0.81;
  matrix_free_operator 0.83 and 1.37. The 2.0-3.0ms window sits in the
  transient and exaggerates everything (lag 1 at 0.18 there, 0.74 and 0.57 on
  the other two). Rung 0 to rung 1 at the same start time: Spearman 1.00, but
  on three settings that are the extremes of the field. Rung 1 to rung 2 has
  one setting in common.
- caveats: the ladder promotes only winners, so it never measures how wrong
  rung 0 is about the middle of the field, where promotion decisions are made.
- rule: rung 0 is a filter, not a measurement. Drop a setting that loses by
  more than the noise bound on a screening window; do not read a rung-0 ratio
  as a prediction of the rung-1 ratio. To measure the correlation, promote
  four mid-field settings to rung 1 regardless of their rung-0 result (about
  2.5 slot-hours); this is an open decision.

### The solver stops on neutral pressure in every window past 3 ms, whatever the setting
- date: 2026-09-22
- status: active
- scope: test4-jacobian, every completed run; shares from the bundles'
  `series.tsv` (`share_<equation>`, time-mean over output steps after the
  first). Report section 6; per-run values in the store's
  `campaigns/test4-jacobian/shares.tsv`.
- evidence: on the 3.0-3.2, 4.0-4.1, 3.0-4.0 and 4.0-5.0 ms windows neutral
  pressure `Pd` holds 0.55 to 0.78 of the residual sum of squares under every
  setting, neutral momentum and density most of the rest. Repeat spread of a
  share is about 0.01 outside the 2-3 ms transient, against 0.08-0.10 between
  settings. Lag 1 moves a share by about 0.1 at most on those windows, but on
  2.0-3.0 ms it flips the dominant equation from `Pd` (0.69) to `NVd+` (0.65)
  with the three repeats disagreeing widely. `rtol=1e-4` leaves 0.97 on `Pd`;
  `target_its=3` moves 0.48 onto `NVd`; the controller gains raise `Pd` to
  0.72-0.78. The full 100 ms run is `Pe`-dominated (0.82-0.91) because its
  outputs are 2 ms apart and mostly in the quiet phase.
- caveats: end-of-step remainders after a converged solve, not within-step
  history. They say which equation the solver stopped on, not which one cost
  the iterations. Settings that change the stopping rule (tolerances,
  iteration caps, target iterations) change the remainder by construction.
- reading: the equation that lingers after Newton is the one whose
  linearisation is weakest, and lag 1 does not change it, so a stale Jacobian
  is not the cause. Since `Pd` dominates the norm, the global tolerance is in
  effect a test on one equation. Untested leads: per-equation scaling
  (`scale_vars`), the colouring stencil against the neutral diffusion
  operator, the per-region shares (`resid_regions.tsv`, whose "core" region
  holds 99 per cent on the window checked and needs a grid check first).

### Every setting pays the same 0.28 s per Jacobian build, so the only lever is builds per iteration
- date: 2026-09-22
- status: active
- scope: the two rung-0 screening windows, every setting; PETSc profile
  fractions from the index. Report section 7.
- evidence: one finite-difference Jacobian build costs 0.27-0.30 s on every
  setting and both windows; the MUMPS factorisation 0.08 s, strumpack 0.15 s,
  superlu_dist 0.25 s, bjacobi and asm about 0. Building is 70-75 per cent of
  every run that keeps MUMPS, factorising 21 per cent, linear solves and
  residual evaluations under a tenth together. Builds per Newton iteration:
  0.51 baseline, 0.69 lag 2, 1.2 lag 1, 0.24 lag 10 and 20, 1.7 for the
  controller gains kI 0.3 kP 0.7 (retried steps).
- rule: seconds per iteration is builds per iteration times 0.28 s plus a
  fifth for the factorisation. Rank a setting by iterations times builds per
  iteration; no preconditioner or Krylov setting in the search space changes
  the price of a build. Only a change to the colouring, the stencil or the RHS
  would.

### The end-of-step residual is set by the tolerance, not by the setting or the step
- date: 2026-09-22
- status: active
- scope: the two rung-0 screening windows, every setting; `snes_global_residual`
  per output step from the bundles. Report section 8.
- evidence: median end-of-step residual 2e-4 to 6e-4 on every setting; log-log
  slope against the timestep at the output 0.03 over every run on both
  windows; orders dropped across a window within -0.7 to +0.7 for every
  setting.
- rule: on a window, read the residual's split between equations (section 6),
  never its level. See the root findings entry on `resid_drop` and
  `resid_per_rhs`.

### Lag 1 wins twice: fewer iterations per step, and the controller rewards that with bigger steps
- date: 2026-09-22
- status: active
- scope: the two rung-0 screening windows; per-internal-step histories from
  the bundles' `snes_steps.tsv`. Report section 9.
- evidence: on 3.0-3.2 ms the baseline takes 277 steps at 3.9 Newton
  iterations each, lag 1 121 steps at 2.8: of the 3.2-fold fall in iterations,
  1.4 is per step and 2.3 is fewer steps, because the controller grows the
  step when a solve is short (mean step 1.7 µs against 0.7). The controller
  gains kI 0.3 kP 0.7 reach 15-20 µs steps and take 40 steps; `target_its=3`
  holds the step under a microsecond and takes 323. Failed solves, each
  retried with a shorter step: about a fifth of the baseline's steps, a
  quarter of lag 1's, more than half of the gains' (23 of 40), almost none
  with `target_its=3`. The gains win on 3.0-3.2 ms (0.34) while discarding
  most of their solves, because the surviving steps are so long.
- rule: the lag and the controller are one mechanism. A setting that shortens
  the Newton solve is rewarded again by the controller; judge a controller
  setting by its failed-solve fraction as well as its wall time, and take the
  failure fraction into the rung-1 decision on the gains.

### The residual norm sits at the core edge all run long; the neutral floor cells hold it only through the 2-10 ms transient
- date: 2026-09-22
- status: active
- supersedes: the same-day entry "The whole residual norm sits in a few cells
  at the inboard core edge, where the neutrals are at their floor", which
  read two 4.0-4.1 ms dumps. Three of its claims were wrong: the cells are at
  the OUTBOARD midplane (the core ring spans R 0.325 m at the inboard
  midplane, theta 22, to 0.685 m at the outboard, theta 76; the finding's
  cells at 0.61-0.69 m are outboard); the cells are not fixed in time; and
  "at their floor" is the solver's scaling floor, not a density floor.
- scope: all six overnight test4 100 ms runs (three baseline, three lag 1),
  the dumps at their 50 outputs 2 ms apart, every `resid_*` field with guards
  cleared, per output. Tables cached in the store under
  `investigations/I01-2026-09-22-core-edge-residual/data/` as
  `neutral_cells_vs_time.csv` and `allsys_cells_vs_time.csv`, made by its
  `make_tables.py`; report `reports/investigations/I01-2026-09-22-core-edge-residual.pdf`.
  Tracker: Investigation 01.
- evidence, location: the residual summed over all seven equations sits in
  the first five interior radial cells at the core boundary (x 2-6) at every
  output of every run, median share 0.98-1.00 in each third of the run; the
  ten largest cells hold 0.7-0.95 of it.
- evidence, equation and cells: the neutral equations (Pd, NVd) and NVd+
  hold the norm only to about 10 ms; after that the neutral share is zero in
  every run (bundle `series.tsv`). Under lag 1 `Pe` holds 0.98-1.00 of it
  from 12 ms to the end; under the baseline `Pe` and `NVd+` trade it output
  by output until about 40 ms and `Pe` holds it alone after. Only one output
  per run, at 4 ms, has Pd as the largest equation (one lag-1 repeat: 10 ms
  too). At 2-6 ms the peak is at the outboard midplane core edge (theta
  72-80); afterwards it sits in the core-edge cells beside the upper and
  lower X-points on both sides (theta 12-15, 28-31, 66-68, 82-84 at x 2-4),
  where Pe is the domain maximum, 1.9e4 Pa at Te 3.7 keV, at no floor.
- evidence, floor: the dump's `resid_*` fields are `output_f = snes_f`, and
  `snes_f` is the SCALED residual (`scaled_rhs_function` divides by
  `var_scaling_factors`), so the shares are what the convergence test ranks.
  At the early peak cells Nd/Nnorm is 1.6e-5 to 6e-5 (Nnorm 1e17), within a
  factor of a few of the rtol = 1e-5 scaling floor; the domain minimum is
  0.7e-5 to 1.4e-5 up to 10 ms, 2e-5 at 16 ms, 1e-3 by 40 ms, and the neutral
  share vanishes as it climbs. No physics floor sets 1e12 m^-3: `[d]
  density_floor` is 1e-8 normalised (1e9 m^-3) and `neutral_mixed` floors at
  zero. This is the scale_vars floor bug in the tracker, seen from the dumps.
- evidence, cost: the share of Newton iterations spent by 12 ms, the end of
  the neutral phase, is 0.92-0.93 for the baseline repeats and 0.79, 0.71,
  0.56 for the lag-1 repeats (0.85-0.87 and 0.37-0.69 inside 2-6 ms;
  `snes_steps.tsv`, time / 95788). Every screening window sits in that phase.
- caveats: a time-mean of squared residual is weighted by each output's
  total, which varies by fifteen orders of magnitude between outputs, so the
  report's section 7 map shows the output with the largest total; two
  outputs of the coasted lag-1 repeat (4 and 12 ms) hold residual values of
  1e15 and 0.5 over 100-160 cells in the inner divertor legs, unlike every
  other output (`output_f` can be a blend, snes.cxx 1203-1204).
- rule: the campaign measured every setting in the scaling-floor regime,
  where under ten neutral cells at the outboard midplane core edge decide
  convergence and most of the cost is spent. Before tuning further, decide
  the scaling-floor bug; a fix changes what every setting was measured
  against. After the transient the residual is a plasma matter, Pe above all,
  at the X-point corners of the core edge, which no setting here touched.

### The 2-3 ms transient has a cliff at 2.65 ms that the baseline falls off and lag 1 does not
- date: 2026-09-22
- status: active
- scope: test4_2.0-3.0ms, baseline and lag 1, all three repeats of each; the
  bundles' snes_steps.tsv. Report section 11, second figure.
- evidence: all six runs climb together to steps of tens of microseconds.
  At 2.65 ms the three baseline repeats collapse, within a few steps of each
  other, to steps under 1 µs with failed solves on most of them, and never
  recover: two thirds of their 1100-1700 Newton iterations are spent after
  2.65 ms. The three lag-1 repeats hold 30-100 µs steps through the same
  stretch (80-130 iterations for the window) and diverge from each other
  earlier and more gently: one dips at 2.5 ms, two fall off in the last 0.1 ms.
- reading: the repeat spread on this window is the sensitivity of a cliff,
  not a noise floor. Something at 2.65 ms puts the lagged solver into a
  failed-solve regime; a fresh Jacobian gets through it. Whether this is the
  same event that produced 4455/3104/2442 iterations on the full runs is
  untested; the full runs' step histories would say.
- rule: do not size repeats on this window from a spread measured elsewhere,
  and when the non-determinism is investigated, start at 2.65 ms.

### On rung 1 the gains change the iteration count and nothing else
- date: 2026-09-22
- status: active
- scope: the controller study's rung-1 windows, every cell; controller report
  section 5.
- evidence: one Jacobian build costs 0.28-0.29 s on every rung-1 cell and is
  three quarters of every run; the gains build 1.68 Jacobians per Newton
  iteration against lag 1's 1.29 (more retried solves) and win anyway. Neutral
  pressure holds 0.50-0.75 of the residual norm under every setting; the one
  shift is the gains on 4.0-5.0 ms, where their long steps move 0.31 of the
  norm onto NVd+, as lag 1 did on 2.0-3.0 ms.
- rule: the controller cannot touch the residual that sits at the inboard
  core edge; that is a physics or boundary change, not a solver setting.

### The SCOTCH MUMPS ordering aborts the run before the first solve
- date: 2026-09-22
- status: active
- scope: study 3, slot 2, every trial carrying petsc:mat_mumps_icntl_7=3.
- evidence: six trials so far, five repeats on test4_3.0-3.2ms and one on
  test4_4.0-4.1ms, all dead with rank 0 on signal 6. The stack is inside the
  ordering itself: SCOTCH_graphOrderList -> _ESMUMPSorderGraph ->
  mumps_scotch_ -> dmumps_ana_driver_, so MUMPS aborts in its analysis phase
  and the solver never runs. The log stops after the first residual line and
  no field is out of range, which is why this reads as a crash and not as a
  divergence.
- reading: icntl_7 = 3 selects SCOTCH, and the SCOTCH in this PETSc build
  (petsc-3.23.3, arch-linux-c-opt) cannot order this matrix. That is a
  property of the build, not of the campaign's physics or of lag_jacobian:
  the same cell carries the controller gains that work everywhere else.
- cost: each trial dies within a second, so the whole cell costs about the
  25 s of window-making and extraction per trial and nothing in solver time.
  It was left to run out rather than interrupted mid-night.
- rule: the search space should refuse icntl_7 = 3 on this machine until the
  PETSc build is rebuilt with a SCOTCH that works, so no later study spends
  trials on it. The other MUMPS orderings in the study are untouched by this.

### Reusing the last solution as the KSP initial guess kills every run
- date: 2026-09-23
- status: active
- scope: study 3, slot 2, every trial carrying
  solver:kspsetinitialguessnonzero=true on the controller gains and lag 1.
- evidence: ten of ten diverged, five repeats each on test4_3.0-3.2ms and
  test4_4.0-4.1ms, in 14-17 s. Each died the same way: SNES reason -3, the
  linear solve, twenty failures in a row, then "Too many SNES failures (20)".
  The 4.0-4.1 ms runs reached 0.002 ms of the window and the 3.0-3.2 ms runs
  recorded no simulated time at all. Every field was finite at the failure,
  with Nd+ at 1979 and Pd+ at 7510 in normalised units, so nothing had blown
  up: the linear solve simply never converged.
- reading: a nonzero initial guess and a lagged Jacobian do not mix here. The
  guess is the previous step's solution, and with lag_jacobian=1 the operator
  it is fed to is one step stale, so fgmres starts outside the basin the
  stale operator can correct. Untested whether it also fails with a fresh
  Jacobian; nothing in this study runs that pair.
- cost: about 2.5 minutes of slot time for the whole cell.
- rule: do not combine kspsetinitialguessnonzero with a lagged Jacobian. If
  the option is worth another look, test it at lag_jacobian=0 first.

### The gains on lag 1 hold over the whole 100 ms run
- date: 2026-09-23
- status: active
- scope: study 3 (store report S03), rung 2, five repeats each.
- evidence: gains kI 0.3, kP 0.7 on lag 1: 607 to 1442 s, 0.39 of the
  baseline (range 0.24 to 0.56); with max_nonlinear_iterations=20, 0.34
  (0.25 to 0.46); lag 1 alone 0.65; baseline 1892 to 2862 s. End states
  within 0.04 per cent of the baseline's.
- reading: the cap is inside the gains' own 2.4x spread, so it is neither a
  win nor a loss.
- rule: the gains on lag 1 are the recipe to beat on test4.

### kI 0.6, kP 0.7 is the only gain point that beats the gains at rung 1
- date: 2026-09-23
- status: active
- scope: study 3 slot 3, four grid points at rung 1, three repeats.
- evidence: 0.89 of the gains on 3.0-4.0ms and 0.14 on 4.0-5.0ms (34 to 35 s,
  65 iterations, 4 failed solves, mean step 47 us); 0.84 on the 2-3 ms cliff
  window over ten repeats. End states within 0.1 per cent.
- rule: take it to the full run at five repeats before calling it.

### The predictor off and target 10 are fast but land somewhere else
- date: 2026-09-23
- status: active
- scope: study 3 slot 2, layered on the gains.
- evidence: predictor=false is 0.04 of the baseline on 4.0-5.0ms (64
  iterations, no failed solves) but its end state is 1.4 to 1.5 per cent off
  the baseline's where every other setting is within 0.1; 0.2 to 0.3 per cent
  on the 0.1 ms windows. Its residual ends ten times higher and moves onto
  NVd+. target_its=10 with the cap at 20 is 3.6 per cent off at the end of the
  cliff window, against 2.3 for the gains alone.
- reading: both pass the 5 per cent tolerance, but the gap may grow over a
  longer run; a smaller residual is not being reached.
- rule: no win until a full run shows the end-state gap does not grow.

### A step ceiling doubles the cost of the full run
- date: 2026-09-23
- status: active
- evidence: gains with max_timestep=1000 (10.4 us): 2.08 of the baseline on
  0-100 ms, 12,000 iterations against 1300 to 2600 for the gains. It won on
  4.0-4.1ms (0.80 of the gains) and lost on everything longer.
- rule: never cap the step on this test; the quiet 6-100 ms stretch is where
  long steps pay.

### The gains are the tightest reference; the baseline and lag 1 are wide on the cliff
- date: 2026-09-23
- status: active
- evidence: ten repeats on 2.0-3.0ms: baseline 213 to 382 s (1.8x), lag 1 36
  to 140 s (3.9x), gains 27 to 28 s. On 4.0-4.1ms lag 1 is 79 to 81 s over
  five repeats.
- rule: quote future ratios against the gains.

### The rung-0 gain grid is too rugged to screen on
- date: 2026-09-23
- status: active
- evidence: neighbouring grid points differ by 2 to 8x on 0.1 ms windows, and
  the two screening windows disagree (kI 0.45, kP 0.85: 0.27 of the gains on
  3.0-3.2ms, 0.85 on 4.0-4.1ms). Rung 0 to rung 1 verdict agreement over all
  settings was 0.83 and 0.74.
- rule: screen controller settings on whole-millisecond windows only.
