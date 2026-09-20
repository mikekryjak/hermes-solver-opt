# solver-opt system design

Written 2026-09-18 by Claude, revised 2026-09-19 to the user's rulings of that
day. This is the "how". The
"why" is `requirements.md`, and every choice here names the requirement it
serves. Tasks live in beads, never here.

The design was checked against a web literature review on 2026-09-18 covering
three areas: how agents should store durable knowledge, LLMs as optimisers with
multi-fidelity ladders, and experiment tracking at scale. Where the review
changed a decision, the entry says so.

## 1. What the system is

Two layers that meet at one narrow interface.

- The runner is a plain command-line program. It prepares a case, launches it,
  watches it, extracts the record, and repeats. It has no judgement in it, so
  it runs unattended and ports to any machine.
- The optimiser decides what to try next. It may be an LLM, an algorithm, or a
  person writing a list. It reads a compact view of past results and writes a
  study file.

The interface is two operations: suggest trials, report results. Swapping the
optimiser changes nothing else.

Work is organised in campaigns. A campaign has one goal, one directory, one
budget and one approval. Inside it, a study is a batch of runs answering one
question.

## 2. Vocabulary

- Knob: one solver setting, e.g. `solver:lag_jacobian`.
- Recipe: a named block of `[solver]` and `[petsc]` settings.
- Trial: one intended configuration — test, build, recipe plus knob overrides.
- Run: one execution of a trial. A trial repeated three times is three runs.
- Parent run: a full-length run from initial conditions, at the campaign's
  build with its starting recipe. One per test per build. It supplies the seeds
  and the reference solution.
- Window: a slice of a parent run, restarted from its state at time a and run
  to time b. Named `test4_1.0-2.0ms`.
- Seed: the restart files cut from a parent run at one time.
- Rung: a set of windows of similar cost, used as one fidelity level.
- Promotion: moving a configuration from one rung to the next.
- Index: one TSV per campaign, one row per run.
- Bundle: the extracted evidence for one run.
- Store: the git repository holding campaigns, indexes and bundles.

## 3. Where everything lives

Two repositories and one data directory, split on 2026-09-20.

- The tool: `hermes-solver-opt` (public), at `/home/mike/work/hermes-solver-opt`.
  It holds this design, the requirements, the extraction layer, the runner, the
  search space file, the tracker and the agent instructions. Collaborators need
  only this repository, cloned with `--recursive`.
- `hermes-perftest` (public): the test templates, grid files, solver recipes and
  the window generator, pinned here as a submodule. Other people use these
  tests, so this project never modifies them.
- The store (private, one per user), at `/home/mike/work/solver-opt-store`:
  indexes, bundles, and the analysis that reads them.
- The data directory, at `/home/mike/work/solver-opt-data`: dumps, seeds and
  case directories. Never in git.

`sdtools` (public) holds general Hermes-3 tooling — the launcher, the report
machinery — and is shared with the user's other campaigns. Nothing in it knows
about this project, and no tool written for this project goes there.

Layout of the store:

```
<store>/
  campaigns/<campaign>/
    campaign.toml          goal, build, baseline, space, ladder, budget, approval
    index.tsv              one row per run, append-only
    runs/<run_id>/         bundle per run
    studies/<study>.toml   one record per question asked
```

Layout of the data directory:

```
<data>/
  seeds/<hermes_sha>/<test>/<time>ms/    restart files cut from a parent run
  dumps/<run_id>/                        kept while the retention rule allows
  cases/                                 run area, emptied after extraction
```

Nothing in the tool or the store contains an absolute path. One environment
variable names the store, one names the data directory, and a config file holds
the rest.

The seed library is keyed by parent case, `seeds/<hermes_sha>/<parent case>/<time>ms/`,
so two parents built from one commit do not share seed folders.

## 4. Tests: parents, windows and rungs

### Naming

