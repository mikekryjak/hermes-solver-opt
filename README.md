# hermes-solver-opt

A framework to optimise Hermes-3 performance by exploring the PETSc solver
parameter space.

This repository is the whole machine: the instructions, the design, the
requirements, the runner, the extractor and the search space. Clone it with
`--recursive` and nothing else is needed to set up, launch, extract and record
a performance test.

```
git clone --recursive https://github.com/mikekryjak/hermes-solver-opt
export PATH="$PWD/hermes-solver-opt/cli:$PATH"
```

There is no packaging yet, so there is nothing to install. The tools in `cli/`
are run by name, and each one puts the repository root on `sys.path` itself so
that `import perftest` works. Packaging is on the list; until it lands, `import
perftest` from your own script needs the repository root added by hand.

## Where everything lives

The project is split by lifetime, so that the parts which change fastest never
force a change in the parts which do not.

- `hermes-solver-opt` (this repository, public) — everything durable: rules,
  design, tools. Read `requirements.md` first; it is the source of truth.
- `hermes-perftest` (public, pinned here as a submodule) — the test templates,
  the grid files, the solver recipes and the window generator. Other people use
  these tests, so this project never modifies them.

The record of what was run lives outside both, in a private store: one
`index.tsv` with a row per run, a bundle of extracted evidence per run, and the
analysis that reads them.

## Layout

```
perftest/          the extraction layer: extract, index, store, recipe, verify,
                   log parsing
cli/               the command-line tools, run by name
design.md          how the system is built and why
requirements.md    R1-R25, the rules
search-space.toml  every solver knob the optimiser may set
findings.md        learned conclusions, agent-facing
capture-set.md     what each run records
.beads/            the issue tracker
hermes-perftest/   submodule
```
