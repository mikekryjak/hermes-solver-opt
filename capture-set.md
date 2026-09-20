# Capture set

Phase 3 of the diagnostics deep-dive (R9), agreed 2026-07-30. What gets
recorded on every run, what only on short tests, and why. Built on
`diagnostics-inventory.md`. Decisions already taken: `diagnose = true`
everywhere, SNES is what we optimise with CVODE as reference (R26), overhead
accepted (R21).

This is now the specification the extractor (so-s0b.1) is built against, not a
proposal. Changing it means changing what future runs record, so it changes by
edit and review, not by drift.

## Core — every run, no exceptions

Run setup:
- `[solver] diagnose = true`. Gates the SNES per-step log line and the
  `resid_<var>` fields. Without it the SNES record is nearly empty.
- stdout redirected to a file beside the run. Everything PETSc prints goes to
  stdout, and today all of it is discarded (F6).

From the dump, free on every solver — per output step:
`ncalls`, `ncalls_e`, `ncalls_i`, `wtime`, `wall_time`, `wtime_rhs`,
`wtime_invert`, `wtime_comms`, `wtime_io`, `wtime_per_rhs*`, `iteration`.
`ncalls` is per step, not cumulative, and must be summed (F7).

From the dump, free on every solver — constants, the provenance R17 asks for
without anyone declaring it:
| Constant | What it settles |
| --- | --- |
| `run_id`, `run_restart_from` | UUIDs. The second names the run this one restarted from, so the seed chain is machine-readable and does not have to be remembered. |
| `HERMES_SLOPE_LIMITER` | F1's largest confounder, recorded automatically. |
| `HERMES_REVISION`, `BOUT_VERSION` | Code identity. |
| `use_check_level` | Timings only compare at equal CHECK. |
| `NXPE`, `NYPE` | The decomposition, not merely the core count — same cores, different shape, different performance. |
| `nx`, `ny`, `nz`, `ixseps1/2`, `jyseps*` | Grid fingerprint, survives the grid file being renamed. |
| `has_*`, `use_*` | Build configuration. |

Gap: the conduction method has no dump constant, though the slope limiter does,
and F1 has it moving test5 by 32%. Until Hermes-3 records it the same way it
must be declared by hand.

From the dump, solver-specific:
- SNES — `snes_global_residual` and `snes_local_residual`, written whether or
  not `diagnose` is set (`snes.cxx:1715`), and `resid_<var>` per evolved field,
  which is gated. The global residual is one scalar per output step measuring
  distance from steady state: at fixed test length it is what separates two
  recipes that both finished, and for a failed run it says whether progress was
  being made. It is an unweighted RMS over the evolved 3D fields in normalised
  units, so it compares across recipes but not across runs with a different
  variable set or different `scale_vars` settings.
- CVODE — the `cvode_*` counters. No residual equivalent (F8).

From `BOUT.log.0`:
- the per-output `Sim Time / RHS evals / Wall Time / Calc Inv Comm I/O SOLVER`
  table (always present);
- the SNES per-output line: timestep, nonlinear iterations, linear iterations,
  convergence reason, SNES failures.

From `[petsc]`, all one-off or end-of-run, so cost does not scale with the run:
| Option | Why |
| --- | --- |
| `log_view` | The profiling report R9 asks for. Printed once at finalize. |
| `options_left` | Catches options that were set but never used. `[petsc]` has no whitelist, so a misspelled option is silently ignored and the recipe quietly does not do what it says. Set deliberately even though it is redundant: PETSc reports unused options unless the option is explicitly false (`pinit.c:1584-1587` — unset means on, and its own docs wrongly say otherwise). Keeping it states the intent and survives the default changing. |
| `snes_view`, `ksp_view` | What PETSc actually built — the provenance R17 wants, rather than what we think we asked for. NOT one-off: they print after every solve (66 and 390 times in a 2.5 minute run), so the extractor keeps only the first block and discards the rest. A 34-hour run would otherwise leave a console file of order 1 GB. |