`test4_1.0-2.0ms` means test4, restarted from the parent state at 1.0 ms of
plasma time, run to 2.0 ms. Rules:

- Times always carry one decimal, and sit on a 0.1 ms grid.
- The parent run is `test4_0.0-100.0ms`.
- The names `scratch`, `stiff` and `steady` are retired for this project. The
  existing short tests stay unchanged in `hermes-perftest`, because other
  people use them; this project cuts its own windows from its own parents.
- A run directory is `<window>-<YYYY-MM-DD>[-<desc>]`, e.g.
  `test2_0.0-100.0ms-2026-09-19-neutlag-va`.

### Parent runs

A parent runs from initial conditions to 100 ms: `nout = 100` at 1 ms, which
is `timestep = 95788` normalised. Parents are the exception to the 50-output
rule, so every whole millisecond has a saved state for a window to start from.

Every template starts the neutrals non-zero, at 1e16 m^-3 and 3 eV. With
`scale_vars`, a value of exactly zero takes the scale floor and dominates the
residual norm. The momenta still start at zero; only a code fix removes that
part.

### Build, versions and starting recipe

The first campaigns run on Hermes-3 `neutlim-lagging` at `ef2ef9dd`, built with
the VanAlbada limiter at CHECK=2, with `limiter_gradient_floor = 10` and
`lag_limiter = gradient` in the neutral species. They start from the recipe
SNES-MUMPS-3: SNES-MUMPS-2 with `target_its = 7` and `mat_mumps_icntl_24 = 1`.

The build is not fixed for the whole project (R18). A version bump opens an
epoch, needs new parent runs from scratch, since old seeds are not reused, and
a quick rebaseline. It must not invalidate a campaign's results.

### Generation, not storage

The repository holds the parent test definitions and a window generator. It
does not hold a directory per window, because each window needs its own restart
files and there will be many. The generator writes a window into the campaign's
case area from the seed library.

The generator is `make_window.py` in `hermes-perftest` (branch
`window-scheme`). It cuts a missing seed from the parent's dumps, refuses a
seed off the requested time, and copies the parent's input so the physics
settings match the state the seed came from.

Every window requests 50 output steps, whatever its length. Dump size scales
with the number of outputs, not the duration, so this fixes the cost per run at
roughly 100 MB for test4.

### The ladder

Starting values, to be retuned once rung 0 has been timed:

| Rung | Windows | Noise bound |
| --- | --- | --- |
| 0 | `_0.0-0.2ms`, `_5.0-5.5ms`, `_30.0-30.5ms` | 15% |
| 1 | `_0.0-0.8ms`, `_5.0-7.0ms`, `_30.0-32.0ms` | 10% |
| 2 | `_0.0-100.0ms` | 5% |

Rung 1 is rung 0 quadrupled. The three positions test the transient from a flat
start, the approach to steady state, and near-steady state.

The noise bound is the size a difference must exceed to count. It is declared,
not measured: this project does not spend runs measuring scatter.

### From windows to a full-run estimate

A recipe may be slow early in a run and fast late, so no single window predicts
the full run, and a window's ranking of recipes need not match the full run's.
Windows are therefore not trusted by rank correlation. Instead (R39):

- Windows at several points along the run each measure a speed: plasma time
  per wall-clock time.
- The full-run time is estimated by adding up the time each stretch of the run
  would take at its window's speed.
- A real full run checks the estimate from time to time.
- Promote generously. The cheap rungs cannot see a slow divergence, which is
  the failure mode this project most fears, so the promoted set is wider than a
  pure ranking would give.

Cutting a simulation into restart windows as a tuning fidelity appears to be
unpublished.

### Restart transients

A window starts from the input file's timestep, with no Jacobian history, so
its first steps cost more than the parent paid there. This is not removed from
the measurement. Every configuration pays it, and recovering quickly from a
restart is a real solver virtue.

## 5. Trials, runs and identity

