Written by Claude on 2026-09-19 from capture-set.md, diagnostics-inventory.md, the store schema and a real bundle.

# What we record about each run's performance

## Where it lives

Each run gets one row in `/home/mike/work/perftest-results/index.tsv` and one
bundle folder, `runs/<test_id>/`, beside it. The row holds scalars: one number
per quantity for the whole run. The bundle holds tables over time, plus the raw
logs as evidence. Both are written by `extract_test.py` from three sources: the
console log (`BOUT.log.console`), BOUT++'s own log (`BOUT.log.0`) and the dump
files. Dumps are kept for now, so a run can be re-extracted if we add a
quantity.

Terms used below:
- PETSc: the numerical library BOUT++ uses for its implicit solvers.
- SNES: PETSc's nonlinear solver. It takes a timestep by Newton iteration.
- Newton iteration: one linearise-and-solve update inside a timestep.
- KSP: PETSc's linear solver, run once per Newton iteration.
- Jacobian: the matrix of derivatives the Newton iteration linearises with.
- Preconditioner: a cheap approximation to the Jacobian's inverse that speeds
  up the linear solve. Ours is an exact LU factorisation by MUMPS.
- RHS evaluation: one call to Hermes-3's physics, computing every field's rate
  of change. It is the unit of physics work.
- Residual: how far the current state is from satisfying the equations.
- Output step: one write to the dump files; our windows have 50, parents 100.
- Solver step: one internal timestep taken by SNES; many per output step.

## How long did it take, and how fast?

- `wall_s` (row): wall-clock seconds for the whole run.
- `sim_time_ms` (row): plasma time actually reached. For a failed run it says
  how far it got.
- `ms_per_24h` (row): plasma milliseconds per 24 h of wall clock, averaged
  over the whole run. Other sdtools speed figures smooth differently and are
  not comparable with it.
- `steps.tsv` (per output step): wall time for that step, and its split into
  calculation, linear inversion, communication, file writing and solver time.
- `series.tsv` (per output step): the same timings as the dump records them,
  in seconds, including time spent in RHS evaluations.

## Where did the time go?

From PETSc's end-of-run profile (`log_view`), which we capture from the
console.
- `t_jac_frac` (row): share of the run spent building the Jacobian.
- `t_pcsetup_frac` (row): share spent factorising it for the preconditioner.
- `t_ksp_frac` (row): share spent in the linear solve.
- `t_func_frac` (row): share spent evaluating the residual.
- `events.tsv` (per run): the full profile, about 50 PETSc events with call
  counts, times, flop rates and message counts. The four shares above come
  from it.

## How hard did the solver work?

- `ncalls` (row): total RHS evaluations. Independent of machine speed.
- `nl_its`, `lin_its` (row): total Newton and linear iterations. With an exact
  preconditioner they are equal.
- `n_jac_builds` (row): Jacobian constructions. `ncalls` divided by this is
  roughly the RHS evaluations each build costs.
- `series.tsv` (per output step): RHS evaluations in that step.
- `snes_steps.tsv` (per solver step): plasma time, timestep size, Newton and
  linear iterations, convergence reason, and failures since the last step.
  This is the timestep history.

## Why did steps fail?

- `solver_fails` (row): total SNES failures over the run. Each one rejects a
  step, halves the timestep and forces a new Jacobian.
- `solver_fails_max` (row): the most failures in any one output step. It is
  what approaches `max_snes_failures`, the limit that stops a run.
- `outcome` (row): meant to classify the run as completed, diverged at start,
  SNES failure, linear-solver failure, crawl aborted or completed but wrong.
  See the gaps: today it is wrong for completed runs.
- `BOUT.log.0` (raw, per failure): with `diagnose_failures = true`, every
  failure prints a block with PETSc's reason code and each field's minimum and
  maximum. Only the raw log holds these; no table does.

## Which equation and region limit convergence?

- `series.tsv` (per output step): `snes_global_residual`, one number for the
  distance from steady state, and each equation's share of the residual.
