# Project Instructions for AI Agents

This file provides instructions and context for AI coding agents working on this project.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:7510c1e2 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->


## Committing

Commit and push without asking after each change or beads export, including at
the push step of the generated "Session Completion" block above.

## What this project is

A framework to optimise Hermes-3 performance by exploring the PETSc solver
parameter space. Read `requirements.md` first — R1-R25 are the source of truth,
and R11 (keep the user's mental load low) outranks the rest.

## What counts as this project's data

This project's runs live in `$data/cases/` and nowhere else. Launch there,
extract from there, count from there. Anything outside it is other work: the
user has ~580 runs across 20 campaigns, and the older `test2dev` / `test4dev` /
`test5dev` areas are to be redone and deleted by their owner. Never launch into
them, extract from them or compare against them.

The index defines what exists. A run belongs to this project if and only if it
has a row in `solver-opt-store/index.tsv`. NEVER enumerate case directories to
find runs, and never treat a directory without a row as a backlog.
When counting this project's runs, treat a campaign's index under
`$store/campaigns/` as outside that rule until its rows reach `index.tsv`.

A directory with no `BOUT.log.console` predates the launch convention, which is
the check that survives a run being moved.

## Where things go

The shell variables used below are set in `~/.bashrc`: `$solveropt` is this
repository, `$store` the results store, `$data` the case and seed directory.

- Rules and constraints: `requirements.md`. IDs R1.. are stable and never
  reused, so numbering is not reading order. New proposals go in the candidates
  section for the user to accept or reject; never promote your own.
- Findings shown on more than one test, or about the run system or PETSc:
  `findings.md`. Terse, agent-facing, no cap on entries, a cap on what loads.
- One test's findings: `campaigns/<campaign>/findings.md`, conclusion first.
  Load `findings.md` and the current campaign's file, never another campaign's.
  Graduate a finding into requirements / the run skill / a test / a ledger
  column, then mark it graduated with a pointer to where it landed. Delete
  nothing while the project is exploratory; the user will revisit this.
- Tasks: beads. Never TodoWrite or markdown lists.
- Run results — the index, its schema, the per-run bundles — and the analysis
  that reads them: the private `solver-opt-store` repo at `$store`.
- When committing in `$store`, leave `campaigns/<name>/` out: a campaign's
  config, index and log stay local, and only the top-level `index.tsv` goes in.
- Add no rows to `$store/run_records-preproject.csv` and compare nothing against
  it: it is the frozen record of 18 runs dropped from the index on 2026-07-31.
- Tools that capture or extract results: here, in `perftest/` and `cli/`. Put
  one in `sdtools` only when another campaign uses it too.
- Design and rationale for this project — requirements, capture set,
  diagnostics inventory: here.
- Case directories, seeds and dumps: `$data`, outside git because one run is
  about a gigabyte.

## Tracker conventions

- Every issue hangs off an epic: Diagnostics and record, Evaluation method,
  Process and provenance, Non-solver factors, Solver behaviour puzzles,
  perf-bisect. Wire with `bd dep add <child> <parent> -t parent-child`.
- `bd ready --exclude-type=epic` is the work queue. Keep it near 30 items. If
  it grows, add the missing dependency rather than re-shuffling priorities.
- Priority encodes sequence, not importance: P1 now, P2 next, P3 later.
- Title each issue with the requirement or finding it serves, e.g. "(R15)".
- Put the reasoning and the open question in the description; a title alone is
  not a handover.
- Close with `--reason`.
- In conversation, name the work, not the ID.

Do not edit inside the BEADS INTEGRATION markers above — that block is
generated.
