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

(none yet)

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
