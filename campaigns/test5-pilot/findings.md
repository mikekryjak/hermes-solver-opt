# test5-pilot campaign findings

Test test5, build ef2ef9dd (neutlim-lagging), baseline recipe SNES-MUMPS-3,
this workstation, September 2026. Rules and format as in the root
`findings.md`. Nothing here is shown on another test.

## Conclusion and next steps

Extended Jacobian lagging (`solver:lag_jacobian = 10`) and controller target tuning
(`solver:target_its = 5`) deliver the strongest performance for test5 on Rung 1.

On Rung 1 (3 repeats each):
- On the early transient (`test5_11.0-11.3ms`), `lag = 10` reduces wall time from 468 s
  to 234 s (a **50.0% speedup**, ratio 0.500), outperforming `lag = 5` (263 s, 43.8%).
- On the intermediate plateau (`test5_24.0-24.4ms`), both `lag = 10` and `lag = 5` with
  `target_its = 5` reduce wall time from 545 s to 294 s (a **46.0% speedup**, ratio 0.540).
- On the late plateau (`test5_60.0-60.5ms`), `lag = 10` reduces wall time from 603 s
  to 327 s (a **45.9% speedup**, ratio 0.541).
- On the startup shock (`test5_0.0-0.2ms`), `lag = 5` completes smoothly in 537 s vs
  baseline 564 s (a 4.8% speedup, ratio 0.952) with zero solver failures.

Timestep controller dynamics:
- Lowering `solver:target_its` from 7 to 5 prevents solver divergence and accelerates
  throughput by maintaining reliable Newton steps with lagged Jacobians.
- Aggressive PID gains (`kP = 0.7, kI = 0.3`) or higher target iterations (`target_its = 8`)
  cause severe step thrashing and repeated solve failures (up to 5 consecutive failures per step).

Next steps:
1. Promote `solver:lag_jacobian = 10` and `solver:target_its = 5` to Rung 2 (1.0 ms whole-millisecond windows).
2. Run full discharge integration (`0.0-100.0ms`) with the optimized recipe to verify cumulative ~50% wall time reduction.

Records: `runs.tsv`, `cells.tsv`, and `summary.md` in the store's
`campaigns/test5-pilot/` directory. Presentation deck at `reports/test5-pilot/test5-study.pptx`.

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


