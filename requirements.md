# Hermes-3 solver performance optimisation — design requirements

Living document, started 2026-07-27 (the user + Claude). This is the requirements
layer: what the framework must achieve and why. Design decisions (the how)
come later, in design docs and beads issues, once these requirements have been
thoroughly explored. Requirements carry IDs (R1..) so beads issues and design
docs can reference them. IDs are stable and never reused: a new requirement
takes the next free number wherever it sits in the document, so the numbering
is not reading order. Claude's proposed additions are separated at the bottom
and are not requirements until the user accepts them.

Last reviewed: 2026-09-19. Review at every epoch boundary and at least monthly
(R28).

## Read this first

The rules that change behaviour every session. Violating one of these is
always wrong; everything else in this document is context for them.

- R11 outranks all others. If a result cannot be presented digestibly, it is
  not finished.
- R10. Pipeline before work. No experiment runs until the recording pipeline
  is built and working. Deciding the capture set is not enough, and results
  are never transcribed by hand.
- R3. Isolate one part at a time — preconditioner, linear solve, nonlinear
  solve, timestepper. Experiments are designed and recorded in those terms.
- R17. Record everything a timing depends on, or the timing cannot be compared
  later.
- R32. No result is an improvement until it clears its rung's declared noise
  bound.
- R22. Extract diagnostics and validate them before deleting any dump.
- R33. The user approves each campaign as a whole before it launches anything.
- R26. SNES is what we optimise; CVODE is the reference to beat.

Entries tagged `[working plan]` are current thinking, expected to change, and
can be revised by proposing it. Untagged entries are constraints.

## Headline objective

- R1. Build a framework that optimises Hermes-3 performance by exploring the
  solver settings parameter space — mostly finding the optimum set of PETSc
  solver parameters (the `[solver]` and `[petsc]` sections of BOUT.inp) — by
  deploying simulations and analysing the results. (PETSc is the numerical
  library BOUT++ uses for its implicit solvers; a recipe is a named block of
  `[solver]` + `[petsc]` settings, e.g. SNES-MUMPS-1.)

- R38. Objective, set by the user 2026-09-19. Make the full simulation, from
  initial conditions to steady state, as fast as possible. There is no finish
  line and no target time. Numerics work in other campaigns contributes too
  (R4).

- R25. CLOSED 2026-09-19, replaced by R38: the user wants no specific win
  condition. Kept for its history. End condition. The project is finished when test4scratch and
  test5scratch run all the way to convergence, robustly and quickly, in under
  an hour each. A convergence run is two to three times a scratch run, so the
  gap is large: as measured on 2026-07-29 it was roughly 70-100x on test 4 and
  4-6x on test 5 from its best recipe. Recompute from `run_records.csv` rather
  than trusting those figures. Solver settings alone are unlikely to deliver
  all of it, so this end condition depends partly on the numerics and model
  work running in parallel
  (R4) — it is the project's success criterion, not a claim about what solver
  tuning can achieve on its own.

## Strategy

- R2. One recipe first. The optimum settings may vary by condition or test
  case, but the first working assumption is that there is one best solver
  recipe for everything, and the project's first goal is to find it. Only
  once performance is very robust does per-condition fine-tuning begin.

- R3. Subsystem isolation as method. It is not known whether the main issues
  sit in the preconditioner, the timestepper, the nonlinear solve or the
  linear solve. The framework must support isolating these parts. Reference
  technique: SNES-MUMPS-1 has an expensive but very good preconditioner
  (linear-to-nonlinear iteration ratio almost always 1), which may not be the
  fastest recipe but removes the linear solve as a variable, exposing
  nonlinear/timestepper issues for optimisation in isolation. Experiments
  must be designed, and recorded, in these isolate-one-part terms.

- R4. Solver-vs-numerics awareness. It is unknown how much of the performance
  problem originates outside the solver (plasma model, discretisation, etc.);
  that side is being optimised in parallel in other campaigns. Some failures
  (e.g. SNES convergence failures) may be caused by numerics issues rather
  than solver settings. The investigation must stay open to this and be
  designed so it also helps diagnose solver vs numerics origins.