Measured 2026-07-29 (so-r53.7): the whole set costs 1-2 s on a 155 s run,
inside the run-to-run spread. `memory_view` produced no output and is dropped.
`options_left` works and flagged `snes_fd_color_use_mat` — set in three recipes
— as never used by PETSc (F12). It had in fact been reporting that on every run
ever done; what changed was capturing stdout, not setting the option.

## The log_view event table is data, not a report

Its event table is around fifty rows by eight columns — call count, time, flop
rate, message counts, and each event's percentage of the run. Stored as text it
is a thing to read; parsed into a table it is the cost breakdown that says which
lever to pull. It is a few kilobytes either way, so the bundle keeps both: the
raw report as evidence, and a parsed table as the analysis input.

Measured on test4steady (see F13) the breakdown was 78% building the Jacobian,
15% factorising it, 1% solving the linear system. Wall clock alone says only
that a run was slow; this says why.

## Residual fields: keep at run time, reduce to metrics at extraction

The `resid_<var>` fields are seven extra 2D fields per output step. They stay on
for every SNES run and are reduced to derived metrics when the record is
extracted, after which the dumps are deleted (R8).

The reason for reducing them is not disk — see the measurement below, which
settles disk as a non-issue. It is that the fields cannot outlive the dump and
the metrics can. Analysis reads the metrics anyway, and after R8 deletion the
fields are gone whether or not anything was derived from them.

Measured on a completed scratch-length run — `test4scratch-2026-07-29-master-mc-mumps2`,
SNES-MUMPS-2, 451 output steps, 2044 MiB of dumps across 10 files:

| Field group | Gated on `diagnose` | Per output step | Whole run | Share of dumps |
| --- | --- | --- | --- | --- |
| `resid_<var>` — 7 fields | yes | 0.299 MiB | 135 MiB | 6.6% |
| `snes_local_residual` | no — always written | 0.043 MiB | 19 MiB | 0.9% |

So `diagnose = true` costs 6.6% of the dump at full scratch length — the same
0.342 MiB per step the short test4steady runs showed, because the cost is
exactly grid cells × fields × 8 bytes and does not vary with run length. test5
is cheaper, not dearer: 2800 cells per step against test4's 5600, so the same
seven fields cost 0.15 MiB per step there.

Note in passing: `snes_local_residual` is a full 3D field written on every SNES
run whether or not `diagnose` is set, so a run recorded as having no diagnostics
still carries 19 MiB of residual field at scratch length. It is free information
and the extractor should use it, but it also means "diagnostics off" is not a
clean control for disk.

That settles it as a non-issue. Three concurrent scratch runs peak around 6 GiB
of dumps, of which the gated fields are 0.4 GiB, against 79 GB free. The real
disk pressure is elsewhere: `cases/perftests` holds 52 GB of accumulated dumps
on a filesystem at 91%, and the lever for that is R8's delete-after-extraction,
not the residual fields.

Decided 2026-07-30: scalars only. No residual field is stored outside the dump,
in any format, and `snes_global_residual` is recorded on every SNES run
including when `scale_vars` is on — it is cheap, and what can be read off it
under scaling is worth finding out rather than assuming.

Candidate derived metrics per output step, drawn from what the residual-norm
notebook actually uses:
- per-equation share of the total residual sum-of-squares — seven numbers,
  dimensionless, comparable across time and cases;
- `snes_global_residual`, already a scalar;
- location of the largest `snes_local_residual` cell, as a grid index or R-Z
  position;
- share of the norm falling in named regions (core, SOL, targets), probably
  time-averaged rather than per step.

That is order ten to twenty numbers per output step in place of seven full
fields, and it is what the analysis reads anyway. Which of these to compute is
still open (so-r53.6); that they are scalars is not.

Adding fields back later is not free, but it is not a one-way door either. While
a dump exists the metric set widens for nothing — re-run the extractor over the
same run. After R8 deletion it costs a re-run. Accepted 2026-07-30: that price
is fine, since older cases still on disk can be re-extracted and new tests can
be run to regenerate dumps. So deletion is not gated on so-r53.6 settling.

SNES only — CVODE writes no equivalent fields (F8), so this part of the record
does not exist for the reference solver.

