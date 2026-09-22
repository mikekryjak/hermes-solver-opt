"""The query tool refuses to summarise a clock across machines.

A wall time only means something against a baseline measured on the same
machine, so a median of wall_s over rows from two machines is one number
made of two clock speeds. Counts of work compare across machines and pass.
"""

import importlib.util
import os

import pytest

from perftest import runner as rn

_spec = importlib.util.spec_from_file_location(
    "query", os.path.join(rn.TOOL_ROOT, "cli", "query.py")
)
query = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(query)

ROWS = [
    {"recipe": "A", "machine": "here", "wall_s": "100", "nl_its": "10"},
    {"recipe": "A", "machine": "there", "wall_s": "50", "nl_its": "11"},
    {"recipe": "B", "machine": "here", "wall_s": "80", "nl_its": "8"},
]


def test_wall_time_is_not_summarised_across_machines():
    with pytest.raises(query.QueryProblem, match="here, there"):
        query.group_rows(ROWS, "recipe", ["wall_s"])


def test_work_counts_cross_machines_and_grouping_by_machine_is_fine():
    summary, columns = query.group_rows(ROWS, "recipe", ["nl_its"])
    assert columns == ["recipe", "n", "nl_its_med"]
    summary, _ = query.group_rows(ROWS, "machine", ["wall_s"])
    assert {s["machine"] for s in summary} == {"here", "there"}