- R5. Multi-test awareness. There are several types of tests (test families,
  scratch/stiff/steady variants, SNES- and CVODE-based). The system must know
  which tests each optimisation step was evaluated on — how broad the
  evidence is — and support strategies such as optimising on one test first
  then trying another, or choosing a pair of tests to run at the same time.

- R15. Precise objective metric. Define exactly what performance means before
  the first optimisation wave. Performance has a cost part and a correctness
  part, and a run only counts as a result if it passes the correctness part.

  Cost is measured two ways, both recorded for every run:
  - Wall clock time to complete the test. This is what ultimately matters, but
    it varies with machine, core count, node contention and CHECK level, so it
    only compares across runs when those are pinned (R17).
  - Total RHS evaluations — the number of times Hermes-3 evaluates the
    right-hand side (the time derivatives of the evolving fields). This is
    machine-independent and reproducible, and moves only when the solver
    settings or Hermes-3 itself change.
  Which of the two ranks recipes was settled by R29: wall clock.

  The correctness paragraph below is refined by R30.

  Correctness is judged on four physics quantities, taken at the end of the
  test and compared against the reference run: outboard-midplane separatrix
  electron density and temperature, and maximum target electron density and
  temperature — cmonitor's top row run without `--neutrals`. They are allowed
  to move within a tolerance that tightens as the test gets longer: loosest on
  short tests, tighter on scratch tests, very tight on a test run to
  convergence. The tolerance values and the choice of
  reference are still to be set (so-joa).

- R16. We need to distinguish between tests. The simulations are much stiffer
  at the beginning than at the end. Short tests take a short plasma time
  from part of the whole solution and isolate it as a test that takes a few
  mins. They can tell us performance but not necessarily that we haven't
  introduced a numerical issue that affects results. The gold answer is a test
  from scratch, but that is currently very expensive (10s of hours for tests 4
  and 5). It is not obvious which tests to use. Right now even the scratch
  tests aren't long enough to reach steady state.

  `[working plan]` A sequence of tests of increasing cost, run further along
  only as performance improves rather than run in full every time: a short test
  first, then a second short test that is hard in a different way, then a
  scratch test, then a test run to convergence. A convergence test is just a
  scratch test run longer — roughly double. Only the two short tests need
  choosing now; the physics changes they reveal will themselves be informative.
  The final steady-state check matters less and serves as a last verification
  rather than a routine gate. Which tests fill each position is decided per
  optimisation campaign, not once for the project — it depends on what is being
  optimised at the time — and is expected to be re-learned as the project goes
  (so-eqk).

  The working plan above is replaced by R31 (2026-09-19). The problem statement
  stands.

- R29. Wall clock is the primary cost metric. Counts — RHS evaluations,
  nonlinear and linear iterations, Jacobian builds — are recorded for every run
  and used as diagnostics. Any comparison where wall clock and counts disagree
  on the ordering is flagged. That flag triggers building a modelled cost from
  counts and per-machine unit times. Accepted 2026-09-19.

- R30. Correctness has two levels, because the project optimises towards a
  steady state and two runs may take different paths and both be right. Cheap
  rungs check a sanity band against the parent run. Only the full run checks
  the endpoint against the reference steady state. Correctness is a pass/fail
  flag beside the cost, never a term inside it. Accepted 2026-09-19.

  Set by the user 2026-09-19 for test 2: the parent run counts as the steady
  state. A full run reaches steady state if its endpoint lies within 5% of the
  parent's endpoint. The ruling was made on a zero-neutral parent, since
  deleted; it carries to the rerun with non-zero neutrals,
  test2_0.0-100.0ms-20260919-201426, whose endpoint matches the deleted run's
  within 0.1% on all four physics quantities.

- R31. Tests are windows of a parent run: restarts from the parent's state at
  one plasma time, run to a later one. They are named by their plasma time on a
  0.1 ms grid, e.g. `test4_1.0-2.0ms`. The names scratch, stiff and steady are
  retired. Rungs — sets of windows of similar cost — replace the fixed sequence
  of tests in R16. Accepted 2026-09-19.

- R39. Windows estimate the full run by summing, not by ranking. A recipe may
  be slow early in a run and fast late, so no single window predicts the full
  run. Windows placed at several points along the run each measure a speed
  (plasma time per wall-clock time). The full-run time is estimated by adding
  up the time each stretch of the run would take at its window's speed. A real
  full run checks the estimate from time to time. Accepted 2026-09-19, in place
  of trusting a ladder by its rank correlation with the full run.

