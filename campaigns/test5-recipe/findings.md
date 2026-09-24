# test5-recipe campaign findings

Test test5, build ef2ef9dd (neutlim-lagging), baseline recipe SNES-MUMPS-4,
this workstation, from 2026-09-24. Rules and format as in the root
`findings.md`.

## Conclusion and next steps

None yet: study 1 queued 2026-09-24.

## Findings

### test5's cost is flat, so a 1 ms window samples the full run
- date: 2026-09-24
- status: active
- scope: test5 on SNES-MUMPS-3, build ef2ef9dd.
- evidence: the parent run's per-output wall times (BOUT.log.0 of
  test5_0.0-100.0ms-2026-09-19-neutlag-va-repeat): 530-730 s per simulated
  ms from 1 ms to 100 ms, 1070 s for 0-1 ms; 60580 s in total.
- rule: size test5 windows at 1 ms; shorter ones carry more of the
  timestep ramp after the restart (not yet measured on this machine).
