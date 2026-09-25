# test5-recipe campaign findings

Test test5, build ef2ef9dd (neutlim-lagging), baseline recipe SNES-MUMPS-4,
this workstation, from 2026-09-24. Rules and format as in the root
`findings.md`.

## Conclusion and next steps

CVODE-1 as written runs test5's 1 ms windows in 0.50 of SNES-MUMPS-3's time
(0.37-0.60 per window), with the end state within 0.1 per cent. The best SNES
setting, SNES-MUMPS-3 with lag 10 and target_its 5, takes 0.72. The registered
baseline SNES-MUMPS-4 is slower than SNES-MUMPS-3 on every window it finished
(1.40x, 1.59x), so test4's promotion does not carry to test5.

Next steps (the user decides): a full 0-100 ms run of CVODE-1 beside
SNES-MUMPS-3 with lag 10 and target_its 5 (estimates from the window sums:
about 8 h and 12 h, against 16.6 h for the parent); a CVODE screen on
rung 0 (CVODE-2, CVODE-STRUMPACK-1, tolerances, max order).

Records: `s01-results.md` and `runlog.md` in the store's
`campaigns/test5-recipe/`.

## Findings

### CVODE-1 halves test5's wall time against SNES-MUMPS-3 on 1 ms windows
- date: 2026-09-25
- status: active
- scope: test5, build ef2ef9dd, rung 0 (four 1 ms windows), 2 runs a cell.
- evidence: `s01-results.md`. Sum of four windows: CVODE-1 1507 s,
  SNES-MUMPS-3 + lag 10 + target_its 5 2173 s, SNES-MUMPS-3 3028 s,
  SNES-MUMPS-2 3990 s. CVODE-1's two runs per window agree to the iteration.
- rule: on test5, compare every new SNES setting against CVODE-1 as well as the
  baseline recipe; a full run decides.

### SNES-MUMPS-4 is slower than SNES-MUMPS-3 on test5
- date: 2026-09-25
- status: active
- scope: test5, build ef2ef9dd, rung 0.
- evidence: 1440 s against 1032 s on 0-1 ms, 1170 s against 734 s on
  11-12 ms; killed past 2x SNES-MUMPS-3 on 24 and 60 ms. It makes 1.4-1.6x
  SNES-MUMPS-3's Jacobian builds (lag 1). Lag 10 on top of it recovers only to
  0.95-1.27x SNES-MUMPS-3: the faster controller costs time here, as
  test5-pilot found for lag 5.
- rule: a recipe proven on one test is checked, not assumed, on another; on
  test5 measure from SNES-MUMPS-3 until the user decides the reference.

### test5's cost is flat, so a 1 ms window samples the full run
- date: 2026-09-24
- status: active
- scope: test5 on SNES-MUMPS-3, build ef2ef9dd.
- evidence: the parent run's per-output wall times (BOUT.log.0 of
  test5_0.0-100.0ms-2026-09-19-neutlag-va-repeat): 530-730 s per simulated
  ms from 1 ms to 100 ms, 1070 s for 0-1 ms; 60580 s in total.
- rule: size test5 windows at 1 ms; shorter ones carry more of the
  timestep ramp after the restart (not yet measured on this machine).
