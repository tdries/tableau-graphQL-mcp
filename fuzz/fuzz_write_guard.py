"""Fuzz the read-only guard (`_is_write`), the server's security-critical parser.

Run on Linux with Python 3.12+ (atheris ships Linux wheels only):

    uv run --python 3.12 --group fuzz python fuzz/fuzz_write_guard.py -max_total_time=60

Invariants: the guard never raises, and a top-level mutation appended after any input
that cannot open a string, comment or selection set is always rejected (fail closed).
"""

import sys

import atheris

with atheris.instrument_imports(include=["tableau_graphql_mcp"]):
    from tableau_graphql_mcp.server import _is_write


def test_one_input(data: bytes) -> None:
    doc = atheris.FuzzedDataProvider(data).ConsumeUnicodeNoSurrogates(2048)
    _is_write(doc)  # must never raise
    if not any(c in doc for c in '{}"#'):
        assert _is_write(doc + "\nmutation { x }"), repr(doc)


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
