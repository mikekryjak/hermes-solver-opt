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

### Lagging the Jacobian costs more than it saves on the test4 transient
- date: 2026-09-21
- status: active
- scope: test4's 2-6 ms transient, build ef2ef9dd, recipe SNES-MUMPS-3, rung 0.
  NOT yet shown at rung 1 or 2, nor on test2 or test5.
- evidence: rung 0 batch 1 of the test4-jacobian campaign, `solver:lag_jacobian`
  at 1, the baseline's 3, 10 and 20, on three windows.

  | window | lag 1 | lag 3 | lag 10 | lag 20 |
  |---|---|---|---|---|
  | 2.0-3.0ms | 36 s / 81 | 213 s / 1094 | killed | killed |
  | 3.0-3.2ms | 126 s / 273 | 205 s / 1082 | 238 s / 2404 | 234 s / 2404 |
  | 4.0-4.1ms | 79 s / 170 | 129 s / 646 | 174 s / 1779 | 173 s / 1779 |

  Wall seconds / nonlinear iterations. Cost rises monotonically with the lag on
  every window. Solver failures track it: 1, 54 on the 2.0-3.0 ms window.
  Target density and temperature agree to about 5e-5 across all four settings
  on both short windows.
- rule: rebuild the Jacobian every iteration on this transient. The fresher
  Newton direction cuts nonlinear iterations by 4 to 13 times, which more than
  pays for the extra assembly. The production recipe's lag of 3 is a cost, not
  a saving, and the search space's range of 1-20 has its optimum at the floor,
  so the range may need to open below 1 if the knob allows it.
- caution: the two killed cells are the cutoff ratchet, not a result. Their
  target values come from partial windows and must not be compared.

### The Jacobian lag saturates above about 10, which measures the timing noise
- date: 2026-09-21
- status: active
- scope: test4 rung-0 windows; the mechanism should hold wherever SNES
  converges in fewer iterations than the lag.
- evidence: at lag 10 and lag 20 the solver does identical work -- 2404 and
  2404 nonlinear iterations on test4_3.0-3.2ms, 1779 and 1779 on
  test4_4.0-4.1ms, the same solver_fails, and target values identical to every
  printed digit. Beyond the iterations a solve actually takes, a larger lag
  changes nothing.
- rule: treat lag_jacobian above roughly 10 as one setting, and do not spend
  runs sampling it. The saturation is also a free control: two runs doing
  provably identical work differed by 1.7% and 0.6% in wall clock, at
  concurrency 2.35 against 1.81 and 2.05 against 2.00, with the more loaded run
  slower both times. That is the project's first same-work timing comparison,
  and it puts wall-clock noise plus loading at a few per cent, well inside the
  15% rung-0 bound. It is two pairs, not a distribution.

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