- R20. Know the noise floor. Repeated identical runs do not take identical
  wall-clock time. Until that scatter is measured we cannot tell a real
  improvement from a quiet machine, and with hundreds of comparisons ahead
  that is the cheapest way to waste months. Measure the run-to-run spread on
  each test at least once per epoch, and call no result an improvement unless
  it clears that spread. Timed runs are made at a fixed machine loading — the
  standard three concurrent runs of R21 — and placed on the machine the same
  way every time, because sharing a workstation changes both the timing and
  its spread. Whether the spread itself varies with loading is worth
  establishing once; after that it may be treated as constant per loading.

  Replaced by R32 on 2026-09-19: noise is declared, not measured.

- R32. Noise is not measured and no runs are spent on scatter. Each rung
  carries a declared bound a difference must exceed to count: 15, 10 and 5 per
  cent. The one exception is promotion to the full run, which takes the median
  of three runs. Accepted 2026-09-19.

- R26. Solver scope. SNES is the solver being optimised. CVODE stays in scope
  as the reference to beat — it is currently the best performer on test 5,
  which SNES has never been made to work on at all. `imexbdf2`, `arkode` and
  `ida` are out of scope entirely; they emit almost no solver diagnostics
  anyway. The TS-based `petsc` solver belongs to phase 2 (R27), and enters once
  someone has tidied it and checked it for bugs.

- R27. Three phases, each expected to take several months.
  1. Steady state. Optimise the existing tests, where the goal is reaching a
     converged steady solution and time accuracy along the way does not matter.
  2. Time-dependent. Use PETSc TS to get good performance while keeping time
     accuracy — a different objective, needing a different solver and different
     success criteria.
  3. Many species. Larger systems, which strain the preconditioner in ways the
     current tests do not exercise.
  Everything currently written in this document is phase 1 unless it says
  otherwise. Decisions taken now should not silently assume time accuracy is
  worthless, because in phase 2 it becomes the point.

## Knowledge and data

- R6. Scale of recording. There will be thousands of setting variations. The
  record of which settings did what must be so efficient that the outcomes of
  several hundred simulations can be loaded into an agent's context easily,
  every time runs are planned or analysed. This is a hard requirement on the
  compactness and structure of the results store.

- R7. Hermes-3 is a moving target. Hermes-3 is under constant development and
  many updates will land during this project. The system must capture
  performance evolution between Hermes-3 versions without rerunning hundreds
  of simulations each time.

- R8. Disk-independent capture. There will be many cases but disk space is
  limited. The inputs and results of a simulation must be captured separately
  from the dump files, so that the full dumps are not needed to keep the
  record. The whole case directory goes, not just the dumps: once the record is
  extracted and validated (R22), nothing in the run directory is needed again.

  No dumps are kept by default — not even for baselines — unless the user asks for
  a specific case. The cost of that is real but bounded: a derived metric
  invented later cannot be computed on a completed run. The insurance is R18,
  which re-runs the baseline set at every epoch bump anyway, so a new metric
  can be prototyped on the next baseline rather than needing an archive.

  Restart files hold no results, so ordinary runs keep none. They are seeds:
  keep them only for the baseline set, whose scratch runs define the states
  that the stiff and steady tests restart from at that epoch.

  Softened by R37 on 2026-09-19: dumps are kept for now.

- R37. Dumps are kept for now, with every run requesting 50 output steps.
  Each campaign declares a disk budget and a retention rule, and the runner
  refuses to launch below a disk floor. Accepted 2026-09-19.

- R9. Comprehensive diagnostics. What is currently captured per run is not
  nearly enough. Required: a super comprehensive system capturing every
  relevant PETSc diagnostic (e.g. log_view, PETSc's end-of-run profiling
  report), every time-history type output, the shares of the residual norm
  (per-equation contributions), the residual itself, and possibly time
  derivatives. cmonitor's physics monitors are reusable; the rest of cmonitor
  is not fit for this. Adding more PETSc diagnostics into BOUT++ is in scope
  if needed.

