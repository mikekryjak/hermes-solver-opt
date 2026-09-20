"""Capturing Hermes-3 performance test results into a durable record.

Deliberately separate from any particular results store: this package knows how
to turn a finished case directory into a bundle plus one index row, and nothing
about whose results they are. The store itself -- the index file, the schema,
the conventions for naming and epochs -- lives in its own repository. The
bundles do not: they are per-case evidence, so they sit in the data directory
beside the cases and seeds they came from.
"""

from .extract import extract_case
from .index import INDEX_COLUMNS, read_index, write_index

__all__ = ["extract_case", "read_index", "write_index", "INDEX_COLUMNS"]