A run's identity is a hash of its resolved configuration: the normalised
recipe with its overrides, the test, the Hermes-3 commit, the build flags, the
core count and the pinning. Two runs of the same configuration share the hash
and are distinguished by an index suffix. This makes an accidental duplicate
and a deliberate repeat different things, mechanically.

The row lifecycle is unchanged from the current store: a row carries declared
intent before the run, and the extractor fills the measured fields afterwards.
Nothing is typed twice. `varied` states what the run is deliberately testing,
`diffs` states every deviation from the named recipe, and a setting in `diffs`
but not in `varied` is flagged, because it means something changed that nobody
intended.

## 6. Cost and correctness

### Cost

Wall clock is the primary metric. Counts are recorded alongside it: RHS
evaluations, nonlinear and linear iterations, Jacobian builds, and the time
shares from the PETSc profile.

The reason wall clock leads: a run's time is roughly

```
wall ≈ N_rhs × t_rhs + N_jac × t_jac + N_ksp × t_ksp + overheads
```

Few knobs change `t_rhs`, but several change the mix. Jacobian lagging cuts
`N_jac` and raises `N_rhs`; matrix-free trades a cheap Jacobian for many more
linear iterations. Ranking on RHS count alone therefore flatters recipes that
do heavy linear algebra per evaluation.

A modelled cost — the counts multiplied by unit times measured once per machine
— is the machine-independent ranking, and is the way to compare machines. It
is not built yet. The rule is: rank on wall clock, record the
counts, and flag any comparison where the two orderings disagree. A flagged
disagreement is a finding, and the trigger to build the modelled cost.

### Correctness

A setting can be fast by taking sloppy steps and reaching the wrong plasma.
Timing alone never reveals that. Because the project optimises towards a steady
state, two runs may take different paths and both be right, so the check has two
levels:

- Window check, on every rung: a sanity band. Finite, physical, and near the
  parent at the same time, on four quantities — separatrix density and
  temperature at the outboard midplane, and maximum density and temperature at
  the target. Failing it disqualifies the run. Passing it proves little.
- Endpoint check, on the full run only: does it reach the same steady state as
  the reference? This is the verdict that counts.

Correctness is a pass/fail flag beside the cost, never a term inside it.

For test 2 the parent run is the reference steady state, and a full run passes
if its endpoint lies within 5% of the parent's endpoint.

Still unset, and to live in `campaign.toml`: the tolerances for the other tests,
and which of the four midplanes of a connected double null defines the
separatrix. Until the second is fixed, only the target maxima are computed.

### Residual space

SNES reports a residual, and the store already records its final value, its
drop over the run and the drop per RHS evaluation. For steady-state work the
honest objective is the work needed to reach a residual level, not the work
needed to reach a fixed plasma time. The current ladder is built on plasma-time
windows and does not express that.

This matters for pseudo-transient continuation, which is on the list to test
later: such methods are judged in residual space, not in plasma time. The
design therefore records the residual history per output step for every run,
and states plainly that the objective is a campaign-level choice rather than a
property of the system. Reconciling a residual-target objective with the
window ladder is an open question.

### Repeats

No repeats at rungs 0 and 1; the declared noise bounds apply there. Three runs
of a configuration before it is promoted to the full run, and the median is
used. This is the minimum the review would accept and the maximum this project
will pay.

### Cutoff

A run is killed at two to three times the current best time for that window,
and recorded as a timeout. A timeout means "at least this slow", which is
usable evidence, not a missing result.

## 7. Outcome taxonomy

Every outcome must be decidable by a script from the log and the dump.

| State | Definition |
| --- | --- |
| completed | Reached the window's end time, solver reported success, outputs written |
| invalid | Completed, but failed the correctness check |
| diverged | Solver gave up: non-finite values, or the consecutive-failure cap reached |
| timeout | Still progressing, but past the cutoff |
| crashed | Died for reasons outside the solver: MPI, memory, machine |
| cancelled | Stopped deliberately |

