#!/usr/bin/env python3
"""Run a campaign: prepare, launch, watch, extract, prune, repeat.

Reads the campaign's config and its index, works out which trials have no
result yet, and runs them one at a time on one slot. Interrupt it and run it
again: the index is the only state, so it picks up where it left off.

    run_campaign.py --campaign snes-mumps3-knobs --study lag-jacobian.toml
    run_campaign.py --campaign snes-mumps3-knobs --status
    run_campaign.py --campaign snes-mumps3-knobs --study s.toml --dry-run

The campaign is named, not pathed: it is read from
`<store>/campaigns/<name>/campaign.toml`, and a path may be given instead. The
store, the data directory and the Hermes-3 checkout come from the environment
unless an option names them.

Exit status:

    0  every trial that could run has run
    1  the campaign file or the study is wrong, and the message says how
    2  the campaign has no usable approval, so nothing was launched

Filling all three slots means three of these, one per slot, over separate
studies. The runner watches one run at a time on purpose.
"""

import argparse
import os
import pathlib
import sys

# This repository ships no packaging; cli/ is on $PATH and its tools are run
# by name, so each puts the repository root on the path itself.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from perftest import runner as rn  # noqa: E402
from perftest.campaign import ApprovalMissing, CampaignProblem, load_campaign  # noqa: E402


def campaign_path(named, store_dir):
    """Where this campaign's config is: a path if given one, else by name."""

    if named.endswith(".toml") or os.sep in named:
        return named
    return os.path.join(
        rn.find_store(store_dir), "campaigns", named, "campaign.toml"
    )


def print_status(runner):
    state = runner.status()
    print(f"campaign  {runner.campaign.name}")
    print(f"goal      {runner.campaign.goal}")
    print(f"index     {runner.index_path}")
    print(f"rows      {state['rows']}")
    for name, count in sorted(state["states"].items()):
        print(f"          {count:4d}  {name or '(no state)'}")
    print(
        f"budget    {state['slot_hours_spent']:.1f} of"
        f" {state['slot_hours_budget']:.1f} slot-hours spent"
    )
    print(
        f"disk      {state['free_gb']:.0f} GB free, floor"
        f" {runner.campaign.disk['floor_gb']:.0f} GB"
    )
    if runner.campaign.approval is None:
        print("approval  MISSING: this campaign may not launch anything")
    else:
        print(
            f"approval  {runner.campaign.approval.approved_by} on"
            f" {runner.campaign.approval.approved_on}, "
            f"{runner.campaign.approval.slot_hours:.0f} slot-hours"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--campaign", required=True, help="campaign name, or a path to campaign.toml"
    )
    parser.add_argument("--study", help="study file listing the variants to try")
    parser.add_argument("--store", help="results store (holds campaigns/)")
    parser.add_argument("--data", help="data directory (cases, seeds, bundles)")
    parser.add_argument("--hermes", help="Hermes-3 checkout holding the build")
    parser.add_argument("--recipes", help="directory of recipe files")
    parser.add_argument("--slot", type=int, help="which core slot to run on")
    parser.add_argument(
        "--status", action="store_true", help="say what is done and stop"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="say what it would do, touch nothing"
    )
    args = parser.parse_args()

    try:
        campaign = load_campaign(campaign_path(args.campaign, args.store))
        runner = rn.Runner(
            campaign,
            store_dir=args.store,
            data_dir=args.data,
            hermes_dir=args.hermes,
            recipes_dir=args.recipes,
            slot=args.slot,
            dry_run=args.dry_run,
        )

        if args.status:
            print_status(runner)
            return 0

        if not args.study:
            raise rn.RunnerProblem("no --study: there is nothing to run.")

        space = rn.load_space(
            os.path.join(rn.TOOL_ROOT, campaign.search_space)
        )
        trials = rn.load_study(args.study, campaign, space)
        runner.run(trials)
        return 0

    except ApprovalMissing as refusal:
        # Its own status, because the file is fine and the permission is not.
        print(f"run_campaign.py: NOT APPROVED: {refusal}", file=sys.stderr)
        return 2
    except (CampaignProblem, rn.RunnerProblem) as problem:
        print(f"run_campaign.py: {problem}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("run_campaign.py: interrupted", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
