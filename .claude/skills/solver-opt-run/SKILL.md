---
name: solver-opt-run
description: >-
  Run and record a Hermes-3 performance test for the solver-opt project.
  Use when asked to run, queue, re-run, extract or record a perftest, or to
  delete a finished case directory.
---

# Running a solver-opt performance test

Builds on the `run-case` skill, which owns setup, build-check, launch and the
approval gate. Inherit that gate; do not restate it. Everything below is what
this project adds. Read `requirements.md` first — R11 outranks the rest.

## What a test is

Copy the base restart files into the case directory over whatever was there,
run once, capture the output. That is the whole test. Anything run afterwards
is a different test, not a continuation.

- A run that dies and is resumed is a different test. Never record it as the
  original.
- Capture before the directory is reused, because the next test overwrites it.

## Order of operations

Never vary this order. Each step is what licenses the next.

1. Open the row in `solver-opt-store/index.tsv` BEFORE launching: `case_dir`,
   `test`, `recipe`, `varied`, `epoch`, `note` by hand, the rest by extraction.
   At most one `planned` row per case directory.
2. Prepare: copy `$solveropt/hermes-perftest/<test>`, then `reset_test.py -y`,
   `apply_recipe.py` and `add_views.py`; a fresh test seeds from `base/`.
3. Launch per `run-case`, teeing to `BOUT.log.console` — PETSc's `log_view` report
   exists nowhere else.
4. Extract with the hermes3 Spack environment active: `extract_test.py <case>
   --store $store --recipes $solveropt/hermes-perftest/recipes`.
5. Delete the dumps only once that extraction reports validated.

Dumps are deleted only after their diagnostics are extracted AND the extraction
validated. Never before, and never for a run whose record failed validation —
deletion is irreversible and rerunning a scratch test costs a day.

## Naming a run directory

Name it `<window>-<YYYY-MM-DD>[-<desc>]`, e.g.
`test2_0.0-100.0ms-2026-09-19-neutlag-va`, with the window on a 0.1 ms grid.

- Date the run directory by the day it was set up, and leave the build commit
  out of the name: the index, not the name, is the authoritative record.
- Keep the sha in BUILD directory names, e.g. `build-va-master-a1c3ba38`, so
  rebuilds at different commits stay distinct.
- Add `<desc>` whenever the build is not plain master, naming the branch and
  every compile-time option that differs (limiter, conduction method).
- Suffix a rerun of an identical configuration `-repeat`, never `-r2` or any
  other abbreviation, and keep the rest of the name byte-identical.
- Name one run of a walk between recipes `step<N>-<what changed>`, spelled out,
  because a bare `s2` reads as slot 2.
- Name a run for its window, date and build only: slot and core range are
  measured into the index, never declared in the name.

## Rules

- Launch every run in `$data/cases/` and nowhere else, which is also where the
  grid files sit, because Hermes resolves them from the launch directory.
- Never launch into, extract from or compare against `test2dev`, `test4dev` or
  `test5dev`: they are another project's.
- The index defines what exists. A directory without a row is not a backlog
  item; never enumerate directories to find runs.
- Tag every run with its epoch (R18). Results compare directly only within an
  epoch, and across epochs only through the baselines.
- Three 10-core slots, so three concurrent runs at most. Concurrency is itself a
  variable in the timings: hold loading constant across runs being compared, and
  record it. A full machine costs about 10%; the slot itself is interchangeable.
- Classify every failure (R19): diverged at start, SNES failure, linear-solve
  failure, crawl aborted, or completed but wrong. A failed run is a result and
  gets a row; it is never left as missing data.
- Abort a crawling run when it has written no output step for two hours. Read
  progress from the dump files, not the log: a stalling run keeps writing
  solver-step lines indefinitely. Record it as `crawl_aborted` and attempt
  extraction anyway — a partial run still shows how the timestep collapsed.
- Deviations from the named recipe land in `diffs` automatically. Anything in
  `diffs` that is not in `varied` means a setting changed that nobody intended;
  resolve it rather than recording both.
