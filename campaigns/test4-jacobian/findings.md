# test4-jacobian campaign findings

Test test4, build ef2ef9dd (neutlim-lagging), baseline recipe SNES-MUMPS-3,
this workstation, September 2026. Rules and format as in the root
`findings.md`. Nothing here is shown on another test.

## Conclusion and next steps

Rebuild the Jacobian every Newton iteration: `solver:lag_jacobian = 1` beats the
baseline on every rung, and the whole win is two and a half to three times
fewer iterations at about twice the cost each. On the full 100 ms run it is
0.39 to 0.74 of the baseline wall time across three repeats, mean 0.55; quote
the range, never the mean alone. All six full runs pass the correctness check
against the parent.

Lag 1 is the recipe to beat. Nothing layered on it wins on both screening
windows; every preconditioner and Krylov change loses. The one lead is the
timestep-controller gains kI 0.3, kP 0.7, which win on one rung-0 window and
lose on the other.

Decisions for the user:

1. Whether the controller gains go up to rung 1 (tracker: next-rung decision).
2. Whether the non-determinism through the 2-6 ms transient must be understood
   before more repeats are bought (tracker: the non-determinism bug).
3. Whether the next campaign on this test starts from lag 1 as its baseline.

Records: the runlog, tables and figures in the store's campaign directory;
the report script `analysis/report_test4_jacobian.py` in the store.

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