- R10. Pipeline before work. Deciding the capture set and the postprocessing
  package is a separate investigation that comes first, and it must be
  in-depth. Deciding is not enough: the recording pipeline must be built and
  working before any experiment is run. A finished run must turn into a
  validated record automatically — no hand-transcribed results, no "we will
  write the extractor afterwards". Until that exists, runs are for testing the
  pipeline itself and nothing else.

- R17. Reproducibility floor. Every recorded run must be regenerable from its
  record alone: exact inputs, build/commit, grid, seed case. Required for
  re-baselining under R7 and for trusting old rows after dumps are deleted
  (R8). The record must also pin everything R15's wall-clock number depends
  on, or that number cannot be compared later: core count, machine and whether
  it was shared, CHECK level, and the BOUT++ and PETSc versions alongside the
  Hermes-3 commit.

- R18. Baseline discipline. The Hermes-3 version the project builds on is
  changed deliberately, never drifted into. A version bump happens only when
  the project needs a feature that has landed, or when the performance of a
  particular feature is itself what we want to measure. Updates change both the
  performance and the results of the tests, so every bump costs a rebaseline —
  which is exactly why bumps are chosen rather than taken automatically.

  Each bump opens a new epoch: a re-run of the fixed baseline set at the new
  version. `[working plan]` The baseline set is one run of each Test 2, Test 4
  and Test 5
  variant — the project's primary tests at present, described in
  `hermes-perftest/readme.md`. Every result carries the epoch it was measured
  in. Results compare directly within an epoch, and across epochs only through
  the baselines. This is the cheap mechanism that satisfies R7.

  The bump itself must be a defined, repeatable procedure whose execution is
  recorded — date, old and new commit, the reason for bumping, and the baseline
  numbers either side. Without that record the project loses track of which
  results belong to which version, which is precisely the getting-lost that R11
  forbids.

  Kept 2026-09-19, when the user rejected fixing one build for the whole
  project. The user's ruling: the project stays aware of version changes and
  accounts for them, and a bump must not invalidate everything in a campaign.
  A quick rebaseline at each bump is the expected mechanism.

  Ruled 2026-09-19: a new version needs a new parent run from scratch. Seeds
  cut under the old version are not reused under the new one.

- R19. Failure taxonomy. Failed runs are first-class outcomes, not missing
  data: they are classified, because failure fingerprints carry exactly the
  solver-vs-numerics signal R4 asks for. (Example from this week: scale_vars
  on test4 fails instantly with loose tolerances but hits a wall at t≈3.4e5
  with tight ones — that shape is diagnostic.) The classes are:
  - diverged at start — never gets going;
  - SNES failure — the nonlinear solve stops converging mid-run;
  - linear-solve failure — the Krylov solve (KSP) diverges, reported by PETSc
    as a distinct reason and worth separating from a SNES failure where the
    logs allow it;
  - crawl — still running but so slow it has to be aborted; needs a written
    abort criterion so the call is mechanical, not a judgement each time
    (so-0zl);
  - completed but wrong — finished, and possibly fast, but failed R15's
    correctness check. The most dangerous class, because nothing about the run
    announces it.

- R21. Compute budget and concurrency. The machine is a 32-core workstation.
  A test takes 10 cores, so three run at once with two cores left over for
  everything else. Orders of magnitude for planning: short tests under an hour,
  scratch tests tens of hours, convergence tests two to three times a scratch
  test. For actual current durations read `run_records.csv` — do not quote
  figures from this document. Anything that plans a wave of runs must fit
  inside these limits, and must respect that concurrency is itself a variable
  in the timings (R20).

- R22. Procedure lives in a skill, not in habit. The repeatable mechanics of
  this project — applying a recipe, launching, gating, extracting the record,
  validating it, deleting dumps — belong in a written skill that is followed,
  not re-improvised each session. Two rules it must carry. First, dumps are
  deleted only after their diagnostics have been extracted and the extraction
  validated; never before, and never for a run whose record failed validation.
  Deletion is irreversible and R17 would otherwise force a rerun, which for a
  scratch test costs a day. Second, runs may be prepared by an agent but are
  presented for approval before launch — this inherits the gate the `run-case` skill
  already defines rather than restating it. For campaigns, R33 replaces this
  second rule with approval of the whole campaign.

