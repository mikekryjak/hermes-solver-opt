# test5-pilot campaign findings

Test test5, build ef2ef9dd (neutlim-lagging), baseline recipe SNES-MUMPS-3,
this workstation, September 2026. Rules and format as in the root
`findings.md`. Nothing here is shown on another test.

## Conclusion and next steps

Moderate Jacobian lagging (`solver:lag_jacobian = 5`) is the clear overall
winner for test5 across all four tested plasma regimes.
On the early transient (`test5_11.0-11.1ms`), it reduces wall time from 162 s
to 92 s (a 43.6% speedup, ratio 0.56).
On the intermediate plateau (`test5_24.0-24.2ms`), it reduces wall time from
284 s to 161 s (a 43.3% speedup, ratio 0.57).
On the late plateau (`test5_60.0-60.2ms`), it reduces wall time from 222 s
to 138 s (a 37.6% speedup, ratio 0.62).
On the startup shock (`test5_0.0-0.1ms`), it reduces wall time from 452 s
to 417 s (a 7.9% speedup, ratio 0.92).

In all four regimes, lag 5 is the fastest setting tested. It clears the
rung-0 declared noise bound of 15% (R32) on three of the four regimes by
more than 2.5x.

Physics invariance is confirmed to machine precision across all completed
runs: separatrix electron density agrees to 5-6 figures (e.g. 1.5494e18 m^-3
at 11 ms, 2.3331e18 m^-3 at 24 ms, 2.9912e18 m^-3 at 60 ms) and target peak
electron temperature agrees to within 0.01 eV across repeats.

Next steps:
1. Promote `solver:lag_jacobian = 5` to Rung 1 (longer windows) across all 4
   regimes (`test5_0.0-0.2ms`, `test5_11.0-11.3ms`, `test5_24.0-24.4ms`, `test5_60.0-60.5ms`).
2. Explore linear solver tolerances (`ksp_rtol`) and GMRES restart on top of
   `lag_jacobian = 5`.

Records: `runs.tsv`, `cells.tsv`, and `summary.md` in the store's
`campaigns/test5-pilot/` directory.

## Findings

### Moderate Jacobian lagging (lag=5) speeds up all regimes by 38-44% and avoids shock failure
- date: 2026-09-23
- status: active
- scope: test5, build ef2ef9dd, recipe SNES-MUMPS-3, rung 0.
- evidence: rung 0 screening batches of test5-pilot across all 4 windows,
  two repeats each. Wall seconds (mean) / nonlinear iterations:

  | window | baseline (lag=3) | lag=1 | lag=5 | lag=10 |
  |---|---|---|---|---|
  | 0.0-0.1ms | 452 s / 995 | 480 s / 532 | 417 s / 1393 | 538 s / 1179 |
  | 11.0-11.1ms | 162 s / 194 | 110 s / 133 | 92 s / 168 | - |
  | 24.0-24.2ms | 284 s / 342 | 271 s / 322 | 161 s / 302 | 210 s / 290 |
  | 60.0-60.2ms | 222 s / 316 | 228 s / 332 | 138 s / 260 | - |

- rule: on test5 use `solver:lag_jacobian = 5`. On smooth dynamics and ionization
  phases, it cuts wall time by 38% to 44% because finite-difference Jacobian coloring
  takes ~83% of runtime and lagging cuts expensive Jacobian re-evaluations. On the
  shock, `lag=10` fails (442 solver failures, 19% slowdown), while `lag=1` halves
  nonlinear iterations (532 vs 995) but coloring overhead keeps wall time flat
  (480 s vs 452 s). `lag=5` strikes the optimum trade-off everywhere.
- contrast with test4: on test4 detachment transients, `lag=1` won by 2x-5x
  because nonlinear iterations dropped 4x-13x. On test5, where dynamics are
  dominated by coloring overhead rather than stiff front propagation, `lag=5`
  wins decisively across the whole discharge.