- `resid_regions.tsv` (per output step): each equation's residual share within
  named regions: core, the private-flux regions, the four divertor legs, the
  upstream scrape-off layer, and any cells left unassigned.
- `resid_final`, `resid_drop`, `resid_per_rhs` (row): the global residual at the
  end, how many orders of magnitude it fell, and the fall per RHS evaluation.
- These exist for SNES runs only. With `scale_vars` on, the residual is
  weighted by scale factors we do not record, so compare it only between runs
  with the same scaling.

## Did the physics come out right?

- `physics.tsv` (per output step): outboard-midplane separatrix density and
  temperature, and the peak target density and temperature, in SI units.
- `ne_target_max`, `te_target_max` (row): the last two at the end of the run.
- `ne_sep`, `te_sep` (row): meant to hold the first two; empty, see the gaps.
- `verdict`, `max_dev`, `reference_id` (row): pass or fail against a reference
  run, the largest relative deviation, and which run was the reference.
- `ddt.tsv` (per output step and field): how fast each evolved field is still
  changing, as the RMS and maximum of its time derivative. A field near steady
  state shows a small rate relative to its own size (`rms_state`).

## What exactly was run?

- `hermes_commit`, `bout_version`, `bout_commit`, `petsc_version` (row): code
  identity, read from the logs, not declared.
- `limiter`, `check_level`, `build_type` (row): compile-time choices that
  change timings. `CHECK` is BOUT++'s level of internal checking.
- `grid`, `cores`, `decomposition` (row): grid file with a shape fingerprint,
  core count, and how the grid is split across cores.
- `recipe`, `varied`, `diffs` (row): the named recipe, what the run
  deliberately changed, and every actual deviation from the recipe.
- `run_id`, `seed` (row): the run's unique ID, and the ID of the run it
  restarted from.
- `slot`, `concurrency`, `machine`, `run_started` (row): where and when it ran,
  and how many other runs overlapped it.
- `BOUT.inp`, `BOUT.settings` (bundle): the input as run, and every option with
  its value and source.
- `petsc_views.txt` (bundle): PETSc version and any options PETSc never used.

## Gaps

Known record bugs:
- `outcome` says `snes_failure` whenever any step failed, even when the run
  completed. Recovered failures are normal, so this is wrong on most runs.
- `slot` and `hermes_branch` are empty. The launcher prints them, then
  replaces itself with `mpirun` before its output is flushed to the console.

Missing by design or not yet built:
- Failure reasons are not tabulated. `snes_steps.tsv` holds only successful
  steps, whose reasons are all "converged". The failure reasons, such as
  divergence or too many iterations, sit only in the raw failure blocks. So
  SNES failures and linear-solver failures cannot yet be told apart in a table.
- The field minima and maxima in each failure block are not extracted.
- `ne_sep` and `te_sep` are empty, because no separatrix location is agreed on
  these double-null grids. `physics.tsv` does hold them.
- `verdict` is always `no_reference`, because no reference run is linked yet.
  Test 2 now has one, set by the user.
- SNES iteration counts and convergence reasons are not in the dump files.
  They come from the log only (open task).
- `petsc_views.txt` lacks the description of the solver PETSc actually built,
  because our recipes do not request `snes_view` or `ksp_view`.
- The `scale_vars` weights are not recorded; only a min-to-max line per
  rescale sits in the raw log.
- Per-iteration convergence history (residual after each Newton or linear
  iteration) is not collected. Its cost grows with iteration count, so it is
  reserved for short diagnostic runs that are never timed.
- `conduction_method` is never filled: Hermes-3 does not record it, and nobody
  declares it.
- `diffs` covers only the recipe's `[solver]` and `[petsc]` sections. Physics
  settings such as `limiter_gradient_floor` appear in `varied` but are not
  checked against the input.
- `seed` holds BOUT++'s placeholder of repeated `z` for a run from scratch,
  not an empty cell.
- `concurrency` is stored as a fraction (e.g. 1.02), though the schema says
  integer.