- R33. Each campaign keeps its own index inside the store, and the user
  approves each campaign as a whole: search space, ladder and budget in
  slot-hours. The approval is recorded in the campaign's config, and the runner
  refuses to start without it. This is a deliberate exception to per-launch
  approval, granted by the user 2026-09-19 for this project's campaigns only:
  approving a campaign authorises every launch inside it and nothing outside it.

- R34. The system is two layers: a runner that is a plain program with no
  judgement in it, and an optimiser that decides what to try next. They meet at
  one interface: suggest trials, report results. Accepted 2026-09-19.

- R35. Everything must run under another vendor's agents on a fresh VM. No
  absolute paths, pinned dependencies, packaging on `sdtools`, and instructions
  written for any agent rather than one product. Accepted 2026-09-19.

- R23. Trust the tooling. Hundreds of rows will be produced by extraction code
  rather than read by a human, so a bug in that code silently corrupts both the
  record and every conclusion drawn from it. The extraction and metric code
  carries its own tests, and any stored row must be re-derivable from the raw
  artefacts to prove it still agrees.

## Human factors

- R11. The user is co-investigator. The system must allow the simulation results
  and setup to be very effectively communicated so that the user can follow closely
  without a huge mental load. So we need a very effective and efficient system to 
  record and follow progress and decide on next steps without getting lost in 
  the weeds of settings trees, hermes versions and so on. This is top priority.

- R24. Findings log, terse and agent-facing. Beads (R13) tracks what needs
  doing; the findings log records what was learned, including dead ends, which
  are expensive to rediscover. It exists primarily for Claude to load, so it is
  written dense: a few lines per finding, evidence pointer, no exposition. Keep
  it small enough to load whole. It is a staging area, not an archive: findings
  graduate into requirements, the run skill, the extraction tests or a ledger
  column, and are deleted from the log once they land. Capped at 20 entries and
  pruned at every epoch boundary. The user keeps their own separate record; this one
  is not written for them and is not co-authored.

  The cap and the deletion rule are replaced by R36 on 2026-09-19.

- R36. Knowledge is stored in five tiers with one fact in one place, and
  machine-written content never shares a file with hand-written content. A
  record carries a date, a status, what it supersedes, its scope and the runs
  it rests on. The cap is on what is loaded, not on what exists, and a finding
  that graduates changes status rather than being deleted. Accepted 2026-09-19.

- R12. PETSc apprenticeship. The user needs to become a PETSc, numerics and performance
  expert during this
  project, with Claude's help. Analyses and reports must teach as they go:
  terms defined on first use, reasoning shown, a glossary that grows.

## Process

- R13. Beads tracking, used fully. This project is complex and is tracked with
  beads (bd) from day one, using the tool to its full potential: dependencies,
  epics, structured workflows, stored memory, health checks. Do not water the
  workflow down for the sake of simplicity — the user is new to beads but intends
  to learn it properly, so teach it as the project goes and document the
  conventions in this directory. The tracker absorbs complexity; it must not
  pass it on to the human (R11).

- R14. Requirements before details. Implementation details (foundation
  package, gating cadence, first target test, search autonomy, naming) are
  deliberately deferred until the requirements above have been thoroughly
  explored. Two provisional, non-binding leanings recorded so far: extend the
  existing caseplan package rather than start fresh, and gate deployments per
  wave. Both are revisitable.

- R28. Review these requirements periodically. This document accumulates, and
  over three phases (R27) that means rules from a finished phase sitting there
  still looking authoritative. Review it at every epoch boundary (R18) and at
  least monthly, and update the "Last reviewed" date at the top. A review asks:
  which entries have gone stale, which quoted numbers are now wrong, which
  `[working plan]` entries have hardened into constraints or been abandoned,
  and — at a phase boundary — which entries were phase-specific and should be
  marked closed rather than left implying they still bind. Closed entries keep
  their IDs and are never renumbered.

## Claude's proposed additions (for review — not requirements yet)

