# Diagnostic signal inventory

Phase 2 of the diagnostics deep-dive (R9/R10): everything capturable today,
with no code changes. Source-grounded; file:line refer to
`/home/mike/work/hermes-3/external/BOUT-dev` unless stated. Gathered by survey
agents, spot-checked by hand where marked.

Cadence terms: "output step" = a dump write; "solver step" = an internal
timestep, of which there may be many per output step.

## Always in the dump, every solver

Written by `RunMetrics` every output step (`src/bout++.cxx:1011-1025`), plus
`tt` and `hist_hi` from `Solver::outputVars` (`src/solver/solver.cxx:694-741`).

| Signal | Meaning |
| --- | --- |
| `ncalls`, `ncalls_e`, `ncalls_i` | RHS evaluations — total, explicit, implicit |
| `wtime` | wall seconds for this output step |
| `wall_time` | cumulative wall seconds |
| `wtime_rhs`, `wtime_invert`, `wtime_comms`, `wtime_io` | wall time split by activity |
| `wtime_per_rhs`, `wtime_per_rhs_e`, `wtime_per_rhs_i` | cost per RHS evaluation |
| `tt`, `hist_hi` | simulated time, output index |

This is the single most important row in the inventory: a machine-independent
cost measure (`ncalls`) and a partial cost breakdown already exist for every
solver, in the dump, with nothing switched on.

## Solver-specific, in the dump

| Solver | Signals | Needs `diagnose` |
| --- | --- | --- |
| cvode | `cvode_nsteps`, `nfevals`, `nniters`, `npevals`, `nliters`, `last_step`, `last_order`, `num_fails`, `nonlin_fails`, `stab_lims` (`impls/cvode/cvode.cxx:179-196`) | no |
| arkode | `arkode_*` equivalents (`impls/arkode/arkode.cxx:168-177`) | no |
| snes / beuler | `snes_local_residual`, `snes_global_residual`; `snes_pseudo_*` in pseudo-transient mode (`impls/snes/snes.cxx:1707-1744`) | no |
| snes / beuler | `resid_<var>` per evolved field | yes |
| petsc (TS) | none — no `outputVars` override | — |
| imexbdf2 | none — no `outputVars` override | — |
| ida | none, no diagnostics at all | — |

CVODE counters are cumulative since solver start; differencing consecutive
samples gives per-output rates.

## Log only (`BOUT.log.0`)

| Signal | Cadence | Condition |
| --- | --- | --- |
| `Sim Time / RHS evals / Wall Time / Calc Inv Comm I/O SOLVER` table | output step | always |
| SNES `nl iter`, `lin iter`, `reason`, `timestep`, SNES failures (`impls/snes/snes.cxx:961-973`) | output step | `solver:diagnose=true` |
| Same line format for the TS-based `petsc` solver (`impls/petsc/petsc.cxx:151-156`) | solver step | `diagnose=true` |
| imexbdf2 `linear_fails`, `nonlinear_fails`, order, dt | output step | `diagnose=true` |
| CVODE counter summary | output step | `diagnose=true` — duplicates the dump, so redundant |

`BOUT.log.*` is overwritten on restart. Anything that lives only here is lost
when a case is restarted, which is most of the SNES record.

Existing parser: `/home/mike/work/sdtools/cli/cmonitor.py:279-318` extracts
time, timestep, nniters, nliters, reason from the SNES lines.

## PETSc options — available, mostly unused

`[petsc]` forwards every key verbatim to PETSc with a `-` prefix and no
whitelist; a bare key means true (`src/sys/petsclib.cxx:28-58`). So any PETSc
diagnostic is one input-file line away.

Enabled somewhere today: `log_view` (SNES-MUMPS-1, SNES-MUMPS-2, TS-PSEUDO-1).
Commented out everywhere: `snes_monitor`, `snes_converged_reason`,
`ksp_converged_reason`, `ksp_monitor_short`, `ts_monitor`.
Never mentioned: `snes_view`, `ksp_view`, `-info`, `-memory_view`, any
file-redirected `log_view` form, any residual-history option.

For CVODE with `cvode_precon_method=petsc`, KSP options need the
`cvode_petscpre_` prefix, hardcoded at `impls/cvode/cvode.cxx:480`.

## Gaps against R9

| R9 asks for | Status |
| --- | --- |
| PETSc `log_view` profiling report | Enabled in 3 recipes but discarded — see below |
| Time-history outputs | Largely present via RunMetrics and CVODE counters |
| Per-equation residual norm shares | SNES only, `diagnose=true`, and only as an unpackaged notebook |
| The residual itself | SNES only (`snes_local_residual`, `snes_global_residual`) |
| Time derivatives | `ddt(*)` present when component `diagnose` flags are on |

Not available from any solver without new C++: SNES iteration counts and
convergence reasons as dump variables; anything at all from the TS `petsc` and
`imexbdf2` solvers; PETSc convergence-history arrays (nothing in the codebase
calls `SNESSetConvergenceHistory`, `KSPSetConvergenceHistory` or
`PetscLogView`).

## The log_view problem (verified by hand)

`log_view` is active in three recipes, but PETSc writes that report to stdout at
`PetscFinalize`, and BOUT++ neither captures nor reformats it. `sdrun.py` ends
in `os.execvp` (`/home/mike/work/sdtools/cli/sdrun.py:307`), so stdout goes
wherever the launching shell sent it.

Searched the whole perftests tree for a `log_view` report signature: zero hits.
Every profiling report generated so far has been thrown away. `sdtools`
already has a parser for these tables (`hermes3/logparse.py`), with nothing to
parse.

Fixing this needs no code — only redirecting stdout to a file at launch, which
belongs in the run skill (R22).

## Reuse candidates found

- `hermes3/logparse.py` — PETSc log_view table parser, ready and unused.
- `cmonitor.py:279-318` — SNES log line parser.
- `case_comparison/provenance.py` — option and commit extraction, but recomputed
  per report, not persisted.
- `caseplan` — the only persisted run record in sdtools (`cases.csv`,
  `case.json`), oriented at case bookkeeping rather than solver diagnostics.
  It is also the only part of sdtools with tests.

Watch out: the "ms simulated per 24 h" speed metric is implemented four times
across sdtools with different smoothing (`cmonitor.py:240`,
`hermes3/plotting.py:906` with a 20-point rolling mean, `plotting.py:2073`,
`case_comparison/scalars.py:100`). Two numbers from different implementations
are not comparable.

Known defect: `cmonitor -t` raises `NameError` — it references
`wtime_per_stime`, which is never defined.
