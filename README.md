# hermes-solver-opt

A framework to optimise Hermes-3 performance by exploring the PETSc solver
parameter space.

This repository is the whole machine: the instructions, the design, the
requirements, the runner, the extractor and the search space. Clone it with
`--recursive` and nothing else is needed to set up, launch, extract and record
a performance test.

```
git clone --recursive https://github.com/mikekryjak/hermes-solver-opt
cd hermes-solver-opt
pip install -e .
```

The install puts five command-line tools on your path -- `extract-test`,
`query-store`, `verify-store`, `add-views` and `can-delete` -- and makes
`import perftest` work from any directory. Reading BOUT.dmp files needs
xhermes as well, which is an optional extra: `pip install -e ".[dumps]"`.

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
pyproject.toml     the packaging: the perftest package and the cli tools
perftest/          the extraction layer: extract, index, store, recipe, verify,
                   log parsing
cli/               the command-line tools, installed by name
design.md          how the system is built and why
requirements.md    R1-R25, the rules
search-space.toml  every solver knob the optimiser may set
findings.md        learned conclusions, agent-facing
capture-set.md     what each run records
.beads/            the issue tracker
hermes-perftest/   submodule
```