Round 1 (C1-C4 plus the user's added candidate) became R15-R19 and round 2
(C1-C7, from a sweep for unmentioned subjects) became R20-R25, both accepted on
2026-07-29. Round 2's capture-before-delete and launch-gating candidates were
merged into one requirement, R22, because both are procedure that belongs in a
skill rather than separate rules. New candidates go here, lettered C1 onwards
again, and are deleted or promoted once the user rules on them.

Round 3, proposed 2026-07-30, on how many runs a scan spends on noise. Prompted
by that being argued from scratch on every scan, which is itself the problem.

- C1. Standard loading is all three slots busy. That is what the machine is for,
  and it is the condition every recorded timing is measured under; a solo run is
  a special case that needs a reason. A scan is padded to a multiple of three so
  every batch fills the machine and the loading does not change midway. Holding
  loading constant is what makes it stop being a confounder — the effort goes
  into keeping it fixed, not into correcting for it.

- C2. A test's noise is the relative spread of a metric across repeats of one
  configuration, holding fixed the test, the build (commit, limiter, conduction
  method, CHECK level), the decomposition and the loading. It is quoted per
  metric, never as one number: the runs are not deterministic, and on
  test4steady the RHS count scatters wider than the wall clock it was meant to
  stabilise (F16).

  Nothing derived is stored. The repeat runs are the record, and the figure is
  computed from the index rows that already carry every field the grouping
  needs. "Measured once" means runs are not spent re-measuring it — not that
  the number is written down somewhere to go stale.

  Scratch tests are never repeated for noise: they inherit the figure from the
  matching short test, and any result quoted from one says so.

- C3. Every scan includes exactly one repeat of its own baseline configuration.
  One run, and it is the standing check that the recorded figure still holds. If
  that pair disagrees with the recorded figure, the scan is suspect and stops
  there rather than being interpreted.

- C4. A difference smaller than the recorded noise figure is reported as no
  measurable effect. Never as a small improvement, and never with more decimal
  places to make it look resolved. Extra repeats are bought only when a marginal
  difference would actually change a decision, and then only for the one
  configuration in question — never as a blanket policy across a scan.

Round 4, proposed 2026-07-31, on the boundary of the project's own data.
Lettered C4 onwards because round 3 is still open on C1-C3.
Prompted by an agent enumerating case directories, calling the 43 without an
index row a backlog, and proposing to extract them — when they are other
people's runs, to be redone and deleted by them.

- C4. The index defines what exists. A run belongs to this project if and only
  if it has a row in the results index. No tool and no agent enumerates case
  directories to discover runs, and a directory without a row is never a
  backlog. There are ~580 runs across 20 campaigns on this machine and only the
  ones this project launched are its own.
- C5. A run with no captured console predates the launch convention and is out
  of scope: not extracted, not compared against, not counted. This is what makes
  C4 checkable rather than remembered.
- C6. RULED 2026-07-31, and done: the index holds this project's runs only. The
  user's call was to remove the 18 migrated rows outright rather than move them,
  since those runs will be redone. They remain in `run_records.csv`. The index
  now carries one state, `recorded`, and every row has a case directory and a
  bundle — an invariant the code can rely on rather than a convention to
  remember. Left here until C4 and C5 are ruled on, then all three go.

Round 5, proposed 2026-08-01, on where a finding is allowed to graduate to.
Prompted by the log standing at 22 entries against a cap of 20, with the overrun
made entirely of findings whose content is now a tracked issue and nowhere else.

- C7. Amend R24 to name beads as a graduation destination alongside
  requirements, the run skill, the extraction tests and a ledger column. R24
  lists only durable-artefact destinations, so a finding that is really a lead
  with a planned experiment has nowhere to go and stays in the log forever. That
  is what the overrun is made of. The cap stays at 20 — it is the forcing
  function, not a storage limit, and raising it removes the only pressure that
  makes anything graduate at all.

  Acted on already for the 2026-08-01 prune, on the reading that R24's
  staging-area principle already covers it and only the destination list is
  short. If the ruling goes the other way, the entries are in git.

Round 6, proposed 2026-09-18 after the hackathon design session, ruled
2026-09-19. Accepted and promoted: R29-R37 (from C10, C11, C12, C14, C15, C16,
C17, C18, C19). The user also set R38 in place of R25. Kept unchanged: R2 (each
campaign starts from one named recipe), R18 (versions), R21 (the 32-core
workstation), R26, R27. Still open:

- C8. Deferred 2026-09-19. The 30-core VM is not the machine yet; the user is
  still on the 32-core workstation, so R21 stands.
- C9. Rejected 2026-09-19; see the notes under R18.
- C13. Rejected 2026-09-19 and replaced by R39. The user's objection: the best
  settings may be slow early in a run and fast late, so a short window may
  never rank recipes the way the full run does.

Round 7, proposed 2026-09-21, after an adversarial review of the overnight plan
found three ways a night could be spent producing nothing the record would
notice.

- C1. A knob's declared dependency is enforced before a run is launched.
  `search-space.toml` declares `depends` on 65 knobs and `check_overrides`
  never reads it, so the runner will spend machine time on a setting that
  cannot apply — a `pc_factor_*` option under a preconditioner that factorises
  nothing, for instance, which the extractor then refuses to record at all.

- C2. Every attempt that occupies a slot charges the slot-hour budget, whether
  it finished, was killed or crashed. A killed run records no `wall_s` and so
  costs the budget nothing today, which means a slot can spend a whole night
  being killed while the approved budget appears untouched.

- C3. A performance result is not a result until the answer has been compared
  with the baseline's. The tooling records no verdict at all: the runner never
  reads the `[correctness]` table and the extractor hard-codes `no_reference`.
  Until that closes, a loosened tolerance is indistinguishable from a faster
  solver, and the record will call it completed either way.

Round 3's C1, on holding loading constant, is still unruled and now has its
evidence: two runs of bit-identical work differed by 1.7 per cent in wall clock
at concurrency 2.35 against 1.81, with the more loaded run slower.


## Glossary

- PETSc: numerical solver library used by BOUT++ for implicit time
  integration; configured via the `[petsc]` section.
- SNES: PETSc's nonlinear solver framework (Newton-type). Each timestep is a
  nonlinear solve; each nonlinear iteration contains a linear solve.
- KSP: PETSc's linear (Krylov subspace) solver layer, e.g. GMRES/FGMRES.
- Preconditioner (PC): a transformation that makes the linear system easier
  to solve. MUMPS is a direct LU factorisation used as an essentially exact
  preconditioner — hence linear:nonlinear ratio ~1 in SNES-MUMPS-1.
- lag_jacobian: reuse the Jacobian (and its factorisation) for N nonlinear
  iterations instead of rebuilding every time; cheaper but staler.
- Residual: the amount by which the current iterate fails to satisfy the
  system; residual norm shares = per-equation contributions to it.
- log_view: PETSc's built-in end-of-run performance/profiling report.
- RHS evaluation: one call to the function computing the right-hand side of
  the equations — the time derivatives of every evolving field. It is the unit
  of physics work the solver asks for, so counting them measures how hard the
  solver had to work, independently of how fast the machine is.
- Recipe: a named `[solver]` + `[petsc]` settings block (SNES-MUMPS-1,
  CVODE-2, ...), stored in hermes-perftest/recipes.
- Scratch test: a run started from initial conditions rather than from a saved
  solution. The honest test, but expensive — 10s of hours on tests 4 and 5.
- Short test: a run seeded from a saved state so it covers only a slice of
  plasma time and finishes in minutes. Cheap, and fine for timing, but cannot
  show whether a change has damaged the eventual solution (R16).
- Stiffness: how strongly a problem resists large timesteps. These simulations
  are much stiffer early on than late, which is why a short test sampled late
  is easier than a scratch run.
- Steady state: the condition where the solution stops changing in time.
  Current scratch tests do not run long enough to reach it (R16).
- CHECK level: BOUT++ compile-time flag setting how many internal consistency
  checks run. Higher CHECK is slower, so timings only compare at equal CHECK.
- Epoch: a stretch of the project sitting on one Hermes-3 version, opened by a
  deliberate version bump and its baseline re-run. Results compare freely
  within an epoch and only through baselines across epochs (R18).

## Immediate next steps

1. Finish the requirements sweep: gaps not yet written down at all, and the
   open questions R15/R16 leave behind (what counts as "physics results stay
   reasonable"; which tests the project evaluates on).
2. Diagnostics deep-dive (R9, R10) — scoped as its own beads issue; runs
   before any optimisation wave.
3. Results store design against R6/R7/R8.
4. Beads conventions note for this project (R13).
