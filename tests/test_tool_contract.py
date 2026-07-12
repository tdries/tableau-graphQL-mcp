"""Pin the MCP public API: the tool names and their argument schemas.

The tool list and each tool's argument names ARE the contract every downstream
agent binds to. A rename or a changed/removed argument must be a DELIBERATE,
documented change, not something that slips through because only callable-existence
was tested. If this test fails, either you broke the public API by accident, or you
changed it on purpose and must regenerate the snapshot:

    uv run python -c "import sys,json; sys.path.insert(0,'tests'); import test_tool_contract as t; \
open('tests/tool_contract.json','w').write(json.dumps(t._contract(), indent=2, sort_keys=True) + chr(10))"

...and note the change in the CHANGELOG (it is a MAJOR change if a tool/arg is renamed or removed).
"""

import json
from pathlib import Path

from tableau_graphql_mcp import server

_EXPECTED_TOOLS = {
    "graphql_query",
    "introspect_schema",
    "lineage_examples",
    "where_used",
    "impact_analysis",
    "search_content",
    "server_info",
}

_CONTRACT_FILE = Path(__file__).parent / "tool_contract.json"


def _contract() -> dict[str, dict[str, list[str]]]:
    """The current name -> {required args, all args} map, derived from the live tool manager."""
    out: dict[str, dict[str, list[str]]] = {}
    for tool in server.mcp._tool_manager.list_tools():
        schema = tool.parameters or {}
        props = schema.get("properties") or {}
        out[tool.name] = {
            "required": sorted(schema.get("required") or []),
            "props": sorted(props.keys()),
        }
    return out


def test_tool_set_is_exactly_the_seven():
    assert set(_contract().keys()) == _EXPECTED_TOOLS


def test_tool_schema_matches_snapshot():
    expected = json.loads(_CONTRACT_FILE.read_text())
    assert _contract() == expected, (
        "MCP public API changed. If intentional, regenerate tests/tool_contract.json "
        "(see the module docstring) and note it in the CHANGELOG."
    )
