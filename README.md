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
`index.tsv` with a row per run, the schema that explains its columns, and the
analysis that reads them. Nothing per-case is committed there, so the store
stays small.

The evidence bundle for each run sits in the data directory instead, at
`<data>/bundles/<test_id>/`, beside the cases and seeds it came from. That
directory has never been in git.

## Campaigns

Each campaign is one test on one machine. Its findings, with the conclusion
and next steps first, live in `campaigns/<campaign>/findings.md` here, named
after the campaign in the store. Read the root `findings.md` and the file of
the campaign you work on, never another campaign's.

- `test4-jacobian`: test4 on this workstation, September 2026. Concluded: the
  Jacobian is rebuilt every iteration.

## Setting up on a new machine

Every step is a command any agent can run; nothing assumes a particular test,
campaign or host. `design.md` section 4 explains parents, windows and rungs.

1. Clone the three repositories side by side: this one with `--recursive`,
   the user's private results store, and the user's `sdtools`. Install this
   one with `pip install -e .`; the tools need only numpy and pandas, and the
   dump reader is the optional `dumps` extra.
2. Export the four variables the tools read, each an absolute path on this
   machine: `store` (the results store clone), `data` (a directory for cases,
   seeds and bundles, outside git), `hermes` (the Hermes-3 checkout) and
   `sdtools` (that clone, so the recipe tool is found without editing PATH).
3. Build Hermes-3 at the commit and with the settings the campaign's `[build]`
   table will pin, in a build directory named there relative to `hermes`.
4. Make a parent run: copy a test template from `hermes-perftest/`, apply the
   baseline recipe from `hermes-perftest/recipes/`, run it from initial
   conditions to 100 ms as `<test>_0.0-100.0ms-<date>-<tag>` under
   `$data/cases/`, and record it with `extract-test` so it has a row in the
   store's top-level `index.tsv`. Parents never move between machines: each
   machine makes its own.
5. Cut a window with `hermes-perftest/make_window.py` once, by hand, to check
   the seed library fills under `$data/seeds/`. The runner cuts the rest.
6. Copy `campaign.example.toml` to `$store/campaigns/<name>/campaign.toml`.
   Set `[machine] name` to this host's `hostname`, and either keep the
   sdtools launcher line or give one core set per slot and a `taskset` and
   `mpirun` launch line, as the example shows. Name the parent, the build and
   the ladder. The user fills `[approval]`.
7. `run-campaign --campaign <name> --study <file> --dry-run` checks every
   override against the search space without launching. Then run it for real
   on one slot per process, inside a session that survives a logout.

Two machines commit to the same repositories, so every session on either one
syncs the same way: at the start, `bd dolt pull` for the tracker and
`git pull --rebase` in this repository and the store; at the end, `bd dolt
push`, then `git pull --rebase` and `git push` in both. The tracker's
`.beads/issues.jsonl` is a passive export, so if it conflicts on a rebase,
take either side and let the next `bd` command rewrite it. The store's
top-level `index.tsv` merges by union, because each machine only appends its
own parent runs to it, and campaign directories never collide, because each
belongs to one machine.


```
pyproject.toml     the packaging: the perftest package and the cli tools
perftest/          the extraction layer: extract, index, store, recipe, verify,
                   log parsing
cli/               the command-line tools, installed by name
design.md          how the system is built and why
requirements.md    R1-R25, the rules
search-space.toml  every solver knob the optimiser may set
findings.md        cross-campaign conclusions, agent-facing
campaigns/         one findings file per campaign, conclusion first
capture-set.md     what each run records
.beads/            the issue tracker
hermes-perftest/   submodule
```