Every row also records the plasma time reached. Failed runs stay as rows with
their timings blank; an unrecorded failure is a lie about the search space.
A crash says nothing about the recipe and never counts as a bad score.

## 8. The runner

One program, one cycle:

1. Read `campaign.toml` and the index. Decide what is left to do.
2. Check the approval record and the remaining budget. Stop if either fails.
3. Check free disk against the floor. Stop if below it.
4. Generate the case: copy the template, apply the recipe and the overrides,
   seed it from the seed library, set the outputs to 50.
5. Open the index row with the declared intent.
6. Launch into a free slot, pinned to its cores.
7. Watch for a stall or a cutoff breach; kill and classify if either fires.
8. Extract the bundle, fill the row, validate.
9. Apply the retention rule to the dumps.
10. Repeat.

Properties that matter:

- It orchestrates and never reimplements. Every step is an existing tool
  invoked as a subprocess, so each stays runnable by hand with the same
  command. This is the rule `run_ladder.py` already follows.
- The index is the only state. The driver decides what is left by reading it,
  so it is idempotent and resumable. A private progress file would be a second
  record able to disagree with the first.
- Machine parameters come from config: total cores, cores per run, the slot
  map. Today that is the user's 32-core workstation with three 10-core slots. The house rule on this workstation — runs launch through screen
  sessions and run plans — is local procedure and stays out of the tool.

### Budget, approval and disk

- The budget is in slot-hours, declared per campaign. The runner stops when it
  is spent.
- Approval is a record inside `campaign.toml`: who approved it, when, and the
  budget approved. The runner refuses to start without it. One `engage` from
  the user on a campaign plan — search space, ladder, budget — authorises every
  launch the runner makes inside it, and nothing outside it. This exception to
  per-launch approval is written into the `run-case` skill.
- Dumps are kept for now, at 50 outputs each. `campaign.toml` carries a disk
  budget and a retention rule: keep the dumps of promoted runs and of the most
  recent N, prune the rest when over budget. The runner refuses to launch below
  the disk floor. At roughly 100 MB per test4 run, a thousand runs is about
  100 GB, so this rule is what stops the disk filling at run 700.

## 9. The optimiser

### Interface

Two operations. Suggest: read a compact view of the campaign, write a study
file listing trials. Report: the runner fills the index; the optimiser reads it
back. Nothing else crosses the boundary.

### What the first version is

A study file listing explicit variants, written by the user or by an LLM. No
sampler. The interface is shaped so that a sampler drops in later without
touching the runner.

### What the review said about LLM optimisers

Evidence to respect when the sampler question is opened:

- The measured gains from LLM optimisers come from warm-starting and from
  proposing candidates when data are sparse, not from prediction. As a
  predictor an LLM loses to standard methods.
- A budget-matched study in June 2026 found the apparent advantage was mostly a
  sensible default configuration: seeded random search tied at five evaluations
  and won by twelve.
- A March 2026 benchmark of LLM agents tuning physics-solver parameters across
  eleven simulators reached 66 to 81 per cent success with iteration, but used
  1.5 to 2.7 times more compute than plain scanning.
- LLM optimisers stagnate rather than converge, so a fallback is needed.

The consequences, for whenever a sampler is adopted: run the hand-tuned recipe
and a seeded random search as controls; show the model at most about thirty
trials in a fixed table, with a knob dictionary and a strict output schema the
runner validates before launch; fall back to the sampler if two consecutive
batches drift or repeat.

### The search space file

Brute force over this space is not the plan. An intelligent mapping of it is,
and that mapping needs an explicit description to be built on. The tool
therefore carries a declarative file, one entry per knob:

```toml
[knobs."solver:lag_jacobian"]
type     = "integer"
range    = [1, 20]
applies  = "snes"
depends  = { "solver:matrix_free_operator" = false }
cost     = "fewer Jacobian builds, more nonlinear iterations"
```