The `scale_vars` weights are not recorded at all, and deliberately stay that way
for now. `var_scaling_factors` never reaches the dump; the only trace is a
`Var scaling: min -> max` log line per rescale event, gated on `diagnose`
(`snes.cxx:643-651`). So a residual recorded under `scale_vars` cannot be
un-weighted after the fact. Accepted: the global scalar is recorded anyway and
interpreted with that limit in mind.

## Extended — short tests only, never for a timed comparison

Per-iteration convergence history: `snes_monitor`, `ksp_monitor_short`,
`snes_converged_reason`, `ksp_converged_reason`, and `-info` filtered to the
classes of interest if it comes to that.

These emit once per iteration, so their cost scales with the number of
iterations — meaning they cost more on exactly the recipes that take more
iterations. A comparison timed with these on is biased in favour of whatever
converges fast, which is the thing being measured.

Rule: a run with extended capture is for understanding, not for timing. Its
wall-clock never enters the ledger as a comparable number.

## Not captured, and why

- TS `petsc`, `imexbdf2`, `arkode`, `ida` — out of scope (R26). The last three
  emit almost nothing anyway.
- PETSc convergence-history arrays — nothing in the codebase calls
  `SNESSetConvergenceHistory` or `KSPSetConvergenceHistory`, so this needs C++.
  The per-iteration monitors above give the same information as text.
- SNES iteration counts as dump variables — wanted, filed, deliberately not
  blocking. The log route is proven first.

## Cadence, and the joining problem

Three different clocks, and the record has to keep them straight:
- dump variables — per output step;
- the log table and the SNES line — per output step;
- PETSc monitors — per solver iteration, many per output step;
- `log_view` — once, for the whole run.

The log-overwrite problem does not apply to a test, by construction. A test is:
copy the base restart files into the test directory, overwriting whatever was
there, run once, capture the output. That is the whole test. Anything run after
that is a different test, not a continuation.

So `BOUT.log.0` is complete for the test it belongs to. Two consequences worth
writing into the run skill (R22): a run that dies and is resumed is a different
test and its timing is not comparable, so it must not be recorded as the
original; and the capture step must happen before the directory is reused,
since the next test overwrites it.

## Saving and analysing are different jobs

Capture decides what leaves the run. Extraction turns it into a stored record.
Analysis reads stored records and produces plots and comparisons. Keeping them
separate matters because they have different failure modes and different
lifetimes: capture and extraction happen once and cannot be repeated after the
dumps are deleted (R8), while analysis is rewritten as often as the questions
change.

The rule that follows: extraction must store everything analysis could
plausibly want, in a form analysis can read without parsing text. Text goes in
the bundle as evidence; every number is also stored as a table. If a plot needs
a number that was left in prose, it cannot be recovered — the run is gone.

Analysis itself belongs in the campaign script, not here (see the perftests
conventions), and reads bundles only.

## Settled

The two questions this document was left open on, and everything else decided
along the way. Numbers live in the sections above; this is the decision list.

- Time cost: accepted, measured, not revisited. `memory_view` dropped for
  producing no output.
- Disk cost: a non-issue at full scratch length. No compression, no gating, no
  per-test exceptions — the residual fields stay on for every SNES run.
- What survives extraction: scalars, never fields. `snes_global_residual` is
  recorded on every SNES run, `scale_vars` on or off, and the weights are not
  recorded. Revisitable for runs whose dumps still exist, not for ones already
  cleared.
- Table format inside the bundle: TSV, matching the index (`schema.md`). Read by
  eye and by every tool, and it diffs and compresses in git, which a binary
  table does not — the bundles live in a git repo and the point of storing them
  is that a later reader can see what changed. The per-step and per-event tables
  are a few kilobytes, so nothing faster is warranted. Revisit only if the
  per-iteration monitors are ever stored, which the extended set forbids for
  timed runs anyway.
- Float precision in those tables: write full round-trip precision (17
  significant digits). A metric re-derived from a truncated table silently
  disagrees with the same metric read from the dump, and once the dump is
  deleted there is no way to tell which was right.
