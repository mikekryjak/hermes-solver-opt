# test5-recipe campaign findings

Test test5, build ef2ef9dd (neutlim-lagging), baseline recipe SNES-MUMPS-4,
this workstation, from 2026-09-24. Rules and format as in the root
`findings.md`.

## Conclusion and next steps

SNES-MUMPS-3 with line search bt is the fastest setting on test5's 1 ms
windows: 0.38 of SNES-MUMPS-3's time and 0.77 of CVODE-1's over the four
windows, end state within 0.07 per cent (study 2). bt cuts failed solve
attempts from 761 to 237 a run and removes every divergence-limit failure;
the rest are line-search failures (83 per cent). CVODE-1 takes 0.50 of
SNES-MUMPS-3 (study 1). The registered baseline SNES-MUMPS-4 is slower than
SNES-MUMPS-3 on every window it finished (1.40x, 1.59x), so test4's promotion
does not carry to test5.

Paused 2026-09-25 by the user: the failed solves look like a code problem,
to be fixed before further optimisation, in a development campaign that
instruments them (the priority). bt is not registered as a recipe: it is a
test5 result, and a recipe should help every test. Study 2 part 2 is shelved.

Records: `s01-results.md` and `runlog.md` in the store's
`campaigns/test5-recipe/`; study 2 report
`reports/test5-recipe/S02-2026-09-25-failure-fixes.pdf`.

## Findings

### Line search bt runs test5 2.4-3.0x faster than SNES-MUMPS-3 by cutting failed solves
- date: 2026-09-25
- status: active
- scope: test5, build ef2ef9dd, rung 0 (four 1 ms windows), 2 runs a cell, slot 2 alone.
- evidence: S02 report. Sum of four windows: bt 1159 s, CVODE-1 1507 s (study 1,
  two slots busy), SNES-MUMPS-3 3063 s. Failed attempts a run 237 against 761;
  Jacobian builds a Newton iteration 0.74 against 1.8, at the same 0.165 s a build.
- inferred: fewer failures let the Jacobian lag run, since each failure resets it.
- open: what a line-search failure (reason -6) is; bt against CVODE-1 on the
  11-12 ms window (264 s against 271 s) is inside the load margin.

### The divergence test protects SNES-MUMPS-3 runs on test5
- date: 2026-09-25
- status: active
- scope: test5, SNES-MUMPS-3, petsc:snes_divergence_tolerance -3 (off on PETSc 3.23).
- evidence: all 8 runs stopped within 0.02 ms. Monitor lines show the residual
  growing to 4e37, fields reaching zero, then linear-solve failures (reason -3)
  until the 20-failure limit.

### Iteration cap 20 trades cap failures for divergence, with no speed-up
- date: 2026-09-25
- status: active
- scope: test5, SNES-MUMPS-3, 2 runs a cell.
- evidence: cap failures 49 -> 16 per cent of failures, divergence 46 -> 77,
  failures a run 761 -> 630; wall 0.91-1.12x SNES-MUMPS-3.

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