Types are switch, choice, integer and continuous. `depends` records the
settings a knob is only meaningful under — the factorisation method means
nothing unless the preconditioner is a direct solve. The file is written from
what is known now and marked incomplete.

## 10. The store

- The index stays a fixed-column TSV, one row per run. At thousands of rows
  this is two to three orders of magnitude below where a columnar format would
  pay.
- It is append-only, with a git merge rule set so two parallel appends never
  conflict, and a validator that checks for duplicate run identities and column
  drift.
- A schema file describes the columns once — name, type, units, constraints —
  for the validator and for any reader.
- No database. A query script reads the TSV and prints a filtered, grouped,
  ranked projection of about ten columns.
- Neither a person nor a model ever reads the raw fifty columns or aggregates
  the table by eye. Measured work shows single-value lookups are near-perfect
  while counting and filtering over a table is where model reading fails, and
  long inputs degrade recall on their own.
- Each bundle carries a manifest for regeneration: commit, build flags, input
  checksums, launch command, extractor version. Deleting raw output is accepted
  practice only when what is needed to regenerate it is kept.

## 11. Knowledge

Two rules. One fact lives in exactly one place, enforced by a validator rather
than by a sentence. Machine-written and hand-written content never share a
file.

| Tier | Holds | Where | Written by |
| --- | --- | --- | --- |
| 1 | One row per run | `index.tsv` | machine |
| 2 | Evidence per run | `runs/<id>/` | machine |
| 3 | One record per question | `studies/<name>.toml` | agent, user reviews |
| 4 | The campaign's answer | generated from the index | machine |
| 5 | Rules that outlive the campaign | tool repository | mixed |

A study record carries: the question, the rung, the windows, the variants, the
result with its numbers, the verdict, the confidence, the run identities it
rests on, a date, a status, what it supersedes, its scope, and the question it
opens. One free-text field holds the user's interpretation. Nothing else in the
file is prose.

Scope is not decoration: a benchmark measured overgeneralised memories at
17 per cent, and a finding from one test must not silently become a rule for
all tests.

Freshness is decided by comparing dates, never by a model's judgement.

The durable layer is four files and nothing else: `requirements.md`,
`design.md`, the agent instructions with their procedures, and `findings.md`.
A finding graduates into a requirement, a procedure, a test or a config
default, and its entry then changes status rather than being deleted. There is
no hard cap on how many findings exist; the cap is on how many are loaded.

One caution, measured: model-written instruction files reduced agent success in
a February 2026 study over 438 tasks, while human-written ones improved it, and
both raised cost by over twenty per cent. So the durable files stay minimal,
the user reviews every diff, and machine-written records are never pasted into
the always-loaded context.

## 12. Portability

The system must run under Google agents on a fresh VM, so:

- The runner is a program, not a sequence of agent judgements.
- No absolute path appears in the tool, the store or a config.
- `sdtools` gains packaging so it installs anywhere, and its hardcoded default
  paths move into config.
- Python dependencies are pinned in the tool repository.
- The environment, the compilation and the VM are the user's to provide.
- Instruction files convert to the cross-agent format on the day, not before.
- The test drive runs the loop from a clean checkout in a fresh Python
  environment, with no path under the user's home directory in any config.

## 13. Open questions

Carried into the hackathon rather than answered here:

1. How to map the search space intelligently, given a mix of switches, choices
   and continuous knobs with dependencies between them.
2. How a residual-target objective fits a ladder built on plasma-time windows,
   which pseudo-transient methods will need.
3. Which midplane defines the separatrix on a connected double null, and what
   the correctness tolerances are.
4. Whether the summed window estimate matches a real full run.
5. Whether dumps can stay at 50 outputs per run, or the retention rule has to
   tighten.
6. How the quick rebaseline after a version bump is done in practice.
