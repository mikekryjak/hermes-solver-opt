# hermes-solver-opt

A framework to optimise Hermes-3 performance by exploring the PETSc solver
parameter space.

This repository is the whole machine: the instructions, the design, the
requirements, the runner, the extractor and the search space. Clone it with
`--recursive` and nothing else is needed to set up, launch, extract and record
a performance test.

```
git clone --recursive https://github.com/mikekryjak/hermes-solver-opt
```

## The three repositories

The project is split by lifetime, so that the parts which change fastest never
force a change in the parts which do not.

- `hermes-solver-opt` (this repository, public) — everything durable: rules,
  design, tools. Read `requirements.md` first; it is the source of truth.
- `hermes-perftest` (public, pinned here as a submodule) — the test templates,
  the grid files, the solver recipes and the window generator. Other people use
  these tests, so this project never modifies them.
- `sdtools` (public, pinned here as a submodule) — general Hermes-3 tooling
  shared with other work: log parsing, the launcher, the report machinery.
  Nothing in it knows about this project.

The record of what was run lives outside all three, in a private store: one
`index.tsv` with a row per run, a bundle of extracted evidence per run, and the
analysis that reads them.

## Layout

```
perftest/          the extraction layer: extract, index, store, recipe, verify
cli/               command-line entry points
design.md          how the system is built and why
requirements.md    R1-R25, the rules
findings.md        learned conclusions, agent-facing
capture-set.md     what each run records
.beads/            the issue tracker
hermes-perftest/   submodule
sdtools/           submodule
```
