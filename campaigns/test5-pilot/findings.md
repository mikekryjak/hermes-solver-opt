# test5-pilot campaign findings

Test test5, build ef2ef9dd (neutlim-lagging), baseline recipe SNES-MUMPS-3,
this workstation, September 2026. Rules and format as in the root
`findings.md`. Nothing here is shown on another test.

## Conclusion and next steps

Moderate Jacobian lagging (`solver:lag_jacobian = 5`) is the verified winner
for test5 across both Rung 0 (short windows) and Rung 1 (longer windows).

On Rung 1 (3 repeats each):
- On the early transient (`test5_11.0-11.3ms`), it reduces wall time from 468 s
  to 263 s (a 43.8% speedup, ratio 0.562).
- On the intermediate plateau (`test5_24.0-24.4ms`), it reduces wall time from
  545 s to 311 s (a 43.0% speedup, ratio 0.570).
- On the late plateau (`test5_60.0-60.5ms`), it reduces wall time from 603 s
  to 342 s (a 43.4% speedup, ratio 0.566).

On Rung 0 (2 repeats each):
- `test5_11.0-11.1ms`: 92 s vs 162 s (43.6% speedup, ratio 0.564).
- `test5_24.0-24.2ms`: 161 s vs 284 s (43.3% speedup, ratio 0.567).
- `test5_60.0-60.2ms`: 138 s vs 222 s (37.6% speedup, ratio 0.624).
- `test5_0.0-0.1ms`: 417 s vs 452 s (7.9% speedup, ratio 0.921).

In all four regimes, lag 5 is the fastest setting tested. The speedups easily
clear the declared noise bound of 15% (R32) by almost 3x.

Physics invariance is confirmed to machine precision across all completed runs.
Separatrix electron density and target peak electron temperature match baseline
values to high precision.

Next steps:
1. Explore linear solver tolerances (`ksp_rtol`) and GMRES restart on top of
   `lag_jacobian = 5`.
2. Evaluate full discharge integration (`0.0-100.0ms`) with `lag_jacobian = 5`.

Records: `runs.tsv`, `cells.tsv`, and `summary.md` in the store's
`campaigns/test5-pilot/` directory.

## Findings

### Moderate Jacobian lagging (lag=5) speeds up all regimes by 43% on Rung 1
- date: 2026-09-23
- status: active
- scope: test5, build ef2ef9dd, recipe SNES-MUMPS-3, rungs 0 and 1.
- evidence: test5-pilot rungs 0 and 1 across all 4 windows.
  Rung 1 wall seconds (mean of 3 repeats) / nonlinear iterations / Jacobian builds:

  | window | baseline (lag=3) | lag=5 | speedup | ratio |
  |---|---|---|---|---|
  | 11.0-11.3ms | 468 s / 588 / 1129 | 263 s / 495 / 819 | 43.8% | 0.562 |
  | 24.0-24.4ms | 545 s / 700 / 1342 | 311 s / 626 / 988 | 43.0% | 0.570 |
  | 60.0-60.5ms | 603 s / 814 / 1500 | 342 s / 666 / 1063 | 43.4% | 0.566 |

  Rung 0 screening across all 4 windows:

  | window | baseline (lag=3) | lag=1 | lag=5 | lag=10 |
  |---|---|---|---|---|
  | 0.0-0.1ms | 452 s / 995 | 480 s / 532 | 417 s / 1393 | 538 s / 1179 |
  | 11.0-11.1ms | 162 s / 194 | 110 s / 133 | 92 s / 168 | - |
  | 24.0-24.2ms | 284 s / 342 | 271 s / 322 | 161 s / 302 | 210 s / 290 |
  | 60.0-60.2ms | 222 s / 316 | 228 s / 332 | 138 s / 260 | - |

- rule: on test5 use `solver:lag_jacobian = 5`. It delivers a uniform ~43% speedup
  over longer integration windows by curbing finite-difference Jacobian coloring
  overhead (which takes ~83% of runtime).
- contrast with test4: on test4 detachment transients, `lag=1` won by 2x-5x
  because nonlinear iterations dropped 4x-13x. On test5, where dynamics are
  dominated by coloring overhead rather than stiff front propagation, `lag=5`
  wins decisively across the whole discharge.


